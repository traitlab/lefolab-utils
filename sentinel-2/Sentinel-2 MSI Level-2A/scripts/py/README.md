# Sentinel-2 Level-2A STAC Script

Script to query and process Sentinel-2 MSI Level-2A data from Microsoft Planetary Computer STAC API.

## Setup with uv

This project uses `uv` for fast Python package management. Follow these steps to set up the environment:

### 1. Create virtual environment

```bash
uv venv -p python3.11 .venv/s2-postburn
```

### 2. Activate virtual environment

```bash
source .venv/s2-postburn/bin/activate
```

### 3. Install dependencies

```bash
uv pip install -r requirements.txt
```

### 4. Generate lock file (optional)

```bash
uv pip freeze > requirements.lock.txt
```

## Usage

This workflow consists of three scripts:

### 1. Query and Fetch Data

First, fetch Sentinel-2 data from the STAC API:

```bash
python3 sentinel-2-level2a-stac.py
```

This creates: `output/sentinel2_assets_AprOct_2022_2023_2024.csv`

### 2. Filter Best Acquisitions

Filter to keep only the best acquisition per ~30-day period:

```bash
python3 filter_best_acquisitions.py
```

This creates: `output/sentinel2_assets_filtered_monthly_best.csv`

**Options:**
- `--input <path>`: Custom input CSV path
- `--output <path>`: Custom output CSV path
- `--window-days <days>`: Window size (default: 30, uses monthly grouping)

**Selection criteria (priority order):**
1. Cloud cover (lowest first)
2. Processing baseline (newest first)
3. Platform (prefer Sentinel-2B over 2A)
4. Datetime (earliest if all else equal)

### 3. Download GeoTIFF Files

Download the filtered GeoTIFF files:

```bash
python3 download_geotiffs.py
```

This downloads files to: `downloads/`

**Options:**
- `--input <path>`: Custom input CSV path
- `--output-dir <path>`: Custom download directory
- `--bands B02 B03 B04`: Download only specific bands
- `--skip-existing`: Skip files that already exist
- `--delay <seconds>`: Delay between downloads (default: 0.5)

**Examples:**
```bash
# Download only RGB bands
python3 download_geotiffs.py --bands B02 B03 B04

# Resume interrupted download (skip existing files)
python3 download_geotiffs.py --skip-existing

# Faster downloads with less delay
python3 download_geotiffs.py --delay 0.1
```

## Requirements

- Python 3.11+
- uv (Python package manager)
- See `requirements.txt` for Python dependencies

## Installing uv

If you don't have `uv` installed:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv
```

## Notes

- The virtual environment is created in `.venv/s2-postburn/`
- The lock file (`requirements.lock.txt`) contains exact versions for reproducibility
- Make sure to activate the virtual environment before running the script

