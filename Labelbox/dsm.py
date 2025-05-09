import numpy as np
import numpy.ma as ma
import folium
import rioxarray
import matplotlib.pyplot as plt
from matplotlib import colormaps
from pyproj import Transformer
import rasterio


infile = "mdt_bcnm.tif"
da_dem = rioxarray.open_rasterio(infile).rename({'x':'longitude', 'y':'latitude'})
arr_dem = da_dem.values

clat = da_dem.latitude.values.mean()
clon = da_dem.longitude.values.mean()

mlat = da_dem.latitude.values.min()
mlon = da_dem.longitude.values.min()

xlat = da_dem.latitude.values.max()
xlon = da_dem.longitude.values.max()

print(clat, clon, mlat, mlon, xlat, xlon)

with rasterio.open(infile) as dtm:
    dtm_crs = dtm.crs

transformer = Transformer.from_crs(dtm_crs, "EPSG:4326", always_xy=True)

clon, clat = transformer.transform(clon, clat)
mlon, mlat = transformer.transform(mlon, mlat)
xlon, xlat = transformer.transform(xlon, xlat)

bounds = [[mlat, mlon], [xlat, xlon]]

def colorize(array, cmap='turbo'):
    # normed_data = (array - array.compressed().min()) / (array.compressed().max() - array.compressed().min())  
    # normed_data = (array - array.min()) / (array.max() - array.min())  
    cm = colormaps.get_cmap(cmap)

    valid_data = array.data[~array.mask]
    vmin = valid_data.min()
    vmax = valid_data.max()

    normed = np.zeros_like(array.data, dtype=np.float32)
    normed[~array.mask] = (valid_data - vmin) / (vmax - vmin)
 
    rgba = cm(normed)
    rgba[array.mask] = (0, 0, 0, 0)

    return rgba

masked = np.ma.masked_equal(arr_dem[0], da_dem.rio.nodata)
colored_data = colorize(masked, cmap='turbo')

m = folium.Map(
    location=[clat, clon],
    zoom_start=18,
    max_zoom=20,
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri"
)

folium.raster_layers.ImageOverlay(colored_data,
                                  [[mlat, mlon], [xlat, xlon]],
                                  opacity=0.7).add_to(m)

import branca
from branca.colormap import LinearColormap

vmin = masked.min()
vmax = masked.max()
# Use matplotlib colormap
terrain_cmap = colormaps.get_cmap('turbo')
colors = [terrain_cmap(i) for i in np.linspace(0, 1, 256)]
colormap = LinearColormap(colors, vmin=vmin, vmax=vmax)
colormap = colormap.to_step(n=10)  # Adjust the number of steps as needed
colormap.caption = 'Terrain elevation (meters) - Elevación del terreno (metros)'

colormap.add_to(m)

# Make the legend larger and text more readable
legend_css = """
<style>
.legend {
    line-height: 24px !important;
    font-size: 14px !important;
    background: white !important;
    padding: 16px !important;
    border-radius: 8px !important;
    box-shadow: 2px 2px 6px rgba(0,0,0,0.3) !important;
}
.legend .caption {
    font-size: 12px !important;
    font-weight: bold !important;
    margin-bottom: 8px !important;
}
</style>
"""

m.get_root().header.add_child(folium.Element(legend_css))

html_file = "quick.html"
m.save(html_file)