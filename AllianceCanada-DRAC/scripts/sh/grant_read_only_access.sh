#!/bin/bash

# Usage: /bin/bash grant_read_only_access.sh <PI> <shared_folder> <owner_user> <target_user>
# Example: /bin/bash grant_read_only_access.sh elalib sharing vincelf jcarreau
# will give access (x) and read permission (r) to jcarreau at /home/vincelf/projects/def-elalib/sharing

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

echo ":closed_lock_with_key: Granting read-only access to '${TARGET_USER}' on '${BASE_PATH}'"

# Step 1: Allow path traversal to the shared folder
setfacl -m u:${TARGET_USER}:x /home/${OWNER}
if [ "$PI" == "$TARGET_USER" ]; then
  setfacl -m u:${TARGET_USER}:x /home/${OWNER}/projects/def-${PI}
fi

# Step 2: Give read + execute access to the shared folder
setfacl -m u:${TARGET_USER}:rx ${BASE_PATH}

# Step 3: Make existing files readable
find "${BASE_PATH}" -type f -exec setfacl -m u:${TARGET_USER}:r {} \;

# Step 4: Make existing subdirectories traversable
find "${BASE_PATH}" -type d -exec setfacl -m u:${TARGET_USER}:rx {} \;

# Step 5: Apply default ACLs so future files/dirs are readable
setfacl -d -m u:${TARGET_USER}:rx ${BASE_PATH}

echo ":white_check_mark: Done. '${TARGET_USER}' has read-only access to '${BASE_PATH}'"

