# 1. Define the folder containing the .DAT files
folder_path <- "path/to/your/folder"  # Replace with the actual folder path

# 2. List all .DAT files in the folder
dat_files <- list.files(path = folder_path, pattern = "\\.DAT$", full.names = TRUE)

# 3. Function to extract the date-time from the filename and append it
add_datetime_to_filename <- function(file_path) {
  # Extract the original file name (without the path)
  original_name <- basename(file_path)
  
  # Extract the date-time from the filename
  datetime_pattern <- "([0-9]{12})"  # Matches the date-time in the filename
  datetime <- sub(paste0(".*_", datetime_pattern, ".*"), "\\1", original_name)
  
  # Replace the extension and append the date-time
  new_name <- sub("\\.DAT$", paste0("_", datetime, ".RTCM3"), original_name)
  
  # Return the full path of the new file name
  file.path(dirname(file_path), new_name)
}

# 4. Generate new file names with the appended date-time and .RTCM3 extension
new_filenames <- sapply(dat_files, add_datetime_to_filename)

# 5. Rename the files
rename_success <- file.rename(from = dat_files, to = new_filenames)

# 6. Print a message about the results
if (all(rename_success)) {
  cat("All files successfully renamed with the date-time and .RTCM3 extension\n")
} else {
  failed_files <- dat_files[!rename_success]
  cat("Failed to rename the following files:\n")
  print(failed_files)
}