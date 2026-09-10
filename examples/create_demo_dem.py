#!/usr/bin/env python3
"""Create a small synthetic projected DEM for testing LiDAR Cave Scan."""

from __future__ import annotations

import argparse
from pathlib import Path


def create_demo_dem(out_path: str, size: int = 240, resolution: float = 1.0) -> Path:
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    y, x = np.mgrid[0:size, 0:size]
    terrain = 240 + 0.05 * x + 0.025 * y
    terrain += 1.4 * np.sin(x / 20) + 0.8 * np.cos(y / 18)

    def depression(cx, cy, radius, depth):
        d = np.hypot(x - cx, y - cy)
        bowl = np.clip(1 - d / radius, 0, 1)
        return depth * bowl**2

    dem = terrain.copy()
    dem -= depression(72, 82, 24, 3.2)
    dem -= depression(160, 130, 18, 1.8)
    dem -= depression(190, 62, 13, 1.1)
    dem += np.random.default_rng(7).normal(0, 0.035, dem.shape)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    transform = from_origin(420000, 6243000, resolution, resolution)
    profile = {
        "driver": "GTiff",
        "height": size,
        "width": size,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:2154",
        "transform": transform,
        "compress": "deflate",
        "nodata": -9999,
    }
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(dem.astype("float32"), 1)
    print(f"Demo DEM written to {out.resolve()}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="examples/demo_dem.tif")
    parser.add_argument("--size", type=int, default=240)
    parser.add_argument("--resolution", type=float, default=1.0)
    args = parser.parse_args()
    create_demo_dem(args.out, args.size, args.resolution)


if __name__ == "__main__":
    main()
