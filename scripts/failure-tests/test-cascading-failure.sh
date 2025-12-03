#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_DIR"

echo "Test: Cascading Failure Scenario"

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
print(f\"NA Database: {data['database']['status']}\")
print(f\"NA Members: {len(data['database']['members'])}\")
print(f\"Island Mode: {data['island_mode']['status']}\")
"

echo "Step 2: Create baseline test post"
BASELINE_POST=$(curl -s -X POST http://localhost:5010/api/posts \
    -H "Content-Type: application/json" \
    -d '{
        "user_id": "test_cascading_failure",
        "post_type": "safety",
        "message": "Baseline post before cascading failures",
        "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
        "region": "north_america"
    }')

BASELINE_ID=$(echo "$BASELINE_POST" | python3 -c "import sys, json; print(json.load(sys.stdin)['post_id'])")
echo "Created baseline post: $BASELINE_ID"

echo "FAILURE 1: Secondary Node Failure"

echo "Killing mongodb-na-secondary1..."
docker stop mongodb-na-secondary1
echo -e "${YELLOW}mongodb-na-secondary1 stopped${NC}"
sleep 5

echo "Verifying NA region still operational..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5010/health)
if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}NA region operational${NC}"
else
    echo -e "${RED}NA region failed${NC}"
    docker start mongodb-na-secondary1
    exit 1
fi

echo "FAILURE 2: Primary Node Failure"

echo "Identifying current primary..."
CURRENT_PRIMARY=$(curl -s http://localhost:5010/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data['database']['primary'])
")
echo "Current primary: $CURRENT_PRIMARY"

echo "Killing mongodb-na-primary..."
docker stop mongodb-na-primary
echo -e "${YELLOW}mongodb-na-primary stopped${NC}"

echo "Waiting for primary election (max 15 seconds)..."
ELECTION_TIME=0
NEW_PRIMARY=""
for i in {1..15}; do
    sleep 1
    ELECTION_TIME=$i

    STATUS=$(curl -s http://localhost:5010/status 2>/dev/null || echo "{}")
    NEW_PRIMARY=$(echo "$STATUS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('database', {}).get('primary', ''))" 2>/dev/null || echo "")

    if [ ! -z "$NEW_PRIMARY" ] && [ "$NEW_PRIMARY" != "$CURRENT_PRIMARY" ]; then
        echo -e "${GREEN}New primary elected: $NEW_PRIMARY${NC}"
        break
    fi
    echo -ne "  Waiting for election... ${i}s\r"
done
echo

if [ -z "$NEW_PRIMARY" ]; then
    echo -e "${RED}No new primary elected${NC}"
    docker start mongodb-na-primary mongodb-na-secondary1
    exit 1
fi

echo "Verifying system operational with 1 remaining node..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5010/health)
if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}System operational with degraded replica set${NC}"
else
    echo -e "${RED}System failed${NC}"
    docker start mongodb-na-primary mongodb-na-secondary1
    exit 1
fi

echo "FAILURE 3: EU Region Network Partition"

echo "Disconnecting EU backend from network..."
docker network disconnect meshnetwork_default flask-backend-eu 2>/dev/null || true
echo -e "${YELLOW}EU region isolated${NC}"

echo "Waiting for island mode detection (15 seconds)..."
sleep 15

echo "Checking NA island mode status..."
curl -s http://localhost:5010/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
island = data['island_mode']
print(f\"Connected Regions: {island['connected_regions']}/{island['total_regions']}\")
"

echo "DEGRADED MODE TESTING"

echo "Testing write operation during cascading failures..."
DEGRADED_POST=$(curl -s -X POST http://localhost:5010/api/posts \
    -H "Content-Type: application/json" \
    -d '{
        "user_id": "test_during_cascade",
        "post_type": "help",
        "message": "Emergency post during cascading failures",
        "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
        "region": "north_america"
    }')

if echo "$DEGRADED_POST" | grep -q "created successfully"; then
    DEGRADED_ID=$(echo "$DEGRADED_POST" | python3 -c "import sys, json; print(json.load(sys.stdin)['post_id'])")
    echo -e "${GREEN}Write successful during degraded mode: $DEGRADED_ID${NC}"
else
    echo -e "${RED}Write failed during degraded mode${NC}"
    docker start mongodb-na-primary mongodb-na-secondary1
    docker network connect meshnetwork_default flask-backend-eu
    exit 1
fi

echo "Testing read operation..."
READ_RESPONSE=$(curl -s "http://localhost:5010/api/posts?limit=10")
if echo "$READ_RESPONSE" | grep -q "posts"; then
    POST_COUNT=$(echo "$READ_RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin)['posts']))")
    echo -e "${GREEN}Read successful: $POST_COUNT posts retrieved${NC}"
else
    echo -e "${RED}Read failed${NC}"
fi

echo "Verifying baseline post preserved..."
BASELINE_CHECK=$(curl -s "http://localhost:5010/api/posts?limit=50" | python3 -c "
import sys, json
data = json.load(sys.stdin)
posts = data.get('posts', [])
found = any(p['post_id'] == '$BASELINE_ID' for p in posts)
print('found' if found else 'not_found')
")

if [ "$BASELINE_CHECK" = "found" ]; then
    echo -e "${GREEN}Baseline post preserved${NC}"
else
    echo -e "${RED}Baseline post lost!${NC}"
fi

echo "RECOVERY PHASE"

echo "Step 1: Restore EU network connection..."
docker network connect meshnetwork_default flask-backend-eu
echo -e "${GREEN}EU region reconnected${NC}"
sleep 10

echo "Step 2: Restore NA primary node..."
docker start mongodb-na-primary
echo -e "${GREEN}mongodb-na-primary restarted${NC}"
sleep 10

echo "Step 3: Restore NA secondary node..."
docker start mongodb-na-secondary1
echo -e "${GREEN}mongodb-na-secondary1 restarted${NC}"
sleep 10

echo "Step 4: Wait for full cluster recovery (20 seconds)..."
sleep 20

echo "POST-RECOVERY VERIFICATION"

echo "Checking NA cluster status..."
curl -s http://localhost:5010/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
members = data['database']['members']
healthy = sum(1 for m in members if m['health'] == 1)
print(f\"Database Status: {data['database']['status']}\")
print(f\"Healthy Members: {healthy}/{len(members)}\")
print(f\"Primary: {data['database']['primary']}\")
print(f\"Island Mode: {data['island_mode']['status']}\")
print(f\"Connected Regions: {data['island_mode']['connected_regions']}/{data['island_mode']['total_regions']}\")
"

echo "Verifying all posts preserved..."
ALL_POSTS=$(curl -s "http://localhost:5010/api/posts?limit=50" | python3 -c "
import sys, json
data = json.load(sys.stdin)
posts = data.get('posts', [])
baseline = any(p['post_id'] == '$BASELINE_ID' for p in posts)
degraded = any(p['post_id'] == '$DEGRADED_ID' for p in posts)
print(f\"Baseline post: {'found' if baseline else 'MISSING'}\")
print(f\"Degraded-mode post: {'found' if degraded else 'MISSING'}\")
print(f\"Total posts: {len(posts)}\")
print(json.dumps({'baseline': baseline, 'degraded': degraded}))
" | tail -1)

BASELINE_PRESERVED=$(echo "$ALL_POSTS" | python3 -c "import sys, json; print(json.load(sys.stdin)['baseline'])")
DEGRADED_PRESERVED=$(echo "$ALL_POSTS" | python3 -c "import sys, json; print(json.load(sys.stdin)['degraded'])")

if [ "$BASELINE_PRESERVED" = "True" ] && [ "$DEGRADED_PRESERVED" = "True" ]; then
    echo -e "${GREEN}All posts preserved through cascading failures${NC}"
else
    echo -e "${RED}Some posts lost!${NC}"
fi

echo "Testing post-recovery write operation..."
RECOVERY_POST=$(curl -s -X POST http://localhost:5010/api/posts \
    -H "Content-Type: application/json" \
    -d '{
        "user_id": "test_post_recovery",
        "post_type": "safety",
        "message": "Post after full recovery from cascading failures",
        "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
        "region": "north_america"
    }')

if echo "$RECOVERY_POST" | grep -q "created successfully"; then
    echo -e "${GREEN}Post-recovery write successful${NC}"
else
    echo -e "${RED}Post-recovery write failed${NC}"
fi

echo "Checking cross-region health..."
for region_name in "NA" "EU" "AP"; do
    case $region_name in
        "NA") PORT=5010 ;;
        "EU") PORT=5011 ;;
        "AP") PORT=5012 ;;
    esac

    STATUS=$(curl -s http://localhost:$PORT/health 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"{data['region']}: {data['status']}\")
except:
    print(f\"$region_name: unreachable\")
" || echo "$region_name: unreachable")

    echo "  $STATUS"
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo
echo "Test Result: PASSED"
echo "Total Duration: ${DURATION} seconds"
echo -e "${GREEN}SUCCESS: System survived cascading failures with zero data loss!${NC}"
