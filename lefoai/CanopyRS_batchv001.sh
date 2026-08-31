#!/bin/bash

source /opt/miniconda3/bin/activate
conda activate canopyrsv001

# List of missions_id
MISSIONS_ID=(
"" # Add mission_id
"" # Add mission_id
# Add more mission_id here
)
USER="" # lefoai username
YEAR="" # Year of the missions, or can be left empty to extract it from 4 first digits of MISSION_ID
EXT="" # Extension of the orthomosaic files (tif or cog.tif)

# Loop through each project
for MISSION_ID in "${MISSIONS_ID[@]}"; do
    echo "Processing project: $MISSION_ID"
    # Extract year from first 4 digits of MISSION_ID, or use $YEAR if not 20XX
    YEAR_EXTRACTED=$(echo "$MISSION_ID" | grep -oE '^20[0-9]{2}')
    if [[ "$YEAR_EXTRACTED" =~ ^20[0-9]{2}$ ]]; then
        YEAR_TO_USE="$YEAR_EXTRACTED"
    else
        YEAR_TO_USE="$YEAR"
    fi
    python /app/CanopyRSv0.0.1/main.py -t pipeline -c default -i /mnt/nfs/conrad/labolaliberte_data/metashape/$YEAR_TO_USE/$MISSION_ID/${MISSION_ID}_rgb.${EXT} -o /data/$USER/CanopyRSv0.0.1/$YEAR_TO_USE/$MISSION_ID
done
