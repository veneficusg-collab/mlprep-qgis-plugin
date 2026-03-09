#landslide_worker.py
import sys
import argparse
import os
import json
import numpy as np
import rasterio
import rasterio.mask
import geopandas as gpd
from rasterio import features
from shapely.geometry import shape
from rasterio.warp import reproject, Resampling

def run_landslide_detection(dem_path, before_path, after_path, lulc_path, output_path, roi_path, filter_col, filter_val):
    NDVI_THRESHOLD = -0.2
    TARGET_CRS = "EPSG:4326"
    METRIC_CRS = "EPSG:32651" 
    BUFFER_METERS = 10

    # 1. LOAD AND FILTER ROI
    if not os.path.exists(roi_path):
        return {"status": "error", "message": f"ROI file not found at: {roi_path}"}

    try:
        gdf = gpd.read_file(roi_path).to_crs(TARGET_CRS)
        
        # Filter: e.g. WHERE ADM3_EN == 'Alamada'
        if filter_col and filter_val:
            gdf = gdf[gdf[filter_col] == filter_val]
            
        if gdf.empty:
            return {"status": "error", "message": f"No features found for {filter_col}={filter_val}"}
            
        roi_union = gdf.unary_union
        shapes = [roi_union]
    except Exception as e:
        return {"status": "error", "message": f"Error loading ROI: {str(e)}"}

    # Initialize meta
    after_meta = None
    after_crs = None

    # 2. LOAD IMAGES (Satellite)
    with rasterio.open(after_path) as src_after:
        try:
            after_img, after_transform = rasterio.mask.mask(
                src_after, shapes, crop=True, nodata=np.nan, filled=True
            )
            after_meta = src_after.meta.copy()
            after_meta.update({
                "driver": "GTiff",
                "height": after_img.shape[1],
                "width": after_img.shape[2],
                "transform": after_transform
            })
            after_crs = src_after.crs
        except ValueError:
            return {"status": "error", "message": "ROI outside After image bounds"}

    with rasterio.open(before_path) as src_before:
        try:
            before_img, _ = rasterio.mask.mask(
                src_before, shapes, crop=True, nodata=np.nan, filled=True
            )
        except ValueError:
            return {"status": "error", "message": "ROI outside Before image bounds"}

    if after_img.shape != before_img.shape:
         return {"status": "error", "message": f"Shape mismatch: {after_img.shape} vs {before_img.shape}"}

    # 3. CALCULATE NDVI
    def calculate_ndvi(arr):
        nir = arr[0].astype('float64')
        red = arr[1].astype('float64')
        numerator = nir - red
        denominator = nir + red
        np.seterr(divide='ignore', invalid='ignore')
        return np.where(denominator != 0, numerator / denominator, np.nan)

    ndvi_after = calculate_ndvi(after_img)
    ndvi_before = calculate_ndvi(before_img)
    ndvi_diff = ndvi_after - ndvi_before

    # 4. DEM & GEOMORPHOLOGY MASKING
    if dem_path and os.path.exists(dem_path):
        try:
            with rasterio.open(dem_path) as src_dem:
                dem_img, dem_transform = rasterio.mask.mask(src_dem, shapes, crop=True)
                elevation = dem_img[0]
                
                if src_dem.nodata is not None:
                    elevation = np.where(elevation == src_dem.nodata, np.nan, elevation)
                
                res_x, res_y = src_dem.res
                scale_factor = 111320 
                dy, dx = np.gradient(elevation, res_y * scale_factor, res_x * scale_factor)
                slope_percent = np.sqrt(dx**2 + dy**2) * 100
                
                conditions = [
                    (elevation < 5) & (slope_percent < 8),
                    (elevation >= 5) & (elevation <= 50) & (slope_percent < 8),
                    (elevation > 50) & (elevation <= 150) & (slope_percent < 8),
                    (elevation > 150) & (elevation <= 500) & (slope_percent < 8),
                    (elevation >= 500) & (slope_percent < 20),
                    (elevation > 50) & (elevation <= 500) & (slope_percent >= 8) & (slope_percent < 20),
                    (elevation < 50) & (slope_percent >= 8),
                    (elevation >= 50) & (elevation <= 500) & (slope_percent >= 20),
                    (elevation >= 500) & (slope_percent >= 20)
                ]
                geomorphology = np.select(conditions, [1, 2, 3, 4, 5, 6, 7, 8, 9], default=0).astype(np.uint8)
                raw_hazard_mask = (geomorphology >= 8).astype(np.uint8)

                aligned_hazard_mask = np.zeros(ndvi_diff.shape, dtype='uint8')
                reproject(
                    source=raw_hazard_mask,
                    destination=aligned_hazard_mask,
                    src_transform=dem_transform,
                    src_crs=src_dem.crs,
                    dst_transform=after_transform,
                    dst_crs=after_crs,
                    resampling=Resampling.nearest
                )
                ndvi_diff[aligned_hazard_mask == 0] = np.nan

        except Exception as e:
            return {"status": "error", "message": f"DEM Error: {str(e)}"}

    # 5. LULC MASKING
    if lulc_path and os.path.exists(lulc_path):
        try:
            landcover_gdf = gpd.read_file(lulc_path).to_crs(TARGET_CRS)
            exclude_classes = ["Built-up", "Inland Water", "Marshland/Swamp", "Open/Barren", "Annual Crop"]
            col_name = 'class_name'
            if col_name not in landcover_gdf.columns:
                for c in ['Class_Name', 'CLASS_NAME', 'type', 'TYPE']:
                    if c in landcover_gdf.columns:
                        col_name = c
                        break
            
            if col_name in landcover_gdf.columns:
                mask_out_gdf = landcover_gdf[landcover_gdf[col_name].isin(exclude_classes)]
                if not mask_out_gdf.empty:
                    mask_out_gdf = mask_out_gdf.to_crs(METRIC_CRS)
                    mask_out_gdf['geometry'] = mask_out_gdf.geometry.buffer(BUFFER_METERS)
                    mask_out_gdf = mask_out_gdf.to_crs(TARGET_CRS)
                    temp_exclude = mask_out_gdf.clip(roi_union)
                    if not temp_exclude.empty:
                        lc_mask = features.geometry_mask(
                            temp_exclude.geometry,
                            out_shape=(after_img.shape[1], after_img.shape[2]),
                            transform=after_transform,
                            invert=True 
                        )
                        ndvi_diff[lc_mask] = np.nan
        except Exception as e:
            return {"status": "error", "message": f"LULC Error: {str(e)}"}

    # 6. THRESHOLD & SAVE
    landslide_mask = (ndvi_diff < NDVI_THRESHOLD).astype('uint8')
    landslide_mask[np.isnan(ndvi_diff)] = 0

    after_meta.update({"count": 1, "dtype": 'uint8', "nodata": 0})
    with rasterio.open(output_path, "w", **after_meta) as dst:
        dst.write(landslide_mask, 1)

    base, ext = os.path.splitext(output_path)
    ndvi_output_path = f"{base}_ndvi_diff{ext}"
    after_meta.update({"count": 1, "dtype": 'float32', "nodata": np.nan})
    with rasterio.open(ndvi_output_path, "w", **after_meta) as dst:
        dst.write(ndvi_diff.astype('float32'), 1)

    return {
        "status": "success", 
        "output_mask": output_path,
        "output_ndvi": ndvi_output_path
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dem", required=True)
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--lulc", required=True)
    parser.add_argument("--output", required=True)
    # NEW ARGUMENTS FOR DYNAMIC ROI
    parser.add_argument("--roi_path", required=True)
    parser.add_argument("--filter_col", required=True)
    parser.add_argument("--filter_val", required=True)
    
    args = parser.parse_args()
    
    try:
        result = run_landslide_detection(
            args.dem, args.before, args.after, args.lulc, args.output,
            args.roi_path, args.filter_col, args.filter_val
        )
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))