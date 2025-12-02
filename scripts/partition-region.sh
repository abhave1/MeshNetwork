#!/bin/bash

# Script to partition a region from others while keeping localhost access
# Usage: ./partition-region.sh <region> <action>
# Example: ./partition-region.sh na partition
#          ./partition-region.sh na restore

set -e

REGION=$1
ACTION=$2

if [ -z "$REGION" ] || [ -z "$ACTION" ]; then
    echo "Usage: $0 <region> <partition|restore>"
    echo "Example: $0 na partition"
    echo "         $0 na restore"
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

    # Block traffic by adding black hole IPs to /etc/hosts
    docker exec $CONTAINER sh -c "
        echo '0.0.0.0 $TARGET1' >> /etc/hosts
        echo '0.0.0.0 $TARGET2' >> /etc/hosts
    "

    # Also block from the other direction - make EU and AP not try to reach NA
    docker exec $TARGET1 sh -c "echo '0.0.0.0 $CONTAINER' >> /etc/hosts"
    docker exec $TARGET2 sh -c "echo '0.0.0.0 $CONTAINER' >> /etc/hosts"

    echo "Partition activated"
    echo "✓ $REGION is now partitioned from other regions"
    echo "  - localhost:$PORT still accessible"
    echo "  - Local database operations continue"
    echo "  - Cannot communicate with other regions"

elif [ "$ACTION" = "restore" ]; then
    echo "Restoring $REGION connectivity..."

    # Restart containers to reset /etc/hosts
    echo "Restarting containers to restore connectivity..."
    docker restart $CONTAINER $TARGET1 $TARGET2 > /dev/null 2>&1

    # Wait for containers to be ready
    sleep 3

    echo "Connectivity restored"
    echo "✓ $REGION connectivity restored"

else
    echo "Invalid action: $ACTION (must be partition or restore)"
    exit 1
fi
