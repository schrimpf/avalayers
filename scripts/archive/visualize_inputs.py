import rasterio
from rasterio.plot import show
import matplotlib.pyplot as plt
import numpy as np
import os

def visualize_prepped_data(dem_path, rel_path, output_image):
    with rasterio.open(dem_path) as dem_src:
        dem = dem_src.read(1)
        dem_extent = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top] if 'src' in locals() else None # fix scope
        dem_crs = dem_src.crs
        # Correction: extent logic
        dem_extent = [dem_src.bounds.left, dem_src.bounds.right, dem_src.bounds.bottom, dem_src.bounds.top]

    with rasterio.open(rel_path) as rel_src:
        rel = rel_src.read(1)
        # Handle nodata in release area
        rel = np.where(rel > 0, 1, np.nan)

    plt.figure(figsize=(12, 10))
    
    # Plot DEM
    img = plt.imshow(dem, extent=dem_extent, cmap='terrain')
    plt.colorbar(img, label='Elevation (m)')
    
    # Overlay Release Area (semi-transparent red)
    plt.imshow(rel, extent=dem_extent, cmap='Reds_r', alpha=0.5)
    
    plt.title('Sky Pilot HRDEM and Release Area Mask')
    plt.xlabel('Easting (m)')
    plt.ylabel('Northing (m)')
    plt.grid(True, linestyle='--', alpha=0.6)
    
    os.makedirs(os.path.dirname(output_image), exist_ok=True)
    plt.savefig(output_image, dpi=300)
    print(f"Visualization saved to {output_image}")

if __name__ == "__main__":
    visualize_prepped_data(
        'SkyPilot/Inputs/ElevationModel/sky_pilot_dem.tif',
        'SkyPilot/Inputs/REL/sky_pilot_rel.tif',
        'outputs/sky_pilot_overlay.png'
    )
