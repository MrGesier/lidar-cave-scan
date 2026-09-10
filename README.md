# LiDAR Cave Scan

Outil Python de présélection de dépressions de surface dans un MNT LiDAR, avec deux utilitaires de recherche SAR expérimentaux. Le projet est prêt à être publié sur GitHub et à être déployé dans un conteneur Docker.

Important : cet outil ne détecte pas directement les grottes, ne voit pas sous terre et ne fournit pas une probabilité de cavité. Les résultats sont des indices de tri à vérifier dans QGIS et sur le terrain par des personnes compétentes et autorisées.

## Fonctionnalités

- Analyse d'un MNT LiDAR GeoTIFF en CRS projeté métrique.
- Détection de dépressions fermées par remplissage priority-flood.
- Export de rasters, GeoPackage, CSV, carte PNG et métadonnées JSON.
- Croisement facultatif avec géologie, cavités connues et failles.
- Démo micro-Doppler SAR sur données synthétiques.
- Recherche de métadonnées publiques Sentinel-1 SLC via le catalogue STAC Copernicus.
- Interface desktop Windows avec boutons de lancement et journal d'exécution.
- Générateur de MNT synthétique pour tester l'outil sans données externes.

## Structure

```text
.
├── app.py
├── desktop_app.py
├── run_desktop.bat
├── install_windows.bat
├── examples/
│   └── create_demo_dem.py
├── src/lidar_cave_scan/
│   ├── cli.py
│   ├── gui.py
│   ├── lidar.py
│   ├── microdoppler.py
│   └── catalog.py
├── tests/
├── requirements.txt
├── pyproject.toml
├── Dockerfile
└── .github/workflows/ci.yml
```

## Installation locale

Python 3.11 ou 3.12 est recommandé.

Sur Windows, le plus simple est de double-cliquer sur :

```text
install_windows.bat
```

Le script crée `.venv` puis installe l'application et ses dépendances.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Sous Windows, l'installation de `rasterio` et `geopandas` peut nécessiter un environnement conda-forge si `pip` échoue :

```powershell
conda create -n lidar-cave-scan -c conda-forge python=3.12 numpy scipy rasterio geopandas shapely pyproj matplotlib
conda activate lidar-cave-scan
python -m pip install -e .
```

## Lancer le logiciel

Après installation, double-cliquez sur :

```text
LANCER_LIDAR_CAVE_SCAN.bat
```

Ce raccourci ouvre l'interface desktop. Le lanceur historique reste aussi disponible :

```text
run_desktop.bat
```

Ou lancez-le en ligne de commande :

```powershell
python app.py gui
```

L'interface permet de choisir un GeoTIFF, régler les seuils, lancer l'analyse, ouvrir le dossier de résultats, créer un MNT de test et lancer la démo micro-Doppler.

## Tester avec un MNT synthétique

Pour voir l'outil sans télécharger immédiatement une dalle LiDAR :

```powershell
python examples\create_demo_dem.py --out examples\demo_dem.tif
python app.py lidar --dem examples\demo_dem.tif --out outputs\demo_lidar
```

Dans l'interface desktop, utilisez directement le bouton `Créer et analyser un MNT de test`.

Vous pouvez aussi double-cliquer sur :

```text
run_demo.bat
```

Ce script génère le GeoTIFF de test, lance l'analyse et ouvre automatiquement `outputs\demo_lidar`.

## Analyse LiDAR

Téléchargez un MNT LiDAR HD terrain nu au format GeoTIFF. Les coordonnées de `--bbox` doivent être dans le CRS projeté du raster, par exemple Lambert-93 EPSG:2154 en France métropolitaine. N'utilisez pas directement latitude/longitude pour cette commande.

```powershell
python app.py lidar --dem "C:\data\mnt.tif" --out outputs\barzun
```

Avec une emprise métrique :

```powershell
python app.py lidar --dem "C:\data\mnt.tif" --bbox 421000 6242000 422000 6243000 --min-depth 0.5 --min-area 10 --max-area 10000 --out outputs\barzun
```

### Couches facultatives

Les couches vectorielles doivent avoir un CRS défini. La couche géologique doit déjà être filtrée sur les lithologies pertinentes.

```powershell
python app.py lidar --dem "C:\data\mnt.tif" --geology "C:\data\calcaires.gpkg" --cavities "C:\data\cavites.gpkg" --faults "C:\data\failles.gpkg"
```

## Résultats LiDAR

- `fill_depth.tif` : profondeur de remplissage en mètres.
- `slope_deg.tif` : pente en degrés.
- `candidate_ids.tif` : identifiants raster des dépressions conservées.
- `candidates.gpkg` : polygones et attributs pour QGIS.
- `candidates.geojson` : version GeoJSON pour webmapping ou outils SIG légers.
- `candidates.csv` : table lisible dans Excel/QGIS.
- `candidate_locations.csv` : coordonnées GPS, liens Google Maps/OpenStreetMap et résumé terrain.
- `map.png` : carte d'inspection avec ombrage, contours, classes et scores.
- `interactive_map.html` : carte zoomable/dézoomable avec fond OpenStreetMap et popups.
- `ranked_candidates.png` : graphique de classement des candidats.
- `report.html` : rapport lisible dans le navigateur avec synthèse, carte et tableau.
- `run.json` : paramètres et provenance.

Les champs enrichis incluent `priority_class`, `hypothesis`, `review_hint`, `latitude`, `longitude`, `google_maps`, `openstreetmap`, `p90_depth_m`, `equiv_diameter_m`, `elongation_ratio`, `bbox_width_m` et `bbox_height_m`.

La carte `map.png` est une image statique pour inspection. Pour naviguer, zoomer et situer les candidats, ouvrez `interactive_map.html`.

## Micro-Doppler SAR expérimental

Démo synthétique :

```powershell
python app.py microdoppler --demo --out outputs\microdoppler_demo
```

Analyse d'une série cohérente préparée :

```powershell
python app.py microdoppler --input prepared_target.npz --out outputs\target01
```

Le fichier NPZ doit contenir `time_s`, `samples`, `wavelength_m` et éventuellement `reference`. Le module n'extrait pas de vibrations depuis une image Sentinel-1 standard et ne valide pas une cavité.

## Catalogue SAR public

La recherche utilise l'endpoint STAC Copernicus Data Space et nécessite Internet.

```powershell
python app.py catalog --bbox -0.25 43.0 -0.05 43.15 --start 2025-01-01 --end 2025-02-01 --out outputs\barzun_sar.json
```

Les coordonnées de `catalog --bbox` sont en WGS84 longitude/latitude. Les résultats sont des métadonnées de catalogue, pas des images téléchargées.

## Déploiement Docker

Construire l'image :

```bash
docker build -t lidar-cave-scan .
```

Lancer une analyse en montant un dossier de données :

```bash
docker run --rm -v "$PWD/data:/data" -v "$PWD/outputs:/app/outputs" lidar-cave-scan lidar --dem /data/mnt.tif --out /app/outputs/run01
```

Démo micro-Doppler :

```bash
docker run --rm -v "$PWD/outputs:/app/outputs" lidar-cave-scan microdoppler --demo --out /app/outputs/microdoppler_demo
```

## Tests

```powershell
python -m unittest discover -s tests
```

## Limites et sécurité

Le score `terrain_score` est un score heuristique de tri. Les carrières, terrassements, mares, erreurs de MNT, artefacts de bordure et bassins tronqués peuvent produire de faux positifs. Toute interprétation doit être contrôlée dans QGIS avec orthophotos, géologie, inventaires publics et expertise locale.

Ne pénétrez jamais dans une cavité non reconnue ou non autorisée. Les risques incluent effondrement, chute, atmosphère dangereuse et restrictions de protection de sites ou de propriétés privées.
