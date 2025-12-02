"""
Posts API endpoints.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import logging

from config import config
from services.database import db_service
from services.replication_engine import replication_engine, _serialize_for_json
from services.query_router import query_router
from models.post import Post

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint
posts_bp = Blueprint('posts', __name__, url_prefix='/api')


def _add_timezone_metadata(response_data: dict) -> dict:
    """Add timezone metadata to API responses."""
    response_data['_metadata'] = {
        'timezone': 'UTC',
        'timezone_offset': '+00:00'
    }
    return response_data


@posts_bp.route('/posts', methods=['GET'])
def get_posts():
    """
    Get posts with optional filters.
    Query parameters:
        - post_type: Filter by post type
        - region: Filter by region
        - global: If 'true', query all regions (scatter-gather)
        - limit: Maximum number of results (default: 100)
    """
    try:
        # Get query parameters
        post_type = request.args.get('post_type')
        region = request.args.get('region')
        global_query = request.args.get('global', 'false').lower() == 'true'
        limit = int(request.args.get('limit', 100))

        # Global query: scatter-gather across all regions
        if global_query:
            logger.info("Executing global query across all regions")

            # Build query params for remote regions
            # NOTE: Don't filter by region - we want all posts from remote regions
            # Each remote region will query its entire local database
            params = {'region': 'all'}  # Special value to skip region filtering
            if post_type:
                params['post_type'] = post_type
            if limit:
                params['limit'] = str(limit)

            # Query local region
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

            # Serialize local posts
            local_posts_serialized = [_serialize_for_json(post) for post in local_posts]

            # Scatter-gather from remote regions
            scatter_result = query_router.scatter_gather('/api/posts', params, min_responses=0)
            remote_responses = scatter_result['results']
            query_metadata = scatter_result['metadata']

            logger.info(f"Scatter-gather returned {len(remote_responses)} responses")
            logger.info(f"Response types: {[type(r).__name__ for r in remote_responses]}")
            logger.info(f"Query metadata: {query_metadata}")

            # Extract posts from remote responses
            remote_posts = []
            for response in remote_responses:
                if isinstance(response, dict) and 'posts' in response:
                    logger.info(f"Extracting {len(response['posts'])} posts from dict response")
                    remote_posts.extend(response['posts'])
                elif isinstance(response, list):
                    logger.info(f"Extracting {len(response)} posts from list response")
                    remote_posts.extend(response)
                else:
                    logger.warning(f"Unexpected response type: {type(response)}, content: {response}")

            logger.info(f"Total remote posts extracted: {len(remote_posts)}")

            # Combine local and remote results
            all_posts = local_posts_serialized + remote_posts

            # Merge and sort results
            sorted_posts = query_router.merge_results(all_posts, sort_by='timestamp', reverse=True)

            # Apply limit to combined results
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

        # Regional query: query specific region or local
        else:
            # Build query
            query = {}
            if post_type:
                if not config.validate_post_type(post_type):
                    return jsonify({'error': f'Invalid post type: {post_type}'}), 400
                query['post_type'] = post_type

            if region:
                # Special case: region='all' means query all posts (no region filter)
                if region == 'all':
                    pass  # Don't add region filter
                elif not config.validate_region(region):
                    return jsonify({'error': f'Invalid region: {region}'}), 400
                else:
                    query['region'] = region
            else:
                # Default to local region
                query['region'] = config.REGION

            # Execute query
            posts = db_service.find_many(
                'posts',
                query,
                sort=[('timestamp', -1)],
                limit=limit
            )

            # Convert ObjectId to string for JSON serialization
            for post in posts:
                post['_id'] = str(post['_id'])

            response = {
                'posts': posts,
                'count': len(posts),
                'region': config.REGION
            }
            return jsonify(_add_timezone_metadata(response)), 200

    except Exception as e:
        logger.error(f"Error getting posts: {e}")
        return jsonify({'error': str(e)}), 500


@posts_bp.route('/posts/<post_id>', methods=['GET'])
def get_post(post_id):
    """Get a specific post by ID."""
    try:
        post = db_service.find_one('posts', {'post_id': post_id})

        if not post:
            return jsonify({'error': 'Post not found'}), 404

        # Convert ObjectId to string
        post['_id'] = str(post['_id'])

        return jsonify(post), 200

    except Exception as e:
        logger.error(f"Error getting post {post_id}: {e}")
        return jsonify({'error': str(e)}), 500


@posts_bp.route('/posts', methods=['POST'])
def create_post():
    """
    Create a new post.
    Request body should contain post data.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Create Post object
        post = Post(
            user_id=data.get('user_id'),
            post_type=data.get('post_type'),
            message=data.get('message'),
            location=data.get('location'),
            region=data.get('region', config.REGION),
            capacity=data.get('capacity')
        )

        # Validate post
        is_valid, error_message = post.validate()
        if not is_valid:
            return jsonify({'error': error_message}), 400

        # Insert into database
        post_dict = post.to_dict()
        db_service.insert_one('posts', post_dict)

        # Queue for cross-region replication
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
    """
    Update an existing post.
    Request body should contain fields to update.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Check if post exists
        existing_post = db_service.find_one('posts', {'post_id': post_id})
        if not existing_post:
            return jsonify({'error': 'Post not found'}), 404

        # Update allowed fields
        update_data = {}
        allowed_fields = ['message', 'post_type', 'capacity', 'location']

        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]

        # Add last_modified timestamp
        update_data['last_modified'] = datetime.now(timezone.utc)

        # Update in database
        db_service.update_one('posts', {'post_id': post_id}, update_data)

        # Queue for cross-region replication
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
    """Delete a post."""
    try:
        # Check if post exists
        existing_post = db_service.find_one('posts', {'post_id': post_id})
        if not existing_post:
            return jsonify({'error': 'Post not found'}), 404

        # Delete from database
        db_service.delete_one('posts', {'post_id': post_id})

        # Queue for cross-region replication
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
    """
    Get help requests near a location.
    Query parameters:
        - longitude: Longitude coordinate
        - latitude: Latitude coordinate
        - radius: Search radius in meters (default: 10000)
    """
    try:
        longitude = request.args.get('longitude', type=float)
        latitude = request.args.get('latitude', type=float)
        radius = request.args.get('radius', type=int, default=10000)

        if longitude is None or latitude is None:
            return jsonify({'error': 'Location coordinates required'}), 400

        # Build geospatial query
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

        # Execute query
        help_requests = db_service.find_many('posts', query, limit=50)

        # Convert ObjectId to string
        for req in help_requests:
            req['_id'] = str(req['_id'])

        return jsonify({
            'help_requests': help_requests,
            'count': len(help_requests)
        }), 200

    except Exception as e:
        logger.error(f"Error getting help requests: {e}")
        return jsonify({'error': str(e)}), 500
