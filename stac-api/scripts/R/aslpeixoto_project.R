# --- Pacotes necessários ---
library(sf)
library(terra)
library(dplyr)
library(stringr)
library(httr)

# --- Proxy desativado para acesso STAC ---
Sys.setenv(http_proxy = "", https_proxy = "",
           no_proxy = "lab.lefolab.stac-assets.umontreal.ca,stac-assets.umontreal.ca,lefolab.stac.umontreal.ca,localhost,127.0.0.1,umontreal.ca")

# --- Caminho para MDT (como raster global) ---
mdt_path <- "/mnt/nfs/conrad/labolaliberte_upload/_data/features/projects/aslpeixoto_canopyrs/LAS_min10_quadplus_smoothed.tif"
mdt_rast_global <- terra::rast(mdt_path)

# --- Datas que devem passar pela correção DSM - MDT ---
datas_corrigir <- as.Date(c(
  "2018-09-18", "2018-10-24", "2019-01-28", "2019-04-05", "2019-05-28",
  "2019-06-29", "2019-07-15", "2019-08-17", "2019-08-29", "2019-10-21",
  "2019-11-30", "2019-12-15", "2020-01-30", "2020-02-19", "2020-03-31",
  "2020-04-16", "2020-06-16", "2020-07-29", "2020-09-29", "2020-10-26",
  "2021-01-19", "2021-03-31", "2021-05-18", "2021-07-23", "2021-08-31", "2022-01-26"
))

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

# --- 5. Função principal de extração por data ---
extract_all_pixel_values <- function(date_stac) {
  date_stac <- as.Date(date_stac)
  message("⏳ Processando data: ", date_stac)
  
  date_filename <- unique(crown_data$date_filename[crown_data$date_stac == date_stac])
  
  shp <- shp_list[[date_filename]]
  if (is.null(shp)) {
    message("❌ Shapefile não encontrado para a data: ", date_filename)
    return(NULL)
  }
  
  if (!"canopyrs_object_id" %in% names(shp)) {
    if ("layer" %in% names(shp)) {
      shp <- shp %>% rename(canopyrs_object_id = layer)
    } else {
      stop(paste("Coluna 'canopyrs_object_id' ou 'layer' não encontrada no shapefile da data", date_filename))
    }
  }
  
  ids <- crown_data$canopyrs_object_id[crown_data$date_stac == date_stac]
  shp_sub <- shp %>% filter(canopyrs_object_id %in% ids)
  
  if (nrow(shp_sub) == 0) {
    message("❌ Nenhum polígono correspondente aos IDs para a data: ", date_stac)
    return(NULL)
  }
  
  vector_path_match <- shp_files[substr(basename(shp_files), 1, 8) == date_filename][1]
  message("🗂 Shapefile usado: ", vector_path_match)
  
  urls <- get_stac_urls(vector_path_match)
  if (is.null(urls)) {
    message("❌ URLs STAC não construídas para: ", date_filename)
    return(NULL)
  }
  
  
  message("🌐 URL ortho: ", urls$ortho)
  message("🌐 URL dsm: ", urls$dsm)
  
  # 💡 Aqui a principal mudança: usar /vsicurl/ para acesso online via GDAL virtual file system
  ortho_rast <- try(rast(paste0("/vsicurl/", urls$ortho))[[1:3]], silent = TRUE)  # usar apenas R,G,B
  dsm_rast   <- try(rast(paste0("/vsicurl/", urls$dsm)), silent = TRUE)
  
  if (inherits(ortho_rast, "try-error") || inherits(dsm_rast, "try-error")) {
    message("❌ Falha ao abrir ortho ou dsm diretamente da URL via vsicurl.")
    return(NULL)
  }
  
  dsm_rast <- try(resample(dsm_rast, ortho_rast, method = "near"), silent = TRUE)
  if (inherits(dsm_rast, "try-error")) {
    message("❌ Falha ao reamostrar o DSM.")
    return(NULL)
  }
  
  if (is.na(crs(ortho_rast))) {
    message("❌ CRS inválido no ortho.")
    return(NULL)
  }
  
  if (nlyr(ortho_rast) != 3) {
    message("❌ Esperado 3 bandas no ortho, mas encontrado: ", nlyr(ortho_rast))
    return(NULL)
  }
  
  
  # --- CORREÇÃO DSM - MDT para datas específicas ---
  if (date_stac %in% datas_corrigir) {
    message("🛠 Aplicando correção DSM - MDT para a data: ", date_stac)
    
    # Reprojetar MDT para CRS do DSM
    mdt_proj <- try(project(mdt_rast_global, crs(dsm_rast)), silent = TRUE)
    if (inherits(mdt_proj, "try-error")) {
      message("❌ Falha ao reprojetar MDT, pulando correção")
      height_rast <- dsm_rast
    } else {
      # Cortar MDT para extensão do DSM
      mdt_crop <- try(crop(mdt_proj, dsm_rast, snap = "out"), silent = TRUE)
      if (inherits(mdt_crop, "try-error")) {
        message("❌ Falha ao crop MDT, pulando correção")
        height_rast <- dsm_rast
      } else {
        # Reamostrar MDT para resolução do DSM
        mdt_resamp <- try(resample(mdt_crop, dsm_rast, method = "bilinear"), silent = TRUE)
        if (inherits(mdt_resamp, "try-error")) {
          message("❌ Falha ao reamostrar MDT, pulando correção")
          height_rast <- dsm_rast
        } else {
          # Subtrair MDT do DSM para obter altura corrigida
          height_rast <- dsm_rast - mdt_resamp
        }
      }
    }
  } else {
    height_rast <- dsm_rast
  }
  
  all_rasters <- c(ortho_rast, height = height_rast)
  names(all_rasters) <- c("R", "G", "B", "height")
  
  # Transformar shapefile subset para CRS igual do raster
  shp_sub <- st_transform(shp_sub, crs = crs(ortho_rast))
  
  # Extrair valores dos rasters pelos polígonos
  extracted <- try(
    terra::extract(all_rasters, vect(shp_sub), ID = TRUE, cells = TRUE, xy = TRUE),
    silent = TRUE
  )
  
  if (inherits(extracted, "try-error") || is.null(extracted) || nrow(extracted) == 0) {
    message("❌ Extração vazia ou erro para a data: ", date_stac)
    return(NULL)
  }
  
  extracted <- extracted %>%
    rename(canopyrs_object_id = ID) %>%
    mutate(date = date_stac) %>%
    select(date, canopyrs_object_id, cell, x, y, R, G, B, height)
  
  message("✅ Extração OK: ", nrow(extracted), " pixels")
  return(extracted)
}

# --- (Opcional) Loop para processamento em lote ---
valid_dates <- unique(crown_data$date_stac[!is.na(crown_data$canopyrs_object_id)])
result_all <- lapply(valid_dates, extract_all_pixel_values)
result_df <- bind_rows(result_all)


# --- 7. Exportação opcional ---
write.csv(result_df, "/data/aslpeixoto/pixel_values_all_dtm.csv", row.names = FALSE)

