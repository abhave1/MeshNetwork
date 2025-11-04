"""
Main Flask application for MeshNetwork backend.
Disaster Resilient Social Platform - Distributed Database System
"""

from flask import Flask, jsonify
from flask_cors import CORS
import logging
import sys

from config import config
from services.database import db_service
from services.replication_engine import replication_engine
from routes import health_bp, posts_bp, users_bp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def create_app():
    """Create and configure Flask application."""
    app = Flask(__name__)

    # Enable CORS for all routes
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(posts_bp)
    app.register_blueprint(users_bp)

    # Root endpoint
    @app.route('/', methods=['GET'])
    def root():
        return jsonify({
            'service': 'MeshNetwork Backend',
            'region': config.get_region_display_name(),
            'version': '1.0.0',
            'endpoints': {
                'health': '/health',
                'status': '/status',
                'posts': '/api/posts',
                'users': '/api/users'
            }
        }), 200

    # Internal endpoints for cross-region sync
    @app.route('/internal/sync', methods=['POST'])
    def receive_sync():
        """Receive sync operations from other regions."""
        from flask import request

        try:
            data = request.get_json()
            operations = data.get('operations', [])

            if not operations:
                return jsonify({'message': 'No operations provided'}), 400

            # Apply operations
            replication_engine._apply_operations(operations)

            return jsonify({
                'message': 'Operations applied successfully',
                'count': len(operations)
            }), 200

        except Exception as e:
            logger.error(f"Error receiving sync: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/internal/changes', methods=['GET'])
    def get_changes():
        """Provide recent changes for other regions to sync."""
        from flask import request

        try:
            since = request.args.get('since')

            # Build query
            query = {'region_origin': config.REGION}
            if since:
                query['timestamp'] = {'$gt': since}

            # Get recent operations
            operations = db_service.find_many(
                'operation_log',
                query,
                sort=[('timestamp', 1)],
                limit=100
            )

            # Convert ObjectId to string
            for op in operations:
                op['_id'] = str(op['_id'])

            return jsonify({
                'operations': operations,
                'count': len(operations)
            }), 200

        except Exception as e:
            logger.error(f"Error getting changes: {e}")
            return jsonify({'error': str(e)}), 500

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({'error': 'Internal server error'}), 500

    return app


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("MeshNetwork Backend Starting")
    logger.info(f"Region: {config.get_region_display_name()}")
    logger.info(f"Port: {config.FLASK_PORT}")
    logger.info(f"MongoDB: {config.MONGODB_URI}")
    logger.info(f"Remote Regions: {config.REMOTE_REGIONS}")
    logger.info("=" * 60)

    try:
        # Test database connection
        db_health = db_service.check_health()
        if db_health.get('status') == 'healthy':
            logger.info("✓ Database connection successful")
            logger.info(f"✓ Replica Set: {db_health.get('replica_set')}")
            logger.info(f"✓ Primary: {db_health.get('primary')}")
        else:
            logger.error("✗ Database connection failed")
            logger.error(f"Error: {db_health.get('error')}")
            sys.exit(1)

        # Start replication engine
        logger.info("Starting replication engine...")
        replication_engine.start_sync_daemon()
        logger.info("✓ Replication engine started")

        # Create Flask app
        app = create_app()

        # Run Flask app
        logger.info(f"Starting Flask server on port {config.FLASK_PORT}...")
        app.run(
            host='0.0.0.0',
            port=config.FLASK_PORT,
            debug=config.DEBUG
        )

    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
        replication_engine.stop_sync_daemon()
        db_service.close()
        sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
