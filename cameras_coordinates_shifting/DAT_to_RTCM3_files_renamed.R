# 1. Define the folder containing the .DAT files
folder_path <- "path/to/your/folder"  # Replace with the actual folder path

# 2. List all .DAT files in the folder
dat_files <- list.files(path = folder_path, pattern = "\\.DAT$", full.names = TRUE)

# 3. Generate new file names with the .RTCM3 extension
new_file_names <- sub("\\.DAT$", ".RTCM3", dat_files)  # Replace ".DAT" with ".RTCM3"

# 4. Rename the files
rename_success <- file.rename(from = dat_files, to = new_file_names)

# 5. Print a message about the results
if (all(rename_success)) {
  cat("All files successfully renamed to .RTCM3\n")
} else {
  failed_files <- dat_files[!rename_success]
  cat("Failed to rename the following files:\n")
  print(failed_files)
}