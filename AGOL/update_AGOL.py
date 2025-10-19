# On Windows, run these commands first to activate the ArcGIS Pro Python environment:
# "C:/Program Files/ArcGIS/Pro/bin/Python/Scripts/activate.bat"
# conda activate arcgispro-py3

import argparse
import os
import logging
import sys

from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
from dotenv import load_dotenv

# Setup logging with timestamp
logger = logging.getLogger('update_AGOL')
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

def update_layer(env_path, project_name, shp_path):
	logger = logging.getLogger('update_AGOL')
	logger.info(f"Loading environment variables from {env_path}")
	load_dotenv(env_path)

	proxy = {
		'http': os.getenv("PROXY_HTTP"),
		'https': os.getenv("PROXY_HTTPS"),
	}

	if not proxy['http'] or not proxy['https']:
		logger.error("Proxy settings not set in environment.")
		return

	ArcGIS_username = os.getenv("AGOL_USER")
	ArcGIS_password = os.getenv("AGOL_PASSWORD")
	if not ArcGIS_username or not ArcGIS_password:
		logger.error("AGOL_USER or AGOL_PASSWORD not set in environment.")
		return

	env_var = f"{project_name.upper()}_ITEM_ID"
	item_id = os.getenv(env_var)
	if not item_id:
		logger.error(f"Environment variable {env_var} not set.")
		return

	update_shp = os.path.join(shp_path, f"{project_name}_wpt_3857.zip")

	logger.info("Connecting to ArcGIS Online...")
	gis = GIS("https://lefo.maps.arcgis.com/", ArcGIS_username, ArcGIS_password, proxy=proxy)
	logger.info(f"Logged to {gis.url} as {gis.properties.user.username}")

	logger.info(f"Getting content item: {item_id}")
	layer = gis.content.get(item_id)
	if not layer:
		logger.error(f"Content item {item_id} not found.")
		return
	flc = FeatureLayerCollection.fromitem(layer)

	logger.info(f"Overwriting layer with file: {update_shp}")
	try:
		flc.manager.overwrite(update_shp)
		logger.info("Layer updated successfully.")
	except Exception as e:
		logger.error(f"Failed to update layer: {e}")

def main():
	parser = argparse.ArgumentParser(description="Update ArcGIS Online layer with zipped shapefile.")
	parser.add_argument('--env_path', required=True, help='Path to .env file with AGOL_USER and AGOL_PASSWORD')
	parser.add_argument('--project_name', required=True, help='Project name')
	parser.add_argument('--shp_path', required=True, help='Directory containing zipped shapefile')
	args = parser.parse_args()

	update_layer(args.env_path, args.project_name, args.shp_path)

if __name__ == "__main__":
	main()