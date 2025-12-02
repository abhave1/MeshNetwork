# Failure Test Scripts - Phase 4

Automated test suite for validating fault tolerance and failure simulation requirements.

## Test Scripts

### 1. test-single-node-failure.sh
**Duration:** ~35 seconds
**Tests:** Secondary node failure and recovery
**Validates:**
- System continues with degraded replica set (2/3 nodes)
- Write operations succeed
- Read operations succeed
- Automatic recovery when node restored

**Run:**
```bash
bash test-single-node-failure.sh
```

### 2. test-primary-failure.sh
**Duration:** ~23 seconds
**Tests:** Primary node failure and automatic election
**Validates:**
- New primary elected within <10s (typically ~1s)
- All acknowledged writes preserved
- System operational during failover
- Old primary rejoins as secondary

**Run:**
```bash
bash test-primary-failure.sh
```

### 3. test-network-partition.sh
**Duration:** ~150 seconds (includes 70s island mode wait)
**Tests:** Network isolation and island mode activation
**Validates:**
- Island mode activates after 60s isolation
- Local operations continue during isolation
- Query latency <100ms during island mode
- Automatic reconciliation after reconnection (<30s)
- Zero data loss

**Run:**
```bash
bash test-network-partition.sh
```

### 4. test-cascading-failure.sh
**Duration:** ~120 seconds
**Tests:** Multiple concurrent failures
**Validates:**
- Secondary node failure
- Primary node failure with election
- Network partition (multi-region isolation)
- System operates in degraded mode
- Zero data loss through entire cascade
- Full recovery after restoration

**Run:**
```bash
bash test-cascading-failure.sh
```

### 5. run-all-tests.sh
**Duration:** ~5-6 minutes total
**Master test runner**
**Features:**
- Executes all tests sequentially
- Tracks pass/fail status
- Generates summary report
- Displays final metrics

**Run:**
```bash
bash run-all-tests.sh
```

## Prerequisites

1. System must be running:
```bash
docker-compose up -d
```

2. All regions should be healthy:
```bash
curl http://localhost:5010/health  # North America
curl http://localhost:5011/health  # Europe
curl http://localhost:5012/health  # Asia-Pacific
```

## Success Criteria

All tests validate against Milestone 2 Phase 4 requirements:

| Requirement | Target | Test Script |
|------------|--------|-------------|
| Primary election time | <10s | test-primary-failure.sh |
| Island mode threshold | 60s | test-network-partition.sh |
| Local query latency (island) | <100ms | test-network-partition.sh |
| Cross-region reconciliation | <30s | test-network-partition.sh |
| Data loss | Zero | All tests |
| System resilience | Degraded operation | test-cascading-failure.sh |

## Expected Output

### Successful Test Run
```
==========================================
Test: Primary Node Failure
==========================================

Step 1: Identify current primary
--------------------------------
Current Primary: mongodb-na-primary:27017

[... test steps ...]

==========================================
Test Result: PASSED ✓
==========================================
Total Duration: 23 seconds
Primary Election Time: 1 seconds
Data Loss: Zero
```

### All Tests Summary
```
==========================================
MeshNetwork Phase 4 Failure Test Suite
==========================================

✓ Test 1: Single Node Failure PASSED
✓ Test 2: Primary Node Failure PASSED
✓ Test 3: Network Partition (Island Mode) PASSED
✓ Test 4: Cascading Failures PASSED

==========================================
✓ ALL TESTS PASSED
==========================================

Phase 4 Requirements Validated:
  ✓ Automatic failover and recovery
  ✓ Replica set elections
  ✓ Island mode detection and operation
  ✓ Zero data loss during failures
  ✓ System resilience under stress
```

## Troubleshooting

### Test Fails to Start
**Issue:** "System not running" error
**Solution:**
```bash
docker-compose up -d
sleep 10  # Wait for containers to be ready
```

### Network Already Disconnected
**Issue:** Network disconnect fails
**Solution:**
```bash
# Reconnect first
docker network connect meshnetwork_default flask-backend-na
docker network connect meshnetwork_default flask-backend-eu
docker network connect meshnetwork_default flask-backend-ap
```

### Containers Not Starting
**Issue:** MongoDB nodes show as unhealthy
**Solution:**
```bash
# Restart all containers
docker-compose restart
sleep 20  # Wait for replica sets to elect primaries
```

### Test Cleanup
If a test fails midway, ensure cleanup:
```bash
# Restart stopped containers
docker start mongodb-na-primary mongodb-na-secondary1 mongodb-na-secondary2
docker start mongodb-eu-primary mongodb-eu-secondary1 mongodb-eu-secondary2
docker start mongodb-ap-primary mongodb-ap-secondary1 mongodb-ap-secondary2

# Reconnect networks
docker network connect meshnetwork_default flask-backend-na
docker network connect meshnetwork_default flask-backend-eu
docker network connect meshnetwork_default flask-backend-ap
```

## Test Implementation Details

### Failure Simulation Methods

**Node Failures:**
```bash
docker stop mongodb-na-primary
docker stop mongodb-na-secondary1
```

**Network Partitions:**
```bash
docker network disconnect meshnetwork_default flask-backend-na
```

**Recovery:**
```bash
docker start mongodb-na-primary
docker network connect meshnetwork_default flask-backend-na
```

### Validation Methods

**Health Checks:**
```bash
curl -s http://localhost:5010/health
```

**Island Mode Status:**
```bash
curl -s http://localhost:5010/status | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data['island_mode']['active'])
"
```

**Data Preservation:**
```bash
curl -s "http://localhost:5010/api/posts?limit=50" | python3 -c "
import sys, json
data = json.load(sys.stdin)
found = any(p['post_id'] == '$POST_ID' for p in data['posts'])
print('found' if found else 'not_found')
"
```

## Documentation

For detailed test results and analysis:
- **Test Results:** `/docs/PHASE4_TEST_RESULTS.md`
- **Completion Summary:** `/docs/PHASE4_COMPLETION_SUMMARY.md`

## Version

**Version:** 1.0
**Date:** December 1, 2025
**Phase:** 4 - Fault Tolerance & Failure Simulation
**Status:** Complete
