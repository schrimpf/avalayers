import rasterio
import matplotlib.pyplot as plt
import numpy as np
import os

def visualize_overlay_subsampled(dem_path, rel_path, output_image):
    with rasterio.open(dem_path) as src:
        factor = max(1, src.width // 1000, src.height // 1000)
        out_shape = (src.height // factor, src.width // factor)
        dem = src.read(1, out_shape=out_shape)
        extent = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top]
        nodata = src.nodata
        if nodata is not None:
            dem = np.where(dem == nodata, np.nan, dem)

    with rasterio.open(rel_path) as src:
        # Same out_shape to match DEM
        rel = src.read(1, out_shape=out_shape)
        # Handle nodata/background
        rel = np.where(rel > 0, 1.0, np.nan)

    plt.figure(figsize=(12, 10))
    plt.imshow(dem, extent=extent, cmap='terrain')
    plt.colorbar(label='Elevation (m)')
    
    plt.imshow(rel, extent=extent, cmap='Reds_r', alpha=0.5)
    
    plt.title('Sky Pilot HRDEM and Release Area Mask - Subsampled')
    plt.xlabel('Easting (m)')
    plt.ylabel('Northing (m)')
    plt.grid(True, linestyle='--', alpha=0.6)
    
    os.makedirs(os.path.dirname(output_image), exist_ok=True)
    plt.savefig(output_image, dpi=150)
    print(f"Subsampled overlay visualization saved to {output_image}")

if __name__ == "__main__":
    visualize_overlay_subsampled(
        'SkyPilot/Inputs/ElevationModel/sky_pilot_dem.tif',
        'SkyPilot/Inputs/REL/sky_pilot_rel.tif',
        'outputs/sky_pilot_overlay_subsampled.png'
    )
