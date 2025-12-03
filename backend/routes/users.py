from flask import Blueprint, request, jsonify
from datetime import datetime
import logging

from config import config
from services.database import db_service
from services.replication_engine import replication_engine
from models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

users_bp = Blueprint('users', __name__, url_prefix='/api')

@users_bp.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    try:
        user = db_service.find_one('users', {'user_id': user_id})

        if not user:
            return jsonify({'error': 'User not found'}), 404

        user['_id'] = str(user['_id'])

        return jsonify(user), 200

    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return jsonify({'error': str(e)}), 500

@users_bp.route('/users', methods=['POST'])
def create_user():
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        user = User(
            name=data.get('name'),
            email=data.get('email'),
            region=data.get('region', config.REGION),
            location=data.get('location'),
            verified=data.get('verified', False),
            reputation=data.get('reputation', 0)
        )

        is_valid, error_message = user.validate()
        if not is_valid:
            return jsonify({'error': error_message}), 400

        existing_user = db_service.find_one('users', {'email': user.email})
        if existing_user:
            return jsonify({'error': 'User with this email already exists'}), 409

        user_dict = user.to_dict()
        db_service.insert_one('users', user_dict)

        replication_engine.queue_operation(
            'insert',
            'users',
            user.user_id,
            user_dict
        )

        logger.info(f"Created user {user.user_id} ({user.email})")

        return jsonify({
            'message': 'User created successfully',
            'user_id': user.user_id,
            'region': config.REGION
        }), 201

    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return jsonify({'error': str(e)}), 500

@users_bp.route('/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        existing_user = db_service.find_one('users', {'user_id': user_id})
        if not existing_user:
            return jsonify({'error': 'User not found'}), 404

        update_data = {}
        allowed_fields = ['name', 'location', 'verified', 'reputation']

        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]

        db_service.update_one('users', {'user_id': user_id}, update_data)

        replication_engine.queue_operation(
            'update',
            'users',
            user_id,
            update_data
        )

        logger.info(f"Updated user {user_id}")

        return jsonify({
            'message': 'User updated successfully',
            'user_id': user_id
        }), 200

    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        return jsonify({'error': str(e)}), 500

@users_bp.route('/mark-safe', methods=['POST'])
def mark_user_safe():
    try:
        data = request.get_json()

        if not data or 'user_id' not in data:
            return jsonify({'error': 'user_id is required'}), 400

        user_id = data['user_id']

        existing_user = db_service.find_one('users', {'user_id': user_id})
        if not existing_user:
            return jsonify({'error': 'User not found'}), 404

        from models.post import Post

        safety_post = Post(
            user_id=user_id,
            post_type='safety',
            message=f"{existing_user.get('name', 'User')} marked themselves as safe",
            location=existing_user.get('location'),
            region=existing_user.get('region', config.REGION)
        )

        post_dict = safety_post.to_dict()
        db_service.insert_one('posts', post_dict)

        replication_engine.queue_operation(
            'insert',
            'posts',
            safety_post.post_id,
            post_dict
        )

        logger.info(f"User {user_id} marked as safe")

        return jsonify({
            'message': 'User marked as safe',
            'user_id': user_id,
            'post_id': safety_post.post_id
        }), 200

    except Exception as e:
        logger.error(f"Error marking user safe: {e}")
        return jsonify({'error': str(e)}), 500
