# Globus Data Transfer with Environment Configuration

This directory contains scripts for transferring CHM files from NFS to DFDR collection using Globus SDK with modern OAuth authentication and environment-based configuration.

## Files

- `to_dfdr.py` - Main script with OAuth authentication and `.env` configuration
- `env_template.txt` - Template for environment configuration
- `requirements.txt` - Python dependencies

## Setup

### 1. Create and Activate Virtual Environment (Recommended)

It's recommended to use a virtual environment to isolate the project dependencies:

```bash
# Create virtual environment
python3 -m venv globus-env

# Activate virtual environment
source globus-env/bin/activate

# Verify activation (you should see (globus-env) in your prompt)
which python
```

To deactivate the virtual environment later:
```bash
deactivate
```

### 2. Install Dependencies
```bash
# Make sure virtual environment is activated
pip install -r requirements.txt
```

### 3. Install Globus CLI (Global Installation)

The Globus CLI is used for authentication and can be installed globally on the system:

```bash
# Install Globus CLI globally
sudo pip install globus-cli

# Or if pip is not available, try:
python3 -m pip install --user globus-cli

# Verify installation
globus version
```

**Alternative installation methods:**
```bash
# Via snap (if available)
sudo snap install globus-cli

# Via conda (if available)
conda install -c conda-forge globus-cli
```

### 4. Authenticate with Globus CLI
```bash
# Login to Globus (this will open a browser for authentication)
globus login

# Verify you're logged in
globus whoami

# Logout when needed
globus logout
```

**Note:** The script uses OAuth2 authentication directly, but having the CLI installed and logged in can be helpful for testing endpoints and troubleshooting.

### 5. Register a Globus Auth App

Before using the script, you need to register your own application in Globus Auth:

1. **Navigate to the Globus Auth Developer Console:**
   - Go to [https://auth.globus.org/v2/web/developers](https://auth.globus.org/v2/web/developers)
   - Log in with your Globus account

2. **Create a New Native App:**
   - Click "Add New App"
   - Select "Register a thick client or script that will be installed and run by users on their devices"
   - Create or select a project (if you don't have one, you'll be prompted to create it)
   - Give your app a name (e.g., "Lefolab Data Transfer")
   - Click "Register App"

3. **Configure Your App:**
   - **Redirect URIs**: `https://auth.globus.org/v2/web/auth-code`
   - **Required Identity**: Globus ID
   - **Pre-select Identity Provider**: Globus ID
   - **Use effective identity**: Selected

4. **Copy Your Client ID:**
   - Copy the "Client UUID" from the app page
   - This is your `GLOBUS_CLIENT_ID` that you'll use in the configuration

For more detailed instructions, see the [official Globus SDK documentation](https://globus-sdk-python.readthedocs.io/en/stable/user_guide/getting_started/register_app.html).

### 6. Create Your Configuration File
```bash
cp env_template.txt .env
```

### 7. Configure Your `.env` File
Edit `.env` and fill in your actual values:
- `SRC_ID`: Your source endpoint ID (lefocalcul endpoint)
- `DST_ID`: Your destination endpoint ID (DFDR collection)
- `GLOBUS_CLIENT_ID`: Your registered app's client ID from step 5
- `FILE_PATTERN`: File pattern to match (e.g., `*CHM*.tif`)
- Other settings as needed

## Usage

### Activate Virtual Environment (if using one):
```bash
# Activate the virtual environment
source globus-env/bin/activate

# Verify you're in the virtual environment
which python
```

### Basic Transfer:
```bash
python to_dfdr.py
```

The script will:
1. Prompt you to authorize the application in your browser
2. Ask for the authorization code
3. Authenticate with Globus using OAuth2
4. List missions in the destination endpoint
5. Find matching files and transfer them

### Dry Run (see what would be transferred):
```bash
# Set DRY_RUN=true in .env file, or:
DRY_RUN=true python to_dfdr.py
```

### Verbose Logging:
```bash
# Set VERBOSE_LOGGING=true in .env file, or:
VERBOSE_LOGGING=true python to_dfdr.py
```

## Configuration Options

### Required Settings
- `SRC_ID`: Source Globus endpoint ID
- `DST_ID`: Destination Globus endpoint ID
- `GLOBUS_CLIENT_ID`: Your registered Globus Auth app's client ID

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

# Globus authentication
GLOBUS_CLIENT_ID=your-globus-client-id-here

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

1. **Virtual Environment Issues**:
   - Make sure the virtual environment is activated: `source globus-env/bin/activate`
   - Verify Python path: `which python` should show the venv path
   - If packages are missing, reinstall: `pip install -r requirements.txt`

2. **Globus CLI Installation Issues**:
   - If `sudo pip install globus-cli` fails, try: `python3 -m pip install --user globus-cli`
   - Add user bin to PATH: `export PATH="$HOME/.local/bin:$PATH"`
   - Verify installation: `globus version`

3. **Authentication errors**: 
   - Make sure you've registered your app in [Globus Auth Developer Console](https://auth.globus.org/v2/web/developers)
   - Verify your `GLOBUS_CLIENT_ID` is correct in the `.env` file
   - If authorization code fails, get a fresh one from the browser
   - Test CLI login: `globus login` and `globus whoami`

4. **Endpoint errors**: 
   - Verify your endpoint IDs are correct and accessible
   - Test with CLI: `globus endpoint search --filter-scope=recently-used`

5. **File not found**: Check that `SRC_ROOT` path exists and contains the expected directory structure

6. **Permission errors**: Ensure you have read access to source files and write access to destination

7. **OAuth flow issues**: Make sure your app is configured with the correct redirect URI: `https://auth.globus.org/v2/web/auth-code`

## References

- [Globus SDK Python Documentation](https://globus-sdk-python.readthedocs.io/)
- [Register an App in Globus Auth](https://globus-sdk-python.readthedocs.io/en/stable/user_guide/getting_started/register_app.html)
- [Globus Auth Developer Console](https://auth.globus.org/v2/web/developers)
