#!/usr/bin/env python3
"""
Fully headless Globus transfer script using client credentials authentication.
This script can run completely without any human intervention.
"""

import os
import glob
import globus_sdk
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv("globus/.env")

# ------------------------
# CONFIGURATION FROM .ENV
# ------------------------
SRC_ID = os.getenv("SRC_ID", "SOURCE_ENDPOINT_ID")
DST_ID = os.getenv("DST_ID", "DEST_ENDPOINT_ID")
DST_PATH = os.getenv("DST_PATH", "/13/published/publication_974/submitted_data/Dataset/Photogrammetry_Products/")
SRC_ROOT = os.getenv("SRC_ROOT", "/mnt/nfs/conrad/labolaliberte_data/metashape")
GLOBUS_CLIENT_ID = os.getenv("GLOBUS_CLIENT_ID", "cf15eb47-ac2b-442a-9dfa-d9fe4d91cf98")
GLOBUS_CLIENT_SECRET = os.getenv("GLOBUS_CLIENT_SECRET", "")
GLOBUS_REFRESH_TOKEN = os.getenv("GLOBUS_REFRESH_TOKEN", "")
FILE_PATTERN = os.getenv("FILE_PATTERN", "*CHM*.tif")
MISSION_YEAR_LENGTH = int(os.getenv("MISSION_YEAR_LENGTH", "4"))
TRANSFER_LABEL = os.getenv("TRANSFER_LABEL", "CHM Upload")
SYNC_LEVEL = os.getenv("SYNC_LEVEL", "checksum")
AUTO_ACTIVATE_ENDPOINTS = os.getenv("AUTO_ACTIVATE_ENDPOINTS", "true").lower() == "true"
VERBOSE_LOGGING = os.getenv("VERBOSE_LOGGING", "true").lower() == "true"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
MAX_FILES_PER_BATCH = int(os.getenv("MAX_FILES_PER_BATCH", "1000"))
CREATE_DEST_DIRS = os.getenv("CREATE_DEST_DIRS", "true").lower() == "true"
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))

def log(message):
    """Log message if verbose logging is enabled"""
    if VERBOSE_LOGGING:
        print(message)

def validate_config():
    """Validate that required configuration is present"""
    if SRC_ID == "SOURCE_ENDPOINT_ID":
        raise ValueError("SRC_ID must be set in .env file")
    if DST_ID == "DEST_ENDPOINT_ID":
        raise ValueError("DST_ID must be set in .env file")

def setup_globus_client():
    """Set up Globus transfer client using headless authentication"""
    log("Setting up Globus authentication...")
    
    # Try refresh token first (most reliable for headless)
    if GLOBUS_REFRESH_TOKEN:
        log("Using refresh token for headless authentication...")
        try:
            client = globus_sdk.NativeAppAuthClient(GLOBUS_CLIENT_ID)
            authorizer = globus_sdk.RefreshTokenAuthorizer(
                GLOBUS_REFRESH_TOKEN,
                client
            )
            log("Authentication successful using refresh token!")
            return globus_sdk.TransferClient(authorizer=authorizer)
        except Exception as e:
            log(f"Refresh token authentication failed: {e}")
            log("Falling back to client credentials...")
    
    # Try client credentials (requires confidential app)
    if GLOBUS_CLIENT_SECRET:
        log("Using client credentials for headless authentication...")
        try:
            client = globus_sdk.ConfidentialAppAuthClient(GLOBUS_CLIENT_ID, GLOBUS_CLIENT_SECRET)
            authorizer = globus_sdk.ClientCredentialsAuthorizer(
                client,
                "urn:globus:auth:scope:transfer.api.globus.org:all"
            )
            log("Authentication successful using client credentials!")
            return globus_sdk.TransferClient(authorizer=authorizer)
        except Exception as e:
            log(f"Client credentials authentication failed: {e}")
    
    # If all else fails, provide instructions
    raise Exception("""
No valid authentication method found. Please set one of the following in your .env file:

1. GLOBUS_REFRESH_TOKEN=your-refresh-token (recommended)
   - Get this by running: python get_refresh_token.py
   - Then add the output to your .env file

2. GLOBUS_CLIENT_SECRET=your-client-secret (for confidential apps)
   - Register a confidential app in Globus Auth Developer Console
   - Use the client secret for headless authentication

For more information, see the README.md file.
""")

# ------------------------
# MAIN TRANSFER LOGIC
# ------------------------
def main():
    """Main transfer function"""
    try:
        # Validate configuration
        validate_config()
        
        # Set up Globus client
        tc = setup_globus_client()
        
        # Auto-activate endpoints if enabled
        if AUTO_ACTIVATE_ENDPOINTS:
            log("Auto-activating endpoints...")
            tc.endpoint_autoactivate(SRC_ID)
            tc.endpoint_autoactivate(DST_ID)
        
        # List missions on DFDR
        log("Listing missions in DFDR...")
        missions = []
        for entry in tc.operation_ls(DST_ID, path=DST_PATH):
            if entry["type"] == "dir":
                missions.append(entry["name"])
        log(f"Missions found in DFDR: {missions}")
        
        # Collect files to transfer
        log("Collecting files to transfer...")
        files_to_transfer = []
        
        for mission in missions:
            year = mission[:MISSION_YEAR_LENGTH]  # Extract year from mission name
            search_path = os.path.join(SRC_ROOT, year, mission, FILE_PATTERN)
            matching_files = glob.glob(search_path)
            
            if not matching_files:
                log(f"No files matching pattern '{FILE_PATTERN}' found for mission {mission}")
                continue
                
            for file_path in matching_files:
                dst = os.path.join(DST_PATH, mission, os.path.basename(file_path))
                files_to_transfer.append((file_path, dst))
                log(f"Found file: {file_path} -> {dst}")
        
        # Handle dry run mode
        if DRY_RUN:
            print(f"\nDRY RUN: Would transfer {len(files_to_transfer)} files:")
            for src, dst in files_to_transfer:
                print(f"  {src} -> {dst}")
            return
        
        # Submit transfer
        if not files_to_transfer:
            print("No files to transfer.")
        else:
            log(f"Submitting transfer of {len(files_to_transfer)} files...")
            tdata = globus_sdk.TransferData(
                tc, SRC_ID, DST_ID, 
                label=TRANSFER_LABEL, 
                sync_level=SYNC_LEVEL
            )
            
            for src, dst in files_to_transfer:
                tdata.add_item(src, dst)
            
            task = tc.submit_transfer(tdata)
            print(f"Submitted transfer task: {task['task_id']}")
            print(f"Monitor progress at: https://app.globus.org/activity/{task['task_id']}")
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
