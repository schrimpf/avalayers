import os
import json
import threading
import webbrowser
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
import rasterio
from rasterio.merge import merge
import requests
import pystac_client
import planetary_computer

PORT = 8080
BBOX = None

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Select DEM Area</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
        #map { height: 600px; width: 100%; border: 1px solid #ccc; }
        .controls { margin-top: 20px; }
        button { padding: 10px 20px; font-size: 16px; cursor: pointer; }
    </style>
</head>
<body>
    <h2 id="header">Select Area for DEM Download</h2>
    <p id="instructions">Draw a rectangle over the area you want to download (e.g., in British Columbia). Then click Download.</p>
    <div id="map"></div>
    <div class="controls">
        <button id="downloadBtn" disabled onclick="download()">Download DEMs</button>
        <p id="status"></p>
    </div>
    <script>
        // Parse URL parameters
        var urlParams = new URLSearchParams(window.location.search);
        var minx = parseFloat(urlParams.get('minx'));
        var miny = parseFloat(urlParams.get('miny'));
        var maxx = parseFloat(urlParams.get('maxx'));
        var maxy = parseFloat(urlParams.get('maxy'));
        var readonly = !isNaN(minx) && !isNaN(miny) && !isNaN(maxx) && !isNaN(maxy);

        var map = L.map('map');
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap'
        }).addTo(map);

        var drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);

        if (readonly) {
            // Draw the provided bbox
            var bounds = [[miny, minx], [maxy, maxx]];
            L.rectangle(bounds, {color: "#ff7800", weight: 2}).addTo(drawnItems);
            map.fitBounds(bounds, {padding: [50, 50]});
            
            document.getElementById('header').innerText = "Downloading DEMs for Command Line Box";
            document.getElementById('instructions').innerText = "You provided a bounding box in your terminal. We are continuing the script automatically. You can close this window at any time.";
            document.getElementById('downloadBtn').style.display = 'none';
            document.getElementById('status').innerText = "Downloading in terminal...";
        } else {
            // Interactive mode
            map.setView([49.5, -123.0], 8);
            var drawControl = new L.Control.Draw({
                draw: {
                    polygon: false, polyline: false, circle: false,
                    marker: false, circlemarker: false, rectangle: true
                },
                edit: { featureGroup: drawnItems }
            });
            map.addControl(drawControl);

            var currentBbox = null;

            map.on(L.Draw.Event.CREATED, function (e) {
                drawnItems.clearLayers();
                var layer = e.layer;
                drawnItems.addLayer(layer);
                var bounds = layer.getBounds();
                currentBbox = {
                    minx: bounds.getWest(),
                    miny: bounds.getSouth(),
                    maxx: bounds.getEast(),
                    maxy: bounds.getNorth()
                };
                document.getElementById('downloadBtn').disabled = false;
            });
        }

        function download() {
            document.getElementById('status').innerText = "Sending request to Python script...";
            document.getElementById('downloadBtn').disabled = true;
            fetch('/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentBbox)
            }).then(response => {
                document.getElementById('status').innerText = "Download started! Check your terminal for progress. You can close this window.";
            }).catch(err => {
                document.getElementById('status').innerText = "Error communicating with local server.";
            });
        }
    </script>
</body>
</html>
"""

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Allow serving paths that include query string params (e.g. /?minx=...)
        if self.path.startswith('/'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        else:
            self.send_error(404)
            
    def do_POST(self):
        global BBOX
        if self.path == '/submit':
            content_len = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_len)
            BBOX = json.loads(post_data.decode('utf-8'))
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
            
            # Shut down the server asynchronously
            threading.Thread(target=self.server.shutdown).start()

def get_bounding_box(prefill_bbox=None):
    """Open a browser-based Leaflet map to select a geographic bounding box.

    This function starts a temporary local HTTP server on port 8080 to serve 
    an interactive map. Once the user selects a box and clicks "Download",
     the coordinates are sent back to Python via a POST request.

    Args:
        prefill_bbox (dict, optional): Initial coordinates to show on the map.
            Should contain 'minx', 'miny', 'maxx', 'maxy'.

    Returns:
        dict: The selected bounding box coordinates.
    """
    server = socketserver.TCPServer(("", PORT), RequestHandler)
    if prefill_bbox:
        url = f"http://localhost:{PORT}/?minx={prefill_bbox['minx']}&miny={prefill_bbox['miny']}&maxx={prefill_bbox['maxx']}&maxy={prefill_bbox['maxy']}"
        print(f"Opening browser to visualize CLI bounding box at {url}...")
        webbrowser.open(url)
        # We don't block by serving forever, just return so the script can continue
        # Close server in the background shortly after loading
        def stop_server():
            import time
            time.sleep(3)
            server.shutdown()
            server.server_close()
        threading.Thread(target=stop_server, daemon=True).start()
        server.serve_forever() # block for a brief moment until thread shuts it down
        return prefill_bbox
    else:
        url = f"http://localhost:{PORT}"
        print(f"Opening browser at {url} to select bounding box...")
        webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return BBOX

def format_bbox_str(bbox):
    return f"{bbox['minx']:.4f}_{bbox['miny']:.4f}_{bbox['maxx']:.4f}_{bbox['maxy']:.4f}"

def download_copernicus_dem(bbox, output_dir):
    """Download and mosaic Copernicus GLO-30 DSM tiles for a bounding box.

    Uses the Microsoft Planetary Computer STAC API to find and download tiles.

    Args:
        bbox (dict): Bounding box coordinates (minx, miny, maxx, maxy).
        output_dir (str): Directory to save the final mosaicked GeoTIFF.
    """
    bbox_str = format_bbox_str(bbox)
    out_path = os.path.join(output_dir, f'copernicus_glo30_dsm_{bbox_str}.tif')
    if os.path.exists(out_path):
        print(f"Copernicus DEM already exists at {out_path}. Skipping download.")
        return
        
    print("Downloading Copernicus GLO-30 DEM via Planetary Computer...")
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    search_bbox = [bbox['minx'], bbox['miny'], bbox['maxx'], bbox['maxy']]
    search = catalog.search(
        collections=["cop-dem-glo-30"],
        bbox=search_bbox,
    )
    items = list(search.items())
    if not items:
        print("No Copernicus DEM tiles found for this area.")
        return

    src_files_to_mosaic = []
    print(f"Found {len(items)} Copernicus DEM tiles.")
    for item in items:
        url = item.assets["data"].href
        src = rasterio.open(url)
        src_files_to_mosaic.append(src)
    
    mosaic, out_trans = merge(src_files_to_mosaic, bounds=search_bbox)
    out_meta = src_files_to_mosaic[0].meta.copy()
    out_meta.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_trans,
    })

    with rasterio.open(out_path, "w", **out_meta) as dest:
        dest.write(mosaic)
    
    for src in src_files_to_mosaic:
        src.close()
    
    print(f"Copernicus DEM saved to {out_path}")

def download_cdem(bbox, output_dir):
    """Stub for Canadian Digital Elevation Model (CDEM) download.

    Currently prints instructions for manual download as CDEM endpoints 
    can be unstable for direct scripting.

    Args:
        bbox (dict): Bounding box coordinates.
        output_dir (str): Output directory.
    """
    # CDEM download is tricky without a direct WCS endpoint that supports arbitrary bboxes easily
    # It usually requires hitting the WMS or NRCAN extraction tool. Here we will leave a stub
    # and instructions, or try a generic WCS if it exists.
    print("Note: CDEM automatic download requires WCS/WFS endpoints which frequently change.")
    print("For CDEM, it's recommended to download the tiles manually from open.canada.ca")
    print("or use the Copernicus/FABDEM which are more easily scriptable.")

def download_fabdem(bbox, output_dir):
    """Download and mosaic FABDEM (bare-earth DTM) tiles.

    FABDEM is a processed version of Copernicus GLO-30 with trees and 
    buildings removed.

    Args:
        bbox (dict): Bounding box coordinates.
        output_dir (str): Output directory.
    """
    bbox_str = format_bbox_str(bbox)
    fabdem_out = os.path.join(output_dir, f'fabdem_dtm_{bbox_str}.tif')
    if os.path.exists(fabdem_out):
        print(f"FABDEM already exists at {fabdem_out}. Skipping download.")
        return
        
    try:
        from pyproj import CRS
        import rasterio
        from rasterio.merge import merge
        from shapely.geometry import box
        from geopandas import GeoDataFrame
        import requests
        from zipfile import ZipFile
        from pathlib import Path
        
        print("Downloading FABDEM (bare-earth DTM)...")
        bounds = (bbox['minx'], bbox['miny'], bbox['maxx'], bbox['maxy'])
        
        cache_dir = os.path.join(output_dir, 'raw_tiles', 'fabdem')
        os.makedirs(cache_dir, exist_ok=True)
        
        # 1. Gather Required Tiles
        rect = box(*bounds)
        base_url = "https://data.bris.ac.uk/datasets/s5hqmjcdj8yo2ibzi9b4ew3sn"
        print("Fetching FABDEM tile index...")
        response = requests.get(f"{base_url}/FABDEM_v1-2_tiles.geojson")
        response.raise_for_status()
        
        tiles_gdf = GeoDataFrame.from_features(response.json()["features"], crs=4326)
        intersecting_tiles = tiles_gdf[tiles_gdf.geometry.intersects(rect)]
        
        # 2. Extract or Download from Cache
        for zipfile_name in set(intersecting_tiles.zipfile_name):
            zip_path = Path(cache_dir) / zipfile_name
            if not zip_path.exists():
                print(f"Downloading {zipfile_name} from {base_url}... this may take a while (1GB+)")
                resp = requests.get(f"{base_url}/{zipfile_name}", stream=True)
                resp.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
            else:
                print(f"{zip_path} loaded from cache")
                
            print(f"Extracting {zip_path}...")
            with ZipFile(zip_path, 'r') as zf:
                zf.extractall(cache_dir)
                
        # 3. Correctly map the extracted file paths
        def correct_name(json_name): return json_name[0] + json_name[2:]
        tile_paths = [Path(cache_dir) / correct_name(f) for f in intersecting_tiles.file_name]
        
        # 4. Safe Merge using native rasterio
        print("Merging FABDEM tiles...")
        rasters = [rasterio.open(str(t)) for t in tile_paths]
        
        # Use positional args to be compatible with both new and old rasterio versions
        merged_raster, merged_transform = merge(rasters, bounds=bounds)
        
        with rasterio.open(str(tile_paths[0])) as template:
            source_crs = template.crs
            
        for r in rasters:
            r.close()
            
        meta = {
            'driver': 'GTiff',
            'count': merged_raster.shape[0],
            'height': merged_raster.shape[1],
            'width': merged_raster.shape[2],
            'dtype': merged_raster.dtype,
            'crs': source_crs,
            'transform': merged_transform,
            'nodata': -9999.0
        }
        
        with rasterio.open(fabdem_out, 'w', **meta) as dst:
            dst.write(merged_raster)
            
        print(f"FABDEM successfully downloaded and saved to {fabdem_out}")
    except Exception as e:
        print(f"Could not download FABDEM. Error: {e}")

import argparse

def download_cmd(args):
    """CLI command entry point for downloading DEMs.

    Args:
        args (argparse.Namespace): Arguments containing:
            bbox: Optional list of 4 floats (minx, miny, maxx, maxy).
            out: Optional output directory for DEMs.
    """
    if args.bbox:
        bbox = {
            'minx': args.bbox[0],
            'miny': args.bbox[1],
            'maxx': args.bbox[2],
            'maxy': args.bbox[3]
        }
        print(f"Using provided Bounding Box: {bbox}")
        bbox = get_bounding_box(bbox)
    else:
        bbox = get_bounding_box()
        
    if not bbox:
        print("No bounding box selected. Exiting.")
        return
        
    print(f"Selected Bounding Box: {bbox}")
    
    output_dir = args.out if getattr(args, 'out', None) else os.path.join(os.getcwd(), 'data', 'dems')
    os.makedirs(output_dir, exist_ok=True)
    
    download_copernicus_dem(bbox, output_dir)
    download_cdem(bbox, output_dir)
    download_fabdem(bbox, output_dir)
    
    print("Processing complete!")
 