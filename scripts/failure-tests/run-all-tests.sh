#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "MeshNetwork Phase 4 Failure Test Suite"

TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

echo "Checking system status..."
if ! curl -s http://localhost:5010/health > /dev/null 2>&1; then
    echo -e "${RED}ERROR: System not running. Please start with 'docker-compose up -d'${NC}"
    exit 1
fi
echo "System is running"

run_test() {
    local test_name="$1"
    local test_script="$2"

    echo "Running: $test_name"

    if bash "$SCRIPT_DIR/$test_script" > /tmp/test-output.log 2>&1; then
        echo -e "${GREEN}PASS: $test_name${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}FAIL: $test_name${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        FAILED_TESTS+=("$test_name")
        
        echo "Last 20 lines of output:"
        tail -20 /tmp/test-output.log
    fi
}

START_TIME=$(date +%s)

run_test "Test 1: Single Node Failure" "test-single-node-failure.sh"
sleep 5

run_test "Test 2: Primary Node Failure" "test-primary-failure.sh"
sleep 5

run_test "Test 3: Network Partition (Island Mode)" "test-network-partition.sh"
sleep 5

run_test "Test 4: Cascading Failures" "test-cascading-failure.sh"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "Test Suite Summary"
echo "Total Tests Run: $((TESTS_PASSED + TESTS_FAILED))"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo "Duration: ${DURATION} seconds"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}ALL TESTS PASSED${NC}"
    exit 0
else
    echo -e "${RED}SOME TESTS FAILED${NC}"
    echo "Failed tests:"
    for test in "${FAILED_TESTS[@]}"; do
        echo "  - $test"
    done
    exit 1
fi
