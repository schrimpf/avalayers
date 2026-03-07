import os
import rasterio
from rasterio.enums import Resampling
import numpy as np

def calculate_slope(dem, res_x, res_y):
    """Calculate the slope of a digital elevation model in degrees.

    This function uses NumPy's gradient method to compute the x and y gradients
    of the elevation data and then calculates the slope magnitude.

    Args:
        dem (numpy.ndarray): 2D array of elevation values.
        res_x (float): Horizontal resolution in meters.
        res_y (float): Vertical resolution in meters.

    Returns:
        numpy.ndarray: 2D array representing the slope in degrees at each cell.
    """
    dy, dx = np.gradient(dem, res_y, res_x)
    # Slope = arctan(sqrt(dx^2 + dy^2))
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    slope_deg = np.degrees(slope_rad)
    return slope_deg

def prepare_cmd(args):
    """CLI command to prepare FlowPy project inputs from raw DTM and DSM tiles.

    This function performs the following steps:
    1. Creates the standard AvaFrame/FlowPy project directory structure.
    2. Reprojects (if target resolution is set) and reads DTM and DSM data.
    3. Calculates slope and Canopy Height Model (CHM).
    4. Normalizes CHM into Forest Structure Information (FSI).
    5. Enters an interactive loop to tune release area masks based on slope, 
       elevation, and tree coverage.
    6. Saves the finalized rasters (dem.asc, rel.tif, fsi.tif) to the project.

    Args:
        args (argparse.Namespace): Arguments parsed from the CLI, including:
            dtm: Path to the bare-earth DTM.
            dsm: Path to the surface DSM.
            out: Target project directory.
            res: Optional target resolution (meters).
            min_slope: Initial minimum slope threshold.
            max_slope: Initial maximum slope threshold.
            min_elevation: Initial minimum elevation threshold.
            max_tree_cov: Initial maximum FSI threshold.
            tree_height_limit: Height for FSI normalization.
    """
    dtm_path = args.dtm
    dsm_path = args.dsm
    output_dir = args.out
    target_res = args.res
    
    print(f"Preparing FlowPy Project at: {output_dir}")
    if target_res is None:
        print("Using native resolution for FABDEM & Copernicus.")
    else:
        print(f"Using target resolution: {target_res}m")
    
    # Required FlowPy structure
    dem_dir = os.path.join(output_dir, 'Inputs', 'ElevationModel')
    rel_dir = os.path.join(output_dir, 'Inputs', 'REL')
    res_dir = os.path.join(output_dir, 'Inputs', 'RES')
    inputs_dir = os.path.join(output_dir, 'Inputs')
    
    os.makedirs(dem_dir, exist_ok=True)
    os.makedirs(rel_dir, exist_ok=True)
    os.makedirs(res_dir, exist_ok=True)

    from rasterio.warp import calculate_default_transform, reproject, Resampling
    
    with rasterio.open(dtm_path) as dtm_src:
        if target_res is not None:
            # Reproject DTM
            dst_crs = 'EPSG:3857'
            transform, new_width, new_height = calculate_default_transform(
                dtm_src.crs, dst_crs, dtm_src.width, dtm_src.height, *dtm_src.bounds, resolution=(target_res, target_res)
            )
            meta = dtm_src.meta.copy()
            meta.update({
                'crs': dst_crs,
                'transform': transform,
                'width': new_width,
                'height': new_height,
                'nodata': -9999.0
            })
            nodata_dtm = meta['nodata']
            print(f"Reprojecting DTM from {dtm_src.crs} to {dst_crs} at {target_res}m resolution...")
            dtm_data = np.zeros((new_height, new_width), dtype=meta['dtype'])
            reproject(
                source=rasterio.band(dtm_src, 1),
                destination=dtm_data,
                src_transform=dtm_src.transform,
                src_crs=dtm_src.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear
            )
            bounds = rasterio.transform.array_bounds(new_height, new_width, transform)
        else:
            meta = dtm_src.meta.copy()
            print(f"Reading DTM natively ({dtm_src.width}x{dtm_src.height})...")
            dtm_data = dtm_src.read(1)
            nodata_dtm = meta['nodata'] if meta['nodata'] is not None else -9999.0
            transform = dtm_src.transform
            bounds = dtm_src.bounds

        # Replace extreme low values or NaNs in DTM with nodata
        dtm_data = np.nan_to_num(dtm_data, nan=nodata_dtm)
        dtm_data[dtm_data < -1000] = nodata_dtm

    with rasterio.open(dsm_path) as dsm_src:
        if target_res is not None:
            print("Reprojecting DSM (Surface)...")
            dsm_data = np.zeros((new_height, new_width), dtype=meta['dtype'])
            reproject(
                source=rasterio.band(dsm_src, 1),
                destination=dsm_data,
                src_transform=dsm_src.transform,
                src_crs=dsm_src.crs,
                dst_transform=transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear
            )
            nodata_dsm = -9999.0
        else:
            print("Reading DSM natively...")
            dsm_data = dsm_src.read(1)
            nodata_dsm = dsm_src.nodata if dsm_src.nodata is not None else -9999.0
            
        dsm_data = np.nan_to_num(dsm_data, nan=nodata_dsm)
        dsm_data[dsm_data < -1000] = nodata_dsm

    print("Calculating Slope from DTM...")
    if target_res is None:
        # 1 degree latitude is approx 111,320 meters everywhere.
        lat_center = np.radians((bounds.top + bounds.bottom) / 2.0)
        x_res_meters = abs(transform.a) * 111320.0 * np.cos(lat_center)
        y_res_meters = abs(transform.e) * 111320.0
        print(f"Estimated native resolution: ~{x_res_meters:.2f}m x {y_res_meters:.2f}m")
    else:
        x_res_meters = target_res
        y_res_meters = target_res

    valid_data_mask = (dtm_data != nodata_dtm)
    slope_data = np.zeros_like(dtm_data)
    
    # np.gradient asks for the distance between points
    slope_data[valid_data_mask] = calculate_slope(
        dtm_data, 
        x_res_meters, 
        y_res_meters
    )[valid_data_mask]

    print("Calculating Canopy Height Model (CHM) and FSI...")
    valid_both_mask = valid_data_mask & (dsm_data != nodata_dsm)
    chm = np.zeros_like(dtm_data)
    # CHM is difference between Surface and Bare Earth
    chm[valid_both_mask] = dsm_data[valid_both_mask] - dtm_data[valid_both_mask]
    
    # Remove negative canopy heights (artifacts)
    chm = np.clip(chm, 0, None)
    
    # Normalize
    max_tree_height_m = args.tree_height_limit
    fsi_data = np.zeros_like(dtm_data)
    fsi_data[valid_both_mask] = np.clip(chm[valid_both_mask] / max_tree_height_m, 0, 1.0)
    fsi_data[~valid_both_mask] = -9999.0

    min_slope = args.min_slope
    max_slope = args.max_slope
    max_tree_cov = args.max_tree_cov
    min_elevation = args.min_elevation
    
    from .visualize import generate_interactive_map

    while True:
        print(f"Generating Release Area (REL)... min_elevation={min_elevation}, min_slope={min_slope}, max_slope={max_slope}, max_tree={max_tree_cov}")
        release_mask = (
            (dtm_data > min_elevation) & 
            (slope_data >= min_slope) & 
            (slope_data <= max_slope) & 
            (fsi_data <= max_tree_cov) &
            valid_data_mask
        )
        release_data = np.where(release_mask, 1.0, 0.0).astype('float32')

        dem_out_path = os.path.join(inputs_dir, 'dem.asc')
        asc_meta = meta.copy()
        asc_meta.update({'driver': 'AAIGrid', 'nodata': nodata_dtm})
        with rasterio.open(dem_out_path, 'w', **asc_meta) as dst:
            dst.write(dtm_data, 1)

        rel_out_path = os.path.join(rel_dir, 'rel.tif')
        rel_meta = meta.copy()
        rel_meta.update(dtype='float32', nodata=0.0)
        with rasterio.open(rel_out_path, 'w', **rel_meta) as dst:
            dst.write(release_data, 1)
            
        fsi_out_path = os.path.join(res_dir, 'fsi.tif')
        fsi_meta = meta.copy()
        fsi_meta.update(dtype='float32', nodata=-9999.0)
        with rasterio.open(fsi_out_path, 'w', **fsi_meta) as dst:
            dst.write(fsi_data.astype('float32'), 1)

        slope_out_path = os.path.join(res_dir, 'slope.tif')
        slope_meta = meta.copy()
        slope_meta.update(dtype='float32', nodata=0.0)
        with rasterio.open(slope_out_path, 'w', **slope_meta) as dst:
            dst.write(slope_data.astype('float32'), 1)
            
        try:
            generate_interactive_map(output_dir)
        except Exception as e:
            print(f"Warning: Could not generate map preview: {e}")
            
        print("\n--- Interactive Tuning ---")
        prompt = "Press Enter to finalize preparation, or enter 'min_elev,min_slope,max_slope,max_tree_cov' (e.g. 1100,30,55,0.1) to adjust parameters: "
        resp = input(prompt).strip()
        
        if not resp:
            break
            
        try:
            parts = [float(p.strip()) for p in resp.split(',')]
            if len(parts) == 4:
                min_elevation, min_slope, max_slope, max_tree_cov = parts
            else:
                print("Invalid format. Please provide 4 comma-separated numbers.")
        except Exception:
            print("Invalid input. Could not parse values.")

    res_str = f"{target_res}m" if target_res is not None else "native"
    print(f"Preparation complete ({res_str})! Project is ready for `avalayers simulate`")
