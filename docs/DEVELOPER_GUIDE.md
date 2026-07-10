# Manual del desarrollador

## 1. Objetivo y componentes

El repositorio contiene dos add-ons de Blender:

- `Data_Loggers/Data_Logger_3D.py`: variante normal que captura eventos técnicos y guarda un CSV dentro del archivo `.blend`.
- `Data_Loggers/Data_Logger_3D_Debug.py`: variante de diagnóstico con panel y variables de depuración adicionales. No debe activarse a la vez que la variante normal.
- `Analysis_3D/`: carga los CSV, calcula métricas y genera visualizaciones.

La lógica que puede probarse sin Blender se encuentra en `core/` y en los módulos de análisis que no dependen directamente de `bpy`.

## 2. Requisitos

- Git.
- Blender 4.0 o posterior.
- Python externo opcional para ejecutar las pruebas desacopladas.
- Conexión a Internet durante la instalación inicial de NumPy y Matplotlib.

Las librerías externas no se guardan en el repositorio ni dentro de `Analysis_3D.zip`. Deben instalarse en el Python incluido con Blender mediante los scripts del directorio `scripts/`.

## 3. Preparar el repositorio

```bash
git clone https://github.com/crimsonCh4os/Add_On_Blender_2026.git
cd Add_On_Blender_2026
```

No crees entornos virtuales dentro de `Analysis_3D/` y no copies una carpeta `site-packages` al add-on.

## 4. Instalar el entorno de Blender

### Windows

Ejecuta desde la raíz del repositorio:

```powershell
.\scripts\install_environment.bat "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe"
```

Cambia la ruta por la instalación real de Blender.

### Linux

```bash
./scripts/install_environment.sh /usr/bin/blender
```

### macOS

```bash
./scripts/install_environment.sh /Applications/Blender.app/Contents/MacOS/Blender
```

El instalador abre Blender en modo background, localiza su Python interno y ejecuta:

```text
python -m ensurepip --upgrade
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Después de instalar, cierra y vuelve a abrir Blender.

### Instalación manual

Para localizar el prefijo del Python de Blender:

```bash
blender --background --python-expr "import sys; print(sys.prefix); print(sys.version)"
```

Dentro de ese prefijo, el intérprete suele estar en `bin/python`, `bin/python3` o `bin/python.exe`. Con esa ruta:

```bash
<RUTA_PYTHON_BLENDER> -m ensurepip --upgrade
<RUTA_PYTHON_BLENDER> -m pip install -r requirements.txt
```

## 5. Instalar los add-ons

### Data Logger 3D

En Blender, abre `Edit > Preferences > Add-ons > Install...`, selecciona `Data_Loggers/Data_Logger_3D.py` o, para diagnóstico, `Data_Loggers/Data_Logger_3D_Debug.py` y activa **Data Logger 3D**.

### Analysis 3D

Primero instala las dependencias. Después selecciona `Analysis_3D.zip` desde el mismo diálogo y activa **Analysis 3D**.

Si faltan NumPy o Matplotlib, Blender impedirá activar el add-on y mostrará el comando de instalación recomendado.

## 6. Estructura del código

```text
Analysis_3D/
├── __init__.py              # Registro del add-on y comprobación de dependencias
├── dependencies.py          # Detección de NumPy y Matplotlib
├── analytics.py             # Cálculo de métricas a partir de CSV
├── csv_schema.py            # Compatibilidad y normalización de esquemas CSV
├── graphs.py                # Gráficos y registro de funcionalidad gráfica
├── operator.py              # Operadores de Blender
├── ui.py                    # Registro principal de la interfaz
├── ui_graph_rendering.py    # Renderizado de gráficos en Blender
├── ui_graph_service.py      # Coordinación de datos y gráficos
├── ui_helpers.py            # Utilidades de interfaz
├── ui_operators.py          # Operadores expuestos desde la UI
├── ui_panels.py             # Paneles de la barra lateral
├── ui_properties.py         # Propiedades de escenas y controles
├── constants.py             # Constantes compartidas
└── utils.py                 # Funciones geométricas y auxiliares

core/
└── data_logger_core.py      # Lógica del logger que puede probarse fuera de Blender

tests/
├── test_core.py
└── test_csv_schema.py

scripts/
├── install_environment.py
├── install_environment.bat
└── install_environment.sh
```

## 7. Dónde hacer cada cambio

- Nueva columna o cambio del CSV: `Data_Loggers/Data_Logger_3D.py` y `Data_Loggers/Data_Logger_3D_Debug.py`, `Analysis_3D/csv_schema.py` y pruebas relacionadas.
- Nueva métrica: `Analysis_3D/analytics.py`; añade una prueba con un CSV mínimo.
- Nuevo gráfico: `Analysis_3D/graphs.py` y, cuando corresponda, `ui_graph_service.py` o `ui_graph_rendering.py`.
- Nuevo botón u operador: `ui_operators.py`; registra el control desde `ui_panels.py` o `ui.py`.
- Nueva propiedad de Blender: `ui_properties.py`; recuerda eliminarla correctamente durante `unregister()`.
- Cambio en la captura: actualiza de forma coherente `Data_Loggers/Data_Logger_3D.py` y `Data_Loggers/Data_Logger_3D_Debug.py`; mantén consentimiento, anonimización y compatibilidad de esquemas.
- Cambio de dependencias: `requirements.txt`, `Analysis_3D/dependencies.py` y esta documentación.

## 8. Pruebas

Desde la raíz del repositorio:

### Linux/macOS

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

### Windows PowerShell

```powershell
$env:PYTHONPATH="."
python -m unittest discover -s tests -v
```

Las pruebas que dependen de `bpy` o `mathutils` deben ejecutarse además dentro de Blender. Las pruebas externas no sustituyen la validación manual de paneles, operadores, registro y desregistro.

## 9. Validación manual en Blender

Antes de publicar:

1. Instala las dependencias en una instalación limpia de Blender.
2. Instala y activa ambos add-ons.
3. Guarda y reabre un `.blend` para probar el consentimiento.
4. Inicia y detén el logger.
5. Exporta CSV normal y anónimo.
6. Carga ambos esquemas CSV en Analysis 3D.
7. Calcula métricas y genera todos los gráficos.
8. Desactiva y vuelve a activar los add-ons.
9. Revisa la consola de Blender y `data_logger_warnings.txt`.

## 10. Construir el ZIP instalable

Desde la raíz del repositorio:

### Linux/macOS

```bash
rm -f Analysis_3D.zip
zip -r Analysis_3D.zip Analysis_3D \
  -x '*/__pycache__/*' '*.pyc' '*.pyo' '*/site-packages/*' 'Analysis_3D/tests/*'
```

### PowerShell

```powershell
Remove-Item Analysis_3D.zip -ErrorAction SilentlyContinue
Compress-Archive -Path Analysis_3D -DestinationPath Analysis_3D.zip
```

Antes de publicar el ZIP de PowerShell, comprueba que no contiene `__pycache__`, `.pyc`, `site-packages` ni archivos de pruebas innecesarios.

## 11. Reglas de dependencias

- No subir binarios o paquetes de terceros al repositorio.
- No instalar paquetes automáticamente al activar el add-on.
- Fijar versiones reproducibles en `requirements.txt`.
- Probar las versiones con el Python de la versión mínima de Blender soportada.
- Actualizar el manual y las pruebas cuando cambien las dependencias.
