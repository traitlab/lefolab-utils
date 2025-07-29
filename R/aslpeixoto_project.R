# --- Pacotes necessários ---
library(sf)
library(terra)
library(dplyr)
library(stringr)
library(httr)

# --- Definir diretório temporário seguro para terra (ainda usado para alguns buffers internos) ---
custom_tmp <- "/data/aslpeixoto/tmp"
dir.create(custom_tmp, showWarnings = FALSE, recursive = TRUE)
Sys.setenv(TMPDIR = custom_tmp, TEMP = custom_tmp, TMP = custom_tmp)
terraOptions(tempdir = custom_tmp)

# --- Proxy desativado para acesso STAC ---
Sys.setenv(http_proxy = "", https_proxy = "",
           no_proxy = "lab.lefolab.stac-assets.umontreal.ca,stac-assets.umontreal.ca,lefolab.stac.umontreal.ca,localhost,127.0.0.1,umontreal.ca")

# --- 1. Definir caminhos e configurar crown_data ---
crown_data <- read.csv("/mnt/nfs/conrad/labolaliberte_data/features/projects/aslpeixoto_canopyrs/timeline_singlecrown_height_R_G_B.csv")
crown_data$date <- as.Date(as.character(crown_data$date), format = "%Y%m%d")
names(crown_data)[names(crown_data) == "date"] <- "date_stac"
crown_data$date_stac <- as.Date(crown_data$date_stac)
crown_data$date_filename <- format(crown_data$date_stac, "%Y%m%d")

# --- 2. Carregar shapefiles GPKG por data ---
shp_files <- list.files("/mnt/nfs/conrad/labolaliberte_data/features/projects/aslpeixoto_canopyrs", 
                        pattern = "\\.gpkg$", full.names = TRUE)
shp_list <- setNames(lapply(shp_files, st_read, quiet = TRUE), substr(basename(shp_files), 1, 8))

# --- 3. Função para montar URLs COG direto pelo shapefile ---
get_stac_urls <- function(vector_file) {
  if (is.na(vector_file) || length(vector_file) == 0 || !file.exists(vector_file)) return(NULL)
  file_base <- basename(vector_file)
  
  name_match <- str_extract(file_base, "^\\d{8}_[^_]+(?:_[^_]+)?")
  if (is.na(name_match)) return(NULL)
  
  year_str <- substr(name_match, 1, 4)
  folder <- name_match
  
  ortho_file <- paste0(folder, "_rgb.cog.tif")
  dsm_file   <- paste0(folder, "_dsm.cog.tif")
  
  list(
    dsm   = paste0("http://www.lab.lefolab.stac-assets.umontreal.ca:8888/assets/", year_str, "/", folder, "/", dsm_file),
    ortho = paste0("http://www.lab.lefolab.stac-assets.umontreal.ca:8888/assets/", year_str, "/", folder, "/", ortho_file)
  )
}

# --- 4. Função principal de extração por data ---
extract_all_pixel_values <- function(date_stac) {
  date_stac <- as.Date(date_stac)
  message("⏳ Processando data: ", date_stac)
  
  date_filename <- unique(crown_data$date_filename[crown_data$date_stac == date_stac])
  message("📁 date_filename: ", date_filename)
  
  shp <- shp_list[[date_filename]]
  if (is.null(shp)) {
    message("❌ Shapefile não encontrado em shp_list para a data: ", date_filename)
    return(NULL)
  }
  
  ids <- crown_data$canopyrs_object_id[crown_data$date_stac == date_stac]
  shp_sub <- shp %>% filter(canopyrs_object_id %in% ids)
  
  if (nrow(shp_sub) == 0) {
    message("❌ Nenhum polígono correspondente aos IDs para a data: ", date_stac)
    return(NULL)
  }
  
  vector_path_match <- shp_files[substr(basename(shp_files), 1, 8) == date_filename][1]
  message("🗂 vector_path_match: ", vector_path_match)
  
  if (is.na(vector_path_match) || !file.exists(vector_path_match)) {
    message("❌ Caminho do shapefile inválido para a data: ", date_filename)
    return(NULL)
  }
  
  urls <- get_stac_urls(vector_path_match)
  if (is.null(urls)) {
    message("❌ Não foi possível montar as URLs para: ", date_filename)
    return(NULL)
  }
  
  message("🌐 URL ortho: ", urls$ortho)
  message("🌐 URL dsm: ", urls$dsm)
  
  ortho_rast <- try(rast(urls$ortho)[[1:3]], silent = TRUE)  # usa apenas as 3 primeiras bandas
  dsm_rast   <- try(rast(urls$dsm), silent = TRUE)
  
  if (inherits(ortho_rast, "try-error") || inherits(dsm_rast, "try-error")) {
    message("❌ Falha ao abrir ortho ou dsm para: ", date_stac)
    return(NULL)
  }
  
  dsm_rast <- try(resample(dsm_rast, ortho_rast, method = "near"), silent = TRUE)
  if (inherits(dsm_rast, "try-error")) {
    message("❌ Falha ao reamostrar o DSM para coincidir com o ortho.")
    return(NULL)
  }
  
  if (is.na(crs(ortho_rast))) {
    message("❌ CRS inválido no ortho para: ", date_stac)
    return(NULL)
  }
  
  if (nlyr(ortho_rast) == 3) {
    names(ortho_rast) <- c("R", "G", "B")
  } else {
    message("❌ Esperado 3 bandas no ortho, mas encontrado: ", nlyr(ortho_rast))
    return(NULL)
  }
  
  all_rasters <- c(ortho_rast, height = dsm_rast)
  names(all_rasters) <- c("R", "G", "B", "height")
  
  shp_sub <- st_transform(shp_sub, crs = crs(ortho_rast))
  shp_sub$ID <- shp_sub$canopyrs_object_id
  
  raster_bbox <- st_as_sfc(st_bbox(ext(ortho_rast)))
  st_crs(raster_bbox) <- crs(ortho_rast)
  
  intersects <- st_intersects(st_geometry(shp_sub), raster_bbox, sparse = FALSE)
  if (!any(intersects)) {
    message("❌ Nenhuma interseção entre os polígonos e o raster na data: ", date_stac)
    return(NULL)
  }
  
  extracted <- try(
    terra::extract(all_rasters, vect(shp_sub), ID = TRUE, cells = TRUE, xy = TRUE),
    silent = TRUE
  )
  
  if (inherits(extracted, "try-error") || is.null(extracted) || nrow(extracted) == 0) {
    message("❌ Falha ou extração vazia para a data: ", date_stac)
    return(NULL)
  }
  
  message("✅ Extração realizada: ", nrow(extracted), " pixels")
  
  extracted <- extracted %>%
    rename(canopyrs_object_id = ID) %>%
    mutate(date = date_stac) %>%
    select(date, canopyrs_object_id, cell, x, y, R, G, B, height)
  
  return(extracted)
}
