#!/bin/bash

# Activate the conda environment
source /opt/miniconda3/bin/activate
conda activate labelbox

# List of missions_id
MISSIONS_ID=(
"" # Add mission_id
"" # Add mission_id
# Add more mission_id here
)
PROJECT="" # project name for Labelbox

# Loop through each mission
for MISSION_ID in "${MISSIONS_ID[@]}"; do

    echo "Processing mission: $MISSION_ID with project: $PROJECT"
    python /app/lefolab-utils/Labelbox/import_datarows.py --mission_id "$MISSION_ID" --project "$PROJECT"
done
