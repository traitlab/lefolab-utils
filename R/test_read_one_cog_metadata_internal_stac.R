# Désactive les proxies
Sys.setenv(http_proxy = "", https_proxy = "", no_proxy = "lab.lefolab.stac-assets.umontreal.ca,stac-assets.umontreal.ca,lefolab.stac.umontreal.ca,localhost,127.0.0.1,umontreal.ca")

# Load common STAC utility functions
source("lefolab_common_stac_utils.R")
library(httr)
library(terra)

cog_url <- "http://www.lab.lefolab.stac-assets.umontreal.ca:8888/assets/2024/20240902_sblz1z2_p1/20240902_sblz1z2_p1_rgb.cog.tif"

res <- HEAD(cog_url)
status_code(res)
headers(res)

# Open the COG using terra (note: terra supports remote access via GDAL)
r <- rast(paste0("/vsicurl/", cog_url))

# Print basic metadata
print(r)

# Access and display individual metadata components
cat("CRS:\n"); print(crs(r))
cat("Extent:\n"); print(ext(r))
cat("Resolution (x, y):\n"); print(res(r))
cat("Number of bands:\n"); print(nlyr(r))
cat("Band names:\n"); print(names(r))
