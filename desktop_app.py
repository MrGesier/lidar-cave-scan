#!/usr/bin/env python3
"""Launch the LiDAR Cave Scan desktop application."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lidar_cave_scan.gui import main


if __name__ == "__main__":
    main()
