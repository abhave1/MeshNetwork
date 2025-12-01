"""
Replication engine for cross-region data synchronization.
Handles asynchronous replication between geographic regions.
"""

import threading
import time
import requests
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from bson import ObjectId

from config import config
from services.database import db_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _serialize_for_json(obj: Any) -> Any:
    """Convert MongoDB objects to JSON-serializable format."""
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_for_json(item) for item in obj]
    return obj


class ReplicationEngine:
    """Manages cross-region data replication."""

    def __init__(self):
        self.local_region = config.REGION
        self.remote_regions = config.REMOTE_REGIONS
        self.sync_interval = config.SYNC_INTERVAL
        self.running = False
        self.sync_thread: Optional[threading.Thread] = None
        self.region_status: Dict[str, Dict[str, Any]] = {}  # Track connectivity per region
        self.conflict_metrics: Dict[str, Any] = {
            'total_conflicts': 0,
            'remote_wins': 0,
            'local_wins': 0,
            'unresolved': 0,
            'by_collection': {},
            'recent_conflicts': []  # Last 10 conflicts
        }
        self.cleanup_counter = 0  # Counter for periodic cleanup

    def start_sync_daemon(self):
        """Start the background synchronization daemon."""
        if self.running:
            logger.warning("Sync daemon is already running")
            return

        self.running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        logger.info(f"Sync daemon started with interval: {self.sync_interval}s")

    def stop_sync_daemon(self):
        """Stop the background synchronization daemon."""
        if not self.running:
            return

        self.running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=5)
        logger.info("Sync daemon stopped")

    def _sync_loop(self):
        """Main synchronization loop."""
        while self.running:
            try:
                # Check for local changes and push to remote regions
                self._push_local_changes()

                # Pull changes from remote regions
                self._pull_remote_changes()

                # Periodic cleanup (every 60 sync cycles = ~5 minutes with 5s interval)
                self.cleanup_counter += 1
                if self.cleanup_counter >= 60:
                    logger.info("Running periodic operation log cleanup")
                    deleted = self.cleanup_old_operations(max_age_hours=24)
                    if deleted > 0:
                        logger.info(f"Cleaned up {deleted} old operations")
                    self.cleanup_counter = 0

            except Exception as e:
                logger.error(f"Error in sync loop: {e}")

            # Wait for next sync interval
            time.sleep(self.sync_interval)

    def _push_local_changes(self):
        """Push local changes to remote regions."""
        try:
            # Get unsynced operations from operation_log
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

            # Try to push to each remote region
            for region_url in self.remote_regions:
                try:
                    self._push_to_region(region_url, operations)
                except Exception as e:
                    logger.error(f"Failed to push to {region_url}: {e}")

        except Exception as e:
            logger.error(f"Error pushing local changes: {e}")

    def _update_region_status(self, region_url: str, is_connected: bool):
        """
        Update connectivity status for a region.

        Args:
            region_url: URL of the region
            is_connected: Whether connection was successful
        """
        now = datetime.utcnow()

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

    def get_island_mode_status(self) -> Dict[str, Any]:
        """
        Get island mode status for this region.

        Returns:
            Dict with island mode info and connectivity status
        """
        connected_regions = sum(1 for s in self.region_status.values() if s.get('connected', False))
        total_regions = len(self.remote_regions)

        # Serialize region details for JSON
        serialized_details = {}
        for region_url, status in self.region_status.items():
            serialized_details[region_url] = {
                'connected': status.get('connected', False),
                'last_success': status['last_success'].isoformat() if status.get('last_success') else None,
                'last_attempt': status['last_attempt'].isoformat() if status.get('last_attempt') else None,
                'consecutive_failures': status.get('consecutive_failures', 0)
            }

        return {
            'is_island': connected_regions == 0 and total_regions > 0,
            'connected_regions': connected_regions,
            'total_regions': total_regions,
            'region_details': serialized_details
        }

    def _push_to_region(self, region_url: str, operations: List[Dict[str, Any]]):
        """
        Push operations to a specific region.

        Args:
            region_url: URL of the target region
            operations: List of operations to push
        """
        try:
            # Convert MongoDB objects to JSON-serializable format
            serializable_ops = [_serialize_for_json(op) for op in operations]

            response = requests.post(
                f"{region_url}/internal/sync",
                json={'operations': serializable_ops},
                timeout=config.REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                # Mark operations as synced to this region
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
        """Pull changes from remote regions."""
        for region_url in self.remote_regions:
            try:
                self._pull_from_region(region_url)
            except Exception as e:
                logger.error(f"Failed to pull from {region_url}: {e}")

    def _pull_from_region(self, region_url: str):
        """
        Pull changes from a specific region.

        Args:
            region_url: URL of the source region
        """
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

                    # Update last sync time to current time
                    self._update_last_sync_time(region_url, datetime.utcnow())

                # Update connectivity status
                self._update_region_status(region_url, True)
            else:
                self._update_region_status(region_url, False)

        except Exception as e:
            logger.error(f"Error pulling from {region_url}: {e}")
            self._update_region_status(region_url, False)

    def _apply_operations(self, operations: List[Dict[str, Any]]):
        """
        Apply operations received from remote regions.

        Args:
            operations: List of operations to apply
        """
        for op in operations:
            try:
                operation_type = op.get('operation_type')
                collection = op.get('collection')
                document_id = op.get('document_id')
                data = op.get('data')

                if operation_type == 'insert':
                    # Check if document already exists
                    existing = db_service.find_one(collection, {f"{collection[:-1]}_id": document_id})
                    if not existing:
                        db_service.insert_one(collection, data)
                        logger.info(f"Applied insert operation for {collection}/{document_id}")
                    else:
                        # Check for conflicts and resolve
                        self._resolve_conflict(collection, document_id, data, existing)

                elif operation_type == 'update':
                    # Update document with conflict resolution
                    existing = db_service.find_one(collection, {f"{collection[:-1]}_id": document_id})
                    if existing:
                        self._resolve_conflict(collection, document_id, data, existing)
                    else:
                        # Document doesn't exist locally, insert it
                        db_service.insert_one(collection, data)
                        logger.info(f"Applied update as insert for {collection}/{document_id}")

                elif operation_type == 'delete':
                    db_service.delete_one(collection, {f"{collection[:-1]}_id": document_id})
                    logger.info(f"Applied delete operation for {collection}/{document_id}")

            except Exception as e:
                logger.error(f"Error applying operation: {e}")

    def _record_conflict(self, collection: str, document_id: str, outcome: str):
        """
        Record a conflict for metrics tracking.

        Args:
            collection: Collection name
            document_id: Document ID
            outcome: 'remote_wins', 'local_wins', or 'unresolved'
        """
        self.conflict_metrics['total_conflicts'] += 1
        self.conflict_metrics[outcome] += 1

        # Track by collection
        if collection not in self.conflict_metrics['by_collection']:
            self.conflict_metrics['by_collection'][collection] = {
                'total': 0,
                'remote_wins': 0,
                'local_wins': 0,
                'unresolved': 0
            }
        self.conflict_metrics['by_collection'][collection]['total'] += 1
        self.conflict_metrics['by_collection'][collection][outcome] += 1

        # Record recent conflict (keep last 10)
        recent = {
            'collection': collection,
            'document_id': document_id,
            'outcome': outcome,
            'timestamp': datetime.utcnow().isoformat()
        }
        self.conflict_metrics['recent_conflicts'].append(recent)
        if len(self.conflict_metrics['recent_conflicts']) > 10:
            self.conflict_metrics['recent_conflicts'].pop(0)

    def get_conflict_metrics(self) -> Dict[str, Any]:
        """Get conflict resolution metrics."""
        return self.conflict_metrics.copy()

    def _resolve_conflict(
        self,
        collection: str,
        document_id: str,
        remote_data: Dict[str, Any],
        local_data: Dict[str, Any]
    ):
        """
        Resolve conflicts using Last-Write-Wins strategy.

        Args:
            collection: Collection name
            document_id: Document ID
            remote_data: Data from remote region
            local_data: Local data
        """
        try:
            # Last-Write-Wins based on timestamp
            remote_time = remote_data.get('last_modified') or remote_data.get('timestamp')
            local_time = local_data.get('last_modified') or local_data.get('timestamp')

            if remote_time and local_time:
                if remote_time > local_time:
                    # Remote data is newer, update local
                    db_service.update_one(
                        collection,
                        {f"{collection[:-1]}_id": document_id},
                        remote_data
                    )
                    logger.info(f"Resolved conflict for {collection}/{document_id} - remote wins")
                    self._record_conflict(collection, document_id, 'remote_wins')
                else:
                    logger.info(f"Resolved conflict for {collection}/{document_id} - local wins")
                    self._record_conflict(collection, document_id, 'local_wins')
            else:
                logger.warning(f"Could not resolve conflict for {collection}/{document_id} - missing timestamps")
                self._record_conflict(collection, document_id, 'unresolved')

        except Exception as e:
            logger.error(f"Error resolving conflict: {e}")

    def _get_last_sync_time(self, region_url: str) -> Optional[str]:
        """
        Get the timestamp of the last successful sync with a region.

        Args:
            region_url: URL of the region

        Returns:
            ISO format timestamp or None
        """
        try:
            # Query sync_metadata collection for last sync time
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
        """
        Update the last successful sync time with a region.

        Args:
            region_url: URL of the region
            sync_time: Timestamp of successful sync
        """
        try:
            # Upsert sync metadata
            metadata = {
                'local_region': self.local_region,
                'remote_region': region_url,
                'last_sync_time': sync_time,
                'last_updated': datetime.utcnow()
            }

            # Check if metadata exists
            existing = db_service.find_one(
                'sync_metadata',
                {
                    'local_region': self.local_region,
                    'remote_region': region_url
                }
            )

            if existing:
                # Update existing metadata
                db_service.update_one(
                    'sync_metadata',
                    {
                        'local_region': self.local_region,
                        'remote_region': region_url
                    },
                    {
                        'last_sync_time': sync_time,
                        'last_updated': datetime.utcnow()
                    }
                )
            else:
                # Insert new metadata
                db_service.insert_one('sync_metadata', metadata)

            logger.info(f"Updated last sync time for {region_url}: {sync_time.isoformat()}")

        except Exception as e:
            logger.error(f"Error updating last sync time for {region_url}: {e}")

    def cleanup_old_operations(self, max_age_hours: int = 24):
        """
        Clean up old synced operations from operation_log.

        Args:
            max_age_hours: Maximum age in hours for operations to keep
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

            # Find operations that are:
            # 1. Older than cutoff_time
            # 2. Synced to all remote regions
            query = {
                'timestamp': {'$lt': cutoff_time},
                'region_origin': self.local_region,
                'synced_to': {'$all': self.remote_regions}  # Synced to all remotes
            }

            # Count operations to delete
            operations = db_service.find_many('operation_log', query)
            count = len(operations)

            if count > 0:
                # Delete old synced operations
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
        """
        Queue an operation for cross-region synchronization.

        Args:
            operation_type: Type of operation (insert, update, delete)
            collection: Collection name
            document_id: Document ID
            data: Document data
        """
        try:
            operation = {
                'operation_type': operation_type,
                'collection': collection,
                'document_id': document_id,
                'data': data,
                'timestamp': datetime.utcnow(),
                'synced_to': [],
                'region_origin': self.local_region
            }

            db_service.insert_one('operation_log', operation)
            logger.info(f"Queued {operation_type} operation for {collection}/{document_id}")

        except Exception as e:
            logger.error(f"Error queuing operation: {e}")


# Create singleton instance
replication_engine = ReplicationEngine()
