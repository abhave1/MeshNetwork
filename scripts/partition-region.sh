#!/bin/bash

# Script to partition a region from others while keeping localhost access
# Usage: ./partition-region.sh <region> <action>
# Example: ./partition-region.sh na partition
#          ./partition-region.sh na restore
#          ./partition-region.sh status

set -e

REGION=$1
ACTION=$2

# Special case: reset command clears all partitions
if [ "$REGION" = "reset" ]; then
    echo "=== Resetting all partitions ==="
    for container in flask-backend-na flask-backend-eu flask-backend-ap; do
        docker exec $container rm -f /tmp/PARTITIONED 2>/dev/null || true
        docker exec $container sh -c "grep -v '0.0.0.0 flask-backend' /etc/hosts > /tmp/hosts.tmp && cat /tmp/hosts.tmp > /etc/hosts" 2>/dev/null || true
    done
    echo "✓ All partitions cleared"
    echo ""
    $0 status
    exit 0
fi

# Special case: status command shows all partition states
if [ "$REGION" = "status" ]; then
    echo "=== Partition Status ==="
    echo ""
    
    for region in na eu ap; do
        case $region in
            na) container="flask-backend-na"; name="North America" ;;
            eu) container="flask-backend-eu"; name="Europe" ;;
            ap) container="flask-backend-ap"; name="Asia-Pacific" ;;
        esac
        
        # Check if this region initiated its own partition (has marker file)
        is_partitioned=$(docker exec $container sh -c "test -f /tmp/PARTITIONED && echo 'yes' || echo 'no'" 2>/dev/null)
        
        # Count blocks in /etc/hosts for additional info
        blocked=$(docker exec $container cat /etc/hosts 2>/dev/null | grep "0.0.0.0 flask-backend" | wc -l | tr -d ' ')
        
        if [ "$is_partitioned" = "yes" ]; then
            echo "🏝️  $name ($region): PARTITIONED (blocking $blocked regions)"
        elif [ "$blocked" -gt 0 ]; then
            echo "🔗 $name ($region): Connected (has $blocked incoming blocks from other partitions)"
        else
            echo "🔗 $name ($region): Connected"
        fi
    done
    
    echo ""
    exit 0
fi

if [ -z "$REGION" ] || [ -z "$ACTION" ]; then
    echo "Usage: $0 <region> <partition|restore>"
    echo "       $0 status"
    echo "       $0 reset"
    echo ""
    echo "Examples:"
    echo "  $0 na partition  - Partition North America from other regions"
    echo "  $0 na restore    - Restore North America connectivity only"
    echo "  $0 status        - Show current partition status for all regions"
    echo "  $0 reset         - Clear ALL partitions (full reset)"
    exit 1
fi

case $REGION in
    na)
        CONTAINER="flask-backend-na"
        TARGET1="flask-backend-eu"
        TARGET2="flask-backend-ap"
        PORT="5010"
        TARGET1_PORT="5011"
        TARGET2_PORT="5012"
        ;;
    eu)
        CONTAINER="flask-backend-eu"
        TARGET1="flask-backend-na"
        TARGET2="flask-backend-ap"
        PORT="5011"
        TARGET1_PORT="5010"
        TARGET2_PORT="5012"
        ;;
    ap)
        CONTAINER="flask-backend-ap"
        TARGET1="flask-backend-na"
        TARGET2="flask-backend-eu"
        PORT="5012"
        TARGET1_PORT="5010"
        TARGET2_PORT="5011"
        ;;
    *)
        echo "Invalid region: $REGION (must be na, eu, or ap)"
        exit 1
        ;;
esac

if [ "$ACTION" = "partition" ]; then
    echo "Partitioning $REGION from other regions..."

    # Mark this region as partitioned (for tracking)
    docker exec $CONTAINER sh -c "touch /tmp/PARTITIONED"

    # Block traffic by adding black hole IPs to /etc/hosts (avoid duplicates)
    docker exec $CONTAINER sh -c "grep -q '0.0.0.0 $TARGET1' /etc/hosts || echo '0.0.0.0 $TARGET1' >> /etc/hosts"
    docker exec $CONTAINER sh -c "grep -q '0.0.0.0 $TARGET2' /etc/hosts || echo '0.0.0.0 $TARGET2' >> /etc/hosts"

    # Also block from the other direction - make others not try to reach this region (avoid duplicates)
    docker exec $TARGET1 sh -c "grep -q '0.0.0.0 $CONTAINER' /etc/hosts || echo '0.0.0.0 $CONTAINER' >> /etc/hosts"
    docker exec $TARGET2 sh -c "grep -q '0.0.0.0 $CONTAINER' /etc/hosts || echo '0.0.0.0 $CONTAINER' >> /etc/hosts"

    echo "Partition activated"
    echo "✓ $REGION is now partitioned from other regions"
    echo "  - localhost:$PORT still accessible"
    echo "  - Local database operations continue"
    echo "  - Cannot communicate with other regions"

elif [ "$ACTION" = "restore" ]; then
    echo "Restoring $REGION connectivity..."

    # Remove partition marker
    docker exec $CONTAINER sh -c "rm -f /tmp/PARTITIONED" 2>/dev/null || true
    
    # Check which targets are partitioned BEFORE removing blocks
    TARGET1_IS_PARTITIONED=$(docker exec $TARGET1 sh -c "test -f /tmp/PARTITIONED && echo 'yes' || echo 'no'" 2>/dev/null)
    TARGET2_IS_PARTITIONED=$(docker exec $TARGET2 sh -c "test -f /tmp/PARTITIONED && echo 'yes' || echo 'no'" 2>/dev/null)
    
    # Remove blocks from this region's /etc/hosts, but KEEP blocks for regions that are still partitioned
    # (those blocks are "incoming" from the other region's partition)
    if [ "$TARGET1_IS_PARTITIONED" = "no" ]; then
        docker exec $CONTAINER sh -c "grep -v '0.0.0.0 $TARGET1' /etc/hosts > /tmp/hosts.tmp && cat /tmp/hosts.tmp > /etc/hosts" 2>/dev/null || true
    fi
    if [ "$TARGET2_IS_PARTITIONED" = "no" ]; then
        docker exec $CONTAINER sh -c "grep -v '0.0.0.0 $TARGET2' /etc/hosts > /tmp/hosts.tmp && cat /tmp/hosts.tmp > /etc/hosts" 2>/dev/null || true
    fi

    # Remove this region's block from other containers
    # BUT only if that other region is NOT itself partitioned (check for marker file)
    if [ "$TARGET1_IS_PARTITIONED" = "no" ]; then
        docker exec $TARGET1 sh -c "grep -v '0.0.0.0 $CONTAINER' /etc/hosts > /tmp/hosts.tmp && cat /tmp/hosts.tmp > /etc/hosts" 2>/dev/null || true
        echo "  ✓ $REGION ↔ $TARGET1: bidirectional communication restored"
    else
        echo "  ⚠ $REGION ↔ $TARGET1: $TARGET1 is partitioned, both directions blocked"
    fi
    
    if [ "$TARGET2_IS_PARTITIONED" = "no" ]; then
        docker exec $TARGET2 sh -c "grep -v '0.0.0.0 $CONTAINER' /etc/hosts > /tmp/hosts.tmp && cat /tmp/hosts.tmp > /etc/hosts" 2>/dev/null || true
        echo "  ✓ $REGION ↔ $TARGET2: bidirectional communication restored"
    else
        echo "  ⚠ $REGION ↔ $TARGET2: $TARGET2 is partitioned, both directions blocked"
    fi

    echo ""
    echo "✓ $REGION restored (keeping blocks for still-partitioned regions)"

else
    echo "Invalid action: $ACTION (must be partition or restore)"
    exit 1
fi
