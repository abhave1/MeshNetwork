#!/usr/bin/env python3

import requests
import time
import json
import statistics
from typing import List, Dict, Any
from datetime import datetime

REGIONS = {
    'north_america': 'http://localhost:5010',
    'europe': 'http://localhost:5011',
    'asia_pacific': 'http://localhost:5012'
}

NUM_WARMUP_REQUESTS = 5
NUM_TEST_REQUESTS = 20

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{text}{Colors.ENDC}\n")

def print_success(text: str):
    print(f"{Colors.OKGREEN}{text}{Colors.ENDC}")

def print_error(text: str):
    print(f"{Colors.FAIL}{text}{Colors.ENDC}")

def print_info(text: str):
    print(f"{Colors.OKCYAN}{text}{Colors.ENDC}")

def measure_request_latency(url: str, params: Dict[str, Any] = None) -> float:
    start_time = time.time()
    try:
        response = requests.get(url, params=params, timeout=10)
        end_time = time.time()

        if response.status_code == 200:
            return (end_time - start_time) * 1000
        else:
            print_error(f"Request failed with status {response.status_code}")
            return -1
    except Exception as e:
        print_error(f"Request error: {e}")
        return -1

def benchmark_query(
    region_name: str,
    base_url: str,
    query_params: Dict[str, Any],
    num_requests: int = NUM_TEST_REQUESTS
) -> Dict[str, Any]:
    print_info(f"Benchmarking {region_name} with params: {query_params}")

    print_info(f"Warming up ({NUM_WARMUP_REQUESTS} requests)...")
    for _ in range(NUM_WARMUP_REQUESTS):
        measure_request_latency(f"{base_url}/api/posts", query_params)

    print_info(f"Running benchmark ({num_requests} requests)...")
    latencies = []

    for i in range(num_requests):
        latency = measure_request_latency(f"{base_url}/api/posts", query_params)
        if latency > 0:
            latencies.append(latency)

        if (i + 1) % 5 == 0:
            print_info(f"  Progress: {i + 1}/{num_requests} requests completed")

    if not latencies:
        print_error("All requests failed!")
        return None

    results = {
        'region': region_name,
        'query_params': query_params,
        'num_requests': len(latencies),
        'mean_latency_ms': round(statistics.mean(latencies), 2),
        'median_latency_ms': round(statistics.median(latencies), 2),
        'min_latency_ms': round(min(latencies), 2),
        'max_latency_ms': round(max(latencies), 2),
        'stdev_latency_ms': round(statistics.stdev(latencies), 2) if len(latencies) > 1 else 0
    }

    return results

def test_local_query_performance():
    print_header("TEST 1: Local Query Performance")

    results = {}

    for region_name, base_url in REGIONS.items():
        print_info(f"\nTesting {region_name}...")

        local_params = {'region': region_name, 'limit': 100}
        result = benchmark_query(region_name, base_url, local_params)

        if result:
            results[region_name] = result
            print_success(
                f"{region_name}: Mean={result['mean_latency_ms']}ms, "
                f"Median={result['median_latency_ms']}ms, "
                f"StdDev={result['stdev_latency_ms']}ms"
            )

    print(f"\n{Colors.BOLD}Summary - Local Queries:{Colors.ENDC}")
    print(f"{'Region':<20} {'Mean (ms)':<12} {'Median (ms)':<12} {'Min (ms)':<12} {'Max (ms)':<12}")
    print('-' * 70)

    for region_name, result in results.items():
        print(
            f"{region_name:<20} "
            f"{result['mean_latency_ms']:<12} "
            f"{result['median_latency_ms']:<12} "
            f"{result['min_latency_ms']:<12} "
            f"{result['max_latency_ms']:<12}"
        )

    target_latency = 50
    all_meet_target = all(r['mean_latency_ms'] < target_latency for r in results.values())

    if all_meet_target:
        print_success(f"\nAll regions meet target latency (<{target_latency}ms)")
    else:
        print_error(f"\nSome regions exceed target latency (<{target_latency}ms)")

    return results

def test_global_query_performance():
    print_header("TEST 2: Global Query Performance (Scatter-Gather)")

    results = {}

    for region_name, base_url in REGIONS.items():
        print_info(f"\nTesting global query from {region_name}...")

        global_params = {'global': 'true', 'limit': 100}
        result = benchmark_query(f"{region_name} (global)", base_url, global_params)

        if result:
            results[region_name] = result
            print_success(
                f"{region_name} global query: Mean={result['mean_latency_ms']}ms, "
                f"Median={result['median_latency_ms']}ms"
            )

    print(f"\n{Colors.BOLD}Summary - Global Queries:{Colors.ENDC}")
    print(f"{'Region':<20} {'Mean (ms)':<12} {'Median (ms)':<12} {'Min (ms)':<12} {'Max (ms)':<12}")
    print('-' * 70)

    for region_name, result in results.items():
        print(
            f"{region_name:<20} "
            f"{result['mean_latency_ms']:<12} "
            f"{result['median_latency_ms']:<12} "
            f"{result['min_latency_ms']:<12} "
            f"{result['max_latency_ms']:<12}"
        )

    target_latency = 300
    all_meet_target = all(r['mean_latency_ms'] < target_latency for r in results.values())

    if all_meet_target:
        print_success(f"\nAll regions meet target latency (<{target_latency}ms)")
    else:
        print_error(f"\nSome regions exceed target latency (<{target_latency}ms)")

    return results

def test_scatter_gather_metadata():
    print_header("TEST 3: Scatter-Gather Metadata & Success Rate")

    region_name = 'north_america'
    base_url = REGIONS[region_name]

    print_info(f"Testing scatter-gather from {region_name}...")

    try:
        response = requests.get(
            f"{base_url}/api/posts",
            params={'global': 'true', 'limit': 10},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()

            if 'query_metadata' in data:
                metadata = data['query_metadata']

                print_success("Query metadata present in response")
                print(f"\n{Colors.BOLD}Scatter-Gather Metadata:{Colors.ENDC}")
                print(json.dumps(metadata, indent=2))

                required_fields = [
                    'total_regions_queried',
                    'successful_regions',
                    'failed_regions',
                    'success_rate',
                    'query_time_seconds'
                ]

                all_present = all(field in metadata for field in required_fields)

                if all_present:
                    print_success("\nAll required metadata fields present")

                    success_rate = metadata['success_rate']
                    if success_rate >= 0.5:
                        print_success(f"Success rate: {success_rate * 100:.1f}% (>= 50%)")
                    else:
                        print_error(f"Success rate: {success_rate * 100:.1f}% (< 50%)")

                    query_time = metadata['query_time_seconds']
                    print_info(f"Query execution time: {query_time}s")

                else:
                    print_error("Some metadata fields missing")
                    missing = [f for f in required_fields if f not in metadata]
                    print_error(f"Missing fields: {missing}")

            else:
                print_error("No query_metadata in response")

            if 'sources' in data:
                sources = data['sources']
                print(f"\n{Colors.BOLD}Data Sources:{Colors.ENDC}")
                print(f"  Local posts: {sources.get('local', 0)}")
                print(f"  Remote posts: {sources.get('remote', 0)}")
                print_success("Sources metadata present")

        else:
            print_error(f"Request failed with status {response.status_code}")

    except Exception as e:
        print_error(f"Error testing scatter-gather: {e}")

def test_consistent_hashing():
    print_header("TEST 4: Consistent Hashing Distribution")

    print_info("Testing consistent hashing for user partitioning...")

    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

        from services.partitioning import ConsistentHash

        nodes = ['primary', 'secondary1', 'secondary2']
        hash_ring = ConsistentHash(nodes, virtual_nodes=150)

        print_success(f"Created hash ring with nodes: {nodes}")

        num_users = 1000
        distribution = {node: 0 for node in nodes}

        for i in range(num_users):
            user_id = f"user_{i:04d}"
            node = hash_ring.get_node(user_id)
            distribution[node] += 1

        print(f"\n{Colors.BOLD}Distribution ({num_users} users):{Colors.ENDC}")
        print(f"{'Node':<20} {'Users':<10} {'Percentage':<15}")
        print('-' * 50)

        for node, count in sorted(distribution.items()):
            percentage = (count / num_users) * 100
            print(f"{node:<20} {count:<10} {percentage:>6.2f}%")

        expected_percentage = 100 / len(nodes)
        tolerance = 10

        balanced = all(
            abs((count / num_users * 100) - expected_percentage) <= tolerance
            for count in distribution.values()
        )

        if balanced:
            print_success(f"\nDistribution is balanced (within ±{tolerance}% of {expected_percentage:.1f}%)")
        else:
            print_error(f"\nDistribution is unbalanced (exceeds ±{tolerance}% tolerance)")

        print_info("\nTesting node addition...")
        hash_ring.add_node('secondary3')

        distribution_after = {'primary': 0, 'secondary1': 0, 'secondary2': 0, 'secondary3': 0}

        for i in range(num_users):
            user_id = f"user_{i:04d}"
            node = hash_ring.get_node(user_id)
            distribution_after[node] += 1

        print(f"\n{Colors.BOLD}Distribution after adding secondary3:{Colors.ENDC}")
        for node, count in sorted(distribution_after.items()):
            percentage = (count / num_users) * 100
            print(f"{node:<20} {count:<10} {percentage:>6.2f}%")

        moved_users = sum(abs(distribution.get(node, 0) - distribution_after.get(node, 0))
                          for node in ['primary', 'secondary1', 'secondary2']) // 2

        moved_percentage = (moved_users / num_users) * 100

        print_info(f"\nUsers moved: {moved_users} ({moved_percentage:.1f}%)")

        if moved_percentage < 30:
            print_success(f"Minimal data movement ({moved_percentage:.1f}% < 30%)")
        else:
            print_error(f"Excessive data movement ({moved_percentage:.1f}% >= 30%)")

    except ImportError as e:
        print_error(f"Could not import partitioning service: {e}")
        print_info("This test requires the backend/services/partitioning.py module")
    except Exception as e:
        print_error(f"Error testing consistent hashing: {e}")

def compare_local_vs_global():
    print_header("TEST 5: Local vs Global Query Comparison")

    region_name = 'north_america'
    base_url = REGIONS[region_name]

    print_info("Benchmarking local query...")
    local_params = {'region': region_name, 'limit': 100}
    local_result = benchmark_query(f"{region_name} (local)", base_url, local_params, num_requests=10)

    print_info("\nBenchmarking global query...")
    global_params = {'global': 'true', 'limit': 100}
    global_result = benchmark_query(f"{region_name} (global)", base_url, global_params, num_requests=10)

    if local_result and global_result:
        print(f"\n{Colors.BOLD}Comparison:{Colors.ENDC}")
        print(f"{'Query Type':<20} {'Mean Latency':<20} {'Median Latency':<20}")
        print('-' * 60)
        print(f"{'Local':<20} {local_result['mean_latency_ms']:<20} {local_result['median_latency_ms']:<20}")
        print(f"{'Global':<20} {global_result['mean_latency_ms']:<20} {global_result['median_latency_ms']:<20}")

        speedup = global_result['mean_latency_ms'] / local_result['mean_latency_ms']
        print(f"\n{Colors.BOLD}Global query is {speedup:.2f}x slower than local query{Colors.ENDC}")

        if global_result['mean_latency_ms'] < 300:
            print_success("Global query latency is acceptable (<300ms)")
        else:
            print_error("Global query latency exceeds target (>=300ms)")

def main():
    print_header("PHASE 2 PERFORMANCE TESTING")
    print_info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_info(f"Testing {len(REGIONS)} regions: {list(REGIONS.keys())}")

    start_time = time.time()

    try:
        test_local_query_performance()
        test_global_query_performance()
        test_scatter_gather_metadata()
        test_consistent_hashing()
        compare_local_vs_global()

        end_time = time.time()
        elapsed = end_time - start_time

        print_header("PHASE 2 TESTING COMPLETE")
        print_success(f"All tests completed in {elapsed:.2f} seconds")
        print_info(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    except KeyboardInterrupt:
        print_error("\n\nTesting interrupted by user")
    except Exception as e:
        print_error(f"\n\nTesting failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
