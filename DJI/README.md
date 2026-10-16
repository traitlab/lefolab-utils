# DJI Folder Scripts

This folder contains R and Python scripts for processing DJI drone data, including file renaming, time conversion, RINEX file merging, and geotag correction. Below is a summary of each script and its purpose:

---

## DAT_to_RTCM3_files_renamed.R
Renames all `.DAT` files in a specified folder by extracting a date-time string from each filename and appending it to the new filename with a `.RTCM3` extension. This helps organize and prepare DJI raw data files from RTK base for further processing or conversion.

**Usage:**
- Set `folder_path` to the directory containing your `.DAT` files.
- Run the script in R. All `.DAT` files will be renamed accordingly.

---

## convert_base_log_to_utc.py
Converts the GPS timestamps of a DJI RTK base log to UTC, accounting for leap seconds. Auto-detects which base station generation the folder holds:

- **D-RTK 2** — text `.DAT` log with one `bestpos:<week>,<ms>ms,...` line per record (e.g. `RTK235.DAT`).
- **D-RTK 3** — tab-separated `.MRK` log, `<index> <seconds of week> [<week>] ...` (e.g. `DRTK3_0100_20260818094346_XX.MRK`). Its `.dat` is binary RTCM for PPK and holds no readable timestamps, so it is skipped.

A folder of raw RTCM `.DAT` files with no `bestpos:` lines is reported rather than silently producing nothing. Output is one `<YYYYMMDD_HHMMSS>_UTC_<file number>.txt` per input file, each source line kept as-is with ` [UTC: ...]` appended.

Drone photo-event `.MRK` files share the same column layout as a D-RTK 3 base log, so pointing the script at a mission folder would otherwise convert photo timestamps without a word. It warns when a file looks like photo events — name ending in `_Timestamp.MRK`, or records carrying non-zero N/E/V antenna offsets — and converts anyway, since the timestamps are valid either way.

**Usage:**
- Run `python convert_base_log_to_utc.py` and enter the path to your folder, or pass it as an argument: `python convert_base_log_to_utc.py "E:/path/to/logs"`.
- Leap seconds are set by `LEAP_SECONDS = 18` at the top of the script (unchanged since 2017-01-01); update it if a new leap second is ever introduced.

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

## shift_pictures_coordinates.py
Shifts the geotagged coordinates of pictures by the difference between an old and a new base station position (e.g. RTK base set up on an approximate position, corrected after PPK). The XY difference is computed in a projected CRS and the ellipsoidal height difference is added to the altitude. With `--closeup`, each wide picture defines a set with its close-up pictures (legacy `zoom`, M3E/M3T `tele`, M4E `med` + `tele`), and the shifted position of the wide picture is written to all the pictures of the set. With `--no-closeup`, every picture is shifted from its own position (e.g. mapping pictures).

Only the GPS values are changed (EXIF `GPSLatitude`, `GPSLongitude`, `GPSAltitude` and XMP `drone-dji:GpsLatitude`, `GpsLongitude`, `AbsoluteAltitude`). They are written in place in the format DJI uses, so the rest of the file stays byte-identical and the pictures can still be read by tools that parse DJI's metadata, such as [closeup-ortho](https://github.com/traitlab/closeup-ortho). The log file `<folder>_PPKshift.txt` records the exact original values of every picture, so the shift can be reversed to byte-identical original pictures.

**Usage:**
- Shift the pictures of one or more folders. Each folder's shifted pictures and its log are written to `<folder>/afterppk/`:
  ```bash
  python shift_pictures_coordinates.py shift \
      --old-base 45.589184009 -75.241806593 4.088 \
      --new-base 45.58919069 -75.24180156 44.0035 \
      --projected-crs 32618 --closeup \
      /path/to/mission/flight_folder1 /path/to/mission/flight_folder2
  ```
  - `--old-base`, `--new-base`: latitude, longitude and ellipsoidal height of the old and new base positions.
  - `--input-crs` (default `4326`), `--projected-crs`: coordinate reference systems.
  - `--closeup` for wide + close-up picture sets, `--no-closeup` for standalone pictures. One of them is required.
- Replace the pictures of each folder by the shifted ones in `afterppk/` (**deletes the original pictures** of the folder):
  `python shift_pictures_coordinates.py cleanup /path/to/mission`
- Restore the original pictures into `<folder>/beforeppk/`, from the folder holding the shifted pictures and their `*_PPKshift.txt` (the flight folder after cleanup, or its `afterppk/` folder before cleanup):
  `python shift_pictures_coordinates.py reverse /path/to/mission/flight_folder`
- Shell globs work. `shift` and `reverse` only read the pictures directly in each folder, so the glob has to reach the flight folders (e.g. `.../2026/*_wpt_m4e/*/`). `cleanup` searches subfolders, so mission folders are enough.
- Requires Python package: `pyproj`. ExifTool is not needed.

---

## shift_pictures_coordinates.R
**Outdated: use `shift_pictures_coordinates.py` instead.** This script rewrites the whole XMP packet through ExifTool, which changes DJI's metadata format (closeup-ortho can no longer read the position of the shifted pictures). The close-up pictures also lose their own original position, and the log does not keep enough information to restore the original pictures.

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

## rename_wpt_ppk_files.py
Renames the PPK files (`.MRK`, `.NAV`, `.OBS`, `.RTK`) of DJI M4E waypoint missions to the name of their parent folder. The RTK filename referenced in `ppk_file_name.pbk` is updated accordingly.

**Usage:**
- Run `python rename_wpt_ppk_files.py <path> [<path> ...]` (or without argument to be prompted), where each `<path>` is a mission directory containing flight folders, or a single flight folder. Shell globs work too (e.g. `.../2026/*_wpt_m4e`).
- Review the planned renames and confirm to proceed.

---

For more details, see comments in each script or contact the script author.
