import rasterio
from rasterio.enums import Resampling
import numpy as np
import os

def prepare_inputs(dtm_path, slope_path, output_dir, target_res=5.0):
    os.makedirs(os.path.join(output_dir, 'Inputs'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'Inputs', 'REL'), exist_ok=True)

    with rasterio.open(dtm_path) as dtm_src:
        # Calculate new shape for downsampling
        upscale_factor = dtm_src.res[0] / target_res
        new_height = int(dtm_src.height * upscale_factor)
        new_width = int(dtm_src.width * upscale_factor)
        
        dtm_data = dtm_src.read(
            1,
            out_shape=(new_height, new_width),
            resampling=Resampling.bilinear
        )
        
        # Update transform
        new_transform = dtm_src.transform * dtm_src.transform.scale(
            (dtm_src.width / new_width),
            (dtm_src.height / new_height)
        )
        
        meta = dtm_src.meta.copy()
        meta.update({
            "height": new_height,
            "width": new_width,
            "transform": new_transform
        })
        nodata_dtm = dtm_src.nodata

    with rasterio.open(slope_path) as slope_src:
        slope_data = slope_src.read(
            1,
            out_shape=(new_height, new_width),
            resampling=Resampling.bilinear
        )
        nodata_slope = slope_src.nodata

    # Criteria: Elevation > 1100m AND Slope between 29 and 60 degrees
    release_mask = (dtm_data > 1100) & (slope_data >= 29) & (slope_data <= 60)
    
    # Handle nodata
    if nodata_dtm is not None:
        release_mask &= (dtm_data != nodata_dtm)
    if nodata_slope is not None:
        release_mask &= (slope_data != nodata_slope)

    # Create release array (1 for release, 0 otherwise)
    release_data = np.where(release_mask, 1.0, 0.0).astype('float32')

    # Save DEM to <ProjectName>/Inputs/dem.tif
    dem_out_path = os.path.join(output_dir, 'Inputs', 'dem.tif')
    with rasterio.open(dem_out_path, 'w', **meta) as dst:
        dst.write(dtm_data, 1)
    print(f"Saved 5m DEM to {dem_out_path}")

    # Save Release Area to <ProjectName>/Inputs/REL/rel.tif
    rel_out_path = os.path.join(output_dir, 'Inputs', 'REL', 'rel.tif')
    rel_meta = meta.copy()
    rel_meta.update(dtype='float32', nodata=0.0)
    with rasterio.open(rel_out_path, 'w', **rel_meta) as dst:
        dst.write(release_data, 1)
    print(f"Saved 5m Release Area to {rel_out_path}")

if __name__ == "__main__":
    # Use subset data and downsample to 5m
    prepare_inputs('subset_data/sky_pilot_dtm_subset.tif', 'subset_data/sky_pilot_slope_subset.tif', 'SkyPilotSubset5m', target_res=5.0)
