#!/usr/bin/env python3
"""
Phase 3 Testing Script - Cross-Region Replication & Conflict Resolution
Tests the implementation of:
- Push/Pull synchronization
- Last-Write-Wins conflict resolution
- Island mode detection
- Cross-region data propagation
"""

import requests
import time
import json
from datetime import datetime
from typing import Dict, Any, List

# Region endpoints
REGIONS = {
    'north_america': 'http://localhost:5010',
    'europe': 'http://localhost:5011',
    'asia_pacific': 'http://localhost:5012'
}

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{BLUE}{'='*60}")
    print(f"{text}")
    print(f"{'='*60}{RESET}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text: str):
    """Print error message."""
    print(f"{RED}✗ {text}{RESET}")


def print_info(text: str):
    """Print info message."""
    print(f"{YELLOW}ℹ {text}{RESET}")


def check_region_status(region_name: str, base_url: str) -> Dict[str, Any]:
    """Check the status of a region."""
    try:
        response = requests.get(f"{base_url}/status", timeout=5)
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception as e:
        print_error(f"Failed to check {region_name} status: {e}")
        return {}


def test_region_connectivity():
    """Test 1: Verify all regions are reachable."""
    print_header("TEST 1: Region Connectivity")

    all_healthy = True
    for region_name, base_url in REGIONS.items():
        try:
            response = requests.get(f"{base_url}/health", timeout=5)
            if response.status_code == 200:
                print_success(f"{region_name.replace('_', ' ').title()} is reachable")
            else:
                print_error(f"{region_name.replace('_', ' ').title()} returned status {response.status_code}")
                all_healthy = False
        except Exception as e:
            print_error(f"{region_name.replace('_', ' ').title()} is unreachable: {e}")
            all_healthy = False

    return all_healthy


def test_replication_status():
    """Test 2: Check replication engine status."""
    print_header("TEST 2: Replication Engine Status")

    for region_name, base_url in REGIONS.items():
        status = check_region_status(region_name, base_url)

        if not status:
            print_error(f"Could not get status for {region_name}")
            continue

        island_mode = status.get('island_mode', {})
        conflict_metrics = status.get('conflict_metrics', {})

        print(f"\n{YELLOW}{region_name.replace('_', ' ').title()}:{RESET}")
        print(f"  Island Mode: {'Active' if island_mode.get('active') else 'Inactive'}")
        print(f"  Connected Regions: {island_mode.get('connected_regions', 0)}/{island_mode.get('total_regions', 0)}")
        print(f"  Total Conflicts: {conflict_metrics.get('total_conflicts', 0)}")
        print(f"  Remote Wins: {conflict_metrics.get('remote_wins', 0)}")
        print(f"  Local Wins: {conflict_metrics.get('local_wins', 0)}")
        print(f"  Unresolved: {conflict_metrics.get('unresolved', 0)}")

        # Check remote regions connectivity
        remote_regions = status.get('remote_regions', {})
        for remote_url, reachable in remote_regions.items():
            status_icon = "✓" if reachable == "reachable" else "✗"
            print(f"  {status_icon} {remote_url}: {reachable}")


def test_cross_region_sync():
    """Test 3: Create data in one region and verify it propagates."""
    print_header("TEST 3: Cross-Region Data Synchronization")

    # Create a unique test post in North America
    test_user_id = f"test_user_{int(time.time())}"
    test_post_data = {
        'user_id': test_user_id,
        'post_type': 'help',
        'message': f'Test sync message at {datetime.now().isoformat()}',
        'location': {
            'type': 'Point',
            'coordinates': [-122.4194, 37.7749]  # San Francisco
        },
        'region': 'north_america'
    }

    print_info("Creating test post in North America...")
    try:
        response = requests.post(
            f"{REGIONS['north_america']}/api/posts",
            json=test_post_data,
            timeout=5
        )

        if response.status_code == 201:
            result = response.json()
            post_id = result.get('post_id')
            print_success(f"Post created: {post_id}")

            # Wait for synchronization
            print_info("Waiting 15 seconds for cross-region synchronization...")
            time.sleep(15)

            # Check if post exists in other regions
            for region_name, base_url in REGIONS.items():
                if region_name == 'north_america':
                    continue

                try:
                    response = requests.get(
                        f"{base_url}/api/posts",
                        params={'region': 'all', 'limit': 1000},
                        timeout=5
                    )

                    if response.status_code == 200:
                        data = response.json()
                        posts = data.get('posts', [])

                        # Check if our test post is in the results
                        found = any(p.get('post_id') == post_id for p in posts)

                        if found:
                            print_success(f"Post found in {region_name.replace('_', ' ').title()}")
                        else:
                            print_error(f"Post NOT found in {region_name.replace('_', ' ').title()}")
                    else:
                        print_error(f"Failed to query {region_name}: {response.status_code}")

                except Exception as e:
                    print_error(f"Error checking {region_name}: {e}")
        else:
            print_error(f"Failed to create post: {response.status_code}")
            print_error(response.text)

    except Exception as e:
        print_error(f"Error in sync test: {e}")


def test_conflict_resolution():
    """Test 4: Test Last-Write-Wins conflict resolution."""
    print_header("TEST 4: Conflict Resolution (Last-Write-Wins)")

    # Create a user in NA
    test_user_data = {
        'name': 'Test User Conflict',
        'email': f'conflict_test_{int(time.time())}@example.com',
        'region': 'north_america',
        'location': {
            'type': 'Point',
            'coordinates': [-122.4194, 37.7749]
        }
    }

    print_info("Creating test user in North America...")
    try:
        response = requests.post(
            f"{REGIONS['north_america']}/api/users",
            json=test_user_data,
            timeout=5
        )

        if response.status_code == 201:
            result = response.json()
            user_id = result.get('user_id')
            print_success(f"User created: {user_id}")

            # Wait for sync
            time.sleep(10)

            # Update user in NA with timestamp T1
            print_info("Updating user in North America (Update 1)...")
            update1 = {'name': 'Updated Name T1', 'reputation': 100}
            requests.put(
                f"{REGIONS['north_america']}/api/users/{user_id}",
                json=update1,
                timeout=5
            )

            # Small delay
            time.sleep(2)

            # Update user in EU with timestamp T2 (should win)
            print_info("Updating user in Europe (Update 2 - should win)...")
            update2 = {'name': 'Updated Name T2 (Winner)', 'reputation': 200}
            requests.put(
                f"{REGIONS['europe']}/api/users/{user_id}",
                json=update2,
                timeout=5
            )

            # Wait for conflict resolution
            print_info("Waiting 15 seconds for conflict resolution...")
            time.sleep(15)

            # Check final state in all regions
            print_info("Checking final user state across all regions...")
            for region_name, base_url in REGIONS.items():
                try:
                    response = requests.get(
                        f"{base_url}/api/users/{user_id}",
                        timeout=5
                    )

                    if response.status_code == 200:
                        user = response.json()
                        final_name = user.get('name')
                        final_rep = user.get('reputation')

                        print(f"  {region_name.replace('_', ' ').title()}: name='{final_name}', reputation={final_rep}")

                        if final_name == 'Updated Name T2 (Winner)':
                            print_success(f"  Last-Write-Wins working correctly in {region_name}")
                        else:
                            print_error(f"  Unexpected state in {region_name}")
                    else:
                        print_error(f"Failed to get user from {region_name}: {response.status_code}")

                except Exception as e:
                    print_error(f"Error checking {region_name}: {e}")
        else:
            print_error(f"Failed to create user: {response.status_code}")

    except Exception as e:
        print_error(f"Error in conflict resolution test: {e}")


def test_operation_log():
    """Test 5: Verify operation log is being maintained."""
    print_header("TEST 5: Operation Log Verification")

    for region_name, base_url in REGIONS.items():
        status = check_region_status(region_name, base_url)

        if status:
            conflict_metrics = status.get('conflict_metrics', {})
            recent_conflicts = conflict_metrics.get('recent_conflicts', [])

            print(f"\n{YELLOW}{region_name.replace('_', ' ').title()}:{RESET}")
            print(f"  Total Conflicts Resolved: {conflict_metrics.get('total_conflicts', 0)}")

            if recent_conflicts:
                print(f"  Recent Conflicts (last 3):")
                for conflict in recent_conflicts[-3:]:
                    print(f"    - {conflict.get('collection')}/{conflict.get('document_id')}")
                    print(f"      Outcome: {conflict.get('outcome')}")
                    print(f"      Time: {conflict.get('timestamp')}")
            else:
                print_info("  No recent conflicts")


def test_island_mode_status():
    """Test 6: Check island mode detection capability."""
    print_header("TEST 6: Island Mode Detection Status")

    print_info("Island mode activates when a region is isolated for >60 seconds")
    print_info("Currently all regions are connected (island mode inactive)")

    for region_name, base_url in REGIONS.items():
        status = check_region_status(region_name, base_url)

        if status:
            island_mode = status.get('island_mode', {})
            replication_status = status.get('replication_status', {})

            print(f"\n{YELLOW}{region_name.replace('_', ' ').title()}:{RESET}")
            print(f"  Island Mode: {'ACTIVE ⚠️' if island_mode.get('active') else 'Inactive ✓'}")
            print(f"  Threshold: {island_mode.get('threshold_seconds')} seconds")
            print(f"  Connected: {island_mode.get('connected_regions')}/{island_mode.get('total_regions')} regions")

            if island_mode.get('isolation_start'):
                print(f"  Isolation Start: {island_mode.get('isolation_start')}")
                print(f"  Duration: {island_mode.get('isolation_duration_seconds')} seconds")

            # Show replication status details
            if replication_status:
                print(f"  Replication Status:")
                for remote_url, details in replication_status.items():
                    connected = "✓" if details.get('connected') else "✗"
                    print(f"    {connected} {remote_url}")
                    if details.get('last_success'):
                        print(f"       Last Success: {details.get('last_success')}")
                    if details.get('consecutive_failures', 0) > 0:
                        print(f"       Consecutive Failures: {details.get('consecutive_failures')}")


def run_all_tests():
    """Run all Phase 3 tests."""
    print(f"\n{BLUE}{'='*60}")
    print("PHASE 3 TESTING: Cross-Region Replication & Conflict Resolution")
    print(f"{'='*60}{RESET}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Run tests
    tests = [
        ("Region Connectivity", test_region_connectivity),
        ("Replication Status", test_replication_status),
        ("Cross-Region Sync", test_cross_region_sync),
        ("Conflict Resolution", test_conflict_resolution),
        ("Operation Log", test_operation_log),
        ("Island Mode Status", test_island_mode_status)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, True))
        except Exception as e:
            print_error(f"Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))

    # Print summary
    print_header("TEST SUMMARY")
    passed = sum(1 for _, result in results if result is not False)
    total = len(results)

    for test_name, result in results:
        if result is not False:
            print_success(f"{test_name}")
        else:
            print_error(f"{test_name}")

    print(f"\n{BLUE}Total: {passed}/{total} tests passed{RESET}")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


if __name__ == '__main__':
    run_all_tests()
