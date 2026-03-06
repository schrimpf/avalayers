import os
import pathlib
import configparser
from avaframe import runCom4FlowPy
from .visualize import generate_interactive_map

def simulate_cmd(args):
    """CLI command to run a FlowPy avalanche simulation with forest friction.

    This function coordinates the simulation execution by:
    1. Validating the FlowPy project structure (checks for dem.asc).
    2. Displaying an interactive Folium map for final inspection.
    3. Programmatically generating a `local_com4FlowPyCfg.ini` file in the project 
       root to enable and configure the `ForestFriction` module.
    4. Optionally clearing previous simulation results if `--overwrite` is set.
    5. Triggering the AvaFrame `runCom4FlowPy` engine.

    Args:
        args (argparse.Namespace): Arguments parsed from the CLI, including:
            project: Path to the prepared project directory.
            max_forest_friction: Additional friction (alpha angle) for dense canopy.
            forest_vel_thresh: Velocity threshold for dampening effect.
            overwrite: Boolean flag to purge existing outputs.
    """
    project_dir = str(pathlib.Path(args.project).resolve())
    print(f"Loading project from: {project_dir}")
    
    # Check if necessary directories exist
    if not os.path.exists(os.path.join(project_dir, 'Inputs', 'dem.asc')):
        print(f"Error: Could not find ElevationModel directly under {project_dir}/Inputs/")
        return
        
    try:
        generate_interactive_map(project_dir)
    except Exception as e:
        print(f"Warning: Could not generate interactive map preview: {e}")
        
    response = input("Review the map in your browser. Proceed with FlowPy simulation? [y/N]: ")
    if response.lower() not in ['y', 'yes', 'true']:
        print("Simulation aborted by user.")
        return

    print("Configuring local variables...")
    # Programmatically write local_com4FlowPyCfg.ini configuration to use the built FSI forest layer
    local_cfg_path = os.path.join(project_dir, 'local_com4FlowPyCfg.ini')
    config = configparser.ConfigParser()
    
    # Initialize basic configuration block dictating the forest settings
    config['GENERAL'] = {
        'forest': 'True',
        'forestModule': 'ForestFriction',
        'maxAddedFrictionFor': str(args.max_forest_friction),
        'velThForFriction': str(args.forest_vel_thresh),
        'previewMode': 'False'
    }
    
    with open(local_cfg_path, 'w') as configfile:
        config.write(configfile)
        
    print(f"Wrote local configuration to {local_cfg_path} to enable Forest module.")
    
    if args.overwrite:
        import shutil
        out_dir = os.path.join(project_dir, 'Outputs', 'com4FlowPy')
        if os.path.exists(out_dir):
            print(f"Removing existing results in {out_dir} because --overwrite was specified...")
            shutil.rmtree(out_dir)

    try:
        # Pass the local configuration overriding the defaults automatically through AvaFrame
        runCom4FlowPy.main(project_dir)
        print("Simulation completed successfully.")
    except Exception as e:
        print(f"An error occurred during simulation: {e}")
