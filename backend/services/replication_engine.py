"""
Replication engine for cross-region data synchronization.
Handles asynchronous replication between geographic regions.
"""

import threading
import time
import requests
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from config import config
from services.database import db_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReplicationEngine:
    """Manages cross-region data replication."""

    def __init__(self):
        self.local_region = config.REGION
        self.remote_regions = config.REMOTE_REGIONS
        self.sync_interval = config.SYNC_INTERVAL
        self.running = False
        self.sync_thread: Optional[threading.Thread] = None

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

    def _push_to_region(self, region_url: str, operations: List[Dict[str, Any]]):
        """
        Push operations to a specific region.

        Args:
            region_url: URL of the target region
            operations: List of operations to push
        """
        try:
            response = requests.post(
                f"{region_url}/internal/sync",
                json={'operations': operations},
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
                        }
                    )
                logger.info(f"Successfully pushed {len(operations)} operations to {region_url}")
            else:
                logger.warning(f"Failed to push to {region_url}: {response.status_code}")

        except Exception as e:
            logger.error(f"Error pushing to {region_url}: {e}")

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

        except Exception as e:
            logger.error(f"Error pulling from {region_url}: {e}")

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
                else:
                    logger.info(f"Resolved conflict for {collection}/{document_id} - local wins")
            else:
                logger.warning(f"Could not resolve conflict for {collection}/{document_id} - missing timestamps")

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
        # For MVP, return None to sync all changes
        # In production, track last sync time per region
        return None

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
