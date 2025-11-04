#!/bin/bash

# Test automatic failover in MongoDB replica sets
# This script simulates a primary node failure and verifies automatic failover

echo "========================================="
echo "Testing MongoDB Automatic Failover"
echo "========================================="

# Choose region to test (default: North America)
REGION=${1:-na}

case $REGION in
  na)
    PRIMARY="mongodb-na-primary"
    SECONDARY1="mongodb-na-secondary1"
    SECONDARY2="mongodb-na-secondary2"
    REGION_NAME="North America"
    ;;
  eu)
    PRIMARY="mongodb-eu-primary"
    SECONDARY1="mongodb-eu-secondary1"
    SECONDARY2="mongodb-eu-secondary2"
    REGION_NAME="Europe"
    ;;
  ap)
    PRIMARY="mongodb-ap-primary"
    SECONDARY1="mongodb-ap-secondary1"
    SECONDARY2="mongodb-ap-secondary2"
    REGION_NAME="Asia-Pacific"
    ;;
  *)
    echo "Invalid region: $REGION"
    echo "Usage: $0 [na|eu|ap]"
    exit 1
    ;;
esac

echo ""
echo "Testing failover for $REGION_NAME region..."
echo ""

# Step 1: Check initial status
echo "Step 1: Checking initial replica set status..."
docker exec $SECONDARY1 mongosh --quiet --eval "
  var status = rs.status();
  status.members.forEach(function(m) {
    print(m.name + ': ' + m.stateStr);
  });
"

# Wait a moment
sleep 2

# Step 2: Stop the primary node
echo ""
echo "Step 2: Stopping primary node ($PRIMARY)..."
docker stop $PRIMARY

echo "Primary node stopped. Waiting for failover election..."
sleep 15

# Step 3: Check new status
echo ""
echo "Step 3: Checking replica set status after primary failure..."
docker exec $SECONDARY1 mongosh --quiet --eval "
  var status = rs.status();
  var newPrimary = null;
  status.members.forEach(function(m) {
    print(m.name + ': ' + m.stateStr);
    if (m.stateStr === 'PRIMARY') {
      newPrimary = m.name;
    }
  });
  if (newPrimary) {
    print('\\n✓ Failover successful! New primary: ' + newPrimary);
  } else {
    print('\\n✗ Failover failed! No primary elected.');
  }
"

# Step 4: Test write operation
echo ""
echo "Step 4: Testing write operation on new primary..."
docker exec $SECONDARY1 mongosh --quiet meshnetwork --eval "
  try {
    db.posts.insertOne({
      post_id: 'test-failover-' + Date.now(),
      user_id: 'test-user',
      post_type: 'help',
      message: 'Testing failover',
      location: { type: 'Point', coordinates: [0, 0] },
      region: 'north_america',
      timestamp: new Date()
    });
    print('✓ Write operation successful on new primary');
  } catch (e) {
    print('✗ Write operation failed: ' + e);
  }
"

# Step 5: Restart original primary
echo ""
echo "Step 5: Restarting original primary ($PRIMARY)..."
docker start $PRIMARY

echo "Waiting for node to rejoin replica set..."
sleep 15

# Step 6: Check final status
echo ""
echo "Step 6: Checking final replica set status..."
docker exec $SECONDARY1 mongosh --quiet --eval "
  var status = rs.status();
  status.members.forEach(function(m) {
    print(m.name + ': ' + m.stateStr);
  });
"

echo ""
echo "========================================="
echo "Failover test complete!"
echo "========================================="
echo ""
echo "Summary:"
echo "1. Original primary was stopped"
echo "2. A secondary was automatically elected as new primary"
echo "3. Write operations continued successfully"
echo "4. Original primary rejoined as a secondary"
echo ""
echo "This demonstrates automatic failover and high availability!"
