"""
Generate unique data for each region via the backend API.
This automatically triggers replication between regions.
"""
import requests
import random
import uuid
from datetime import datetime, timezone, timedelta
from faker import Faker
import time

# Import from original script
import sys
sys.path.insert(0, '/Users/apgupta/Documents/Fall2025/CSE512/MeshNetwork')
from generate_data import REGIONS, POST_TYPES, POST_MESSAGES, get_random_location

# Configuration
USERS_PER_REGION = 100   # 100 users per region
POSTS_PER_USER = 10      # 10 posts per user = 1000 posts per region

# Backend URLs
BACKENDS = {
    'NA': 'http://localhost:5010',
    'EU': 'http://localhost:5011',
    'AP': 'http://localhost:5012'
}

def generate_post_via_api(backend_url: str, region_code: str, days_ago_range: tuple):
    """Generate a single post via the API."""
    faker = Faker()

    # Generate user_id
    user_id = f"{region_code.lower()}_user_{uuid.uuid4().hex[:8]}"

    # Random post type and message
    post_type = random.choice(POST_TYPES)
    message = random.choice(POST_MESSAGES[post_type])

    # Get random location for this region
    location = get_random_location(region_code)

    # Create post data
    post_data = {
        'user_id': user_id,
        'post_type': post_type,
        'message': message,
        'location': location,
        'region': REGIONS[region_code]['name']
    }

    # Add capacity for shelter posts
    if post_type == 'shelter':
        post_data['capacity'] = random.randint(10, 200)

    try:
        response = requests.post(
            f"{backend_url}/api/posts",
            json=post_data,
            timeout=5
        )

        if response.status_code == 201:
            return True
        else:
            print(f"  Error: {response.status_code} - {response.text[:100]}")
            return False
    except Exception as e:
        print(f"  Error creating post: {e}")
        return False

def main():
    print("="*60)
    print("API-based Regional Data Generator")
    print("="*60)
    print(f"Users per region: {USERS_PER_REGION}")
    print(f"Posts per user: {POSTS_PER_USER}")
    print(f"Total posts per region: {USERS_PER_REGION * POSTS_PER_USER}")
    print("="*60)
    print("")
    print("NOTE: This uses the backend API which automatically")
    print("      triggers cross-region replication!")
    print("")

    region_configs = [
        ('NA', BACKENDS['NA'], (0, 10)),
        ('EU', BACKENDS['EU'], (10, 20)),
        ('AP', BACKENDS['AP'], (20, 30))
    ]

    total_created = 0

    for region_code, backend_url, days_range in region_configs:
        print(f"\n{region_code} Region ({REGIONS[region_code]['name']})")
        print(f"Backend: {backend_url}")
        print(f"Timestamp range: {days_range[0]}-{days_range[1]} days ago")
        print("-" * 60)

        created = 0
        failed = 0
        total_posts = USERS_PER_REGION * POSTS_PER_USER

        for i in range(total_posts):
            if generate_post_via_api(backend_url, region_code, days_range):
                created += 1
            else:
                failed += 1

            # Progress indicator
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i+1}/{total_posts} ({created} created, {failed} failed)")

            # Small delay to avoid overwhelming the API
            time.sleep(0.01)

        print(f"✓ {region_code}: Created {created} posts ({failed} failed)")
        total_created += created

    print("\n" + "="*60)
    print("DATA GENERATION COMPLETE")
    print("="*60)
    print(f"Total posts created: {total_created}")
    print("")
    print("✓ Each region now has unique posts")
    print("✓ Replication engine is syncing posts between regions")
    print("✓ Wait 1-2 minutes for full cross-region sync")
    print("")
    print("Open http://localhost:3000 and:")
    print("1. Select each region and click 'Refresh Posts'")
    print("2. You should see posts from ALL regions (after sync)")
    print("3. Posts will have different timestamps per region")
    print("="*60)

if __name__ == '__main__':
    main()
