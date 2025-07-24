# Common STAC utility functions for test scripts

library(rstac)
library(stringr)
library(purrr)

# Search STAC collections with flexible parameters
default_bbox <- c(-79.76259, 45.00495, -57.10592, 62.58502)
default_limit <- 200

default_stac_api_url <- "http://www.lab.lefolab.stac.umontreal.ca/stac-fastapi-pgstac/api/v1/pgstac/#/"

search_collections <- function(
  stac_api_url = default_stac_api_url,
  bbox = default_bbox,
  datetime_range = NULL,
  keyword = NULL,
  limit = default_limit
) {
  s <- stac(stac_api_url)
  search_args <- list(bbox = bbox, limit = limit)
  if (!is.null(datetime_range)) search_args$datetime <- datetime_range
  res <- do.call(stac_search, c(list(s), search_args)) %>% post_request()
  features <- res$features
  if (is.null(features)) return(list())
  if (!is.null(keyword)) {
    filtered <- keep(features, function(feature) {
      collection_name <- tolower(feature$collection)
      str_detect(collection_name, keyword)
    })
    return(filtered)
  }
  return(features)
}

# Print COG asset URLs from collections
print_cog_assets <- function(collections) {
  for (collection in collections) {
    assets <- collection$assets
    if (is.null(assets)) next
    walk(names(assets), function(asset_key) {
      asset_info <- assets[[asset_key]]
      asset_href <- asset_info$href
      mime_type <- tolower(asset_info$type %||% "")
      if (
        (str_detect(mime_type, "cloud-optimized") || str_detect(asset_key, "cog")) &&
        !str_detect(asset_key, "lowres") &&
        !str_detect(asset_key, "overview")
      ) {
        cat(asset_href, "\n")
      }
    })
  }
}

# Read COG metadata using terra (optional, only if terra is available)
read_cog_metadata <- function(collections) {
  if (!requireNamespace("terra", quietly = TRUE)) {
    stop("terra package is required for reading COG metadata.")
  }
  for (collection in collections) {
    assets <- collection$assets
    if (is.null(assets)) next
    for (asset_key in names(assets)) {
      asset_info <- assets[[asset_key]]
      asset_href <- asset_info$href
      mime_type <- tolower(asset_info$type %||% "")
      if (
        (str_detect(mime_type, "cloud-optimized") || str_detect(asset_key, "cog")) &&
        !str_detect(asset_key, "lowres") &&
        !str_detect(asset_key, "overview")
      ) {
        vsi_url <- paste0("/vsicurl/", asset_href)
        cat("\n🔍 Reading metadata for:", vsi_url, "\n")
        tryCatch({
          r <- terra::rast(vsi_url)
          print(r)
        }, error = function(e) {
          cat("❌ Failed to read:", vsi_url, "\nReason:", e$message, "\n")
        })
      }
    }
  }
} 