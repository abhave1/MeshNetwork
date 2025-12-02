#!/bin/bash

# Master Test Runner: Phase 4 Failure Tests
# Runs all failure simulation tests and generates summary report

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_DIR"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo
echo -e "${CYAN}=========================================="
echo "MeshNetwork Phase 4 Failure Test Suite"
echo "==========================================${NC}"
echo
echo "This test suite validates:"
echo "  • Automatic failover mechanisms"
echo "  • Island mode operation"
echo "  • Data preservation during failures"
echo "  • System resilience and recovery"
echo

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

# Ensure system is running
echo "Checking system status..."
if ! curl -s http://localhost:5010/health > /dev/null 2>&1; then
    echo -e "${RED}ERROR: System not running. Please start with 'docker-compose up -d'${NC}"
    exit 1
fi
echo -e "${GREEN}✓ System is running${NC}"
echo

# Function to run a test
run_test() {
    local test_name="$1"
    local test_script="$2"

    echo
    echo -e "${BLUE}=========================================="
    echo "Running: $test_name"
    echo "==========================================${NC}"
    echo

    if bash "$SCRIPT_DIR/$test_script" > /tmp/test-output.log 2>&1; then
        echo -e "${GREEN}✓ $test_name PASSED${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        echo "  (See /tmp/test-output.log for details)"
    else
        echo -e "${RED}✗ $test_name FAILED${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        FAILED_TESTS+=("$test_name")
        echo "  (See /tmp/test-output.log for error details)"

        # Show last 20 lines of output for debugging
        echo
        echo "Last 20 lines of output:"
        tail -20 /tmp/test-output.log
    fi
}

# Run all tests
START_TIME=$(date +%s)

run_test "Test 1: Single Node Failure" "test-single-node-failure.sh"
sleep 5  # Brief pause between tests

run_test "Test 2: Primary Node Failure" "test-primary-failure.sh"
sleep 5

run_test "Test 3: Network Partition (Island Mode)" "test-network-partition.sh"
sleep 5

run_test "Test 4: Cascading Failures" "test-cascading-failure.sh"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Generate summary report
echo
echo -e "${CYAN}=========================================="
echo "Test Suite Summary"
echo "==========================================${NC}"
echo
echo "Total Tests Run: $((TESTS_PASSED + TESTS_FAILED))"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo "Duration: ${DURATION} seconds"
echo

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}=========================================="
    echo "✓ ALL TESTS PASSED"
    echo "==========================================${NC}"
    echo
    echo "Phase 4 Requirements Validated:"
    echo "  ✓ Automatic failover and recovery"
    echo "  ✓ Replica set elections"
    echo "  ✓ Island mode detection and operation"
    echo "  ✓ Zero data loss during failures"
    echo "  ✓ System resilience under stress"
    echo
    exit 0
else
    echo -e "${RED}=========================================="
    echo "✗ SOME TESTS FAILED"
    echo "==========================================${NC}"
    echo
    echo "Failed tests:"
    for test in "${FAILED_TESTS[@]}"; do
        echo "  • $test"
    done
    echo
    exit 1
fi
