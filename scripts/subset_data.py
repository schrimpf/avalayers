import rasterio
from rasterio.windows import Window
import os

def subset_rasters(dtm_path, slope_path, output_dir, size=1000):
    os.makedirs(output_dir, exist_ok=True)
    
    with rasterio.open(dtm_path) as src:
        # Center of the mosaic
        center_x, center_y = src.width // 2, src.height // 2
        
        # Define window (size x size)
        win = Window(center_x - size // 2, center_y - size // 2, size, size)
        
        # Read subset
        subset_dtm = src.read(1, window=win)
        transform = src.window_transform(win)
        meta = src.meta.copy()
        meta.update({
            "height": size,
            "width": size,
            "transform": transform
        })
        
        dtm_sub_path = os.path.join(output_dir, 'sky_pilot_dtm_subset.tif')
        with rasterio.open(dtm_sub_path, 'w', **meta) as dst:
            dst.write(subset_dtm, 1)
        print(f"Subset DTM saved to {dtm_sub_path}")

    with rasterio.open(slope_path) as src:
        subset_slope = src.read(1, window=win)
        slope_sub_path = os.path.join(output_dir, 'sky_pilot_slope_subset.tif')
        with rasterio.open(slope_sub_path, 'w', **meta) as dst:
            dst.write(subset_slope, 1)
        print(f"Subset Slope saved to {slope_sub_path}")

if __name__ == "__main__":
    subset_rasters('sky_pilot_dtm_mosaicked.tif', 'sky_pilot_slope_mosaicked.tif', 'subset_data')
