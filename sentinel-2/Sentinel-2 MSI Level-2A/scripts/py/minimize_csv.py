#!/usr/bin/env python3
"""
Minimize Sentinel-2 CSV Output

This script reduces a CSV file to only the essential columns:
- datetime: Date and time of acquisition
- cloud_cover: Cloud cover percentage
- item_id: Product ID
- asset_key: Band identifier

Usage:
    python minimize_csv.py [input_file] [output_file]

Arguments:
    input_file:  Path to the input CSV file (default: output/sentinel2_assets_filtered_monthly_best.csv)
    output_file: Path to the output CSV file (default: output/sentinel2_assets_filtered_monthly_best_minimal.csv)

Examples:
    # Use default file paths
    python minimize_csv.py

    # Specify custom input and output files
    python minimize_csv.py input.csv output.csv

    # Specify only input file (output will be input_minimal.csv)
    python minimize_csv.py input.csv
"""

import csv
import sys
import os
from pathlib import Path


def minimize_csv(input_file, output_file):
    """
    Minimize CSV file to only essential columns.

    Args:
        input_file: Path to input CSV file
        output_file: Path to output CSV file
    """
    # Columns to keep in the minimized CSV
    columns_to_keep = ['datetime', 'cloud_cover', 'item_id', 'asset_key']

    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)

    # Read input CSV and write minimized output
    try:
        with open(input_file, 'r', encoding='utf-8') as infile, \
             open(output_file, 'w', encoding='utf-8', newline='') as outfile:
            
            reader = csv.DictReader(infile)
            
            # Verify required columns exist
            missing_columns = [col for col in columns_to_keep if col not in reader.fieldnames]
            if missing_columns:
                print(f"Error: Missing required columns in input file: {', '.join(missing_columns)}")
                print(f"Available columns: {', '.join(reader.fieldnames)}")
                sys.exit(1)
            
            writer = csv.DictWriter(outfile, fieldnames=columns_to_keep)
            writer.writeheader()
            
            row_count = 0
            for row in reader:
                # Only write the columns we want to keep
                filtered_row = {col: row[col] for col in columns_to_keep}
                writer.writerow(filtered_row)
                row_count += 1
        
        print(f"✓ Successfully created minimized CSV: {output_file}")
        print(f"  Processed {row_count} rows")
        print(f"  Columns kept: {', '.join(columns_to_keep)}")
        
    except Exception as e:
        print(f"Error processing CSV: {e}")
        sys.exit(1)


def main():
    """Main function to handle command-line arguments and execute CSV minimization."""
    # Get script directory to set default paths relative to script location
    script_dir = Path(__file__).parent
    default_input = script_dir / 'output' / 'sentinel2_assets_filtered_monthly_best.csv'
    default_output = script_dir / 'output' / 'sentinel2_assets_filtered_monthly_best_minimal.csv'
    
    # Parse command-line arguments
    if len(sys.argv) == 1:
        # No arguments: use defaults
        input_file = str(default_input)
        output_file = str(default_output)
    elif len(sys.argv) == 2:
        # One argument: input file only
        input_file = sys.argv[1]
        # Generate output filename from input
        input_path = Path(input_file)
        output_file = str(input_path.parent / f"{input_path.stem}_minimal{input_path.suffix}")
    elif len(sys.argv) == 3:
        # Two arguments: input and output files
        input_file = sys.argv[1]
        output_file = sys.argv[2]
    else:
        print("Error: Too many arguments")
        print(__doc__)
        sys.exit(1)
    
    # Convert to absolute paths
    input_file = os.path.abspath(input_file)
    output_file = os.path.abspath(output_file)
    
    print(f"Input file:  {input_file}")
    print(f"Output file: {output_file}")
    print()
    
    # Execute CSV minimization
    minimize_csv(input_file, output_file)


if __name__ == '__main__':
    main()

