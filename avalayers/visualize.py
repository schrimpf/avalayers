import os
import rasterio
import folium
import numpy as np
import base64
from io import BytesIO
from PIL import Image
import matplotlib.cm as cm
import webbrowser
import glob

LAYER_INFO = {
    'dem': {
        'name': 'Elevation Grid (DTM)',
        'cmap': 'terrain',
        'desc': 'Digital Terrain Model: Represents the bare earth elevation without trees or buildings.'
    },
    'rel': {
        'name': 'Release Area (REL)',
        'cmap': 'Greys',
        'desc': 'Avalanche Release Zones: Areas identified as potential start points based on slope and elevation.'
    },
    'fsi': {
        'name': 'Tree Mask (FSI)',
        'cmap': 'Greens',
        'desc': 'Forest Structure Information: Normalized tree height (0 to 1) used to calculate friction.'
    },
    'zdelta': {
        'name': 'Max Flow Thickness (zdelta)',
        'cmap': 'plasma',
        'desc': 'Simulation Output: Maximum thickness (meters) of the snow flow during the event.'
    },
    'fptravelanglemax': {
        'name': 'Friction Alpha Angle',
        'cmap': 'YlOrBr',
        'desc': 'Simulation Output: The maximum travel angle (friction) reached during the flow.'
    },
    'travellengthmax': {
        'name': 'Max Travel Length',
        'cmap': 'Purples',
        'desc': 'Simulation Output: The maximum distance traveled by the flow at this point.'
    },
    'cellcounts': {
        'name': 'Cell Counts',
        'cmap': 'Blues',
        'desc': 'Simulation Output: Number of particles that passed through this cell.'
    }
}

def generate_rgba_for_raster(data, nodata, cmap_name, alpha_val=0.7, vmin=None, vmax=None):
    """Convert a 2D numpy array into a base64 encoded RGBA PNG string.

    This utility function is used to prepare raster data for Folium's `ImageOverlay`.
    It masks nodata values, normalizes the data, applies a colormap, and sets
    the alpha channel.

    Args:
        data (numpy.ndarray): 2D array of raster data.
        nodata (float): The nodata value to mask out.
        cmap_name (str): Name of the Matplotlib colormap to apply.
        alpha_val (float, optional): Global alpha value for non-masked data. Defaults to 0.7.
        vmin (float, optional): Minimum value for normalization. Defaults to data min.
        vmax (float, optional): Maximum value for normalization. Defaults to data max.

    Returns:
        str: Base64 encoded PNG string with data URI prefix.
    """
    # mask out nodata
    mask = (data == nodata) | np.isnan(data)
    
    # normalize data for colormap
    d_min = vmin if vmin is not None else np.nanmin(data[~mask])
    d_max = vmax if vmax is not None else np.nanmax(data[~mask])
    
    if d_max == d_min: 
        norm_data = np.zeros_like(data)
    else:
        norm_data = (data - d_min) / (d_max - d_min)
        
    cmap = cm.get_cmap(cmap_name)
    rgba = cmap(norm_data)
    
    # Set transparent alpha where data is missing
    rgba[mask, 3] = 0.0
    # Set global alpha where data exists
    rgba[~mask, 3] = alpha_val
    
    # Convert float [0,1] to uint8 [0,255]
    rgba_uint8 = (rgba * 255).astype(np.uint8)
    img = Image.fromarray(rgba_uint8, 'RGBA')
    
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode('utf-8')

def generate_interactive_map(project_dir):
    """Generate an interactive Folium map visualization for a project's inputs.

    This map is typically used for a final preview before starting a simulation.
    It includes toggleable layers for the DTM, FSI (Tree Mask), and REL (Release).

    Args:
        project_dir (str): Path to the FlowPy project directory.

    Returns:
        str: Absolute path to the generated HTML file.
    """
    print(f"Generating interactive map for {project_dir}...")
    
    dem_path = os.path.join(project_dir, 'Inputs', 'dem.asc')
    rel_path = os.path.join(project_dir, 'Inputs', 'REL', 'rel.tif')
    fsi_path = os.path.join(project_dir, 'Inputs', 'RES', 'fsi.tif')
    
    # We must determine bounds and center from the DEM
    with rasterio.open(dem_path) as src:
        bounds = src.bounds
        nodata = src.nodata if src.nodata is not None else -9999.0
        
        # Folium uses Lat/Lon (EPSG:4326), but our DEM might be projected.
        # FlowPy pipeline inputs should be in EPSG:4326 implicitly if we kept native.
        # But let's accurately extract corners and assume they are WGS84 per user's last request.
        if src.crs is not None and src.crs.to_string() != 'EPSG:4326':
            from rasterio.warp import transform_bounds
            bounds = transform_bounds(src.crs, 'EPSG:4326', *bounds)
            
        center_lat = (bounds[1] + bounds[3]) / 2.0
        center_lon = (bounds[0] + bounds[2]) / 2.0
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='OpenTopoMap')
        
        # 1. Base Elevation (DTM) - Terrain colormap
        # We subsample large rasters for the browser overlay so it doesn't crash 
        factor = max(1, src.width // 1000, src.height // 1000)
        out_shape = (src.height // factor, src.width // factor)
        
        dtm_data = src.read(1, out_shape=out_shape)
        dtm_b64 = generate_rgba_for_raster(dtm_data, nodata, 'terrain', alpha_val=0.6)
        
        folium.raster_layers.ImageOverlay(
            image=dtm_b64,
            bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
            name='Elevation Grid (DTM)',
            interactive=True,
            cross_origin=False,
            zindex=1,
            opacity=1.0 # Alpha is controlled deeply in generate_rgba
        ).add_to(m)

    # 2. Release Area (REL) - Greys colormap
    if os.path.exists(rel_path):
        with rasterio.open(rel_path) as rel_src:
            rel_data = rel_src.read(1, out_shape=out_shape)
            rel_nodata = rel_src.nodata if rel_src.nodata is not None else 0.0
            
            # Mask out non-release areas entirely so they are absolutely transparent
            rel_data[rel_data <= 0] = rel_nodata
            
            rel_b64 = generate_rgba_for_raster(rel_data, rel_nodata, 'Greys', alpha_val=0.8, vmin=0, vmax=1)
            folium.raster_layers.ImageOverlay(
                image=rel_b64,
                bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
                name='Release Area (REL)',
                interactive=True,
                cross_origin=False,
                zindex=2
            ).add_to(m)
            
    # 3. Tree Mask (FSI) - Greens colormap
    if os.path.exists(fsi_path):
        with rasterio.open(fsi_path) as fsi_src:
            fsi_data = fsi_src.read(1, out_shape=out_shape)
            fsi_nodata = fsi_src.nodata if fsi_src.nodata is not None else -9999.0
            
            # Mask out 0 tree coverage completely to avoid green tint everywhere
            fsi_data[fsi_data <= 0.0] = fsi_nodata
            
            fsi_b64 = generate_rgba_for_raster(fsi_data, fsi_nodata, 'Greens', alpha_val=0.7, vmin=0, vmax=1)
            folium.raster_layers.ImageOverlay(
                image=fsi_b64,
                bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
                name='Tree Mask (FSI)',
                interactive=True,
                cross_origin=False,
                zindex=3
            ).add_to(m)

    folium.LayerControl().add_to(m)
    
    map_path = os.path.join(project_dir, 'interactive_preview.html')
    m.save(map_path)
    print(f"Map successfully generated at {map_path}")
    
    try:
        webbrowser.open('file://' + os.path.abspath(map_path))
    except Exception as e:
        print(f"Could not automatically open browser: {e}")
        
    return map_path

def generate_project_dashboard(project_dir, opacity=0.7):
    """Generate a comprehensive multi-layer dashboard for a finished project.

    This dashboard aggregates all input layers (DTM, REL, FSI) and all 
    simulation output layers (zdelta, peak velocities, etc.) into a 
    single interactive map with detailed popups and opacity controls.

    Args:
        project_dir (str): Path to the FlowPy project directory.
        opacity (float, optional): Fixed opacity level for all overlays. Defaults to 0.7.

    Returns:
        str: Absolute path to the generated `project_dashboard.html`.
    """
    print(f"Generating comprehensive project dashboard for {project_dir} with opacity {opacity}...")
    
    dem_path = os.path.join(project_dir, 'Inputs', 'dem.asc')
    if not os.path.exists(dem_path):
        print(f"Error: Could not find base DEM at {dem_path}")
        return None

    with rasterio.open(dem_path) as src:
        bounds = src.bounds
        nodata = src.nodata if src.nodata is not None else -9999.0
        
        if src.crs is not None and src.crs.to_string() != 'EPSG:4326':
            from rasterio.warp import transform_bounds
            bounds = transform_bounds(src.crs, 'EPSG:4326', *bounds)
            
        center_lat = (bounds[1] + bounds[3]) / 2.0
        center_lon = (bounds[0] + bounds[2]) / 2.0
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='OpenTopoMap')
        
        factor = max(1, src.width // 1000, src.height // 1000)
        out_shape = (src.height // factor, src.width // factor)
        
        # 1. Base Elevation (DTM)
        dtm_data = src.read(1, out_shape=out_shape)
        dtm_b64 = generate_rgba_for_raster(dtm_data, nodata, 'terrain', alpha_val=opacity * 0.8)
        
        folium.raster_layers.ImageOverlay(
            image=dtm_b64,
            bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
            name=LAYER_INFO['dem']['name'],
            interactive=True,
            cross_origin=False,
            zindex=1,
            show=False,
            popup=LAYER_INFO['dem']['desc']
        ).add_to(m)

    # 2. Add other inputs
    inputs = {
        'rel': os.path.join(project_dir, 'Inputs', 'REL', 'rel.tif'),
        'fsi': os.path.join(project_dir, 'Inputs', 'RES', 'fsi.tif')
    }
    
    for key, path in inputs.items():
        if os.path.exists(path):
            with rasterio.open(path) as s:
                data = s.read(1, out_shape=out_shape)
                nd = s.nodata if s.nodata is not None else (-9999.0 if key == 'fsi' else 0.0)
                if key == 'fsi': data[data <= 0] = nd
                else: data[data <= 0] = nd
                
                b64 = generate_rgba_for_raster(data, nd, LAYER_INFO[key]['cmap'], alpha_val=opacity, vmin=0, vmax=1)
                folium.raster_layers.ImageOverlay(
                    image=b64,
                    bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
                    name=LAYER_INFO[key]['name'],
                    interactive=True,
                    zindex=2 if key == 'rel' else 3,
                    show=False,
                    popup=LAYER_INFO[key]['desc']
                ).add_to(m)

    # 3. Add simulation outputs (Peak Files)
    peak_root = os.path.join(project_dir, 'Outputs', 'com4FlowPy', 'peakFiles')
    if os.path.exists(peak_root):
        # Scan recursively for all .tif files
        peak_files = glob.glob(os.path.join(peak_root, '**', '*.tif'), recursive=True)
        zindex = 10
        for pf in peak_files:
            pf_name = os.path.basename(pf).lower()
            # Identify the layer type from PLAYER_INFO keys
            info_key = next((k for k in LAYER_INFO.keys() if k in pf_name), None)
            
            if info_key and info_key not in ['dem', 'rel', 'fsi']:
                with rasterio.open(pf) as s:
                    data = s.read(1, out_shape=out_shape)
                    nd = s.nodata if s.nodata is not None else -9999.0
                    data[data <= 0] = nd
                    
                    name = LAYER_INFO[info_key]['name']
                    desc = LAYER_INFO[info_key]['desc']
                    cmap = LAYER_INFO[info_key]['cmap']
                    
                    show_layer = (info_key == 'zdelta')
                    
                    b64 = generate_rgba_for_raster(data, nd, cmap, alpha_val=opacity)
                    folium.raster_layers.ImageOverlay(
                        image=b64,
                        bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
                        name=f"Output: {name}",
                        interactive=True,
                        show=show_layer,
                        zindex=zindex,
                        popup=desc
                    ).add_to(m)
                    zindex += 1

    folium.LayerControl(collapsed=False).add_to(m)

    map_path = os.path.join(project_dir, 'project_dashboard.html')
    m.save(map_path)
    print(f"Project dashboard successfully generated at {map_path}")
    
    try:
        webbrowser.open('file://' + os.path.abspath(map_path))
    except Exception as e:
        print(f"Could not automatically open browser: {e}")
        
    return map_path

def visualize_cmd(args):
    """CLI command entry point for all visualization tasks.

    This function dispatches to either `generate_project_dashboard` if a 
    project directory is provided, or `folium`/`matplotlib` logic for 
    individual raster overlays.

    Args:
        args (argparse.Namespace): Arguments parsed from the CLI, including:
            project: Optional path to a FlowPy project.
            input: Optional path to a single raster file.
            overlay: Optional path to an overlay raster file.
            browser: Boolean flag to use interactive Folium instead of static PNG.
            opacity: Opacity level for project dashboard layers.
    """
    if getattr(args, 'project', None):
        generate_project_dashboard(args.project, opacity=args.opacity)
        return

    if args.input:
        input_path = args.input
        overlay_path = args.overlay
        
        # Describe the base layer
        base_desc = "Base Layer"
        if "dem" in input_path.lower():
            base_desc = "Digital Elevation Model (DEM)"
        elif "dtm" in input_path.lower():
            base_desc = "Digital Terrain Model (DTM)"
        elif "dsm" in input_path.lower():
            base_desc = "Digital Surface Model (DSM)"
            
        print(f"Visualizing: {input_path}")
        print(f" > Shows {base_desc}")
        
        # Describe the overlay layer if present
        ol_name = ""
        ol_desc = ""
        if overlay_path:
            ol_name = os.path.basename(overlay_path).lower()
            ol_desc = "Overlay Layer"
            if "zdelta" in ol_name:
                ol_desc = "Maximum Flow Depth (zdelta)"
            elif "travellengthmax" in ol_name:
                ol_desc = "Maximum Travel Length"
            elif "fptravelanglemax" in ol_name:
                ol_desc = "Maximum Alpha Angle (Friction)"
            elif "rel" in ol_name:
                ol_desc = "Release Area"
            elif "fsi" in ol_name:
                ol_desc = "Forest Structure Information (Tree Coverage)"
                
            print(f" > Overlaid with: {ol_desc} (from {overlay_path})")

        if getattr(args, 'browser', False):
            # Generate Interactive Browser Map
            with rasterio.open(input_path) as src:
                bounds = src.bounds
                nodata = src.nodata if src.nodata is not None else -9999.0
                
                if src.crs is not None and src.crs.to_string() != 'EPSG:4326':
                    from rasterio.warp import transform_bounds
                    bounds = transform_bounds(src.crs, 'EPSG:4326', *bounds)
                    
                center_lat = (bounds[1] + bounds[3]) / 2.0
                center_lon = (bounds[0] + bounds[2]) / 2.0
                
                m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles='OpenTopoMap')
                
                factor = max(1, src.width // 1000, src.height // 1000)
                out_shape = (src.height // factor, src.width // factor)
                base_data = src.read(1, out_shape=out_shape)
                base_b64 = generate_rgba_for_raster(base_data, nodata, 'terrain', alpha_val=0.6)
                
                folium.raster_layers.ImageOverlay(
                    image=base_b64,
                    bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
                    name=base_desc,
                    interactive=True,
                    cross_origin=False,
                    zindex=1,
                    opacity=1.0
                ).add_to(m)

            if overlay_path:
                with rasterio.open(overlay_path) as src_ol:
                    ol_data = src_ol.read(1, out_shape=out_shape)
                    ol_nodata = src_ol.nodata if src_ol.nodata is not None else -9999.0
                    
                    ol_data[ol_data <= 0] = ol_nodata
                    cmap = 'Greens' if "fsi" in ol_name else 'Reds_r'
                    ol_b64 = generate_rgba_for_raster(ol_data, ol_nodata, cmap, alpha_val=0.8)
                    
                    folium.raster_layers.ImageOverlay(
                        image=ol_b64,
                        bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
                        name=ol_desc,
                        interactive=True,
                        cross_origin=False,
                        zindex=2
                    ).add_to(m)

            folium.LayerControl().add_to(m)
            map_path = f"{os.path.splitext(input_path)[0]}_interactive.html"
            m.save(map_path)
            print(f"Interactive map successfully generated at {map_path}")
            
            try:
                webbrowser.open('file://' + os.path.abspath(map_path))
            except Exception as e:
                print(f"Could not automatically open browser: {e}")
                
        else:
            # Generate Static Matplotlib PNG
            import matplotlib.pyplot as plt
            with rasterio.open(input_path) as src:
                factor = max(1, src.width // 1000, src.height // 1000)
                out_shape = (src.height // factor, src.width // factor)
                base_layer = src.read(1, out_shape=out_shape)
                nodata = src.nodata
                if nodata is not None:
                    base_layer = np.where(base_layer == nodata, np.nan, base_layer)
                extent = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top]
                
            plt.figure(figsize=(12, 10))
            img = plt.imshow(base_layer, extent=extent, cmap='terrain')
            plt.colorbar(img, label=base_desc)

            if overlay_path:
                with rasterio.open(overlay_path) as src_ol:
                    ol_layer = src_ol.read(1, out_shape=out_shape)
                    ol_nodata = src_ol.nodata
                    if ol_nodata is not None:
                        ol_layer = np.where(ol_layer == ol_nodata, np.nan, ol_layer)
                    ol_layer = np.where(ol_layer <= 0, np.nan, ol_layer)
                    
                    cmap = 'Greens' if "fsi" in ol_name else 'Reds_r'
                    ol_img = plt.imshow(ol_layer, extent=extent, cmap=cmap, alpha=0.5)
                    plt.colorbar(ol_img, label=ol_desc)
                    
            plt.title(f"Visualization of {os.path.basename(input_path)}")
            plt.xlabel('Easting')
            plt.ylabel('Northing')
            plt.grid(True, linestyle='--', alpha=0.6)
            
            out_png = f"{os.path.splitext(os.path.basename(input_path))[0]}_vis.png"
            plt.savefig(out_png, dpi=150)
            print(f"Saved visualization to {out_png}")

def raster_to_png(path, out_path, cmap_name, nodata_val=None):
    """Convert a GeoTIFF raster to a colormapped PNG for KMZ ground overlays.

    This function reads a raster, normalizes it, applies the specified colormap,
    and returns the geographic bounding box in WGS84 (EPSG:4326).

    Args:
        path (str): Path to the source raster file.
        out_path (str): Path where the resulting PNG should be saved.
        cmap_name (str): Name of the Matplotlib colormap to use.
        nodata_val (float, optional): Custom nodata value if not in metadata.

    Returns:
        collections.namedtuple: A BBox namedtuple with (left, bottom, right, top) in EPSG:4326.
    """
    with rasterio.open(path) as src:
        data = src.read(1)
        nodata = src.nodata if src.nodata is not None else nodata_val
        if nodata is None: nodata = -9999.0
        
        mask = (data == nodata) | np.isnan(data)
        data_clean = data[~mask]
        
        if data_clean.size == 0:
            return None
            
        d_min, d_max = data_clean.min(), data_clean.max()
        if d_max == d_min:
            norm = np.zeros_like(data)
        else:
            norm = (data - d_min) / (d_max - d_min)
            
        cmap = cm.get_cmap(cmap_name)
        rgba = cmap(norm)
        rgba[mask, 3] = 0.0 # Transparent
        rgba[~mask, 3] = 0.8 # Global opacity
        
        rgba_uint8 = (rgba * 255).astype(np.uint8)
        img = Image.fromarray(rgba_uint8, 'RGBA')
        img.save(out_path, format="PNG")
        
        # Get lat/lon bounds
        bounds = src.bounds
        if src.crs is not None and src.crs.to_string() != 'EPSG:4326':
            from rasterio.warp import transform_bounds
            bounds = transform_bounds(src.crs, 'EPSG:4326', *bounds)
            # transform_bounds returns (left, bottom, right, top)
            from collections import namedtuple
            BBox = namedtuple('BBox', ['left', 'bottom', 'right', 'top'])
            bounds = BBox(*bounds)
            
        return bounds

def export_project_kmz(project_dir):
    """Export all relevant project layers into a single Google Earth KMZ file.

    This function bundles DTM, REL, FSI, and all simulation results (*_zdelta.tif, etc.)
    into a KMZ archive. It converts each raster to a PNG and generates a 
    `doc.kml` manifest with `GroundOverlay` elements.

    Args:
        project_dir (str): Path to the FlowPy project directory.

    Returns:
        str: Absolute path to the generated `.kmz` file.
    """
    import zipfile
    print(f"Exporting project {project_dir} to KMZ...")
    kmz_path = os.path.join(project_dir, 'project_layers.kmz')
    tmp_dir = os.path.join(project_dir, 'kmz_tmp')
    os.makedirs(tmp_dir, exist_ok=True)
    
    kml_content = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '<Document>',
        f'<name>{os.path.basename(project_dir)} Avalanche Layers</name>'
    ]
    
    # 1. Inputs
    layers = {
        'dem': os.path.join(project_dir, 'Inputs', 'dem.asc'),
        'rel': os.path.join(project_dir, 'Inputs', 'REL', 'rel.tif'),
        'fsi': os.path.join(project_dir, 'Inputs', 'RES', 'fsi.tif')
    }
    
    # 2. Outputs
    peak_root = os.path.join(project_dir, 'Outputs', 'com4FlowPy', 'peakFiles')
    if os.path.exists(peak_root):
        peak_files = glob.glob(os.path.join(peak_root, '**', '*.tif'), recursive=True)
        for pf in peak_files:
            pf_base = os.path.basename(pf)
            # Make sure we don't have name collisions in the zip
            pf_name = pf_base.replace('.tif', '')
            layers[pf_name] = pf

    with zipfile.ZipFile(kmz_path, 'w') as kmz:
        for key, path in layers.items():
            if not os.path.exists(path): continue
            
            # Map key to LAYER_INFO for cmap/name
            info_key = next((ik for ik in LAYER_INFO.keys() if ik in key.lower()), None)
            cmap = LAYER_INFO[info_key]['cmap'] if info_key else 'Reds'
            name = LAYER_INFO[info_key]['name'] if info_key else key
            
            # Sanitise key for filename
            safe_key = "".join([c if c.isalnum() else "_" for c in key])
            png_name = f"{safe_key}.png"
            png_path = os.path.join(tmp_dir, png_name)
            
            bounds = raster_to_png(path, png_path, cmap)
            if bounds:
                kmz.write(png_path, png_name)
                kml_content.append(f'''
    <GroundOverlay>
        <name>{name}</name>
        <Icon><href>{png_name}</href></Icon>
        <LatLonBox>
            <north>{bounds.top}</north>
            <south>{bounds.bottom}</south>
            <east>{bounds.right}</east>
            <west>{bounds.left}</west>
        </LatLonBox>
    </GroundOverlay>''')

        kml_content.append('</Document></kml>')
        kmz.writestr('doc.kml', '\n'.join(kml_content))
    
    import shutil
    shutil.rmtree(tmp_dir)
    print(f"Successfully created KMZ at {kmz_path}")
    return kmz_path

def export_cmd(args):
    """CLI command entry point for KMZ export.

    Args:
        args (argparse.Namespace): Arguments containing:
            project: Path to the project directory.
            open: Boolean flag to automatically open the KMZ in the OS default app.
    """
    kmz_file = export_project_kmz(args.project)
    if args.open:
        print(f"Attempting to open {kmz_file}...")
        try:
            import subprocess
            if os.name == 'nt':
                os.startfile(kmz_file)
            elif sys.platform == 'darwin':
                subprocess.run(['open', kmz_file])
            else:
                subprocess.run(['xdg-open', kmz_file])
        except Exception as e:
            print(f"Could not open KMZ: {e}")
