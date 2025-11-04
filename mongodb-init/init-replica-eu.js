// Europe Replica Set Initialization Script
// This script initializes the replica set for the Europe region

rs.initiate({
  _id: "rs-eu",
  members: [
    { _id: 0, host: "mongodb-eu-primary:27017", priority: 2 },
    { _id: 1, host: "mongodb-eu-secondary1:27017", priority: 1 },
    { _id: 2, host: "mongodb-eu-secondary2:27017", priority: 1 }
  ]
});

// Wait for replica set to initialize
sleep(5000);

// Switch to meshnetwork database
db = db.getSiblingDB('meshnetwork');

// Create collections
db.createCollection('users');
db.createCollection('posts');
db.createCollection('operation_log');

// ========================================
// USERS COLLECTION INDEXES
// ========================================

// Unique index on user_id
db.users.createIndex({ user_id: 1 }, { unique: true });

// Index on region for regional queries
db.users.createIndex({ region: 1 });

// Geospatial index on location for proximity queries
db.users.createIndex({ location: "2dsphere" });

// Index on email for user lookup
db.users.createIndex({ email: 1 });

// Compound index for region-based user queries
db.users.createIndex({ region: 1, created_at: -1 });

// ========================================
// POSTS COLLECTION INDEXES
// ========================================

// Unique index on post_id
db.posts.createIndex({ post_id: 1 }, { unique: true });

// Compound index for regional post queries filtered by type and sorted by time
db.posts.createIndex({ region: 1, post_type: 1, timestamp: -1 });

// Geospatial index on location for proximity queries
db.posts.createIndex({ location: "2dsphere" });

// Index on user_id for user-specific queries
db.posts.createIndex({ user_id: 1 });

// Index on timestamp for time-based queries
db.posts.createIndex({ timestamp: -1 });

// Index on post_type for filtering by type
db.posts.createIndex({ post_type: 1 });

// ========================================
// OPERATION_LOG COLLECTION INDEXES
// ========================================

// Index on timestamp for time-ordered operations
db.operation_log.createIndex({ timestamp: 1 });

// Index on synced_to for tracking sync status
db.operation_log.createIndex({ synced_to: 1 });

// Index on region_origin for filtering operations by source
db.operation_log.createIndex({ region_origin: 1 });

// Compound index for efficient sync queries
db.operation_log.createIndex({ region_origin: 1, timestamp: 1 });

print("Europe replica set initialized successfully!");
print("Database: meshnetwork");
print("Collections: users, posts, operation_log");
print("All indexes created.");
