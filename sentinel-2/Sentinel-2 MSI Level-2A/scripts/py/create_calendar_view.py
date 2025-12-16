#!/usr/bin/env python3
"""
Create a calendar view of Sentinel-2 Level-2A assets availability.
Shows which days have data available in a visual calendar format.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from datetime import datetime, date
import os
import numpy as np

# Get script directory and output folder
script_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(script_dir, "output")
csv_file = os.path.join(output_dir, "sentinel2_assets_AprOct_2022_2023_2024.csv")

if not os.path.exists(csv_file):
    print(f"Error: CSV file not found: {csv_file}")
    print("Please run sentinel-2-level2a-stac.py first to generate the CSV file.")
    exit(1)

# Read the CSV file
print(f"Reading CSV file: {csv_file}")
df = pd.read_csv(csv_file)

# Convert datetime to datetime type
df["datetime"] = pd.to_datetime(df["datetime"])

# Extract date (without time) for grouping by day
df["date"] = df["datetime"].dt.date

# Get unique dates (one per day, since we already have best item per day)
unique_dates = sorted(df["date"].unique())

print(f"\nFound {len(unique_dates)} days with Sentinel-2 Level-2A data")
print(f"Date range: {min(unique_dates)} to {max(unique_dates)}")

# Group by year and month for calendar view
df["year"] = df["datetime"].dt.year
df["month"] = df["datetime"].dt.month
df["day"] = df["datetime"].dt.day

# Create calendar visualization
years = sorted(df["year"].unique())
fig, axes = plt.subplots(len(years), 1, figsize=(16, 4 * len(years)))
if len(years) == 1:
    axes = [axes]

fig.suptitle("Sentinel-2 Level-2A Assets Availability Calendar - Scotty Creek\nBands: R(B02), G(B03), B(B04), NIR(B08) | Apr-Oct only", 
             fontsize=16, fontweight='bold', y=0.995)

for idx, year in enumerate(years):
    ax = axes[idx]
    year_data = df[df["year"] == year]
    
    # Create a matrix for the calendar (months x days)
    # We only have Apr-Oct (months 4-10)
    months = [4, 5, 6, 7, 8, 9, 10]
    month_names = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]
    
    # Create calendar grid
    calendar_data = {}
    for month in months:
        month_days = year_data[year_data["month"] == month]["day"].unique()
        calendar_data[month] = set(month_days)
    
    # Plot calendar - April at top, October at bottom
    ax.set_xlim(0, 33)  # Days 1-31 with more space
    ax.set_ylim(-1.0, len(months) + 0.5)  # Add more padding at top (white band before April)
    ax.set_yticks(range(len(months)))
    ax.set_yticklabels(month_names)
    ax.set_xticks([1, 7, 14, 21, 28])
    ax.set_xticklabels([1, 7, 14, 21, 28])
    ax.set_xlabel("Day of Month", fontsize=10)
    ax.set_title(f"{year}", fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.invert_yaxis()  # Invert y-axis so April (0) is at top and October (6) at bottom
    
    # Plot available days
    for month_idx, month in enumerate(months):
        available_days = calendar_data.get(month, set())
        for day in range(1, 32):
            # Check if this day exists in the month and has data
            try:
                test_date = date(year, month, day)
                if day in available_days:
                    # Day has data - green
                    rect = Rectangle((day - 0.4, month_idx - 0.4), 0.8, 0.8,
                                     facecolor='#2ecc71', edgecolor='white', linewidth=0.5)
                    ax.add_patch(rect)
                else:
                    # Day exists but no data - light gray
                    rect = Rectangle((day - 0.4, month_idx - 0.4), 0.8, 0.8,
                                     facecolor='#ecf0f1', edgecolor='white', linewidth=0.5)
                    ax.add_patch(rect)
            except ValueError:
                # Day doesn't exist in this month (e.g., Feb 30) - white
                pass
    
    # Add legend above the plot at top right
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#2ecc71', label='Data Available'),
        Patch(facecolor='#ecf0f1', label='No Data'),
    ]
    ax.legend(handles=legend_elements, loc='lower right', bbox_to_anchor=(1.0, 1.05), 
              fontsize=9, ncol=2, frameon=True, fancybox=True)

plt.tight_layout()

# Save calendar as PNG
calendar_output = os.path.join(output_dir, "sentinel2_calendar_view.png")
plt.savefig(calendar_output, dpi=300, bbox_inches='tight')
print(f"\n✓ Calendar view saved to: {calendar_output}")

# Also create a text summary
text_output = os.path.join(output_dir, "sentinel2_calendar_summary.txt")
with open(text_output, 'w') as f:
    f.write("Sentinel-2 Level-2A Assets Availability Summary\n")
    f.write("=" * 60 + "\n\n")
    f.write(f"Total days with data: {len(unique_dates)}\n")
    f.write(f"Date range: {min(unique_dates)} to {max(unique_dates)}\n\n")
    
    f.write("Breakdown by Year and Month:\n")
    f.write("-" * 60 + "\n")
    for year in years:
        f.write(f"\n{year}:\n")
        year_data = df[df["year"] == year]
        for month in [4, 5, 6, 7, 8, 9, 10]:
            month_data = year_data[year_data["month"] == month]
            if not month_data.empty:
                month_days = sorted(month_data["day"].unique())
                month_name = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"][month - 4]
                f.write(f"  {month_name}: {len(month_days)} days - Days: {', '.join(map(str, month_days))}\n")
    
    f.write("\n\nAll Available Dates:\n")
    f.write("-" * 60 + "\n")
    for d in unique_dates:
        f.write(f"{d}\n")

print(f"✓ Text summary saved to: {text_output}")

# Print summary to console
print("\n" + "=" * 60)
print("Summary by Year and Month:")
print("=" * 60)
for year in years:
    print(f"\n{year}:")
    year_data = df[df["year"] == year]
    for month in [4, 5, 6, 7, 8, 9, 10]:
        month_data = year_data[year_data["month"] == month]
        if not month_data.empty:
            month_days = sorted(month_data["day"].unique())
            month_name = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"][month - 4]
            print(f"  {month_name}: {len(month_days)} days with data")

print(f"\n✓ Calendar visualization complete!")
print(f"  - PNG image: {calendar_output}")
print(f"  - Text summary: {text_output}")

