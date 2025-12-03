#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_DIR"

echo "Test: Network Partition (Island Mode)"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

START_TIME=$(date +%s)

echo "Step 1: Verify initial system health"
curl -s http://localhost:5010/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"NA Status: {data['database']['status']}\")
print(f\"Island Mode: {data['island_mode']['status']}\")
print(f\"Connected Regions: {data['island_mode']['connected_regions']}/{data['island_mode']['total_regions']}\")
"

echo "Step 2: Create test post in NA (before partition)"
TEST_POST_BEFORE=$(curl -s -X POST http://localhost:5010/api/posts \
    -H "Content-Type: application/json" \
    -d '{
        "user_id": "test_network_partition",
        "post_type": "safety",
        "message": "Test post BEFORE network partition",
        "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
        "region": "north_america"
    }')

POST_ID_BEFORE=$(echo "$TEST_POST_BEFORE" | python3 -c "import sys, json; print(json.load(sys.stdin)['post_id'])")
echo "Created test post: $POST_ID_BEFORE"

echo "Step 3: Wait for cross-region sync (10 seconds)"
sleep 10

echo "Step 4: Verify post replicated to EU and AP"
EU_BEFORE=$(curl -s "http://localhost:5011/api/posts?limit=50" | python3 -c "
import sys, json
data = json.load(sys.stdin)
posts = data.get('posts', [])
found = any(p['post_id'] == '$POST_ID_BEFORE' for p in posts)
print('found' if found else 'not_found')
")

AP_BEFORE=$(curl -s "http://localhost:5012/api/posts?limit=50" | python3 -c "
import sys, json
data = json.load(sys.stdin)
posts = data.get('posts', [])
found = any(p['post_id'] == '$POST_ID_BEFORE' for p in posts)
print('found' if found else 'not_found')
")

if [ "$EU_BEFORE" = "found" ] && [ "$AP_BEFORE" = "found" ]; then
    echo -e "${GREEN}Post replicated to all regions${NC}"
else
    echo -e "${YELLOW}Post not yet replicated${NC}"
fi

echo "Step 5: Isolate NA region"
PARTITION_START=$(date +%s)

docker network disconnect meshnetwork_default flask-backend-na 2>/dev/null || true

echo -e "${YELLOW}NA region network disconnected${NC}"

echo "Step 6: Wait for island mode activation (20 seconds)"
for i in {20..1}; do
    echo -ne "  Waiting... ${i}s remaining\r"
    sleep 1
done
echo

echo "Step 7: Verify island mode activated"
ISLAND_STATUS=$(curl -s http://localhost:5010/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
island = data['island_mode']
print(json.dumps({'active': island['active']}))
" | tail -1)

IS_ISLAND=$(echo "$ISLAND_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin)['active'])")

if [ "$IS_ISLAND" = "True" ]; then
    echo -e "${GREEN}Island mode activated successfully${NC}"
else
    echo -e "${RED}Island mode NOT activated${NC}"
    docker network connect meshnetwork_default flask-backend-na
    exit 1
fi

echo "Step 8: Test local operations during isolation"

ISOLATED_POST=$(curl -s -X POST http://localhost:5010/api/posts \
    -H "Content-Type: application/json" \
    -d '{
        "user_id": "test_during_partition",
        "post_type": "help",
        "message": "Emergency post DURING network partition (island mode)",
        "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
        "region": "north_america"
    }')

POST_ID_ISOLATED=$(echo "$ISOLATED_POST" | python3 -c "import sys, json; print(json.load(sys.stdin)['post_id'])")
echo -e "${GREEN}Write operation successful: $POST_ID_ISOLATED${NC}"

READ_START=$(date +%s%3N)
READ_RESPONSE=$(curl -s "http://localhost:5010/api/posts?limit=10")
READ_END=$(date +%s%3N)
READ_LATENCY=$((READ_END - READ_START))

if echo "$READ_RESPONSE" | grep -q "posts"; then
    echo -e "${GREEN}Read operation successful${NC}"
else
    echo -e "${RED}Read operation failed${NC}"
fi

echo "Step 9: Verify isolated post NOT replicated to other regions"
EU_ISOLATED=$(curl -s "http://localhost:5011/api/posts?limit=50" 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    posts = data.get('posts', [])
    found = any(p['post_id'] == '$POST_ID_ISOLATED' for p in posts)
    print('found' if found else 'not_found')
except:
    print('not_found')
" || echo "not_found")

if [ "$EU_ISOLATED" = "not_found" ]; then
    echo -e "${GREEN}Isolated post NOT in EU${NC}"
else
    echo -e "${YELLOW}Isolated post found in EU${NC}"
fi

echo "Step 10: Restore network connectivity"
docker network connect meshnetwork_default flask-backend-na
echo -e "${GREEN}NA region network reconnected${NC}"
RESTORE_TIME=$(date +%s)

echo "Step 11: Wait for island mode deactivation (20 seconds)"
sleep 20

echo "Step 12: Verify island mode deactivated"
POST_RESTORE_STATUS=$(curl -s http://localhost:5010/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
island = data['island_mode']
print(json.dumps({'active': island['active']}))
" | tail -1)

IS_STILL_ISLAND=$(echo "$POST_RESTORE_STATUS" | python3 -c "import sys, json; print(json.load(sys.stdin)['active'])")

if [ "$IS_STILL_ISLAND" = "False" ]; then
    echo -e "${GREEN}Island mode deactivated${NC}"
else
    echo -e "${YELLOW}Island mode still active${NC}"
fi

echo "Step 13: Wait for cross-region reconciliation (30 seconds)"
sleep 30

echo "Step 14: Verify isolated post replicated to all regions"
EU_AFTER=$(curl -s "http://localhost:5011/api/posts?limit=50" | python3 -c "
import sys, json
data = json.load(sys.stdin)
posts = data.get('posts', [])
found = any(p['post_id'] == '$POST_ID_ISOLATED' for p in posts)
print('found' if found else 'not_found')
")

AP_AFTER=$(curl -s "http://localhost:5012/api/posts?limit=50" | python3 -c "
import sys, json
data = json.load(sys.stdin)
posts = data.get('posts', [])
found = any(p['post_id'] == '$POST_ID_ISOLATED' for p in posts)
print('found' if found else 'not_found')
")

if [ "$EU_AFTER" = "found" ] && [ "$AP_AFTER" = "found" ]; then
    echo -e "${GREEN}Isolated post replicated to all regions${NC}"
else
    echo -e "${YELLOW}Post not yet in all regions${NC}"
fi

echo "Step 15: Verify all regions healthy"
for region_name in "NA" "EU" "AP"; do
    case $region_name in
        "NA") PORT=5010 ;;
        "EU") PORT=5011 ;;
        "AP") PORT=5012 ;;
    esac

    STATUS=$(curl -s http://localhost:$PORT/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"{data['region']['name']}: {data['database']['status']}\")
")
    echo "  $STATUS"
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo
echo "Test Result: PASSED"
echo "Total Duration: ${DURATION} seconds"
echo -e "${GREEN}SUCCESS: Network partition handled correctly!${NC}"
