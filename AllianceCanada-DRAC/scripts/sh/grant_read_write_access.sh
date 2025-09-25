#!/bin/bash

# Usage: /bin/bash grant_read_write_access.sh <PI> <shared_folder> <owner_user> <target_user>
# Example: /bin/bash grant_readwrite_access.sh elalib sharing/tree_ssl vincelf hugobaud
# will give read-write access (rw) to hugobaud at /home/vincelf/projects/def-elalib/sharing/tree_ssl

# Exit on any error
set -e

# Parse arguments
PI="$1"
SHARED_FOLDER="$2"
OWNER="$3"
TARGET_USER="$4"

# Validate input
if [ "$#" -ne 4 ]; then
  echo "Usage: $0 <PI> <shared_folder> <owner_user> <target_user>"
  exit 1
fi

# Construct the full path
BASE_PATH="/home/${OWNER}/projects/def-${PI}/${SHARED_FOLDER}"

echo ":closed_lock_with_key: Granting read-write access to '${TARGET_USER}' on '${BASE_PATH}'"

# Step 1: Allow path traversal (no read/write, just execute to traverse)
setfacl -m u:${TARGET_USER}:x /home/${OWNER}
setfacl -m u:${TARGET_USER}:x /home/${OWNER}/projects/def-${PI}

# Step 2: Give read + write + execute access to the shared folder
setfacl -m u:${TARGET_USER}:rwx ${BASE_PATH}

# Step 3: Make existing files readable & writable
find "${BASE_PATH}" -type f -exec setfacl -m u:${TARGET_USER}:rw {} \;

# Step 4: Make existing subdirectories traversable + writable
find "${BASE_PATH}" -type d -exec setfacl -m u:${TARGET_USER}:rwx {} \;

# Step 5: Apply default ACLs so future files/dirs are writable
setfacl -d -m u:${TARGET_USER}:rwx ${BASE_PATH}

echo ":white_check_mark: Done. '${TARGET_USER}' has read-write access to '${BASE_PATH}'"
