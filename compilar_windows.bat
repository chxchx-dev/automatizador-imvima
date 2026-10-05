@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "TEMPLATE=2026 - Propuesta Formato de Control y Seguimiento de Alertas Sanitarias SIGAVI.xlsx"

if not exist "%TEMPLATE%" (
  echo No se encontro la plantilla XLSX junto al codigo:
  echo %TEMPLATE%
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv 2>nul
  if errorlevel 1 python -m venv .venv
  if errorlevel 1 exit /b 1
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1

python -m PyInstaller --noconfirm --clean --onefile --windowed --name SIGAVI --add-data "%TEMPLATE%;." app.py
if errorlevel 1 exit /b 1

echo.
echo Ejecutable creado en: dist\SIGAVI.exe
pause
