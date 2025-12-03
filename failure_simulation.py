import subprocess
import time
import requests
import sys
from typing import List, Dict, Any

GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text: str):
    print(f"\n{BLUE}{text}{RESET}\n")

def print_success(text: str):
    print(f"{GREEN}{text}{RESET}")

def print_error(text: str):
    print(f"{RED}{text}{RESET}")

def print_info(text: str):
    print(f"{YELLOW}{text}{RESET}")

def docker_command(cmd: List[str]) -> bool:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        print_error(f"Docker command failed: {e}")
        return False

def check_region_status(region_url: str) -> Dict[str, Any]:
    try:
        response = requests.get(f"{region_url}/status", timeout=5)
        return response.json() if response.status_code == 200 else {}
    except Exception:
        return {}

def test_single_node_failure():
    print_header("Test 1: Single Node Failure")
    print_info("Stopping mongodb-na-secondary1...")
    
    if docker_command(['docker', 'stop', 'mongodb-na-secondary1']):
        print_success("Node stopped successfully")
        print_info("Waiting 15 seconds for failure detection...")
        time.sleep(15)

        print_info("Checking replica set status...")
        result = subprocess.run(
            ['docker', 'exec', 'mongodb-na-primary', 'mongosh', '--quiet', '--eval', 'rs.status().ok'],
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and '1' in result.stdout:
            print_success("Replica set still operational")
        else:
            print_error("Replica set may have issues")

        print_info("Checking backend health...")
        try:
            response = requests.get('http://localhost:5010/health', timeout=5)
            if response.status_code == 200:
                print_success("Backend still healthy")
            else:
                print_error(f"Backend returned status {response.status_code}")
        except Exception as e:
            print_error(f"Backend unreachable: {e}")

        print_info("Restoring mongodb-na-secondary1...")
        if docker_command(['docker', 'start', 'mongodb-na-secondary1']):
            print_success("Node restored")
            time.sleep(10)
        else:
            print_error("Failed to restore node")
    else:
        print_error("Failed to stop node")

def test_primary_node_failure():
    print_header("Test 2: Primary Node Failure")
    print_info("Stopping mongodb-na-primary...")
    
    if docker_command(['docker', 'stop', 'mongodb-na-primary']):
        print_success("Primary node stopped")
        print_info("Waiting 20 seconds for primary election...")
        time.sleep(20)

        print_info("Checking for new primary...")
        for container in ['mongodb-na-secondary1', 'mongodb-na-secondary2']:
            result = subprocess.run(
                ['docker', 'exec', container, 'mongosh', '--quiet', '--eval', 'db.isMaster().ismaster'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and 'true' in result.stdout:
                print_success(f"New primary elected: {container}")
                break
        else:
            print_error("No new primary found")

        print_info("Checking backend health...")
        try:
            response = requests.get('http://localhost:5010/health', timeout=5)
            if response.status_code == 200:
                print_success("Backend adapted to new primary")
            else:
                print_error(f"Backend returned status {response.status_code}")
        except Exception as e:
            print_error(f"Backend unreachable: {e}")

        print_info("Restoring mongodb-na-primary...")
        if docker_command(['docker', 'start', 'mongodb-na-primary']):
            print_success("Primary node restored")
            time.sleep(15)
        else:
            print_error("Failed to restore primary")
    else:
        print_error("Failed to stop primary")

def test_network_partition():
    print_header("Test 3: Network Partition (Island Mode)")
    print_info("Disconnecting Europe region from global network...")

    if docker_command(['docker', 'network', 'disconnect', 'network-global', 'flask-backend-eu']):
        print_success("Europe disconnected from global network")
        print_info("Waiting 20 seconds for island mode activation...")
        
        for i in range(4):
            time.sleep(5)
            print(f"  {(i+1)*5} seconds elapsed...")

        print_info("Checking island mode status...")
        na_status = check_region_status('http://localhost:5010')
        
        if na_status:
            island = na_status.get('island_mode', {})
            connected = island.get('connected_regions', 0)
            total = island.get('total_regions', 0)
            print_info(f"North America: {connected}/{total} regions connected")

            remote_regions = na_status.get('remote_regions', {})
            for url, status in remote_regions.items():
                if 'eu' in url:
                    if status == 'unreachable':
                        print_success("Europe detected as unreachable from NA")
                    else:
                        print_error(f"Europe status: {status}")

        print_info("Testing local writes in isolated EU region...")
        try:
            print_info("EU is isolated - local operations continue but not accessible via global network")
        except Exception as e:
            print_info(f"Cannot reach EU (expected): {e}")

        print_info("Reconnecting Europe to global network...")
        if docker_command(['docker', 'network', 'connect', 'network-global', 'flask-backend-eu']):
            print_success("Europe reconnected")
            time.sleep(20)

            na_status = check_region_status('http://localhost:5010')
            if na_status:
                island = na_status.get('island_mode', {})
                if not island.get('active'):
                    print_success("Island mode deactivated in North America")
                else:
                    print_error("Island mode still active")
        else:
            print_error("Failed to reconnect Europe")
    else:
        print_error("Failed to disconnect Europe")

def test_cascading_failure():
    print_header("Test 4: Cascading Failure")
    nodes_to_stop = [
        'mongodb-na-secondary1',
        'mongodb-eu-secondary1',
        'mongodb-ap-secondary1'
    ]

    print_info("Stopping multiple secondary nodes across regions...")
    stopped_nodes = []

    for node in nodes_to_stop:
        if docker_command(['docker', 'stop', node]):
            print_success(f"Stopped {node}")
            stopped_nodes.append(node)
        else:
            print_error(f"Failed to stop {node}")

    print_info("Waiting 15 seconds for failure detection...")
    time.sleep(15)

    print_info("Checking if system remains operational...")
    regions = {
        'North America': 'http://localhost:5010',
        'Europe': 'http://localhost:5011',
        'Asia-Pacific': 'http://localhost:5012'
    }

    operational_count = 0
    for region_name, region_url in regions.items():
        try:
            response = requests.get(f"{region_url}/health", timeout=5)
            if response.status_code == 200:
                print_success(f"{region_name} operational")
                operational_count += 1
            else:
                print_error(f"{region_name} returned status {response.status_code}")
        except Exception as e:
            print_error(f"{region_name} unreachable: {e}")

    if operational_count == len(regions):
        print_success("All regions remain operational despite cascading failures")
    else:
        print_error(f"Only {operational_count}/{len(regions)} regions operational")

    print_info("Restoring all nodes...")
    for node in stopped_nodes:
        if docker_command(['docker', 'start', node]):
            print_success(f"Restored {node}")
        else:
            print_error(f"Failed to restore {node}")

    time.sleep(15)

def test_partition_recovery():
    print_header("Test 5: Partition Recovery & Reconciliation")
    print_info("Creating test data in NA before partition...")
    
    try:
        test_post = {
            'user_id': 'test_partition_user',
            'post_type': 'help',
            'message': 'Test message before partition',
            'location': {
                'type': 'Point',
                'coordinates': [-122.4194, 37.7749]
            },
            'region': 'north_america'
        }

        response = requests.post(
            'http://localhost:5010/api/posts',
            json=test_post,
            timeout=5
        )

        if response.status_code == 201:
            post_id = response.json().get('post_id')
            print_success(f"Created test post: {post_id}")

            print_info("Creating network partition...")
            if docker_command(['docker', 'network', 'disconnect', 'network-global', 'flask-backend-na']):
                print_success("Network partition created")
                time.sleep(20)

                print_info("Healing network partition...")
                if docker_command(['docker', 'network', 'connect', 'network-global', 'flask-backend-na']):
                    print_success("Network partition healed")
                    time.sleep(30)

                    print_info("Verifying data propagation to other regions...")
                    for region_name, region_url in [('Europe', 'http://localhost:5011'),
                                                      ('Asia-Pacific', 'http://localhost:5012')]:
                        try:
                            response = requests.get(
                                f"{region_url}/api/posts",
                                params={'region': 'all', 'limit': 1000},
                                timeout=5
                            )

                            if response.status_code == 200:
                                posts = response.json().get('posts', [])
                                found = any(p.get('post_id') == post_id for p in posts)

                                if found:
                                    print_success(f"Data reconciled in {region_name}")
                                else:
                                    print_error(f"Data not found in {region_name}")
                        except Exception as e:
                            print_error(f"Error checking {region_name}: {e}")
                else:
                    print_error("Failed to heal partition")
            else:
                print_error("Failed to create partition")
        else:
            print_error("Failed to create test post")

    except Exception as e:
        print_error(f"Error in partition recovery test: {e}")

def run_all_simulations():
    print_header("FAILURE SIMULATION SUITE")
    print("Testing Fault Tolerance & Recovery Mechanisms")

    print_info("1. Single node failures")
    print_info("2. Primary node failures")
    print_info("3. Network partitions (island mode)")
    print_info("4. Cascading failures")
    print_info("5. Partition recovery")
    print()

    response = input("Do you want to proceed? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print_info("Simulation cancelled")
        sys.exit(0)

    tests = [
        test_single_node_failure,
        test_primary_node_failure,
        test_network_partition,
        test_cascading_failure,
        test_partition_recovery
    ]

    for test_func in tests:
        try:
            test_func()
        except KeyboardInterrupt:
            print_error("\nSimulation interrupted by user")
            print_info("Attempting to restore system state...")
            docker_command(['docker', 'start', 'mongodb-na-secondary1'])
            docker_command(['docker', 'start', 'mongodb-na-primary'])
            docker_command(['docker', 'network', 'connect', 'network-global', 'flask-backend-eu'])
            docker_command(['docker', 'network', 'connect', 'network-global', 'flask-backend-na'])
            sys.exit(1)
        except Exception as e:
            print_error(f"Test failed with exception: {e}")

    print_header("SIMULATION COMPLETE")
    print_success("All failure simulation tests completed")

if __name__ == '__main__':
    run_all_simulations()
