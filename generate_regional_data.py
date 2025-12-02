"""
Generate unique data for each region with different timestamps.
This data will then be synced across regions by the replication engine.
"""
import random
import uuid
from datetime import datetime, timezone, timedelta
from faker import Faker
import sys

# Import from the original script
sys.path.insert(0, '/Users/apgupta/Documents/Fall2025/CSE512/MeshNetwork')
from generate_data import (
    REGIONS, POST_TYPES, POST_MESSAGES,
    get_random_location, DATABASE_NAME
)

# Configuration - reduced for faster generation
USERS_PER_REGION = 1000  # 1000 users per region = 3000 total
POSTS_PER_USER = 100     # 100 posts per user = 100,000 posts per region = 300,000 total
BATCH_SIZE = 500

def generate_user(faker: Faker, region_code: str) -> dict:
    """Generate a user for a specific region."""
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

def generate_post(user_id: str, region_code: str, days_ago_range: tuple) -> dict:
    """Generate a post with timestamp in a specific time range."""
    post_type = random.choice(POST_TYPES)
    message = random.choice(POST_MESSAGES[post_type])

    # Use different time ranges for different regions
    days_ago = random.randint(*days_ago_range)
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

    if post_type == 'shelter':
        post['capacity'] = random.randint(10, 200)

    return post

def generate_region_data_script(region_code: str, container: str, days_range: tuple):
    """
    Generate a mongosh script to create data directly in the container.
    Each region gets different timestamp ranges to make posts unique.
    """
    faker = Faker()
    Faker.seed(42 + ord(region_code[0]))  # Different seed per region
    random.seed(42 + ord(region_code[0]))

    region_name = REGIONS[region_code]['name']

    print(f"\n{'='*60}")
    print(f"Generating data for {region_code} ({region_name})")
    print(f"Timestamp range: {days_range[0]}-{days_range[1]} days ago")
    print(f"{'='*60}")

    # Generate users
    print(f"Generating {USERS_PER_REGION} users...")
    users = []
    for i in range(USERS_PER_REGION):
        user = generate_user(faker, region_code)
        users.append(user)

    # Generate posts
    print(f"Generating {USERS_PER_REGION * POSTS_PER_USER} posts...")
    posts = []
    for user in users:
        for _ in range(POSTS_PER_USER):
            post = generate_post(user['user_id'], region_code, days_range)
            posts.append(post)

    print(f"✓ Generated {len(users)} users and {len(posts)} posts")

    # Create mongosh script to insert data
    import subprocess
    import json
    from datetime import datetime

    # Custom JSON encoder for datetime
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime):
                return {'$date': obj.isoformat()}
            return super().default(obj)

    print(f"Inserting data into {container}...")

    # Insert users in batches
    for i in range(0, len(users), BATCH_SIZE):
        batch = users[i:i+BATCH_SIZE]
        users_json = json.dumps(batch, cls=DateTimeEncoder)

        cmd = f"""
        db = db.getSiblingDB('{DATABASE_NAME}');
        var users = {users_json};
        users.forEach(function(u) {{
            if (u.created_at && u.created_at.$date) {{
                u.created_at = new Date(u.created_at.$date);
            }}
            if (u.location) {{
                u.location.coordinates = [
                    parseFloat(u.location.coordinates[0]),
                    parseFloat(u.location.coordinates[1])
                ];
            }}
        }});
        db.users.insertMany(users);
        """

        result = subprocess.run(
            ['docker', 'exec', container, 'mongosh', '--quiet', '--eval', cmd],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"Error inserting users: {result.stderr}")
        else:
            print(f"  Inserted {len(batch)} users ({i+len(batch)}/{len(users)})")

    # Insert posts in batches
    for i in range(0, len(posts), BATCH_SIZE):
        batch = posts[i:i+BATCH_SIZE]
        posts_json = json.dumps(batch, cls=DateTimeEncoder)

        cmd = f"""
        db = db.getSiblingDB('{DATABASE_NAME}');
        var posts = {posts_json};
        posts.forEach(function(p) {{
            if (p.timestamp && p.timestamp.$date) {{
                p.timestamp = new Date(p.timestamp.$date);
            }}
            if (p.last_modified && p.last_modified.$date) {{
                p.last_modified = new Date(p.last_modified.$date);
            }}
            if (p.location) {{
                p.location.coordinates = [
                    parseFloat(p.location.coordinates[0]),
                    parseFloat(p.location.coordinates[1])
                ];
            }}
        }});
        db.posts.insertMany(posts);
        """

        result = subprocess.run(
            ['docker', 'exec', container, 'mongosh', '--quiet', '--eval', cmd],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"Error inserting posts: {result.stderr}")
        else:
            if (i + len(batch)) % 10000 == 0:
                print(f"  Inserted {i+len(batch)} posts...")

    print(f"✓ {region_code} region data generation complete!")
    return len(users), len(posts)

def main():
    print("="*60)
    print("Regional Data Generator for MeshNetwork")
    print("="*60)
    print(f"Users per region: {USERS_PER_REGION}")
    print(f"Posts per user: {POSTS_PER_USER}")
    print(f"Total posts per region: {USERS_PER_REGION * POSTS_PER_USER}")
    print("="*60)

    # First, clear all existing data
    print("\nClearing existing data...")
    import subprocess
    for container in ['mongodb-na-primary', 'mongodb-eu-primary', 'mongodb-ap-primary']:
        subprocess.run(
            ['docker', 'exec', container, 'mongosh', '--quiet', '--eval',
             f"db.getSiblingDB('{DATABASE_NAME}').users.deleteMany({{}});" +
             f"db.getSiblingDB('{DATABASE_NAME}').posts.deleteMany({{}});"],
            capture_output=True
        )
    print("✓ All regions cleared")

    # Generate data for each region with different timestamp ranges
    # This makes posts unique per region
    region_configs = [
        ('NA', 'mongodb-na-primary', (0, 10)),    # NA: posts from last 10 days
        ('EU', 'mongodb-eu-primary', (10, 20)),   # EU: posts from 10-20 days ago
        ('AP', 'mongodb-ap-primary', (20, 30))    # AP: posts from 20-30 days ago
    ]

    total_users = 0
    total_posts = 0

    for region_code, container, days_range in region_configs:
        users, posts = generate_region_data_script(region_code, container, days_range)
        total_users += users
        total_posts += posts

    print("\n" + "="*60)
    print("DATA GENERATION COMPLETE")
    print("="*60)
    print(f"Total users across all regions: {total_users}")
    print(f"Total posts across all regions: {total_posts}")
    print("")
    print("Each region now has unique posts with different timestamps.")
    print("The replication engine will sync posts between regions automatically.")
    print("")
    print("✓ Open http://localhost:3000 to see the data")
    print("✓ Switch between regions to see different posts")
    print("✓ Wait a few minutes for cross-region sync to complete")
    print("="*60)

if __name__ == '__main__':
    main()
