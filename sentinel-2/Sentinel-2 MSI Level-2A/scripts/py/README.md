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

After setting up the environment, run the script:

```bash
python sentinel-2-level2a-stac.py
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

