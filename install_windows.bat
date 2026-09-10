@echo off
cd /d "%~dp0"
PowerShell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_windows.ps1"
if errorlevel 1 goto error
echo.
echo Installation terminee. Lancez run_desktop.bat
pause
exit /b 0

:error
echo.
echo Installation echouee. Si rasterio/geopandas posent probleme, utilisez conda-forge comme indique dans README.md
pause
exit /b 1
