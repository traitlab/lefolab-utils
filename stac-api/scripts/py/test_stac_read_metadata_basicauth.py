import os
from pathlib import Path
import rasterio
from dotenv import load_dotenv

# Load variables from the .env file into the environment
# Use the .env file in the same directory as this script
env_path = Path(__file__).parent / f"{Path(__file__).name}.env"
load_dotenv(dotenv_path=env_path) 

# Get credentials using os.getenv()
username = os.getenv('RASTER_USER')
password = os.getenv('RASTER_PASSWORD')

# Verify credentials are loaded
if not username or not password:
    raise ValueError("RASTER_USER and RASTER_PASSWORD must be set in .env file")

print(f"Loaded credentials for user: {username}")

# Embed credentials directly in the URL
ortho_url = f'http://{username}:{password}@206.12.100.29/share/1/20240716_bciwhole_rx1rii/20240716_bciwhole_rx1rii_rgb.cog.tif'

try:
    print(f"\nAttempting to open: {ortho_url.replace(f'{username}:{password}@', '***:***@')}")
    with rasterio.open(ortho_url) as src:
        print("\n=== Successfully opened remote orthomosaic ===")
        print("CRS:", src.crs)
        print("Bounds:", src.bounds)
        print("Width, Height:", src.width, src.height)
        print("Driver:", src.driver)
        print("Count (bands):", src.count)
        print("Dtype:", src.dtypes)
        print("Metadata:", src.meta)
except Exception as e:
    print(f"\n❌ Error opening remote orthomosaic: {e}")
    print("\nTroubleshooting tips:")
    print("1. Verify credentials in .env file are correct")
    print("2. Test URL access with: curl -u username:password", ortho_url)
    print("3. Ensure the server supports HTTP Basic Auth")
    raise