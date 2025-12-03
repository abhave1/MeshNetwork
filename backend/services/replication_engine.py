import threading
import time
import requests
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from bson import ObjectId

from config import config
from services.database import db_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _serialize_for_json(obj: Any) -> Any:
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_for_json(item) for item in obj]
    return obj

def _deserialize_timestamps(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return data

    result = data.copy()
    timestamp_fields = ['timestamp', 'last_modified', 'created_at', 'updated_at']

    for field in timestamp_fields:
        if field in result and isinstance(result[field], str):
            try:
                result[field] = datetime.fromisoformat(result[field].replace('Z', '+00:00'))
            except (ValueError, AttributeError) as e:
                logger.warning(f"Failed to parse timestamp field '{field}': {e}")

    return result

class ReplicationEngine:
    def __init__(self):
        self.local_region = config.REGION
        self.remote_regions = config.REMOTE_REGIONS
        self.sync_interval = config.SYNC_INTERVAL
        self.running = False
        self.sync_thread: Optional[threading.Thread] = None
        self.region_status: Dict[str, Dict[str, Any]] = {}
        self.conflict_metrics: Dict[str, Any] = {
            'total_conflicts': 0,
            'remote_wins': 0,
            'local_wins': 0,
            'unresolved': 0,
            'by_collection': {},
            'recent_conflicts': []
        }
        self.cleanup_counter = 0
        self.island_mode_active = False
        self.island_mode_start_time: Optional[datetime] = None
        self.island_mode_threshold = 10

    def start_sync_daemon(self):
        if self.running:
            logger.warning("Sync daemon is already running")
            return

        self.running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        logger.info(f"Sync daemon started with interval: {self.sync_interval}s")

    def stop_sync_daemon(self):
        if not self.running:
            return

        self.running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=5)
        logger.info("Sync daemon stopped")

    def _sync_loop(self):
        while self.running:
            try:
                self._push_local_changes()
                self._pull_remote_changes()

                self.cleanup_counter += 1
                if self.cleanup_counter >= 60:
                    logger.info("Running periodic operation log cleanup")
                    deleted = self.cleanup_old_operations(max_age_hours=24)
                    if deleted > 0:
                        logger.info(f"Cleaned up {deleted} old operations")
                    self.cleanup_counter = 0

            except Exception as e:
                logger.error(f"Error in sync loop: {e}")

            time.sleep(self.sync_interval)

    def _push_local_changes(self):
        try:
            operations = db_service.find_many(
                'operation_log',
                {
                    'region_origin': self.local_region,
                    'synced_to': {'$ne': {'$all': self.remote_regions}}
                },
                limit=100
            )

            if not operations:
                return

            logger.info(f"Found {len(operations)} operations to sync")

            for region_url in self.remote_regions:
                try:
                    self._push_to_region(region_url, operations)
                except Exception as e:
                    logger.error(f"Failed to push to {region_url}: {e}")

        except Exception as e:
            logger.error(f"Error pushing local changes: {e}")

    def _update_region_status(self, region_url: str, is_connected: bool):
        now = datetime.now(timezone.utc)

        if region_url not in self.region_status:
            self.region_status[region_url] = {
                'connected': is_connected,
                'last_success': now if is_connected else None,
                'last_attempt': now,
                'consecutive_failures': 0 if is_connected else 1
            }
        else:
            status = self.region_status[region_url]
            status['connected'] = is_connected
            status['last_attempt'] = now

            if is_connected:
                status['last_success'] = now
                status['consecutive_failures'] = 0
            else:
                status['consecutive_failures'] = status.get('consecutive_failures', 0) + 1

        self._check_island_mode()

    def _check_island_mode(self):
        now = datetime.now(timezone.utc)
        connected_regions = sum(1 for s in self.region_status.values() if s.get('connected', False))
        total_regions = len(self.remote_regions)

        if total_regions == 0:
            if self.island_mode_active:
                logger.info("Exiting island mode - no remote regions configured")
                self.island_mode_active = False
                self.island_mode_start_time = None
            return

        if connected_regions == 0:
            if not self.island_mode_active:
                if self.island_mode_start_time is None:
                    self.island_mode_start_time = now
                    logger.warning(f"All regions disconnected. Island mode will activate in {self.island_mode_threshold}s")
                else:
                    isolation_duration = (now - self.island_mode_start_time).total_seconds()
                    if isolation_duration >= self.island_mode_threshold:
                        self.island_mode_active = True
                        logger.warning(f"ISLAND MODE ACTIVATED - Region isolated for {isolation_duration:.0f}s")
            else:
                isolation_duration = (now - self.island_mode_start_time).total_seconds()
                if int(isolation_duration) % 10 == 0:
                    logger.info(f"Island mode active for {isolation_duration:.0f}s")
        else:
            if self.island_mode_active or self.island_mode_start_time is not None:
                if self.island_mode_active:
                    isolation_duration = (now - self.island_mode_start_time).total_seconds()
                    logger.info(f"ISLAND MODE DEACTIVATED - Connectivity restored after {isolation_duration:.0f}s")
                else:
                    logger.info("Connectivity restored before island mode threshold")

                self.island_mode_active = False
                self.island_mode_start_time = None

    def get_island_mode_status(self) -> Dict[str, Any]:
        connected_regions = sum(1 for s in self.region_status.values() if s.get('connected', False))
        total_regions = len(self.remote_regions)

        isolation_duration = None
        if self.island_mode_start_time:
            isolation_duration = (datetime.now(timezone.utc) - self.island_mode_start_time).total_seconds()

        serialized_details = {}
        for region_url, status in self.region_status.items():
            serialized_details[region_url] = {
                'connected': status.get('connected', False),
                'last_success': status['last_success'].isoformat() if status.get('last_success') else None,
                'last_attempt': status['last_attempt'].isoformat() if status.get('last_attempt') else None,
                'consecutive_failures': status.get('consecutive_failures', 0)
            }

        is_suspect = (connected_regions == 0 and 
                      total_regions > 0 and 
                      self.island_mode_start_time is not None and 
                      not self.island_mode_active)

        return {
            'is_island': self.island_mode_active,
            'is_suspect': is_suspect,
            'island_mode_threshold': self.island_mode_threshold,
            'isolation_start': self.island_mode_start_time.isoformat() if self.island_mode_start_time else None,
            'isolation_duration_seconds': isolation_duration,
            'connected_regions': connected_regions,
            'total_regions': total_regions,
            'region_details': serialized_details
        }

    def _push_to_region(self, region_url: str, operations: List[Dict[str, Any]]):
        try:
            serializable_ops = [_serialize_for_json(op) for op in operations]

            response = requests.post(
                f"{region_url}/internal/sync",
                json={'operations': serializable_ops},
                timeout=config.REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                for op in operations:
                    op_id = op.get('_id')
                    db_service.update_one(
                        'operation_log',
                        {'_id': op_id},
                        {
                            '$addToSet': {'synced_to': region_url}
                        },
                        use_operators=True
                    )
                logger.info(f"Successfully pushed {len(operations)} operations to {region_url}")
                self._update_region_status(region_url, True)
            else:
                logger.warning(f"Failed to push to {region_url}: {response.status_code}")
                self._update_region_status(region_url, False)

        except Exception as e:
            logger.error(f"Error pushing to {region_url}: {e}")
            self._update_region_status(region_url, False)

    def _pull_remote_changes(self):
        for region_url in self.remote_regions:
            try:
                self._pull_from_region(region_url)
            except Exception as e:
                logger.error(f"Failed to pull from {region_url}: {e}")

    def _pull_from_region(self, region_url: str):
        try:
            response = requests.get(
                f"{region_url}/internal/changes",
                params={'since': self._get_last_sync_time(region_url)},
                timeout=config.REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                operations = response.json().get('operations', [])
                if operations:
                    self._apply_operations(operations)
                    logger.info(f"Successfully pulled {len(operations)} operations from {region_url}")
                    self._update_last_sync_time(region_url, datetime.now(timezone.utc))

                self._update_region_status(region_url, True)
            else:
                self._update_region_status(region_url, False)

        except Exception as e:
            logger.error(f"Error pulling from {region_url}: {e}")
            self._update_region_status(region_url, False)

    def _apply_operations(self, operations: List[Dict[str, Any]]):
        for op in operations:
            try:
                operation_type = op.get('operation_type')
                collection = op.get('collection')
                document_id = op.get('document_id')
                data = op.get('data')

                data = _deserialize_timestamps(data)

                if operation_type == 'insert':
                    existing = db_service.find_one(collection, {f"{collection[:-1]}_id": document_id})
                    if not existing:
                        db_service.insert_one(collection, data)
                        logger.info(f"Applied insert operation for {collection}/{document_id}")
                    else:
                        self._resolve_conflict(collection, document_id, data, existing)

                elif operation_type == 'update':
                    existing = db_service.find_one(collection, {f"{collection[:-1]}_id": document_id})
                    if existing:
                        self._resolve_conflict(collection, document_id, data, existing)
                    else:
                        db_service.insert_one(collection, data)
                        logger.info(f"Applied update as insert for {collection}/{document_id}")

                elif operation_type == 'delete':
                    db_service.delete_one(collection, {f"{collection[:-1]}_id": document_id})
                    logger.info(f"Applied delete operation for {collection}/{document_id}")

            except Exception as e:
                logger.error(f"Error applying operation: {e}")

    def _record_conflict(self, collection: str, document_id: str, outcome: str):
        self.conflict_metrics['total_conflicts'] += 1
        self.conflict_metrics[outcome] += 1

        if collection not in self.conflict_metrics['by_collection']:
            self.conflict_metrics['by_collection'][collection] = {
                'total': 0,
                'remote_wins': 0,
                'local_wins': 0,
                'unresolved': 0
            }
        self.conflict_metrics['by_collection'][collection]['total'] += 1
        self.conflict_metrics['by_collection'][collection][outcome] += 1

        recent = {
            'collection': collection,
            'document_id': document_id,
            'outcome': outcome,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        self.conflict_metrics['recent_conflicts'].append(recent)
        if len(self.conflict_metrics['recent_conflicts']) > 10:
            self.conflict_metrics['recent_conflicts'].pop(0)

    def get_conflict_metrics(self) -> Dict[str, Any]:
        return self.conflict_metrics.copy()

    def _resolve_conflict(
        self,
        collection: str,
        document_id: str,
        remote_data: Dict[str, Any],
        local_data: Dict[str, Any]
    ):
        try:
            remote_time = remote_data.get('last_modified') or remote_data.get('timestamp')
            local_time = local_data.get('last_modified') or local_data.get('timestamp')

            if remote_time and isinstance(remote_time, str):
                remote_time = datetime.fromisoformat(remote_time.replace('Z', '+00:00'))
            if local_time and isinstance(local_time, str):
                local_time = datetime.fromisoformat(local_time.replace('Z', '+00:00'))

            if remote_time and local_time:
                if remote_time > local_time:
                    db_service.update_one(
                        collection,
                        {f"{collection[:-1]}_id": document_id},
                        remote_data
                    )
                    logger.info(f"Resolved conflict for {collection}/{document_id} - remote wins")
                    self._record_conflict(collection, document_id, 'remote_wins')
                else:
                    local_has_string_timestamps = (
                        isinstance(local_data.get('timestamp'), str) or
                        isinstance(local_data.get('last_modified'), str)
                    )

                    if local_has_string_timestamps:
                        update_fields = {}
                        if isinstance(local_data.get('timestamp'), str):
                            update_fields['timestamp'] = remote_time if isinstance(remote_time, datetime) else datetime.fromisoformat(str(remote_time).replace('Z', '+00:00'))
                        if isinstance(local_data.get('last_modified'), str):
                            local_modified = local_data.get('last_modified')
                            update_fields['last_modified'] = datetime.fromisoformat(local_modified.replace('Z', '+00:00'))

                        if update_fields:
                            db_service.update_one(
                                collection,
                                {f"{collection[:-1]}_id": document_id},
                                update_fields
                            )
                            logger.info(f"Fixed string timestamps for {collection}/{document_id} - local wins (timestamps corrected)")
                    else:
                        logger.info(f"Resolved conflict for {collection}/{document_id} - local wins")

                    self._record_conflict(collection, document_id, 'local_wins')
            else:
                logger.warning(f"Could not resolve conflict for {collection}/{document_id} - missing timestamps")
                self._record_conflict(collection, document_id, 'unresolved')

        except Exception as e:
            logger.error(f"Error resolving conflict: {e}")

    def _get_last_sync_time(self, region_url: str) -> Optional[str]:
        try:
            metadata = db_service.find_one(
                'sync_metadata',
                {
                    'local_region': self.local_region,
                    'remote_region': region_url
                }
            )

            if metadata and 'last_sync_time' in metadata:
                last_sync = metadata['last_sync_time']
                if isinstance(last_sync, datetime):
                    logger.info(f"Retrieved last sync time for {region_url}: {last_sync.isoformat()}")
                    return last_sync.isoformat()
                logger.info(f"Retrieved last sync time for {region_url}: {last_sync}")
                return last_sync

            logger.info(f"No last sync time found for {region_url}, syncing all operations")
            return None

        except Exception as e:
            logger.error(f"Error getting last sync time for {region_url}: {e}")
            return None

    def _update_last_sync_time(self, region_url: str, sync_time: datetime):
        try:
            metadata = {
                'local_region': self.local_region,
                'remote_region': region_url,
                'last_sync_time': sync_time,
                'last_updated': datetime.now(timezone.utc)
            }

            existing = db_service.find_one(
                'sync_metadata',
                {
                    'local_region': self.local_region,
                    'remote_region': region_url
                }
            )

            if existing:
                db_service.update_one(
                    'sync_metadata',
                    {
                        'local_region': self.local_region,
                        'remote_region': region_url
                    },
                    {
                        'last_sync_time': sync_time,
                        'last_updated': datetime.now(timezone.utc)
                    }
                )
            else:
                db_service.insert_one('sync_metadata', metadata)

            logger.info(f"Updated last sync time for {region_url}: {sync_time.isoformat()}")

        except Exception as e:
            logger.error(f"Error updating last sync time for {region_url}: {e}")

    def cleanup_old_operations(self, max_age_hours: int = 24):
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

            query = {
                'timestamp': {'$lt': cutoff_time},
                'region_origin': self.local_region,
                'synced_to': {'$all': self.remote_regions}
            }

            operations = db_service.find_many('operation_log', query)
            count = len(operations)

            if count > 0:
                collection = db_service.get_collection('operation_log')
                result = collection.delete_many(query)
                logger.info(f"Cleaned up {result.deleted_count} old operations from operation_log")
                return result.deleted_count
            else:
                logger.debug("No old operations to clean up")
                return 0

        except Exception as e:
            logger.error(f"Error cleaning up old operations: {e}")
            return 0

    def queue_operation(
        self,
        operation_type: str,
        collection: str,
        document_id: str,
        data: Dict[str, Any]
    ):
        try:
            operation = {
                'operation_type': operation_type,
                'collection': collection,
                'document_id': document_id,
                'data': data,
                'timestamp': datetime.now(timezone.utc),
                'synced_to': [],
                'region_origin': self.local_region
            }

            db_service.insert_one('operation_log', operation)
            logger.info(f"Queued {operation_type} operation for {collection}/{document_id}")

        except Exception as e:
            logger.error(f"Error queuing operation: {e}")

replication_engine = ReplicationEngine()
