# Create PNG from Orthomosaic with AOI Clipping

Create a PNG image from an orthomosaic (GeoTIFF) clipped to an Area of Interest (AOI) polygon. The data is automatically reprojected to the appropriate UTM zone.

**Two versions available:**
- **Bash script** (RECOMMENDED): `create_aoi_png.sh` - Fast, uses GDAL command-line tools
- **Python script**: `create_aoi_pngs.py` - More flexible, but slower for reprojection

## Files Required

The scripts expect two files with matching codes:
- `{CODE}_*.tif` - Orthomosaic GeoTIFF (starts with code)
- `dataset_{CODE}_aoi_only.gpkg` - AOI GeoPackage

Example for code `5980`:
- `5980_odm_orthophoto.tif` (or any file starting with `5980_` and ending in `.tif`)
- `dataset_5980_aoi_only.gpkg`

**Note**: If multiple TIF files start with the same code, the script will use the first one found.

## Installation

### Bash Script (Recommended - Faster)

Requires GDAL/OGR tools:
```bash
# Ubuntu/Debian
sudo apt-get install gdal-bin

# macOS
brew install gdal

# Verify installation
gdalinfo --version
```

### Python Script

```bash
pip install -r requirements_aoi_png.txt
```

## Usage

### Bash Script (Fast - Uses GDAL)

```bash
# Make script executable (first time only)
chmod +x create_aoi_png.sh

# Basic usage - process code 5980
./create_aoi_png.sh 5980

# With verbose logging
./create_aoi_png.sh 5980 --verbose

# Specify input and output directories
./create_aoi_png.sh 5980 --input-dir /path/to/data --output-dir /path/to/output

# Keep temporary files for debugging
./create_aoi_png.sh 5980 --keep-temp --verbose

# Full example
./create_aoi_png.sh 5980 \
  --input-dir /mnt/ceph/def-elalib-ivado/ivado/dataset/deadtrees.earth/3034orthos/ \
  --output-dir ./output \
  --verbose
```

### Python Script (Slower)

```bash
# Basic usage - process code 5980
python3 create_aoi_pngs.py 5980

# With verbose logging
python3 create_aoi_pngs.py 5980 --verbose

# Specify input directory
python3 create_aoi_pngs.py 5980 --input-dir /path/to/data

# Specify output directory
python3 create_aoi_pngs.py 5980 --output-dir /path/to/output

# Full example
python3 create_aoi_pngs.py 5980 \
  --input-dir /mnt/ceph/def-elalib-ivado/ivado/dataset/deadtrees.earth/3034orthos/ \
  --output-dir ./output \
  --verbose
```

## What It Does

1. **Loads Data**: Reads the orthomosaic GeoTIFF and AOI GeoPackage
2. **Auto-detects UTM**: Determines the appropriate UTM zone from the data's location
3. **Reprojects**: Transforms both orthomosaic and AOI to UTM projection
4. **Clips**: Masks the orthomosaic to the AOI extent
5. **Exports**: Saves as PNG (RGB image only)

## Output Files

For code `5980`, the script creates:

- `5980_aoi_clipped.png` - RGB PNG image

## Command-Line Options

### Bash Script
```
Arguments:
  code                  Code number to process (e.g., 5980)

Options:
  --input-dir DIR       Input directory (default: /mnt/ceph/def-elalib-ivado/ivado/dataset/deadtrees.earth/3034orthos/)
  --output-dir DIR      Output directory (default: same as input)
  --verbose             Enable verbose debug logging
  --keep-temp           Keep temporary files for debugging
  --help, -h            Show help message
```

### Python Script
```
positional arguments:
  code                  Code number to process (e.g., 5980)

optional arguments:
  --input-dir DIR       Input directory (default: /mnt/ceph/def-elalib-ivado/ivado/dataset/deadtrees.earth/3034orthos/)
  --output-dir DIR      Output directory (default: same as input)
  --verbose             Enable verbose debug logging
  --help, -h            Show help message
```

## UTM Auto-Detection

The script automatically:
- Calculates the centroid of the AOI polygon
- Determines the appropriate UTM zone (1-60)
- Detects northern/southern hemisphere
- Uses the correct EPSG code (326XX for north, 327XX for south)

Example: Data in eastern Canada → UTM Zone 18N (EPSG:32618)

## Requirements

### Bash Script
- GDAL/OGR command-line tools (gdalwarp, gdal_translate, ogr2ogr, ogrinfo, gdalinfo)
- bc (basic calculator, usually pre-installed)

### Python Script
- Python 3.7+
- rasterio
- geopandas
- numpy
- Pillow
- pyproj
- shapely

## Performance Comparison

**Bash script (GDAL)**: ⚡ **Recommended for speed**
- Uses highly optimized C++ GDAL libraries
- Multi-threaded reprojection
- Efficient memory usage
- Typically 3-10x faster than Python for large files

**Python script**: 🐍 Better for integration
- Easier to modify and integrate with other Python code
- More detailed error handling
- Slower reprojection, especially for large orthomosaics

## Troubleshooting

**"Orthomosaic not found"** or **"AOI file not found"**
- Check that files exist in the input directory
- Verify the code number is correct
- Ensure files follow naming convention: `{CODE}_odm_orthophoto.tif` and `dataset_{CODE}_aoi_only.gpkg`

**"No features found"**
- The GeoPackage file is empty or corrupted

**"Raster has only X band(s), need at least 3 for RGB"**
- The orthomosaic must have at least 3 bands (RGB)

**Memory errors**
- Large orthomosaics require significant RAM during reprojection
- Close other applications or use a machine with more memory

