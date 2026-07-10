@echo off
setlocal

if "%~1"=="" (
    echo Uso: install_environment.bat "C:\Ruta\A\blender.exe"
    echo Ejemplo: install_environment.bat "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe"
    exit /b 2
)

set "BLENDER=%~1"
if not exist "%BLENDER%" (
    echo No se encontro Blender en: %BLENDER%
    exit /b 2
)

"%BLENDER%" --background --python "%~dp0install_environment.py"
if errorlevel 1 exit /b %errorlevel%

echo Dependencias instaladas. Reinicia Blender antes de activar Analysis 3D.
