# requirements:
# - an Internet connexion
# - python3 installed
# - within the UdeM network, or having the UdeM VPN active
# - tunnel to lefoai active

# Create the Python virtual environment where the python script is located
# cd /where/your/python/script/is/located
# python3 -m venv .venv

# Activate the Python virtual environment
# source ./.venv/bin/activate

# Setup the Python virtual environment
# python3 -m pip install --upgrade pip
# python3 -m pip install requests

# Execute your script
# python3 test_stac_search.py

# Deactivate the Python virtual environment once not needed anymore

import requests

# STAC API endpoint
STAC_API_URL = "http://206.12.102.82/stac-fastapi-pgstac/api/v1/pgstac/"

# Define search parameters
start_date = "2024-09-01T00:00:00Z"
end_date = "2024-10-01T23:59:59Z"
keyword = "sbl"
# Approximate bounding box for Quebec
quebec_bbox = [-79.76259, 45.00495, -57.10592, 62.58502]
limit = 200

# Search collections in the STAC API with proxy bypass


def search_collections():
    payload = {
        "datetime": f"{start_date}/{end_date}",
        "bbox": quebec_bbox,
        "limit": limit  # Increase limit as needed
    }

    response = requests.post(
        f"{STAC_API_URL}/search",
        json=payload,
        # Disable proxies for this request
        proxies={"http": None, "https": None}
    )
    response.raise_for_status()
    data = response.json()

    # Filter results for collections with the keyword in their name
    filtered_collections = []
    for feature in data.get("features", []):
        collection_name = feature.get("collection", "").lower()
        if keyword in collection_name:
            filtered_collections.append(feature)

    return filtered_collections

# Print the asset files of type COG


def print_cog_assets(collections):
    for collection in collections:
        collection_id = collection.get("id")
        collection_name = collection.get("collection")
        assets = collection.get("assets", {})

        # print(f"\nCollection ID: {collection_id}, Name: {collection_name}")

        # Iterate over assets and print only those that are COGs
        for asset_key, asset_info in assets.items():
            asset_type = asset_info.get("type", "")
            asset_href = asset_info.get("href", "")
            mime_type = asset_info.get("type", "")

            # Check if the asset is a COG
            if (
                "cloud-optimized" in mime_type.lower()
                or "cog" in asset_key.lower()
            ) and "lowres" not in asset_key.lower() and "overview" not in asset_key.lower():
                print(f"{asset_href}")


def main():
    collections = search_collections()
    if collections:
        print(f"Found {len(collections)} matching collections:")
        print_cog_assets(collections)
    else:
        print("No collections found with the specified parameters.")


if __name__ == "__main__":
    main()
