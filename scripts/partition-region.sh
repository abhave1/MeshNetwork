#!/bin/bash

set -e

REGION=$1
ACTION=$2

if [ "$REGION" = "reset" ]; then
    echo "Resetting all partitions"
    for container in flask-backend-na flask-backend-eu flask-backend-ap; do
        docker exec $container rm -f /tmp/PARTITIONED 2>/dev/null || true
        docker exec $container sh -c "grep -v '0.0.0.0 flask-backend' /etc/hosts > /tmp/hosts.tmp && cat /tmp/hosts.tmp > /etc/hosts" 2>/dev/null || true
    done
    echo "All partitions cleared"
    $0 status
    exit 0
fi

if [ "$REGION" = "status" ]; then
    echo "Partition Status"
    
    for region in na eu ap; do
        case $region in
            na) container="flask-backend-na"; name="North America" ;;
            eu) container="flask-backend-eu"; name="Europe" ;;
            ap) container="flask-backend-ap"; name="Asia-Pacific" ;;
        esac
        
        is_partitioned=$(docker exec $container sh -c "test -f /tmp/PARTITIONED && echo 'yes' || echo 'no'" 2>/dev/null)
        blocked=$(docker exec $container cat /etc/hosts 2>/dev/null | grep "0.0.0.0 flask-backend" | wc -l | tr -d ' ')
        
        if [ "$is_partitioned" = "yes" ]; then
            echo "$name ($region): PARTITIONED (blocking $blocked regions)"
        elif [ "$blocked" -gt 0 ]; then
            echo "$name ($region): Connected (has $blocked incoming blocks from other partitions)"
        else
            echo "$name ($region): Connected"
        fi
    done
    
    exit 0
fi

if [ -z "$REGION" ] || [ -z "$ACTION" ]; then
    echo "Usage: $0 <region> <partition|restore>"
    echo "       $0 status"
    echo "       $0 reset"
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

    docker exec $CONTAINER sh -c "touch /tmp/PARTITIONED"

    docker exec $CONTAINER sh -c "grep -q '0.0.0.0 $TARGET1' /etc/hosts || echo '0.0.0.0 $TARGET1' >> /etc/hosts"
    docker exec $CONTAINER sh -c "grep -q '0.0.0.0 $TARGET2' /etc/hosts || echo '0.0.0.0 $TARGET2' >> /etc/hosts"

    docker exec $TARGET1 sh -c "grep -q '0.0.0.0 $CONTAINER' /etc/hosts || echo '0.0.0.0 $CONTAINER' >> /etc/hosts"
    docker exec $TARGET2 sh -c "grep -q '0.0.0.0 $CONTAINER' /etc/hosts || echo '0.0.0.0 $CONTAINER' >> /etc/hosts"

    echo "Partition activated for $REGION"

elif [ "$ACTION" = "restore" ]; then
    echo "Restoring $REGION connectivity..."

    docker exec $CONTAINER sh -c "rm -f /tmp/PARTITIONED" 2>/dev/null || true
    
    TARGET1_IS_PARTITIONED=$(docker exec $TARGET1 sh -c "test -f /tmp/PARTITIONED && echo 'yes' || echo 'no'" 2>/dev/null)
    TARGET2_IS_PARTITIONED=$(docker exec $TARGET2 sh -c "test -f /tmp/PARTITIONED && echo 'yes' || echo 'no'" 2>/dev/null)
    
    if [ "$TARGET1_IS_PARTITIONED" = "no" ]; then
        docker exec $CONTAINER sh -c "grep -v '0.0.0.0 $TARGET1' /etc/hosts > /tmp/hosts.tmp && cat /tmp/hosts.tmp > /etc/hosts" 2>/dev/null || true
    fi
    if [ "$TARGET2_IS_PARTITIONED" = "no" ]; then
        docker exec $CONTAINER sh -c "grep -v '0.0.0.0 $TARGET2' /etc/hosts > /tmp/hosts.tmp && cat /tmp/hosts.tmp > /etc/hosts" 2>/dev/null || true
    fi

    if [ "$TARGET1_IS_PARTITIONED" = "no" ]; then
        docker exec $TARGET1 sh -c "grep -v '0.0.0.0 $CONTAINER' /etc/hosts > /tmp/hosts.tmp && cat /tmp/hosts.tmp > /etc/hosts" 2>/dev/null || true
        echo "  $REGION - $TARGET1: bidirectional communication restored"
    else
        echo "  $REGION - $TARGET1: $TARGET1 is partitioned"
    fi
    
    if [ "$TARGET2_IS_PARTITIONED" = "no" ]; then
        docker exec $TARGET2 sh -c "grep -v '0.0.0.0 $CONTAINER' /etc/hosts > /tmp/hosts.tmp && cat /tmp/hosts.tmp > /etc/hosts" 2>/dev/null || true
        echo "  $REGION - $TARGET2: bidirectional communication restored"
    else
        echo "  $REGION - $TARGET2: $TARGET2 is partitioned"
    fi

    echo "$REGION restored"

else
    echo "Invalid action: $ACTION (must be partition or restore)"
    exit 1
fi
