#!/bin/bash

# Usage: /bin/bash grant_read_write_access_group.sh <PI> <shared_folder> <owner_user> <target_group>
# Example:
#   /bin/bash grant_read_write_access_group.sh elalib sharing/tree_ssl vincelf researchteam
#
# Grants read-write access (rwx) to target_group on the specified folder.

set -euo pipefail

PI="$1"
SHARED_FOLDER="$2"
OWNER="$3"
TARGET_GROUP="$4"

if [ "$#" -ne 4 ]; then
  echo "Usage: $0 <PI> <shared_folder> <owner_user> <target_group>"
  exit 1
fi

# check the group exists
if ! getent group "$TARGET_GROUP" >/dev/null; then
  echo "Error: group '$TARGET_GROUP' does not exist."
  exit 2
fi

BASE_PATH="/home/${OWNER}/projects/def-${PI}/${SHARED_FOLDER}"

echo "Granting read-write access to group '${TARGET_GROUP}' on '${BASE_PATH}'"

# Step 1: Allow path traversal (execute only) for group
setfacl -m g:${TARGET_GROUP}:x "/home/${OWNER}"

setfacl -m g:${TARGET_GROUP}:x "$(dirname "${BASE_PATH}")" 2>/dev/null || true

# Step 2: Give read + write + execute access to the target folder
setfacl -m g:${TARGET_GROUP}:rwx "${BASE_PATH}"
setfacl -m m:rwx "${BASE_PATH}"

# Step 3: Update existing files (read+write)
find "${BASE_PATH}" -type f -exec setfacl -m g:${TARGET_GROUP}:rw {} \;
find "${BASE_PATH}" -type f -exec setfacl -m m:rw {} \;

# Step 4: Update existing subdirectories (rwx)
find "${BASE_PATH}" -type d -exec setfacl -m g:${TARGET_GROUP}:rwx {} \;
find "${BASE_PATH}" -type d -exec setfacl -m m:rwx {} \;

# Step 5: Apply default ACLs so future files/dirs are writable
setfacl -d -m g:${TARGET_GROUP}:rwx "${BASE_PATH}"
setfacl -d -m m:rwx "${BASE_PATH}"

echo ":white_check_mark: Done. Group '${TARGET_GROUP}' has read-write access to '${BASE_PATH}'"
