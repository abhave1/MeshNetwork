#!/bin/bash

echo "Initializing MongoDB Replica Sets"

echo "Waiting for MongoDB containers to start..."
sleep 15

echo "Initializing North America replica set..."
docker exec mongodb-na-primary mongosh --eval "
rs.initiate({
  _id: 'rs-na',
  members: [
    { _id: 0, host: 'mongodb-na-primary:27017', priority: 2 },
    { _id: 1, host: 'mongodb-na-secondary1:27017', priority: 1 },
    { _id: 2, host: 'mongodb-na-secondary2:27017', priority: 1 }
  ]
});
"

echo "Waiting for primary election..."
sleep 10

echo "Creating collections and indexes for North America..."
docker exec mongodb-na-primary mongosh meshnetwork --eval "
db.createCollection('users');
db.createCollection('posts');
db.createCollection('operation_log');

db.users.createIndex({ user_id: 1 }, { unique: true });
db.users.createIndex({ region: 1 });
db.users.createIndex({ location: '2dsphere' });
db.users.createIndex({ email: 1 });

db.posts.createIndex({ post_id: 1 }, { unique: true });
db.posts.createIndex({ region: 1, post_type: 1, timestamp: -1 });
db.posts.createIndex({ location: '2dsphere' });
db.posts.createIndex({ user_id: 1 });
db.posts.createIndex({ timestamp: -1 });

db.operation_log.createIndex({ timestamp: 1 });
db.operation_log.createIndex({ synced_to: 1 });
db.operation_log.createIndex({ region_origin: 1 });
"

echo "Initializing Europe replica set..."
docker exec mongodb-eu-primary mongosh --eval "
rs.initiate({
  _id: 'rs-eu',
  members: [
    { _id: 0, host: 'mongodb-eu-primary:27017', priority: 2 },
    { _id: 1, host: 'mongodb-eu-secondary1:27017', priority: 1 },
    { _id: 2, host: 'mongodb-eu-secondary2:27017', priority: 1 }
  ]
});
"

echo "Waiting for primary election..."
sleep 10

echo "Creating collections and indexes for Europe..."
docker exec mongodb-eu-primary mongosh meshnetwork --eval "
db.createCollection('users');
db.createCollection('posts');
db.createCollection('operation_log');

db.users.createIndex({ user_id: 1 }, { unique: true });
db.users.createIndex({ region: 1 });
db.users.createIndex({ location: '2dsphere' });
db.users.createIndex({ email: 1 });

db.posts.createIndex({ post_id: 1 }, { unique: true });
db.posts.createIndex({ region: 1, post_type: 1, timestamp: -1 });
db.posts.createIndex({ location: '2dsphere' });
db.posts.createIndex({ user_id: 1 });
db.posts.createIndex({ timestamp: -1 });

db.operation_log.createIndex({ timestamp: 1 });
db.operation_log.createIndex({ synced_to: 1 });
db.operation_log.createIndex({ region_origin: 1 });
"

echo "Initializing Asia-Pacific replica set..."
docker exec mongodb-ap-primary mongosh --eval "
rs.initiate({
  _id: 'rs-ap',
  members: [
    { _id: 0, host: 'mongodb-ap-primary:27017', priority: 2 },
    { _id: 1, host: 'mongodb-ap-secondary1:27017', priority: 1 },
    { _id: 2, host: 'mongodb-ap-secondary2:27017', priority: 1 }
  ]
});
"

echo "Waiting for primary election..."
sleep 10

echo "Creating collections and indexes for Asia-Pacific..."
docker exec mongodb-ap-primary mongosh meshnetwork --eval "
db.createCollection('users');
db.createCollection('posts');
db.createCollection('operation_log');

db.users.createIndex({ user_id: 1 }, { unique: true });
db.users.createIndex({ region: 1 });
db.users.createIndex({ location: '2dsphere' });
db.users.createIndex({ email: 1 });

db.posts.createIndex({ post_id: 1 }, { unique: true });
db.posts.createIndex({ region: 1, post_type: 1, timestamp: -1 });
db.posts.createIndex({ location: '2dsphere' });
db.posts.createIndex({ user_id: 1 });
db.posts.createIndex({ timestamp: -1 });

db.operation_log.createIndex({ timestamp: 1 });
db.operation_log.createIndex({ synced_to: 1 });
db.operation_log.createIndex({ region_origin: 1 });
"

echo "All replica sets initialized successfully"

echo "North America Replica Set Status:"
docker exec mongodb-na-primary mongosh --quiet --eval "rs.status().members.forEach(m => print(m.name + ': ' + m.stateStr))"

echo "Europe Replica Set Status:"
docker exec mongodb-eu-primary mongosh --quiet --eval "rs.status().members.forEach(m => print(m.name + ': ' + m.stateStr))"

echo "Asia-Pacific Replica Set Status:"
docker exec mongodb-ap-primary mongosh --quiet --eval "rs.status().members.forEach(m => print(m.name + ': ' + m.stateStr))"

echo "Initialization complete"
