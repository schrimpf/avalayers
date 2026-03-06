import argparse
import sys

from .prepare import prepare_cmd
from .visualize import visualize_cmd
from .simulate import simulate_cmd

def main():
    """Main entry point for the avalayers CLI.

    This function defines the argument parser and all subcommands (prepare, 
    visualize, simulate, export). It dispatches the execution to the 
    corresponding command handler functions.
    """
    parser = argparse.ArgumentParser(
        description="avalayers: A unified pipeline for FlowPy avalanche simulations",
        prog="avalayers"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Prepare command
    parser_prep = subparsers.add_parser("prepare", help="Prepare FlowPy inputs from raw DEM and DSM tiles")
    parser_prep.add_argument("--dtm", required=True, help="Path to bare-earth DTM (e.g., FABDEM .tif)")
    parser_prep.add_argument("--dsm", required=True, help="Path to surface DSM (e.g., Copernicus GLO-30 .tif)")
    parser_prep.add_argument("--out", required=True, help="Path to store the FlowPy project inputs")
    parser_prep.add_argument("--min-elevation", type=float, default=1100.0, help="Minimum elevation for release zones (meters)")
    parser_prep.add_argument("--min-slope", type=float, default=30.0, help="Minimum slope angle for release zones (degrees)")
    parser_prep.add_argument("--max-slope", type=float, default=55.0, help="Maximum slope angle for release zones (degrees)")
    parser_prep.add_argument("--max-tree-cov", type=float, default=0.1, help="Maximum tree coverage (FSI) allowed in release zones (0.0 to 1.0)")
    parser_prep.add_argument("--res", type=float, default=None, help="Optional target resolution in meters to downsample to (e.g. 5.0). Defaults to native resolution if omitted.")
    parser_prep.add_argument("--tree-height-limit", type=float, default=30.0, help="Tree height at which forest is considered fully dense (FSI=1.0). Default 30.0m.")
    parser_prep.set_defaults(func=prepare_cmd)

    # Visualize command
    parser_vis = subparsers.add_parser("visualize", help="Quickly visualize raster layers and optional overlays")
    vis_group = parser_vis.add_mutually_exclusive_group(required=True)
    vis_group.add_argument("--input", help="Path to the primary raster to display (e.g., DEM.tif)")
    vis_group.add_argument("--project", help="Path to a FlowPy project to visualize all inputs and results interactively")
    parser_vis.add_argument("--overlay", help="Path to an optional mask raster to overlay (e.g., REL.tif)")
    parser_vis.add_argument("--browser", action="store_true", help="Display interactive map in the browser instead of a static PNG")
    parser_vis.add_argument("--opacity", type=float, default=0.7, help="Default opacity for dashboard layers (0.0 to 1.0). Default 0.7.")
    parser_vis.set_defaults(func=visualize_cmd)

    # Simulate command
    parser_sim = subparsers.add_parser("simulate", help="Run FlowPy simulation")
    parser_sim.add_argument("--project", required=True, help="Path to the prepared FlowPy project directory")
    parser_sim.add_argument("--overwrite", action="store_true", help="Overwrite existing simulation results")
    parser_sim.add_argument("--max-forest-friction", type=float, default=10.0, help="Maximum added friction (alpha angle in degrees) for fully dense forests. Default 10.0.")
    parser_sim.add_argument("--forest-vel-thresh", type=float, default=30.0, help="Velocity threshold for forest friction effect (m/s). Default 30.0.")
    parser_sim.set_defaults(func=simulate_cmd)

    # Export command
    from .visualize import export_cmd
    parser_exp = subparsers.add_parser("export", help="Export project layers to Google Earth KMZ")
    parser_exp.add_argument("--project", required=True, help="Path to the FlowPy project directory")
    parser_exp.add_argument("--open", action="store_true", help="Automatically open the KMZ file in Google Earth")
    parser_exp.set_defaults(func=export_cmd)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
