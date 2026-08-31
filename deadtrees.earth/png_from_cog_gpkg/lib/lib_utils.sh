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

