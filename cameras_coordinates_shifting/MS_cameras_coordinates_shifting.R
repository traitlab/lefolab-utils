MS_cameras_coordinates_shifting <- function(file_path, 
                                            output_path,        # Path for the output file
                                            sep = ",",          # Optional, default to comma
                                            old_base_position,  # Vector c(x, y, z) of old base position 
                                            new_base_position,  # Vector c(x, y, z) of new base position  
                                            input_crs = 4326,   # Input CRS, default to EPSG 4326 for WGS84
                                            projected_crs       # Projected CRS
                                            ) {
  
  require(sf)
  
  # Read the text file, skipping the metadata lines
  data <- read.table(file_path, sep = sep, header = FALSE)
  colnames(data) <- c("Label", "X", "Y", "Z")
  
  # Validate file structure
  if (class(data$Label) != "character" |
      class(data$X) != "numeric" |
      class(data$Y) != "numeric" |
      class(data$Z) != "numeric") {
    stop("Verify the input file format: X, Y, and Z must be numeric.")
  }

  # Convert data to sf object in the input CRS (WGS84)
  points_sf <- st_as_sf(data, coords = c("X", "Y"), crs = input_crs, remove = FALSE)
  
  # Project the data to the specified projected CRS
  points_projected <- st_transform(points_sf, crs = projected_crs)
  
  # Extract projected coordinates from the geometry
  coords <- st_coordinates(points_projected)
  
  # Project the base positions to the projected CRS
  old_base_projected <- st_sfc(st_point(old_base_position[1:2]), crs = input_crs) %>% 
    st_transform(crs = projected_crs) %>% st_coordinates()
  new_base_projected <- st_sfc(st_point(new_base_position[1:2]), crs = input_crs) %>% 
    st_transform(crs = projected_crs) %>% st_coordinates()
  
  # Calculate the XY difference in the projected CRS
  xy_difference <- new_base_projected - old_base_projected
    
  # Apply the XY offset to the projected coordinates
  shifted_coords <- coords
  shifted_coords[, "X"] <- coords[, "X"] + xy_difference[1]
  shifted_coords[, "Y"] <- coords[, "Y"] + xy_difference[2]
  
  # Create a new sf object with shifted coordinates
  points_projected_shifted <- st_as_sf(
    data.frame(
      Label = points_projected$Label,
      Z_shifted = points_projected$Z + (new_base_position[3] - old_base_position[3]),
    ),
    coords = c("X_shifted", "Y_shifted"),
    crs = projected_crs
  )
    
  # Reproject back to WGS84 (EPSG:4326)
  points_shifted_WGS84 <- st_transform(points_projected_shifted, crs = 4326)
  
  # Prepare the output table
  output_data <- data.frame(
    Label = points_shifted_WGS84$Label,
    X_shifted = st_coordinates(points_shifted_WGS84)[, "X"],
    Y_shifted = st_coordinates(points_shifted_WGS84)[, "Y"],
    Z_shifted = points_shifted_WGS84$Z_shifted
  )
  
  # Write the corrected data to a new file
  write.table(output_data, output_path, sep = sep, row.names = FALSE, quote = FALSE)
  
  return(output_path)
  }

# # Example usage
# # Define file paths and base positions
# file_path <- "reference_exported_from_MS.txt"
# output_path <- "shifted_coordinates_to_MS.txt"
# old_base_position = c(-79.855842824, 9.128305469, 53.989)
# new_base_position = c(-79.85587214, 9.12827812, 43.124)
# 
# # Call the function
# MS_cameras_coordinates_shifting(file_path, 
#                                 output_path,
#                                 sep = ",",
#                                 old_base_position,
#                                 new_base_position,
#                                 input_crs = 4326,      # WGS84
#                                 projected_crs = 32617) # UTM Zone 17N