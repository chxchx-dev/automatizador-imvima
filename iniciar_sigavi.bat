@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"

if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno de desarrollo de SIGAVI...
  py -3 -m venv .venv 2>nul
  if errorlevel 1 python -m venv .venv
  if errorlevel 1 goto :error
  call ".venv\Scripts\activate.bat"
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"
python -c "import requests, bs4, pypdf, openpyxl" >nul 2>nul
if errorlevel 1 (
  python -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)
python app.py
if errorlevel 1 goto :error
goto :eof

:error
echo.
echo SIGAVI no pudo iniciar. Revisa Python 3.11 o superior y la conexion a Internet para la primera instalacion.
pause
exit /b 1
