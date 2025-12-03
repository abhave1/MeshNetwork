#!/bin/bash

echo "Simulating Network Partition"

REGION=${1:-ap}

case $REGION in
  na)
    BACKEND="flask-backend-na"
    MONGODB_PRIMARY="mongodb-na-primary"
    MONGODB_SECONDARY1="mongodb-na-secondary1"
    MONGODB_SECONDARY2="mongodb-na-secondary2"
    REGION_NAME="North America"
    PORT="5010"
    ;;
  eu)
    BACKEND="flask-backend-eu"
    MONGODB_PRIMARY="mongodb-eu-primary"
    MONGODB_SECONDARY1="mongodb-eu-secondary1"
    MONGODB_SECONDARY2="mongodb-eu-secondary2"
    REGION_NAME="Europe"
    PORT="5011"
    ;;
  ap)
    BACKEND="flask-backend-ap"
    MONGODB_PRIMARY="mongodb-ap-primary"
    MONGODB_SECONDARY1="mongodb-ap-secondary1"
    MONGODB_SECONDARY2="mongodb-ap-secondary2"
    REGION_NAME="Asia-Pacific"
    PORT="5012"
    ;;
  *)
    echo "Invalid region: $REGION"
    exit 1
    ;;
esac

echo "Isolating $REGION_NAME region from global network..."

echo "Checking initial connectivity..."
curl -s http://localhost:$PORT/health | grep -q "healthy" && echo "Backend is reachable" || echo "Backend is unreachable"

echo "Disconnecting $REGION_NAME from global network..."
docker network disconnect network-global $MONGODB_PRIMARY 2>/dev/null || true
docker network disconnect network-global $MONGODB_SECONDARY1 2>/dev/null || true
docker network disconnect network-global $MONGODB_SECONDARY2 2>/dev/null || true
docker network disconnect network-global $BACKEND 2>/dev/null || true

echo "$REGION_NAME is now isolated (island mode)"

echo "Testing local functionality in island mode..."

sleep 3

curl -s http://localhost:$PORT/health | grep -q "healthy" && \
  echo "Backend is still operational in island mode" || \
  echo "Backend is not responding"

echo "Region is operating in island mode..."
echo "Waiting 15 seconds..."
sleep 15

echo "Verifying isolation..."

docker exec $BACKEND curl -s -m 2 http://flask-backend-na:5010/health 2>&1 | grep -q "healthy" && \
  echo "Can still reach North America (unexpected)" || \
  echo "Cannot reach North America (expected)"

docker exec $BACKEND curl -s -m 2 http://flask-backend-eu:5011/health 2>&1 | grep -q "healthy" && \
  echo "Can still reach Europe (unexpected)" || \
  echo "Cannot reach Europe (expected)"

docker exec $BACKEND curl -s -m 2 http://flask-backend-ap:5012/health 2>&1 | grep -q "healthy" && \
  echo "Can still reach Asia-Pacific (unexpected)" || \
  echo "Cannot reach Asia-Pacific (expected)"

echo "Reconnecting $REGION_NAME to global network..."
docker network connect network-global $MONGODB_PRIMARY
docker network connect network-global $MONGODB_SECONDARY1
docker network connect network-global $MONGODB_SECONDARY2
docker network connect network-global $BACKEND

echo "$REGION_NAME is reconnected to global network"

echo "Waiting for cross-region synchronization..."
sleep 10

echo "Verifying connectivity restored..."

docker exec $BACKEND curl -s -m 5 http://flask-backend-na:5010/health 2>&1 | grep -q "healthy" && \
  echo "Can reach North America" || \
  echo "Cannot reach North America"

docker exec $BACKEND curl -s -m 5 http://flask-backend-eu:5011/health 2>&1 | grep -q "healthy" && \
  echo "Can reach Europe" || \
  echo "Cannot reach Europe"

docker exec $BACKEND curl -s -m 5 http://flask-backend-ap:5012/health 2>&1 | grep -q "healthy" && \
  echo "Can reach Asia-Pacific" || \
  echo "Cannot reach Asia-Pacific"

echo "Network partition simulation complete"
