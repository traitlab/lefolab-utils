# Clip a Cloud Optimized GeoTIFF (COG) using a GeoJSON polygon
# This script reads ONLY the necessary portion of the remote COG, not the whole file!
#
# Requirements:
# - python3 -m pip install rasterio python-dotenv shapely
#
# Create a .env file named: clip_cog_by_geojson.py.env
# RASTER_USER=your_username
# RASTER_PASSWORD=your_password

import os
import json
from pathlib import Path
import rasterio
from rasterio.mask import mask
from dotenv import load_dotenv
from shapely.geometry import shape

# Load credentials from .env file
env_path = Path(__file__).parent / f"{Path(__file__).name}.env"
load_dotenv(dotenv_path=env_path)

username = os.getenv('RASTER_USER')
password = os.getenv('RASTER_PASSWORD')

if not username or not password:
    raise ValueError("RASTER_USER and RASTER_PASSWORD must be set in .env file")

print(f"Loaded credentials for user: {username}")

# COG URL with embedded credentials
ortho_url = f'http://{username}:{password}@206.12.100.29/share/1/20240716_bciwhole_rx1rii/20240716_bciwhole_rx1rii_rgb.cog.tif'

# GeoJSON polygon (50 Ha plot in UTM Zone 17N - EPSG:32617)
# These coordinates are in meters and match the COG's coordinate system
# Area: 700m x 700m = 49 hectares
geojson_polygon = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "id": 1,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [626500, 1012000],
                [627200, 1012000],
                [627200, 1012700],
                [626500, 1012700],
                [626500, 1012000]
            ]]
        },
        "properties": {
            "OBJECTID": 1,
            "Id": 0,
            "AREA": 49.0,
            "DESCRIP_EN": "50 Ha Plot (UTM)",
            "width_m": 700,
            "height_m": 700
        }
    }]
}

# Output file path
output_file = Path(__file__).parent / "clipped_50ha_plot.tif"

try:
    print(f"\nOpening remote COG: {ortho_url.replace(f'{username}:{password}@', '***:***@')}")
    
    with rasterio.open(ortho_url) as src:
        print(f"\nSource COG info:")
        print(f"  CRS: {src.crs}")
        print(f"  Full bounds: {src.bounds}")
        print(f"  Full dimensions: {src.width} x {src.height}")
        print(f"  Resolution: {src.res}")
        
        # Extract the geometry from the GeoJSON
        geom = [feature["geometry"] for feature in geojson_polygon["features"]]
        
        print(f"\nClipping to polygon...")
        print(f"  Polygon bounds: {shape(geom[0]).bounds}")
        
        # Use rasterio.mask to clip - this only reads the necessary portion!
        clipped_data, clipped_transform = mask(
            src, 
            geom, 
            crop=True,
            all_touched=True
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
            "COPY_SRC_OVERVIEWS": "YES"
        })
        
        print(f"\nClipped raster info:")
        print(f"  Dimensions: {clipped_data.shape[2]} x {clipped_data.shape[1]}")
        print(f"  Bands: {clipped_data.shape[0]}")
        print(f"  Data downloaded: ~{clipped_data.nbytes / (1024**2):.2f} MB")
        
        # Write the clipped data to a local file as a COG with pyramids
        print(f"\nWriting clipped raster to: {output_file}")
        with rasterio.open(output_file, "w", **clipped_meta) as dest:
            dest.write(clipped_data)
            
            # Build overviews (pyramids) for COG
            print(f"Building overviews (pyramids) for COG...")
            overview_levels = [2, 4, 8, 16]
            dest.build_overviews(overview_levels, rasterio.enums.Resampling.average)
        
        print(f"\n✅ Successfully clipped and saved as COG with pyramids!")
        print(f"\nKey advantage: Only downloaded the clipped portion, not the entire {src.width}x{src.height} raster!")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    raise

