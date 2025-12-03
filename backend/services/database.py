from pymongo import MongoClient, ReadPreference, WriteConcern
from pymongo.errors import ConnectionFailure, OperationFailure
from typing import Optional, Dict, Any, List
import logging

from config import config
from services.partitioning import PartitioningService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db = None
        self.partitioning_service: Optional[PartitioningService] = None
        self._connect()
        self._init_partitioning()

    def _connect(self):
        try:
            logger.info(f"Connecting to MongoDB: {config.MONGODB_URI}")

            read_pref = {
                'primary': ReadPreference.PRIMARY,
                'primaryPreferred': ReadPreference.PRIMARY_PREFERRED,
                'secondary': ReadPreference.SECONDARY,
                'secondaryPreferred': ReadPreference.SECONDARY_PREFERRED
            }.get(config.MONGODB_READ_PREFERENCE, ReadPreference.PRIMARY_PREFERRED)

            write_concern = WriteConcern(w=config.MONGODB_WRITE_CONCERN)

            self.client = MongoClient(
                config.MONGODB_URI,
                replicaSet=config.MONGODB_REPLICA_SET,
                read_preference=read_pref,
                w=write_concern.document['w'],
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000
            )

            self.client.admin.command('ping')
            self.db = self.client[config.MONGODB_DATABASE]

            logger.info(f"Successfully connected to MongoDB replica set: {config.MONGODB_REPLICA_SET}")

        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def _init_partitioning(self):
        try:
            rs_status = self.client.admin.command('replSetGetStatus')
            members = []

            for member in rs_status.get('members', []):
                member_name = member.get('name')
                if member_name:
                    hostname = member_name.split(':')[0]
                    members.append(hostname)

            if members:
                self.partitioning_service = PartitioningService(members)
                logger.info(f"Initialized partitioning service with replica set members: {members}")
            else:
                self.partitioning_service = PartitioningService()
                logger.warning("Could not retrieve replica set members, using default partitioning nodes")

        except Exception as e:
            self.partitioning_service = PartitioningService()
            logger.warning(f"Could not initialize partitioning from replica set: {e}. Using defaults.")

    def get_collection(self, collection_name: str):
        if self.db is None:
            raise RuntimeError("Database connection not established")
        return self.db[collection_name]

    def _get_partition_aware_read_preference(self, user_id: Optional[str] = None) -> ReadPreference:
        if not user_id or not self.partitioning_service:
            return {
                'primary': ReadPreference.PRIMARY,
                'primaryPreferred': ReadPreference.PRIMARY_PREFERRED,
                'secondary': ReadPreference.SECONDARY,
                'secondaryPreferred': ReadPreference.SECONDARY_PREFERRED
            }.get(config.MONGODB_READ_PREFERENCE, ReadPreference.PRIMARY_PREFERRED)

        target_node = self.partitioning_service.get_node_for_user(user_id)
        logger.debug(f"Consistent hash mapped user {user_id} to node {target_node}")

        return ReadPreference.NEAREST

    def check_health(self) -> Dict[str, Any]:
        try:
            self.client.admin.command('ping')
            rs_status = self.client.admin.command('replSetGetStatus')

            members = []
            primary_host = None

            for member in rs_status.get('members', []):
                member_info = {
                    'name': member.get('name'),
                    'state': member.get('stateStr'),
                    'health': member.get('health')
                }
                members.append(member_info)

                if member.get('stateStr') == 'PRIMARY':
                    primary_host = member.get('name')

            health_info = {
                'status': 'healthy',
                'replica_set': rs_status.get('set'),
                'primary': primary_host,
                'members': members,
                'database': config.MONGODB_DATABASE
            }

            if self.partitioning_service:
                health_info['partitioning'] = self.get_partitioning_info()

            return health_info

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

    def get_partitioning_info(self) -> Dict[str, Any]:
        if not self.partitioning_service:
            return {
                'enabled': False,
                'message': 'Partitioning service not initialized'
            }

        try:
            distribution_report = self.partitioning_service.get_distribution_report()
            return {
                'enabled': True,
                'strategy': distribution_report.get('partitioning_strategy'),
                'partition_key': distribution_report.get('partition_key'),
                'nodes': distribution_report.get('nodes'),
                'distribution': distribution_report.get('distribution')
            }
        except Exception as e:
            logger.error(f"Error getting partitioning info: {e}")
            return {
                'enabled': True,
                'error': str(e)
            }

    def insert_one(self, collection_name: str, document: Dict[str, Any]) -> str:
        try:
            collection = self.get_collection(collection_name)
            result = collection.insert_one(document)
            logger.info(f"Inserted document into {collection_name}: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error inserting document into {collection_name}: {e}")
            raise

    def find_one(
        self,
        collection_name: str,
        query: Dict[str, Any],
        use_partitioning: bool = True
    ) -> Optional[Dict[str, Any]]:
        try:
            user_id = query.get('user_id') if use_partitioning else None
            read_pref = self._get_partition_aware_read_preference(user_id)

            collection = self.get_collection(collection_name).with_options(
                read_preference=read_pref
            )

            result = collection.find_one(query)

            if user_id:
                logger.debug(
                    f"Partition-aware query for user {user_id} executed on "
                    f"node with read preference {read_pref}"
                )

            return result
        except Exception as e:
            logger.error(f"Error finding document in {collection_name}: {e}")
            raise

    def find_many(
        self,
        collection_name: str,
        query: Dict[str, Any],
        sort: Optional[List[tuple]] = None,
        skip: Optional[int] = None,
        limit: Optional[int] = None,
        use_partitioning: bool = True
    ) -> List[Dict[str, Any]]:
        try:
            user_id = query.get('user_id') if use_partitioning else None
            read_pref = self._get_partition_aware_read_preference(user_id)

            collection = self.get_collection(collection_name).with_options(
                read_preference=read_pref
            )

            cursor = collection.find(query)

            if sort:
                cursor = cursor.sort(sort)

            if skip:
                cursor = cursor.skip(skip)

            if limit:
                cursor = cursor.limit(limit)

            results = list(cursor)

            if user_id:
                logger.debug(
                    f"Partition-aware query for user {user_id} returned {len(results)} results "
                    f"using read preference {read_pref}"
                )

            return results
        except Exception as e:
            logger.error(f"Error finding documents in {collection_name}: {e}")
            raise

    def count(self, collection_name: str, query: Dict[str, Any]) -> int:
        try:
            collection = self.get_collection(collection_name)
            return collection.count_documents(query)
        except Exception as e:
            logger.error(f"Error counting documents in {collection_name}: {e}")
            raise

    def update_one(
        self,
        collection_name: str,
        query: Dict[str, Any],
        update: Dict[str, Any],
        use_operators: bool = False
    ) -> bool:
        try:
            collection = self.get_collection(collection_name)
            if use_operators:
                result = collection.update_one(query, update)
            else:
                result = collection.update_one(query, {'$set': update})
            logger.info(f"Updated document in {collection_name}: modified={result.modified_count}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating document in {collection_name}: {e}")
            raise

    def delete_one(self, collection_name: str, query: Dict[str, Any]) -> bool:
        try:
            collection = self.get_collection(collection_name)
            result = collection.delete_one(query)
            logger.info(f"Deleted document from {collection_name}: deleted={result.deleted_count}")
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting document from {collection_name}: {e}")
            raise

    def close(self):
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")

db_service = DatabaseService()
