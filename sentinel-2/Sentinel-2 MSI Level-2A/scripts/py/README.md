# Sentinel-2 Level-2A STAC Script

Query and process Sentinel-2 MSI Level-2A data from Microsoft Planetary Computer STAC API.

## Installation

Install `uv` (Python package manager):

```bash
# System-wide installation (for servers, requires sudo)
curl -LsSf https://astral.sh/uv/install.sh | sudo sh

# User-specific installation (default: ~/.local/bin)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After installation, ensure `uv` is in PATH:
```bash
# Add to PATH if needed (for user install)
export PATH="$HOME/.local/bin:$PATH"

# Or add to ~/.bashrc for persistence
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

Setup environment:

```bash
uv venv -p python3.11 .venv/s2-postburn
source .venv/s2-postburn/bin/activate
uv pip install -r requirements.txt
```

## Usage

### 1. Query and Fetch Data

```bash
python3 sentinel-2-level2a-stac.py
```

Output: `output/sentinel2_assets_AprOct_2022_2023_2024.csv`

### 2. Filter Best Acquisitions

```bash
python3 filter_best_acquisitions.py
```

Output: `output/sentinel2_assets_filtered_monthly_best.csv`

Options:
- `--input <path>`: Custom input CSV path
- `--output <path>`: Custom output CSV path
- `--window-days <days>`: Window size (default: 30)

Selection criteria (priority): Cloud cover → Processing baseline → Platform → Datetime

### 3. Download GeoTIFF Files

```bash
python3 download_geotiffs.py
python3 download_geotiffs.py --bands B02 B03 B04
python3 download_geotiffs.py --skip-existing
python3 download_geotiffs.py --delay 0.1
```

Output: `downloads/`

Options:
- `--input <path>`: Custom input CSV path
- `--output-dir <path>`: Custom download directory
- `--bands B02 B03 B04`: Download only specific bands
- `--skip-existing`: Skip files that already exist
- `--delay <seconds>`: Delay between downloads (default: 0.5)
- `--quiet`: Suppress progress output (automatically enabled when logging to file)

**Run in background with logging (survives SSH disconnection):**
```bash
cd "/app/lefolab-utils/sentinel-2/Sentinel-2 MSI Level-2A/scripts/py"
mkdir -p log
LOG_FILE="log/download_geotiffs-$(date +%Y%m%dT%H%M%S).log"
nohup python3 download_geotiffs.py --skip-existing --quiet --output-dir "/data/lefolab/sentinel-2/Sentinel-2 MSI Level-2A/ScottyCreek" > "$LOG_FILE" 2>&1 &
echo "Process started. Log file: $LOG_FILE"
echo "PID: $!"
```

**Monitor progress:**
```bash
# View latest log in real-time
tail -f log/download_geotiffs-*.log
less log/download_geotiffs-*.log

# Check if process is running
ps aux | grep download_geotiffs

# Check process status by PID (replace PID with actual process ID)
ps -p <PID> -o pid,cmd,etime,stat
```

## Requirements

- Python 3.11+
- uv package manager
- See `requirements.txt` for dependencies

