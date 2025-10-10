#!/bin/bash

# requires .env file 
# REMOTE_HOST="u497507.your-storagebox.de"
# REMOTE_USER="u497507"
# REMOTE_PATH="share-hugo"
# LOCAL_DEST="/mnt/ceph/def-elalib-ivado/ivado/dataset/deadtrees.earth/3034orthos"

# requires .config/rclone/rclone.conf file
# Example rclone config (obfuscated sensitive info, do not use in production)
# [u497507_yourstoragebox_de]
# type = sftp
# host = u497507.your-storagebox.de
# user = u497507
# port = 22
# pass = <OBFUSCATED_PASSWORD>
# md5sum_command = none
# sha1sum_command = none

echo "# -----------------------------------------------------------------------"
echo "script $0 $@"

set -o pipefail
set -o errexit
set -o nounset

date

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
source "${SCRIPT_DIR}/.env/download_orthophotos_aoi.env.sh"
source "${SCRIPT_DIR}/lib/lib_utils.sh"

SERVICE_NAME="download_orthophotos_aoi"

# Create destination directory
mkdir -p "$LOCAL_DEST"

# Log start
log ${SERVICE_NAME} "INFO" "Starting SFTP download from $REMOTE_USER@$REMOTE_HOST"
log ${SERVICE_NAME} "INFO" "Remote path: $REMOTE_PATH"
log ${SERVICE_NAME} "INFO" "Local destination: $LOCAL_DEST"

# Use existing rclone config with stored password
rclone copy "u497507_yourstoragebox_de:${REMOTE_PATH}" "${LOCAL_DEST}" \
  --progress \
  --transfers=4 \
  --checkers=8 \
  --retries=3 \
  --low-level-retries=10 \
  --stats=30s

# Log completion
log ${SERVICE_NAME} "INFO" "Download completed"

date
echo "# -----------------------------------------------------------------------"
exit 0