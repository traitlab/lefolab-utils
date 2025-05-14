#!/bin/bash

source /opt/miniconda3/bin/activate
conda activate canopyrs

# List of missions_id
MISSIONS_ID=(
"" # Add mission_id
"" # Add mission_id
# Add more mission_id here
)
USER="" # lefoai username
YEAR="" # Year of the missions
EXT="" # Extension of the orthomosaic files (tif or cog.tif)

# Loop through each project
for MISSION_ID in "${MISSIONS_ID[@]}"; do

    echo "Processing project: $MISSION_ID"
    python /app/CanopyRS/main.py -t pipeline -c default -i /mnt/nfs/conrad/labolaliberte_data/metashape/$YEAR/$MISSION_ID/${MISSION_ID}_rgb.${EXT} -o /data/$USER/CanopyRS/$YEAR/$MISSION_ID
done
