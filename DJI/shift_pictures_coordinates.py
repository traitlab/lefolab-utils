#!/usr/bin/env python3
"""
Shift the GPS position of DJI pictures by the difference between an old and a new base
position (e.g. RTK base set up on an approximate position, corrected after PPK), and undo
the shift from the log file.

Python port of shift_pictures_coordinates.R, with these differences:
- The GPS tags are patched in place, in the exact format DJI writes them (EXIF rationals
  with DJI's denominators, XMP "drone-dji:GpsLatitude="+45.594438582"" attributes with the
  same sign and number of decimals). Nothing else in the file changes, not even its size.
  The R script goes through ExifTool, which rewrites the whole XMP packet as elements
  (<drone-dji:GpsLatitude>45.5944452361748</drone-dji:GpsLatitude>), and tools parsing
  DJI's attribute format (e.g. closeup-ortho) then no longer find the position.
- The log records the exact original tag values and MD5 checksums of every picture, so
  `reverse` restores byte-identical original pictures. This includes the own position of
  the close-up (zoom/med/tele) pictures, which, as in the R script, get the shifted
  position of their wide picture.

Only the XY translation (in the projected CRS) and the height difference between the two
base positions are applied, exactly as in the R script.

Usage:
  # Shift (pictures written to <folder>/afterppk/, with <folder>_PPKshift.txt)
  python shift_pictures_coordinates.py shift \\
      --old-base 0.00000000 0.00000000 0.000 \\
      --new-base 0.00000000 0.00000000 0.000 \\
      --projected-crs 32618 --closeup \\
      /path/to/mission_folder1 /path/to/mission_folder2

  # Replace the pictures of each folder by the shifted ones in afterppk/ (deletes the originals!)
  python shift_pictures_coordinates.py cleanup /path/to/mission_folder1 /path/to/mission_folder2

  # Restore the original pictures in <folder>/beforeppk/ from <folder>_PPKshift.txt
  # (folder holding the shifted pictures and the log: the mission folder after cleanup,
  # or its afterppk/ folder before cleanup)
  python shift_pictures_coordinates.py reverse /path/to/mission_folder1

Requires pyproj.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import struct
import sys

from pyproj import Transformer

# Suffixes of the close-up pictures that follow a wide picture:
#   legacy naming: "<id>zoom"
#   current naming: "<id>tele" (M3E/M3T) or "<id>med" + "<id>tele" (M4E),
#   the wide picture being named "<id>wide"
CLOSEUP_SUFFIXES = ("zoom", "med", "tele")
CLOSEUP_PATTERN = re.compile(r"_(\d+)(" + "|".join(CLOSEUP_SUFFIXES) + r")\.(jpg|jpeg)$", re.IGNORECASE)

XMP_SIGNATURE = b"http://ns.adobe.com/xap/1.0/\x00"
# DJI XMP tags holding the position. DJI writes them as attributes (drone-dji:Tag="value");
# the element form (<drone-dji:Tag>value</drone-dji:Tag>) is what ExifTool writes back.
XMP_TAGS = ("GpsLatitude", "GpsLongitude", "AbsoluteAltitude")
XMP_ATTR_RE = re.compile(rb'drone-dji:(' + b"|".join(t.encode() for t in XMP_TAGS) + rb')="([^"]*)"')
XMP_ELEM_RE = re.compile(rb'<drone-dji:(' + b"|".join(t.encode() for t in XMP_TAGS) + rb')>([^<]*)</drone-dji:\1>')
# A changed XMP value length is absorbed by the XMP padding, so that the file layout does
# not move: spaces are added to/removed from the first run of at least this many spaces
XMP_PAD_RUN = 64

# EXIF GPS IFD tags
GPS_IFD_POINTER = 0x8825
GPS_LATITUDE_REF, GPS_LATITUDE = 0x0001, 0x0002
GPS_LONGITUDE_REF, GPS_LONGITUDE = 0x0003, 0x0004
GPS_ALTITUDE_REF, GPS_ALTITUDE = 0x0005, 0x0006

ORIGINAL_TAGS_PREFIX = "Original tags: "


# ---------------------------------------------------------------------------
# Logging (console + log file, like sink(split = TRUE) in the R script)
# ---------------------------------------------------------------------------

class Logger:
    def __init__(self, log_file):
        self.fh = open(log_file, "a", encoding="utf-8")

    def __call__(self, message="", console=True):
        if console:
            print(message)
        self.fh.write(message + "\n")
        self.fh.flush()

    def warning(self, message):
        self(f"Warning: {message}")

    def close(self):
        self.fh.close()


def progress(i, total):
    """Text progress bar on the console only (like txtProgressBar in the R script)."""
    width = 50
    done = int(width * i / total)
    sys.stdout.write(f"\r|{'=' * done}{' ' * (width - done)}| {100 * i // total:3d}%")
    sys.stdout.flush()
    if i == total:
        sys.stdout.write("\n")


# ---------------------------------------------------------------------------
# JPEG / EXIF / XMP access
# ---------------------------------------------------------------------------

def find_metadata_segments(data):
    """Return (tiff_start, (xmp_start, xmp_end)) of the EXIF and XMP APP1 segments of a JPEG."""
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG file")
    tiff_start = xmp = None
    pos = 2
    while pos < len(data) - 4:
        if data[pos] != 0xFF:
            raise ValueError(f"corrupt JPEG segment at byte {pos}")
        marker = data[pos + 1]
        if marker == 0xFF:  # fill byte
            pos += 1
            continue
        if marker in (0xD9, 0xDA):  # end of image / start of scan: no more metadata
            break
        if 0xD0 <= marker <= 0xD7 or marker == 0x01:  # markers without payload
            pos += 2
            continue
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        start, end = pos + 4, pos + 2 + length
        if marker == 0xE1:
            if data[start:start + 6] == b"Exif\x00\x00" and tiff_start is None:
                tiff_start = start + 6
            elif data[start:start + len(XMP_SIGNATURE)] == XMP_SIGNATURE and xmp is None:
                xmp = (start + len(XMP_SIGNATURE), end)
        pos = end
    return tiff_start, xmp


def read_gps_entries(data, tiff_start):
    """Return (byte order, {tag: (type, count, absolute position of the value or of its offset)})
    of the EXIF GPS IFD."""
    bo = {b"II": "<", b"MM": ">"}.get(bytes(data[tiff_start:tiff_start + 2]))
    if bo is None:
        raise ValueError("invalid EXIF byte order")

    def ifd_entries(ifd_offset):
        pos = tiff_start + ifd_offset
        count = struct.unpack(bo + "H", data[pos:pos + 2])[0]
        entries = {}
        for k in range(count):
            e = pos + 2 + 12 * k
            tag, typ, n = struct.unpack(bo + "HHI", data[e:e + 8])
            entries[tag] = (typ, n, e + 8)
        return entries

    ifd0 = ifd_entries(struct.unpack(bo + "I", data[tiff_start + 4:tiff_start + 8])[0])
    if GPS_IFD_POINTER not in ifd0:
        raise ValueError("no EXIF GPS data")
    gps_offset = struct.unpack(bo + "I", data[ifd0[GPS_IFD_POINTER][2]:ifd0[GPS_IFD_POINTER][2] + 4])[0]
    return bo, ifd_entries(gps_offset)


class PictureTags:
    """Locations and raw values of the GPS tags of one DJI picture, read from its bytes."""

    def __init__(self, data):
        self.data = data
        tiff_start, self.xmp_span = find_metadata_segments(data)
        if tiff_start is None:
            raise ValueError("no EXIF data")
        self.tiff_start = tiff_start
        self.bo, gps = read_gps_entries(data, tiff_start)
        for tag in (GPS_LATITUDE_REF, GPS_LATITUDE, GPS_LONGITUDE_REF, GPS_LONGITUDE, GPS_ALTITUDE_REF, GPS_ALTITUDE):
            if tag not in gps:
                raise ValueError(f"no EXIF GPS tag 0x{tag:04x}")
        self.gps = gps

    # EXIF values: refs are read/written inline in the IFD entry, rationals at their offset
    def _rational_pos(self, tag):
        return self.tiff_start + struct.unpack(self.bo + "I", self.data[self.gps[tag][2]:self.gps[tag][2] + 4])[0]

    def _read_rationals(self, tag):
        pos, n = self._rational_pos(tag), self.gps[tag][1]
        vals = struct.unpack(self.bo + "I" * (2 * n), self.data[pos:pos + 8 * n])
        return [[vals[2 * k], vals[2 * k + 1]] for k in range(n)]

    def _write_rationals(self, tag, rationals):
        if len(rationals) != self.gps[tag][1]:
            raise ValueError(f"wrong number of rationals for EXIF GPS tag 0x{tag:04x}")
        pos = self._rational_pos(tag)
        flat = [v for r in rationals for v in r]
        self.data[pos:pos + 4 * len(flat)] = struct.pack(self.bo + "I" * len(flat), *flat)

    def read_exif(self):
        return {
            "GPSLatitudeRef": chr(self.data[self.gps[GPS_LATITUDE_REF][2]]),
            "GPSLatitude": self._read_rationals(GPS_LATITUDE),
            "GPSLongitudeRef": chr(self.data[self.gps[GPS_LONGITUDE_REF][2]]),
            "GPSLongitude": self._read_rationals(GPS_LONGITUDE),
            "GPSAltitudeRef": self.data[self.gps[GPS_ALTITUDE_REF][2]],
            "GPSAltitude": self._read_rationals(GPS_ALTITUDE)[0],
        }

    def write_exif(self, exif):
        self.data[self.gps[GPS_LATITUDE_REF][2]] = ord(exif["GPSLatitudeRef"])
        self._write_rationals(GPS_LATITUDE, exif["GPSLatitude"])
        self.data[self.gps[GPS_LONGITUDE_REF][2]] = ord(exif["GPSLongitudeRef"])
        self._write_rationals(GPS_LONGITUDE, exif["GPSLongitude"])
        self.data[self.gps[GPS_ALTITUDE_REF][2]] = exif["GPSAltitudeRef"]
        self._write_rationals(GPS_ALTITUDE, [exif["GPSAltitude"]])

    # XMP values
    def _xmp_matches(self):
        if self.xmp_span is None:
            return {}
        start, end = self.xmp_span
        matches = {}
        for regex in (XMP_ATTR_RE, XMP_ELEM_RE):
            for m in regex.finditer(self.data, start, end):
                matches.setdefault(m.group(1).decode(), m)
        return matches

    def read_xmp(self):
        return {tag: m.group(2).decode() for tag, m in self._xmp_matches().items()}

    def write_xmp(self, xmp):
        matches = self._xmp_matches()
        start, end = self.xmp_span
        packet = bytes(self.data[start:end])
        # Replace values from the end of the packet so earlier positions stay valid
        delta = 0
        for tag in sorted(xmp, key=lambda t: matches[t].start(2), reverse=True):
            m = matches[tag]
            new_value = xmp[tag].encode()
            packet = packet[:m.start(2) - start] + new_value + packet[m.end(2) - start:]
            delta += len(new_value) - (m.end(2) - m.start(2))
        if delta:
            packet = adjust_xmp_padding(packet, delta)
        self.data[start:end] = packet


def adjust_xmp_padding(packet, delta):
    """Remove (delta > 0) or add (delta < 0) spaces in the XMP padding to keep the packet length."""
    pad_end = packet.rfind(b"<?xpacket end")
    pad_start = packet.rfind(b"</x:xmpmeta>", 0, pad_end)
    if pad_start < 0 or pad_end < 0:
        raise ValueError("no XMP padding to absorb the change of length of the XMP values")
    run = re.compile(rb" {%d,}" % XMP_PAD_RUN).search(packet, pad_start, pad_end)
    if run is None or run.end() - run.start() - delta < XMP_PAD_RUN:
        raise ValueError("not enough XMP padding to absorb the change of length of the XMP values")
    return packet[:run.end() - delta] + packet[run.end():] if delta > 0 else \
        packet[:run.end()] + b" " * (-delta) + packet[run.end():]


# ---------------------------------------------------------------------------
# Value conversions, keeping DJI's formats
# ---------------------------------------------------------------------------

def dms_to_degrees(rationals, ref):
    d, m, s = (n / den for n, den in rationals)
    value = d + m / 60 + s / 3600
    return -value if ref in ("S", "W") else value


def degrees_to_dms(value, template):
    """DMS rationals of |value|, with the denominators of the template (DJI: 1, 1, 10000)."""
    (_, deg_den), (_, min_den), (_, sec_den) = template
    if deg_den != 1 or min_den != 1:
        raise ValueError(f"unexpected EXIF GPS DMS rationals {template}")
    units = round(abs(value) * 3600 * sec_den)
    d, rem = divmod(units, 3600 * sec_den)
    m, s = divmod(rem, 60 * sec_den)
    return [[d, 1], [m, 1], [s, sec_den]]


def format_like(value, template):
    """Format a number like a DJI XMP string: same explicit sign and number of decimals."""
    decimals = len(template.split(".")[1]) if "." in template else 0
    return f"{value:+.{decimals}f}" if template[:1] in "+-" else f"{value:.{decimals}f}"


def md5sum(data):
    return hashlib.md5(data).hexdigest()


# ---------------------------------------------------------------------------
# Shift
# ---------------------------------------------------------------------------

def read_position(tags):
    """Return the original tags and (lat, lon, GPSAltitude, AbsoluteAltitude) of a picture."""
    exif, xmp = tags.read_exif(), tags.read_xmp()

    # The XMP holds the most precise position (1e-9 degrees), EXIF is the fallback
    if "GpsLatitude" in xmp and "GpsLongitude" in xmp:
        lat, lon = float(xmp["GpsLatitude"]), float(xmp["GpsLongitude"])
    else:
        lat = dms_to_degrees(exif["GPSLatitude"], exif["GPSLatitudeRef"])
        lon = dms_to_degrees(exif["GPSLongitude"], exif["GPSLongitudeRef"])
    alt_num, alt_den = exif["GPSAltitude"]
    alt = (-1 if exif["GPSAltitudeRef"] == 1 else 1) * alt_num / alt_den
    if "AbsoluteAltitude" not in xmp:
        raise ValueError("no GPS altitude data found (XMP AbsoluteAltitude)")
    abs_alt = float(xmp["AbsoluteAltitude"])
    return {"exif": exif, "xmp": xmp}, (lat, lon, alt, abs_alt)


def write_position(tags, original_tags, position):
    """Write (lat, lon, GPSAltitude, AbsoluteAltitude) into the GPS tags of a picture, in the
    format (denominators, sign, decimals) of its original tags."""
    exif, xmp = original_tags["exif"], original_tags["xmp"]
    new_lat, new_lon, new_alt, new_abs_alt = position
    alt_den = exif["GPSAltitude"][1]
    new_exif = {
        "GPSLatitudeRef": "N" if new_lat >= 0 else "S",
        "GPSLatitude": degrees_to_dms(new_lat, exif["GPSLatitude"]),
        "GPSLongitudeRef": "E" if new_lon >= 0 else "W",
        "GPSLongitude": degrees_to_dms(new_lon, exif["GPSLongitude"]),
        "GPSAltitudeRef": 1 if new_alt < 0 else 0,
        "GPSAltitude": [round(abs(new_alt) * alt_den), alt_den],
    }
    new_xmp = {}
    if "GpsLatitude" in xmp:
        new_xmp["GpsLatitude"] = format_like(new_lat, xmp["GpsLatitude"])
    if "GpsLongitude" in xmp:
        new_xmp["GpsLongitude"] = format_like(new_lon, xmp["GpsLongitude"])
    if "AbsoluteAltitude" in xmp:
        new_xmp["AbsoluteAltitude"] = format_like(new_abs_alt, xmp["AbsoluteAltitude"])

    tags.write_exif(new_exif)
    tags.write_xmp(new_xmp)


def list_pictures(folder):
    return sorted(f for f in glob.glob(os.path.join(folder, "*"))
                  if re.search(r"\.(jpg|jpeg)$", f, re.IGNORECASE) and os.path.isfile(f))


def find_folders(folder, has_content, skip):
    """Return the folder and its subfolders for which has_content(folder) is true, without
    descending into the subfolders named in skip (e.g. the afterppk/beforeppk outputs)."""
    found = []
    for root, dirs, _ in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d not in skip)
        if has_content(root):
            found.append(root)
    return found


def shift_pictures_coordinates(input_folder,
                               old_base_position,  # dict(lat=, lon=, height=) of old base position (ellipsoidal height)
                               new_base_position,  # dict(lat=, lon=, height=) of new base position (ellipsoidal height)
                               projected_crs,      # Projected CRS (EPSG code)
                               closeup,           # True for wide + close-up picture sets (legacy wide+zoom, M3E/M3T wide+tele, M4E wide+med+tele), False for standalone pictures (mapping pictures for instance)
                               input_crs=4326):    # Input CRS, default to EPSG 4326 for WGS84
    success_count = 0
    error_count = 0

    # Create 'afterppk' directory inside input_folder
    output_folder = os.path.join(input_folder, "afterppk")
    os.makedirs(output_folder, exist_ok=True)

    # Create a log file in the output folder
    folder_name = os.path.basename(os.path.normpath(os.path.abspath(input_folder)))
    log = Logger(os.path.join(output_folder, f"{folder_name}_PPKshift.txt"))

    # Log input parameters
    log("Processing started")
    log(f"Input folder:  {input_folder} ")
    log(f"Old base position:  {old_base_position['lat']}, {old_base_position['lon']}, {old_base_position['height']} ")
    log(f"New base position:  {new_base_position['lat']}, {new_base_position['lon']}, {new_base_position['height']} ")
    log(f"Input CRS:  {input_crs} ")
    log(f"Projected CRS:  {projected_crs} ")
    log(f"Close-up:  {str(closeup).upper()} ")

    image_files = list_pictures(input_folder)

    # A folder shot with a "med" camera (M4E) is expected to hold both a "med" and a "tele"
    # picture per wide picture; on M3E/M3T a lone "tele" picture is the normal case
    folder_has_med = any(re.search(r"_(\d+)med\.(jpg|jpeg)$", os.path.basename(f), re.IGNORECASE) for f in image_files)

    # Determine files to process (the wide pictures define the picture sets)
    if closeup:
        wide_files = [f for f in image_files if not CLOSEUP_PATTERN.search(os.path.basename(f))]
    else:
        wide_files = image_files

    if not wide_files:
        log.close()
        raise RuntimeError("No image files found in the input folder.")

    # Project the base positions to the projected CRS and compute the XY difference
    to_projected = Transformer.from_crs(input_crs, projected_crs, always_xy=True)
    to_input = Transformer.from_crs(projected_crs, input_crs, always_xy=True)
    old_x, old_y = to_projected.transform(old_base_position["lon"], old_base_position["lat"])
    new_x, new_y = to_projected.transform(new_base_position["lon"], new_base_position["lat"])
    xy_difference = (new_x - old_x, new_y - old_y)
    height_shift = new_base_position["height"] - old_base_position["height"]

    # Process each picture set
    for i, wide_file in enumerate(wide_files, start=1):
        progress(i, len(wide_files))
        pair_files = [wide_file]  # Default to single file

        if closeup:
            # Extract the polygon id from image file (the wide picture has no suffix in the
            # legacy naming, and a "wide" suffix in the current naming)
            polygon_id = re.sub(r".*_(\d+)(wide)?\..*", r"\1", os.path.basename(wide_file), flags=re.IGNORECASE)

            # Search for the corresponding close-up file(s): "zoom" (legacy) or "med"/"tele" (current)
            identifier_match = re.compile(r"_" + re.escape(polygon_id) + r"(" + "|".join(CLOSEUP_SUFFIXES) + r")\.(jpg|jpeg)$", re.IGNORECASE)
            zoom_files = [f for f in image_files if identifier_match.search(os.path.basename(f))]

            # Check if at least one close-up file exists
            if not zoom_files:
                log.warning(f"Skipping {os.path.basename(wide_file)} - no corresponding zoom/med/tele file found.")
                error_count += 1
                continue

            # Warn on incomplete M4E sets, where both a "med" and a "tele" picture are expected
            set_has_med = any(re.search(r"med\.(jpg|jpeg)$", f, re.IGNORECASE) for f in zoom_files)
            set_has_tele = any(re.search(r"tele\.(jpg|jpeg)$", f, re.IGNORECASE) for f in zoom_files)
            if set_has_med and not set_has_tele:
                log.warning(f"Incomplete set for {os.path.basename(wide_file)} - 'med' picture found but no corresponding 'tele' picture.")
            elif folder_has_med and set_has_tele and not set_has_med:
                log.warning(f"Incomplete set for {os.path.basename(wide_file)} - 'tele' picture found but no corresponding 'med' picture.")

            pair_files = [wide_file] + zoom_files

        # Shift the position of the wide picture and write it into all the pictures of the set
        # (the close-up pictures get the position of the wide picture, as in the R script);
        # the whole set is skipped if one picture cannot be read or written
        results = []
        try:
            for f in pair_files:
                with open(f, "rb") as fh:
                    original = fh.read()
                data = bytearray(original)
                tags = PictureTags(data)
                original_tags, position = read_position(tags)
                results.append((f, original, data, tags, original_tags, position))

            lat, lon, alt, abs_alt = results[0][5]
            x, y = to_projected.transform(lon, lat)
            new_lon, new_lat = to_input.transform(x + xy_difference[0], y + xy_difference[1])
            shifted = (new_lat, new_lon, alt + height_shift, abs_alt + height_shift)

            for f, original, data, tags, original_tags, position in results:
                write_position(tags, original_tags, shifted)
        except (ValueError, struct.error) as e:
            log.warning(f"Skipping {', '.join(os.path.basename(f) for f in pair_files)} - {os.path.basename(f)}: {e}")
            error_count += 1
            continue

        for f, original, data, tags, original_tags, position in results:
            output_file = os.path.join(output_folder, os.path.basename(f))
            if os.path.exists(output_file):
                os.chmod(output_file, 0o644)  # originals are often read-only
            with open(output_file, "wb") as fh:
                fh.write(data)
            st = os.stat(f)
            os.utime(output_file, (st.st_atime, st.st_mtime))

        success_count += 1
        log(f"Successfully updated EXIF metadata for: {', '.join(os.path.basename(f) for f in pair_files)} | "
            f"Before: ({lat:.8f}, {lon:.8f}, {alt:.3f}) | "
            f"After: ({shifted[0]:.8f}, {shifted[1]:.8f}, {shifted[2]:.3f})", console=False)
        # Exact original tag values of every picture (including the own position of the
        # close-up pictures), used by `reverse` to restore byte-identical pictures
        for f, original, data, tags, original_tags, position in results:
            record = dict(original_tags, md5_original=md5sum(original), md5_shifted=md5sum(data))
            log(f"{ORIGINAL_TAGS_PREFIX}{os.path.basename(f)} | {json.dumps(record)}", console=False)

    log(f"Processing complete: {success_count} successful, {error_count} failed")
    log.close()
    return f"Output files in: {output_folder}"


# ---------------------------------------------------------------------------
# Reverse
# ---------------------------------------------------------------------------

def find_log_file(folder):
    """Find the *_PPKshift.txt log of a folder holding shifted pictures."""
    logs = glob.glob(os.path.join(folder, "*_PPKshift.txt"))
    if len(logs) != 1:
        raise FileNotFoundError(f"Expected one *_PPKshift.txt file in {folder}, found {len(logs)}")
    return logs[0]


def read_original_tags(log_file):
    """Return {file name: original tags record} from a log (the last record of a file wins)."""
    records = {}
    with open(log_file, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith(ORIGINAL_TAGS_PREFIX):
                name, record = line[len(ORIGINAL_TAGS_PREFIX):].split(" | ", 1)
                records[name] = json.loads(record)
    return records


def reverse_pictures_coordinates(folder, log_file=None):
    """Restore the original GPS tags of the shifted pictures of a folder into <folder>/beforeppk/."""
    log_file = log_file or find_log_file(folder)
    records = read_original_tags(log_file)
    if not records:
        raise RuntimeError(f"No '{ORIGINAL_TAGS_PREFIX.strip()}' lines in {log_file}: it was not written by "
                           "this script (the R script does not log what is needed to reverse the shift).")

    output_folder = os.path.join(folder, "beforeppk")
    os.makedirs(output_folder, exist_ok=True)
    identical, modified, failed = 0, 0, 0

    names = sorted(records)
    for i, name in enumerate(names, start=1):
        progress(i, len(names))
        record = records[name]
        path = os.path.join(folder, name)
        try:
            with open(path, "rb") as fh:
                data = bytearray(fh.read())
            if md5sum(data) != record["md5_shifted"]:
                print(f"\nWarning: {name} changed since it was shifted, the restored file will not be byte-identical.")
            tags = PictureTags(data)
            tags.write_exif(record["exif"])
            tags.write_xmp(record["xmp"])
        except (OSError, ValueError, struct.error) as e:
            print(f"\nWarning: could not restore {name}: {e}")
            failed += 1
            continue

        output_file = os.path.join(output_folder, name)
        if os.path.exists(output_file):
            os.chmod(output_file, 0o644)
        with open(output_file, "wb") as fh:
            fh.write(data)
        st = os.stat(path)
        os.utime(output_file, (st.st_atime, st.st_mtime))
        if md5sum(data) == record["md5_original"]:
            identical += 1
        else:
            modified += 1

    print(f"Reverse complete: {identical} restored byte-identical, {modified} restored with different bytes, {failed} failed")
    return f"Output files in: {output_folder}"


# ---------------------------------------------------------------------------
# Cleanup: replace the pictures of a folder by the shifted ones
# ---------------------------------------------------------------------------

def cleanup(folder):
    # Recursively search for 'afterppk' folders in the folder and subfolders
    for afterppk_folder in sorted(glob.glob(os.path.join(folder, "**", "afterppk"), recursive=True)):
        files_to_move = glob.glob(os.path.join(afterppk_folder, "*"))
        parent_folder = os.path.dirname(afterppk_folder)

        # Delete all pictures from the parent folder
        pictures_to_delete = list_pictures(parent_folder)
        for f in pictures_to_delete:
            os.remove(f)
        print(f"Deleted {len(pictures_to_delete)} pictures from {parent_folder}")

        # Move files from 'afterppk' folder to the parent folder
        for f in files_to_move:
            shutil.move(f, os.path.join(parent_folder, os.path.basename(f)))
        print(f"Moved {len(files_to_move)} files from {afterppk_folder} to {parent_folder}")

        # Delete the empty 'afterppk' folder
        os.rmdir(afterppk_folder)


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("shift", help="shift the pictures of each folder into <folder>/afterppk/")
    p.add_argument("folders", nargs="+", help="folders containing the pictures")
    p.add_argument("--recursive", action=argparse.BooleanOptionalAction, default=True,
                   help="also shift the pictures of every subfolder, each into its own afterppk/ (default: on)")
    p.add_argument("--old-base", nargs=3, type=float, required=True, metavar=("LAT", "LON", "HEIGHT"),
                   help="old base position (ellipsoidal height)")
    p.add_argument("--new-base", nargs=3, type=float, required=True, metavar=("LAT", "LON", "HEIGHT"),
                   help="new base position (ellipsoidal height)")
    p.add_argument("--input-crs", type=int, default=4326, help="input CRS (default: 4326, WGS84)")
    p.add_argument("--projected-crs", type=int, required=True, help="projected CRS, e.g. 32618 (UTM 18N)")
    p.add_argument("--closeup", action=argparse.BooleanOptionalAction, required=True,
                   help="--closeup for wide + close-up picture sets, --no-closeup for standalone pictures")

    p = sub.add_parser("reverse", help="restore the original pictures into <folder>/beforeppk/")
    p.add_argument("folders", nargs="+", help="folders containing the shifted pictures and their *_PPKshift.txt")
    p.add_argument("--log", help="log file (default: the *_PPKshift.txt of each folder)")
    p.add_argument("--recursive", action=argparse.BooleanOptionalAction, default=True,
                   help="also reverse every subfolder holding a *_PPKshift.txt (default: on, off with --log)")

    p = sub.add_parser("cleanup", help="replace the pictures of each folder by those of its afterppk/ subfolders")
    p.add_argument("folders", nargs="+")

    args = parser.parse_args()

    folders = []
    for folder in args.folders:
        if args.command == "cleanup" or not args.recursive or (args.command == "reverse" and args.log):
            folders.append(folder)
        elif args.command == "shift":
            folders += find_folders(folder, list_pictures, skip=("afterppk", "beforeppk")) or [folder]
        else:
            folders += find_folders(folder, lambda f: glob.glob(os.path.join(f, "*_PPKshift.txt")),
                                    skip=("beforeppk",)) or [folder]

    failed = False
    for folder in folders:
        try:
            if args.command == "shift":
                print(shift_pictures_coordinates(
                    folder,
                    old_base_position=dict(zip(("lat", "lon", "height"), args.old_base)),
                    new_base_position=dict(zip(("lat", "lon", "height"), args.new_base)),
                    projected_crs=args.projected_crs,
                    closeup=args.closeup,
                    input_crs=args.input_crs))
            elif args.command == "reverse":
                print(reverse_pictures_coordinates(folder, args.log))
            else:
                cleanup(folder)
        except Exception as e:
            print(f"Failed to process folder: {folder} : {e}", file=sys.stderr)
            failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
