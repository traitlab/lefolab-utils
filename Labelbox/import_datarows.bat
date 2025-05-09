@echo off
setlocal EnableDelayedExpansion

:: List of mission IDs to process
set missions=20250425_tbschorongo_wptno_m3e 20250426_tbschichico_wptoeste_m3e 20250427_tbschichico_wpteste_m3e 20250427_tbschichico_wptnorte_m3e 20250427_tbschorongo_wptne_m3e

:: Project name
set project=2025_tiputini

:: Loop through each mission
for %%m in (%missions%) do (
    echo Processing mission: %%m
    python import_datarows.py --mission_id %%m --project %project%
    echo.
)

echo All missions processed.
pause