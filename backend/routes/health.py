from flask import Blueprint, jsonify
import logging

from config import config
from services.database import db_service
from services.query_router import query_router
from services.replication_engine import replication_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'region': config.REGION,
        'service': 'meshnetwork-backend'
    }), 200

@health_bp.route('/status', methods=['GET'])
def detailed_status():
    try:
        db_health = db_service.check_health()
        remote_health = query_router.check_network_health()
        island_status = replication_engine.get_island_mode_status()
        conflict_metrics = replication_engine.get_conflict_metrics()
        partitioning_info = db_service.get_partitioning_info()

        return jsonify({
            'status': 'healthy' if db_health.get('status') == 'healthy' else 'degraded',
            'region': {
                'name': config.REGION,
                'display_name': config.get_region_display_name()
            },
            'database': db_health,
            'partitioning': partitioning_info,
            'island_mode': {
                'active': island_status['is_island'],
                'suspect': island_status.get('is_suspect', False),
                'threshold_seconds': island_status['island_mode_threshold'],
                'isolation_start': island_status['isolation_start'],
                'isolation_duration_seconds': island_status['isolation_duration_seconds'],
                'connected_regions': island_status['connected_regions'],
                'total_regions': island_status['total_regions'],
                'status': 'ISLAND MODE' if island_status['is_island'] else ('SUSPECT' if island_status.get('is_suspect', False) else 'connected')
            },
            'remote_regions': {
                url: 'reachable' if reachable else 'unreachable'
                for url, reachable in remote_health.items()
            },
            'replication_status': island_status['region_details'],
            'conflict_metrics': conflict_metrics,
            'configuration': {
                'sync_interval': config.SYNC_INTERVAL,
                'request_timeout': config.REQUEST_TIMEOUT
            }
        }), 200

    except Exception as e:
        logger.error(f"Error in status check: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500
