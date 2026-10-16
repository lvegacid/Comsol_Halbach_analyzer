@echo off
setlocal

if "%~1"=="" goto :usage
if "%~2"=="" goto :usage
if "%~3"=="" goto :usage

set "RAW_FILE=%~f1"
set "RAW_COLUMN=%~2"
set "HIST_BINS=%~3"
set "MAGNET_INFO=%~4"
set "FOV_INFO=%~5"
set "ANALYSIS_INFO=%~6"

if not exist "%RAW_FILE%" (
    echo ERROR: No existe el archivo: "%RAW_FILE%"
    exit /b 1
)

if "%MAGNET_INFO%"=="" set "MAGNET_INFO=%~n1"
if "%FOV_INFO%"=="" set "FOV_INFO=Raw TXT"
if "%ANALYSIS_INFO%"=="" set "ANALYSIS_INFO=Column %RAW_COLUMN% histogram (%HIST_BINS% bins)"

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%SCRIPT_DIR%..\Assembly_force_extractor\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%SCRIPT_DIR%..\Vertical_insertion_force_extractor\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo ERROR: No encontre un Python reutilizable con dependencias en:
    echo   "%SCRIPT_DIR%..\Assembly_force_extractor\.venv\Scripts\python.exe"
    echo   "%SCRIPT_DIR%..\Vertical_insertion_force_extractor\.venv\Scripts\python.exe"
    exit /b 1
)

pushd "%SCRIPT_DIR%"
"%PYTHON_EXE%" "%SCRIPT_DIR%Comsol_extracted_histograms_BFOV_Magnets.py" ^
  --raw-bfov-file "%RAW_FILE%" ^
  --raw-b-column %RAW_COLUMN% ^
  --hist-bins %HIST_BINS% ^
  --magnet-info "%MAGNET_INFO%" ^
  --fov-info "%FOV_INFO%" ^
  --analysis "%ANALYSIS_INFO%" ^
  --bfov-only ^
  --no-show
set "EXIT_CODE=%ERRORLEVEL%"
popd

if not "%EXIT_CODE%"=="0" (
    echo ERROR: El postproceso fallo con codigo %EXIT_CODE%.
    exit /b %EXIT_CODE%
)

echo OK: Histograma BFOV generado para "%RAW_FILE%"
echo Salidas esperadas en la misma carpeta del TXT:
echo   BFOV_histogram_%~n1.txt
echo   BFOV_histogram_%~n1_normalized.txt
echo   BFOV_histogram_%~n1_BFOV.png
exit /b 0

:usage
echo Uso:
echo   %~nx0 "ruta\archivo.txt" columna bins [magnet_info] [fov_info] [analysis]
echo.
echo Ejemplo:
echo   %~nx0 "Z:\Projects\PhysioII - NextMRI\Magnet\Comsol\Original\Nonlinear_nosymmetry\B_coordinates_Spherical_coord_ntheta_30_nphi_30_R100mm.txt" 5 100
exit /b 1