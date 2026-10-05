shift_pictures_coordinates <- function(input_folder,
                          old_base_position,  # Vector c(lat, lon, ellips height) of old base position 
                          new_base_position,  # Vector c(lat, lon, ellips height) of new base position  
                          input_crs = 4326,   # Input CRS, default to EPSG 4326 for WGS84
                          projected_crs,      # Projected CRS
                          withzoom            # TRUE for wide + close-up picture sets (legacy wide+zoom, M3E/M3T wide+tele, M4E wide+med+tele), FALSE for standalone pictures (mapping pictures for instance)
                          ) {
  
  require(exiftoolr) # need to install Strawberry Perl to use this package on Windows - https://strawberryperl.com/
  require(sf)
  require(tidyverse)
  
  exif_version()

  # Initialize counters
  success_count <- 0
  error_count <- 0

  # Create 'afterppk' directory inside input_folder
  output_folder <- file.path(input_folder, "afterppk")
  if (!dir.exists(output_folder)) {
  dir.create(output_folder)
  }

  # Create a log file in the output folder
  folder_name <- basename(normalizePath(input_folder))
  log_file <- file.path(output_folder, paste0(folder_name, "_PPKshift.txt"))
  sink(log_file, append = TRUE, split = TRUE)

  # Log input parameters
  cat("Processing started\n")
  cat("Input folder: ", input_folder, "\n")
  cat("Old base position: ", paste(old_base_position, collapse = ", "), "\n")
  cat("New base position: ", paste(new_base_position, collapse = ", "), "\n")
  cat("Input CRS: ", input_crs, "\n")
  cat("Projected CRS: ", projected_crs, "\n")
  cat("With zoom: ", withzoom, "\n")

  # List all image files in the input folder
  image_files <- list.files(input_folder, pattern = "\\.(jpg|jpeg|JPG|JPEG)$", full.names = TRUE)

  # Suffixes of the close-up pictures that follow a wide picture:
  #   legacy naming: "<id>zoom"
  #   current naming: "<id>tele" (M3E/M3T) or "<id>med" + "<id>tele" (M4E),
  #   the wide picture being named "<id>wide"
  closeup_suffixes <- c("zoom", "med", "tele")
  closeup_pattern <- paste0("_(\\d+)(", paste(closeup_suffixes, collapse = "|"), ")\\.(jpg|jpeg)$")

  # A folder shot with a "med" camera (M4E) is expected to hold both a "med" and a "tele"
  # picture per wide picture; on M3E/M3T a lone "tele" picture is the normal case
  folder_has_med <- any(grepl("_(\\d+)med\\.(jpg|jpeg)$", basename(image_files), ignore.case = TRUE))

  # Determine files to process (the wide pictures carry the GPS position to shift)
  wide_files <- if (withzoom) {
    image_files[!grepl(closeup_pattern, basename(image_files), ignore.case = TRUE)]
  } else {
    image_files
  }
  
  if (length(wide_files) == 0) {
    sink()
    stop("No image files found in the input folder.")
  }
  
  # Project the base positions to the projected CRS
  old_base_projected <- st_sfc(st_point(c(old_base_position["lon"], old_base_position["lat"])), crs = input_crs) %>% 
  st_transform(crs = projected_crs) %>% st_coordinates()
  new_base_projected <- st_sfc(st_point(c(new_base_position["lon"], new_base_position["lat"])), crs = input_crs) %>% 
  st_transform(crs = projected_crs) %>% st_coordinates()
  
  # Calculate the XY difference in the projected CRS
  xy_difference <- new_base_projected - old_base_projected
  
  # Read all EXIF metadata in one batch call (much faster than per-file)
  all_exif_raw <- exif_read(wide_files, tags = c("GPSLongitude", "GPSLatitude", "GPSAltitude", "AbsoluteAltitude", "SourceFile"))
  if (nrow(all_exif_raw) == 0) {
    sink()
    stop("ExifTool could not read any files in the input folder.")
  }
  # Align to wide_files order (exif_read does not guarantee order)
  all_exif <- all_exif_raw[match(normalizePath(wide_files), normalizePath(all_exif_raw$SourceFile)), ]

  # Vectorized coordinate transform for all images at once
  # Use (0, 0) as placeholder for NA coordinates; those rows are skipped in the loop
  coords_sfc <- st_sfc(
    lapply(seq_len(nrow(all_exif)), function(i) {
      lon <- if (is.na(all_exif$GPSLongitude[i])) 0 else all_exif$GPSLongitude[i]
      lat <- if (is.na(all_exif$GPSLatitude[i]))  0 else all_exif$GPSLatitude[i]
      st_point(c(lon, lat))
    }),
    crs = input_crs
  )
  coords_projected <- st_coordinates(st_transform(coords_sfc, crs = projected_crs))
  shifted_projected <- coords_projected
  shifted_projected[, "X"] <- coords_projected[, "X"] + xy_difference[1]
  shifted_projected[, "Y"] <- coords_projected[, "Y"] + xy_difference[2]
  shifted_sfc <- st_sfc(
    lapply(seq_len(nrow(shifted_projected)), function(i) st_point(shifted_projected[i, ])),
    crs = projected_crs
  )
  shifted_wgs84 <- st_coordinates(st_transform(shifted_sfc, crs = input_crs))

  height_shift <- new_base_position["height"] - old_base_position["height"]
  abs_alt_is_char <- is.character(all_exif$AbsoluteAltitude)
  abs_alt_numeric <- if (abs_alt_is_char) {
    as.numeric(gsub("\\+", "", all_exif$AbsoluteAltitude))
  } else {
    all_exif$AbsoluteAltitude
  }

  # Initialize progress bar
  sink(NULL)
  total_files <- length(wide_files)
  pb <- txtProgressBar(min = 0, max = total_files, style = 3)
  sink(log_file, append = TRUE, split = TRUE)

  # Process each image
  for (i in seq_along(wide_files)) {
    wide_file <- wide_files[i]

    # Update progress bar
    sink(NULL)
    setTxtProgressBar(pb, i)
    sink(log_file, append = TRUE, split = TRUE)

    pair_files <- wide_file  # Default to single file

    if (withzoom) {
      # Extract the polygon id from image file (the wide picture has no suffix in the
      # legacy naming, and a "wide" suffix in the current naming)
      polygon_id <- gsub(".*_(\\d+)(wide)?\\..*", "\\1", basename(wide_file), ignore.case = TRUE)

      # Construct the pattern to match the corresponding close-up file(s): "zoom" (legacy) or "med"/"tele" (current)
      identifier_match <- paste0("_", polygon_id, "(", paste(closeup_suffixes, collapse = "|"), ")\\.(jpg|jpeg)$")

      # Search for the close-up file(s) in the same folder
      zoom_file <- list.files(dirname(wide_file), pattern = identifier_match, full.names = TRUE, ignore.case = TRUE)

      # Check if at least one close-up file exists
      if (length(zoom_file) == 0) {
        warning(paste("Skipping", basename(wide_file), "- no corresponding zoom/med/tele file found."))
        error_count <- error_count + 1
        next
      }

      # Warn on incomplete M4E sets, where both a "med" and a "tele" picture are expected
      set_has_med  <- any(grepl("med\\.(jpg|jpeg)$", basename(zoom_file), ignore.case = TRUE))
      set_has_tele <- any(grepl("tele\\.(jpg|jpeg)$", basename(zoom_file), ignore.case = TRUE))
      if (set_has_med && !set_has_tele) {
        warning(paste("Incomplete set for", basename(wide_file), "- 'med' picture found but no corresponding 'tele' picture."))
      } else if (folder_has_med && set_has_tele && !set_has_med) {
        warning(paste("Incomplete set for", basename(wide_file), "- 'tele' picture found but no corresponding 'med' picture."))
      }

      pair_files <- c(wide_file, zoom_file)
    }

    # Check if GPS data exists (using pre-read batch data)
    if (is.na(all_exif$GPSLongitude[i]) || is.na(all_exif$GPSLatitude[i])) {
      warning(paste("Skipping", basename(wide_file), "- no GPS XY data found."))
      error_count <- error_count + 1
      next
    }

    if (is.na(all_exif$GPSAltitude[i]) || is.na(all_exif$AbsoluteAltitude[i])) {
      warning(paste("Skipping", basename(wide_file), "- no GPS altitude data found."))
      error_count <- error_count + 1
      next
    }

    gps_coords        <- c(all_exif$GPSLongitude[i], all_exif$GPSLatitude[i])
    gps_altitude      <- all_exif$GPSAltitude[i]
    shifted_gps_alt   <- gps_altitude + height_shift
    shifted_abs_alt   <- abs_alt_numeric[i] + height_shift
    if (abs_alt_is_char) shifted_abs_alt <- sprintf("+%.3f", shifted_abs_alt)

    # Copy files to output folder
    output_files <- file.path(output_folder, basename(pair_files))
    file.copy(pair_files, output_files, overwrite = TRUE)

    # Update EXIF metadata using exiftoolr with error handling
    tryCatch({
      exif_call(
        args = c(
          "-overwrite_original",
          paste0("-GPSLongitude=", shifted_wgs84[i, "X"]),
          paste0("-GPSLatitude=",  shifted_wgs84[i, "Y"]),
          paste0("-GPSAltitude=",  shifted_gps_alt),
          paste0("-AbsoluteAltitude=", shifted_abs_alt)
        ),
        path = output_files
      )
      success_count <- success_count + 1
      cat(sprintf("Successfully updated EXIF metadata for: %s | Before: (%.8f, %.8f, %.3f) | After: (%.8f, %.8f, %.3f)\n",
                  paste(basename(output_files), collapse = ", "),
                  gps_coords[2], gps_coords[1], gps_altitude,
                  shifted_wgs84[i, "Y"], shifted_wgs84[i, "X"], shifted_gps_alt),
          file = log_file, append = TRUE)
    }, error = function(e) {
      warning(paste("Failed to update EXIF metadata for", paste(basename(output_files), collapse = ", "), ":", e$message))
      error_count <- error_count + 1
    })
  }

  close(pb)
  cat(sprintf("Processing complete: %d successful, %d failed\n", success_count, error_count))
  sink()
  return(paste("Output files in:", output_folder))
}

# # Example usage (uncomment this section and change parameters to run)
# # Define input folder and base positions
# input_folder <- "/path/to/input/folder"                      # path to folder containing pictures
# old_base_position <- c(lat = 0.00000000, lon = 0.00000000, height = 0.000)
# new_base_position <- c(lat = 0.00000000, lon = 0.00000000, height = 0.000)
# 
# # Call the function
# shift_pictures_coordinates(input_folder,
#                                       old_base_position,
#                                       new_base_position,
#                                       input_crs = 4326,      # WGS84
#                                       projected_crs = 32XXX, # UTM
#                                       withzoom = TRUE)       # for close-up pictures

# # Batch process --------------------
# # Define a list of input folders
# input_folders <- c(
#   "/path/to/input/folder1",
#   "/path/to/input/folder2",
#   "/path/to/input/folder3"
# )
# 
# # Loop through each folder and process
# for (folder in input_folders) {
#   tryCatch({
#     shift_pictures_coordinates(
#       input_folder = folder,
#       old_base_position = old_base_position,
#       new_base_position = new_base_position,
#       input_crs = 4326,      # WGS84
#       projected_crs = 32XXX,  # UTM
#       withzoom = TRUE)       # for close-up pictures
#
#   }, error = function(e) {
#     warning(paste("Failed to process folder:", folder, ":", e$message))
#   })
# }

# # Cleanup and move files --------------------
# # Define a list of input folders
# input_folders <- c(
#   "/path/to/input/folder1",
#   "/path/to/input/folder2",
#   "/path/to/input/folder3"
# )
# 
# for (folder in input_folders) {
#   # Recursively search for 'afterppk' folders in the current folder and subfolders
#   afterppk_folders <- list.dirs(folder, recursive = TRUE, full.names = TRUE)
#   afterppk_folders <- afterppk_folders[basename(afterppk_folders) == "afterppk"]
#   
#   for (afterppk_folder in afterppk_folders) {
#     if (dir.exists(afterppk_folder)) {
#       # List all files in the 'afterppk' folder
#       files_to_move <- list.files(afterppk_folder, full.names = TRUE)
#       
#       # Get the parent folder of 'afterppk'
#       parent_folder <- dirname(afterppk_folder)
#       
#       # Delete all pictures from the parent folder
#       pictures_to_delete <- list.files(parent_folder, pattern = "\\.(jpg|jpeg|JPG|JPEG)$", full.names = TRUE)
#       num_deleted <- length(pictures_to_delete)
#       invisible(file.remove(pictures_to_delete))
#       cat(sprintf("Deleted %d pictures from %s\n", num_deleted, parent_folder))
#       
#       # Move files from 'afterppk' folder to the parent folder
#       num_moved <- length(files_to_move)
#       invisible(file.rename(files_to_move, file.path(parent_folder, basename(files_to_move))))
#       cat(sprintf("Moved %d files from %s to %s\n", num_moved, afterppk_folder, parent_folder))
#       
#       # Delete the empty 'afterppk' folder
#       unlink(afterppk_folder, recursive = TRUE)
#     }
#   }
# }
