import rasterio
import matplotlib.pyplot as plt
import numpy as np
import os

def visualize_dtm_subsampled(dtm_path, output_image):
    with rasterio.open(dtm_path) as src:
        # Subsample to roughly 1000x1000
        factor = max(1, src.width // 1000, src.height // 1000)
        out_shape = (src.count, src.height // factor, src.width // factor)
        
        dem = src.read(1, out_shape=out_shape[1:])
        nodata = src.nodata
        
        if nodata is not None:
            dem = np.where(dem == nodata, np.nan, dem)
        
        plt.figure(figsize=(10, 8))
        extent = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top]
        img = plt.imshow(dem, extent=extent, cmap='terrain')
        plt.colorbar(img, label='Elevation (m)')
        plt.title('Sky Pilot HRDEM (DTM) - Subsampled')
        plt.xlabel('Easting (m)')
        plt.ylabel('Northing (m)')
        plt.grid(True, linestyle='--', alpha=0.6)
        
        os.makedirs(os.path.dirname(output_image), exist_ok=True)
        plt.savefig(output_image, dpi=150)
        print(f"Subsampled DTM visualization saved to {output_image}")

if __name__ == "__main__":
    visualize_dtm_subsampled('sky_pilot_dtm_mosaicked.tif', 'outputs/sky_pilot_dtm_subsampled.png')
