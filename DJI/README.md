# DJI Folder Scripts

This folder contains R and Python scripts for processing DJI drone data, including file renaming, time conversion, RINEX file merging, and geotag correction. Below is a summary of each script and its purpose:

---

## DAT_to_RTCM3_files_renamed.R
Renames all `.DAT` files in a specified folder by extracting a date-time string from each filename and appending it to the new filename with a `.RTCM3` extension. This helps organize and prepare DJI raw data files from RTK base for further processing or conversion.

**Usage:**
- Set `folder_path` to the directory containing your `.DAT` files.
- Run the script in R. All `.DAT` files will be renamed accordingly.

---

## GPStime2UTCtime.py
Converts GPS time (week and milliseconds) to UTC time, accounting for leap seconds. Process a folder containing `.DAT` files from RTK base, converts all timestamps, and saves the output to a text file named with the first valid UTC timestamp found in the data.

**Usage:**
- Run `python GPStime2UTCtime.py` and enter the path to your folder.
- The script will output a processed text file with UTC times for each `.DAT` files in the folder.

---

## merge_obs_files.R
Merges multiple RINEX observations files (versions 2.10 and 3.03) into a single file. Updates the header to reflect the correct "TIME OF LAST OBS" and concatenates the data, skipping redundant headers from subsequent files.

**Usage:**
- Set `folder_path` to the directory containing your observations files.
- Set `year` to the relevant year.
- Optionally set `survey_marker` for the output filename.
- Run the script in R to generate a merged observations file.

---

## shift_pictures_coordinates.R
Shifts the geotagged coordinates of pictures based on a new base station position. Uses EXIF metadata and spatial libraries to update picture locations, supporting both wide+zoom pairs and mapping pictures. Outputs the results and a log file to a new folder inside the input directory.

**Usage:**
- Call `shift_pictures_coordinates()` with the required parameters:
  - `input_folder`: Folder containing pictures.
  - `old_base_position`, `new_base_position`: Vectors with latitude, longitude, and ellipsoid height.
  - `input_crs`, `projected_crs`: Coordinate reference systems.
  - `withzoom`: TRUE for wide+zoom pairs, FALSE for mapping pictures.
- Requires R packages: `exiftoolr`, `sf`, `tidyverse`.
- [Strawberry Perl](https://strawberryperl.com/) needs to be installed on Windows

---

For more details, see comments in each script or contact the script author.
