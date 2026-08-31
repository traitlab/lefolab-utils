# Désactive les proxies
Sys.setenv(http_proxy = "", https_proxy = "")

# Load common STAC utility functions
source("lefolab_common_stac_utils.R")
library(jsonlite)

# URL de l'API STAC et paramètres
stac_api_url <- default_stac_api_url
start_date <- "2024-09-01T00:00:00Z"
end_date <- "2024-10-01T23:59:59Z"
datetime_range <- paste0(start_date, "/", end_date)
keyword <- "sbl"
quebec_bbox <- default_bbox
limit <- default_limit

# Exécuter
collections <- search_collections(
  stac_api_url = stac_api_url,
  bbox = quebec_bbox,
  datetime_range = datetime_range,
  keyword = keyword,
  limit = limit
)
if (length(collections) > 0) {
  cat(sprintf("Found %d matching collections:\n", length(collections)))
  print_cog_assets(collections)
} else {
  cat("No collections found with the specified parameters.\n")
}
