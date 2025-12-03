import argparse
import random
import uuid
import sys
from datetime import datetime, timezone, timedelta

try:
    from pymongo import MongoClient
    from faker import Faker
except ImportError:
    print("ERROR: Required packages not installed.")
    print("Run: pip install pymongo faker")
    sys.exit(1)

MONGO_URIS = {
    'NA': 'mongodb://localhost:27017/?directConnection=true&w=1',
    'EU': 'mongodb://localhost:27020/?directConnection=true&w=1',
    'AP': 'mongodb://localhost:27023/?directConnection=true&w=1'
}

DATABASE_NAME = 'meshnetwork'

REGIONS = {
    'NA': {'name': 'north_america', 'display': 'North America', 'lon': (-130, -70), 'lat': (25, 50)},
    'EU': {'name': 'europe', 'display': 'Europe', 'lon': (-10, 40), 'lat': (35, 60)},
    'AP': {'name': 'asia_pacific', 'display': 'Asia-Pacific', 'lon': (100, 150), 'lat': (-40, 40)}
}

POST_TYPES = ['shelter', 'food', 'medical', 'water', 'safety', 'help']

MESSAGES = {
    'shelter': ['Red Cross shelter open', 'Emergency shelter accepting families', 'Community center shelter open'],
    'food': ['Food distribution center open', 'Hot meals served', 'Emergency food bank operational'],
    'medical': ['Medical clinic open', 'First aid station 24/7', 'Mobile medical unit on site'],
    'water': ['Clean water available', 'Bottled water distribution', 'Water purification station'],
    'safety': ['Safe zone established', 'Evacuation route open', 'Area secured'],
    'help': ['Need medical supplies', 'Family separated', 'Trapped residents need help']
}

BATCH_SIZE = 2000

def progress(current, total, prefix=''):
    if total == 0:
        return
    pct = 100 * current / total
    sys.stdout.write(f'\r{prefix}: {pct:.1f}% ({current}/{total})')
    sys.stdout.flush()
    if current == total:
        print()

def get_location(region_code):
    r = REGIONS[region_code]
    return {'type': 'Point', 'coordinates': [
        round(random.uniform(*r['lon']), 6),
        round(random.uniform(*r['lat']), 6)
    ]}

def make_user(faker, region_code):
    return {
        'user_id': str(uuid.uuid4()),
        'name': faker.name(),
        'email': faker.email(),
        'region': REGIONS[region_code]['name'],
        'location': get_location(region_code),
        'created_at': datetime.now(timezone.utc)
    }

def make_post(user_id, region_code):
    post_type = random.choice(POST_TYPES)
    post = {
        'post_id': str(uuid.uuid4()),
        'user_id': user_id,
        'post_type': post_type,
        'message': random.choice(MESSAGES[post_type]),
        'location': get_location(region_code),
        'region': REGIONS[region_code]['name'],
        'timestamp': datetime.now(timezone.utc) - timedelta(days=random.randint(0, 20)),
    }
    if post_type == 'shelter':
        post['capacity'] = random.randint(10, 200)
    return post

def main():
    parser = argparse.ArgumentParser(description='Generate MeshNetwork test data')
    parser.add_argument('--users', '-u', type=int, default=100, help='Number of users')
    parser.add_argument('--posts-per-user', '-p', type=int, default=10, help='Posts per user')
    args = parser.parse_args()

    num_users = args.users
    posts_per_user = args.posts_per_user
    total_posts = num_users * posts_per_user

    print("Generating Data")
    print(f"Users: {num_users}")
    print(f"Posts per user: {posts_per_user}")

    print("\nConnecting...")
    connections = {}
    for code in REGIONS:
        try:
            client = MongoClient(MONGO_URIS[code], serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            connections[code] = client[DATABASE_NAME]
            print(f"  Connected to {REGIONS[code]['display']}")
        except Exception as e:
            print(f"  Failed {code}: {e}")
            return

    print("\nClearing data...")
    for code, db in connections.items():
        db.users.drop()
        db.posts.drop()
        db.operation_log.drop()
        print(f"  {code} cleared")

    faker = Faker()
    Faker.seed(42)
    random.seed(42)

    all_users = []
    all_posts = []
    region_codes = list(REGIONS.keys())
    users_per_region = num_users // 3

    print("\nGenerating users...")
    created = 0
    for idx, code in enumerate(region_codes):
        db = connections[code]
        count = users_per_region if idx < 2 else num_users - created
        batch = []
        for _ in range(count):
            user = make_user(faker, code)
            batch.append(user)
            all_users.append(user)
            if len(batch) >= BATCH_SIZE:
                db.users.insert_many(batch, ordered=False)
                created += len(batch)
                progress(created, num_users, "Users")
                batch = []
        if batch:
            db.users.insert_many(batch, ordered=False)
            created += len(batch)
            progress(created, num_users, "Users")

    print("\nGenerating posts...")
    created = 0
    for code in region_codes:
        db = connections[code]
        region_users = [u for u in all_users if u['region'] == REGIONS[code]['name']]
        batch = []
        for user in region_users:
            for _ in range(posts_per_user):
                post = make_post(user['user_id'], code)
                batch.append(post)
                all_posts.append(post)
                if len(batch) >= BATCH_SIZE:
                    db.posts.insert_many(batch, ordered=False)
                    created += len(batch)
                    progress(created, total_posts, "Posts")
                    batch = []
        if batch:
            db.posts.insert_many(batch, ordered=False)
            created += len(batch)
            progress(created, total_posts, "Posts")

    print("\nReplicating data to all regions...")
    for target_code in region_codes:
        target_db = connections[target_code]
        target_region = REGIONS[target_code]['name']

        users_to_copy = [u.copy() for u in all_users if u['region'] != target_region]
        for u in users_to_copy:
            u.pop('_id', None)
        if users_to_copy:
            for i in range(0, len(users_to_copy), BATCH_SIZE):
                target_db.users.insert_many(users_to_copy[i:i+BATCH_SIZE], ordered=False)
        
        posts_to_copy = [p.copy() for p in all_posts if p['region'] != target_region]
        for p in posts_to_copy:
            p.pop('_id', None)
        if posts_to_copy:
            copied = 0
            for i in range(0, len(posts_to_copy), BATCH_SIZE):
                target_db.posts.insert_many(posts_to_copy[i:i+BATCH_SIZE], ordered=False)
                copied += min(BATCH_SIZE, len(posts_to_copy) - i)
                progress(copied, len(posts_to_copy), f"{target_code}")

    print("\nComplete")
    for code, db in connections.items():
        try:
            print(f"  {code}: {db.users.count_documents({})} users, {db.posts.count_documents({})} posts")
        except:
            print(f"  {code}: (connection lost)")

if __name__ == '__main__':
    main()
