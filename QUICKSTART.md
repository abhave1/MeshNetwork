# MeshNetwork - Quick Start Guide

Get MeshNetwork up and running in 5 minutes!

## Prerequisites

✅ Docker Desktop installed and running
✅ At least 8GB RAM available
✅ 10GB free disk space

## Step-by-Step Setup

### 1. Start All Services (2 minutes)

```bash
docker-compose up -d
```

Wait for all services to start. You should see:
```
✔ Container mongodb-na-primary       Started
✔ Container mongodb-na-secondary1    Started
✔ Container mongodb-na-secondary2    Started
✔ Container mongodb-eu-primary       Started
✔ Container mongodb-eu-secondary1    Started
✔ Container mongodb-eu-secondary2    Started
✔ Container mongodb-ap-primary       Started
✔ Container mongodb-ap-secondary1    Started
✔ Container mongodb-ap-secondary2    Started
✔ Container flask-backend-na         Started
✔ Container flask-backend-eu         Started
✔ Container flask-backend-ap         Started
✔ Container react-frontend           Started
```

**Wait 60 seconds** for all health checks to pass.

### 2. Initialize Database (1 minute)

```bash
./scripts/init-all-replicas.sh
```

You should see:
```
=========================================
All replica sets initialized successfully!
=========================================

North America Replica Set Status:
mongodb-na-primary:27017: PRIMARY
mongodb-na-secondary1:27017: SECONDARY
mongodb-na-secondary2:27017: SECONDARY

Europe Replica Set Status:
mongodb-eu-primary:27017: PRIMARY
...
```

### 3. Verify Everything is Working (30 seconds)

Test the backends:
```bash
curl http://localhost:5000/health
curl http://localhost:5001/health
curl http://localhost:5002/health
```

Each should return:
```json
{"status":"healthy","region":"...","service":"meshnetwork-backend"}
```

### 4. Access the Application

Open your browser:
- **Frontend:** http://localhost:3000
- **NA Backend:** http://localhost:5000/status
- **EU Backend:** http://localhost:5001/status
- **AP Backend:** http://localhost:5002/status

## First Steps in the UI

1. **Select Region:** Choose "North America" from the dropdown
2. **Create a Post:**
   - Click "Create Post"
   - Enter a user ID (e.g., "user-001")
   - Select post type (e.g., "Shelter")
   - Enter a message (e.g., "Community center open")
   - Click Submit
3. **View Posts:** Your post appears in the feed!
4. **Switch Regions:** Change to "Europe" and see the same post (after sync)

## Quick Tests

### Test 1: Create and View a Post

```bash
# Create a post in North America
curl -X POST http://localhost:5000/api/posts \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "post_type": "help",
    "message": "Need medical supplies",
    "location": {"type": "Point", "coordinates": [-122.4194, 37.7749]}
  }'

# View posts
curl http://localhost:5000/api/posts
```

### Test 2: Test Automatic Failover

```bash
./scripts/test-failover.sh na
```

This stops the primary MongoDB node and verifies automatic failover.

### Test 3: Test Network Partition

```bash
./scripts/simulate-partition.sh ap
```

This isolates Asia-Pacific and tests island mode operation.

## Troubleshooting

### Services not starting?

```bash
# Check status
docker-compose ps

# Check logs
docker-compose logs flask-backend-na

# Restart
docker-compose restart
```

### Replica sets not initializing?

```bash
# Check MongoDB logs
docker-compose logs mongodb-na-primary

# Try manual initialization
docker exec mongodb-na-primary mongosh --eval "rs.status()"
```

### Frontend not loading?

```bash
# Check frontend logs
docker-compose logs react-frontend

# Rebuild frontend
docker-compose up -d --build react-frontend
```

### Complete reset?

```bash
docker-compose down -v
docker-compose up -d
./scripts/init-all-replicas.sh
```

## What's Next?

- Read the full [README.md](README.md) for detailed documentation
- Explore the API endpoints
- Run the testing scripts
- Modify the code and rebuild

## Common Commands

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f flask-backend-na

# Check service status
docker-compose ps

# Stop all services
docker-compose down

# Stop and remove volumes (deletes data)
docker-compose down -v

# Restart a service
docker-compose restart flask-backend-na

# Rebuild a service
docker-compose up -d --build flask-backend-na
```

## Success Criteria ✅

You should now have:
- ✅ 14 Docker containers running
- ✅ 3 MongoDB replica sets initialized
- ✅ 3 Flask backends responding at ports 5000, 5001, 5002
- ✅ 1 React frontend at port 3000
- ✅ Cross-region replication working
- ✅ Automatic failover functional

## Need Help?

1. Check `docker-compose logs`
2. Review the full [README.md](README.md)
3. Check the Troubleshooting section
4. Ensure Docker has enough resources (8GB+ RAM)

---

**Congratulations!** You now have a fully functional disaster-resilient distributed social platform running locally! 🎉
