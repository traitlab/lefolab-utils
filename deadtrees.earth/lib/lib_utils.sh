#!/bin/bash

# -----------------------------------------------------------------------------
# Function to log messages
log() {
    local service_name="$1"
    local level="$2"
    local message="$3"
    
    # Loop through each line in the message
    while IFS= read -r line; do
        # Skip blank or empty lines
        if [[ -n "$line" ]]; then
            echo "$(date '+%Y-%m-%d %H:%M:%S,%3N')|${service_name}|$$|${0##*/}:${LINENO}|${level}|${line}"
        fi
    done <<< "$message"
}

# -----------------------------------------------------------------------------
# Function to get Tiff overview dimensions, with a max dimension
get_new_dimensions() {
    local file=$1
    local max_dim=$2
    local width height new_width new_height

    # Check if the TIFF file exists
    if [[ ! -f "$file" ]]; then
        return 1
    fi

    # Get the raster size from gdalinfo in JSON format and extract width and height using jq
    size=$(gdalinfo -json ${file} | jq '.size')
    width=$(echo ${size} | jq '.[0]')
    height=$(echo ${size} | jq '.[1]')

    # Ensure the variables are integers
    width=$((${width}))
    height=$((${height}))

    # Calculate new dimensions while maintaining aspect ratio
    if (( ${width} > ${height} )); then
        new_width=${max_dim}
        new_height=$(( ${height} * ${max_dim} / ${width} ))
    else
        new_height=${max_dim}
        new_width=$(( ${width} * ${max_dim} / ${height} ))
    fi

    # Output the new width and height
    echo "${new_width} ${new_height}"
    return 0
}