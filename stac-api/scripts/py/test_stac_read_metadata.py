# requirements:
# - an Internet connexion
# - python3 installed

# Create the Python virtual environment where the python script is located
# cd /where/your/python/script/is/located
# python3 -m venv .venv

# Activate the Python virtual environment
# source ./.venv/bin/activate

# Setup the Python virtual environment
# python3 -m pip install --upgrade pip
# python3 -m pip install rasterio

# Execute your script
# python3 test_stac_read_metadata.py

# Deactivate the Python virtual environment once not needed anymore

import rasterio

# Replace this with a real COG URL from your STAC API results
cog_url = "http://206.12.100.29/share/public/20230724_lichentundra17_m3m/20230724_lichentundra17_m3m_rgb.cog.tif"

def print_cog_metadata(url):
    with rasterio.open(url) as src:
        print("CRS:", src.crs)
        print("Bounds:", src.bounds)
        print("Width, Height:", src.width, src.height)
        print("Driver:", src.driver)
        print("Count (bands):", src.count)
        print("Dtype:", src.dtypes)
        print("Metadata:", src.meta)

if __name__ == "__main__":
    print_cog_metadata(cog_url)