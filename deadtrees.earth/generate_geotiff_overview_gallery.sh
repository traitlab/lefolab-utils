#!/bin/bash
echo "# -----------------------------------------------------------------------"
echo "script $0 $@"

set -o pipefail
set -o errexit
set -o nounset

date

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
source "${SCRIPT_DIR}/lib/lib_utils2.sh"

SERVICE_NAME="generate_geotiff_overview_gallery"

# Default paths - adjust these as needed
GEOTIFF_DIR="/mnt/ceph/def-elalib-ivado/ivado/dataset/deadtrees.earth/3034orthos"
PNG_OUTPUT_DIR="$GEOTIFF_DIR"
HTML_OUTPUT_FILE="$PNG_OUTPUT_DIR/geotiff_overview_gallery.html"
BASE_URL="http://206.12.100.29/share/deadtreesearth/3034orthos"

# Create output directory if it doesn't exist
mkdir -p "$PNG_OUTPUT_DIR"

log ${SERVICE_NAME} "INFO" "Generating HTML gallery for GeoTIFF overviews"
log ${SERVICE_NAME} "INFO" "GeoTIFF directory: $GEOTIFF_DIR"
log ${SERVICE_NAME} "INFO" "PNG directory: $PNG_OUTPUT_DIR"
log ${SERVICE_NAME} "INFO" "HTML output: $HTML_OUTPUT_FILE"

# Find all PNG overview files
png_files=($(find "$PNG_OUTPUT_DIR" -name "*_overview.png" -type f | sort))

if [[ ${#png_files[@]} -eq 0 ]]; then
    log ${SERVICE_NAME} "WARN" "No PNG overview files found in: $PNG_OUTPUT_DIR"
    exit 0
fi

log ${SERVICE_NAME} "INFO" "Found ${#png_files[@]} PNG overview files"

# Generate HTML content
cat > "$HTML_OUTPUT_FILE" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GeoTIFF Overview Gallery</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .thumbnail-card {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .thumbnail-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        }
        .thumbnail {
            width: 100%;
            height: 200px;
            object-fit: cover;
            cursor: pointer;
            transition: opacity 0.2s ease;
        }
        .thumbnail:hover {
            opacity: 0.9;
        }
        .info {
            padding: 15px;
        }
        .filename {
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
            word-break: break-all;
            font-size: 14px;
        }
        .qgis-link {
            background: #4CAF50;
            color: white;
            padding: 8px 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            width: 100%;
            margin-bottom: 8px;
            transition: background-color 0.2s ease;
            text-decoration: none;
            display: block;
            text-align: center;
        }
        .qgis-link:hover {
            background: #45a049;
            color: white;
            text-decoration: none;
        }
        .copy-btn {
            background: #2196F3;
            color: white;
            padding: 6px 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
            width: 100%;
            transition: background-color 0.2s ease;
            text-decoration: none;
            display: block;
            text-align: center;
        }
        .copy-btn:hover {
            background: #1976D2;
            color: white;
            text-decoration: none;
        }
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.9);
        }
        .modal-content {
            margin: auto;
            display: block;
            max-width: 90%;
            max-height: 90%;
            margin-top: 5%;
        }
        .close {
            position: absolute;
            top: 15px;
            right: 35px;
            color: #f1f1f1;
            font-size: 40px;
            font-weight: bold;
            cursor: pointer;
        }
        .close:hover {
            color: #bbb;
        }
        .stats {
            text-align: center;
            margin-bottom: 20px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .search-box {
            width: 100%;
            max-width: 400px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🗺️ GeoTIFF Overview Gallery</h1>
        <p>Click on thumbnails to view full size. Use QGIS links to load original GeoTIFFs.</p>
        <input type="text" id="searchBox" class="search-box" placeholder="Search by filename...">
    </div>
    
    <div class="stats">
        <p><strong>Total files:</strong> <span id="totalCount">0</span></p>
    </div>
    
    <div class="gallery" id="gallery">
EOF

# Add each PNG file to the HTML
for png_file in "${png_files[@]}"; do
    # Get the base name without _overview.png suffix
    base_name=$(basename "$png_file" _overview.png)
    # Get the PNG filename
    png_filename=$(basename "$png_file")
    
    # URL encode the filenames for web access
    geotiff_encoded=$(urlencode "${base_name}.tif")
    png_encoded=$(urlencode "$png_filename")
    
    # Construct the web URLs with proper encoding
    geotiff_url="$BASE_URL/$geotiff_encoded"
    png_url="$BASE_URL/$png_encoded"
    # Get relative path for the PNG (just the filename since HTML is in same directory)
    png_relative_path="$png_filename"
    
    log ${SERVICE_NAME} "INFO" "Adding to gallery: $base_name"
    log ${SERVICE_NAME} "INFO" "PNG URL: $png_url"
    log ${SERVICE_NAME} "INFO" "GeoTIFF URL: $geotiff_url"
    
    cat >> "$HTML_OUTPUT_FILE" << EOF
        <div class="thumbnail-card" data-filename="$base_name">
            <img src="$png_relative_path" alt="$base_name" class="thumbnail" onclick="openModal('$png_relative_path')">
            <div class="info">
                <div class="filename">$base_name.tif</div>
                <a href="$geotiff_url" class="qgis-link" target="_blank">GeoTIFF URL</a>
                <a href="$png_url" class="copy-btn" target="_blank">PNG URL</a>
            </div>
        </div>
EOF
done

# Add the rest of the HTML
cat >> "$HTML_OUTPUT_FILE" << 'EOF'
    </div>

    <!-- Modal for full-size images -->
    <div id="imageModal" class="modal">
        <span class="close" onclick="closeModal()">&times;</span>
        <img class="modal-content" id="modalImage">
    </div>

    <script>
        // Update total count
        document.getElementById('totalCount').textContent = document.querySelectorAll('.thumbnail-card').length;

        // Search functionality
        document.getElementById('searchBox').addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const cards = document.querySelectorAll('.thumbnail-card');
            
            cards.forEach(card => {
                const filename = card.getAttribute('data-filename').toLowerCase();
                if (filename.includes(searchTerm)) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        });

        // Modal functionality
        function openModal(imageSrc) {
            const modal = document.getElementById('imageModal');
            const modalImg = document.getElementById('modalImage');
            modal.style.display = 'block';
            modalImg.src = imageSrc;
        }

        function closeModal() {
            document.getElementById('imageModal').style.display = 'none';
        }

        // Close modal when clicking outside the image
        window.onclick = function(event) {
            const modal = document.getElementById('imageModal');
            if (event.target == modal) {
                closeModal();
            }
        }


        // Keyboard navigation
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                closeModal();
            }
        });
    </script>
</body>
</html>
EOF

log ${SERVICE_NAME} "INFO" "HTML gallery generated successfully: $HTML_OUTPUT_FILE"
log ${SERVICE_NAME} "INFO" "Gallery contains ${#png_files[@]} thumbnails"

date
echo "# -----------------------------------------------------------------------"
exit 0
