#!/usr/bin/env python3
"""
Create PNG images from orthomosaics (GeoTIFF) clipped to AOI polygons (GeoPackage)

This script:
1. Loads orthomosaic and AOI files by code number
2. Reprojects both orthomosaic and AOI to UTM projection (auto-detected)
3. Clips orthomosaic to the AOI polygon extent
4. Exports the result as PNG

Requirements:
- rasterio
- geopandas
- numpy
- PIL (Pillow)
- pyproj
"""

import os
import sys
from pathlib import Path
from typing import Optional
import argparse
import logging

try:
    import rasterio
    from rasterio.mask import mask
    from rasterio.warp import calculate_default_transform, reproject, Resampling
    from rasterio.crs import CRS
    import geopandas as gpd
    import numpy as np
    from PIL import Image
    from pyproj import CRS as ProjCRS
except ImportError as e:
    print(f"Error: Missing required library: {e}")
    print("\nPlease install required packages:")
    print("pip install rasterio geopandas pillow numpy pyproj")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_utm_crs_from_geom(geometry, crs) -> CRS:
    """
    Determine the appropriate UTM CRS based on the centroid of the geometry.
    
    Args:
        geometry: Shapely geometry or bounds
        crs: Current CRS of the geometry
        
    Returns:
        Rasterio CRS object for UTM zone
    """
    # If geometry is a GeoDataFrame or GeoSeries, get its centroid
    if hasattr(geometry, 'centroid'):
        centroid = geometry.centroid
        if hasattr(centroid, 'iloc'):
            centroid = centroid.iloc[0]
    else:
        # Assume it's a bounds tuple (minx, miny, maxx, maxy)
        centroid_x = (geometry[0] + geometry[2]) / 2
        centroid_y = (geometry[1] + geometry[3]) / 2
        from shapely.geometry import Point
        centroid = Point(centroid_x, centroid_y)
    
    # Get lon/lat coordinates
    gdf_temp = gpd.GeoDataFrame(geometry=[centroid], crs=crs)
    gdf_wgs84 = gdf_temp.to_crs('EPSG:4326')
    lon = gdf_wgs84.geometry.iloc[0].x
    lat = gdf_wgs84.geometry.iloc[0].y
    
    # Calculate UTM zone
    utm_zone = int((lon + 180) / 6) + 1
    
    # Determine if northern or southern hemisphere
    if lat >= 0:
        epsg_code = 32600 + utm_zone  # Northern hemisphere
        hemisphere = "North"
    else:
        epsg_code = 32700 + utm_zone  # Southern hemisphere
        hemisphere = "South"
    
    logger.info(f"Determined UTM Zone {utm_zone}{hemisphere} (EPSG:{epsg_code}) from centroid at ({lon:.4f}, {lat:.4f})")
    
    return CRS.from_epsg(epsg_code)


def clip_raster_to_aoi(tif_path: Path, gpkg_path: Path, output_path: Path) -> bool:
    """
    Clip orthomosaic to AOI polygon and save as PNG, with automatic reprojection to UTM.
    
    Args:
        tif_path: Path to orthomosaic GeoTIFF
        gpkg_path: Path to AOI GeoPackage
        output_path: Path for output PNG
        
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Processing {tif_path.name}...")
        
        # Read AOI polygons
        logger.debug(f"Reading AOI from {gpkg_path}")
        gdf = gpd.read_file(gpkg_path)
        
        if len(gdf) == 0:
            logger.error(f"No features found in {gpkg_path}")
            return False
        
        logger.debug(f"Found {len(gdf)} AOI polygon(s), CRS: {gdf.crs}")
        
        # Open the raster
        with rasterio.open(tif_path) as src:
            logger.debug(f"Original Raster CRS: {src.crs}, Shape: {src.shape}, Bands: {src.count}")
            
            # Automatically determine target UTM CRS
            target_crs = get_utm_crs_from_geom(gdf.geometry, gdf.crs)
            
            logger.info(f"Reprojecting to {target_crs}")
            
            # Reproject AOI to target CRS
            if gdf.crs != target_crs:
                logger.debug(f"Reprojecting AOI from {gdf.crs} to {target_crs}")
                gdf = gdf.to_crs(target_crs)
            
            # Calculate transform for reprojection
            transform, width, height = calculate_default_transform(
                src.crs, target_crs, src.width, src.height, *src.bounds
            )
            
            # Prepare destination array
            kwargs = src.meta.copy()
            kwargs.update({
                'crs': target_crs,
                'transform': transform,
                'width': width,
                'height': height
            })
            
            # Reproject raster to target CRS
            logger.debug(f"Reprojecting raster from {src.crs} to {target_crs}")
            reprojected_data = np.zeros((src.count, height, width), dtype=src.dtypes[0])
            
            for band_idx in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, band_idx),
                    destination=reprojected_data[band_idx - 1],
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=target_crs,
                    resampling=Resampling.bilinear
                )
            
            logger.debug(f"Reprojected raster shape: {reprojected_data.shape}")
            
            # Create a memory file with reprojected data
            from rasterio.io import MemoryFile
            with MemoryFile() as memfile:
                with memfile.open(**kwargs) as mem_dataset:
                    mem_dataset.write(reprojected_data)
                
                # Now read back and clip with AOI
                with memfile.open() as mem_src:
                    # Get geometries for masking
                    geometries = [geom for geom in gdf.geometry]
                    
                    # Clip the reprojected raster
                    logger.debug("Clipping reprojected raster to AOI...")
                    out_image, out_transform = mask(mem_src, geometries, crop=True, all_touched=True)
                    out_meta = mem_src.meta.copy()
                    
                    # Update metadata
                    out_meta.update({
                        "driver": "GTiff",
                        "height": out_image.shape[1],
                        "width": out_image.shape[2],
                        "transform": out_transform,
                        "crs": target_crs
                    })
                    
                    logger.debug(f"Clipped shape: {out_image.shape}")
                    
                    # Store the source count and nodata for later use
                    src_count = mem_src.count
                    src_nodata = mem_src.nodata
            
            # Convert to RGB if needed and prepare for PNG
            if src_count >= 3:
                # RGB or RGBA image
                rgb_image = out_image[:3, :, :]  # Take first 3 bands (RGB)
                
                # Handle nodata values
                if src_nodata is not None:
                    # Create mask for nodata
                    nodata_mask = np.all(out_image[:3, :, :] == src_nodata, axis=0)
                    
                    # Replace nodata with white (255) or transparent if RGBA
                    for i in range(3):
                        rgb_image[i][nodata_mask] = 255
                
                # Normalize to 0-255 if needed
                if rgb_image.max() > 255:
                    rgb_image = (rgb_image / rgb_image.max() * 255).astype(np.uint8)
                else:
                    rgb_image = rgb_image.astype(np.uint8)
                
                # Convert to PIL Image (need to transpose from (C, H, W) to (H, W, C))
                rgb_image = np.transpose(rgb_image, (1, 2, 0))
                img = Image.fromarray(rgb_image, mode='RGB')
                
                # Save as PNG
                logger.debug(f"Saving PNG to {output_path}")
                img.save(output_path, 'PNG', optimize=True)
                
                logger.info(f"✓ Successfully created {output_path.name}")
                return True
            else:
                logger.error(f"Raster has only {src_count} band(s), need at least 3 for RGB")
                return False
                
    except Exception as e:
        logger.error(f"Error processing {tif_path.name}: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Create PNG from orthomosaic clipped to AOI polygon, reprojected to auto-detected UTM'
    )
    parser.add_argument(
        'code',
        type=str,
        help='Code number to process (e.g., 5980)'
    )
    parser.add_argument(
        '--input-dir',
        type=Path,
        default=Path('/mnt/ceph/def-elalib-ivado/ivado/dataset/deadtrees.earth/3034orthos/'),
        help='Input directory containing orthomosaics and AOI files'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=None,
        help='Output directory for PNG files (default: same as input directory)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose debug logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Set output directory
    output_dir = args.output_dir if args.output_dir else args.input_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Processing code: {args.code}")
    
    # Find files that match the code
    # TIF: starts with {code}_*.tif
    # GPKG: dataset_{code}_aoi_only.gpkg
    
    # Search for TIF file starting with code
    tif_files = list(args.input_dir.glob(f"{args.code}_*.tif"))
    
    if not tif_files:
        logger.error(f"No orthomosaic found starting with: {args.code}_*.tif in {args.input_dir}")
        sys.exit(1)
    
    if len(tif_files) > 1:
        logger.warning(f"Multiple TIF files found for code {args.code}:")
        for f in tif_files:
            logger.warning(f"  - {f.name}")
        logger.info(f"Using first match: {tif_files[0].name}")
    
    tif_path = tif_files[0]
    
    # Find GPKG file
    gpkg_path = args.input_dir / f"dataset_{args.code}_aoi_only.gpkg"
    
    if not gpkg_path.exists():
        logger.error(f"AOI file not found: {gpkg_path}")
        sys.exit(1)
    
    logger.info(f"Found orthomosaic: {tif_path.name}")
    logger.info(f"Found AOI: {gpkg_path.name}")
    
    # Process the file pair
    output_path = output_dir / f"{args.code}_aoi_clipped.png"
    
    if clip_raster_to_aoi(tif_path, gpkg_path, output_path):
        logger.info("=" * 60)
        logger.info("✓ Processing complete!")
        logger.info(f"Output: {output_path}")
        logger.info("=" * 60)
    else:
        logger.error("=" * 60)
        logger.error("✗ Processing failed!")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == '__main__':
    main()

