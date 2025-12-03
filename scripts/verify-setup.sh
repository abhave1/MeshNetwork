#!/bin/bash

echo "MeshNetwork Setup Verification"

SUCCESS=0
FAILURES=0

check_service() {
    local service=$1
    local url=$2

    if curl -s -f "$url" > /dev/null 2>&1; then
        echo "$service is running"
        ((SUCCESS++))
    else
        echo "$service is NOT running"
        ((FAILURES++))
    fi
}

check_replica_set() {
    local container=$1
    local replica_name=$2

    local status=$(docker exec $container mongosh --quiet --eval "rs.status().ok" 2>/dev/null)

    if [ "$status" == "1" ]; then
        echo "$replica_name replica set is healthy"
        ((SUCCESS++))
    else
        echo "$replica_name replica set is NOT healthy"
        ((FAILURES++))
    fi
}

echo "Checking Docker Containers"

if ! docker-compose ps | grep -q "Up"; then
    echo "Docker containers are not running"
    echo "Run: docker-compose up -d"
    exit 1
fi

RUNNING=$(docker-compose ps | grep -c "Up")
echo "Running containers: $RUNNING/14"

if [ "$RUNNING" -eq 14 ]; then
    echo "All 14 containers are running"
    ((SUCCESS++))
else
    echo "Expected 14 containers, found $RUNNING"
    ((FAILURES++))
fi

echo "Checking MongoDB Replica Sets"

check_replica_set "mongodb-na-primary" "North America"
check_replica_set "mongodb-eu-primary" "Europe"
check_replica_set "mongodb-ap-primary" "Asia-Pacific"

echo "Checking Flask Backends"

check_service "North America Backend" "http://localhost:5010/health"
check_service "Europe Backend" "http://localhost:5011/health"
check_service "Asia-Pacific Backend" "http://localhost:5012/health"

echo "Checking Frontend"

if curl -s -f http://localhost:3000 > /dev/null 2>&1; then
    echo "React Frontend is running"
    ((SUCCESS++))
else
    echo "React Frontend is NOT running"
    ((FAILURES++))
fi

echo "Checking Cross-Region Connectivity"

NA_TO_EU=$(docker exec flask-backend-na curl -s -m 3 http://flask-backend-eu:5011/health 2>&1 | grep -c "healthy")
NA_TO_AP=$(docker exec flask-backend-na curl -s -m 3 http://flask-backend-ap:5012/health 2>&1 | grep -c "healthy")

if [ "$NA_TO_EU" -eq 1 ]; then
    echo "North America can reach Europe"
    ((SUCCESS++))
else
    echo "North America CANNOT reach Europe"
    ((FAILURES++))
fi

if [ "$NA_TO_AP" -eq 1 ]; then
    echo "North America can reach Asia-Pacific"
    ((SUCCESS++))
else
    echo "North America CANNOT reach Asia-Pacific"
    ((FAILURES++))
fi

echo "Checking Database Collections"

NA_COLLECTIONS=$(docker exec mongodb-na-primary mongosh --quiet meshnetwork --eval "db.getCollectionNames().length" 2>/dev/null)

if [ "$NA_COLLECTIONS" -ge 3 ]; then
    echo "Database collections created (found $NA_COLLECTIONS)"
    ((SUCCESS++))
else
    echo "Database collections NOT created"
    echo "Run: ./scripts/init-all-replicas.sh"
    ((FAILURES++))
fi

echo "Testing CRUD Operations"

POST_RESULT=$(curl -s -X POST http://localhost:5010/api/posts \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "verify-test-user",
    "post_type": "help",
    "message": "Setup verification test",
    "location": {"type": "Point", "coordinates": [0, 0]}
  }' 2>&1)

if echo "$POST_RESULT" | grep -q "post_id"; then
    echo "Can create posts"
    ((SUCCESS++))

    GET_RESULT=$(curl -s http://localhost:5010/api/posts 2>&1)
    if echo "$GET_RESULT" | grep -q "posts"; then
        echo "Can read posts"
        ((SUCCESS++))
    else
        echo "Cannot read posts"
        ((FAILURES++))
    fi
else
    echo "Cannot create posts"
    ((FAILURES++))
fi

echo "Verification Complete"
echo "Success: $SUCCESS"
echo "Failures: $FAILURES"

if [ "$FAILURES" -eq 0 ]; then
    echo "All checks passed! MeshNetwork is fully operational."
    exit 0
else
    echo "Some checks failed. Please review the output above."
    exit 1
fi
