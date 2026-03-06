import rasterio
from rasterio.plot import show
import matplotlib.pyplot as plt
import numpy as np
import os

def visualize_dtm_only(dtm_path, output_image):
    with rasterio.open(dtm_path) as src:
        dem = src.read(1)
        nodata = src.nodata
        
        # Mask nodata for visualization
        if nodata is not None:
            dem = np.where(dem == nodata, np.nan, dem)
        
        # Plot
        plt.figure(figsize=(10, 8))
        extent = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top]
        img = plt.imshow(dem, extent=extent, cmap='terrain')
        plt.colorbar(img, label='Elevation (m)')
        plt.title('Sky Pilot HRDEM (DTM)')
        plt.xlabel('Easting (m)')
        plt.ylabel('Northing (m)')
        plt.grid(True, linestyle='--', alpha=0.6)
        
        os.makedirs(os.path.dirname(output_image), exist_ok=True)
        plt.savefig(output_image, dpi=300)
        print(f"DTM-only visualization saved to {output_image}")

if __name__ == "__main__":
    visualize_dtm_only('sky_pilot_dtm_mosaicked.tif', 'outputs/sky_pilot_dtm_only.png')
