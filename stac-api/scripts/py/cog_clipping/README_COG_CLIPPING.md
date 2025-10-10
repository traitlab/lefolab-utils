# Clipping Cloud Optimized GeoTIFFs (COGs) Without Downloading the Whole File

## The Power of COGs

**Yes, you can clip a smaller area from a COG without loading the whole file!** This is one of the main advantages of Cloud Optimized GeoTIFFs (COGs) over regular TIFFs.

### Why COGs are Better than QGIS for Remote Clipping

| Method | Data Downloaded | Speed | Requires |
|--------|----------------|-------|----------|
| **COG (Python)** | Only the clipped area | ⚡ Fast | Basic Python |
| **QGIS** | Entire file first | 🐌 Slow | Download full file |

With a COG, you can extract just the portion you need without downloading gigabytes of data!

## Scripts Provided

All scripts are located in the `cog_clipping/` directory.

### 1. `clip_cog_by_geojson.py`
- Hardcoded example with the 50 Ha plot
- Good for learning and testing
- Run: `python3 cog_clipping/clip_cog_by_geojson.py`

### 2. `clip_cog_by_geojson_file.py` ⭐ Recommended
- Accepts any GeoJSON file as input
- More flexible for different areas
- Run: `python3 cog_clipping/clip_cog_by_geojson_file.py <geojson_file> <output.tif>`

## Setup

### 1. Install Dependencies
```bash
python3 -m pip install rasterio python-dotenv shapely
```

### 2. Create Credentials File
Create a file named `clip_cog_by_geojson_file.py.env` with:
```
RASTER_USER=your_username
RASTER_PASSWORD=your_password
```

## Usage Examples

### Example 1: Using the Provided Sample GeoJSON
```bash
cd stac-api/scripts/py
python3 cog_clipping/clip_cog_by_geojson_file.py cog_clipping/example_50ha_plot.geojson my_clipped_area.tif
```

### Example 2: Using Your Own GeoJSON
1. Create your polygon in QGIS, Google Earth, or geojson.io
2. Export as GeoJSON
3. Run:
```bash
python3 cog_clipping/clip_cog_by_geojson_file.py my_custom_area.geojson output.tif
```

### Example 3: Simple Hardcoded Version
```bash
python3 cog_clipping/clip_cog_by_geojson.py
```
This will clip the 50 Ha plot and save to `clipped_50ha_plot.tif`

## How It Works

The magic happens with `rasterio.mask.mask()`:

```python
clipped_data, clipped_transform = mask(
    src,           # Remote COG connection
    geometries,    # Your polygon(s)
    crop=True,     # Crop to minimum bounding box
    all_touched=True  # Include partially covered pixels
)
```

This function:
1. Calculates which tiles/blocks of the COG intersect your polygon
2. Downloads ONLY those tiles (not the whole file!)
3. Clips to your exact polygon shape
4. Returns the clipped data ready to save

## Performance Comparison

Example with a 10GB COG file:

- **Full download (QGIS)**: 10 GB, ~30 minutes
- **COG clipping (Python)**: 50 MB, ~30 seconds

**You save time, bandwidth, and storage!**

## Creating GeoJSON Polygons

### Option 1: QGIS
1. Create a new polygon layer
2. Draw your polygon
3. Right-click layer → Export → Save Features As
4. Format: GeoJSON

### Option 2: geojson.io
1. Go to [geojson.io](http://geojson.io)
2. Draw your polygon on the map
3. Copy the GeoJSON from the right panel
4. Save to a `.geojson` file

### Option 3: From Coordinates (Python)
```python
polygon = {
    "type": "Polygon",
    "coordinates": [[
        [lon1, lat1],
        [lon2, lat2],
        [lon3, lat3],
        [lon1, lat1]  # Close the polygon
    ]]
}
```

## Troubleshooting

### Error: "RASTER_USER and RASTER_PASSWORD must be set"
- Make sure you created the `.env` file with correct credentials
- File must be named `clip_cog_by_geojson_file.py.env`

### Error: "Polygon outside raster bounds"
- Check your polygon coordinates match the CRS of the COG
- Verify coordinates are in the correct order (longitude, latitude)

### Clipped file is empty or all black
- Try `all_touched=False` instead of `True`
- Check that your polygon actually intersects the COG bounds

## Advanced: Changing the COG URL

To clip a different COG, edit the `ortho_url` variable in the script:

```python
ortho_url = f'http://{username}:{password}@your-server.com/path/to/your.cog.tif'
```

## Output Format

The clipped output is a **proper Cloud Optimized GeoTIFF (COG)** with:

✅ **DEFLATE compression** - Good compression ratio  
✅ **Tiled structure** - 512x512 pixel tiles  
✅ **Pyramids/Overviews** - Multiple resolution levels (2x, 4x, 8x, 16x)  
✅ **Optimized for web serving** - Efficient partial reads

This means your output file can also be served remotely and accessed efficiently!

## Summary

Python with rasterio is **better** for clipping remote COGs than QGIS because:

✅ Only downloads what you need  
✅ Faster than downloading full file  
✅ Works with any size COG  
✅ Can be automated/scripted  
✅ Saves disk space  
✅ Outputs proper COGs with pyramids

QGIS is great for visualization, but for programmatic clipping of remote COGs, Python is the winner! 🏆

