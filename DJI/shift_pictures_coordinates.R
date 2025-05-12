shift_pictures_coordinates <- function(input_folder,
                          old_base_position,  # Vector c(lat, lon, ellips height) of old base position 
                          new_base_position,  # Vector c(lat, lon, ellips height) of new base position  
                          input_crs = 4326,   # Input CRS, default to EPSG 4326 for WGS84
                          projected_crs,      # Projected CRS
                          withzoom            # TRUE for wide+zoom pictures pair, FALSE for standalone pictures (mapping pictures for instance)
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
  log_file <- file.path(output_folder, "processing_log.txt")
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

  # Determine files to process
  wide_files <- if (withzoom) {
    image_files[!grepl("zoom", basename(image_files), ignore.case = TRUE)]
  } else {
    image_files
  }
  
  if (length(wide_files) == 0) {
  stop("No image files found in the input folder.")
  }
  
  # Project the base positions to the projected CRS
  old_base_projected <- st_sfc(st_point(c(old_base_position["lon"], old_base_position["lat"])), crs = input_crs) %>% 
  st_transform(crs = projected_crs) %>% st_coordinates()
  new_base_projected <- st_sfc(st_point(c(new_base_position["lon"], new_base_position["lat"])), crs = input_crs) %>% 
  st_transform(crs = projected_crs) %>% st_coordinates()
  
  # Calculate the XY difference in the projected CRS
  xy_difference <- new_base_projected - old_base_projected
  
  # Initialize progress bar
  total_files <- length(wide_files)
  pb <- txtProgressBar(min = 0, max = total_files, style = 3)

  # Process each image
  for (i in seq_along(wide_files)) {
    wide_file <- wide_files[i]
    
    # Update progress bar
    setTxtProgressBar(pb, i)
  
    pair_files <- wide_file  # Default to single file
    
    if (withzoom) {
      # Extract the polygon id from image file
      polygon_id <- gsub(".*_(\\d+)\\..*", "\\1", basename(wide_file))
      
      # Construct the pattern to match the corresponding "zoom" file
      identifier_match <- paste0("_", polygon_id, "zoom.JPG$")
      
      # Search for the "zoom" file in the same folder
      zoom_file <- list.files(dirname(wide_file), pattern = identifier_match, full.names = TRUE, ignore.case = TRUE)
      
      # Check if the "zoom" file exists
      if (length(zoom_file) == 0) {
        warning(paste("Skipping", basename(wide_file), "- no corresponding zoom file found."))
        error_count <- error_count + 1
        next
      }

      pair_files <- c(wide_file, zoom_file)
    }
    
    # Read EXIF metadata
    exif_data <- exif_read(wide_file)
    
    # Check if GPS data exists
    if (is.na(exif_data$GPSLongitude) || is.na(exif_data$GPSLatitude)) {
      warning(paste("Skipping", basename(wide_file), "- no GPS XY data found."))
      error_count <- error_count + 1
      next
    }
    
    # Extract GPS coordinates
    gps_coords <- c(exif_data$GPSLongitude, exif_data$GPSLatitude)
    
    # Check if altitude data exists
    if (is.na(exif_data$GPSAltitude) || is.na(exif_data$AbsoluteAltitude)) {
      warning(paste("Skipping", basename(wide_file), "- no GPS altitude data found."))
      error_count <- error_count + 1
      next
    }
    
    # Extract altitude and convert AbsoluteAltitude to numeric if needed
    gps_altitude <- exif_data$GPSAltitude
    
    if (is.numeric(exif_data$AbsoluteAltitude)) {
      absolute_altitude <- exif_data$AbsoluteAltitude
    } else {
      absolute_altitude <- as.numeric(gsub("\\+", "", exif_data$AbsoluteAltitude))
    }

    # Convert GPS coordinates to sf object
    point_sf <- st_sfc(st_point(gps_coords), crs = input_crs)
    
    # Project to the specified CRS
    point_projected <- st_transform(point_sf, crs = projected_crs) %>% st_coordinates()
    
    # Apply the XY offset and Z shift
    shifted_coords <- point_projected
    shifted_coords[1] <- point_projected[1] + xy_difference[1]
    shifted_coords[2] <- point_projected[2] + xy_difference[2]
    shifted_gps_altitude <- gps_altitude + (new_base_position["height"] - old_base_position["height"])
    shifted_absolute_altitude <- absolute_altitude + (new_base_position["height"] - old_base_position["height"])
    
    # Format the updated AbsoluteAltitude back to a string with the correct sign if needed
    if (is.character(exif_data$AbsoluteAltitude)) {
      shifted_absolute_altitude <- sprintf("+%.3f", shifted_absolute_altitude)
    }
    
    # Convert back to WGS84
    shifted_point <- st_sfc(st_point(shifted_coords), crs = projected_crs) %>% 
      st_transform(crs = input_crs) %>% st_coordinates()
    
    # Copy files to output folder
    output_files <- file.path(output_folder, basename(pair_files))
    file.copy(pair_files, output_files, overwrite = TRUE)
  
    # Update EXIF metadata using exiftoolr with error handling
    tryCatch({
      exif_call(
        args = c(
          "-overwrite_original",
          paste0("-GPSLongitude=", shifted_point[1]),
          paste0("-GPSLatitude=", shifted_point[2]),
          paste0("-GPSAltitude=", shifted_gps_altitude),
          paste0("-AbsoluteAltitude=", shifted_absolute_altitude)
        ),
        path = output_files
      )
      success_count <- success_count + 1
      cat(sprintf("Successfully updated EXIF metadata for: %s | Before: (%.8f, %.8f, %.3f) | After: (%.8f, %.8f, %.3f)\n", 
                  paste(basename(output_files), collapse = ", "),
                  gps_coords[1], gps_coords[2], gps_altitude,
                  shifted_point[1], shifted_point[2], shifted_gps_altitude), 
          file = log_file, append = TRUE)
    }, error = function(e) {
      warning(paste("Failed to update EXIF metadata for", paste(basename(output_files), collapse = ", "), ":", e$message))
      error_count <- error_count + 1
    })
  }
  
  close(pb)
  cat(sprintf("Processing complete: %d successful, %d failed", success_count, error_count))
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
#   "/path/to/input/folder3",
# )
# 
# # Loop through each folder and process
# for (folder in input_folders) {
#   message(paste("Processing folder:", folder))
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
