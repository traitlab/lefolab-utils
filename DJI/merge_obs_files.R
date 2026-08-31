# Merge several RINEX observation files into a single observation file.
#
# Two naming conventions are auto-detected:
#   * ".<yy>O" (e.g. ".25O") - D-RTK 2 and most receivers, RINEX 2.10 / 3.03.
#                              The year is encoded in the extension itself.
#   * ".OBS"                 - D-RTK 3, RINEX 3.05. The extension carries no
#                              year, so the date is read from the
#                              YYYYMMDDhhmmss block in the file name, e.g.
#                              DRTK3_0101_20260818094419_8PHXP1600A01GG.OBS
#
# Files are merged in chronological order under the header of the first file.
# TIME OF FIRST OBS / TIME OF LAST OBS are computed from the actual first and
# last epochs of the merged data, and inserted into the header when the receiver
# left them out (the D-RTK 3 does).

# ------------------------------------------------------------------ 1. Settings

# A Windows path can be pasted as-is inside r"( )", quotes included, which is
# what Explorer's "Copy as path" gives you:  r"("C:\LEFO\temp\logs_tbs")"
folder_path   <- r"(path\to\folder)"  # folder with the observation files
survey_marker <- ""                   # output name; "" -> "merged_obs_files"
year          <- 2026                 # year of the survey

# Advanced settings. The defaults below suit every normal survey, so leave them
# as they are unless something specific forces your hand: both file conventions
# sitting in the same folder, software that refuses the output extension, a
# receiver logging in another time system. See DJI/README.md before changing one.

rinex_ext         <- NULL   # NULL = auto-detect; force with "OBS" or e.g. "25O"
output_ext        <- NULL   # NULL = "<yy>O", the extension most PPK tools want
filter_by_year    <- TRUE   # keep only the files belonging to `year`
write_time_of_obs <- TRUE   # refresh / insert TIME OF FIRST & LAST OBS
time_system       <- "GPS"  # time system written in those two header lines
gap_warning_secs  <- 600    # warn when consecutive files are further apart

# ------------------------------------------------------------------- 2. Helpers

# An epoch line: ">" + 4-digit year (RINEX 3), or a 2-digit year (RINEX 2)
epoch_pattern <- "^\\s*>?\\s*\\d{2}(\\d{2})?\\s"

list_rinex <- function(path, ext) {
  list.files(path, pattern = paste0("\\.", ext, "$"), full.names = TRUE,
             recursive = TRUE, ignore.case = TRUE)
}

# Accept the usual ways of pasting a folder path: forward slashes, backslashes
# inside r"( )", a trailing separator, and the quotes "Copy as path" wraps it in
clean_path <- function(path) {
  path <- trimws(path)
  path <- gsub('^"|"$', "", path)                     # quotes from Copy as path
  path <- gsub("\\\\", "/", path)                     # backslash -> slash
  if (nchar(path) > 3) path <- sub("/+$", "", path)   # trailing separator
  path
}

# 14-digit YYYYMMDDhhmmss stamp found in D-RTK 3 file names, NA when absent
filename_stamp <- function(name) {
  m <- regmatches(name, regexpr("[0-9]{14}", name))
  if (length(m) == 0) NA_character_ else m
}

# Split an epoch line into its date and time fields
parse_epoch <- function(line) {
  fields <- strsplit(trimws(sub("^\\s*>", "", line)), "\\s+")[[1]]
  nums <- suppressWarnings(as.numeric(fields))
  if (length(nums) < 6 || anyNA(nums[1:6])) return(NULL)
  yy <- nums[1]
  if (yy < 100) yy <- if (yy < 80) 2000 + yy else 1900 + yy  # RINEX 2 short year
  list(year = yy, month = nums[2], day = nums[3],
       hour = nums[4], min = nums[5], sec = nums[6])
}

# POSIXct built with tz = "UTC" so the local time zone never shifts the values.
# Epochs are in GPS time, but these are only used to print and to measure gaps.
epoch_time <- function(e) {
  if (is.null(e)) return(as.POSIXct(NA))
  ISOdatetime(e$year, e$month, e$day, e$hour, e$min, e$sec, tz = "UTC")
}

format_duration <- function(secs) {
  sign <- if (secs < 0) "-" else ""
  secs <- abs(secs)
  sprintf("%s%02d:%02d:%02d", sign, secs %/% 3600,
          (secs %% 3600) %/% 60, round(secs %% 60))
}

# 80-column TIME OF FIRST/LAST OBS header line (5I6, F13.7, 5X, A3, label)
obs_time_line <- function(e, label) {
  body <- sprintf("%6d%6d%6d%6d%6d%13.7f%5s%-3s", e$year, e$month, e$day,
                  e$hour, e$min, e$sec, "", time_system)
  sprintf("%-60s%-20s", body, label)
}

# Replace a header line, or insert it just before END OF HEADER if missing
set_header_line <- function(header, label, line) {
  idx <- grep(label, header, fixed = TRUE)
  if (length(idx) > 0) {
    header[idx] <- line
    return(header)
  }
  eoh <- grep("END OF HEADER", header, fixed = TRUE)[1]
  append(header, line, after = eoh - 1)
}

# Observation type declarations, RINEX 3 and RINEX 2 spellings
obs_type_lines <- function(header) {
  grep("SYS / # / OBS TYPES|# / TYPES OF OBSERV", header, value = TRUE)
}

# Read only the header of a file, plus its first epoch line
read_header_and_first_epoch <- function(path) {
  con <- file(path, "r")
  on.exit(close(con))
  header <- character(0)
  repeat {
    line <- readLines(con, n = 1, warn = FALSE)
    if (length(line) == 0) stop("END OF HEADER not found in ", path)
    header <- c(header, line)
    if (grepl("END OF HEADER", line, fixed = TRUE)) break
  }
  first_epoch <- NA_character_
  repeat {
    line <- readLines(con, n = 1, warn = FALSE)
    if (length(line) == 0) break
    if (grepl(epoch_pattern, line)) {
      first_epoch <- line
      break
    }
  }
  list(header = header, first_epoch = first_epoch)
}

last_epoch_line <- function(path) {
  lines <- readLines(path, warn = FALSE)
  hits <- grep(epoch_pattern, lines)
  if (length(hits) == 0) NA_character_ else lines[hits[length(hits)]]
}

# ----------------------------------------------- 3. Find the observation files

folder_path <- clean_path(folder_path)
if (!dir.exists(folder_path)) stop("Folder not found: ", folder_path)

year_suffix <- sprintf("%02d", year %% 100)
legacy_ext  <- paste0(year_suffix, "O")

if (is.null(rinex_ext)) {
  legacy_files <- list_rinex(folder_path, legacy_ext)
  drtk3_files  <- list_rinex(folder_path, "OBS")

  if (length(legacy_files) > 0 && length(drtk3_files) > 0) {
    stop("Both .", legacy_ext, " and .OBS files were found in this folder.\n",
         "  Set `rinex_ext` to \"", legacy_ext, "\" or \"OBS\" to choose which ",
         "convention to merge.")
  }
  if (length(legacy_files) == 0 && length(drtk3_files) == 0) {
    stop("No .", legacy_ext, " and no .OBS file found under ", folder_path)
  }

  use_drtk3   <- length(drtk3_files) > 0
  rinex_ext   <- if (use_drtk3) "OBS" else legacy_ext
  rinex_files <- if (use_drtk3) drtk3_files else legacy_files
} else {
  use_drtk3   <- toupper(rinex_ext) == "OBS"
  rinex_files <- list_rinex(folder_path, rinex_ext)
  if (length(rinex_files) == 0) {
    stop("No .", rinex_ext, " file found under ", folder_path)
  }
}

# ------------------------------------------- 4. Filter by year, then order them

stamps     <- vapply(basename(rinex_files), filename_stamp, character(1),
                     USE.NAMES = FALSE)
stamp_time <- as.POSIXct(stamps, format = "%Y%m%d%H%M%S", tz = "UTC")

# The .OBS extension holds no year, so filtering relies on the file name stamp
if (use_drtk3 && filter_by_year) {
  undated <- is.na(stamp_time)
  if (any(undated)) {
    warning("Skipping ", sum(undated), " .OBS file(s) without a YYYYMMDDhhmmss ",
            "stamp in the name, so their year is unknown: ",
            paste(basename(rinex_files[undated]), collapse = ", "),
            "\n  Set `filter_by_year <- FALSE` to merge them anyway.")
  }
  keep        <- !undated & as.integer(format(stamp_time, "%Y")) == year
  rinex_files <- rinex_files[keep]
  stamp_time  <- stamp_time[keep]
  if (length(rinex_files) == 0) stop("No .OBS file left for year ", year)
}

if (all(!is.na(stamp_time))) {
  rinex_files <- rinex_files[order(stamp_time)]
  order_note  <- "chronological, from the file name timestamps"
} else {
  rinex_files <- sort(rinex_files)
  order_note  <- "alphabetical (no timestamp in the file names)"
}

cat("Convention : .", rinex_ext, "\n", sep = "")
cat("Files      : ", length(rinex_files), " (order: ", order_note, ")\n",
    sep = "")

# --------------------------------------------------- 5. Build the output header

first  <- read_header_and_first_epoch(rinex_files[1])
header <- first$header

if (write_time_of_obs) {
  first_epoch <- parse_epoch(first$first_epoch)
  last_epoch  <- parse_epoch(last_epoch_line(rinex_files[length(rinex_files)]))

  if (is.null(first_epoch) || is.null(last_epoch)) {
    warning("Could not read the first and/or last epoch, leaving ",
            "TIME OF FIRST/LAST OBS untouched.")
  } else {
    header <- set_header_line(header, "TIME OF FIRST OBS",
                              obs_time_line(first_epoch, "TIME OF FIRST OBS"))
    header <- set_header_line(header, "TIME OF LAST OBS",
                              obs_time_line(last_epoch, "TIME OF LAST OBS"))
  }
}

# ----------------------------------------------------- 6. Merge, streaming out

if (is.null(survey_marker) || survey_marker == "") {
  survey_marker <- "merged_obs_files"
}
if (is.null(output_ext)) output_ext <- paste0(year_suffix, "O")
output_file <- file.path(folder_path, paste0(survey_marker, ".", output_ext))

reference_types <- obs_type_lines(header)
previous_end    <- as.POSIXct(NA)
epochs_written  <- 0

# Written file by file instead of growing one vector: `c(merged, data)` copies
# the whole accumulated file on every iteration, so a long merge costs quadratic
# time and holds about twice the merged file in memory. Here the peak is one
# input file.
out <- file(output_file, "w")
tryCatch({
  writeLines(header, out)

  for (path in rinex_files) {
    file_content <- readLines(path, warn = FALSE)
    header_end <- which(grepl("END OF HEADER", file_content, fixed = TRUE))
    if (length(header_end) == 0) {
      warning("No END OF HEADER in ", path, ", file skipped")
      next
    }
    file_header <- file_content[1:header_end[1]]
    data_lines  <- file_content[-(1:header_end[1])]

    # Concatenating data under a header that declares different observation
    # types would silently misalign the columns
    if (!identical(obs_type_lines(file_header), reference_types)) {
      warning("Observation types in ", basename(path), " differ from the first ",
              "file: the merged columns may not line up.")
    }

    epoch_rows <- grep(epoch_pattern, data_lines)
    if (length(epoch_rows) == 0) {
      warning("No valid epoch line found in ", path)
      next
    }
    writeLines(data_lines[epoch_rows[1]:length(data_lines)], out)
    epochs_written <- epochs_written + length(epoch_rows)

    start_time <- epoch_time(parse_epoch(data_lines[epoch_rows[1]]))
    end_time   <- epoch_time(parse_epoch(data_lines[epoch_rows[length(epoch_rows)]]))

    gap_text <- ""
    if (!is.na(previous_end) && !is.na(start_time)) {
      gap <- as.numeric(difftime(start_time, previous_end, units = "secs"))
      gap_text <- paste0("  gap ", format_duration(gap))
      if (gap < 0) {
        warning("Epochs of ", basename(path), " start ", format_duration(gap),
                " before the end of the previous file (overlap).")
      } else if (gap > gap_warning_secs) {
        warning("Gap of ", format_duration(gap), " before ", basename(path),
                ": check that this file belongs to the same session.")
      }
    }

    cat(sprintf("  %-48s %s -> %s  %6d epochs%s\n", basename(path),
                format(start_time, "%Y-%m-%d %H:%M:%S"),
                format(end_time, "%H:%M:%S"),
                length(epoch_rows), gap_text))
    previous_end <- end_time
  }
}, finally = close(out))

# Confirmation message
cat("\n", epochs_written, " epochs successfully merged into: ", output_file,
    "\n", sep = "")
