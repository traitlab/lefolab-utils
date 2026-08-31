"""
check_sftp_sync.py
Checks that local YYYYMMDD_site_sensor folders are present on the SFTP server,
with all their files/subfolders and the same sizes.
"""

import os
import re
import argparse
import paramiko
import getpass
import keyring
from pathlib import Path
from collections import defaultdict

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
LOCAL_ROOT   = r"C:\path\to\local\folders"      # ← edit
REMOTE_ROOT  = "data/drone_missions"            # ← edit if needed
SFTP_HOST    = "sftp.example.com"               # ← edit
SFTP_PORT    = 22
SFTP_USER    = "username"                       # ← edit
KEYRING_SERVICE = "check_sftp_sync"             # key under which the password is stored
# ──────────────────────────────────────────────────────────────────────────────

KEYRING_ACCOUNT = f"{SFTP_USER}@{SFTP_HOST}"    # keyring entry for the config above
FOLDER_PATTERN  = re.compile(r"^\d{8}_.+_.+$")


def delete_saved_password():
    """Removes the stored password for the configured user/host (run with -d)."""
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
        print(f"Password deleted for {KEYRING_ACCOUNT}.")
    except keyring.errors.PasswordDeleteError:
        print(f"No password stored for {KEYRING_ACCOUNT}.")


def get_local_tree(folder_path: Path) -> dict[str, int]:
    """Returns {relative_path: size} for every file under folder_path."""
    tree = {}
    for root, _, files in os.walk(folder_path):
        for f in files:
            full = Path(root) / f
            rel  = full.relative_to(folder_path).as_posix()
            tree[rel] = full.stat().st_size
    return tree


def get_remote_tree(sftp, remote_path: str) -> dict[str, int]:
    """Returns {relative_path: size} for every file under remote_path via SFTP."""
    tree = {}

    def walk(path, prefix=""):
        try:
            entries = sftp.listdir_attr(path)
        except FileNotFoundError:
            return
        for entry in entries:
            rel  = f"{prefix}{entry.filename}" if not prefix else f"{prefix}/{entry.filename}"
            full = f"{path}/{entry.filename}"
            import stat
            if stat.S_ISDIR(entry.st_mode):
                walk(full, rel)
            else:
                tree[rel] = entry.st_size

    walk(remote_path)
    return tree


def compare(local_tree: dict, remote_tree: dict) -> dict:
    """Compares two trees and returns the differences."""
    local_files  = set(local_tree.keys())
    remote_files = set(remote_tree.keys())

    missing_on_remote = local_files - remote_files
    extra_on_remote   = remote_files - local_files
    size_mismatch     = {
        f for f in local_files & remote_files
        if local_tree[f] != remote_tree[f]
    }

    return {
        "missing":  sorted(missing_on_remote),
        "extra":    sorted(extra_on_remote),
        "mismatch": sorted(size_mismatch),
    }


def format_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def main():
    local_root = Path(LOCAL_ROOT)

    # Find local mission folders
    missions = sorted([
        d for d in local_root.iterdir()
        if d.is_dir() and FOLDER_PATTERN.match(d.name)
    ])

    if not missions:
        print("No mission folder found in", LOCAL_ROOT)
        return

    print(f"{len(missions)} local mission folder(s) found.\n")

    # Password is stored in the OS keyring (Windows Credential Manager, macOS
    # Keychain, Linux Secret Service) and only prompted for the first time.
    password = keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
    if password is None:
        password = getpass.getpass(f"SFTP password for {KEYRING_ACCOUNT}: ")
        keyring.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, password)

    # SFTP connection
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SFTP_HOST, port=SFTP_PORT, username=SFTP_USER, password=password)
    sftp = ssh.open_sftp()
    print("Connected to the SFTP server.\n")

    summary = defaultdict(list)

    for mission in missions:
        year        = mission.name[:4]
        remote_path = f"{REMOTE_ROOT}/{year}/{mission.name}"

        print(f"── {mission.name}")

        # Check that the remote folder exists
        try:
            sftp.stat(remote_path)
        except FileNotFoundError:
            print(f"   ✗ FOLDER MISSING on the server ({remote_path})\n")
            summary["absent"].append(mission.name)
            continue

        local_tree  = get_local_tree(mission)
        remote_tree = get_remote_tree(sftp, remote_path)
        diff        = compare(local_tree, remote_tree)

        has_issues = any(diff.values())

        if not has_issues:
            print(f"   ✓ OK — {len(local_tree)} file(s), identical sizes\n")
            summary["ok"].append(mission.name)
        else:
            summary["issues"].append(mission.name)

            if diff["missing"]:
                print(f"   ✗ Files missing on the server ({len(diff['missing'])}):")
                for f in diff["missing"]:
                    print(f"      - {f}  ({format_size(local_tree[f])})")

            if diff["mismatch"]:
                print(f"   ⚠ Size mismatches ({len(diff['mismatch'])}):")
                for f in diff["mismatch"]:
                    print(f"      - {f}  local={format_size(local_tree[f])}  "
                          f"remote={format_size(remote_tree[f])}")

            if diff["extra"]:
                print(f"   ℹ Extra files on the server ({len(diff['extra'])}):")
                for f in diff["extra"]:
                    print(f"      - {f}")
            print()

    sftp.close()
    ssh.close()

    # Final summary
    print("═" * 50)
    print("SUMMARY")
    print(f"  ✓ OK          : {len(summary['ok'])}")
    print(f"  ✗ Missing     : {len(summary['absent'])}")
    print(f"  ⚠ Differences : {len(summary['issues'])}")
    if summary["absent"]:
        print("\nMissing folders:", ", ".join(summary["absent"]))
    if summary["issues"]:
        print("Folders with differences:", ", ".join(summary["issues"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-d", "--delete-password", action="store_true",
        help="delete the saved SFTP password from the OS keyring and exit",
    )
    if parser.parse_args().delete_password:
        delete_saved_password()
    else:
        main()
