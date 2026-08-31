import os
import csv

# Path to the input directory containing plot folders
output_base_dir = "3DFin/"
output_summary_file = "tree_counts_summary_plots.csv"

# Prepare results storage
results = []

# Iterate through each test folder
for folder in os.listdir(output_base_dir):
    folder_path = os.path.join(output_base_dir, folder)

    # Ensure it's a directory
    if not os.path.isdir(folder_path):
        continue

    # Initialize counts and statistics
    total_trees = 0
    trees_with_dbh = 0
    min_dbh = float("inf")
    max_dbh = float("-inf")
    min_height = float("inf")
    max_height = float("-inf")
    file_found = False  # Flag to check if the file exists

    # Find the dbh_and_heights file inside the folder
    for file in os.listdir(folder_path):
        if file.endswith("_dbh_and_heights.txt"):
            file_path = os.path.join(folder_path, file)
            file_found = True  # File exists

            # Process file
            with open(file_path, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 2:
                        continue  # Skip malformed lines

                    try:
                        height = float(parts[0])  # First column is tree height
                        dbh = float(parts[1])  # Second column is DBH

                        total_trees += 1
                        if dbh > 0:
                            trees_with_dbh += 1
                            min_dbh = min(min_dbh, dbh)
                            max_dbh = max(max_dbh, dbh)

                        min_height = min(min_height, height)
                        max_height = max(max_height, height)
                    
                    except ValueError:
                        continue  # Skip lines with invalid data

            print(f"Processed {file} in {folder}: {total_trees} trees, {trees_with_dbh} with DBH")
            break  # Stop searching if the file is found

    # Handle cases with no trees or missing files
    if not file_found:
        print(f"No dbh_and_heights.txt file found in {folder}, setting counts to 0.")
        total_trees = 0
        trees_with_dbh = 0

    percentage_with_dbh = round((trees_with_dbh / total_trees * 100) if total_trees > 0 else 0)

    # Handle min/max values when no DBH or height data is found
    min_dbh = round(min_dbh, 3) if min_dbh != float("inf") else 0
    max_dbh = round(max_dbh, 3) if max_dbh != float("-inf") else 0
    min_height = round(min_height, 2) if min_height != float("inf") else 0
    max_height = round(max_height, 2) if max_height != float("-inf") else 0

    results.append([folder, total_trees, trees_with_dbh, percentage_with_dbh, min_dbh, max_dbh, min_height, max_height])

# Save results to CSV
with open(output_summary_file, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Plots", "Total Trees", "Trees with DBH", "Percentage with DBH", "Min DBH", "Max DBH", "Min Height", "Max Height"])
    writer.writerows(results)

print(f"Summary saved to {output_summary_file}")
