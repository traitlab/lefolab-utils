#!/bin/bash

# List of containers
CONTAINERS=(
"" # Add mission_id
"" # Add mission_id
# Add more mission_id here
)

# Loop through each container
for CONTAINER in "${CONTAINERS[@]}"; do
    echo "Processing container: $CONTAINER"
    rclone --config /etc/rclone.conf copy /mnt/nfs/lefodata/data/drone_missions/2025/$CONTAINER/ AllianceCanBuckets:$CONTAINER -c -P
done
