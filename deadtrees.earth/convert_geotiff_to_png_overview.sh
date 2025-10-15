#!/bin/bash
echo "# -----------------------------------------------------------------------"
echo "script $0 $@"

set -o pipefail
set -o errexit
set -o nounset

date

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
source "${SCRIPT_DIR}/lib/lib_utils2.sh"

SERVICE_NAME="convert_geotiff_to_png_overview"

# Default paths - adjust these as needed
GEOTIFF_DIR="/mnt/ceph/def-elalib-ivado/ivado/dataset/deadtrees.earth/3034orthos"
PNG_OUTPUT_DIR="$GEOTIFF_DIR"
MAX_DIMENSION=1024

# Create output directory if it doesn't exist
mkdir -p "$PNG_OUTPUT_DIR"

# Function to clean up auxiliary files
cleanup_auxiliary_files() {
    log ${SERVICE_NAME} "INFO" "Cleaning up auxiliary files (.aux.xml and .msk)"
    find "$PNG_OUTPUT_DIR" -name "*.aux.xml" -type f -delete 2>/dev/null || true
    find "$PNG_OUTPUT_DIR" -name "*.msk" -type f -delete 2>/dev/null || true
    log ${SERVICE_NAME} "INFO" "Cleanup completed"
}

# Function to convert a single GeoTIFF to PNG overview
convert_geotiff_to_png() {
    local geotiff_file="$1"
    local base_name=$(basename "$geotiff_file" .tif)
    local png_output="${PNG_OUTPUT_DIR}/${base_name}_overview.png"
    
    log ${SERVICE_NAME} "INFO" "Converting: $geotiff_file"
    log ${SERVICE_NAME} "INFO" "Output: $png_output"
    
    # Check if input file exists
    if [[ ! -f "$geotiff_file" ]]; then
        log ${SERVICE_NAME} "ERROR" "Input file does not exist: $geotiff_file"
        return 1
    fi
    
    # Check if overview already exists
    if [[ -f "$png_output" ]]; then
        log ${SERVICE_NAME} "INFO" "Overview already exists, skipping: $png_output"
        return 0
    fi
    
    # Get new dimensions maintaining aspect ratio
    local dimensions=$(get_new_dimensions "$geotiff_file" "$MAX_DIMENSION")
    if [[ $? -ne 0 ]]; then
        log ${SERVICE_NAME} "ERROR" "Failed to get dimensions for: $geotiff_file"
        return 1
    fi
    
    local new_width=$(echo $dimensions | cut -d' ' -f1)
    local new_height=$(echo $dimensions | cut -d' ' -f2)
    
    log ${SERVICE_NAME} "INFO" "Resizing to: ${new_width}x${new_height}"
    
    # Convert using GDAL
    gdal_translate \
        -of PNG \
        -outsize "$new_width" "$new_height" \
        -co "WORLDFILE=NO" \
        "$geotiff_file" \
        "$png_output"
    
    if [[ $? -eq 0 ]]; then
        log ${SERVICE_NAME} "INFO" "Successfully converted: $base_name"
        return 0
    else
        log ${SERVICE_NAME} "ERROR" "Failed to convert: $geotiff_file"
        return 1
    fi
}

# Main execution
if [[ $# -eq 1 ]]; then
    # Single file mode - process the specified GeoTIFF
    geotiff_file="$1"
    
    # Check if it's a full path or just filename
    if [[ "$geotiff_file" == /* ]]; then
        # Full path provided
        full_path="$geotiff_file"
    else
        # Just filename provided, look in the default directory
        full_path="${GEOTIFF_DIR}/${geotiff_file}"
    fi
    
    log ${SERVICE_NAME} "INFO" "Processing single file: $full_path"
    convert_geotiff_to_png "$full_path"

    # Cleanup auxiliary files
    cleanup_auxiliary_files
 
    
elif [[ $# -eq 0 ]]; then
    # Batch mode - process all GeoTIFF files in the directory
    log ${SERVICE_NAME} "INFO" "Processing all GeoTIFF files in: $GEOTIFF_DIR"
    
    # Find all .tif files in the directory
    geotiff_files=($(find "$GEOTIFF_DIR" -name "*.tif" -type f))
    
    if [[ ${#geotiff_files[@]} -eq 0 ]]; then
        log ${SERVICE_NAME} "WARN" "No GeoTIFF files found in: $GEOTIFF_DIR"
        exit 0
    fi
    
    log ${SERVICE_NAME} "INFO" "Found ${#geotiff_files[@]} GeoTIFF files to process"
    
    success_count=0
    error_count=0
    
    for geotiff_file in "${geotiff_files[@]}"; do
        if convert_geotiff_to_png "$geotiff_file"; then
            success_count=$((success_count + 1))
        else
            error_count=$((error_count + 1))
        fi

        # Cleanup auxiliary files
        cleanup_auxiliary_files   

    done
    
    log ${SERVICE_NAME} "INFO" "Processing complete - Success: $success_count, Errors: $error_count"

else
    # Invalid number of arguments
    echo "Usage: $0 [geotiff_filename]"
    echo "  With filename: Convert specific GeoTIFF file"
    echo "  Without arguments: Convert all GeoTIFF files in $GEOTIFF_DIR"
    exit 1
fi

# Cleanup auxiliary files
cleanup_auxiliary_files

date
echo "# -----------------------------------------------------------------------"
exit 0
