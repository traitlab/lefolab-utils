# pip install pystac-client planetary-computer pyproj pandas

from pystac_client import Client
from pystac_client.exceptions import APIError
import planetary_computer as pc
from pyproj import Transformer
import pandas as pd
import os
import time

# ---- Your extent in EPSG:26910 (meters) ----
xmin, ymin, xmax, ymax = (
    590997.6660000021, 6798503.645999998,
    591797.6660000002, 6798623.645999998
)

# ---- Convert bbox to WGS84 lon/lat for STAC search ----
to_wgs84 = Transformer.from_crs("EPSG:26910", "EPSG:4326", always_xy=True)
lon_min, lat_min = to_wgs84.transform(xmin, ymin)
lon_max, lat_max = to_wgs84.transform(xmax, ymax)
bbox_wgs84 = [lon_min, lat_min, lon_max, lat_max]

# Open catalog and get collection info
catalog = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
collection = catalog.get_collection("sentinel-2-l2a")
print(f"Using collection: {collection.id}")
print(f"Collection title: {collection.title}")
print(f"Collection endpoint: https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a\n")

def list_s2_assets(year: int, cloud_lt: int = 80, limit: int = 500, max_retries: int = 3):
    """
    List Sentinel-2 assets for a given year using the collection endpoint.
    
    Args:
        year: Year to search
        cloud_lt: Maximum cloud cover percentage
        limit: Maximum number of items per page
        max_retries: Maximum number of retry attempts for API errors
    
    Returns:
        DataFrame with asset information
    """
    # Exclude winter: Apr–Oct
    dt = f"{year}-04-01/{year}-10-31"
    
    rows = []
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            print(f"Searching for {year} (attempt {retry_count + 1}/{max_retries})...")
            
            # Use catalog.search() with the collection specified
            # This uses the collection endpoint: /collections/sentinel-2-l2a/items
            search = catalog.search(
                collections=["sentinel-2-l2a"],
                bbox=bbox_wgs84,
                datetime=dt,
                query={"eo:cloud_cover": {"lt": cloud_lt}},
                limit=limit,
                method="GET",  # Use GET method which is more reliable
            )
            
            # Process items with pagination
            item_count = 0
            for item in search.items():
                props = item.properties
                signed = pc.sign(item)

                # Prefer visual, then B04 (red), then first available
                asset_keys = ["visual", "B04", "B03", "B02", "B08"]
                selected_key = None
                selected_asset = None
                
                for key in asset_keys:
                    if key in signed.assets:
                        selected_key = key
                        selected_asset = signed.assets[key]
                        break
                
                # Skip if no suitable asset found
                if selected_key is None:
                    continue

                rows.append({
                    "year": year,
                    "datetime": props.get("datetime"),
                    "cloud_cover": props.get("eo:cloud_cover"),
                    "tile": props.get("s2:mgrs_tile"),
                    "item_id": item.id,
                    "asset_key": selected_key,
                    "href_signed": selected_asset.href,  # signed URL (expires)

                    # optional extras (keep if you want them in the CSV)
                    "platform": props.get("platform"),
                    "asset_title": getattr(selected_asset, "title", None),
                    "media_type": selected_asset.media_type,
                })
                item_count += 1
                
                # Small delay to avoid rate limiting
                if item_count % 50 == 0:
                    time.sleep(0.5)
            
            print(f"  Found {item_count} items for {year}")
            # Success - break out of retry loop
            break
            
        except APIError as e:
            retry_count += 1
            if retry_count >= max_retries:
                print(f"ERROR: Failed to retrieve data for {year} after {max_retries} attempts.")
                print(f"Error: {e}")
                if rows:
                    print(f"Returning partial results ({len(rows)} items found)...")
                break
            else:
                wait_time = min(2 ** retry_count, 30)  # Exponential backoff, max 30s
                print(f"API error for {year}: {e}")
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        
        except Exception as e:
            print(f"Unexpected error for {year}: {e}")
            break

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Convert datetime to datetime type
    df["datetime"] = pd.to_datetime(df["datetime"])
    
    # Extract date (without time) for grouping by day
    df["date"] = df["datetime"].dt.date
    
    # Extract month
    df["month"] = df["datetime"].dt.month

    # Extract processing baseline from item_id: ..._N0510_...
    df["processing"] = (
        df["item_id"].astype(str)
        .str.extract(r"_N(\d{4})_", expand=False)
        .fillna(-1)
        .astype(int)
    )

    # Best first: lowest cloud, then newest processing baseline, then earliest datetime
    df = df.sort_values(
        by=["cloud_cover", "processing", "datetime"],
        ascending=[True, False, True],
        kind="mergesort",  # stable sort (nice when ties)
    )

    # Keep only the best item per day (not per scene/tile/band)
    # Group by date and keep the first (best) item for each day
    df = df.drop_duplicates(
        subset=["date"],
        keep="first"
    )

    # Drop temporary columns
    df = df.drop(columns=["processing", "date"])

    # Optional: enforce exact output column order with month as 2nd column
    csv_cols = [
        "year", "month", "datetime", "item_id", "cloud_cover", "platform",
        "tile", "asset_key", "asset_title", "media_type", "href_signed"
    ]
    df = df[csv_cols]

    return df

# Query each year with delays to avoid rate limiting
print("Querying Sentinel-2 Level-2A data from Planetary Computer...")
print(f"Bounding box: {bbox_wgs84}\n")

df2022 = list_s2_assets(2022, cloud_lt=80)
if not df2022.empty:
    print(f"  ✓ 2022: {len(df2022)} rows\n")
time.sleep(3)  # Delay between requests

df2023 = list_s2_assets(2023, cloud_lt=80)
if not df2023.empty:
    print(f"  ✓ 2023: {len(df2023)} rows\n")
time.sleep(3)  # Delay between requests

df2024 = list_s2_assets(2024, cloud_lt=80)
if not df2024.empty:
    print(f"  ✓ 2024: {len(df2024)} rows\n")

# Combine results
dfs_to_concat = [df for df in [df2022, df2023, df2024] if not df.empty]
if dfs_to_concat:
    df = pd.concat(dfs_to_concat, ignore_index=True)
else:
    print("\nWARNING: No data found for any year!")
    df = pd.DataFrame()

# Optional: keep only GeoTIFF-like assets (most of these are)
# df = df[df["media_type"].fillna("").str.contains("tiff", case=False) | df["asset_key"].isin(["B02","B03","B04","B08","visual"])]

csv_cols = [
    "year",
    "month",
    "datetime",
    "item_id",
    "cloud_cover",
    "platform",
    "tile",
    "asset_key",
    "asset_title",
    "media_type",
    "href_signed",
]

# Create output directory if it doesn't exist
output_dir = "./output"
os.makedirs(output_dir, exist_ok=True)

if df.empty:
    print("\nNo data to save. Exiting.")
else:
    # Print a compact view
    print("\n" + "="*80)
    print("Results Summary:")
    print("="*80)
    print(df[csv_cols].to_string(index=False))
    
    # Save as CSV to output folder
    output_file = os.path.join(output_dir, "sentinel2_assets_AprOct_2022_2023_2024.csv")
    df[csv_cols].to_csv(
        output_file,
        index=False, sep=","
    )
    print(f"\n✓ Wrote {len(df)} rows to: {output_file}")

