@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Lancez d'abord install_windows.bat
  pause
  exit /b 1
)
".venv\Scripts\python.exe" examples\create_demo_dem.py --out examples\demo_dem.tif
if errorlevel 1 goto error
".venv\Scripts\python.exe" app.py lidar --dem examples\demo_dem.tif --out outputs\demo_lidar --min-depth 0.5 --min-area 10 --max-area 10000
if errorlevel 1 goto error
start "" "%~dp0outputs\demo_lidar"
echo.
echo Demo terminee. Le dossier outputs\demo_lidar contient report.html, map.png, candidates.csv, candidates.geojson, candidates.gpkg et les rasters.
pause
exit /b 0

:error
echo.
echo Demo echouee. Consultez le message d'erreur ci-dessus.
pause
exit /b 1
