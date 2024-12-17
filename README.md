# metashape_scripts
scripts and other files used for Metashape software

## How to use batch process files
1. In Metashape, after loading your pictures, changing the name of the chunks and loading the camera calibration file if applicable, go to Workflow > Batch Process... to open the menu.
2. Click on the Load icon in the bottom right corner and load 'step1_pc_medium_dsm_ortho.xml' file.
3. You need to confirm the projection for the jobs 'Build DEM' and 'Build Orthomosaic'.
4. Check the 'Save project after each step' option and run the batch by clicking on Ok.
5. When it's over, click on the Load icon in the bottom right corner and load 'step2_pc_high_dsm_report_export.xml' file.
6. Again, you need to confirm the projection for the jobs 'Export Orthomosaic', 'Build DEM', 'Export Point Cloud' and 'Export DEM'. You also need to confirm the output path for all export jobs.
7. Run the batch by clicking on Ok.
