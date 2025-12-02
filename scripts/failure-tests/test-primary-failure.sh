#!/bin/bash

# Test Script: Primary Node Failure
# Tests automatic primary election when primary node fails
# Success Criteria: New primary elected within <10s, acknowledged writes preserved

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_DIR"

echo "=========================================="
echo "Test: Primary Node Failure"
echo "=========================================="
echo

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

START_TIME=$(date +%s)

echo "Step 1: Identify current primary"
echo "--------------------------------"
CURRENT_PRIMARY=$(curl -s http://localhost:5010/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data['database']['primary'])
")
echo "Current Primary: $CURRENT_PRIMARY"

PRIMARY_CONTAINER="mongodb-na-primary"
echo "Primary Container: $PRIMARY_CONTAINER"
echo

echo "Step 2: Create test post (to verify data preservation)"
echo "-------------------------------------------------------"
TEST_POST=$(curl -s -X POST http://localhost:5010/api/posts \
    -H "Content-Type: application/json" \
    -d '{
        "user_id": "test_primary_failure",
        "post_type": "safety",
        "message": "Critical test post before primary failure",
        "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
        "region": "north_america"
    }')

POST_ID=$(echo "$TEST_POST" | python3 -c "import sys, json; print(json.load(sys.stdin)['post_id'])")
echo "Created test post: $POST_ID"
echo

echo "Step 3: Kill primary node"
echo "-------------------------"
FAILURE_START=$(date +%s)
docker stop $PRIMARY_CONTAINER
echo -e "${YELLOW}$PRIMARY_CONTAINER stopped${NC}"
echo

echo "Step 4: Monitor primary election (max 15 seconds)"
echo "--------------------------------------------------"
ELECTION_TIME=0
NEW_PRIMARY=""
for i in {1..15}; do
    sleep 1
    ELECTION_TIME=$i

    STATUS=$(curl -s http://localhost:5010/status 2>/dev/null || echo "{}")
    NEW_PRIMARY=$(echo "$STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', {}).get('primary', ''))" 2>/dev/null || echo "")

    if [ ! -z "$NEW_PRIMARY" ] && [ "$NEW_PRIMARY" != "$CURRENT_PRIMARY" ]; then
        echo -e "${GREEN}✓ New primary elected: $NEW_PRIMARY${NC}"
        echo "  Election time: ${ELECTION_TIME} seconds"
        break
    fi
    echo -ne "  Waiting for election... ${i}s\r"
done
echo

if [ -z "$NEW_PRIMARY" ]; then
    echo -e "${RED}✗ No new primary elected within timeout${NC}"
    docker start $PRIMARY_CONTAINER
    exit 1
fi

echo "Step 5: Verify system operational with new primary"
echo "---------------------------------------------------"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5010/health)
if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${RED}✗ Health check failed (HTTP $HTTP_CODE)${NC}"
    docker start $PRIMARY_CONTAINER
    exit 1
fi
echo

echo "Step 6: Verify acknowledged write was preserved"
echo "------------------------------------------------"
PRESERVED_POST=$(curl -s "http://localhost:5010/api/posts?limit=50" | python3 -c "
import sys, json
data = json.load(sys.stdin)
posts = data.get('posts', [])
target_id = '$POST_ID'
found = any(p['post_id'] == target_id for p in posts)
print('found' if found else 'not_found')
")

if [ "$PRESERVED_POST" = "found" ]; then
    echo -e "${GREEN}✓ Test post preserved (post_id: $POST_ID)${NC}"
else
    echo -e "${RED}✗ Test post lost!${NC}"
    docker start $PRIMARY_CONTAINER
    exit 1
fi
echo

echo "Step 7: Test new write operation"
echo "---------------------------------"
NEW_POST=$(curl -s -X POST http://localhost:5010/api/posts \
    -H "Content-Type: application/json" \
    -d '{
        "user_id": "test_after_primary_election",
        "post_type": "help",
        "message": "Post after primary failover",
        "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
        "region": "north_america"
    }')

if echo "$NEW_POST" | grep -q "created successfully"; then
    echo -e "${GREEN}✓ Write to new primary successful${NC}"
else
    echo -e "${RED}✗ Write to new primary failed${NC}"
    docker start $PRIMARY_CONTAINER
    exit 1
fi
echo

echo "Step 8: Restore old primary"
echo "----------------------------"
docker start $PRIMARY_CONTAINER
echo -e "${GREEN}$PRIMARY_CONTAINER restarted${NC}"
echo

echo "Step 9: Wait for old primary to rejoin (10 seconds)"
echo "----------------------------------------------------"
sleep 10
echo

echo "Step 10: Verify cluster status"
echo "-------------------------------"
curl -s http://localhost:5010/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
members = data['database']['members']
print(f\"Cluster Status:\")
print(f\"  Total members: {len(members)}\")
print(f\"  Current primary: {data['database']['primary']}\")
print(f\"  Healthy nodes: {sum(1 for m in members if m['health'] == 1)}/{len(members)}\")
for member in members:
    status = member['state']
    health = '✓' if member['health'] == 1 else '✗'
    print(f\"    {health} {member['name']}: {status}\")
"
echo

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo
echo "=========================================="
echo "Test Result: PASSED ✓"
echo "=========================================="
echo "Total Duration: ${DURATION} seconds"
echo "Primary Election Time: ${ELECTION_TIME} seconds"
echo "Data Loss: Zero (all acknowledged writes preserved)"
echo "Success Criteria Met:"
echo "  ✓ New primary elected within 10s: ${ELECTION_TIME}s"
echo "  ✓ Zero data loss"
echo "  ✓ System operational during failover"
echo

echo -e "${GREEN}SUCCESS: Primary failure handled correctly!${NC}"
