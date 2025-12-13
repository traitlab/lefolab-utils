#!/usr/bin/env python3
"""
project2Dpictures_arbutus.py

Generate footprint polygons for aerial images from Arbutus server based on camera parameters and DSM.

Usage:
    python project2Dpictures_arbutus.py --config-path <rclone_config> --project-qualifier <qualifier> --dsm-dir <dsm_directory> --sensor-width <Sw> --focal-length <FR> --crs <EPSG> --output-dir <output_dir> [--output <output.gpkg>] [--center-crop <size>] [--tile-crop <width> <height>]

The script:
1. Lists zoom images from Arbutus server for a given project qualifier
2. Fetches images via HTTP and extracts GPS coordinates and altitude from EXIF
3. For each mission, selects the DSM file with the closest date to the mission date
4. Samples DSM median within 0.5m buffer around image coordinates
5. Computes flight height H = altitude - DSM_median
6. Calculates GSD = (Sw * H) / (FR * imW)
7. Calculates footprint dimensions: Dw = GSD * imW, Dh = GSD * imH
8. Creates north-oriented rectangular footprints
9. Outputs vector layer (GeoPackage) in projected CRS
"""

import argparse
import logging
import os
import re
import subprocess
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import redirect_stderr
from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path
from typing import List, Tuple, Optional, Dict

try:
    import exifread
    import fiona
    import numpy as np
    import rasterio
    import requests
    from fiona.crs import from_epsg
    from pyproj import Transformer, CRS
    from rasterio.windows import from_bounds
    from requests.adapters import HTTPAdapter
    from shapely.geometry import Polygon, Point, box
    from shapely.affinity import translate
    from urllib3.util.retry import Retry
except ImportError as e:
    print(f"Error: Missing required package. {e}")
    print("Please install requirements: pip install exifread fiona numpy pyproj rasterio requests shapely")
    sys.exit(1)


def setup_logging(output_dir: str, project_qualifier: str):
    """Configure logging to file, stdout (INFO), and stderr (WARNING/ERROR)."""
    log_dir = os.path.join(output_dir)
    os.makedirs(log_dir, exist_ok=True)
    info_log_file = os.path.join(log_dir, f'project2D_{project_qualifier}_info.log')
    error_log_file = os.path.join(log_dir, f'project2D_{project_qualifier}_error.log')

    logger = logging.getLogger('project2D')
    logger.setLevel(logging.INFO)
    logger.handlers = []

    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.addFilter(lambda record: record.levelno == logging.INFO)
    stdout_handler.setFormatter(formatter)

    info_file_handler = logging.FileHandler(info_log_file, mode='a')
    info_file_handler.setLevel(logging.INFO)
    info_file_handler.addFilter(lambda record: record.levelno == logging.INFO)
    info_file_handler.setFormatter(formatter)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(formatter)

    error_file_handler = logging.FileHandler(error_log_file, mode='a')
    error_file_handler.setLevel(logging.WARNING)
    error_file_handler.setFormatter(formatter)

    logger.addHandler(stdout_handler)
    logger.addHandler(info_file_handler)
    logger.addHandler(stderr_handler)
    logger.addHandler(error_file_handler)

    return logger


def setup_session():
    """Create a requests session with retry strategy"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        backoff_factor=1
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def extract_date_from_mission_id(mission_id: str) -> Optional[datetime]:
    """
    Extract date from mission ID (e.g., '20240913_bcifairchild_wptse_m3e' -> datetime(2024, 9, 13)).
    
    Args:
        mission_id: Mission identifier string starting with YYYYMMDD
    
    Returns:
        datetime object or None if parsing fails
    """
    logger = logging.getLogger('project2D')
    
    # Extract date prefix (first 8 digits: YYYYMMDD)
    match = re.match(r'^(\d{8})', mission_id)
    if match:
        date_str = match.group(1)
        try:
            return datetime.strptime(date_str, '%Y%m%d')
        except ValueError as e:
            logger.warning(f"Could not parse date from mission_id '{mission_id}': {e}")
            return None
    else:
        logger.warning(f"Mission ID '{mission_id}' does not start with YYYYMMDD format")
        return None


def find_dsm_files(dsm_dir: str) -> List[Tuple[str, datetime]]:
    """
    Find all DSM files in directory and extract their dates.
    
    Args:
        dsm_dir: Directory containing DSM files with dates in filename (YYYYMMDD format)
    
    Returns:
        List of tuples (file_path, date)
    """
    logger = logging.getLogger('project2D')
    dsm_files = []
    
    if not os.path.isdir(dsm_dir):
        logger.error(f"DSM directory does not exist: {dsm_dir}")
        return dsm_files
    
    # Look for DSM file extensions
    extensions = ['.tif', '.tiff']
    
    for file in os.listdir(dsm_dir):
        file_path = os.path.join(dsm_dir, file)
        if os.path.isfile(file_path) and any(file.lower().endswith(ext) for ext in extensions):
            # Try to extract date from filename (look for YYYYMMDD pattern)
            match = re.search(r'(\d{8})', file)
            if match:
                date_str = match.group(1)
                try:
                    date = datetime.strptime(date_str, '%Y%m%d')
                    dsm_files.append((file_path, date))
                    logger.info(f"  Found DSM: {file} (date: {date.strftime('%Y-%m-%d')})")  
                except ValueError:
                    logger.warning(f"  Skipping {file}: could not parse date from '{date_str}'")
            else:
                logger.warning(f"  Skipping {file}: no YYYYMMDD date pattern found")
    
    return dsm_files


def select_closest_dsm(mission_date: datetime, dsm_files: List[Tuple[str, datetime]]) -> Optional[str]:
    """
    Select the DSM file with date before and closest to the mission date.
    
    Args:
        mission_date: Date of the mission
        dsm_files: List of tuples (file_path, date)
    
    Returns:
        Path to the DSM before the mission date or None
    """
    logger = logging.getLogger('project2D')
    
    if not dsm_files:
        logger.error("No DSM files available")
        return None
    
    # Filter DSM files that are on or before the mission date
    valid_dsms = [(path, date) for path, date in dsm_files if date <= mission_date]
    
    if not valid_dsms:
        logger.error(f"No DSM files found on or before mission date {mission_date.strftime('%Y-%m-%d')}")
        return None
    
    # Find the DSM with the most recent date before or on the mission date
    closest_dsm = max(valid_dsms, key=lambda x: x[1])
    dsm_path, dsm_date = closest_dsm
    
    days_diff = (mission_date - dsm_date).days
    logger.info(f"  Selected DSM: {os.path.basename(dsm_path)} (date: {dsm_date.strftime('%Y-%m-%d')}, {days_diff} days before mission)")
    
    return dsm_path


def safe_request(session, url, timeout=30, max_retries=3):
    """Make a safe HTTP request with error handling"""
    logger = logging.getLogger('project2D')

    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=timeout)
            return response
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout,
                requests.exceptions.RequestException) as e:
            logger.error(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"Failed to fetch {url} after {max_retries} attempts")
                return None


def dms_to_decimal(dms_value, ref) -> float:
    """Convert GPS DMS (degrees, minutes, seconds) to decimal degrees."""
    degrees = float(dms_value.values[0].num) / float(dms_value.values[0].den)
    minutes = float(dms_value.values[1].num) / float(dms_value.values[1].den)
    seconds = float(dms_value.values[2].num) / float(dms_value.values[2].den)
    
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    
    if ref in ['S', 'W']:
        decimal = -decimal
    
    return decimal


def extract_gps_altitude_from_url(image_url: str, session) -> Optional[Tuple[float, float, float]]:
    """
    Extract GPS coordinates (lat, lon) and altitude from image EXIF via HTTP.
    
    Args:
        image_url: URL of the image
        session: Requests session with retry logic
        
    Returns:
        Tuple of (latitude, longitude, altitude_meters) or None if not available
    """
    logger = logging.getLogger('project2D')
    
    try:
        response = safe_request(session, image_url)
        
        if response and response.status_code == 200:
            image_data = BytesIO(response.content)
            
            try:
                with redirect_stderr(StringIO()):
                    tags = exifread.process_file(image_data, details=False)
            except (IndexError, KeyError, ValueError) as e:
                logger.error(f"Error processing EXIF data: {e} for {image_url}")
                return None
            
            # Check for GPS data
            if 'GPS GPSLatitude' not in tags or 'GPS GPSLongitude' not in tags:
                return None
            
            # Extract latitude
            lat = dms_to_decimal(tags['GPS GPSLatitude'], tags['GPS GPSLatitudeRef'].values)
            
            # Extract longitude
            lon = dms_to_decimal(tags['GPS GPSLongitude'], tags['GPS GPSLongitudeRef'].values)
            
            # Extract altitude
            altitude = None
            if 'GPS GPSAltitude' in tags:
                alt_value = tags['GPS GPSAltitude']
                altitude = float(alt_value.values[0].num) / float(alt_value.values[0].den)
                
                # Check altitude reference (0 = above sea level, 1 = below sea level)
                if 'GPS GPSAltitudeRef' in tags:
                    if tags['GPS GPSAltitudeRef'].values[0] == 1:
                        altitude = -altitude
            
            if altitude is None:
                return None
                
            return (lat, lon, altitude)
        else:
            if response:
                logger.error(f"Failed to fetch image. HTTP Status Code: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to extract GPS from {image_url}: {e}")
        return None


def get_image_dimensions_from_url(image_url: str, session) -> Optional[Tuple[int, int]]:
    """
    Extract image width and height from EXIF via HTTP.
    
    Args:
        image_url: URL of the image
        session: Requests session with retry logic
    
    Returns:
        Tuple of (width, height) or None
    """
    logger = logging.getLogger('project2D')
    
    try:
        response = safe_request(session, image_url)
        
        if response and response.status_code == 200:
            image_data = BytesIO(response.content)
            
            try:
                with redirect_stderr(StringIO()):
                    tags = exifread.process_file(image_data, details=False)
            except (IndexError, KeyError, ValueError) as e:
                logger.error(f"Error processing EXIF data: {e} for {image_url}")
                return None
            
            if 'EXIF ExifImageWidth' in tags and 'EXIF ExifImageLength' in tags:
                width = int(str(tags['EXIF ExifImageWidth']))
                height = int(str(tags['EXIF ExifImageLength']))
                return (width, height)
            elif 'Image ImageWidth' in tags and 'Image ImageLength' in tags:
                width = int(str(tags['Image ImageWidth']))
                height = int(str(tags['Image ImageLength']))
                return (width, height)
            
            return None
        else:
            return None
            
    except Exception as e:
        logger.error(f"Failed to extract dimensions from {image_url}: {e}")
        return None


def sample_dsm_median(dsm_path: str, lon: float, lat: float, buffer_m: float = 0.5) -> Optional[float]:
    """
    Sample DSM and return median value within buffer around point.
    
    Args:
        dsm_path: Path to DSM raster
        lon: Longitude in WGS84
        lat: Latitude in WGS84
        buffer_m: Buffer radius in meters (default 0.5m)
    
    Returns:
        Median DSM value or None if sampling fails
    """
    try:
        with rasterio.open(dsm_path) as src:
            dsm_crs = src.crs
            
            # Transform point from WGS84 to DSM CRS
            transformer = Transformer.from_crs("EPSG:4326", dsm_crs, always_xy=True)
            x, y = transformer.transform(lon, lat)
            
            # Create buffer bounds
            minx = x - buffer_m
            maxx = x + buffer_m
            miny = y - buffer_m
            maxy = y + buffer_m
            
            # Read window
            window = from_bounds(minx, miny, maxx, maxy, src.transform)
            
            # Read data
            data = src.read(1, window=window, masked=True)
            
            # Calculate median of valid values
            if data.size > 0 and not np.all(data.mask):
                median_val = np.median(data.compressed())
                return float(median_val)
            else:
                return None
                
    except Exception as e:
        warnings.warn(f"Failed to sample DSM at ({lon}, {lat}): {e}")
        return None


def create_footprint_polygon(center_lon: float, center_lat: float, 
                             width_m: float, height_m: float,
                             output_crs: str) -> Polygon:
    """
    Create north-oriented rectangular footprint polygon.
    
    Args:
        center_lon: Center longitude (WGS84)
        center_lat: Center latitude (WGS84)
        width_m: Footprint width in meters
        height_m: Footprint height in meters
        output_crs: Output CRS (projected)
    
    Returns:
        Shapely Polygon in specified CRS
    """
    # Transform center to output CRS
    transformer = Transformer.from_crs("EPSG:4326", output_crs, always_xy=True)
    
    x_proj, y_proj = transformer.transform(center_lon, center_lat)
    
    # Create rectangle in projected CRS (north-oriented, centered on point)
    half_width = width_m / 2.0
    half_height = height_m / 2.0
    
    minx = x_proj - half_width
    maxx = x_proj + half_width
    miny = y_proj - half_height
    maxy = y_proj + half_height
    
    # Create polygon corners (counter-clockwise)
    corners = [
        (minx, miny),  # SW
        (maxx, miny),  # SE
        (maxx, maxy),  # NE
        (minx, maxy),  # NW
        (minx, miny)   # Close
    ]
    
    return Polygon(corners)


def process_image_from_url(args) -> Optional[Dict]:
    """
    Process a single image from URL and compute footprint.
    
    Args:
        args: Tuple of (zoom_url, zoom_name, wide_url, mission_id, session, dsm_path, sensor_width_mm, 
              focal_length_mm, output_crs, center_crop, tile_crop)
    
    Returns:
        List of feature dictionaries (can be multiple if tile_crop is used) or None
    """
    (zoom_url, zoom_name, wide_url, mission_id, session, dsm_path, sensor_width_mm, 
     focal_length_mm, output_crs, center_crop, tile_crop) = args
    
    logger = logging.getLogger('project2D')
    
    # Extract GPS and altitude from wide image
    gps_data = extract_gps_altitude_from_url(wide_url, session)
    if gps_data is None:
        logger.warning(f"SKIP {zoom_name} (no GPS data in wide image)")
        return None
    
    lat, lon, altitude = gps_data
    
    # Get image dimensions from EXIF of zoom image
    dims = get_image_dimensions_from_url(zoom_url, session)
    if dims:
        img_width, img_height = dims
    else:
        logger.warning(f"SKIP {zoom_name} (no dimensions in EXIF)")
        return None
    
    # Sample DSM
    dsm_median = sample_dsm_median(dsm_path, lon, lat, buffer_m=0.5)
    if dsm_median is None:
        logger.warning(f"SKIP {zoom_name} (DSM sampling failed)")
        return None
    
    # Calculate flight height
    flight_height = altitude - dsm_median
    
    if flight_height <= 0:
        logger.warning(f"SKIP {zoom_name} (invalid flight height: {flight_height:.2f}m)")
        return None
    
    # Calculate GSD (Ground Sampling Distance)
    # GSD = (Sw * H) / (FR * imW)
    gsd = (sensor_width_mm * flight_height) / (focal_length_mm * img_width)
    
    # Calculate footprint dimensions
    features = []
    
    if tile_crop:
        # Tile crop mode: create multiple footprints (one per tile)
        tile_width_px, tile_height_px = tile_crop
        
        # Calculate number of tiles
        tiles_x = img_width // tile_width_px
        tiles_y = img_height // tile_height_px
        
        # Calculate tile footprint dimensions in meters
        tile_footprint_width = gsd * tile_width_px
        tile_footprint_height = gsd * tile_height_px
        
        # Calculate full image footprint dimensions for positioning
        full_footprint_width = gsd * img_width
        full_footprint_height = gsd * img_height
        
        # Transform center to output CRS for tile positioning
        transformer = Transformer.from_crs("EPSG:4326", output_crs, always_xy=True)
        center_x, center_y = transformer.transform(lon, lat)
        
        # Calculate starting position (top-left corner of full image footprint)
        start_x = center_x - (full_footprint_width / 2.0)
        start_y = center_y + (full_footprint_height / 2.0)
        
        tile_count = 0
        # Create a feature for each tile
        for row in range(tiles_y):
            for col in range(tiles_x):
                # Calculate tile center position in projected CRS
                tile_center_x = start_x + (col * tile_footprint_width) + (tile_footprint_width / 2.0)
                tile_center_y = start_y - (row * tile_footprint_height) - (tile_footprint_height / 2.0)
                
                # Create tile footprint polygon
                half_width = tile_footprint_width / 2.0
                half_height = tile_footprint_height / 2.0
                
                tile_corners = [
                    (tile_center_x - half_width, tile_center_y - half_height),
                    (tile_center_x + half_width, tile_center_y - half_height),
                    (tile_center_x + half_width, tile_center_y + half_height),
                    (tile_center_x - half_width, tile_center_y + half_height),
                    (tile_center_x - half_width, tile_center_y - half_height)
                ]
                tile_footprint = Polygon(tile_corners)
                
                # Calculate tile footprint area
                tile_area = tile_footprint_width * tile_footprint_height
                
                # Create feature for this tile
                tile_feature = {
                    'geometry': tile_footprint,
                    'properties': {
                        'mission_id': mission_id,
                        'image_name': zoom_name,
                        'image_url': zoom_url,
                        'wide_url': wide_url,
                        'tile_name': f"{Path(zoom_name).stem}_tile_{row}_{col}",
                        'tile_row': row,
                        'tile_col': col,
                        'latitude': lat,
                        'longitude': lon,
                        'altitude_m': altitude,
                        'dsm_file': os.path.basename(dsm_path),
                        'dsm_median_m': dsm_median,
                        'flight_height_m': flight_height,
                        'gsd_m': gsd,
                        'footprint_width_m': tile_footprint_width,
                        'footprint_height_m': tile_footprint_height,
                        'footprint_area_m2': tile_area,
                        'image_width_px': img_width,
                        'image_height_px': img_height,
                        'tile_width_px': tile_width_px,
                        'tile_height_px': tile_height_px,
                        'sensor_width_mm': sensor_width_mm,
                        'focal_length_mm': focal_length_mm
                    }
                }
                features.append(tile_feature)
                tile_count += 1
        
        logger.info(f"OK {zoom_name} (H={flight_height:.1f}m, GSD={gsd:.3f}m, {tile_count} tiles: {tiles_x}x{tiles_y}, Tile={tile_footprint_width:.1f}x{tile_footprint_height:.1f}m)")
        
    elif center_crop:
        # Use center crop dimensions instead of full image
        footprint_width = gsd * center_crop
        footprint_height = gsd * center_crop
        
        # Create footprint polygon (north-oriented)
        footprint = create_footprint_polygon(lon, lat, footprint_width, footprint_height, output_crs)
        
        # Calculate footprint area
        footprint_area = footprint_width * footprint_height
        
        # Create feature
        feature = {
            'geometry': footprint,
            'properties': {
                'mission_id': mission_id,
                'image_name': zoom_name,
                'image_url': zoom_url,
                'wide_url': wide_url,
                'tile_name': None,
                'tile_row': None,
                'tile_col': None,
                'latitude': lat,
                'longitude': lon,
                'altitude_m': altitude,
                'dsm_file': os.path.basename(dsm_path),
                'dsm_median_m': dsm_median,
                'flight_height_m': flight_height,
                'gsd_m': gsd,
                'footprint_width_m': footprint_width,
                'footprint_height_m': footprint_height,
                'footprint_area_m2': footprint_area,
                'image_width_px': img_width,
                'image_height_px': img_height,
                'tile_width_px': None,
                'tile_height_px': None,
                'sensor_width_mm': sensor_width_mm,
                'focal_length_mm': focal_length_mm
            }
        }
        features.append(feature)
        logger.info(f"OK {zoom_name} (H={flight_height:.1f}m, GSD={gsd:.3f}m, Footprint={footprint_width:.1f}x{footprint_height:.1f}m)")
        
    else:
        # Full image footprint
        footprint_width = gsd * img_width
        footprint_height = gsd * img_height
        
        # Create footprint polygon (north-oriented)
        footprint = create_footprint_polygon(lon, lat, footprint_width, footprint_height, output_crs)
        
        # Calculate footprint area
        footprint_area = footprint_width * footprint_height
        
        # Create feature
        feature = {
            'geometry': footprint,
            'properties': {
                'mission_id': mission_id,
                'image_name': zoom_name,
                'image_url': zoom_url,
                'wide_url': wide_url,
                'latitude': lat,
                'longitude': lon,
                'altitude_m': altitude,
                'dsm_file': os.path.basename(dsm_path),
                'dsm_median_m': dsm_median,
                'flight_height_m': flight_height,
                'gsd_m': gsd,
                'footprint_width_m': footprint_width,
                'footprint_height_m': footprint_height,
                'footprint_area_m2': footprint_area,
                'image_width_px': img_width,
                'image_height_px': img_height,
                'sensor_width_mm': sensor_width_mm,
                'focal_length_mm': focal_length_mm
            }
        }
        features.append(feature)
        logger.info(f"OK {zoom_name} (H={flight_height:.1f}m, GSD={gsd:.3f}m, Footprint={footprint_width:.1f}x{footprint_height:.1f}m)")
    
    return features


def write_vector_layer(features: List[Dict], output_path: str, crs: str):
    """
    Write features to vector layer (GeoPackage).
    """
    if not features:
        print("No features to write!")
        return
    
    output_ext = Path(output_path).suffix.lower()
    if output_ext != '.gpkg':
        output_path = str(Path(output_path).with_suffix('.gpkg'))
        print(f"Forcing GeoPackage extension: {output_path}")
    
    driver = 'GPKG'
    
    # Define schema
    has_tiles = any('tile_name' in f['properties'] and f['properties']['tile_name'] is not None for f in features)
    
    if has_tiles:
        schema = {
            'geometry': 'Polygon',
            'properties': {
                'mission_id': 'str',
                'image_name': 'str',
                'image_url': 'str',
                'wide_url': 'str',
                'tile_name': 'str',
                'tile_row': 'int',
                'tile_col': 'int',
                'latitude': 'float',
                'longitude': 'float',
                'altitude_m': 'float',
                'dsm_file': 'str',
                'dsm_median_m': 'float',
                'flight_height_m': 'float',
                'gsd_m': 'float',
                'footprint_width_m': 'float',
                'footprint_height_m': 'float',
                'footprint_area_m2': 'float',
                'image_width_px': 'int',
                'image_height_px': 'int',
                'tile_width_px': 'int',
                'tile_height_px': 'int',
                'sensor_width_mm': 'float',
                'focal_length_mm': 'float'
            }
        }
    else:
        schema = {
            'geometry': 'Polygon',
            'properties': {
                'mission_id': 'str',
                'image_name': 'str',
                'image_url': 'str',
                'wide_url': 'str',
                'latitude': 'float',
                'longitude': 'float',
                'altitude_m': 'float',
                'dsm_file': 'str',
                'dsm_median_m': 'float',
                'flight_height_m': 'float',
                'gsd_m': 'float',
                'footprint_width_m': 'float',
                'footprint_height_m': 'float',
                'footprint_area_m2': 'float',
                'image_width_px': 'int',
                'image_height_px': 'int',
                'sensor_width_mm': 'float',
                'focal_length_mm': 'float'
            }
        }
    
    # Write features
    with fiona.open(output_path, 'w', driver=driver, crs=crs, schema=schema) as dst:
        for feature in features:
            # Remove tile-related fields if not in schema
            props = feature['properties'].copy()
            if 'tile_name' not in schema['properties']:
                props.pop('tile_name', None)
                props.pop('tile_row', None)
                props.pop('tile_col', None)
                props.pop('tile_width_px', None)
                props.pop('tile_height_px', None)
            
            dst.write({
                'geometry': feature['geometry'].__geo_interface__,
                'properties': props
            })
    
    print(f"\nSuccessfully wrote {len(features)} footprints to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate image footprint polygons from Arbutus aerial images and DSM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python project2Dpictures_arbutus.py --config-path ~/.config/rclone/rclone.conf --project-qualifier bci --dsm-dir ./dsm_files --sensor-width 6.4 --focal-length 29.9 --crs EPSG:32617 --output-dir ./output
  python project2Dpictures_arbutus.py --config-path ~/.config/rclone/rclone.conf --project-qualifier bci --dsm-dir ./dsm_files --sensor-width 6.4 --focal-length 29.9 --crs EPSG:32617 --output-dir ./output --center-crop 1008
  python project2Dpictures_arbutus.py --config-path ~/.config/rclone/rclone.conf --project-qualifier bci --dsm-dir ./dsm_files --sensor-width 6.4 --focal-length 29.9 --crs EPSG:32617 --output-dir ./output --tile-crop 1000 1000
        """
    )
    
    parser.add_argument('--config-path', type=str, required=True,
                        help='Path to rclone config file')
    parser.add_argument('--project-qualifier', type=str, required=True,
                        help='Project qualifier string (e.g., bci, quebec)')
    parser.add_argument('--dsm-dir', type=str, required=True,
                        help='Directory containing Digital Surface Model (DSM) raster files with dates in filenames (YYYYMMDD format)')
    parser.add_argument('--sensor-width', type=float, required=True,
                        help='Camera sensor width in millimeters (Sw)')
    parser.add_argument('--focal-length', type=float, required=True,
                        help='Camera focal length in millimeters (FR) - real focal length, not 35mm equivalent')
    parser.add_argument('--center-crop', type=int, default=None,
                        help='Center crop size in pixels (default: None = use full image, recommended: 1008)')
    parser.add_argument('--tile-crop', type=int, nargs=2, metavar=('WIDTH', 'HEIGHT'), default=None,
                        help='Tile crop dimensions in pixels (e.g., --tile-crop 1000 1000 for 1000x1000 tiles)')
    parser.add_argument('--output-dir', type=str, required=True,
                        help='Output directory for logs and GeoPackage')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output GeoPackage file name (default: <project_qualifier>_footprints.gpkg)')
    parser.add_argument('--crs', type=str, required=True,
                        help='Output CRS (projected, e.g., EPSG:32617 for UTM 17N)')
    parser.add_argument('--max-workers', type=int, default=8,
                        help='Number of parallel workers (default: 8)')
    
    args = parser.parse_args()
    
    # Set default output filename
    if not args.output:
        args.output = f"{args.project_qualifier}_footprints.gpkg"
    
    output_path = os.path.join(args.output_dir, args.output)
    
    # Setup logging
    logger = setup_logging(args.output_dir, args.project_qualifier)
    
    # Check if DSM directory exists
    if not os.path.isdir(args.dsm_dir):
        logger.error(f"DSM directory does not exist: {args.dsm_dir}")
        sys.exit(1)
    
    # Find all available DSM files
    logger.info(f"Scanning DSM directory: {args.dsm_dir}")
    available_dsm_files = find_dsm_files(args.dsm_dir)
    
    if not available_dsm_files:
        logger.error(f"No valid DSM files found in {args.dsm_dir}")
        sys.exit(1)
    
    logger.info(f"Found {len(available_dsm_files)} DSM files with valid dates")
    
    # Validate mutually exclusive options
    if args.center_crop and args.tile_crop:
        logger.error("Cannot use both --center-crop and --tile-crop options")
        sys.exit(1)
    
    # Log parameters
    logger.info("Camera parameters:")
    logger.info(f"  Sensor width: {args.sensor_width} mm")
    logger.info(f"  Focal length: {args.focal_length} mm")
    if args.center_crop:
        logger.info(f"  Center crop: {args.center_crop} x {args.center_crop} pixels")
    if args.tile_crop:
        logger.info(f"  Tile crop: {args.tile_crop[0]} x {args.tile_crop[1]} pixels")
    logger.info(f"DSM directory: {args.dsm_dir}")
    logger.info(f"Output CRS: {args.crs}")
    logger.info(f"Max workers: {args.max_workers}")
    
    # Get all folders matching project_qualifier and 'wpt'
    base_url = "https://object-arbutus.cloud.computecanada.ca"
    list_folders = subprocess.run(
        ["rclone", "--config", args.config_path, "lsf", "AllianceCanBuckets:", "--dirs-only"],
        capture_output=True, text=True
    )
    folders = [f.strip().rstrip('/') for f in list_folders.stdout.splitlines() 
               if args.project_qualifier.lower() in f.lower() and 'wpt' in f.lower()]
    
    logger.info(f"Found {len(folders)} mission folders matching '{args.project_qualifier}'")
    
    # Create session for HTTP requests
    session = setup_session()
    
    # Process all zoom images
    all_features = []
    for folder in folders:
        logger.info(f"Processing mission: {folder}")
        
        # Extract mission date and select appropriate DSM
        mission_date = extract_date_from_mission_id(folder)
        if mission_date is None:
            logger.warning(f"Could not extract date from mission '{folder}', skipping")
            continue
        
        logger.info(f"  Mission date: {mission_date.strftime('%Y-%m-%d')}")
        dsm_path = select_closest_dsm(mission_date, available_dsm_files)
        
        if dsm_path is None:
            logger.error(f"Could not select DSM for mission '{folder}', skipping")
            continue
        
        # List files in folder
        file_list = subprocess.run(
            ["rclone", "--config", args.config_path, "lsf", f"AllianceCanBuckets:{folder}", "--files-only", "-R"],
            capture_output=True, text=True
        )
        files = file_list.stdout.strip().split("\n")
        
        # Separate wide and zoom files
        wide_files = [f for f in files if f.endswith('.JPG') and 'zoom' not in f.lower()]
        zoom_files = [f for f in files if f.endswith('.JPG') and 'zoom' in f.lower()]
        
        logger.info(f"  Found {len(zoom_files)} zoom images and {len(wide_files)} wide images")
        
        # Log a warning if the number of wide and zoom files does not match
        if len(wide_files) != len(zoom_files):
            logger.warning(f"Folder '{folder}': Number of wide files ({len(wide_files)}) does not match number of zoom files ({len(zoom_files)})")
        
        # Prepare args for parallel processing
        args_list = []
        for zoom_file in zoom_files:
            zoom_url = f"{base_url}/{folder}/{zoom_file}"
            zoom_name = os.path.basename(zoom_file)
            
            # Find matching wide image
            identifier = zoom_name.split("_")[-1].lower().replace("zoom.jpg", "")
            wide_file = None
            for wide_candidate in wide_files:
                wide_basename = os.path.basename(wide_candidate)
                if re.search(rf'_{identifier}\.jpg$', wide_basename, re.IGNORECASE):
                    wide_file = wide_candidate
                    break
            
            if not wide_file:
                logger.warning(f"Could not find matching wide photo for {zoom_file} with identifier {identifier}")
                continue
            
            wide_url = f"{base_url}/{folder}/{wide_file}"
            
            args_list.append((
                zoom_url, zoom_name, wide_url, folder, session, dsm_path,
                args.sensor_width, args.focal_length, args.crs,
                args.center_crop, tuple(args.tile_crop) if args.tile_crop else None
            ))
        
        # Process images in parallel
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            results = list(executor.map(process_image_from_url, args_list))
        
        # Collect features (each result can be a list of features for tile mode)
        for result in results:
            if result:
                if isinstance(result, list):
                    all_features.extend(result)
                else:
                    all_features.append(result)
        
        logger.info(f"  Processed {len(zoom_files)} images from {folder}")
    
    # Write output
    if all_features:
        write_vector_layer(all_features, output_path, args.crs)
        logger.info(f"Processing complete! Generated {len(all_features)} footprint polygons.")
    else:
        logger.warning("No valid footprints generated. Check image EXIF data and DSM coverage.")
        sys.exit(1)


if __name__ == '__main__':
    main()
