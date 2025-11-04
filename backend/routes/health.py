"""
Health check and status endpoints.
"""

from flask import Blueprint, jsonify
import logging

from config import config
from services.database import db_service
from services.query_router import query_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint
health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    Basic health check endpoint.
    Returns 200 if service is running.
    """
    return jsonify({
        'status': 'healthy',
        'region': config.REGION,
        'service': 'meshnetwork-backend'
    }), 200


@health_bp.route('/status', methods=['GET'])
def detailed_status():
    """
    Detailed status endpoint.
    Returns comprehensive information about service health.
    """
    try:
        # Check database health
        db_health = db_service.check_health()

        # Check connectivity to remote regions
        remote_health = query_router.check_network_health()

        return jsonify({
            'status': 'healthy' if db_health.get('status') == 'healthy' else 'degraded',
            'region': {
                'name': config.REGION,
                'display_name': config.get_region_display_name()
            },
            'database': db_health,
            'remote_regions': {
                url: 'reachable' if reachable else 'unreachable'
                for url, reachable in remote_health.items()
            },
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
