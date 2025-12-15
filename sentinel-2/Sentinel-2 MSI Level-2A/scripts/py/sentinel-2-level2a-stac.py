# pip install pystac-client planetary-computer pyproj pandas

from pystac_client import Client
import planetary_computer as pc
from pyproj import Transformer
import pandas as pd
import os

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

catalog = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")

def list_s2_assets(year: int, cloud_lt: int = 80, limit: int = 200):
    # Exclude winter: Apr–Oct
    dt = f"{year}-04-01/{year}-10-31"
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox_wgs84,
        datetime=dt,
        query={"eo:cloud_cover": {"lt": cloud_lt}},
        limit=limit,
    )

    rows = []
    for item in search.items():
        props = item.properties
        signed = pc.sign(item)

        for key in ["B02", "B03", "B04", "B08", "visual"]:
            if key not in signed.assets:
                continue
            a = signed.assets[key]

            rows.append({
                "year": year,
                "datetime": props.get("datetime"),
                "cloud_cover": props.get("eo:cloud_cover"),
                "tile": props.get("s2:mgrs_tile"),
                "item_id": item.id,
                "asset_key": key,
                "href_signed": a.href,  # signed URL (expires)

                # optional extras (keep if you want them in the CSV)
                "platform": props.get("platform"),
                "asset_title": getattr(a, "title", None),
                "media_type": a.media_type,
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Extract processing baseline from item_id: ..._N0510_...
    df["processing"] = (
        df["item_id"].astype(str)
        .str.extract(r"_N(\d{4})_", expand=False)
        .fillna(-1)
        .astype(int)
    )

    # Best first: lowest cloud, then newest processing baseline
    df = df.sort_values(
        by=["cloud_cover", "processing", "datetime", "asset_key"],
        ascending=[True, False, True, True],
        kind="mergesort",  # stable sort (nice when ties)
    )

    # Keep best candidate for each scene/tile/band
    df = df.drop_duplicates(
        subset=["year", "datetime", "tile", "asset_key"],
        keep="first"
    )

    # If you don't want this column in output:
    df = df.drop(columns=["processing"])

    # Optional: enforce exact output column order
    csv_cols = [
        "year", "datetime", "item_id", "cloud_cover", "platform",
        "tile", "asset_key", "asset_title", "media_type", "href_signed"
    ]
    df = df[csv_cols]

    return df

df2022 = list_s2_assets(2022, cloud_lt=80)
df2023 = list_s2_assets(2023, cloud_lt=80)
df2024 = list_s2_assets(2024, cloud_lt=80)

df = pd.concat([df2022, df2023, df2024], ignore_index=True)

# Optional: keep only GeoTIFF-like assets (most of these are)
# df = df[df["media_type"].fillna("").str.contains("tiff", case=False) | df["asset_key"].isin(["B02","B03","B04","B08","visual"])]

csv_cols = [
    "year",
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

# Print a compact view
print(df[csv_cols].to_string(index=False))

# Save as CSV to output folder
output_file = os.path.join(output_dir, "sentinel2_assets_AprOct_2022_2023_2024.csv")
df[csv_cols].to_csv(
    output_file,
    index=False, sep=","
)
print(f"\nWrote: {output_file}")

