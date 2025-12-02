# Frontend Testing Guide - Phase 4 Island Mode

Complete step-by-step guide for testing Phase 4 fault tolerance features using the frontend UI.

---

## Test 1: Island Mode Activation & Deactivation

**Duration:** ~2-3 minutes
**What you'll see:** Yellow warning banner appears after 60 seconds of isolation

### Prerequisites

```bash
# Make sure system is running
cd /Users/apgupta/Documents/Fall2025/CSE512/MeshNetwork
docker-compose up -d

# Wait 20 seconds for everything to stabilize
sleep 20
```

### Step 1: Open Frontend & Verify Normal State

```bash
# Open browser (or navigate to)
open http://localhost:3000
```

**What you should see:**
- Header: "MeshNetwork - Disaster Resilient Social Platform"
- Connected Region: North America
- **System Status section** showing:
  - Database: healthy
  - Replica Set: rs-na
  - Primary: mongodb-na-primary:27017 (or similar)
- **NO yellow warning banner**
- "All times displayed in UTC" message
- Recent Posts section (may be empty)

### Step 2: Create a Baseline Test Post (Optional)

Click **"Create Post"** button

Fill in the form:
- **User ID:** `test_user_before_island`
- **Post Type:** Select `Safety Status`
- **Message:** `Test post created BEFORE island mode activation`
- **Location:** Leave default (37.7749, -122.4194)

Click **"Submit Post"**

**Expected Result:**
- Success message
- Post appears in Recent Posts section
- Note the timestamp (will verify this survives later)

### Step 3: Simulate Network Partition

**Open a terminal** and run:

```bash
# Partition NA from other regions by modifying container hostnames
bash scripts/partition-region.sh na partition
```

**Expected Terminal Output:**
```
Partitioning na from other regions...
Partition activated
✓ na is now partitioned from other regions
  - localhost:5010 still accessible
  - Local database operations continue
  - Cannot communicate with other regions
```

This isolates NA while:
- ✓ You can still access NA at localhost:5010
- ✓ NA's local database works normally
- ✓ NA can create and read posts locally
- ✓ EU and AP continue syncing with each other

**In the Browser:**
- Nothing changes immediately
- Frontend still works normally
- You're now in the "isolation period" (0-60 seconds)

### Step 4: Watch for Island Mode Activation (Wait 70 seconds)

**Keep the browser window open and visible.**

Start a timer or run this command to track time:
```bash
# In terminal - counts down 70 seconds
for i in {70..1}; do echo -ne "Waiting for island mode: ${i}s remaining\r"; sleep 1; done; echo "Check browser now!"
```

**During the first 60 seconds:**
- Click **"Refresh Posts"** every 15-20 seconds
- System Status should still show Database: healthy
- No warning banner yet

**After ~60-70 seconds:**

**🎯 THE YELLOW WARNING BANNER SHOULD APPEAR AUTOMATICALLY!**
(No need to refresh the page - it will appear on its own!)

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️  ISLAND MODE ACTIVE                                   │
│                                                          │
│ This region is isolated from other regions.             │
│ Isolated for 75s. Local operations continue normally,   │
│ but cross-region sync is paused.                        │
└─────────────────────────────────────────────────────────┘
```

**Banner Features:**
- Yellow/amber background (#FFC107)
- Warning icon: ⚠️
- Pulsing shadow animation (watch it pulse every 2 seconds)
- **LIVE isolation duration counter** - updates every second (75s → 76s → 77s...)
- Appears automatically without page refresh
- Clear message about status

**System Status section may also update to show:**
- Island Mode: ISLAND MODE (instead of "connected")

### Step 5: Test Local Operations During Island Mode

**Click "Create Post" button again**

Fill in the form:
- **User ID:** `test_user_during_island`
- **Post Type:** Select `Help Request`
- **Message:** `Emergency! Post created DURING island mode - should still work!`
- **Location:** Leave default

Click **"Submit Post"**

**Expected Result:**
- ✓ Post creation SUCCEEDS (local database still works!)
- Post appears in Recent Posts section
- No errors
- This proves local operations continue during isolation

**Click "Refresh Posts"**
- Both posts visible (before and during island mode)
- Timestamps showing correctly in UTC

### Step 6: Restore Connectivity

**In the terminal:**

```bash
# Restore NA connectivity
bash scripts/partition-region.sh na restore

# Wait for reconnection
sleep 10
```

**Expected Terminal Output:**
```
Restoring na connectivity...
Connectivity restored
✓ na connectivity restored
```

### Step 7: Watch Island Mode Deactivate

**In the Browser:**

Just wait ~10-20 seconds and watch the screen (no need to refresh).

**Expected Result:**
- 🎯 **The yellow warning banner DISAPPEARS AUTOMATICALLY**
- System Status returns to normal automatically
- Database: healthy
- Island Mode: connected (or status not shown)
- Both your test posts still visible (no data loss!)

### Step 8: Verify Cross-Region Sync Resumed

**Optional - Switch to Europe region:**

In the region dropdown at the top, select **"Europe"**

Click **"Refresh Posts"**

**Expected Result:**
- Your posts from NA should appear in EU after ~5-10 seconds
- This proves cross-region sync resumed after reconnection

---

## Test 2: Primary Node Failure (Quick Test)

**Duration:** ~30 seconds
**What you'll see:** System continues working seamlessly during failover

### Step 1: Verify Current Primary

Look at **System Status** section:
- Note the Primary node (e.g., `mongodb-na-primary:27017`)

### Step 2: Create Test Post

Create a post:
- **User ID:** `test_before_failover`
- **Message:** `Post before primary failure`
- Click Submit

### Step 3: Kill Primary Node

**In terminal:**
```bash
docker stop mongodb-na-primary
```

### Step 4: Immediately Test Frontend

**Within 2-3 seconds, in the browser:**

Click **"Refresh Posts"** rapidly (3-4 times in a row)

**Expected Result:**
- ✓ NO ERRORS! (system automatically elected new primary)
- Your post still visible
- System Status shows different primary now (e.g., `mongodb-na-secondary1:27017`)
- Database status: still "healthy"

### Step 5: Create Another Post

Create a post:
- **User ID:** `test_after_failover`
- **Message:** `Post after primary failover - writing to new primary!`
- Click Submit

**Expected Result:**
- ✓ Post creation succeeds (writes to new primary)
- Both posts visible

### Step 6: Restore Old Primary

```bash
docker start mongodb-na-primary
sleep 10
```

**In browser:** Click "Refresh Posts"
- Both posts still visible
- Old primary rejoined as SECONDARY

---

## Test 3: Cross-Region Synchronization

**Duration:** ~2 minutes
**What you'll see:** Posts replicate across regions

### Step 1: Open Two Browser Windows

**Window 1:** http://localhost:3000
- Should show "North America" in region dropdown

**Window 2:** Same URL, but then change dropdown to **"Europe"**

### Step 2: Create Post in North America

**In Window 1 (North America):**
- Create a post with message: `Cross-region test from NA`
- Click Submit

### Step 3: Watch It Appear in Europe

**In Window 2 (Europe):**
- Wait 5-10 seconds
- Click "Refresh Posts"

**Expected Result:**
- The NA post appears in Europe! (cross-region sync working)
- May take up to 10 seconds for replication

### Step 4: Create Post in Europe

**In Window 2 (Europe):**
- Create a post with message: `Cross-region test from EU`
- Click Submit

### Step 5: See It in North America

**In Window 1 (North America):**
- Wait 5-10 seconds
- Click "Refresh Posts"

**Expected Result:**
- The EU post appears in North America!
- Both directions of sync working

---

## Visual Checklist

### ✓ Normal Operation (What You Should See)
- [ ] No yellow warning banner
- [ ] System Status shows "Database: healthy"
- [ ] Can create posts successfully
- [ ] Can refresh and see posts
- [ ] Posts sync between regions

### ✓ Island Mode Active (What You Should See)
- [ ] **Yellow warning banner visible** with ⚠️ icon
- [ ] Banner shows "ISLAND MODE ACTIVE"
- [ ] Banner shows isolation duration (e.g., "Isolated for 75s")
- [ ] Banner has pulsing animation
- [ ] System Status may show "Island Mode: ISLAND MODE"
- [ ] Can STILL create posts locally (proves system works)
- [ ] Can STILL refresh posts (local queries work)

### ✓ After Reconnection (What You Should See)
- [ ] Yellow warning banner GONE
- [ ] System Status back to normal
- [ ] All posts created during island mode still visible
- [ ] Cross-region sync resumed

---

## Troubleshooting

### "Error: timeout of 5000ms exceeded"

**This is EXPECTED during isolation!** It means the frontend tried to query other regions but couldn't reach them. This is normal and doesn't affect local operations.

Just click the **X** to dismiss it.

### Warning banner doesn't appear after 70 seconds

**Check if NA is actually disconnected:**
```bash
docker inspect flask-backend-na | grep -A 5 "Networks"
# Should NOT see "network-global" in the output
```

If you still see network-global, disconnect it:
```bash
docker network disconnect network-global flask-backend-na
```

Then wait another 70 seconds.

### System Status section not showing

**Hard refresh the page:**
- Mac: Cmd + Shift + R
- Windows/Linux: Ctrl + Shift + R

Or check backend is running:
```bash
curl http://localhost:5010/status
```

### Posts not syncing between regions

**Wait longer** - sync happens every 5 seconds, but may take 10-15 seconds to show.

Also verify backends are running:
```bash
docker ps | grep flask-backend
# Should see all three: na, eu, ap
```

### Reset Everything

If something goes wrong:

```bash
# Reconnect NA to network (if disconnected)
docker network connect network-global flask-backend-na

# Restart all backends
docker restart flask-backend-na flask-backend-eu flask-backend-ap

# Wait for stabilization
sleep 20

# Hard refresh browser (Cmd+Shift+R or Ctrl+Shift+R)
```

---

## Success Criteria Summary

By the end of testing, you should have verified:

✓ **Island Mode Detection**
- Yellow warning banner appears after 60s isolation
- Banner shows isolation duration
- Banner disappears when reconnected

✓ **Local Operations During Island Mode**
- Can create posts while isolated
- Can read posts while isolated
- No errors or failures

✓ **Zero Data Loss**
- Posts created before island mode: preserved
- Posts created during island mode: preserved
- Posts created after reconnection: work normally

✓ **Automatic Failover**
- Primary failure doesn't cause errors
- New primary elected automatically
- System continues operating

✓ **Cross-Region Sync**
- Posts replicate from NA → EU
- Posts replicate from EU → NA
- Sync resumes after island mode

---

## What This Proves

These tests demonstrate that your MeshNetwork platform:

1. **Detects network isolation** automatically (60s threshold)
2. **Notifies users** with visual warnings
3. **Continues operating locally** during regional isolation
4. **Preserves all data** during failures
5. **Recovers automatically** when connectivity restored
6. **Handles database failures** transparently
7. **Synchronizes data across regions** seamlessly

All Phase 4 requirements validated through the frontend! 🎉

---

**Testing Time:** ~5-10 minutes total
**Phase 4 Status:** ✓ COMPLETE and user-verified
