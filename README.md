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
- **Query Routing:** Queries go to local region first (fast), then global if needed
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
- **North America Backend:** http://localhost:5000
- **Europe Backend:** http://localhost:5001
- **Asia-Pacific Backend:** http://localhost:5002

### 5. Verify Everything is Working

Check backend health:
```bash
curl http://localhost:5000/health
curl http://localhost:5001/health
curl http://localhost:5002/health
```

Check detailed status:
```bash
curl http://localhost:5000/status | jq
```

## Usage

### Creating a Post via API

```bash
curl -X POST http://localhost:5000/api/posts \
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
curl http://localhost:5000/api/posts

# Filter by post type
curl "http://localhost:5000/api/posts?post_type=shelter"

# Limit results
curl "http://localhost:5000/api/posts?limit=10"
```

### Creating a User

```bash
curl -X POST http://localhost:5000/api/users \
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

### Manual Testing Scenarios

#### 1. Test Cross-Region Data Visibility

```bash
# Create a post in North America
curl -X POST http://localhost:5000/api/posts -H "Content-Type: application/json" \
  -d '{"user_id":"user1","post_type":"help","message":"Test from NA","location":{"type":"Point","coordinates":[0,0]}}'

# Wait 10 seconds for sync
sleep 10

# Query from Europe
curl "http://localhost:5001/api/posts?limit=5"

# The post should appear in Europe's results
```

#### 2. Test Write During Partition

```bash
# Isolate Asia-Pacific
docker network disconnect network-global flask-backend-ap

# Write to Asia-Pacific (should still work locally)
curl -X POST http://localhost:5002/api/posts -H "Content-Type: application/json" \
  -d '{"user_id":"user2","post_type":"food","message":"Food available","location":{"type":"Point","coordinates":[0,0]}}'

# Reconnect
docker network connect network-global flask-backend-ap

# Wait for sync
sleep 10

# Verify post appears in other regions
curl http://localhost:5000/api/posts
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         React Frontend                          │
│                     http://localhost:3000                       │
└────────────┬────────────────────────────────────┬──────────────┘
             │                                     │
             │         Global Network              │
             │                                     │
┌────────────┴──────────┐         ┌───────────────┴──────────────┐
│   North America       │         │   Europe          │   Asia-Pacific  │
│   Region              │◄────────┤   Region          │   Region        │
└───────────────────────┘         └───────────────────┴─────────────────┘
│                                 │                   │
│  Flask Backend (5000)           │  Flask Backend (5001)  │  Flask Backend (5002)
│       │                         │       │           │       │
│       ├─MongoDB Primary         │       ├─MongoDB Primary  │       ├─MongoDB Primary
│       ├─MongoDB Secondary       │       ├─MongoDB Secondary│       ├─MongoDB Secondary
│       └─MongoDB Secondary       │       └─MongoDB Secondary│       └─MongoDB Secondary
│                                 │                   │
│  Replica Set: rs-na             │  Replica Set: rs-eu     │  Replica Set: rs-ap
└─────────────────────────────────┴────────────────────────────────────┘

Key:
◄────► Cross-region async replication
├─     Replica set member
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
| North America Backend | 5000 |
| Europe Backend | 5001 |
| Asia-Pacific Backend | 5002 |
| MongoDB NA Primary | 27017 |
| MongoDB NA Secondary1 | 27018 |
| MongoDB NA Secondary2 | 27019 |
| MongoDB EU Primary | 27020 |
| MongoDB EU Secondary1 | 27021 |
| MongoDB EU Secondary2 | 27022 |
| MongoDB AP Primary | 27023 |
| MongoDB AP Secondary1 | 27024 |
| MongoDB AP Secondary2 | 27025 |

## Troubleshooting

### Services Won't Start

```bash
# Check service status
docker-compose ps

# Check logs for specific service
docker-compose logs flask-backend-na
docker-compose logs mongodb-na-primary

# Restart all services
docker-compose restart
```

### Replica Set Initialization Failed

```bash
# Check MongoDB logs
docker-compose logs mongodb-na-primary

# Manually check replica set status
docker exec mongodb-na-primary mongosh --eval "rs.status()"

# Re-run initialization
./scripts/init-all-replicas.sh
```

### Backend Can't Connect to MongoDB

```bash
# Check if MongoDB is healthy
docker exec mongodb-na-primary mongosh --eval "db.runCommand('ping')"

# Check backend logs
docker-compose logs flask-backend-na

# Restart backend
docker-compose restart flask-backend-na
```

### Frontend Can't Connect to Backend

```bash
# Check backend is running
curl http://localhost:5000/health

# Check CORS is enabled
curl -H "Origin: http://localhost:3000" http://localhost:5000/health -v

# Check frontend logs
docker-compose logs react-frontend
```

### Clean Reset

To completely reset the system:

```bash
# Stop all services
docker-compose down

# Remove all volumes (WARNING: deletes all data)
docker-compose down -v

# Remove all containers and images
docker-compose down --rmi all

# Start fresh
docker-compose up -d
./scripts/init-all-replicas.sh
```

## Development

### Running Backend Locally (Outside Docker)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export REGION=north_america
export MONGODB_URI=mongodb://localhost:27017,localhost:27018,localhost:27019/meshnetwork?replicaSet=rs-na
export FLASK_PORT=5000

# Run
python app.py
```

### Running Frontend Locally

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

### Running Tests

```bash
cd backend

# Run unit tests
pytest

# Run with coverage
pytest --cov=.
```

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
    "http://flask-backend-eu:5001": "reachable",
    "http://flask-backend-ap:5002": "reachable"
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

## Performance Considerations

### Write Performance
- Writes require majority acknowledgment within replica set
- Cross-region replication is asynchronous (eventual consistency)
- Expected write latency: 10-50ms (local), 100-500ms (cross-region)

### Read Performance
- Reads from primary or secondaries (primaryPreferred)
- Local queries are fast (< 10ms)
- Cross-region queries may be slower (100-500ms)

### Scalability
- Each region can handle ~1000 req/sec
- Horizontal scaling: Add more replica set members
- Sharding: Can add hash-based sharding within regions

## CAP Theorem Trade-offs

This system is **AP (Availability + Partition Tolerance)**:

- ✅ **Availability:** Each region continues operating during partitions
- ✅ **Partition Tolerance:** System functions despite network failures
- ⚠️ **Consistency:** Eventual consistency across regions (not strong consistency)

### Consistency Model

- **Strong consistency** within a region (replica set)
- **Eventual consistency** across regions
- **Conflict resolution:** Last-Write-Wins based on timestamps

## Future Enhancements

- [ ] User authentication and authorization
- [ ] Real-time updates using WebSockets
- [ ] Map view with geospatial queries
- [ ] Push notifications for nearby help requests
- [ ] Image upload support
- [ ] Mobile app (React Native)
- [ ] Load balancing with multiple backend instances per region
- [ ] Monitoring dashboard (Grafana + Prometheus)
- [ ] Automated testing with GitHub Actions

## License

MIT License - see LICENSE file for details

## Contributors

Built for CSE 512 Distributed Database Systems

## Support

For issues or questions:
1. Check the Troubleshooting section
2. Review Docker logs: `docker-compose logs`
3. Open an issue on GitHub

---

**Note:** This is an educational project demonstrating distributed systems concepts. Not intended for production use without additional security and reliability improvements.
