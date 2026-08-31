#!/bin/bash
echo "# -----------------------------------------------------------------------"
echo "script $0 $@"

set -o pipefail
set -o errexit
set -o nounset

date

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
source "${SCRIPT_DIR}/lib/lib_utils.sh"

SERVICE_NAME="convert_geotiff_to_overview"

# Default paths - adjust these as needed
MAX_DIMENSION=1024

# Default output format
OUTPUT_FORMAT="PNG"

# Function to show usage
show_usage() {
    echo "Usage: $0 -i INPUT_DIR -o OUTPUT_DIR [OPTIONS] [geotiff_filename]"
    echo "   or: $0 -w WORKDIR [OPTIONS] [geotiff_filename]  # when input and output are the same"
    echo ""
    echo "Required (choose one):"
    echo "  -i, --input-dir DIR    Input directory containing GeoTIFF files"
    echo "  -o, --output-dir DIR   Output directory"
    echo "  -w, --workdir DIR      Same directory for both input and output (shortcut)"
    echo ""
    echo "Options:"
    echo "  -f, --format FORMAT    Output format: 'tiff' or 'png' (default: png)"
    echo "  -d, --max-dimension N  Maximum dimension for resizing (default: 1024)"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -i /path/to/input -o /path/to/output                # Convert all GeoTIFFs to PNG overviews"
    echo "  $0 -i /path/to/input -o /path/to/output -f tiff        # Convert all GeoTIFFs to TIFF overviews with CRS, pyramids, and COG"
    echo "  $0 -i /path/to/input -o /path/to/output -f png file.tif # Convert specific file to PNG"
    echo "  $0 -i /path/to/input -o /path/to/output -f tiff -d 2048 file.tif # Convert specific file to TIFF with CRS, pyramids, COG, max 2048px"
    echo "  $0 -w /path/to/data -f tiff                            # Process files in place with pyramids and COG"
    echo "  $0 -w /path/to/data -f tiff -d 2048 file.tif          # Process specific file with pyramids and COG"
    echo ""
    echo "Note: TIFF format always preserves the original coordinate reference system."
    echo "      PNG format always strips geospatial information."
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--format)
            OUTPUT_FORMAT="$2"
            shift 2
            ;;
        -d|--max-dimension)
            MAX_DIMENSION="$2"
            shift 2
            ;;
        -i|--input-dir)
            GEOTIFF_DIR="$2"
            shift 2
            ;;
        -o|--output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -w|--workdir)
            GEOTIFF_DIR="$2"
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        -*)
            echo "Error: Unknown option $1" >&2
            show_usage
            exit 1
            ;;
        *)
            # This is the filename argument
            GEOTIFF_FILE="$1"
            shift
            ;;
    esac
done

# Check if required directories are provided
if [[ -z "${GEOTIFF_DIR:-}" ]]; then
    echo "Error: Input directory is required. Use -i/--input-dir or -w/--workdir option." >&2
    show_usage
    exit 1
fi

if [[ -z "${OUTPUT_DIR:-}" ]]; then
    echo "Error: Output directory is required. Use -o/--output-dir or -w/--workdir option." >&2
    show_usage
    exit 1
fi

# Validate output format
if [[ "$OUTPUT_FORMAT" != "tiff" && "$OUTPUT_FORMAT" != "png" ]]; then
    echo "Error: Invalid output format '$OUTPUT_FORMAT'. Must be 'tiff' or 'png'." >&2
    exit 1
fi

# Validate max dimension
if ! [[ "$MAX_DIMENSION" =~ ^[0-9]+$ ]] || [[ "$MAX_DIMENSION" -lt 1 ]]; then
    echo "Error: Max dimension must be a positive integer." >&2
    exit 1
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Function to clean up auxiliary files
cleanup_auxiliary_files() {
    log ${SERVICE_NAME} "INFO" "Cleaning up auxiliary files (.aux.xml and .msk)"
    find "$OUTPUT_DIR" -name "*.aux.xml" -type f -delete 2>/dev/null || true
    find "$OUTPUT_DIR" -name "*.msk" -type f -delete 2>/dev/null || true
    log ${SERVICE_NAME} "INFO" "Cleanup completed"
}

# Function to convert a single GeoTIFF to overview
convert_geotiff_to_overview() {
    local geotiff_file="$1"
    local base_name=$(basename "$geotiff_file" .tif)
    local file_extension=""
    local gdal_format=""
    local gdal_options=""
    
    # Set output format and extension
    if [[ "$OUTPUT_FORMAT" == "tiff" ]]; then
        file_extension="tif"
        gdal_format="COG"
        
        # Build GDAL options for COG with automatic overviews
        gdal_options="-co COMPRESS=DEFLATE -co BIGTIFF=IF_SAFER -co OVERVIEWS=AUTO -co BLOCKSIZE=128"
        log ${SERVICE_NAME} "INFO" "Using COG format with CRS preservation and automatic pyramids"
    else
        file_extension="png"
        gdal_format="PNG"
        gdal_options="-co WORLDFILE=NO"
        log ${SERVICE_NAME} "INFO" "Using PNG format (no geospatial data)"
    fi
    
    # Set output filename with .cog for COG format
    if [[ "$OUTPUT_FORMAT" == "tiff" ]]; then
        local output_file="${OUTPUT_DIR}/${base_name}_overview.cog.${file_extension}"
    else
        local output_file="${OUTPUT_DIR}/${base_name}_overview.${file_extension}"
    fi
    
    log ${SERVICE_NAME} "INFO" "Converting: $geotiff_file"
    log ${SERVICE_NAME} "INFO" "Output: $output_file"
    
    # Check if input file exists
    if [[ ! -f "$geotiff_file" ]]; then
        log ${SERVICE_NAME} "ERROR" "Input file does not exist: $geotiff_file"
        return 1
    fi
    
    # Check if overview already exists
    if [[ -f "$output_file" ]]; then
        log ${SERVICE_NAME} "INFO" "Overview already exists, skipping: $output_file"
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
    
    # Convert using GDAL with COG driver for automatic overviews
    gdalcmd=$(gdal_translate -of "$gdal_format" \
        $gdal_options \
        -outsize "$new_width" "$new_height" \
        "$geotiff_file" \
        "$output_file" 2>&1)
    
    if [[ $? -eq 0 ]]; then
        log ${SERVICE_NAME} "INFO" "Successfully converted: $base_name"
        return 0
    else
        log ${SERVICE_NAME} "ERROR" "Failed to convert: $geotiff_file"
        log ${SERVICE_NAME} "ERROR" "GDAL output: $gdalcmd"
        return 1
    fi
}

# Main execution
if [[ -n "${GEOTIFF_FILE:-}" ]]; then
    # Single file mode - process the specified GeoTIFF
    # Check if it's a full path or just filename
    if [[ "$GEOTIFF_FILE" == /* ]]; then
        # Full path provided
        full_path="$GEOTIFF_FILE"
    else
        # Just filename provided, look in the default directory
        full_path="${GEOTIFF_DIR}/${GEOTIFF_FILE}"
    fi
    
    log ${SERVICE_NAME} "INFO" "Processing single file: $full_path"
    convert_geotiff_to_overview "$full_path"

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
        if convert_geotiff_to_overview "$geotiff_file"; then
            success_count=$((success_count + 1))
        else
            error_count=$((error_count + 1))
        fi

        # Cleanup auxiliary files
        cleanup_auxiliary_files   
    done
    
    log ${SERVICE_NAME} "INFO" "Processing complete - Success: $success_count, Errors: $error_count"

else
    # Invalid arguments
    echo "Error: Invalid arguments" >&2
    show_usage
    exit 1
fi

# Cleanup auxiliary files
cleanup_auxiliary_files

date
echo "# -----------------------------------------------------------------------"
exit 0
