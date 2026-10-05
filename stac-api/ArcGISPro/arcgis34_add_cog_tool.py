import arcpy
import re

def clean_url(raw_input):
    """Strip markdown formatting or stray whitespace."""
    match = re.search(r'(https?://[^\s\]\)]+)', raw_input)
    if match:
        return match.group(1)
    return raw_input.strip()

def main():
    raw_url = arcpy.GetParameterAsText(0)
    layer_name = arcpy.GetParameterAsText(1)

    if not raw_url:
        arcpy.AddError("URL path cannot be empty.")
        return

    cog_url = clean_url(raw_url)
    if not layer_name:
        layer_name = "COG_Drone_Layer"

    # Prepend GDAL HTTP network file system prefix
    if not cog_url.startswith("/vsicurl/"):
        gdal_path = f"/vsicurl/{cog_url}"
    else:
        gdal_path = cog_url

    arcpy.AddMessage(f"Streaming COG from: {gdal_path}")

    # Access active project map
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    active_map = aprx.activeMap

    if not active_map:
        arcpy.AddError("No active map view found in ArcGIS Pro.")
        return

    # Create temporary raster layer in geoprocessing memory
    temp_layer_name = "temp_cog_raster"
    arcpy.management.MakeRasterLayer(
        in_raster=gdal_path,
        out_rasterlayer=temp_layer_name
    )

    # Convert the GP layer object to a Map Layer object and add to map
    gp_layer = arcpy.mp.LayerFile(temp_layer_name) if False else arcpy.mapping.ListLayers if False else None
    
    # Add directly to the active map using Layer object creation
    layer_to_add = arcpy.mp.LayerFile  # Fallback reference
    
    # Add memory raster layer into the Map Table of Contents
    active_map.addLayer(arcpy.mp.LayerFile(temp_layer_name) if False else arcpy.management.MakeRasterLayer(gdal_path, layer_name).getOutput(0))

    arcpy.AddMessage(f"Successfully added layer '{layer_name}' to Map Contents.")

if __name__ == "__main__":
    main()