"""LiDAR DEM depression screening."""

from __future__ import annotations

import heapq
import html
import json
import math
from pathlib import Path
from typing import Sequence

from .science import write_science_guide


def priority_class(score: float) -> str:
    """Return a practical review class from the heuristic terrain score."""
    if score >= 75:
        return "A - priorite terrain"
    if score >= 55:
        return "B - interessant"
    if score >= 35:
        return "C - controle rapide"
    return "D - faible signal"


def candidate_hypothesis(row) -> str:
    """Describe why a candidate deserves attention without claiming a cave."""
    parts = []
    if row.get("max_depth_m", 0) >= 2.0:
        parts.append("depression marquee")
    elif row.get("max_depth_m", 0) >= 1.0:
        parts.append("relief net")
    else:
        parts.append("relief subtil")

    if row.get("circularity", 0) >= 0.65:
        parts.append("forme compacte")
    elif row.get("elongation_ratio", 1) >= 2.5:
        parts.append("forme allongee")

    if row.get("fill_volume_m3", 0) >= 500:
        parts.append("volume notable")

    if row.get("karst_layer_intersects", False):
        parts.append("croise la couche karst")

    dist_cavities = row.get("dist_cavities_m")
    if dist_cavities == dist_cavities and dist_cavities is not None and dist_cavities <= 250:
        parts.append("proche d'une cavite connue")

    if row.get("nodata_edge", False):
        parts.append("attention bordure/nodata")

    return ", ".join(parts)


def review_hint(row) -> str:
    if row.get("nodata_edge", False):
        return "Verifier d'abord les bords de dalle et les pixels nodata."
    if row.get("terrain_score", 0) >= 75:
        return "Priorite haute: controler orthophoto, geologie et terrain si autorise."
    if row.get("terrain_score", 0) >= 55:
        return "Bon candidat: comparer avec ombrages multiples et inventaires publics."
    if row.get("terrain_score", 0) >= 35:
        return "Signal moyen: utile pour balayage QGIS, faible conclusion seul."
    return "Signal faible: conserver comme bruit potentiel ou controle secondaire."


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
        minx, miny, maxx, maxy = geom.bounds
        width = abs(maxx - minx)
        height = abs(maxy - miny)
        long_axis = max(width, height)
        short_axis = max(min(width, height), 1e-9)
        p90_depth = float(np.percentile(vals, 90))
        equivalent_diameter = float(math.sqrt((4 * area) / math.pi)) if area > 0 else 0
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
            "p90_depth_m": round(p90_depth, 3),
            "equiv_diameter_m": round(equivalent_diameter, 2),
            "bbox_width_m": round(width, 2),
            "bbox_height_m": round(height, 2),
            "elongation_ratio": round(long_axis / short_axis, 2),
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
        "p90_depth_m",
        "equiv_diameter_m",
        "bbox_width_m",
        "bbox_height_m",
        "elongation_ratio",
        "circularity",
        "terrain_score",
        "priority_class",
        "hypothesis",
        "review_hint",
        "nodata_edge",
        "x",
        "y",
        "geometry",
    ]
    gdf = gpd.GeoDataFrame(records, geometry="geometry", crs=crs) if records else gpd.GeoDataFrame(columns=columns, geometry="geometry", crs=crs)
    return filled, depth, ids, gdf


def enrich_candidates(candidates):
    if not len(candidates):
        return candidates
    candidates = candidates.copy()
    candidates["priority_class"] = [priority_class(score) for score in candidates["terrain_score"]]
    candidates["hypothesis"] = [candidate_hypothesis(row) for _, row in candidates.iterrows()]
    candidates["review_hint"] = [review_hint(row) for _, row in candidates.iterrows()]
    return candidates


def add_wgs84_locations(candidates):
    import geopandas as gpd

    if not len(candidates):
        return candidates
    candidates = candidates.copy()
    centroids = gpd.GeoSeries(candidates.geometry.centroid, crs=candidates.crs).to_crs(epsg=4326)
    candidates["longitude"] = [round(point.x, 7) for point in centroids]
    candidates["latitude"] = [round(point.y, 7) for point in centroids]
    candidates["google_maps"] = [
        f"https://www.google.com/maps?q={lat},{lon}"
        for lat, lon in zip(candidates["latitude"], candidates["longitude"])
    ]
    candidates["openstreetmap"] = [
        f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}"
        for lat, lon in zip(candidates["latitude"], candidates["longitude"])
    ]
    return candidates


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


def write_interactive_map(out: Path, candidates) -> None:
    if len(candidates):
        wgs84 = candidates.to_crs(epsg=4326)
        center_lat = float(candidates["latitude"].mean()) if "latitude" in candidates else 46.5
        center_lon = float(candidates["longitude"].mean()) if "longitude" in candidates else 2.5
        geojson = wgs84.to_json()
    else:
        center_lat = 46.5
        center_lon = 2.5
        geojson = '{"type":"FeatureCollection","features":[]}'

    map_html = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Carte interactive - LiDAR Cave Scan</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <style>
    html, body, #map {{ height: 100%; margin: 0; }}
    body {{ font-family: Segoe UI, Arial, sans-serif; }}
    .panel {{
      position: absolute; z-index: 1000; top: 14px; left: 14px; max-width: 360px;
      background: white; border-radius: 8px; box-shadow: 0 8px 28px rgba(0,0,0,.18);
      padding: 14px 16px; line-height: 1.35;
    }}
    .panel h1 {{ font-size: 18px; margin: 0 0 8px; }}
    .panel p {{ margin: 6px 0; font-size: 13px; }}
    .legend {{ display: grid; gap: 5px; margin-top: 8px; font-size: 13px; }}
    .swatch {{ display: inline-block; width: 14px; height: 14px; margin-right: 7px; vertical-align: -2px; }}
    .popup table {{ border-collapse: collapse; font-size: 12px; }}
    .popup td {{ padding: 3px 6px 3px 0; vertical-align: top; }}
    .popup a {{ color: #0b5a74; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <aside class="panel">
    <h1>LiDAR Cave Scan</h1>
    <p>Carte zoomable des candidats. Les contours indiquent des dépressions de surface à vérifier, pas des grottes confirmées.</p>
    <p>Utilise la molette pour zoomer/dézoomer, clique sur un candidat pour voir ses coordonnées.</p>
    <div class="legend">
      <div><span class="swatch" style="background:#d7191c"></span>A - priorite terrain</div>
      <div><span class="swatch" style="background:#fdae61"></span>B - interessant</div>
      <div><span class="swatch" style="background:#2c7bb6"></span>C - controle rapide</div>
      <div><span class="swatch" style="background:#969696"></span>D - faible signal</div>
    </div>
  </aside>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const candidates = {geojson};
    const colors = {{
      "A - priorite terrain": "#d7191c",
      "B - interessant": "#fdae61",
      "C - controle rapide": "#2c7bb6",
      "D - faible signal": "#969696"
    }};
    const map = L.map("map", {{ scrollWheelZoom: true }}).setView([{center_lat:.7f}, {center_lon:.7f}], 17);
    L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
      maxZoom: 20,
      attribution: "&copy; OpenStreetMap contributors"
    }}).addTo(map);

    const layer = L.geoJSON(candidates, {{
      style: feature => ({{
        color: colors[feature.properties.priority_class] || "#d4573d",
        weight: 3,
        fillOpacity: 0.18
      }}),
      onEachFeature: (feature, layer) => {{
        const p = feature.properties;
        const lat = p.latitude;
        const lon = p.longitude;
        layer.bindPopup(`
          <div class="popup">
            <h3>Candidat ${{p.id}} - score ${{p.terrain_score}}</h3>
            <table>
              <tr><td>Classe</td><td>${{p.priority_class || ""}}</td></tr>
              <tr><td>Coordonnées</td><td>${{lat}}, ${{lon}}</td></tr>
              <tr><td>Profondeur max</td><td>${{p.max_depth_m}} m</td></tr>
              <tr><td>Profondeur P90</td><td>${{p.p90_depth_m}} m</td></tr>
              <tr><td>Surface</td><td>${{p.area_m2}} m²</td></tr>
              <tr><td>Volume</td><td>${{p.fill_volume_m3}} m³</td></tr>
              <tr><td>Lecture</td><td>${{p.hypothesis || ""}}</td></tr>
              <tr><td>Action</td><td>${{p.review_hint || ""}}</td></tr>
            </table>
            <p><a target="_blank" href="${{p.google_maps}}">Ouvrir dans Google Maps</a></p>
            <p><a target="_blank" href="${{p.openstreetmap}}">Ouvrir dans OpenStreetMap</a></p>
          </div>
        `);
      }}
    }}).addTo(map);
    if (layer.getBounds().isValid()) {{
      map.fitBounds(layer.getBounds(), {{ padding: [40, 40], maxZoom: 18 }});
    }}
  </script>
</body>
</html>
"""
    (out / "interactive_map.html").write_text(map_html, encoding="utf-8")


def write_report(out: Path, candidates, run_metadata: dict) -> None:
    rows = []
    for _, row in candidates.head(100).iterrows():
        rows.append(
            "<tr>"
            f"<td>{int(row['id'])}</td>"
            f"<td>{html.escape(str(row.get('priority_class', '')))}</td>"
            f"<td>{row.get('terrain_score', '')}</td>"
            f"<td>{row.get('max_depth_m', '')}</td>"
            f"<td>{row.get('p90_depth_m', '')}</td>"
            f"<td>{row.get('area_m2', '')}</td>"
            f"<td>{row.get('fill_volume_m3', '')}</td>"
            f"<td>{html.escape(str(row.get('hypothesis', '')))}</td>"
            f"<td>{html.escape(str(row.get('review_hint', '')))}</td>"
            f"<td>{row.get('latitude', '')}</td>"
            f"<td>{row.get('longitude', '')}</td>"
            f"<td><a href=\"{html.escape(str(row.get('google_maps', '')))}\">Google Maps</a></td>"
            f"<td>{row.get('x', '')}</td>"
            f"<td>{row.get('y', '')}</td>"
            "</tr>"
        )

    if rows:
        table = "\n".join(rows)
    else:
        table = '<tr><td colspan="14">Aucun candidat conserve avec ces seuils.</td></tr>'

    report = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Rapport LiDAR Cave Scan</title>
  <style>
    body {{ margin: 0; font-family: Segoe UI, Arial, sans-serif; color: #19201d; background: #f3f0e8; }}
    header {{ padding: 28px 34px; background: #173b35; color: white; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; }}
    main {{ padding: 24px 34px 40px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(150px, 1fr)); gap: 12px; margin-bottom: 22px; }}
    .metric {{ background: white; border-left: 5px solid #d4573d; padding: 14px; box-shadow: 0 1px 2px rgba(0,0,0,.08); }}
    .metric strong {{ display: block; font-size: 24px; }}
    .panel {{ background: white; padding: 18px; margin: 18px 0; box-shadow: 0 1px 2px rgba(0,0,0,.08); }}
    img {{ max-width: 100%; border: 1px solid #d5d0c4; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 8px 9px; border-bottom: 1px solid #e2ddd2; text-align: left; vertical-align: top; }}
    th {{ background: #ede7dc; position: sticky; top: 0; }}
    .warning {{ color: #6b2e1d; background: #fff0e8; border-left: 5px solid #d4573d; padding: 12px 14px; }}
    a {{ color: #0b5a74; }}
  </style>
</head>
<body>
  <header>
    <h1>Rapport LiDAR Cave Scan</h1>
    <div>Presélection morphologique de dépressions de surface, sans validation de cavité.</div>
  </header>
  <main>
    <section class="grid">
      <div class="metric"><span>Candidats</span><strong>{run_metadata.get('candidates', 0)}</strong></div>
      <div class="metric"><span>Meilleur score</span><strong>{int(candidates['terrain_score'].max()) if len(candidates) else 0}</strong></div>
      <div class="metric"><span>CRS</span><strong style="font-size:15px">{html.escape(str(run_metadata.get('crs', '')))}</strong></div>
      <div class="metric"><span>Seuil profondeur</span><strong>{run_metadata['parameters'].get('min_depth')} m</strong></div>
    </section>
    <p class="warning">{html.escape(run_metadata.get('warning', ''))}</p>
    <section class="panel">
      <h2>Carte d'inspection</h2>
      <p>Cette image sert au contrôle visuel. Pour zoomer, dézoomer et situer les points, ouvrez la carte interactive.</p>
      <p><a href="interactive_map.html">Ouvrir la carte interactive zoomable</a></p>
      <img src="map.png" alt="Carte des candidats LiDAR">
    </section>
    <section class="panel">
      <h2>Classement des candidats</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th><th>Classe</th><th>Score</th><th>Max m</th><th>P90 m</th><th>Surface m²</th>
            <th>Volume m³</th><th>Hypothèse</th><th>Contrôle conseillé</th>
            <th>Latitude</th><th>Longitude</th><th>Carte</th><th>X</th><th>Y</th>
          </tr>
        </thead>
        <tbody>{table}</tbody>
      </table>
    </section>
    <section class="panel">
      <h2>Fichiers produits</h2>
      <p><a href="interactive_map.html">interactive_map.html</a> · <a href="candidate_locations.csv">candidate_locations.csv</a> · <a href="candidates.csv">candidates.csv</a> · <a href="candidates.geojson">candidates.geojson</a> · <a href="candidates.gpkg">candidates.gpkg</a> · <a href="ranked_candidates.png">ranked_candidates.png</a></p>
      <p><a href="science_guide.html">Comprendre l'outil et les limites scientifiques</a></p>
    </section>
  </main>
</body>
</html>
"""
    (out / "report.html").write_text(report, encoding="utf-8")


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

    candidates = enrich_candidates(candidates)
    candidates = add_wgs84_locations(candidates)

    if len(candidates):
        if "karst_layer_intersects" in candidates:
            candidates["terrain_score"] = (
                candidates.terrain_score + candidates.karst_layer_intersects.astype(int) * 15
            ).clip(0, 100)
            candidates = enrich_candidates(candidates)
            candidates = add_wgs84_locations(candidates)
        candidates = candidates.sort_values("terrain_score", ascending=False)
        candidates.to_file(out / "candidates.gpkg", layer="candidates", driver="GPKG")
        candidates.to_file(out / "candidates.geojson", driver="GeoJSON")
    candidates.drop(columns="geometry").to_csv(out / "candidates.csv", index=False)
    location_columns = [
        column
        for column in [
            "id",
            "priority_class",
            "terrain_score",
            "latitude",
            "longitude",
            "google_maps",
            "openstreetmap",
            "max_depth_m",
            "p90_depth_m",
            "area_m2",
            "fill_volume_m3",
            "hypothesis",
            "review_hint",
        ]
        if column in candidates.columns
    ]
    candidates[location_columns].to_csv(out / "candidate_locations.csv", index=False)

    dx = abs(transform.a)
    dy = abs(transform.e)
    gy, gx = np.gradient(dem, dy, dx)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    write_raster(out / "slope_deg.tif", np.where(valid, slope, -9999).astype("float32"), profile, -9999)

    shade = LightSource(azdeg=315, altdeg=45).hillshade(dem, vert_exag=1, dx=dx, dy=dy)
    fig, ax = plt.subplots(figsize=(13, 9))
    extent = [
        transform.c,
        transform.c + dem.shape[1] * transform.a,
        transform.f + dem.shape[0] * transform.e,
        transform.f,
    ]
    ax.imshow(np.ma.masked_where(~valid, shade), cmap="gray", extent=extent)
    if len(candidates):
        class_colors = {
            "A - priorite terrain": "#d7191c",
            "B - interessant": "#fdae61",
            "C - controle rapide": "#2c7bb6",
            "D - faible signal": "#969696",
        }
        for class_name, color in class_colors.items():
            subset = candidates[candidates["priority_class"] == class_name]
            if len(subset):
                subset.boundary.plot(ax=ax, edgecolor=color, linewidth=1.8, label=class_name)
        for _, row in candidates.head(50).iterrows():
            ax.annotate(
                f"{row['id']} ({row['terrain_score']})",
                (row["x"], row["y"]),
                fontsize=8,
                color="#101010",
                bbox={"boxstyle": "round,pad=0.18", "fc": "white", "ec": "none", "alpha": 0.78},
            )
        ax.legend(loc="upper right", framealpha=0.9)
    ax.set_title("Depressions candidates - LiDAR (scores exploratoires, non valides)")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(out / "map.png", dpi=160)
    plt.close(fig)

    if len(candidates):
        chart = candidates.head(20).sort_values("terrain_score")
        fig, ax = plt.subplots(figsize=(9, max(3.5, len(chart) * 0.35)))
        colors = [
            "#d7191c" if score >= 75 else "#fdae61" if score >= 55 else "#2c7bb6" if score >= 35 else "#969696"
            for score in chart["terrain_score"]
        ]
        ax.barh([str(int(v)) for v in chart["id"]], chart["terrain_score"], color=colors)
        ax.set_xlabel("Score heuristique")
        ax.set_ylabel("ID candidat")
        ax.set_xlim(0, 100)
        ax.set_title("Classement des candidats")
        fig.tight_layout()
        fig.savefig(out / "ranked_candidates.png", dpi=160)
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
    write_interactive_map(out, candidates)
    write_science_guide(out)
    write_report(out, candidates, run_metadata)
    print(f"{len(candidates)} candidats. Resultats : {out.resolve()}")
    return out
