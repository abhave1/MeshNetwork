from flask import Flask, jsonify
from flask_cors import CORS
import logging
import sys

from config import config
from services.database import db_service
from services.replication_engine import replication_engine
from routes import health_bp, posts_bp, users_bp

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)

    CORS(app, resources={r"/*": {"origins": "*"}})

    app.register_blueprint(health_bp)
    app.register_blueprint(posts_bp)
    app.register_blueprint(users_bp)

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

    @app.route('/internal/sync', methods=['POST'])
    def receive_sync():
        from flask import request
        try:
            data = request.get_json()
            operations = data.get('operations', [])

            if not operations:
                return jsonify({'message': 'No operations provided'}), 400

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
        from flask import request
        from services.replication_engine import _serialize_for_json
        from datetime import datetime

        try:
            since = request.args.get('since')
            query = {'region_origin': config.REGION}
            
            if since:
                try:
                    since_datetime = datetime.fromisoformat(since.replace('Z', '+00:00'))
                    query['timestamp'] = {'$gt': since_datetime}
                except ValueError:
                    logger.warning(f"Invalid since timestamp format: {since}")

            operations = db_service.find_many(
                'operation_log',
                query,
                sort=[('timestamp', 1)],
                limit=100
            )

            serializable_ops = [_serialize_for_json(op) for op in operations]

            return jsonify({
                'operations': serializable_ops,
                'count': len(serializable_ops)
            }), 200

        except Exception as e:
            logger.error(f"Error getting changes: {e}")
            return jsonify({'error': str(e)}), 500

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({'error': 'Internal server error'}), 500

    return app

def main():
    logger.info("MeshNetwork Backend Starting")
    logger.info(f"Region: {config.get_region_display_name()}")
    logger.info(f"Port: {config.FLASK_PORT}")

    try:
        db_health = db_service.check_health()
        if db_health.get('status') == 'healthy':
            logger.info("Database connection successful")
        else:
            logger.error("Database connection failed")
            sys.exit(1)

        logger.info("Starting replication engine...")
        replication_engine.start_sync_daemon()

        app = create_app()

        logger.info(f"Starting Flask server on port {config.FLASK_PORT}...")
        app.run(
            host='0.0.0.0',
            port=config.FLASK_PORT,
            debug=config.DEBUG
        )

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        replication_engine.stop_sync_daemon()
        db_service.close()
        sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
