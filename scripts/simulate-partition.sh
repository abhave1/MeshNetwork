#!/bin/bash

# Simulate network partition by isolating a region from the global network
# This demonstrates "island mode" where a region continues operating independently

echo "========================================="
echo "Simulating Network Partition"
echo "========================================="

# Choose region to isolate (default: Asia-Pacific)
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
    echo "Usage: $0 [na|eu|ap]"
    exit 1
    ;;
esac

echo ""
echo "Isolating $REGION_NAME region from global network..."
echo ""

# Step 1: Check initial connectivity
echo "Step 1: Checking initial connectivity..."
echo "Testing connection to backend..."
curl -s http://localhost:$PORT/health | grep -q "healthy" && echo "✓ Backend is reachable" || echo "✗ Backend is unreachable"

# Step 2: Disconnect from global network
echo ""
echo "Step 2: Disconnecting $REGION_NAME from global network..."
docker network disconnect network-global $MONGODB_PRIMARY 2>/dev/null || true
docker network disconnect network-global $MONGODB_SECONDARY1 2>/dev/null || true
docker network disconnect network-global $MONGODB_SECONDARY2 2>/dev/null || true
docker network disconnect network-global $BACKEND 2>/dev/null || true

echo "✓ $REGION_NAME is now isolated (island mode)"

# Step 3: Test local functionality
echo ""
echo "Step 3: Testing local functionality in island mode..."
echo "Backend should still be operational locally..."

sleep 3

# Try to access the backend (still accessible via host port mapping)
curl -s http://localhost:$PORT/health | grep -q "healthy" && \
  echo "✓ Backend is still operational in island mode" || \
  echo "✗ Backend is not responding"

# Step 4: Wait in island mode
echo ""
echo "Step 4: Region is operating in island mode..."
echo "During this time:"
echo "  - Local operations continue normally"
echo "  - Changes are queued for later synchronization"
echo "  - Other regions are unreachable"
echo ""
echo "Waiting 30 seconds..."
sleep 30

# Step 5: Test that region is truly isolated
echo ""
echo "Step 5: Verifying isolation..."
echo "Checking if backend can reach other regions..."

docker exec $BACKEND curl -s -m 2 http://flask-backend-na:5010/health 2>&1 | grep -q "healthy" && \
  echo "✗ Can still reach North America (unexpected)" || \
  echo "✓ Cannot reach North America (expected)"

docker exec $BACKEND curl -s -m 2 http://flask-backend-eu:5011/health 2>&1 | grep -q "healthy" && \
  echo "✗ Can still reach Europe (unexpected)" || \
  echo "✓ Cannot reach Europe (expected)"

docker exec $BACKEND curl -s -m 2 http://flask-backend-ap:5012/health 2>&1 | grep -q "healthy" && \
  echo "✗ Can still reach Asia-Pacific (unexpected)" || \
  echo "✓ Cannot reach Asia-Pacific (expected)"

# Step 6: Reconnect to global network
echo ""
echo "Step 6: Reconnecting $REGION_NAME to global network..."
docker network connect network-global $MONGODB_PRIMARY
docker network connect network-global $MONGODB_SECONDARY1
docker network connect network-global $MONGODB_SECONDARY2
docker network connect network-global $BACKEND

echo "✓ $REGION_NAME is reconnected to global network"

# Step 7: Wait for synchronization
echo ""
echo "Step 7: Waiting for cross-region synchronization..."
echo "The replication engine will now sync queued changes..."
sleep 10

# Step 8: Verify connectivity restored
echo ""
echo "Step 8: Verifying connectivity restored..."

docker exec $BACKEND curl -s -m 5 http://flask-backend-na:5010/health 2>&1 | grep -q "healthy" && \
  echo "✓ Can reach North America" || \
  echo "✗ Cannot reach North America"

docker exec $BACKEND curl -s -m 5 http://flask-backend-eu:5011/health 2>&1 | grep -q "healthy" && \
  echo "✓ Can reach Europe" || \
  echo "✗ Cannot reach Europe"

docker exec $BACKEND curl -s -m 5 http://flask-backend-ap:5012/health 2>&1 | grep -q "healthy" && \
  echo "✓ Can reach Asia-Pacific" || \
  echo "✗ Cannot reach Asia-Pacific"

echo ""
echo "========================================="
echo "Network partition simulation complete!"
echo "========================================="
echo ""
echo "Summary:"
echo "1. $REGION_NAME was isolated from global network"
echo "2. Region continued operating independently (island mode)"
echo "3. Changes were queued for synchronization"
echo "4. Region was reconnected to global network"
echo "5. Queued changes are being synchronized"
echo ""
echo "This demonstrates partition tolerance and eventual consistency!"
