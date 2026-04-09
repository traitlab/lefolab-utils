import re
import os
import xml.sax.saxutils as saxutils
from osgeo import gdal
from pystac_client import Client
from qgis.core import (
    QgsRasterLayer, QgsProject, QgsDateTimeRange,
    QgsColorRampShader, QgsRasterShader, QgsSingleBandPseudoColorRenderer,
)
from PyQt5.QtCore import QDateTime
from PyQt5.QtGui import QColor

# 1. API Configuration
STAC_API_URL = "https://kanopia.org/stac-fastapi-pgstac/api/v1/pgstac/"
COLLECTION_ID = "2024_bci"

# 2. Regex for filtering RGB COGs
pattern = re.compile(r"(\d{8})_bciwhole_.*rgb\.cog\.tif")


def apply_gcc_style(layer):
    """Apply a brown→yellow→green color ramp to a GCC layer (values ~0.20–0.50)."""
    color_ramp = QgsColorRampShader()
    color_ramp.setColorRampType(QgsColorRampShader.Interpolated)
    color_ramp.setColorRampItemList([
        QgsColorRampShader.ColorRampItem(0.20, QColor('#8B2500'), '0.20 low'),
        QgsColorRampShader.ColorRampItem(0.33, QColor('#FFFF00'), '0.33 neutral'),
        QgsColorRampShader.ColorRampItem(0.50, QColor('#006400'), '0.50 high'),
    ])
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(color_ramp)
    renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
    layer.setRenderer(renderer)


def compute_gcc_vrt(vsi_url, display_name, rgb_layer):
    """
    GCC = B2/(B1+B2+B3) via 3 chained VRTs stored in /vsimem/.

    Uses only GDAL built-in pixel functions — no muparser required:
      sum_vrt : sum(B1, B2, B3)   → denominator
      inv_vrt : inv(sum_vrt)      → 1 / denominator
      gcc_vrt : mul(B2, inv_vrt)  → B2 / (B1+B2+B3) = GCC

    Pixel data is fetched and computed tile-by-tile at render time.
    """
    ref = re.sub(r'[^A-Za-z0-9_]', '_', os.path.splitext(display_name)[0])

    extent = rgb_layer.extent()
    w, h = rgb_layer.width(), rgb_layer.height()
    xres = extent.width()  / w
    yres = extent.height() / h
    crs_wkt = saxutils.escape(rgb_layer.crs().toWkt())
    geo = (f"{extent.xMinimum():.10f}, {xres:.10f}, 0, "
           f"{extent.yMaximum():.10f}, 0, {-yres:.10f}")

    def make_vrt(pixel_func, sources, desc=""):
        srcs = "".join(
            f'    <SimpleSource>\n'
            f'      <SourceFilename relativeToVRT="0">{saxutils.escape(p)}</SourceFilename>\n'
            f'      <SourceBand>{b}</SourceBand>\n'
            f'    </SimpleSource>\n'
            for p, b in sources
        )
        desc_tag = f"    <Description>{desc}</Description>\n" if desc else ""
        return (
            f'<VRTDataset rasterXSize="{w}" rasterYSize="{h}">\n'
            f'  <SRS>{crs_wkt}</SRS>\n'
            f'  <GeoTransform>{geo}</GeoTransform>\n'
            f'  <VRTRasterBand dataType="Float32" band="1" subClass="VRTDerivedRasterBand">\n'
            f'{desc_tag}'
            f'    <PixelFunctionType>{pixel_func}</PixelFunctionType>\n'
            f'{srcs}'
            f'  </VRTRasterBand>\n'
            f'</VRTDataset>'
        ).encode('utf-8')

    sum_path = f'/vsimem/sum_{ref}.vrt'
    inv_path = f'/vsimem/inv_{ref}.vrt'
    gcc_path = f'/vsimem/gcc_{ref}.vrt'

    gdal.FileFromMemBuffer(sum_path, make_vrt('sum', [(vsi_url, 1), (vsi_url, 2), (vsi_url, 3)]))
    gdal.FileFromMemBuffer(inv_path, make_vrt('inv', [(sum_path, 1)]))
    gdal.FileFromMemBuffer(gcc_path, make_vrt('mul', [(vsi_url, 2), (inv_path, 1)], desc='GCC'))

    gcc_layer = QgsRasterLayer(gcc_path, f'GCC_{display_name}', 'gdal')
    if not gcc_layer.isValid():
        print(f"  ERROR: GCC VRT invalid for {display_name}")
        for p in (sum_path, inv_path, gcc_path):
            gdal.Unlink(p)
        return None

    return gcc_layer


def load_gcc_series():
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

    temp_list.sort(key=lambda x: x['date_int'], reverse=False)

    root = QgsProject.instance().layerTreeRoot()
    group_name = "GCC_Phenology_80pct"
    group = root.findGroup(group_name) or root.addGroup(group_name)

    print(f"Building GCC VRTs for {len(temp_list)} COGs (on-the-fly, no disk write)...")

    for asset in temp_list:
        vsi_url = f"/vsicurl/{asset['href']}"
        rgb_layer = QgsRasterLayer(vsi_url, asset['display_name'], "gdal")

        if not rgb_layer.isValid():
            print(f"  SKIP (invalid RGB): {asset['display_name']}")
            continue

        gcc_layer = compute_gcc_vrt(vsi_url, asset['display_name'], rgb_layer)
        if gcc_layer is None:
            continue

        # Style: brown → yellow → green color ramp
        apply_gcc_style(gcc_layer)
        gcc_layer.setOpacity(0.8)

        # Temporal properties
        t_props = gcc_layer.temporalProperties()
        t_props.setIsActive(True)
        t_props.setFixedTemporalRange(QgsDateTimeRange(asset['qdate'], asset['qdate']))

        QgsProject.instance().addMapLayer(gcc_layer, False)
        group.addLayer(gcc_layer)
        print(f"  Loaded: GCC_{asset['display_name']}")

    group.setExpanded(False)
    print(f"--- Finished! Group '{group_name}' collapsed and ready. ---")


# Run
load_gcc_series()
