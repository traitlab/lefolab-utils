# 1. Define the folder containing the .24O files
folder_path <- "path/to/folder" # Replace with the actual folder path

# 2. List all .24O files in the folder and subfolders
rinex_files <- list.files(path = folder_path, pattern = "\\.24O$", full.names = TRUE, recursive = TRUE)

# 3. Read the content of the first file and extract its header
first_file_content <- readLines(rinex_files[1])  # Read the first file
header_end <- which(grepl("END OF HEADER", first_file_content))  # Locate the end of the header
header <- first_file_content[1:header_end]  # Extract the header
data <- first_file_content[-(1:header_end)]  # Extract the data

# 4. Extract `TIME OF LAST OBS` from the last file
last_file_content <- readLines(rinex_files[length(rinex_files)])  # Read the last file
last_file_header <- last_file_content[1:which(grepl("END OF HEADER", last_file_content))]  # Extract header
last_obs_line <- grep("TIME OF LAST OBS", last_file_header, value = TRUE)  # Find the `TIME OF LAST OBS` line

# 5. Replace `TIME OF LAST OBS` in the first file's header if it exists
header <- gsub(".*TIME OF LAST OBS.*", last_obs_line, header)

# 6. Read and merge the content of all files, skipping headers from all except the first
merged_content <- header  # Start with the modified header
for (file in rinex_files) {
  file_content <- readLines(file)  # Read the file
  header_end <- which(grepl("END OF HEADER", file_content))  # Locate the end of the header
  data <- file_content[-(1:header_end)]  # Remove the header lines
  merged_content <- c(merged_content, data)  # Append the non-header content
}

# 7. Write the merged content to a new .24O file
output_file <- file.path(folder_path, "merged_files.24O")  # Output file path
writeLines(merged_content, output_file)

# Confirmation message
cat("Files successfully merged into:", output_file, "\n")