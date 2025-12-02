"""
Copy data from standalone MongoDB instances to replica sets.
"""
from pymongo import MongoClient
import sys

# Source: standalone instances (where data was generated)
SOURCES = {
    'NA': 'mongodb://localhost:27017/?directConnection=true',
    'EU': 'mongodb://localhost:27020/?directConnection=true',
    'AP': 'mongodb://localhost:27023/?directConnection=true'
}

# Destination: replica sets (where backend reads from)
# Connect via docker exec since replica set uses container hostnames
DATABASE_NAME = 'meshnetwork'

def copy_region_data(region_code):
    """Copy data for one region from standalone to replica set."""
    print(f"\n{'='*60}")
    print(f"Copying {region_code} region data...")
    print(f"{'='*60}")

    # Connect to source (standalone)
    source_client = MongoClient(SOURCES[region_code])
    source_db = source_client[DATABASE_NAME]

    # Get data from source
    users = list(source_db.users.find())
    posts = list(source_db.posts.find())
    operation_logs = list(source_db.operation_logs.find())

    print(f"Found {len(users)} users, {len(posts)} posts, {len(operation_logs)} operation logs")

    if len(users) == 0:
        print(f"No data found in {region_code}, skipping...")
        return

    # For replica sets, we need to use docker exec to insert
    # Create a script file that will be executed inside the container
    import subprocess
    import json

    container_map = {
        'NA': 'mongodb-na-primary',
        'EU': 'mongodb-eu-primary',
        'AP': 'mongodb-ap-primary'
    }

    container = container_map[region_code]

    # Insert in batches
    batch_size = 1000

    # Insert users
    print(f"Inserting {len(users)} users...")
    for i in range(0, len(users), batch_size):
        batch = users[i:i+batch_size]
        # Remove _id to let MongoDB generate new ones
        for doc in batch:
            if '_id' in doc:
                del doc['_id']

        # Create mongosh command
        cmd = f"""
        db = db.getSiblingDB('{DATABASE_NAME}');
        db.users.insertMany({json.dumps(batch)});
        """

        result = subprocess.run(
            ['docker', 'exec', container, 'mongosh', '--quiet', '--eval', cmd],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"Error inserting users batch: {result.stderr}")
        else:
            print(f"  Inserted {len(batch)} users ({i+len(batch)}/{len(users)})")

    # Insert posts
    print(f"Inserting {len(posts)} posts...")
    for i in range(0, len(posts), batch_size):
        batch = posts[i:i+batch_size]
        # Remove _id
        for doc in batch:
            if '_id' in doc:
                del doc['_id']

        cmd = f"""
        db = db.getSiblingDB('{DATABASE_NAME}');
        db.posts.insertMany({json.dumps(batch)});
        """

        result = subprocess.run(
            ['docker', 'exec', container, 'mongosh', '--quiet', '--eval', cmd],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"Error inserting posts batch: {result.stderr}")
        else:
            print(f"  Inserted {len(batch)} posts ({i+len(batch)}/{len(posts)})")

    print(f"✓ {region_code} region data copied successfully!")
    source_client.close()

def main():
    print("="*60)
    print("Copying Data to Replica Sets")
    print("="*60)

    for region in ['NA', 'EU', 'AP']:
        try:
            copy_region_data(region)
        except Exception as e:
            print(f"Error copying {region}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*60)
    print("DATA COPY COMPLETE")
    print("="*60)

if __name__ == '__main__':
    main()
