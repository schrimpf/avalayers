import rasterio
from rasterio.merge import merge
import glob
import os

def mosaic_tiles(pattern, output_path):
    search_path = os.path.join('raw_data', pattern)
    files_to_mosaic = glob.glob(search_path)
    if not files_to_mosaic:
        print(f"No files found for pattern: {search_path}")
        return

    src_files_to_mosaic = []
    for fp in files_to_mosaic:
        src = rasterio.open(fp)
        src_files_to_mosaic.append(src)

    mosaic, out_trans = merge(src_files_to_mosaic)

    out_meta = src_files_to_mosaic[0].meta.copy()
    out_meta.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_trans,
        "crs": src_files_to_mosaic[0].crs
    })

    with rasterio.open(output_path, "w", **out_meta) as dest:
        dest.write(mosaic)
    
    for src in src_files_to_mosaic:
        src.close()
    
    print(f"Mosaicked {len(files_to_mosaic)} files into {output_path}")

if __name__ == "__main__":
    mosaic_tiles("dtm_w_*.tif", "sky_pilot_dtm_mosaicked.tif")
    mosaic_tiles("slope_w_*.tif", "sky_pilot_slope_mosaicked.tif")
