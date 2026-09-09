"""LiDAR DEM depression screening."""

from __future__ import annotations

import heapq
import json
import math
from pathlib import Path
from typing import Sequence


def fill_depressions(dem, valid):
    """Priority-flood fill, seeded at raster edges and nodata boundaries."""
    import numpy as np
    from scipy import ndimage as ndi

    h, w = dem.shape
    filled = dem.copy()
    boundary = valid & (~ndi.binary_erosion(valid, structure=np.ones((3, 3)), border_value=0))
    seen = ~valid.copy()
    heap = []
    for r, c in np.argwhere(boundary):
        r, c = int(r), int(c)
        seen[r, c] = True
        heap.append((float(dem[r, c]), r, c))
    heapq.heapify(heap)
    while heap:
        z, r, c = heapq.heappop(heap)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                rr, cc = r + dr, c + dc
                if 0 <= rr < h and 0 <= cc < w and not seen[rr, cc]:
                    seen[rr, cc] = True
                    nz = max(z, float(dem[rr, cc]))
                    filled[rr, cc] = nz
                    heapq.heappush(heap, (nz, rr, cc))
    return filled


def detect(dem, valid, transform, crs, min_depth=0.5, min_area=10, max_area=10000):
    import geopandas as gpd
    import numpy as np
    import rasterio
    from pyproj import CRS
    from rasterio.features import shapes
    from rasterio.windows import Window
    from scipy import ndimage as ndi
    from shapely.geometry import shape
    from shapely.ops import unary_union

    if not crs or not crs.is_projected:
        raise ValueError("Le MNT doit etre dans un CRS projete metrique, par exemple EPSG:2154.")
    units = CRS.from_user_input(crs).axis_info[0].unit_conversion_factor
    if not np.isclose(units, 1):
        raise ValueError("Les unites du CRS doivent etre des metres.")
    if abs(transform.b) > 1e-10 or abs(transform.d) > 1e-10:
        raise ValueError("Raster tourne non pris en charge : reprojetez-le d'abord avec gdalwarp.")

    pixel_area = abs(transform.a * transform.e)
    filled = fill_depressions(dem, valid)
    depth = np.where(valid, np.maximum(filled - dem, 0), 0)
    mask = valid & (depth > 1e-5)
    labels, _ = ndi.label(mask, structure=np.ones((3, 3)))
    objects = ndi.find_objects(labels)
    records = []
    ids = np.zeros(dem.shape, dtype=np.int32)

    for label_id, sl in enumerate(objects, 1):
        if sl is None:
            continue
        local = labels[sl] == label_id
        vals = depth[sl][local]
        area = len(vals) * pixel_area
        dmax = float(vals.max())
        if area < min_area or area > max_area or dmax < min_depth:
            continue

        rr, cc = np.where(local)
        rr = rr + sl[0].start
        cc = cc + sl[1].start
        touches_edge = bool(
            np.any((rr == 0) | (cc == 0) | (rr == dem.shape[0] - 1) | (cc == dem.shape[1] - 1))
        )
        if touches_edge:
            continue

        near_invalid = bool(np.any(ndi.binary_dilation(local, structure=np.ones((3, 3))) & ~valid[sl]))
        local_transform = rasterio.windows.transform(
            Window(sl[1].start, sl[0].start, sl[1].stop - sl[1].start, sl[0].stop - sl[0].start),
            transform,
        )
        polygon_parts = [
            shape(geometry)
            for geometry, value in shapes(local.astype("uint8"), mask=local, transform=local_transform)
            if value == 1
        ]
        geom = unary_union(polygon_parts)
        perimeter = geom.length
        circularity = float(4 * math.pi * geom.area / perimeter**2) if perimeter else 0
        volume = float(vals.sum() * pixel_area)
        score = min(
            100,
            round(
                20 * min(dmax / 2, 1)
                + 25 * min(area / 500, 1)
                + 20 * circularity
                + 15 * min(volume / 500, 1)
            ),
        )
        if near_invalid:
            score = max(0, score - 20)

        row = {
            "id": len(records) + 1,
            "area_m2": round(area, 2),
            "max_depth_m": round(dmax, 3),
            "mean_depth_m": round(float(vals.mean()), 3),
            "fill_volume_m3": round(volume, 2),
            "circularity": round(circularity, 3),
            "terrain_score": score,
            "nodata_edge": near_invalid,
            "x": round(geom.centroid.x, 3),
            "y": round(geom.centroid.y, 3),
            "geometry": geom,
        }
        records.append(row)
        ids[sl][local] = row["id"]

    columns = [
        "id",
        "area_m2",
        "max_depth_m",
        "mean_depth_m",
        "fill_volume_m3",
        "circularity",
        "terrain_score",
        "nodata_edge",
        "x",
        "y",
        "geometry",
    ]
    gdf = gpd.GeoDataFrame(records, geometry="geometry", crs=crs) if records else gpd.GeoDataFrame(columns=columns, geometry="geometry", crs=crs)
    return filled, depth, ids, gdf


def write_raster(path, data, profile, nodata=None):
    import numpy as np
    import rasterio

    raster_profile = profile.copy()
    raster_profile.update(
        count=1,
        dtype=str(data.dtype),
        compress="deflate",
        predictor=3 if np.issubdtype(data.dtype, np.floating) else 2,
    )
    if nodata is not None:
        raster_profile["nodata"] = nodata
    else:
        raster_profile.pop("nodata", None)
    with rasterio.open(path, "w", **raster_profile) as dst:
        dst.write(data, 1)


def run_lidar_scan(
    dem_path: str,
    out_dir: str = "outputs/lidar",
    bbox: Sequence[float] | None = None,
    min_depth: float = 0.5,
    min_area: float = 10.0,
    max_area: float = 10000.0,
    max_cells: int = 4000000,
    geology: str | None = None,
    cavities: str | None = None,
    faults: str | None = None,
) -> Path:
    import geopandas as gpd
    import matplotlib
    import numpy as np
    import rasterio
    from matplotlib.colors import LightSource
    from rasterio.windows import Window, from_bounds

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    with rasterio.open(dem_path) as src:
        if bbox:
            window = from_bounds(*bbox, transform=src.transform).round_offsets().round_lengths()
            window = window.intersection(Window(0, 0, src.width, src.height))
        else:
            window = Window(0, 0, src.width, src.height)
        if window.width * window.height > max_cells:
            raise ValueError("Emprise trop grande : utilisez --bbox ou augmentez --max-cells avec assez de RAM.")
        arr = src.read(1, window=window, masked=True)
        valid = ~np.ma.getmaskarray(arr) & np.isfinite(arr.data)
        dem = np.asarray(arr.filled(0), dtype=np.float64)
        transform = src.window_transform(window)
        crs = src.crs
        profile = src.profile.copy()
        profile.update(height=dem.shape[0], width=dem.shape[1], transform=transform)

    _, depth, ids, candidates = detect(dem, valid, transform, crs, min_depth, min_area, max_area)
    write_raster(out / "fill_depth.tif", np.where(valid, depth, -9999).astype("float32"), profile, -9999)
    write_raster(out / "candidate_ids.tif", ids, profile, 0)

    for key, path in [("geology", geology), ("cavities", cavities), ("faults", faults)]:
        if not path:
            continue
        layer = gpd.read_file(path)
        if layer.crs is None:
            raise ValueError(f"CRS manquant : {path}")
        layer = layer.to_crs(crs)
        union = layer.geometry.union_all() if len(layer) else None
        if key == "geology":
            candidates["karst_layer_intersects"] = [
                bool(union.intersects(geom)) if union is not None else False for geom in candidates.geometry
            ]
        else:
            candidates[f"dist_{key}_m"] = [
                round(geom.distance(union), 1) if union is not None else np.nan for geom in candidates.geometry
            ]

    if len(candidates):
        if "karst_layer_intersects" in candidates:
            candidates["terrain_score"] = (
                candidates.terrain_score + candidates.karst_layer_intersects.astype(int) * 15
            ).clip(0, 100)
        candidates = candidates.sort_values("terrain_score", ascending=False)
        candidates.to_file(out / "candidates.gpkg", layer="candidates", driver="GPKG")
    candidates.drop(columns="geometry").to_csv(out / "candidates.csv", index=False)

    dx = abs(transform.a)
    dy = abs(transform.e)
    gy, gx = np.gradient(dem, dy, dx)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    write_raster(out / "slope_deg.tif", np.where(valid, slope, -9999).astype("float32"), profile, -9999)

    shade = LightSource(azdeg=315, altdeg=45).hillshade(dem, vert_exag=1, dx=dx, dy=dy)
    fig, ax = plt.subplots(figsize=(12, 9))
    extent = [
        transform.c,
        transform.c + dem.shape[1] * transform.a,
        transform.f + dem.shape[0] * transform.e,
        transform.f,
    ]
    ax.imshow(np.ma.masked_where(~valid, shade), cmap="gray", extent=extent)
    if len(candidates):
        candidates.boundary.plot(ax=ax, edgecolor="red", linewidth=1)
        for _, row in candidates.head(50).iterrows():
            ax.annotate(str(row["id"]), (row["x"], row["y"]), fontsize=7, color="red")
    ax.set_title("Depressions candidates - LiDAR (non validees)")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(out / "map.png", dpi=160)
    plt.close(fig)

    run_metadata = {
        "input": str(dem_path),
        "crs": str(crs),
        "candidates": int(len(candidates)),
        "parameters": {
            "bbox": list(bbox) if bbox else None,
            "min_depth": min_depth,
            "min_area": min_area,
            "max_area": max_area,
            "max_cells": max_cells,
            "geology": geology,
            "cavities": cavities,
            "faults": faults,
        },
        "warning": "Screening only. No subsurface imaging or confirmed cave detection.",
    }
    (out / "run.json").write_text(json.dumps(run_metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(candidates)} candidats. Resultats : {out.resolve()}")
    return out
