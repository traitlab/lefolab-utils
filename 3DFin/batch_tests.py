import configparser
import os
import subprocess
import tempfile

# Define input files and output directory
input_las = "las_plots/569383.9_4992843_231.las"
config_file = "3DFinconfig.ini"
base_output_path = "tests"

# # Define the parameters to test
# test_parameters = {
#     "basic": {
#         "upper_limit": [2.5, 3.0, 3.5],
#         "lower_limit": [0.5, 0.7, 1.0],
#         "number_of_iterations": [2, 3, 4],
#         "res_cloth": [0.5, 0.7]
#     },
#     "advanced": {
#         "section_len": [0.2, 0.5],
#         "section_wid": [0.05, 0.10, 0.25, 0.50]
#     },
#     "expert": {
#         "res_xy_stripe": [0.02, 0.3],
#         "res_z_stripe": [0.02, 0.3],
#         "number_of_points": [1000, 500, 10],
#         "verticality_scale_stripe": [0.1, 0.3],
#         "verticality_thresh_stripe": [0.7, 0.5, 0.3],
#         "height_range": [0.7, 0.5, 0.2],
#         "minimum_points": [20, 10],
#         "verticality_scale_stems": [0.1, 0.3],
#         "verticality_thresh_stems": [0.7, 0.4],
#         "maximum_d": [15, 5]
#     }
# }

# Define the parameters to test
test_parameters = {
    "basic": {
        "upper_limit": [3.75, 4.0, 4.25, 4.5],
        "lower_limit": [1.25, 1.5],
        "res_cloth": [0.1, 0.3, 1.0]
    },
    "advanced": {
        "section_len": [0.1, 0.4, 0.7],
        "section_wid": [0.40, 0.60, 0.80]
    },
    "expert": {
        "res_xy_stripe": [0.05, 0.1],
        "res_z_stripe": [0.05, 0.1],
        "number_of_points": [5],
        "verticality_scale_stripe": [0.4, 0.5, 0.6],
        "verticality_thresh_stripe": [0.4, 0.6],
        "height_range": [0.4, 0.3],
        "minimum_points": [5],
        "verticality_scale_stems": [0.4, 0.5, 0.6],
        "verticality_thresh_stems": [0.3, 0.5],
        "maximum_d": [10, 2]
    }
}

# Load the config file
config = configparser.ConfigParser()
config.read(config_file)

# Store the original config values
default_config = {section: dict(config[section]) for section in config.sections()}

# Function to run the command and handle errors
def run_test(input_las, config_file, output_path):
    """Runs the command and handles errors without stopping the loop."""
    try:
        subprocess.run(
            [
                "3DFin", "cli",
                input_las,
                output_path,
                config_file,
                "--export_txt",
                "--normalize",
                "--denoise"
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running test for {param} in [{section}] with value = {value}: {e}")
        print("Continuing with next test...")

# Loop through each parameter and modify only that one
for section, params in test_parameters.items():
    for param, values in params.items():
        for value in values:
            # Restore defaults before modifying the parameter
            for sec, vals in default_config.items():
                config[sec].update(vals)

            # Modify only the current parameter
            config[section][param] = str(value)

            # Create a temporary config file
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".ini") as temp_config:
                temp_config_file = temp_config.name
                config.write(temp_config)

            # Create a unique output folder for each test
            output_path = os.path.join(base_output_path, f"{section}_{param}_{value}")
            os.makedirs(output_path, exist_ok=True)

            print(f"Testing {param} in [{section}] with value = {value}")
            print(f"Using temp config: {temp_config_file}")
            print(f"Saving output to: {output_path}")

            # Run the command
            run_test(input_las, temp_config_file, output_path)

            # Delete temp config after the test
            os.remove(temp_config_file)

            print(f"Completed test for {param} = {value}")
            print("=" * 100)

print("All tests completed.")