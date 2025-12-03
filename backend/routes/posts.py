from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import logging

from config import config
from services.database import db_service
from services.replication_engine import replication_engine, _serialize_for_json
from services.query_router import query_router
from models.post import Post

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

posts_bp = Blueprint('posts', __name__, url_prefix='/api')

def _add_timezone_metadata(response_data: dict) -> dict:
    response_data['_metadata'] = {
        'timezone': 'UTC',
        'timezone_offset': '+00:00'
    }
    return response_data

@posts_bp.route('/posts', methods=['GET'])
def get_posts():
    try:
        post_type = request.args.get('post_type')
        region = request.args.get('region')
        global_query = request.args.get('global', 'false').lower() == 'true'
        limit = int(request.args.get('limit', 100))
        skip = int(request.args.get('skip', 0))

        if global_query:
            logger.info("Executing global query across all regions")

            params = {'region': 'all'}
            if post_type:
                params['post_type'] = post_type
            if limit:
                params['limit'] = str(limit)

            local_query = {}
            if post_type:
                if not config.validate_post_type(post_type):
                    return jsonify({'error': f'Invalid post type: {post_type}'}), 400
                local_query['post_type'] = post_type

            local_posts = db_service.find_many(
                'posts',
                local_query,
                sort=[('timestamp', -1)],
                limit=limit
            )

            local_posts_serialized = [_serialize_for_json(post) for post in local_posts]

            scatter_result = query_router.scatter_gather('/api/posts', params, min_responses=0)
            remote_responses = scatter_result['results']
            query_metadata = scatter_result['metadata']

            logger.info(f"Scatter-gather returned {len(remote_responses)} responses")

            remote_posts = []
            for response in remote_responses:
                if isinstance(response, dict) and 'posts' in response:
                    remote_posts.extend(response['posts'])
                elif isinstance(response, list):
                    remote_posts.extend(response)
                else:
                    logger.warning(f"Unexpected response type: {type(response)}, content: {response}")

            all_posts = local_posts_serialized + remote_posts
            sorted_posts = query_router.merge_results(all_posts, sort_by='timestamp', reverse=True)
            final_posts = sorted_posts[:limit]

            response = {
                'posts': final_posts,
                'count': len(final_posts),
                'region': 'global',
                'sources': {
                    'local': len(local_posts_serialized),
                    'remote': len(remote_posts)
                },
                'query_metadata': query_metadata
            }
            return jsonify(_add_timezone_metadata(response)), 200

        else:
            query = {}
            if post_type:
                if not config.validate_post_type(post_type):
                    return jsonify({'error': f'Invalid post type: {post_type}'}), 400
                query['post_type'] = post_type

            if region:
                if region == 'all':
                    pass
                elif not config.validate_region(region):
                    return jsonify({'error': f'Invalid region: {region}'}), 400
                else:
                    query['region'] = region
            else:
                query['region'] = config.REGION

            total_count = db_service.count('posts', query)

            posts = db_service.find_many(
                'posts',
                query,
                sort=[('timestamp', -1)],
                skip=skip,
                limit=limit
            )

            for post in posts:
                post['_id'] = str(post['_id'])

            response = {
                'posts': posts,
                'count': len(posts),
                'total_count': total_count,
                'skip': skip,
                'limit': limit,
                'region': config.REGION
            }
            return jsonify(_add_timezone_metadata(response)), 200

    except Exception as e:
        logger.error(f"Error getting posts: {e}")
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/posts/<post_id>', methods=['GET'])
def get_post(post_id):
    try:
        post = db_service.find_one('posts', {'post_id': post_id})

        if not post:
            return jsonify({'error': 'Post not found'}), 404

        post['_id'] = str(post['_id'])

        return jsonify(post), 200

    except Exception as e:
        logger.error(f"Error getting post {post_id}: {e}")
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/posts', methods=['POST'])
def create_post():
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        post = Post(
            user_id=data.get('user_id'),
            post_type=data.get('post_type'),
            message=data.get('message'),
            location=data.get('location'),
            region=data.get('region', config.REGION),
            capacity=data.get('capacity')
        )

        is_valid, error_message = post.validate()
        if not is_valid:
            return jsonify({'error': error_message}), 400

        post_dict = post.to_dict()
        db_service.insert_one('posts', post_dict)

        replication_engine.queue_operation(
            'insert',
            'posts',
            post.post_id,
            post_dict
        )

        logger.info(f"Created post {post.post_id} by user {post.user_id}")

        return jsonify({
            'message': 'Post created successfully',
            'post_id': post.post_id,
            'region': config.REGION
        }), 201

    except Exception as e:
        logger.error(f"Error creating post: {e}")
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/posts/<post_id>', methods=['PUT'])
def update_post(post_id):
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        existing_post = db_service.find_one('posts', {'post_id': post_id})
        if not existing_post:
            return jsonify({'error': 'Post not found'}), 404

        update_data = {}
        allowed_fields = ['message', 'post_type', 'capacity', 'location']

        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]

        update_data['last_modified'] = datetime.now(timezone.utc)

        db_service.update_one('posts', {'post_id': post_id}, update_data)

        replication_engine.queue_operation(
            'update',
            'posts',
            post_id,
            update_data
        )

        logger.info(f"Updated post {post_id}")

        return jsonify({
            'message': 'Post updated successfully',
            'post_id': post_id
        }), 200

    except Exception as e:
        logger.error(f"Error updating post {post_id}: {e}")
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/posts/<post_id>', methods=['DELETE'])
def delete_post(post_id):
    try:
        existing_post = db_service.find_one('posts', {'post_id': post_id})
        if not existing_post:
            return jsonify({'error': 'Post not found'}), 404

        db_service.delete_one('posts', {'post_id': post_id})

        replication_engine.queue_operation(
            'delete',
            'posts',
            post_id,
            {}
        )

        logger.info(f"Deleted post {post_id}")

        return jsonify({
            'message': 'Post deleted successfully',
            'post_id': post_id
        }), 200

    except Exception as e:
        logger.error(f"Error deleting post {post_id}: {e}")
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/help-requests', methods=['GET'])
def get_help_requests():
    try:
        longitude = request.args.get('longitude', type=float)
        latitude = request.args.get('latitude', type=float)
        radius = request.args.get('radius', type=int, default=10000)

        if longitude is None or latitude is None:
            return jsonify({'error': 'Location coordinates required'}), 400

        query = {
            'post_type': 'help',
            'location': {
                '$near': {
                    '$geometry': {
                        'type': 'Point',
                        'coordinates': [longitude, latitude]
                    },
                    '$maxDistance': radius
                }
            }
        }

        help_requests = db_service.find_many('posts', query, limit=50)

        for req in help_requests:
            req['_id'] = str(req['_id'])

        return jsonify({
            'help_requests': help_requests,
            'count': len(help_requests)
        }), 200

    except Exception as e:
        logger.error(f"Error getting help requests: {e}")
        return jsonify({'error': str(e)}), 500

@posts_bp.route('/partitioning/stats', methods=['GET'])
def get_partitioning_stats():
    try:
        partitioning_info = db_service.get_partitioning_info()

        return jsonify({
            'region': config.REGION,
            'partitioning': partitioning_info,
            'description': 'Consistent hashing distributes user data across replica set nodes for load balancing'
        }), 200

    except Exception as e:
        logger.error(f"Error getting partitioning stats: {e}")
        return jsonify({'error': str(e)}), 500
