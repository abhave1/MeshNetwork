"""
Data generator for MeshNetwork MongoDB databases.
Generates 10,000 users and 100 posts per user (1,000,000 posts total).
Distributes data across NA, EU, and AP regional databases.
Creates operation logs after each batch insert for replication purposes.
"""

import random
import uuid
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, WriteConcern
from faker import Faker
from typing import List, Dict, Any
import sys


# MongoDB connection URIs for each region
# Use directConnection for simplicity, but write to the same database the backends use
MONGO_URIS = {
    'NA': 'mongodb://localhost:27017/?directConnection=true',
    'EU': 'mongodb://localhost:27020/?directConnection=true',
    'AP': 'mongodb://localhost:27023/?directConnection=true'
}

# Different timestamp ranges for each region (days ago)
REGION_TIME_RANGES = {
    'NA': (0, 10),    # Recent posts (0-10 days ago)
    'EU': (5, 15),    # Mix of recent and older (5-15 days ago)
    'AP': (10, 20)    # Older posts (10-20 days ago)
}

DATABASE_NAME = 'meshnetwork'

# Region configuration with realistic coordinates
REGIONS = {
    'NA': {
        'name': 'north_america',
        'lon_range': (-130, -70),   # North America longitudes
        'lat_range': (25, 50)        # North America latitudes
    },
    'EU': {
        'name': 'europe',
        'lon_range': (-10, 40),      # Europe longitudes
        'lat_range': (35, 60)        # Europe latitudes
    },
    'AP': {
        'name': 'asia_pacific',
        'lon_range': (100, 150),     # Asia-Pacific longitudes
        'lat_range': (-40, 40)       # Asia-Pacific latitudes
    }
}

# Post type templates
POST_TYPES = ['shelter', 'food', 'medical', 'water', 'safety', 'help']

POST_MESSAGES = {
    'shelter': [
        'Red Cross shelter open - beds available',
        'Emergency shelter accepting families',
        'Community center shelter - 24/7 access',
        'Temporary housing available',
        'School gymnasium converted to shelter',
        'Church basement shelter open',
        'Safe shelter with medical support',
        'Overnight shelter - meals provided'
    ],
    'food': [
        'Food distribution center open',
        'Hot meals served 3x daily',
        'Emergency food bank operational',
        'Free meal service - no questions asked',
        'Community kitchen serving hot food',
        'Food donations being distributed',
        'Grocery assistance available',
        'Soup kitchen open for all'
    ],
    'medical': [
        'Medical clinic providing free care',
        'First aid station open 24/7',
        'Paramedic station operational',
        'Mobile medical unit on site',
        'Emergency medical services available',
        'Pharmacy dispensing free medications',
        'Trauma care facility open',
        'Medical volunteers providing care'
    ],
    'water': [
        'Clean water available - bring containers',
        'Bottled water distribution point',
        'Water purification station operational',
        'Potable water available here',
        'Emergency water supplies',
        'Water tanker on location',
        'Safe drinking water - free access',
        'Water dispensing station'
    ],
    'safety': [
        'Safe zone established here',
        'Evacuation route open to north',
        'Road closed due to flooding - avoid area',
        'Police checkpoint - safe passage',
        'Security presence - area secured',
        'Danger: structural damage ahead',
        'Safe assembly point marked',
        'Emergency exit route clear'
    ],
    'help': [
        'Need medical supplies urgently',
        'Seeking volunteers for rescue',
        'Family separated - looking for help',
        'Trapped residents need assistance',
        'Elderly person needs evacuation',
        'Child separated from parents',
        'Urgent: need transportation',
        'Requesting rescue team'
    ]
}

# Configuration
NUM_USERS = 10000
POSTS_PER_USER = 100
BATCH_SIZE = 1000  # Insert in batches for performance


def get_random_location(region_code: str) -> Dict[str, Any]:
    """Generate random GeoJSON location for a region."""
    region = REGIONS[region_code]
    lon = random.uniform(*region['lon_range'])
    lat = random.uniform(*region['lat_range'])

    return {
        'type': 'Point',
        'coordinates': [round(lon, 6), round(lat, 6)]
    }


def generate_user(faker: Faker, region_code: str) -> Dict[str, Any]:
    """Generate a single user document."""
    return {
        'user_id': str(uuid.uuid4()),
        'name': faker.name(),
        'email': faker.email(),
        'region': REGIONS[region_code]['name'],
        'location': get_random_location(region_code),
        'verified': random.choice([True, False]),
        'reputation': random.randint(0, 100),
        'created_at': datetime.now(timezone.utc) - timedelta(days=random.randint(0, 90))
    }


def generate_post(user_id: str, region_code: str) -> Dict[str, Any]:
    """Generate a single post document with region-specific timestamps."""
    post_type = random.choice(POST_TYPES)
    message = random.choice(POST_MESSAGES[post_type])

    # Use region-specific time range
    time_range = REGION_TIME_RANGES.get(region_code, (0, 30))
    days_ago = random.randint(*time_range)
    hours_ago = random.randint(0, 23)
    minutes_ago = random.randint(0, 59)

    post_time = datetime.now(timezone.utc) - timedelta(
        days=days_ago,
        hours=hours_ago,
        minutes=minutes_ago
    )

    post = {
        'post_id': str(uuid.uuid4()),
        'user_id': user_id,
        'post_type': post_type,
        'message': message,
        'location': get_random_location(region_code),
        'region': REGIONS[region_code]['name'],
        'timestamp': post_time,
        'last_modified': post_time
    }

    # Add capacity only for shelter posts
    if post_type == 'shelter':
        post['capacity'] = random.randint(10, 200)

    return post


def log_operation(db, operation_type: str, region_code: str, documents: List[Dict[str, Any]]):
    """Log an operation to the operation_logs collection for replication."""
    operation_log = {
        'operation_id': str(uuid.uuid4()),
        'operation_type': operation_type,  # 'insert_users' or 'insert_posts'
        'region': REGIONS[region_code]['name'],
        'timestamp': datetime.now(timezone.utc),
        'count': len(documents),
        'documents': documents,  # Store the actual documents for replication
        'status': 'completed'
    }
    db.operation_logs.insert_one(operation_log)


def print_progress(current: int, total: int, prefix: str = ''):
    """Print progress bar."""
    bar_length = 50
    filled_length = int(bar_length * current // total)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    percent = 100 * (current / float(total))
    sys.stdout.write(f'\r{prefix} |{bar}| {percent:.1f}% ({current}/{total})')
    sys.stdout.flush()
    if current == total:
        print()


def connect_to_mongodb(region_code: str) -> tuple:
    """Connect to MongoDB for a specific region."""
    try:
        client = MongoClient(
            MONGO_URIS[region_code],
            serverSelectionTimeoutMS=5000
        )
        # Test connection
        client.admin.command('ping')
        db = client[DATABASE_NAME]

        # Set write concern to majority for data safety
        db.users.with_options(write_concern=WriteConcern(w='majority'))
        db.posts.with_options(write_concern=WriteConcern(w='majority'))

        print(f"✓ Connected to {region_code} region MongoDB")
        return client, db
    except Exception as e:
        print(f"✗ Failed to connect to {region_code} region: {e}")
        return None, None


def generate_and_insert_data():
    """Main function to generate and insert all data."""
    print("=" * 60)
    print("MeshNetwork Data Generator")
    print("=" * 60)
    print(f"Users to generate: {NUM_USERS:,}")
    print(f"Posts per user: {POSTS_PER_USER}")
    print(f"Total posts: {NUM_USERS * POSTS_PER_USER:,}")
    print(f"Batch size: {BATCH_SIZE:,}")
    print("=" * 60)

    # Connect to all regions
    connections = {}
    for region_code in REGIONS.keys():
        client, db = connect_to_mongodb(region_code)
        if db is None:
            print(f"\nError: Could not connect to {region_code} region. Aborting.")
            return
        connections[region_code] = {'client': client, 'db': db}

    print()

    # Distribute users evenly across regions
    users_per_region = NUM_USERS // 3
    region_codes = list(REGIONS.keys())

    # Store user IDs by region for post generation
    users_by_region = {region: [] for region in region_codes}

    print("PHASE 1: Generating and inserting users...")
    print("-" * 60)

    total_users_inserted = 0

    for region_code in region_codes:
        db = connections[region_code]['db']
        user_batch = []

        # Initialize Faker with different seed per region
        faker = Faker()
        region_seed = 42 + ord(region_code[0])  # Different seed per region
        Faker.seed(region_seed)
        random.seed(region_seed)

        # Determine number of users for this region (handle remainder)
        if region_code == region_codes[-1]:
            num_users_for_region = NUM_USERS - total_users_inserted
        else:
            num_users_for_region = users_per_region

        print(f"\n{region_code} region: Generating {num_users_for_region:,} users...")
        print(f"  Timestamp range: {REGION_TIME_RANGES[region_code][0]}-{REGION_TIME_RANGES[region_code][1]} days ago")

        for i in range(num_users_for_region):
            user = generate_user(faker, region_code)
            user_batch.append(user)
            users_by_region[region_code].append(user['user_id'])

            # Insert batch when size reached
            if len(user_batch) >= BATCH_SIZE:
                db.users.insert_many(user_batch)
                log_operation(db, 'insert_users', region_code, user_batch)
                total_users_inserted += len(user_batch)
                print_progress(total_users_inserted, NUM_USERS, f'  Inserting users')
                user_batch = []

        # Insert remaining users
        if user_batch:
            db.users.insert_many(user_batch)
            log_operation(db, 'insert_users', region_code, user_batch)
            total_users_inserted += len(user_batch)
            print_progress(total_users_inserted, NUM_USERS, f'  Inserting users')

    print(f"\n✓ Inserted {total_users_inserted:,} users across all regions")

    # PHASE 2: Generate posts
    print("\n" + "=" * 60)
    print("PHASE 2: Generating and inserting posts...")
    print("-" * 60)

    total_posts = NUM_USERS * POSTS_PER_USER
    total_posts_inserted = 0

    for region_code in region_codes:
        db = connections[region_code]['db']
        user_ids = users_by_region[region_code]

        print(f"\n{region_code} region: Generating {len(user_ids) * POSTS_PER_USER:,} posts...")

        post_batch = []

        for user_id in user_ids:
            # Generate POSTS_PER_USER posts for this user
            for _ in range(POSTS_PER_USER):
                post = generate_post(user_id, region_code)
                post_batch.append(post)

                # Insert batch when size reached
                if len(post_batch) >= BATCH_SIZE:
                    db.posts.insert_many(post_batch)
                    log_operation(db, 'insert_posts', region_code, post_batch)
                    total_posts_inserted += len(post_batch)
                    print_progress(total_posts_inserted, total_posts, f'  Inserting posts')
                    post_batch = []

        # Insert remaining posts
        if post_batch:
            db.posts.insert_many(post_batch)
            log_operation(db, 'insert_posts', region_code, post_batch)
            total_posts_inserted += len(post_batch)
            print_progress(total_posts_inserted, total_posts, f'  Inserting posts')

    print(f"\n✓ Inserted {total_posts_inserted:,} posts across all regions")

    # Print summary
    print("\n" + "=" * 60)
    print("DATA GENERATION COMPLETE")
    print("=" * 60)

    for region_code in region_codes:
        db = connections[region_code]['db']
        user_count = db.users.count_documents({})
        post_count = db.posts.count_documents({})
        log_count = db.operation_logs.count_documents({})
        print(f"{region_code} region:")
        print(f"  Users: {user_count:,}")
        print(f"  Posts: {post_count:,}")
        print(f"  Operation logs: {log_count:,}")

    print("\nTotal:")
    print(f"  Users: {total_users_inserted:,}")
    print(f"  Posts: {total_posts_inserted:,}")
    print("=" * 60)

    # Close connections
    for region_code in region_codes:
        connections[region_code]['client'].close()


if __name__ == '__main__':
    try:
        generate_and_insert_data()
    except KeyboardInterrupt:
        print("\n\nData generation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError during data generation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
