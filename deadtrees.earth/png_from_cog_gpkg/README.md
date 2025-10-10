# Create PNG from Orthomosaic with AOI Clipping

Simple script to create a PNG image from an orthomosaic (GeoTIFF) clipped to an Area of Interest (AOI) polygon. The data is automatically reprojected to the appropriate UTM zone.

## Files Required

The script expects two files with matching codes:
- `{CODE}_odm_orthophoto.tif` - Orthomosaic GeoTIFF
- `dataset_{CODE}_aoi_only.gpkg` - AOI GeoPackage

Example for code `5980`:
- `5980_odm_orthophoto.tif`
- `dataset_5980_aoi_only.gpkg`

## Installation

```bash
pip install -r requirements_aoi_png.txt
```

## Usage

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

- Python 3.7+
- rasterio
- geopandas
- numpy
- Pillow
- pyproj
- shapely

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

