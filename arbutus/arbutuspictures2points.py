import argparse
import exifread
import geopandas as gpd
import logging
import os
import pandas as pd
import requests
import re
import subprocess
import time

from contextlib import contextmanager, redirect_stderr
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from io import StringIO
from requests.adapters import HTTPAdapter
from shapely.geometry import Point
from tqdm import tqdm
from urllib3.util.retry import Retry

@contextmanager
def suppress_stderr():
    """Context manager to suppress stderr."""
    with open(os.devnull, 'w') as fnull:
        with redirect_stderr(fnull):
            yield

def convert_to_decimal_degrees(value, ref):
    """
    Convert GPS coordinates to decimal degrees.
    
    Args:
        value: GPS coordinate value.
        ref: GPS coordinate reference (N, S, E, W).
        
    Returns:
        float: Coordinate in decimal degrees.
    """
    if len(value.values) != 3:
        raise ValueError("Malformed or incomplete EXIF data: GPS coordinate value does not contain exactly three elements")
    d, m, s = [float(x.num) / float(x.den) for x in value.values]
    decimal_degrees = d + (m / 60) + (s / 3600)
    if ref.values and ref.values[0] in ['S', 'W']:
        decimal_degrees = -decimal_degrees
    return decimal_degrees

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

def safe_request(session, url, timeout=30, max_retries=3):
    """Make a safe HTTP request with error handling"""
    logger = logging.getLogger('arbutus2points')

    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=timeout)
            return response
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout,
                requests.exceptions.RequestException) as e:
            logger.error(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error(f"Failed to fetch {url} after {max_retries} attempts")
                return None

def get_coordinates_from_image_url(picture_url, session):
    """
    Get latitude and longitude from the image metadata.
    
    Args:
        picture_url (str): URL of the image to process.
        session: Requests session with retry logic.
        
    Returns:
        tuple or None: (latitude, longitude) in decimal degrees if found, otherwise None.
    """
    logger = logging.getLogger('arbutus2points')
    
    response = safe_request(session, picture_url)

    if response and response.status_code == 200:
        # Load the image into BytesIO
        image_data = BytesIO(response.content)
        
        try:
            with redirect_stderr(StringIO()):
                tags = exifread.process_file(image_data, details=False)
        except (IndexError, KeyError, ValueError) as e:
            logger.error(f"Error processing EXIF data: {e} for {picture_url}")
            return None
        
        latitude = tags.get('GPS GPSLatitude')
        latitude_ref = tags.get('GPS GPSLatitudeRef')
        longitude = tags.get('GPS GPSLongitude')
        longitude_ref = tags.get('GPS GPSLongitudeRef')
        
        # Check if EXIF tags are present
        if latitude and latitude_ref and longitude and longitude_ref:
            try:
                # Convert to decimal degrees
                latitude = convert_to_decimal_degrees(latitude, latitude_ref)
                longitude = convert_to_decimal_degrees(longitude, longitude_ref)
                return latitude, longitude
            
            except (ValueError, AttributeError) as e:
                logger.error(f"Error converting GPS coordinates: {e}")
                return None
        else:
            logger.warning("Missing GPS EXIF tags in the image metadata.")
            return None
    else:
        if response:
            logger.error(f"Failed to fetch image. HTTP Status Code: {response.status_code}")
        return None

def process_zoom_file(args):
    logger = logging.getLogger('arbutus2points')

    # Create session with retry logic
    session = setup_session()

    zoom_file, wide_files, folder = args
    zoom_basename = os.path.basename(zoom_file)
    identifier_match = zoom_basename.split("_")[-1].lower().replace("zoom.jpg", "")
    wide_file = None
    for wide_candidate in wide_files:
        wide_basename = os.path.basename(wide_candidate)
        if re.search(rf'_{identifier_match}\.jpg$', wide_basename, re.IGNORECASE):
            wide_file = wide_candidate
            break
    
    if not wide_file:
        logger.warning(f"Could not find matching wide photo for {zoom_file} with identifier {identifier_match}")
        return None
    
    wide_url = f"https://object-arbutus.cloud.computecanada.ca/{folder}/{wide_file}"
    zoom_url = f"https://object-arbutus.cloud.computecanada.ca/{folder}/{zoom_file}"
    coords = get_coordinates_from_image_url(wide_url, session)
    if coords:
        return {
            'geometry': Point(coords[1], coords[0]),
            'mission_id': folder,
            'point_id': identifier_match,
            'wide_url': wide_url,
            'zoom_url': zoom_url
        }
    return None

def setup_logging(output_dir, project_qualifier):
    """Configure logging to both file and console."""
    # Create logs directory
    log_dir = os.path.join(output_dir)
    os.makedirs(log_dir, exist_ok=True)
    
    # Set up logging configuration
    log_file = os.path.join(log_dir, f'arbutus2points_{project_qualifier}.log')
    
    # Create a logger
    logger = logging.getLogger('arbutus2points')
    logger.setLevel(logging.INFO)
    
    # Create handlers
    file_handler = logging.FileHandler(log_file)
    console_handler = logging.StreamHandler()
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def main(output_dir, points_layer, config_path, project_qualifier, max_workers=8):
    # ---- Config ----
    base_url = "https://object-arbutus.cloud.computecanada.ca"

    # Set up logger (output directory can be changed as needed)
    logger = setup_logging(output_dir=output_dir, project_qualifier=project_qualifier)
    points_layer_path = os.path.join(output_dir, points_layer)
    existing_gdf = None
    existing_missions = set()
    existing_counts = dict()
    if os.path.exists(points_layer_path):
        existing_gdf = gpd.read_file(points_layer_path)
        if 'mission_id' in existing_gdf.columns:
            existing_missions = set(existing_gdf['mission_id'].unique())
            # Count points per mission
            existing_counts = existing_gdf.groupby('mission_id').size().to_dict()
            logger.info("Existing point counts per mission:")
            for mission, count in existing_counts.items():
                logger.info(f"  {mission}: {count}")
        else:
            logger.warning("Existing points layer does not have 'mission_id' column. Skipping mission check.")
    else:
        logger.info("No existing points layer found. Will create a new one.")

    # Get all folders matching project_qualifier and 'wpt'
    list_folders = subprocess.run(
        ["rclone", "--config", config_path, "lsf", "AllianceCanBuckets:", "--dirs-only"],
        capture_output=True, text=True
    )
    folders = [f.strip() for f in list_folders.stdout.splitlines() if project_qualifier in f and 'wpt' in f]

    # Loop through each folder and process image pairs
    rows = []
    for folder in tqdm(folders, desc='Folders Progress', unit='folder'):
        folder = folder.rstrip('/')
        file_list = subprocess.run(
            ["rclone", "--config", config_path, "lsf", f"AllianceCanBuckets:{folder}", "--files-only", "-R"],
            capture_output=True, text=True
        )
        files = file_list.stdout.strip().split("\n")
        
        # Separate wide and zoom files
        wide_files = [f for f in files if f.endswith('.JPG') and 'zoom' not in f.lower()]
        zoom_files = [f for f in files if f.endswith('.JPG') and 'zoom' in f.lower()]
        
        # Log a warning if the number of wide and zoom files does not match
        if len(wide_files) != len(zoom_files):
            logger.warning(f"Folder '{folder}': Number of wide files ({len(wide_files)}) does not match number of zoom files ({len(zoom_files)})")
        # Track number of rows before processing this folder
        rows_before = len(rows)
        
        # If mission is already present, only add missing points
        if folder in existing_missions:
            existing_points = set()
            if existing_gdf is not None:
                # Use both wide_url and point_id for more robust matching
                existing_points = set(zip(
                    existing_gdf[existing_gdf['mission_id'] == folder]['wide_url'],
                    existing_gdf[existing_gdf['mission_id'] == folder]['point_id']
                ))
            # Build a lookup for wide_files by identifier
            wide_lookup = {os.path.basename(wf).split('_')[-1].lower().replace('jpg', '').replace('.', '').replace('zoom', ''): wf for wf in wide_files}
            # Only process zoom files whose wide_url+point_id are not already present
            zoom_files_to_add = []
            for zoom_file in zoom_files:
                zoom_basename = os.path.basename(zoom_file)
                identifier_match = zoom_basename.split("_")[-1].lower().replace("zoom.jpg", "")
                wide_file = wide_lookup.get(identifier_match)
                wide_url = f"https://object-arbutus.cloud.computecanada.ca/{folder}/{wide_file}" if wide_file else None
                if wide_url and (wide_url, identifier_match) not in existing_points:
                    zoom_files_to_add.append(zoom_file)
            if not zoom_files_to_add:
                logger.info(f"All points for mission '{folder}' are already present. Skipping.")
                continue
            else:
                logger.info(f"Adding {len(zoom_files_to_add)} missing points for mission '{folder}'.")
                zoom_files = zoom_files_to_add
        
        args_list = [(zoom_file, wide_files, folder) for zoom_file in zoom_files]
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(process_zoom_file, args_list))
        for result in results:
            if result:
                rows.append(result)
        
        # Log summary for this folder
        rows_added = len(rows) - rows_before
        logger.info(f"Finished mission '{folder}': {rows_added} points added, {len(wide_files)} wide images, {len(zoom_files)} zoom images.")

    # After processing all folders
    if rows:
        if existing_gdf is not None and not existing_gdf.empty:
            # Concatenate existing and new rows, avoiding duplicates
            new_gdf = gpd.GeoDataFrame(rows, crs='EPSG:4326')
            combined_gdf = pd.concat([existing_gdf, new_gdf], ignore_index=True)
            # Drop duplicates based on mission_id, point_id, and wide_url
            combined_gdf = combined_gdf.drop_duplicates(subset=['mission_id', 'point_id', 'wide_url'])
            combined_gdf.to_file(points_layer_path, driver="GPKG")
        else:
            gdf = gpd.GeoDataFrame(rows, crs='EPSG:4326')
            gdf.to_file(points_layer_path, driver="GPKG")
        logger.info(f"Successfully saved {len(rows)} new points to {points_layer_path}")
    else:
        logger.info("No new points to add. Points layer unchanged.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Arbutus BCI image folders in parallel.")
    parser.add_argument("--output_dir", required=True, help="Output directory for logs and points layer.")
    parser.add_argument("--points_layer", required=True, help="Points layer filename to use or create. Must be in output directory if using existing one.")
    parser.add_argument("--config_path", required=True, help="Path to rclone config file.")
    parser.add_argument("--project_qualifier", required=True, help="Project qualifier string.")
    parser.add_argument("--max_workers", type=int, default=8, help="Number of parallel workers.")
    args = parser.parse_args()

    main(
        output_dir=args.output_dir,
        points_layer=args.points_layer,
        config_path=args.config_path,
        project_qualifier=args.project_qualifier,
        max_workers=args.max_workers
    )