"""Command-line interface for LiDAR Cave Scan."""

from __future__ import annotations

import argparse
import sys

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lidar-cave-scan",
        description=(
            "Screen LiDAR DEMs for closed surface depressions and run "
            "experimental SAR micro-motion utilities. This is not a cave detector."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    gui = subparsers.add_parser(
        "gui",
        help="Open the Windows desktop interface.",
    )
    gui.set_defaults(handler=_run_gui)

    lidar = subparsers.add_parser(
        "lidar",
        help="Analyze a metric LiDAR DEM GeoTIFF for closed surface depressions.",
    )
    lidar.add_argument("--dem", required=True, help="Input bare-earth DEM GeoTIFF.")
    lidar.add_argument("--out", default="outputs/lidar", help="Output directory.")
    lidar.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        metavar=("XMIN", "YMIN", "XMAX", "YMAX"),
        help="Optional bounding box in the DEM projected CRS.",
    )
    lidar.add_argument("--min-depth", type=float, default=0.5)
    lidar.add_argument("--min-area", type=float, default=10.0)
    lidar.add_argument("--max-area", type=float, default=10000.0)
    lidar.add_argument("--max-cells", type=int, default=4000000)
    lidar.add_argument(
        "--detect-singularities",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Also detect local morphometric anomalies beyond closed depressions.",
    )
    lidar.add_argument("--singularity-z", type=float, default=2.4, help="Robust z-score threshold for anomaly detection.")
    lidar.add_argument("--singularity-min-area", type=float, default=8.0, help="Minimum area for singularity patches.")
    lidar.add_argument("--singularity-max-area", type=float, default=2500.0, help="Maximum area for singularity patches.")
    lidar.add_argument("--smooth-sigma", type=float, default=6.0, help="Gaussian smoothing radius, in pixels, for local terrain residuals.")
    lidar.add_argument("--geology", help="Optional pre-filtered karst geology vector layer.")
    lidar.add_argument("--cavities", help="Optional known cavities vector layer.")
    lidar.add_argument("--faults", help="Optional faults vector layer.")
    lidar.set_defaults(handler=_run_lidar)

    micro = subparsers.add_parser(
        "microdoppler",
        help="Analyze prepared coherent slow-time SAR samples, or run a synthetic demo.",
    )
    micro.add_argument("--input", help="NPZ containing time_s, samples, wavelength_m, optional reference.")
    micro.add_argument("--demo", action="store_true", help="Generate and analyze a synthetic oscillating reflector.")
    micro.add_argument("--out", default="outputs/microdoppler", help="Output directory.")
    micro.add_argument("--min-frequency", type=float, default=0.1)
    micro.add_argument("--max-frequency", type=float)
    micro.set_defaults(handler=_run_microdoppler)

    catalog = subparsers.add_parser(
        "catalog",
        help="Search public Copernicus Sentinel-1 SLC catalog metadata.",
    )
    catalog.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    catalog.add_argument("--start", required=True, help="Start date, for example 2025-01-01.")
    catalog.add_argument("--end", required=True, help="End date, for example 2025-02-01.")
    catalog.add_argument("--out", default="outputs/sar_catalog.json")
    catalog.add_argument("--limit", type=int, default=100)
    catalog.set_defaults(handler=_run_catalog)

    return parser


def _run_gui(args: argparse.Namespace) -> int:
    from .gui import main as gui_main

    gui_main()
    return 0


def _run_lidar(args: argparse.Namespace) -> int:
    from .lidar import run_lidar_scan

    run_lidar_scan(
        dem_path=args.dem,
        out_dir=args.out,
        bbox=args.bbox,
        min_depth=args.min_depth,
        min_area=args.min_area,
        max_area=args.max_area,
        max_cells=args.max_cells,
        geology=args.geology,
        cavities=args.cavities,
        faults=args.faults,
        include_singularities=args.detect_singularities,
        singularity_z=args.singularity_z,
        singularity_min_area=args.singularity_min_area,
        singularity_max_area=args.singularity_max_area,
        smooth_sigma=args.smooth_sigma,
    )
    return 0


def _run_microdoppler(args: argparse.Namespace) -> int:
    from .microdoppler import run_microdoppler

    run_microdoppler(
        input_path=args.input,
        demo=args.demo,
        out_dir=args.out,
        min_frequency=args.min_frequency,
        max_frequency=args.max_frequency,
    )
    return 0


def _run_catalog(args: argparse.Namespace) -> int:
    from .catalog import run_catalog_search

    run_catalog_search(
        bbox=args.bbox,
        start=args.start,
        end=args.end,
        out_path=args.out,
        limit=args.limit,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args) or 0)
    except Exception as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
