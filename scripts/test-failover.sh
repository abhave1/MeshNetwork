#!/bin/bash

echo "Testing MongoDB Automatic Failover"

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
    exit 1
    ;;
esac

echo "Testing failover for $REGION_NAME region..."

echo "Checking initial replica set status..."
docker exec $SECONDARY1 mongosh --quiet --eval "
  var status = rs.status();
  status.members.forEach(function(m) {
    print(m.name + ': ' + m.stateStr);
  });
"

sleep 2

echo "Stopping primary node ($PRIMARY)..."
docker stop $PRIMARY

echo "Primary node stopped. Waiting for failover election..."
sleep 15

echo "Checking replica set status after primary failure..."
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
    print('Failover successful! New primary: ' + newPrimary);
  } else {
    print('Failover failed! No primary elected.');
  }
"

echo "Testing write operation on new primary..."
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
    print('Write operation successful on new primary');
  } catch (e) {
    print('Write operation failed: ' + e);
  }
"

echo "Restarting original primary ($PRIMARY)..."
docker start $PRIMARY

echo "Waiting for node to rejoin replica set..."
sleep 15

echo "Checking final replica set status..."
docker exec $SECONDARY1 mongosh --quiet --eval "
  var status = rs.status();
  status.members.forEach(function(m) {
    print(m.name + ': ' + m.stateStr);
  });
"

echo "Failover test complete"
