"""
Database service for MongoDB connection and operations.
"""

from pymongo import MongoClient, ReadPreference, WriteConcern
from pymongo.errors import ConnectionFailure, OperationFailure
from typing import Optional, Dict, Any, List
import logging

from config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseService:
    """Manages MongoDB connection and provides database operations."""

    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db = None
        self._connect()

    def _connect(self):
        """Establish connection to MongoDB replica set."""
        try:
            logger.info(f"Connecting to MongoDB: {config.MONGODB_URI}")

            # Set read preference based on config
            read_pref = {
                'primary': ReadPreference.PRIMARY,
                'primaryPreferred': ReadPreference.PRIMARY_PREFERRED,
                'secondary': ReadPreference.SECONDARY,
                'secondaryPreferred': ReadPreference.SECONDARY_PREFERRED
            }.get(config.MONGODB_READ_PREFERENCE, ReadPreference.PRIMARY_PREFERRED)

            # Set write concern
            write_concern = WriteConcern(w=config.MONGODB_WRITE_CONCERN)

            # Create MongoDB client
            self.client = MongoClient(
                config.MONGODB_URI,
                replicaSet=config.MONGODB_REPLICA_SET,
                read_preference=read_pref,
                w=write_concern.document['w'],
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000
            )

            # Test connection
            self.client.admin.command('ping')

            # Get database
            self.db = self.client[config.MONGODB_DATABASE]

            logger.info(f"Successfully connected to MongoDB replica set: {config.MONGODB_REPLICA_SET}")

        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    def get_collection(self, collection_name: str):
        """Get a MongoDB collection."""
        if self.db is None:
            raise RuntimeError("Database connection not established")
        return self.db[collection_name]

    def check_health(self) -> Dict[str, Any]:
        """
        Check database health and replica set status.
        Returns health information.
        """
        try:
            # Ping database
            self.client.admin.command('ping')

            # Get replica set status
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

            return {
                'status': 'healthy',
                'replica_set': rs_status.get('set'),
                'primary': primary_host,
                'members': members,
                'database': config.MONGODB_DATABASE
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

    def insert_one(self, collection_name: str, document: Dict[str, Any]) -> str:
        """
        Insert a single document.
        Returns the inserted document ID.
        """
        try:
            collection = self.get_collection(collection_name)
            result = collection.insert_one(document)
            logger.info(f"Inserted document into {collection_name}: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error inserting document into {collection_name}: {e}")
            raise

    def find_one(self, collection_name: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find a single document matching the query."""
        try:
            collection = self.get_collection(collection_name)
            result = collection.find_one(query)
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
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Find multiple documents matching the query with pagination support."""
        try:
            collection = self.get_collection(collection_name)
            cursor = collection.find(query)

            if sort:
                cursor = cursor.sort(sort)

            if skip:
                cursor = cursor.skip(skip)

            if limit:
                cursor = cursor.limit(limit)

            results = list(cursor)
            return results
        except Exception as e:
            logger.error(f"Error finding documents in {collection_name}: {e}")
            raise

    def count(self, collection_name: str, query: Dict[str, Any]) -> int:
        """Count documents matching the query."""
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
        """
        Update a single document.

        Args:
            collection_name: Name of the collection
            query: Query to find the document
            update: Update data or update operators
            use_operators: If True, update contains operators like $set, $addToSet etc.
                          If False, wraps update in {'$set': update}

        Returns:
            True if document was modified.
        """
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
        """
        Delete a single document.
        Returns True if document was deleted.
        """
        try:
            collection = self.get_collection(collection_name)
            result = collection.delete_one(query)
            logger.info(f"Deleted document from {collection_name}: deleted={result.deleted_count}")
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting document from {collection_name}: {e}")
            raise

    def close(self):
        """Close database connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")


# Create singleton instance
db_service = DatabaseService()
