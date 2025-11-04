"""
Configuration management for MeshNetwork backend.
Loads settings from environment variables.
"""

import os
import json


class Config:
    """Application configuration class."""

    # Flask settings
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

    # Region settings
    REGION = os.getenv('REGION', 'north_america')

    # MongoDB settings
    MONGODB_URI = os.getenv(
        'MONGODB_URI',
        'mongodb://localhost:27017/meshnetwork'
    )
    MONGODB_REPLICA_SET = os.getenv('MONGODB_REPLICA_SET', 'rs-na')
    MONGODB_DATABASE = 'meshnetwork'

    # Write concern for MongoDB (majority ensures data is written to majority of replica set)
    MONGODB_WRITE_CONCERN = 'majority'

    # Read preference (primaryPreferred means read from primary if available, else secondary)
    MONGODB_READ_PREFERENCE = 'primaryPreferred'

    # Cross-region replication settings
    REMOTE_REGIONS_STR = os.getenv('REMOTE_REGIONS', '[]')
    try:
        REMOTE_REGIONS = json.loads(REMOTE_REGIONS_STR)
    except json.JSONDecodeError:
        REMOTE_REGIONS = []

    SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL', 5))  # seconds

    # Timeout settings for cross-region requests
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', 3))  # seconds

    # Valid post types
    VALID_POST_TYPES = [
        'shelter',
        'food',
        'medical',
        'water',
        'safety',
        'help'
    ]

    # Valid regions
    VALID_REGIONS = [
        'north_america',
        'europe',
        'asia_pacific'
    ]

    @classmethod
    def get_region_display_name(cls):
        """Get human-readable region name."""
        region_names = {
            'north_america': 'North America',
            'europe': 'Europe',
            'asia_pacific': 'Asia-Pacific'
        }
        return region_names.get(cls.REGION, cls.REGION)

    @classmethod
    def validate_region(cls, region):
        """Validate if region is valid."""
        return region in cls.VALID_REGIONS

    @classmethod
    def validate_post_type(cls, post_type):
        """Validate if post type is valid."""
        return post_type in cls.VALID_POST_TYPES


# Create a singleton instance
config = Config()
