#!/usr/bin/env python3
"""
Script to clean timestamp files before PPK by removing photos without tag.
Removes all lines containing '-259200.000000' as the second field
and deletes the corresponding photos.

Usage: python clean_timestamp_photos.py <folder_path>
"""

import os
import sys
import glob
import re


def find_timestamp_file(folder_path):
    """Find the timestamp .MRK file in the folder."""
    mrk_files = glob.glob(os.path.join(folder_path, "*_Timestamp.MRK"))
    if not mrk_files:
        raise FileNotFoundError(f"No timestamp file found in {folder_path}")
    if len(mrk_files) > 1:
        raise ValueError(f"Multiple timestamp files found. Using: {mrk_files[0]}")
    return mrk_files[0]


def parse_timestamp_file(file_path):
    """
    Parse the timestamp file and identify lines to remove.
    Returns a tuple: (all_lines, lines_to_remove_indices, image_numbers_to_delete)
    """
    lines_to_remove = []
    image_numbers = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for idx, line in enumerate(lines):
        # Split by tabs or multiple spaces
        fields = re.split(r'\t+|\s{2,}', line.strip())
        
        # Check if the second field is '-259200.000000'
        if len(fields) >= 2 and fields[1] == '-259200.000000':
            lines_to_remove.append(idx)
            # First field is the line number (image number)
            image_numbers.append(int(fields[0]))
    
    return lines, lines_to_remove, image_numbers


def delete_images(folder_path, image_numbers):
    """
    Delete images corresponding to the given image numbers.
    Returns list of deleted files.
    """
    deleted_files = []
    for img_num in image_numbers:
        # Format with 4-digit zero padding
        # Pattern: *_NNNN_V.JPG where NNNN is the zero-padded image number
        pattern = os.path.join(folder_path, f"*_{img_num:04d}_V.JPG")
        matching_files = glob.glob(pattern)
        
        if matching_files:
            for img_path in matching_files:
                try:
                    os.remove(img_path)
                    img_filename = os.path.basename(img_path)
                    deleted_files.append(img_filename)
                    print(f"Deleted: {img_filename}")
                except Exception as e:
                    print(f"Error deleting {os.path.basename(img_path)}: {e}")
        else:
            print(f"Warning: No image found matching pattern *_{img_num:04d}_V.JPG")
    
    return deleted_files


def create_backup(file_path):
    """Create a backup of the original file."""
    backup_path = file_path + '.backup'
    counter = 1
    while os.path.exists(backup_path):
        backup_path = f"{file_path}.backup{counter}"
        counter += 1
    
    with open(file_path, 'r', encoding='utf-8') as src:
        with open(backup_path, 'w', encoding='utf-8') as dst:
            dst.write(src.read())
    
    print(f"Backup created: {backup_path}")
    return backup_path


def write_cleaned_file(file_path, lines, indices_to_remove):
    """Write the cleaned timestamp file without the specified lines."""
    with open(file_path, 'w', encoding='utf-8') as f:
        for idx, line in enumerate(lines):
            if idx not in indices_to_remove:
                f.write(line)


def process_folder(folder_path):
    """Process a single folder for timestamp cleaning."""
    print(f"\nProcessing folder: {folder_path}")
    print("-" * 60)
    
    # Find timestamp file
    try:
        timestamp_file = find_timestamp_file(folder_path)
        print(f"Found timestamp file: {os.path.basename(timestamp_file)}")
    except FileNotFoundError:
        print(f"No timestamp file found in {folder_path}, skipping...")
        return None
    
    # Parse timestamp file
    lines, lines_to_remove, image_numbers = parse_timestamp_file(timestamp_file)
    
    if not lines_to_remove:
        print("No lines with '-259200.000000' found. Nothing to do.")
        return None
    
    print(f"\nFound {len(lines_to_remove)} lines to remove:")
    for idx in lines_to_remove:
        print(f"  Line {idx + 1}: Image number {image_numbers[lines_to_remove.index(idx)]}")
    
    return {
        'folder_path': folder_path,
        'timestamp_file': timestamp_file,
        'lines': lines,
        'lines_to_remove': lines_to_remove,
        'image_numbers': image_numbers
    }


def main():
    base_folder = input("Enter the path to the DJI mission directory containing subfolders with photos: ")
    
    if not os.path.isdir(base_folder):
        raise NotADirectoryError(f"{base_folder} is not a valid directory")
    
    # Find all subfolders
    subfolders = [f.path for f in os.scandir(base_folder) if f.is_dir()]
    
    if not subfolders:
        print(f"No subfolders found in {base_folder}")
        sys.exit(0)
    
    print(f"Found {len(subfolders)} subfolders to process")
    print("=" * 60)
    
    # Process each subfolder to gather information
    folders_to_process = []
    for subfolder in subfolders:
        result = process_folder(subfolder)
        if result:
            folders_to_process.append(result)
    
    if not folders_to_process:
        print("\nNo folders with lines to clean. Nothing to do.")
        sys.exit(0)
    
    # Summary of what will be done
    print("\n" + "=" * 60)
    print("SUMMARY OF ACTIONS")
    print("=" * 60)
    total_lines = sum(len(f['lines_to_remove']) for f in folders_to_process)
    total_images = sum(len(f['image_numbers']) for f in folders_to_process)
    print(f"Folders to process: {len(folders_to_process)}")
    print(f"Total lines to remove: {total_lines}")
    print(f"Total images to delete: {total_images}")
    
    # Confirm action
    response = input("\nContinue? (yes/no): ")
    
    if response.lower() not in ['yes', 'y']:
        print("Operation cancelled.")
        sys.exit(0)
    
    # Process each folder
    print("\n" + "=" * 60)
    print("PROCESSING")
    print("=" * 60)
    
    for folder_info in folders_to_process:
        print(f"\nProcessing: {os.path.basename(folder_info['folder_path'])}")
        
        # Create backup
        backup_path = create_backup(folder_info['timestamp_file'])
        
        # Delete images
        print("Deleting images...")
        deleted_files = delete_images(folder_info['folder_path'], folder_info['image_numbers'])
        
        # Write cleaned timestamp file
        print("Updating timestamp file...")
        write_cleaned_file(folder_info['timestamp_file'], folder_info['lines'], folder_info['lines_to_remove'])
        
        print(f"  Lines removed: {len(folder_info['lines_to_remove'])}")
        print(f"  Images deleted: {len(deleted_files)}")
        print(f"  Backup: {os.path.basename(backup_path)}")
    
    # Final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"Folders processed: {len(folders_to_process)}")
    print(f"Total lines removed: {total_lines}")
    print(f"Total images deleted: {total_images}")
    print("\nOperation completed successfully!")


if __name__ == "__main__":
    main()
