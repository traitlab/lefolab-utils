#!/usr/bin/env python3
"""
Clip a Cloud Optimized GeoTIFF (COG) using a GeoJSON file.
This script reads ONLY the necessary portion of the remote COG, not the whole file!

Usage:
    python3 clip_cog_by_geojson_file.py <geojson_file> <output_tif>

Example:
    python3 clip_cog_by_geojson_file.py my_polygon.geojson clipped_area.tif

Requirements:
    python3 -m pip install rasterio python-dotenv shapely

Setup:
    Create a .env file named: clip_cog_by_geojson_file.py.env
    RASTER_USER=your_username
    RASTER_PASSWORD=your_password
"""

import os
import sys
import json
from pathlib import Path
import rasterio
from rasterio.mask import mask
from dotenv import load_dotenv

# Load credentials from .env file
env_path = Path(__file__).parent / f"{Path(__file__).name}.env"
load_dotenv(dotenv_path=env_path)

username = os.getenv('RASTER_USER')
password = os.getenv('RASTER_PASSWORD')

if not username or not password:
    raise ValueError("RASTER_USER and RASTER_PASSWORD must be set in .env file")

# Parse command line arguments
if len(sys.argv) != 3:
    print(__doc__)
    sys.exit(1)

geojson_file = Path(sys.argv[1])
output_file = Path(sys.argv[2])

if not geojson_file.exists():
    print(f"Error: GeoJSON file not found: {geojson_file}")
    sys.exit(1)

print(f"Loaded credentials for user: {username}")

# COG URL with embedded credentials
ortho_url = f'http://{username}:{password}@206.12.100.29/share/1/20240716_bciwhole_rx1rii/20240716_bciwhole_rx1rii_rgb.cog.tif'

try:
    # Load GeoJSON file
    print(f"\nLoading GeoJSON from: {geojson_file}")
    with open(geojson_file, 'r') as f:
        geojson_data = json.load(f)
    
    # Extract geometries from GeoJSON
    if geojson_data["type"] == "FeatureCollection":
        geometries = [feature["geometry"] for feature in geojson_data["features"]]
    elif geojson_data["type"] == "Feature":
        geometries = [geojson_data["geometry"]]
    else:
        geometries = [geojson_data]  # Assume it's a geometry object
    
    print(f"  Found {len(geometries)} geometry(ies)")
    
    print(f"\nOpening remote COG: {ortho_url.replace(f'{username}:{password}@', '***:***@')}")
    
    with rasterio.open(ortho_url) as src:
        print(f"\nSource COG info:")
        print(f"  CRS: {src.crs}")
        print(f"  Full bounds: {src.bounds}")
        print(f"  Full dimensions: {src.width} x {src.height}")
        print(f"  Resolution: {src.res}")
        print(f"  Bands: {src.count}")
        
        print(f"\nClipping to polygon(s)...")
        
        # Use rasterio.mask to clip - this only reads the necessary portion!
        clipped_data, clipped_transform = mask(
            src, 
            geometries, 
            crop=True,
            all_touched=True,
            nodata=0
        )
        
        # Get metadata for the clipped raster - configure as COG
        clipped_meta = src.meta.copy()
        clipped_meta.update({
            "driver": "GTiff",
            "height": clipped_data.shape[1],
            "width": clipped_data.shape[2],
            "transform": clipped_transform,
            "compress": "deflate",
            "tiled": True,
            "blockxsize": 512,
            "blockysize": 512,
            "nodata": 0,
            "COPY_SRC_OVERVIEWS": "YES"
        })
        
        # Calculate data size
        full_size_mb = (src.width * src.height * src.count * 1) / (1024**2)  # Assuming 1 byte per pixel
        clipped_size_mb = clipped_data.nbytes / (1024**2)
        
        print(f"\nClipped raster info:")
        print(f"  Dimensions: {clipped_data.shape[2]} x {clipped_data.shape[1]}")
        print(f"  Bands: {clipped_data.shape[0]}")
        print(f"  Data downloaded: ~{clipped_size_mb:.2f} MB")
        print(f"  Full raster would be: ~{full_size_mb:.2f} MB")
        print(f"  Efficiency: Downloaded only {(clipped_size_mb/full_size_mb)*100:.2f}% of full raster!")
        
        # Write the clipped data to a local file as a COG with pyramids
        print(f"\nWriting clipped raster as COG to: {output_file}")
        with rasterio.open(output_file, "w", **clipped_meta) as dest:
            dest.write(clipped_data)
            
            # Build overviews (pyramids) for COG
            print(f"Building overviews (pyramids) for COG...")
            overview_levels = [2, 4, 8, 16]
            dest.build_overviews(overview_levels, rasterio.enums.Resampling.average)
        
        print(f"\n✅ Successfully clipped and saved as COG with pyramids!")
        print(f"\n💡 This is the power of COGs - you only downloaded what you needed!")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

