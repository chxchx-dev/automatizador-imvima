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

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\SIGAVI.exe' -DestinationPath 'dist\SIGAVI-portable.zip' -Force"
if errorlevel 1 exit /b 1

if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /Qp SIGAVI.iss
  if errorlevel 1 exit /b 1
  echo Instalador creado en: dist\SIGAVI-Setup.exe
) else (
  echo Para crear SIGAVI-Setup.exe localmente instala Inno Setup 6.
  echo GitHub Actions crea el instalador automaticamente al subir cambios a main.
)

echo.
echo Ejecutable portable creado en: dist\SIGAVI.exe
echo Paquete para compartir creado en: dist\SIGAVI-portable.zip
pause
