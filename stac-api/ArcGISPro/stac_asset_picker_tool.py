import json
import urllib.request
import urllib.parse
import os
import arcpy

# STAC Catalog Endpoints
STAC_CATALOGS = {
    "LEFO STAC LAB": "http://www.lab.lefolab.stac.umontreal.ca/stac-fastapi-pgstac/api/v1/pgstac",
    "Kanopia RPP LAB": "https://lab.kanopia.org/stac-fastapi-pgstac/api/v1/pgstac"
}

def create_auth_header(username, password):
    if username and password:
        import base64
        auth_str = f"{username}:{password}"
        encoded_auth = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
        return {'Authorization': f'Basic {encoded_auth}'}
    return {}

def fetch_json(url, headers=None):
    req_headers = {'User-Agent': 'ArcGISPro/3.4'}
    if headers:
        req_headers.update(headers)
    try:
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        arcpy.AddWarning(f"Failed to query STAC endpoint {url}: {e}")
        return {}

def test_asset_accessibility(url, headers=None):
    """Checks accessibility using a range request (byte 0-10)."""
    req_headers = {'User-Agent': 'ArcGISPro/3.4', 'Range': 'bytes=0-10'}
    if headers:
        req_headers.update(headers)
    try:
        req = urllib.request.Request(url, headers=req_headers, method='GET')
        with urllib.request.urlopen(req, timeout=8) as response:
            return True, response.status
    except urllib.error.HTTPError as e:
        return False, e.code
    except Exception as e:
        return False, str(e)

def normalize_fallback_url(url):
    """Maps kanopia share/request-access URLs cleanly to the storage server."""
    if "kanopia.org" in url:
        if "/request-access/assets/" in url:
            subpath = url.split("/request-access/assets/")[1]
        elif "/share/" in url:
            subpath = url.split("/share/")[1]
        else:
            subpath = url.split("kanopia.org/")[1]

        return f"http://www.lab.lefolab.stac-assets.umontreal.ca:8888/assets/{subpath.lstrip('/')}"
    return url

def main():
    stac_choice = arcpy.GetParameterAsText(0)
    collection_id = arcpy.GetParameterAsText(1)
    item_id = arcpy.GetParameterAsText(2)
    selected_asset_str = arcpy.GetParameterAsText(3)
    layer_name = arcpy.GetParameterAsText(4)
    username = arcpy.GetParameterAsText(5)
    password = arcpy.GetParameterAsText(6)

    asset_key = selected_asset_str.split(" : ")[0].strip() if " : " in selected_asset_str else selected_asset_str.strip()

    base_url = STAC_CATALOGS.get(stac_choice, stac_choice)
    if not base_url:
        arcpy.AddError(f"No valid STAC Catalog URL found for choice '{stac_choice}'.")
        return

    item_url = f"{base_url.rstrip('/')}/collections/{collection_id}/items/{item_id}"
    arcpy.AddMessage(f"Fetching STAC Item: {item_url}")

    auth_headers = create_auth_header(username, password)
    item_data = fetch_json(item_url, auth_headers)
    assets = item_data.get("assets", {})

    if asset_key not in assets:
        arcpy.AddError(f"Asset key '{asset_key}' not found in item '{item_id}'.")
        return

    target_url = assets[asset_key].get("href", "")
    if not target_url:
        arcpy.AddError(f"No valid href found for asset '{asset_key}'.")
        return

    arcpy.AddMessage(f"Original Asset URL: {target_url}")

    # Check direct accessibility
    accessible, status = test_asset_accessibility(target_url, auth_headers)

    # Silent failover to fallback URL
    if not accessible:
        fallback_url = normalize_fallback_url(target_url)
        if fallback_url != target_url:
            fb_accessible, fb_status = test_asset_accessibility(fallback_url, auth_headers)
            if fb_accessible:
                arcpy.AddMessage("Redirected request to mirror server.")
                target_url = fallback_url
            else:
                target_url = fallback_url  # Proceed anyway to let GDAL attempt stream

    if username and password:
        os.environ["GDAL_HTTP_USERPWD"] = f"{username}:{password}"
        os.environ["GDAL_HTTP_AUTH"] = "BASIC"

    if target_url.startswith("http") and not target_url.startswith("/vsicurl/"):
        gdal_path = f"/vsicurl/{target_url}"
    else:
        gdal_path = target_url

    if not layer_name:
        filename_clean = os.path.basename(target_url).replace(".cog.tif", "").replace(".tif", "")
        layer_name = f"{item_id}_{filename_clean}"

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    active_map = aprx.activeMap

    if not active_map:
        arcpy.AddError("No active map view found in ArcGIS Pro.")
        return

    arcpy.AddMessage(f"Streaming TIF asset from: {gdal_path}")

    try:
        raster_layer = arcpy.management.MakeRasterLayer(gdal_path, layer_name)
        layer_obj = raster_layer.getOutput(0)

        if layer_obj:
            active_map.addLayer(layer_obj)
            arcpy.AddMessage(f"Successfully added layer '{layer_name}' to map.")
        else:
            arcpy.AddError("MakeRasterLayer executed but did not return a valid layer object.")

    except Exception as e:
        arcpy.AddError(f"Failed to load raster layer: {e}")

if __name__ == "__main__":
    main()