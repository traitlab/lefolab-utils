# Globus Data Transfer with Environment Configuration

This directory contains scripts for transferring CHM files from NFS to DFDR collection using Globus SDK with environment-based configuration.

## Files

- `to_dfdr.py` - Original script with hardcoded configuration
- `to_dfdr_env.py` - Updated script that uses `.env` file for configuration
- `env_template.txt` - Template for environment configuration
- `requirements.txt` - Python dependencies

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create your `.env` file:**
   ```bash
   cp env_template.txt .env
   ```

3. **Configure your `.env` file:**
   Edit `.env` and fill in your actual values:
   - `SRC_ID`: Your source endpoint ID (lefocalcul endpoint)
   - `DST_ID`: Your destination endpoint ID (DFDR collection)
   - `GLOBUS_TOKEN_FILE`: Path to your Globus CLI tokens file
   - `FILE_PATTERN`: File pattern to match (e.g., `*CHM*.tif`)
   - Other settings as needed

4. **Authenticate with Globus:**
   ```bash
   globus login
   ```

## Usage

### Basic transfer:
```bash
python to_dfdr_env.py
```

### Dry run (see what would be transferred):
```bash
# Set DRY_RUN=true in .env file, or:
DRY_RUN=true python to_dfdr_env.py
```

### Verbose logging:
```bash
# Set VERBOSE_LOGGING=true in .env file, or:
VERBOSE_LOGGING=true python to_dfdr_env.py
```

## Configuration Options

### Required Settings
- `SRC_ID`: Source Globus endpoint ID
- `DST_ID`: Destination Globus endpoint ID
- `GLOBUS_TOKEN_FILE`: Path to Globus CLI tokens file

### File Filtering
- `FILE_PATTERN`: Glob pattern for files to transfer (default: `*CHM*.tif`)
- `MISSION_YEAR_LENGTH`: Length of year prefix in mission names (default: 4)

### Transfer Settings
- `TRANSFER_LABEL`: Label for the transfer task
- `SYNC_LEVEL`: Sync level (`checksum`, `mtime`, `size`, or `none`)
- `AUTO_ACTIVATE_ENDPOINTS`: Auto-activate endpoints (default: true)

### Optional Features
- `DRY_RUN`: Show what would be transferred without actually transferring
- `VERBOSE_LOGGING`: Enable detailed logging
- `MAX_FILES_PER_BATCH`: Maximum files per batch (default: 1000)
- `CREATE_DEST_DIRS`: Create destination directories if needed (default: true)

## Example .env File

```bash
# Globus endpoints
SRC_ID=your-source-endpoint-id
DST_ID=your-destination-endpoint-id

# File paths
SRC_ROOT=/mnt/nfs/conrad/labolaliberte_data/metashape
DST_PATH=/13/published/publication_974/submitted_data/Dataset/Photogrammetry_Products/
GLOBUS_TOKEN_FILE=~/.globus_cli_tokens.json

# File filtering
FILE_PATTERN=*CHM*.tif
MISSION_YEAR_LENGTH=4

# Transfer settings
TRANSFER_LABEL=CHM Upload
SYNC_LEVEL=checksum
AUTO_ACTIVATE_ENDPOINTS=true

# Optional settings
VERBOSE_LOGGING=true
DRY_RUN=false
```

## Troubleshooting

1. **Authentication errors**: Make sure you've run `globus login` and the token file exists
2. **Endpoint errors**: Verify your endpoint IDs are correct and accessible
3. **File not found**: Check that `SRC_ROOT` path exists and contains the expected directory structure
4. **Permission errors**: Ensure you have read access to source files and write access to destination
