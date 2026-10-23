#!/usr/bin/env python3
"""
Script to rename the PPK files (.MRK, .NAV, .OBS, .RTK) of DJI M4E waypoint
missions to the name of their parent folder.

The RTK filename referenced in ppk_file_name.pbk is updated accordingly.

Every folder containing PPK files is processed, at any depth below the given directories.

Usage: python rename_wpt_ppk_files.py <mission_directory or flight_folder> [...]
"""

import os
import sys


EXTENSIONS = ['.MRK', '.NAV', '.OBS', '.RTK']
PBK_FILE = 'ppk_file_name.pbk'


def has_ppk_files(folder_path):
    """Return True if the folder directly contains at least one PPK file."""
    return any(os.path.splitext(f)[1].upper() in EXTENSIONS and os.path.isfile(os.path.join(folder_path, f))
               for f in os.listdir(folder_path))


def find_folders(folder):
    """Return the folder and its subfolders (recursively) that contain PPK files."""
    found = []
    for root, dirs, _ in os.walk(folder):
        dirs.sort()
        if has_ppk_files(root):
            found.append(root)
    return found


def process_folder(folder_path):
    """Find the files to rename in a single flight folder."""
    folder_name = os.path.basename(os.path.normpath(folder_path))
    print(f"\nProcessing folder: {folder_name}")
    print("-" * 60)

    renames = []
    for ext in EXTENSIONS:
        matching_files = [f for f in os.listdir(folder_path)
                          if os.path.splitext(f)[1].upper() == ext]
        if not matching_files:
            continue
        if len(matching_files) > 1:
            print(f"Warning: multiple {ext} files found ({', '.join(matching_files)}), skipping {ext}")
            continue

        old_name = matching_files[0]
        new_name = folder_name + os.path.splitext(old_name)[1]
        if old_name == new_name:
            continue
        if os.path.exists(os.path.join(folder_path, new_name)):
            print(f"Warning: {new_name} already exists, skipping {old_name}")
            continue
        renames.append((old_name, new_name))
        print(f"  {old_name} -> {new_name}")

    # The .pbk file references the RTK file, which must point to its final name
    pbk_content = None
    pbk_path = os.path.join(folder_path, PBK_FILE)
    if os.path.isfile(pbk_path):
        with open(pbk_path, 'r', encoding='utf-8') as f:
            content = f.read()
        rtk_name = folder_name + '.RTK'
        referenced_name = content.strip()
        if referenced_name != rtk_name and (
                any(old == referenced_name for old, _ in renames)
                or os.path.isfile(os.path.join(folder_path, rtk_name))):
            pbk_content = content.replace(referenced_name, rtk_name)
            print(f"  {PBK_FILE}: {referenced_name} -> {rtk_name}")

    if not renames and pbk_content is None:
        print("Nothing to rename.")
        return None

    return {
        'folder_path': folder_path,
        'renames': renames,
        'pbk_content': pbk_content
    }


def update_pbk_file(folder_path, pbk_content):
    """
    Rewrite the .pbk file with its new content. The file is often read-only, so a
    new file is written next to it and swapped in (only needs write access to the folder).
    """
    pbk_path = os.path.join(folder_path, PBK_FILE)
    tmp_path = pbk_path + '.tmp'
    mode = os.stat(pbk_path).st_mode
    with open(tmp_path, 'w', encoding='utf-8') as f:
        f.write(pbk_content)
    os.chmod(tmp_path, mode)
    os.replace(tmp_path, pbk_path)
    print(f"Updated: {PBK_FILE}")


def main():
    if len(sys.argv) > 1:
        base_folders = sys.argv[1:]
    else:
        base_folders = [input("Enter the path to the DJI mission directory (or a single flight folder): ")]

    for base_folder in base_folders:
        if not os.path.isdir(base_folder):
            raise NotADirectoryError(f"{base_folder} is not a valid directory")

    # Accept mission directories (searched recursively for flight folders) or single flight folders
    subfolders = []
    for base_folder in base_folders:
        subfolders.extend(find_folders(base_folder) or [base_folder])

    print(f"Found {len(subfolders)} folders to process")
    print("=" * 60)

    folders_to_process = []
    for subfolder in subfolders:
        result = process_folder(subfolder)
        if result:
            folders_to_process.append(result)

    if not folders_to_process:
        print("\nNo files to rename. Nothing to do.")
        sys.exit(0)

    # Summary of what will be done
    print("\n" + "=" * 60)
    print("SUMMARY OF ACTIONS")
    print("=" * 60)
    total_files = sum(len(f['renames']) for f in folders_to_process)
    total_pbk = sum(f['pbk_content'] is not None for f in folders_to_process)
    print(f"Folders to process: {len(folders_to_process)}")
    print(f"Total files to rename: {total_files}")
    print(f"Total {PBK_FILE} files to update: {total_pbk}")

    # Confirm action
    response = input("\nContinue? (yes/no): ")

    if response.lower() not in ['yes', 'y']:
        print("Operation cancelled.")
        sys.exit(0)

    print("\n" + "=" * 60)
    print("PROCESSING")
    print("=" * 60)

    for folder_info in folders_to_process:
        folder_path = folder_info['folder_path']
        print(f"\nProcessing: {os.path.basename(os.path.normpath(folder_path))}")
        for old_name, new_name in folder_info['renames']:
            os.rename(os.path.join(folder_path, old_name), os.path.join(folder_path, new_name))
            print(f"Renamed: {old_name} -> {new_name}")
        if folder_info['pbk_content'] is not None:
            update_pbk_file(folder_path, folder_info['pbk_content'])

    print("\n" + "=" * 60)
    print(f"Total files renamed: {total_files}")
    print("Operation completed successfully!")


if __name__ == "__main__":
    main()
