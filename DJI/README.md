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
Merges multiple RINEX observation files into a single file. Auto-detects the naming convention in use:

- `.<yy>O` (e.g. `.25O`) — D-RTK 2 and most receivers, RINEX 2.10 / 3.03. The year comes from the extension.
- `.OBS` — D-RTK 3, RINEX 3.05. The extension carries no year, so the date is read from the `YYYYMMDDhhmmss` block in the file name (e.g. `DRTK3_0101_20260818094419_8PHXP1600A01GG.OBS`).

Files are merged in chronological order under the header of the first file. `TIME OF FIRST OBS` and `TIME OF LAST OBS` are computed from the actual first and last epochs and inserted into the header when the receiver omitted them (the D-RTK 3 does). Each file's time span, epoch count and the gap to the previous file are printed, with warnings on overlapping epochs, unexpectedly long gaps, and observation types that differ between files.

**Usage:**
- Set `folder_path` to the directory containing your observation files (searched recursively).
- Set `year` to the relevant year.
- Optionally set `survey_marker` for the output filename.
- Run the script in R to generate a merged observations file, named `<survey_marker>.<yy>O` — the extension most PPK software expects.

Advanced settings at the top of the script. The defaults suit every normal survey — only change one when something specific forces your hand:

| Setting | Default | Purpose |
| --- | --- | --- |
| `rinex_ext` | `NULL` (auto-detect) | Force a convention, `"OBS"` or e.g. `"25O"`. Required when both types sit in the same tree. |
| `output_ext` | `NULL` (`<yy>O`) | Override the output extension. |
| `filter_by_year` | `TRUE` | Keep only the `.OBS` files whose file name stamp matches `year`. |
| `write_time_of_obs` | `TRUE` | Set to `FALSE` to leave the header exactly as the receiver wrote it. |
| `time_system` | `"GPS"` | Time system written in the two `TIME OF ... OBS` lines. |
| `gap_warning_secs` | `600` | Gap above which consecutive files raise a warning. |

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

## clean_missing_tag_photos.py
Cleans timestamp files before PPK processing by removing photos without valid GPS tags. Scans all subfolders within a DJI mission directory, identifies lines in timestamp `.MRK` files containing `-259200.000000` (indicating missing GPS data), removes those lines, and deletes the corresponding photo files.

**Usage:**
- Run `python clean_missing_tag_photos.py` and enter the path to your DJI mission directory.
- The script will scan all subfolders for timestamp files and photos.
- Review the summary of actions (lines to remove and images to delete).
- Confirm to proceed. Backups of timestamp files are created automatically.
- Processes all subfolders in batch with a single confirmation.

---

For more details, see comments in each script or contact the script author.
