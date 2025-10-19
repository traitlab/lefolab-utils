import geopandas as gpd
import logging
import os
import sys
import zipfile

# Setup logging with timestamp
logger = logging.getLogger('gpkg2shp')
logger.setLevel(logging.INFO)

# Handler for INFO to stdout
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.INFO)
stdout_handler.addFilter(lambda record: record.levelno == logging.INFO)
stdout_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

# Handler for WARNING and ERROR to stderr
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.WARNING)
stderr_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

# Remove default handlers and add custom ones
logger.handlers = []
logger.addHandler(stdout_handler)
logger.addHandler(stderr_handler)

def delete_old_files(base_path):
    logger = logging.getLogger('gpkg2shp')
    exts = [".shp", ".shx", ".dbf", ".prj", ".cpg", ".zip"]
    for ext in exts:
        file_path = base_path + ext
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Deleted old file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")

def convert_and_zip(input_gpkg, output_dir):
    logger = logging.getLogger('gpkg2shp')
    logger.info(f"Reading GeoPackage: {input_gpkg}")
    try:
        gdf = gpd.read_file(input_gpkg)
    except Exception as e:
        logger.error(f"Failed to read GeoPackage: {e}")
        sys.exit(1)
    logger.info("Reprojecting to EPSG:3857")
    try:
        gdf = gdf.to_crs(epsg=3857)
    except Exception as e:
        logger.error(f"Failed to reproject: {e}")
        sys.exit(1)
    shp_name = os.path.splitext(os.path.basename(input_gpkg))[0] + "_3857.shp"
    shp_path = os.path.join(output_dir, shp_name)
    base_path = shp_path[:-4]
    # Delete old files before generating new ones
    delete_old_files(base_path)
    logger.info(f"Exporting to shapefile: {shp_path}")
    try:
        gdf.to_file(shp_path)
    except Exception as e:
        logger.error(f"Failed to export shapefile: {e}")
        sys.exit(1)
    exts = [".shp", ".shx", ".dbf", ".prj", ".cpg"]
    files = [base_path + ext for ext in exts if os.path.exists(base_path + ext)]
    zip_path = base_path + ".zip"
    logger.info(f"Zipping shapefile components to: {zip_path}")
    try:
        with zipfile.ZipFile(zip_path, "w") as zf:
            for f in files:
                zf.write(f, arcname=os.path.basename(f))
        logger.info(f"Zipped shapefile: {zip_path}")
        for f in files:
            try:
                os.remove(f)
                logger.info(f"Deleted shapefile component: {f}")
            except Exception as e:
                logger.error(f"Failed to delete {f}: {e}")
    except Exception as e:
        logger.error(f"Failed to zip shapefile components: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        logger.error("Usage: python gpkg2shp.py input.gpkg output_dir")
        sys.exit(1)
    input_gpkg = sys.argv[1]
    output_dir = sys.argv[2]
    convert_and_zip(input_gpkg, output_dir)