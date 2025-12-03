# MeshNetwork - Disaster Resilient Social Platform

A geo-distributed, fault-tolerant social platform designed for disaster scenarios where availability is prioritized over consistency (AP in CAP theorem). Built for CSE 512 Distributed Database Systems.

## Overview

During natural disasters, communication infrastructure fails. MeshNetwork allows users to post emergency information (shelters, help requests, safety status) that remains accessible even when regions are network-isolated. Each geographic region operates independently and syncs with other regions when connectivity is restored.

## Architecture

### System Components

- **3 Geographic Regions:** North America, Europe, Asia-Pacific
- **9 MongoDB Nodes:** 3 nodes per region (1 primary + 2 secondaries)
- **3 Flask Backends:** One per region
- **1 React Frontend:** Can connect to any region
- **4 Docker Networks:** 3 regional + 1 global

### Key Features

- **Island Mode:** Regions continue operating when isolated from other regions
- **Automatic Failover:** If primary MongoDB node fails, secondary automatically promoted
- **Cross-Region Sync:** Background process propagates updates between regions
- **Last-Write-Wins:** Timestamp-based conflict resolution

## Technology Stack

- **Database:** MongoDB 6.0+ (replica sets)
- **Backend:** Python 3.10+ with Flask
- **Frontend:** React 18+ with TypeScript
- **Containerization:** Docker & Docker Compose

## Prerequisites

- Docker Desktop or Docker Engine (20.10+)
- Docker Compose (2.0+)
- 8GB+ RAM recommended
- 10GB+ free disk space

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd MeshNetwork
```

### 2. Start All Services

```bash
docker-compose up -d
```

This will start 14 services:
- 9 MongoDB containers (3 regions × 3 nodes)
- 3 Flask backend containers
- 1 React frontend container

Wait about 60 seconds for all services to be healthy.

### 3. Initialize MongoDB Replica Sets

```bash
chmod +x scripts/init-all-replicas.sh
./scripts/init-all-replicas.sh
```

This script:
- Initializes replica sets for all 3 regions
- Creates collections (users, posts, operation_log)
- Creates indexes for optimal query performance
- Verifies replica set status

### 4. Access the Application

- **Frontend:** http://localhost:3000
- **North America Backend:** http://localhost:5010
- **Europe Backend:** http://localhost:5011
- **Asia-Pacific Backend:** http://localhost:5012

### 5. Verify Everything is Working

Run the automated verification script to check all services, database connections, and cross-region connectivity:

```bash
chmod +x scripts/verify-setup.sh
./scripts/verify-setup.sh
```

Alternatively, you can manually check backend health:
```bash
curl http://localhost:5010/health
curl http://localhost:5011/health
curl http://localhost:5012/health
```

Check detailed status:
```bash
curl http://localhost:5010/status | jq
```

### 6. Restart Flask backends

If facing issues with Step 5, run this command:
```bash
docker restart flask-backend-na flask-backend-eu flask-backend-ap
```

### 7. Initialize Data

To create mock data that will be replicated to all servers, use the following command:
```bash
python generate_data.py --users <number of users> --posts-per-user <number of posts per user>
```

For default 1 million posts:
```bash
python generate_data.py --users 10000 --posts-per-user 100 
```

## Usage

### Creating a Post via API

```bash
curl -X POST http://localhost:5010/api/posts \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "post_type": "shelter",
    "message": "Community center open, capacity 100",
    "location": {
      "type": "Point",
      "coordinates": [-122.4194, 37.7749]
    },
    "capacity": 100
  }'
```

### Getting Posts

```bash
# Get all posts in North America
curl http://localhost:5010/api/posts

# Filter by post type
curl "http://localhost:5010/api/posts?post_type=shelter"

# Limit results
curl "http://localhost:5010/api/posts?limit=10"
```

### Creating a User

```bash
curl -X POST http://localhost:5010/api/users \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "region": "north_america",
    "location": {
      "type": "Point",
      "coordinates": [-122.4194, 37.7749]
    }
  }'
```

### Using the Frontend

1. Open http://localhost:3000
2. Select a region from the dropdown
3. Click "Create Post" to add new posts
4. View posts in the feed
5. System status shows database health

## Testing

### Test Automatic Failover

Test MongoDB's automatic failover by stopping the primary node:

```bash
chmod +x scripts/test-failover.sh
./scripts/test-failover.sh na    # Test North America
./scripts/test-failover.sh eu    # Test Europe
./scripts/test-failover.sh ap    # Test Asia-Pacific
```

**What this tests:**
1. Stops the primary MongoDB node
2. Verifies a secondary is elected as new primary
3. Tests that writes continue working
4. Restarts original primary (joins as secondary)

**Expected result:** The replica set automatically elects a new primary within 15 seconds, and operations continue without manual intervention.

### Simulate Network Partition

Test "island mode" by isolating a region:

```bash
chmod +x scripts/simulate-partition.sh
./scripts/simulate-partition.sh ap    # Isolate Asia-Pacific
./scripts/simulate-partition.sh eu    # Isolate Europe
./scripts/simulate-partition.sh na    # Isolate North America
```

**What this tests:**
1. Disconnects a region from the global network
2. Verifies the region continues operating locally
3. Confirms other regions are unreachable
4. Reconnects the region
5. Verifies synchronization resumes

**Expected result:** The isolated region continues serving requests locally, queues changes for sync, and successfully syncs when reconnected.

### Advanced Failure Testing

For more complex failure scenarios, use the scripts in `scripts/failure-tests/`:

```bash
# Run all failure tests suite
./scripts/failure-tests/run-all-tests.sh

# Test specific scenarios
./scripts/failure-tests/test-single-node-failure.sh
./scripts/failure-tests/test-primary-failure.sh
./scripts/failure-tests/test-network-partition.sh
./scripts/failure-tests/test-cascading-failure.sh
```

You can also use `scripts/partition-region.sh` for more granular network partition control (blocking specific host entries) instead of full network disconnection:

```bash
./scripts/partition-region.sh na partition  # Partition North America
./scripts/partition-region.sh na restore    # Restore North America
./scripts/partition-region.sh status        # Check partition status
```

### Performance & Phase Testing

The project includes specific test scripts for performance and replication phases:

```bash
# Phase 2: Performance Testing
python test_phase2_performance.py

# Phase 3: Replication Testing
python test_phase3_replication.py
```

See `TEST_EXECUTION_SUMMARY.md` for details on test execution and `TEST_RESULTS_*.txt` for past results.

### Manual Testing Scenarios

#### 1. Test Cross-Region Data Visibility

```bash
# Create a post in North America
curl -X POST http://localhost:5010/api/posts -H "Content-Type: application/json" \
  -d '{"user_id":"user1","post_type":"help","message":"Test from NA","location":{"type":"Point","coordinates":[0,0]}}'

# Wait 10 seconds for sync
sleep 10

# Query from Europe
curl "http://localhost:5011/api/posts?limit=5"

# The post should appear in Europe's results
```

#### 2. Test Write During Partition

```bash
# Isolate Asia-Pacific
docker network disconnect network-global flask-backend-ap

# Write to Asia-Pacific (should still work locally)
curl -X POST http://localhost:5012/api/posts -H "Content-Type: application/json" \
  -d '{"user_id":"user2","post_type":"food","message":"Food available","location":{"type":"Point","coordinates":[0,0]}}'

# Reconnect
docker network connect network-global flask-backend-ap

# Wait for sync
sleep 10

# Verify post appears in other regions
curl http://localhost:5010/api/posts
```

## Database Schema

### Users Collection

```javascript
{
  user_id: "uuid",
  name: "string",
  email: "string",
  region: "north_america" | "europe" | "asia_pacific",
  location: { type: "Point", coordinates: [lon, lat] },
  verified: boolean,
  reputation: number,
  created_at: ISODate
}
```

**Indexes:**
- `{user_id: 1}` (unique)
- `{region: 1}`
- `{location: "2dsphere"}`
- `{email: 1}`

### Posts Collection

```javascript
{
  post_id: "uuid",
  user_id: "uuid",
  post_type: "shelter" | "food" | "medical" | "water" | "safety" | "help",
  message: "string",
  location: { type: "Point", coordinates: [lon, lat] },
  region: "north_america" | "europe" | "asia_pacific",
  capacity: number (optional),
  timestamp: ISODate,
  last_modified: ISODate
}
```

**Indexes:**
- `{post_id: 1}` (unique)
- `{region: 1, post_type: 1, timestamp: -1}` (compound)
- `{location: "2dsphere"}`
- `{user_id: 1}`
- `{timestamp: -1}`

### Operation Log Collection

Used for cross-region synchronization:

```javascript
{
  operation_type: "insert" | "update" | "delete",
  collection: "users" | "posts",
  document_id: "uuid",
  data: object,
  timestamp: ISODate,
  synced_to: [array of region URLs],
  region_origin: "north_america" | "europe" | "asia_pacific"
}
```

## Port Assignments

| Service | Port |
|---------|------|
| React Frontend | 3000 |
| North America Backend | 5010 |
| Europe Backend | 5011 |
| Asia-Pacific Backend | 5012 |
| MongoDB NA Primary | 27017 |
| MongoDB NA Secondary1 | 27018 |
| MongoDB NA Secondary2 | 27019 |
| MongoDB EU Primary | 27020 |
| MongoDB EU Secondary1 | 27021 |
| MongoDB EU Secondary2 | 27022 |
| MongoDB AP Primary | 27023 |
| MongoDB AP Secondary1 | 27024 |
| MongoDB AP Secondary2 | 27025 |

## API Documentation

### Health Endpoints

#### GET /health
Returns basic health status.

**Response:**
```json
{
  "status": "healthy",
  "region": "north_america",
  "service": "meshnetwork-backend"
}
```

#### GET /status
Returns detailed system status.

**Response:**
```json
{
  "status": "healthy",
  "region": {
    "name": "north_america",
    "display_name": "North America"
  },
  "database": {
    "status": "healthy",
    "replica_set": "rs-na",
    "primary": "mongodb-na-primary:27017",
    "members": [...]
  },
  "remote_regions": {
    "http://flask-backend-eu:5011": "reachable",
    "http://flask-backend-ap:5012": "reachable"
  }
}
```

### Post Endpoints

#### GET /api/posts
Get posts with optional filters.

**Query Parameters:**
- `post_type`: Filter by type (shelter, food, medical, water, safety, help)
- `region`: Filter by region
- `limit`: Maximum results (default: 100)

#### POST /api/posts
Create a new post.

**Request Body:**
```json
{
  "user_id": "string",
  "post_type": "shelter|food|medical|water|safety|help",
  "message": "string",
  "location": {
    "type": "Point",
    "coordinates": [longitude, latitude]
  },
  "capacity": 100 (optional)
}
```

#### PUT /api/posts/{post_id}
Update a post.

#### DELETE /api/posts/{post_id}
Delete a post.

### User Endpoints

#### GET /api/users/{user_id}
Get user by ID.

#### POST /api/users
Create a new user.

#### POST /api/mark-safe
Mark a user as safe (creates a safety status post).