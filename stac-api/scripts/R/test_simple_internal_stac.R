# Désactive les proxies
Sys.setenv(http_proxy = "", https_proxy = "")

# Load common STAC utility functions
source("lefolab_common_stac_utils.R")

# URL de l'API STAC et paramètres
stac_api_url <- default_stac_api_url
limit <- 10

# Use shared search_collections for a simple search
missions <- search_collections(
  stac_api_url = stac_api_url,
  limit = limit
)

print(missions)