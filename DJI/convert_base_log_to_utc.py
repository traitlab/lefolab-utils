"""Convert the GPS timestamps of a DJI RTK base log to UTC.

Handles both base station generations, auto-detected from the folder content:

  * D-RTK 2  -> ".dat" text log, one "bestpos:<week>,<ms>ms,..." line per record.
  * D-RTK 3  -> ".MRK" tab separated log, "<index>\t<seconds of week>\t[<week>]\t...".
               Its ".dat" is binary RTCM (raw observations for PPK, no readable
               timestamps) and is skipped.

The GPS -> UTC conversion was checked against the RINEX epochs of the matching
".OBS" file: with LEAP_SECONDS = 18 the last ".MRK" record and the last RINEX
epoch of the same session agree to the second.

Output: one "<YYYYMMDD_HHMMSS>_UTC_<file number>.txt" per input file, each source
line kept as-is with " [UTC: ...]" appended.
"""

import os
import re
import sys
from datetime import datetime, timedelta

# GPS epoch, and the GPS-UTC offset. 18 s since 2017-01-01; no leap second has
# been introduced since, so this is still correct. Bump it if one ever is.
GPS_EPOCH = datetime(1980, 1, 6, 0, 0, 0)
LEAP_SECONDS = 18


def gps2utc(gps_week, seconds_of_week):
    """GPS week + seconds of week -> UTC datetime."""
    gps_time = GPS_EPOCH + timedelta(weeks=gps_week, seconds=seconds_of_week)
    return gps_time - timedelta(seconds=LEAP_SECONDS)


def file_number(path):
    """Sequence number of a log file, e.g. 0100 in DRTK3_0100_20260818094346_XX.MRK.

    A short group delimited by underscores is taken first, so a date stamp of
    any length cannot be mistaken for the number. Falling back to the first
    short run of digits, once stamps have been stripped out.
    """
    stem = os.path.splitext(os.path.basename(path))[0]
    match = re.search(r"_(\d{3,4})_", stem)
    if match:
        return match.group(1)
    match = re.search(r"(\d{3,4})", re.sub(r"\d{8,}", "", stem))
    return match.group(1) if match else "000"


# --------------------------------------------------------------- D-RTK 3 (.MRK)

def parse_mrk_line(line):
    """Parse one .MRK record, or return None when the line is not a record."""
    fields = line.rstrip("\r\n").split("\t")
    if len(fields) < 3:
        return None
    try:
        seconds_of_week = float(fields[1])
        gps_week = int(fields[2].strip().strip("[]"))
    except (ValueError, IndexError):
        return None

    # Fields 4-6 are the N/E/V offsets: zero on a base log, the real
    # antenna -> camera offsets on a drone photo event file
    offsets = []
    for i in (3, 4, 5):
        if i < len(fields):
            try:
                offsets.append(float(fields[i].split(",")[0].strip()))
            except ValueError:
                pass

    return {
        "gps_week": gps_week,
        "seconds_of_week": seconds_of_week,
        "offsets": offsets,
        "raw": line.rstrip("\r\n"),
    }


def warn_if_not_base_log(path, records):
    """Warn when a .MRK looks like drone photo events instead of a base log.

    Both kinds share the same column layout, so pointing this script at a
    mission folder would otherwise convert photo timestamps without a word. The
    conversion stays valid either way, hence a warning rather than a skip.
    """
    name = os.path.basename(path)
    reasons = []

    if name.upper().endswith("_TIMESTAMP.MRK"):
        reasons.append("name ends with '_Timestamp.MRK', which DJI uses for "
                       "photo events")
    elif not name.upper().startswith("DRTK"):
        reasons.append("name does not start with 'DRTK', unlike a base station "
                       "log")

    with_offsets = sum(1 for r in records
                       if any(abs(v) > 1e-9 for v in r["offsets"]))
    if with_offsets:
        reasons.append(f"{with_offsets} of {len(records)} records carry "
                       "non-zero N/E/V offsets (a base station logs zeros)")

    if reasons:
        print(f"  WARNING: {name} does not look like a D-RTK 3 base log:")
        for reason in reasons:
            print(f"    - {reason}")
        print("    Converting anyway; check that this is the folder you meant.")


def process_mrk_file(path):
    records = []
    with open(path, "r") as infile:
        for line in infile:
            if not line.strip():
                continue
            record = parse_mrk_line(line)
            if record is None:
                print(f"  Skipping unreadable line: {line.strip()[:60]}")
                continue
            records.append(record)

    if not records:
        print(f"  No records found in {os.path.basename(path)}")
        return None

    warn_if_not_base_log(path, records)

    processed_lines = []
    for record in records:
        utc_time = gps2utc(record["gps_week"], record["seconds_of_week"])
        utc_str = utc_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        processed_lines.append(f"{record['raw']} [UTC: {utc_str}]\n")

    first = gps2utc(records[0]["gps_week"], records[0]["seconds_of_week"])
    last = gps2utc(records[-1]["gps_week"], records[-1]["seconds_of_week"])
    print(f"  {len(records)} records, {first} -> {last} UTC")
    if len(records) > 1:
        step = records[1]["seconds_of_week"] - records[0]["seconds_of_week"]
        print(f"  interval between the first two records: {step:.1f} s")

    return write_output(path, first, processed_lines)


# --------------------------------------------------------------- D-RTK 2 (.dat)

def dat_is_text_log(path):
    """True for a D-RTK 2 text log, False for a D-RTK 3 binary RTCM .dat."""
    with open(path, "rb") as fh:
        head = fh.read(65536)
    return b"bestpos" in head


def process_dat_file(path):
    first_valid_utc = None
    processed_lines = []

    with open(path, "r", errors="replace") as infile:
        for line in infile:
            if not line.startswith("bestpos:"):
                continue
            parts = line.strip().split(",")

            # Lines with no GPS data
            if parts[0] == "bestpos:0" or len(parts) < 2:
                continue

            try:
                gps_week = int(parts[0].split(":")[1])
                gps_ms = int(parts[1].split("ms")[0])
                utc_time = gps2utc(gps_week, gps_ms / 1000.0)
            except (ValueError, IndexError) as err:
                print(f"  Error processing line: {line.strip()[:60]}")
                print(f"  Error details: {err}")
                continue

            utc_str = utc_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            if first_valid_utc is None:
                first_valid_utc = utc_time
            processed_lines.append(f"{line.strip()} [UTC: {utc_str}]\n")

    if first_valid_utc is None:
        print(f"  No valid GPS data found in {os.path.basename(path)}")
        return None

    print(f"  {len(processed_lines)} records, first {first_valid_utc} UTC")
    return write_output(path, first_valid_utc, processed_lines)


# ---------------------------------------------------------------------- Output

def write_output(path, first_utc, processed_lines):
    output_name = (f"{first_utc.strftime('%Y%m%d_%H%M%S')}_UTC_"
                   f"{file_number(path)}.txt")
    output_path = os.path.join(os.path.dirname(path), output_name)
    with open(output_path, "w") as outfile:
        outfile.writelines(processed_lines)
    return output_path


# ------------------------------------------------------------------- Detection

def process_folder(input_dir):
    if not os.path.isdir(input_dir):
        print(f"Folder not found: {input_dir}")
        return

    entries = sorted(os.listdir(input_dir))
    mrk_files = [f for f in entries if f.lower().endswith(".mrk")]
    dat_files = [f for f in entries if f.lower().endswith(".dat")]

    # A D-RTK 3 folder holds both: the .MRK carries the timestamps, its .dat is
    # binary RTCM. The .MRK files therefore decide which generation this is.
    if mrk_files:
        print(f"Base: D-RTK 3 ({len(mrk_files)} .MRK file(s))")
        if dat_files:
            print(f"      ignoring {len(dat_files)} binary .dat file(s): "
                  "raw RTCM for PPK, no readable timestamps")
        handler, files = process_mrk_file, mrk_files
    elif dat_files:
        text_logs = [f for f in dat_files
                     if dat_is_text_log(os.path.join(input_dir, f))]
        binary = len(dat_files) - len(text_logs)
        if not text_logs:
            print(f"Found {len(dat_files)} .dat file(s), but none contains "
                  "'bestpos:' lines.")
            print("They look like D-RTK 3 binary RTCM logs, whose timestamps "
                  "are in the .MRK files instead - none found here.")
            return
        print(f"Base: D-RTK 2 ({len(text_logs)} text .dat file(s))")
        if binary:
            print(f"      skipping {binary} .dat file(s) without 'bestpos:' "
                  "lines")
        handler, files = process_dat_file, text_logs
    else:
        print(f"No .MRK and no .dat file found in {input_dir}")
        return

    for name in files:
        print(f"Processing {name}...")
        output_path = handler(os.path.join(input_dir, name))
        if output_path:
            print(f"  Saved results to {os.path.basename(output_path)}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_directory = sys.argv[1]
    else:
        input_directory = input(
            "Enter the path to the directory containing the base log files: ")
    process_folder(input_directory.strip().strip('"'))
    print("Done.")
