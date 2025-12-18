#!/usr/bin/env python3
"""
Filter Sentinel-2 acquisitions to keep only the best one per ~30-day period.

This script reads the CSV output from sentinel-2-level2a-stac.py and filters it
to retain only the highest-quality acquisitions at approximately monthly intervals.

Selection criteria (priority order):
1. Cloud cover (lowest first)
2. Processing baseline (newest first, extracted from item_id)
3. Platform (prefer Sentinel-2B over Sentinel-2A)
4. Datetime (earliest if all else equal)

Usage:
    python filter_best_acquisitions.py
    python filter_best_acquisitions.py --input custom_input.csv --output custom_output.csv
"""

import pandas as pd
import argparse
import os
import sys
from pathlib import Path


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Filter Sentinel-2 acquisitions to keep best per ~30-day period"
    )
    
    # Get script directory for default paths
    script_dir = Path(__file__).parent
    default_input = script_dir / "output" / "sentinel2_assets_AprOct_2022_2023_2024.csv"
    default_output = script_dir / "output" / "sentinel2_assets_filtered_monthly_best.csv"
    
    parser.add_argument(
        "--input",
        type=str,
        default=str(default_input),
        help=f"Input CSV file path (default: {default_input})"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default=str(default_output),
        help=f"Output CSV file path (default: {default_output})"
    )
    
    parser.add_argument(
        "--window-days",
        type=int,
        default=30,
        help="Approximate days per window (default: 30, uses monthly grouping)"
    )
    
    return parser.parse_args()


def extract_processing_baseline(item_id):
    """
    Extract processing baseline number from Sentinel-2 item_id.
    
    Example: S2A_MSIL2A_20220406T192921_R142_T10VEP_20240604T041926
             Contains _N0510_ for processing baseline 510
    
    Args:
        item_id: Sentinel-2 item identifier string
    
    Returns:
        int: Processing baseline number, or -1 if not found
    """
    import re
    match = re.search(r'_N(\d{4})_', str(item_id))
    if match:
        return int(match.group(1))
    return -1


def platform_priority(platform):
    """
    Assign priority value for platform preference.
    
    Args:
        platform: Platform name (e.g., 'Sentinel-2B', 'Sentinel-2A')
    
    Returns:
        int: Priority value (higher is better)
    """
    if platform == 'Sentinel-2B':
        return 2
    elif platform == 'Sentinel-2A':
        return 1
    else:
        return 0


def filter_best_acquisitions(input_path, output_path, window_days=30):
    """
    Filter acquisitions to keep only the best one per ~30-day period.
    
    Args:
        input_path: Path to input CSV file
        output_path: Path to output CSV file
        window_days: Approximate window size in days (uses monthly grouping)
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
    
    print(f"  Loaded {len(df)} rows")
    print(f"  Unique acquisitions (item_id): {df['item_id'].nunique()}")
    
    # Parse datetime
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    # Extract processing baseline from item_id
    print("\nExtracting processing baseline from item_id...")
    df['processing_baseline'] = df['item_id'].apply(extract_processing_baseline)
    
    # Add platform priority
    df['platform_priority'] = df['platform'].apply(platform_priority)
    
    # Create year-month grouping key for ~30-day windows
    df['year_month'] = df['datetime'].dt.to_period('M')
    
    print(f"\nTime periods found:")
    period_counts = df.groupby('year_month')['item_id'].nunique().sort_index()
    for period, count in period_counts.items():
        print(f"  {period}: {count} unique acquisitions")
    
    print("\nSelecting best acquisition per period...")
    
    # For each year-month period, find the best item_id
    # Sort by: cloud_cover (asc), processing_baseline (desc), platform_priority (desc), datetime (asc)
    df_sorted = df.sort_values(
        by=['year_month', 'cloud_cover', 'processing_baseline', 'platform_priority', 'datetime'],
        ascending=[True, True, False, False, True],
        kind='mergesort'  # Stable sort for consistent results
    )
    
    # Get the first (best) unique item_id for each year-month period
    best_items_per_period = df_sorted.drop_duplicates(
        subset=['year_month'], 
        keep='first'
    )[['year_month', 'item_id', 'datetime', 'cloud_cover', 'platform', 'processing_baseline']]
    
    print("\nSelected acquisitions:")
    print("="*80)
    for _, row in best_items_per_period.iterrows():
        print(f"  {row['year_month']} | {row['datetime'].date()} | Cloud: {row['cloud_cover']:5.2f}% | "
              f"{row['platform']:12s} | Proc: N{row['processing_baseline']:04d}")
    print("="*80)
    
    # Create a set of selected item_ids
    selected_item_ids = set(best_items_per_period['item_id'])
    
    # Filter original dataframe to keep all bands of selected items
    df_filtered = df[df['item_id'].isin(selected_item_ids)].copy()
    
    # Drop temporary columns
    df_filtered = df_filtered.drop(columns=['processing_baseline', 'platform_priority', 'year_month'])
    
    # Sort by datetime and asset_key for consistent output
    df_filtered = df_filtered.sort_values(
        by=['datetime', 'asset_key'],
        ascending=[True, True]
    )
    
    print(f"\nFiltered from {df['item_id'].nunique()} to {df_filtered['item_id'].nunique()} acquisitions")
    print(f"Output rows: {len(df_filtered)} (including all bands)")
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    # Write filtered CSV
    df_filtered.to_csv(output_path, index=False)
    print(f"\n✓ Wrote filtered data to: {output_path}")
    
    # Print summary statistics
    print("\n" + "="*80)
    print("Summary Statistics:")
    print("="*80)
    print(f"Total acquisitions selected: {df_filtered['item_id'].nunique()}")
    print(f"Date range: {df_filtered['datetime'].min().date()} to {df_filtered['datetime'].max().date()}")
    print(f"Cloud cover range: {df_filtered['cloud_cover'].min():.2f}% to {df_filtered['cloud_cover'].max():.2f}%")
    print(f"Average cloud cover: {df_filtered['cloud_cover'].mean():.2f}%")
    print(f"\nPlatform distribution:")
    platform_counts = df_filtered.drop_duplicates('item_id')['platform'].value_counts()
    for platform, count in platform_counts.items():
        print(f"  {platform}: {count} acquisitions")


def main():
    """Main entry point."""
    args = parse_args()
    
    print("="*80)
    print("Sentinel-2 Best Acquisition Filter")
    print("="*80)
    print(f"Window strategy: Monthly intervals (~30 days)")
    print(f"Selection priority: Cloud cover > Processing baseline > Platform > Date")
    print()
    
    filter_best_acquisitions(
        input_path=args.input,
        output_path=args.output,
        window_days=args.window_days
    )


if __name__ == "__main__":
    main()

