#!/usr/bin/env python3
"""
Download GeoTIFF files from Sentinel-2 filtered acquisitions.

This script reads the filtered CSV output and downloads all GeoTIFF files
from the signed URLs, organizing them by acquisition date and band.

Usage:
    python3 download_geotiffs.py
    python3 download_geotiffs.py --input custom_input.csv --output-dir downloads
    python3 download_geotiffs.py --bands B02 B03 B04  # Download only RGB bands
"""

import pandas as pd
import argparse
import os
import sys
import time
import json
from pathlib import Path
from urllib.request import urlretrieve
from urllib.error import URLError, HTTPError
from pystac_client import Client
import planetary_computer as pc


def is_tty():
    """Check if stdout is a TTY (terminal)."""
    return sys.stdout.isatty()


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Download GeoTIFF files from Sentinel-2 filtered acquisitions"
    )
    
    # Get script directory for default paths
    script_dir = Path(__file__).parent
    default_input = script_dir / "output" / "sentinel2_assets_filtered_monthly_best.csv"
    default_output_dir = script_dir / "downloads"
    
    parser.add_argument(
        "--input",
        type=str,
        default=str(default_input),
        help=f"Input CSV file path (default: {default_input})"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(default_output_dir),
        help=f"Output directory for downloads (default: {default_output_dir})"
    )
    
    parser.add_argument(
        "--bands",
        nargs="+",
        default=None,
        help="Specific bands to download (e.g., B02 B03 B04). If not specified, downloads all bands."
    )
    
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip files that already exist in the output directory"
    )
    
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between downloads in seconds (default: 0.5)"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output (useful for logging)"
    )
    
    return parser.parse_args()


def format_file_size(size_bytes):
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def create_filename(row):
    """
    Create a descriptive filename for the GeoTIFF.
    
    Format: YYYY-MM-DD_item_id_band.tif
    Example: 2022-04-09_S2A_MSIL2A_20220409T193901_R042_T10VEP_20240525T131307_B02.tif
    """
    datetime_obj = pd.to_datetime(row['datetime'])
    date_str = datetime_obj.strftime('%Y-%m-%d')
    item_id = row['item_id']
    band = row['asset_key']
    
    filename = f"{date_str}_{item_id}_{band}.tif"
    return filename


def log_debug(session_id, run_id, hypothesis_id, location, message, data):
    """Write debug log entry to NDJSON file."""
    # #region agent log
    # Use log folder under scripts/py directory
    script_dir = Path(__file__).parent
    log_dir = script_dir / "log"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / "debug.log"
    try:
        with open(log_path, "a") as f:
            log_entry = {
                "sessionId": session_id,
                "runId": run_id,
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data,
                "timestamp": int(time.time() * 1000)
            }
            f.write(json.dumps(log_entry) + "\n")
    except Exception:
        pass  # Silently fail if logging doesn't work
    # #endregion agent log


def get_fresh_signed_url(item_id, asset_key, catalog, session_id, run_id):
    """
    Get a fresh signed URL from Planetary Computer.
    
    Args:
        item_id: Sentinel-2 item identifier
        asset_key: Asset key (e.g., B02, B03, B04, B08)
        catalog: STAC catalog client
        session_id: Debug session ID
        run_id: Debug run ID
        
    Returns:
        tuple: (signed_url: str or None, error_msg: str or None)
    """
    # #region agent log
    log_debug(session_id, run_id, "A", "download_geotiffs.py:get_fresh_signed_url", 
              "Attempting to get fresh signed URL", 
              {"item_id": item_id, "asset_key": asset_key})
    # #endregion agent log
    
    try:
        # Get the collection
        collection = catalog.get_collection("sentinel-2-l2a")
        
        # #region agent log
        log_debug(session_id, run_id, "B", "download_geotiffs.py:get_fresh_signed_url",
                  "Collection retrieved", {"collection_id": collection.id})
        # #endregion agent log
        
        # Get the item from STAC API
        item = collection.get_item(item_id)
        
        # #region agent log
        log_debug(session_id, run_id, "C", "download_geotiffs.py:get_fresh_signed_url",
                  "Item retrieved from STAC", {"item_id": item_id, "item_exists": item is not None})
        # #endregion agent log
        
        # Sign the item
        signed = pc.sign(item)
        
        # #region agent log
        log_debug(session_id, run_id, "D", "download_geotiffs.py:get_fresh_signed_url",
                  "Item signed", {"item_id": item_id, "available_assets": list(signed.assets.keys())})
        # #endregion agent log
        
        # Get the signed URL for the specific asset
        if asset_key in signed.assets:
            signed_url = signed.assets[asset_key].href
            
            # #region agent log
            log_debug(session_id, run_id, "E", "download_geotiffs.py:get_fresh_signed_url",
                      "Fresh signed URL obtained", {"item_id": item_id, "asset_key": asset_key, 
                      "url_length": len(signed_url), "url_preview": signed_url[:100] + "..."})
            # #endregion agent log
            
            return signed_url, None
        else:
            error_msg = f"Asset key '{asset_key}' not found in item"
            
            # #region agent log
            log_debug(session_id, run_id, "F", "download_geotiffs.py:get_fresh_signed_url",
                      "Asset key not found", {"item_id": item_id, "asset_key": asset_key,
                      "available_assets": list(signed.assets.keys())})
            # #endregion agent log
            
            return None, error_msg
            
    except Exception as e:
        error_msg = f"Error getting fresh URL: {str(e)}"
        
        # #region agent log
        log_debug(session_id, run_id, "G", "download_geotiffs.py:get_fresh_signed_url",
                  "Exception getting fresh URL", {"item_id": item_id, "asset_key": asset_key,
                  "error_type": type(e).__name__, "error_message": str(e)})
        # #endregion agent log
        
        return None, error_msg


def download_with_progress(url, output_path, session_id, run_id, item_id, asset_key, quiet=False):
    """
    Download a file with basic progress indication.
    
    Args:
        url: URL to download from
        output_path: Path to save the file
        session_id: Debug session ID
        run_id: Debug run ID
        item_id: Item ID for logging
        asset_key: Asset key for logging
        quiet: If True, suppress progress output
        
    Returns:
        tuple: (success: bool, file_size: int, error_msg: str)
    """
    # #region agent log
    log_debug(session_id, run_id, "H", "download_geotiffs.py:download_with_progress",
              "Starting download", {"item_id": item_id, "asset_key": asset_key,
              "url_length": len(url), "output_path": str(output_path)})
    # #endregion agent log
    
    try:
        # Use urlretrieve which handles the download
        temp_path = str(output_path) + ".tmp"
        
        # Only show progress if in TTY and not quiet
        show_progress = is_tty() and not quiet
        
        def reporthook(block_num, block_size, total_size):
            """Simple progress reporter"""
            if show_progress and total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, (downloaded / total_size) * 100)
                if block_num % 20 == 0:  # Print every 20 blocks
                    print(f"    Progress: {percent:.1f}%", end='\r', flush=True)
        
        urlretrieve(url, temp_path, reporthook if show_progress else None)
        
        # Move temp file to final location
        os.rename(temp_path, output_path)
        
        file_size = os.path.getsize(output_path)
        print(f"    ✓ Downloaded: {format_file_size(file_size)}        ")
        
        # #region agent log
        log_debug(session_id, run_id, "I", "download_geotiffs.py:download_with_progress",
                  "Download successful", {"item_id": item_id, "asset_key": asset_key,
                  "file_size": file_size})
        # #endregion agent log
        
        return True, file_size, None
        
    except HTTPError as e:
        error_msg = f"HTTP Error {e.code}: {e.reason}"
        
        # #region agent log
        log_debug(session_id, run_id, "J", "download_geotiffs.py:download_with_progress",
                  "HTTP error during download", {"item_id": item_id, "asset_key": asset_key,
                  "http_code": e.code, "http_reason": e.reason, "url_preview": url[:100]})
        # #endregion agent log
        
        return False, 0, error_msg
    except URLError as e:
        error_msg = f"URL Error: {e.reason}"
        
        # #region agent log
        log_debug(session_id, run_id, "K", "download_geotiffs.py:download_with_progress",
                  "URL error during download", {"item_id": item_id, "asset_key": asset_key,
                  "error_reason": str(e.reason)})
        # #endregion agent log
        
        return False, 0, error_msg
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        
        # #region agent log
        log_debug(session_id, run_id, "L", "download_geotiffs.py:download_with_progress",
                  "Exception during download", {"item_id": item_id, "asset_key": asset_key,
                  "error_type": type(e).__name__, "error_message": str(e)})
        # #endregion agent log
        
        return False, 0, error_msg
    finally:
        # Clean up temp file if it exists
        temp_path = str(output_path) + ".tmp"
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass


def download_geotiffs(input_path, output_dir, bands=None, skip_existing=False, delay=0.5, quiet=False):
    """
    Download GeoTIFF files from the CSV.
    
    Args:
        input_path: Path to input CSV file
        output_dir: Directory to save downloaded files
        bands: List of specific bands to download, or None for all
        skip_existing: If True, skip files that already exist
        delay: Seconds to wait between downloads
        quiet: If True, suppress progress output
    """
    print(f"Reading input CSV: {input_path}")
    
    # Check if input file exists
    if not os.path.exists(input_path):
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)
    
    # Load CSV
    df = pd.read_csv(input_path)
    
    if df.empty:
        print("WARNING: Input CSV is empty!")
        return
    
    # Filter by bands if specified
    if bands:
        df = df[df['asset_key'].isin(bands)]
        print(f"  Filtered to bands: {', '.join(bands)}")
    
    print(f"  Total files to download: {len(df)}")
    print(f"  Unique acquisitions: {df['item_id'].nunique()}")
    
    # Connect to Planetary Computer STAC catalog
    print("\nConnecting to Planetary Computer STAC API...")
    catalog = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
    print("  ✓ Connected")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    print(f"\nOutput directory: {output_dir}")
    
    # Debug session tracking
    session_id = "debug-session"
    run_id = "run1"
    
    # #region agent log
    log_debug(session_id, run_id, "M", "download_geotiffs.py:download_geotiffs",
              "Starting download session", {"total_files": len(df), "unique_items": df['item_id'].nunique(),
              "bands": bands if bands else "all", "output_dir": str(output_dir)})
    # #endregion agent log
    
    # Statistics
    total_files = len(df)
    downloaded_count = 0
    skipped_count = 0
    failed_count = 0
    total_bytes = 0
    failed_files = []
    
    print("\n" + "="*80)
    print("Starting downloads...")
    print("="*80 + "\n")
    
    # Download each file
    for idx, row in df.iterrows():
        file_num = idx + 1
        filename = create_filename(row)
        output_path = Path(output_dir) / filename
        item_id = row['item_id']
        asset_key = row['asset_key']
        
        print(f"[{file_num}/{total_files}] {filename}")
        print(f"  Date: {row['datetime']}")
        print(f"  Band: {row['asset_key']} - {row['asset_title']}")
        print(f"  Cloud cover: {row['cloud_cover']:.2f}%")
        
        # Check if file already exists
        if skip_existing and output_path.exists():
            existing_size = os.path.getsize(output_path)
            print(f"  ⊗ Skipped: File exists ({format_file_size(existing_size)})")
            skipped_count += 1
        else:
            # Get fresh signed URL instead of using expired one from CSV
            print(f"  Getting fresh signed URL...")
            fresh_url, url_error = get_fresh_signed_url(item_id, asset_key, catalog, session_id, run_id)
            
            if fresh_url is None:
                failed_count += 1
                error_msg = url_error or "Could not retrieve fresh signed URL"
                failed_files.append((filename, error_msg))
                print(f"  ✗ Failed: {error_msg}")
            else:
                # Download the file using fresh URL
                success, file_size, error_msg = download_with_progress(
                    fresh_url, output_path, session_id, run_id, item_id, asset_key, quiet
                )
                
                if success:
                    downloaded_count += 1
                    total_bytes += file_size
                else:
                    failed_count += 1
                    failed_files.append((filename, error_msg))
                    print(f"  ✗ Failed: {error_msg}")
            
            # Delay between downloads to be nice to the server
            if file_num < total_files and delay > 0:
                time.sleep(delay)
        
        print()  # Blank line between files
    
    # Print summary
    print("="*80)
    print("Download Summary")
    print("="*80)
    print(f"Total files processed:  {total_files}")
    print(f"Successfully downloaded: {downloaded_count}")
    print(f"Skipped (existing):     {skipped_count}")
    print(f"Failed:                 {failed_count}")
    print(f"Total data downloaded:  {format_file_size(total_bytes)}")
    print(f"\nFiles saved to: {output_dir}")
    
    # Print failed files if any
    if failed_files:
        print("\n" + "="*80)
        print("Failed Downloads:")
        print("="*80)
        for filename, error_msg in failed_files:
            print(f"  - {filename}")
            print(f"    {error_msg}")
    
    print()


def main():
    """Main entry point."""
    args = parse_args()
    
    print("="*80)
    print("Sentinel-2 GeoTIFF Downloader")
    print("="*80)
    print()
    
    download_geotiffs(
        input_path=args.input,
        output_dir=args.output_dir,
        bands=args.bands,
        skip_existing=args.skip_existing,
        delay=args.delay,
        quiet=args.quiet or not is_tty()
    )


if __name__ == "__main__":
    main()

