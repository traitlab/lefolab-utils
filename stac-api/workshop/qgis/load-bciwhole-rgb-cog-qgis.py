import re
import os
from pystac_client import Client
from qgis.core import QgsRasterLayer, QgsProject, QgsDateTimeRange
from PyQt5.QtCore import QDateTime

# 1. API Configuration
STAC_API_URL = "https://kanopia.org/stac-fastapi-pgstac/api/v1/pgstac/"
COLLECTION_ID = "2024_bci"

# 2. Regex for filtering
pattern = re.compile(r"(\d{8})_bciwhole_.*rgb\.cog\.tif")

def load_dead_tree_series():
    client = Client.open(STAC_API_URL)
    search = client.search(collections=[COLLECTION_ID], max_items=100)
    
    # Version 0.3.2 legacy check
    item_collection = search.get_all_items()
    items = item_collection.features if hasattr(item_collection, 'features') else item_collection
    
    temp_list = []
    for item in items:
        assets = item.assets if hasattr(item, 'assets') else item.get('assets', {})
        for key, val in assets.items():
            href = val.href if hasattr(val, 'href') else val.get('href', '')
            
            match = pattern.search(href)
            if match and "request-access" not in href:
                date_str = match.group(1)
                file_name = os.path.basename(href)
                
                y, m, d = date_str[:4], date_str[4:6], date_str[6:8]
                dt = QDateTime.fromString(f"{y}-{m}-{d}T12:00:00", "yyyy-MM-ddThh:mm:ss")
                
                temp_list.append({
                    'date_int': int(date_str),
                    'qdate': dt,
                    'href': href,
                    'display_name': file_name
                })

    # SORTING: reverse=True so oldest ends up at the TOP of the Layers panel
    temp_list.sort(key=lambda x: x['date_int'], reverse=False)

    root = QgsProject.instance().layerTreeRoot()
    group_name = "Dead_Tree_Evolution_80pct"
    group = root.findGroup(group_name) or root.addGroup(group_name)

    print(f"Adding {len(temp_list)} COGs with 80% opacity...")

    for asset in temp_list:
        vsi_url = f"/vsicurl/{asset['href']}"
        layer = QgsRasterLayer(vsi_url, asset['display_name'], "gdal")
        
        if layer.isValid():
            # 1. Set Opacity to 80% (0.8)
            layer.setOpacity(0.8)
            
            # 2. Enable Temporal Properties
            t_props = layer.temporalProperties()
            t_props.setIsActive(True)
            time_range = QgsDateTimeRange(asset['qdate'], asset['qdate'])
            t_props.setFixedTemporalRange(time_range)
            
            # 3. Add to project and group
            QgsProject.instance().addMapLayer(layer, False)
            group.addLayer(layer)
            print(f"Loaded: {asset['display_name']}")

    # 4. Collapse the group to keep the UI clean
    group.setExpanded(False)
    
    print(f"--- Finished! Group '{group_name}' is collapsed and ready. ---")

# Run
load_dead_tree_series()