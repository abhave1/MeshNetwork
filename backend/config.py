import os
import json

class Config:
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5010))
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

    REGION = os.getenv('REGION', 'north_america')

    MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/meshnetwork')
    MONGODB_REPLICA_SET = os.getenv('MONGODB_REPLICA_SET', 'rs-na')
    MONGODB_DATABASE = 'meshnetwork'
    MONGODB_WRITE_CONCERN = 'majority'
    MONGODB_READ_PREFERENCE = 'primaryPreferred'

    REMOTE_REGIONS_STR = os.getenv('REMOTE_REGIONS', '[]')
    try:
        REMOTE_REGIONS = json.loads(REMOTE_REGIONS_STR)
    except json.JSONDecodeError:
        REMOTE_REGIONS = []

    SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL', 5))
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', 3))

    VALID_POST_TYPES = [
        'shelter', 'food', 'medical', 'water', 'safety', 'help'
    ]

    VALID_REGIONS = [
        'north_america', 'europe', 'asia_pacific'
    ]

    @classmethod
    def get_region_display_name(cls):
        region_names = {
            'north_america': 'North America',
            'europe': 'Europe',
            'asia_pacific': 'Asia-Pacific'
        }
        return region_names.get(cls.REGION, cls.REGION)

    @classmethod
    def validate_region(cls, region):
        return region in cls.VALID_REGIONS

    @classmethod
    def validate_post_type(cls, post_type):
        return post_type in cls.VALID_POST_TYPES

config = Config()
