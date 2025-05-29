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
DTM_PATH=""     # Path to DTM file, if available
OUTPUT_DIR=""   # Base directory where output folder and maps will be saved
PROJECT_ID=""   # Project ID for copying DTM overview file from GitHub repo (optional)

# Loop through each project
for MISSION_ID in "${MISSIONS_ID[@]}"; do
    python /app/lefolab-utils/Labelbox/generate_maps.py --mission_id $MISSION_ID --dtm_path  $DTM_PATH --output_dir $OUTPUT_DIR --project_id $PROJECT_ID
done
