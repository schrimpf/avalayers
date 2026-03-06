# avalayers

`avalayers` is a unified, high-performance pipeline for preparing, simulating, and visualizing avalanche flow dynamics using the **FlowPy** (AvaFrame) engine. 

It streamlines the transition from raw satellite data (Copernicus DSM and FABDEM DTM) to complex 3D visualizations, specifically focusing on the interaction between terrain obstacles and forest canopy friction.

## Key Features

- **Automated Data Processing**: Download and merge high-resolution DTM/DSM tiles across custom bounding boxes.
- **Dynamic Terrain Analysis**: Calculate Canopy Height Models (CHM) and normalize them into Forest Structure Information (FSI) layers.
- **Interactive Start-Zone Tuning**: Refine avalanche release zones in real-time via a command-line interface and topographical map previews.
- **Advanced Forest Friction**: Leverages FlowPy's `ForestFriction` module with custom configuration for maximum resistance in dense canopies.
- **Integrated Dashboard**: Generate interactive, browser-based dashboards with toggleable layers, opacity controls, and scientific descriptions.
- **3D Export**: One-click generation of KMZ files for high-fidelity visualization in Google Earth Pro.

## Installation

This project uses `uv` for lightning-fast dependency management.

```bash
# Clone the repository
git clone <repo-url>
cd avylayers

# Create environment and install dependencies
uv sync
```

## Quick Start

### 1. Acquire Elevation Data
Download tiles for your region of interest (e.g., Sky Pilot, BC).
```bash
uv run scripts/download_dems.py --bbox -123.1488 49.6315 -123.0692 49.6684
```

### 2. Prepare Simulation Project
Generate the DTM, FSI, and Release Area masks.
```bash
uv run -m avalayers prepare \
    --dtm data/dems/fabdem_dtm_...tif \
    --dsm data/dems/copernicus_glo30_dsm_...tif \
    --out MySimulation
```

### 3. Run Simulation
Execute the FlowPy engine with custom friction parameters.
```bash
uv run -m avalayers simulate --project MySimulation --max-forest-friction 20.0
```

### 4. Visualize Results
Open the project dashboard or export to Google Earth.
```bash
uv run -m avalayers visualize --project MySimulation --browser
uv run -m avalayers export --project MySimulation --open
```

## Scientific Documentation
For detailed information on the FSI calculation, friction models, and advanced CLI options, please refer to the [User Guide](user_guide.md).

## License
MIT
