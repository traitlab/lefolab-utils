import os
import subprocess

# Define paths
las_dir = ""
output_dir = ""
config_file = ""

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

# Loop through all LAS files in las_plots/
for las_file in os.listdir(las_dir):
    if las_file.endswith(".las"):
        las_path = os.path.join(las_dir, las_file)

        # Create output folder name based on LAS file name (without extension)
        plot_name = os.path.splitext(las_file)[0]
        # plot_name = las_file.split('.')[0]
        plot_output_dir = os.path.join(output_dir, plot_name)
        os.makedirs(plot_output_dir, exist_ok=True)

        # Construct CLI command
        cmd = [
            "3DFin", "cli",
            las_path, plot_output_dir, config_file,
            "--export_txt", "--normalize", "--denoise"
        ]

        # Run command
        subprocess.run(cmd)
