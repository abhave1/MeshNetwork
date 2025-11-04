#!/bin/bash

# Verify MeshNetwork setup is complete and working
# Run this script after starting services and initializing replica sets

echo "========================================="
echo "MeshNetwork Setup Verification"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SUCCESS=0
FAILURES=0

# Function to check service
check_service() {
    local service=$1
    local url=$2

    if curl -s -f "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $service is running"
        ((SUCCESS++))
    else
        echo -e "${RED}✗${NC} $service is NOT running"
        ((FAILURES++))
    fi
}

# Function to check MongoDB replica set
check_replica_set() {
    local container=$1
    local replica_name=$2

    local status=$(docker exec $container mongosh --quiet --eval "rs.status().ok" 2>/dev/null)

    if [ "$status" == "1" ]; then
        echo -e "${GREEN}✓${NC} $replica_name replica set is healthy"
        ((SUCCESS++))
    else
        echo -e "${RED}✗${NC} $replica_name replica set is NOT healthy"
        ((FAILURES++))
    fi
}

echo "Step 1: Checking Docker Containers"
echo "-----------------------------------"

# Check if docker-compose is running
if ! docker-compose ps | grep -q "Up"; then
    echo -e "${RED}✗${NC} Docker containers are not running"
    echo "Run: docker-compose up -d"
    exit 1
fi

# Count running containers
RUNNING=$(docker-compose ps | grep -c "Up")
echo -e "Running containers: $RUNNING/14"

if [ "$RUNNING" -eq 14 ]; then
    echo -e "${GREEN}✓${NC} All 14 containers are running"
    ((SUCCESS++))
else
    echo -e "${YELLOW}⚠${NC} Expected 14 containers, found $RUNNING"
    ((FAILURES++))
fi

echo ""
echo "Step 2: Checking MongoDB Replica Sets"
echo "--------------------------------------"

check_replica_set "mongodb-na-primary" "North America"
check_replica_set "mongodb-eu-primary" "Europe"
check_replica_set "mongodb-ap-primary" "Asia-Pacific"

echo ""
echo "Step 3: Checking Flask Backends"
echo "--------------------------------"

check_service "North America Backend" "http://localhost:5010/health"
check_service "Europe Backend" "http://localhost:5011/health"
check_service "Asia-Pacific Backend" "http://localhost:5012/health"

echo ""
echo "Step 4: Checking Frontend"
echo "-------------------------"

if curl -s -f http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} React Frontend is running"
    ((SUCCESS++))
else
    echo -e "${RED}✗${NC} React Frontend is NOT running"
    ((FAILURES++))
fi

echo ""
echo "Step 5: Checking Cross-Region Connectivity"
echo "-------------------------------------------"

# Test if backends can reach each other
NA_TO_EU=$(docker exec flask-backend-na curl -s -m 3 http://flask-backend-eu:5011/health 2>&1 | grep -c "healthy")
NA_TO_AP=$(docker exec flask-backend-na curl -s -m 3 http://flask-backend-ap:5012/health 2>&1 | grep -c "healthy")

if [ "$NA_TO_EU" -eq 1 ]; then
    echo -e "${GREEN}✓${NC} North America can reach Europe"
    ((SUCCESS++))
else
    echo -e "${RED}✗${NC} North America CANNOT reach Europe"
    ((FAILURES++))
fi

if [ "$NA_TO_AP" -eq 1 ]; then
    echo -e "${GREEN}✓${NC} North America can reach Asia-Pacific"
    ((SUCCESS++))
else
    echo -e "${RED}✗${NC} North America CANNOT reach Asia-Pacific"
    ((FAILURES++))
fi

echo ""
echo "Step 6: Checking Database Collections"
echo "--------------------------------------"

# Check if collections exist
NA_COLLECTIONS=$(docker exec mongodb-na-primary mongosh --quiet meshnetwork --eval "db.getCollectionNames().length" 2>/dev/null)

if [ "$NA_COLLECTIONS" -ge 3 ]; then
    echo -e "${GREEN}✓${NC} Database collections created (found $NA_COLLECTIONS)"
    ((SUCCESS++))
else
    echo -e "${RED}✗${NC} Database collections NOT created"
    echo "Run: ./scripts/init-all-replicas.sh"
    ((FAILURES++))
fi

echo ""
echo "Step 7: Testing CRUD Operations"
echo "--------------------------------"

# Test creating a post
POST_RESULT=$(curl -s -X POST http://localhost:5010/api/posts \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "verify-test-user",
    "post_type": "help",
    "message": "Setup verification test",
    "location": {"type": "Point", "coordinates": [0, 0]}
  }' 2>&1)

if echo "$POST_RESULT" | grep -q "post_id"; then
    echo -e "${GREEN}✓${NC} Can create posts"
    ((SUCCESS++))

    # Test reading posts
    GET_RESULT=$(curl -s http://localhost:5010/api/posts 2>&1)
    if echo "$GET_RESULT" | grep -q "posts"; then
        echo -e "${GREEN}✓${NC} Can read posts"
        ((SUCCESS++))
    else
        echo -e "${RED}✗${NC} Cannot read posts"
        ((FAILURES++))
    fi
else
    echo -e "${RED}✗${NC} Cannot create posts"
    ((FAILURES++))
fi

echo ""
echo "========================================="
echo "Verification Complete"
echo "========================================="
echo ""
echo -e "Success: ${GREEN}$SUCCESS${NC}"
echo -e "Failures: ${RED}$FAILURES${NC}"
echo ""

if [ "$FAILURES" -eq 0 ]; then
    echo -e "${GREEN}🎉 All checks passed! MeshNetwork is fully operational.${NC}"
    echo ""
    echo "Next steps:"
    echo "  - Open http://localhost:3000 in your browser"
    echo "  - Run: ./scripts/test-failover.sh na"
    echo "  - Run: ./scripts/simulate-partition.sh ap"
    exit 0
else
    echo -e "${RED}⚠ Some checks failed. Please review the output above.${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  - Check logs: docker-compose logs"
    echo "  - Restart services: docker-compose restart"
    echo "  - Initialize replica sets: ./scripts/init-all-replicas.sh"
    exit 1
fi
