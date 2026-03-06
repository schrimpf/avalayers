import rasterio
import matplotlib.pyplot as plt
import numpy as np
import os
import glob

def visualize_results(dem_path, res_path, output_image):
    with rasterio.open(dem_path) as src:
        dem = src.read(1)
        extent = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top]
        nodata = src.nodata
        if nodata is not None:
            dem = np.where(dem == nodata, np.nan, dem)

    with rasterio.open(res_path) as src:
        res = src.read(1)
        # FlowPy results often use 0 as background
        res = np.where(res > 0, res, np.nan)

    plt.figure(figsize=(12, 10))
    # Terrain background
    plt.imshow(dem, extent=extent, cmap='terrain', alpha=0.8)
    plt.colorbar(label='Elevation (m)')
    
    # Results overlay (Flow Depth)
    img = plt.imshow(res, extent=extent, cmap='hot', alpha=0.7)
    plt.colorbar(img, label='Peak Flow Depth (m?)')
    
    plt.title('Sky Pilot FlowPy Result - Peak Flow Depth (5m Subset)')
    plt.xlabel('Easting (m)')
    plt.ylabel('Northing (m)')
    plt.grid(True, linestyle='--', alpha=0.4)
    
    os.makedirs(os.path.dirname(output_image), exist_ok=True)
    plt.savefig(output_image, dpi=150)
    print(f"Result visualization saved to {output_image}")

if __name__ == "__main__":
    # Find the latest zdelta file
    res_files = glob.glob('SkyPilotSubset5m/Outputs/com4FlowPy/peakFiles/res_*/com4_*_zdelta.tif')
    if res_files:
        latest_res = sorted(res_files)[-1]
        visualize_results(
            'SkyPilotSubset5m/Inputs/dem.tif',
            latest_res,
            'outputs/sky_pilot_subset_5m_results.png'
        )
    else:
        print("No result files found.")
