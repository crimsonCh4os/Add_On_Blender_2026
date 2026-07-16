@echo off
setlocal
cd /d "%~dp0"
echo Proyecto: %CD%
echo.
python -m pytest -v
set "TEST_EXIT=%ERRORLEVEL%"
echo.
if not "%TEST_EXIT%"=="0" (
    echo Los tests han terminado con errores ^(codigo %TEST_EXIT%^).
) else (
    echo Todos los tests han terminado correctamente.
)
pause
exit /b %TEST_EXIT%
