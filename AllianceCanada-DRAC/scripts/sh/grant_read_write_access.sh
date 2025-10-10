#!/bin/bash

# Usage: /bin/bash grant_read_write_access.sh <PI> <shared_folder> <owner_user> <target_user>
# Example:
#   /bin/bash grant_read_write_access.sh elalib sharing/tree_ssl vincelf hugobaud
#   /bin/bash grant_read_write_access.sh elalib sharing/tree_ssl vincelf elalib
#
# Grants read-write access (rwx) to target_user on the specified folder.

set -e

PI="$1"
SHARED_FOLDER="$2"
OWNER="$3"
TARGET_USER="$4"

if [ "$#" -ne 4 ]; then
  echo "Usage: $0 <PI> <shared_folder> <owner_user> <target_user>"
  exit 1
fi

BASE_PATH="/home/${OWNER}/projects/def-${PI}/${SHARED_FOLDER}"

echo "Granting read-write access to '${TARGET_USER}' on '${BASE_PATH}'"

# Step 1: Allow path traversal (execute only)
setfacl -m u:${TARGET_USER}:x /home/${OWNER}
if [ "$PI" != "$TARGET_USER" ]; then
    setfacl -m u:${TARGET_USER}:x /home/${OWNER}/projects/def-${PI}
fi
setfacl -m u:${TARGET_USER}:x "$(dirname "${BASE_PATH}")" 2>/dev/null || true

# Step 2: Give read + write + execute access to the target folder
setfacl -m u:${TARGET_USER}:rwx "${BASE_PATH}"
setfacl -m m:rwx "${BASE_PATH}"   # ensure mask allows rwx

# Step 3: Update existing files (read+write)
find "${BASE_PATH}" -type f -exec setfacl -m u:${TARGET_USER}:rw {} \;
find "${BASE_PATH}" -type f -exec setfacl -m m:rw {} \;

# Step 4: Update existing subdirectories (rwx)
find "${BASE_PATH}" -type d -exec setfacl -m u:${TARGET_USER}:rwx {} \;
find "${BASE_PATH}" -type d -exec setfacl -m m:rwx {} \;

# Step 5: Apply default ACLs so future files/dirs are writable
setfacl -d -m u:${TARGET_USER}:rwx "${BASE_PATH}"
setfacl -d -m m:rwx "${BASE_PATH}"

echo ":white_check_mark: Done. '${TARGET_USER}' has read-write access to '${BASE_PATH}'"
