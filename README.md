# Herramientas para la monitorización y análisis de procesos de modelado 3D en Blender

Suite de add-ons para Blender orientada al registro (logging), análisis y visualización de procesos de modelado 3D.

El proyecto se divide en dos componentes principales:

1. **Data Logger 3D**: add-on encargado de registrar eventos técnicos de una sesión de modelado 3D en Blender.
2. **Analysis 3D**: add-on encargado de procesar los archivos CSV generados y calcular métricas sobre la sesión registrada.

## Estructura del repositorio

```text
GitHub/
├── Data_Logger_3D.py        # Add-on de captura de eventos
├── Analysis_3D/             # Add-on de análisis y visualización
├── core/                    # Lógica desacoplada (agnóstica a Blender)
├── tests/                   # Pruebas automatizadas (unittest)
├── docs/                    # Memoria, manuales y documentación técnica
├── historial_desarrollo/    # Versiones antiguas
├── requirements.txt         # Dependencias para Analysis 3D
├── README.md
└── LICENSE

```

## Licencia

Este software se distribuye bajo la licencia **GNU General Public License v3.0 or later** (`GPL-3.0-or-later`). Consulta el archivo `LICENSE` incluido en el repositorio.

## Instalación

### Data Logger 3D

1. Abre Blender.
2. Ve a `Edit > Preferences > Add-ons`.
3. Pulsa `Install...` y selecciona el archivo `Data_Logger_3D.py`.
4. Activa el add-on **Data Logger 3D**.
5. En la Vista 3D, presiona `N` para abrir la barra lateral y accede a la pestaña **Data Logger**.

### Analysis 3D

1. Sigue los pasos 1 a 3 anteriores seleccionando la carpeta o el ZIP de `Analysis_3D`.
2. Activa el add-on **Analysis 3D**.
3. *Nota:* `Analysis 3D` requiere `numpy` y `matplotlib`. Si el Python interno de Blender no dispone de estas librerías, instálalas en el entorno de Python de Blender.

## Uso básico

### Data Logger 3D

Desde el panel **Data Logger** puedes:

* **Start/Stop Logger**: Gestiona el inicio y fin de la sesión.
* **Exportar a CSV**: Guarda el registro en un archivo externo.
* **Privacidad**: Exportar sin `UserID`, regenerar identificadores o borrar datos incrustados en el `.blend`.

### Analysis 3D

1. Selecciona un archivo CSV generado por **Data Logger 3D**.
2. Carga el archivo y ejecuta el cálculo de métricas para visualizar los resultados.

### Debug

El panel **Data Logger Debug** ofrece telemetría en tiempo real: último operador, estado de UV, advertencias y logs almacenados en el Text Block `data_logger_warnings.txt`.

## Formato CSV

El proyecto soporta dos esquemas:

* **v1**: Formato heredado (incluye `USER_ID`).
* **v2**: Formato actual (incluye `SchemaVersion`, `LoggerVersion`, `SessionID` y `UserID`).

`Analysis 3D` normaliza automáticamente los archivos v1. Especificaciones completas en [`docs/CSV_SCHEMA.md`](docs/CSV_SCHEMA.md).

## Datos CSV de ejemplo

La entrega limpia no incluye CSV reales de participantes para evitar riesgos de identificación indirecta. Para la defensa se recomienda generar un CSV nuevo durante la demostración o incluir únicamente una versión revisada y anonimizada.

Si se añade un CSV de ejemplo, debe comprobarse que no contiene nombres propios, rutas locales, identificadores personales ni valores que permitan vincular directa o indirectamente el registro con una persona concreta.


## Vídeo demostrativo

La entrega incluye un vídeo demostrativo del funcionamiento completo del sistema. En el vídeo se muestra el flujo principal de uso: activación de los add-ons en Blender, inicio de una sesión de captura, realización de operaciones de modelado, exportación del CSV, carga del archivo en `Analysis 3D`, cálculo de métricas y generación de visualizaciones.

Este vídeo se considera una evidencia complementaria de validación funcional y no sustituye a las pruebas automatizadas ni a la validación manual indicada en `docs/VALIDACION_BLENDER.md`.

## Pruebas automatizadas

El proyecto utiliza `unittest` para validar la lógica desacoplada (`core/` y lógica de análisis).

**Ejecución (Raíz del proyecto):**

* **Linux/macOS:** `PYTHONPATH=. python3 -m unittest discover -s tests -v`
* **Windows (PowerShell):** `$env:PYTHONPATH="."; python -m unittest discover -s tests -v`

> **Nota:** Las pruebas automatizadas no sustituyen la validación funcional dentro de Blender (UI, contextos, operadores). Para la ejecución de los mismos Analysis_3D debe ser extraido en la raiz del proyecto.

## Dependencias y Entorno

`Analysis 3D` requiere `numpy` y `matplotlib`. Para instalar librerías en el Python interno de Blender:

```bash
# Localizar el ejecutable de Python de Blender
blender --background --python-expr "import sys; print(sys.executable)"

# Instalar dependencias (usando la ruta obtenida arriba)
/ruta/al/python/de/blender -m pip install -r requirements.txt

```

## Entorno de validación

Las pruebas automatizadas del proyecto se ejecutan fuera de Blender mediante `unittest`. La funcionalidad integrada con la interfaz, los operadores y el ciclo de vida de los add-ons debe validarse además dentro de Blender.

Las pruebas automatizadas de esta entrega limpia se han verificado fuera de Blender con el siguiente entorno:

| Componente | Versión probada | Observaciones |
|---|---|---|
| Python externo | 3.13.5 | Usado para ejecutar `unittest` fuera de Blender. |
| NumPy externo | 2.3.5 | Disponible en el entorno de pruebas externo. |
| Matplotlib externo | 3.10.8 | Disponible en el entorno de pruebas externo. |
| Pruebas automatizadas | 51 OK, 3 omitidas | Las 3 omitidas dependen de `mathutils`/Blender. |
| Blender | No validado en este entorno | Debe completarse en el equipo real de defensa. |
| Python de Blender | No validado en este entorno | Obtener con `blender --background --python-expr "import sys; print(sys.version)"`. |
| NumPy en Blender | No validado en este entorno | Obtener desde el Python de Blender con `import numpy; print(numpy.__version__)`. |
| Matplotlib en Blender | No validado en este entorno | Obtener desde el Python de Blender con `import matplotlib; print(matplotlib.__version__)`. |
| Sistema operativo de validación manual | No validado en este entorno | Indicar sistema y versión usados en las pruebas manuales. |

## Validación funcional en Blender

La siguiente tabla debe utilizarse como registro de validación manual. No debe darse por superada una fila si no se ha comprobado en Blender con el entorno indicado en la sección anterior.

| Prueba manual | Resultado | Evidencia recomendada |
|---|---|---|
| Instalación de `Data_Logger_3D.py` desde `Edit > Preferences > Add-ons > Install...` | No validado en este entorno | Captura del add-on instalado o anotación de versión de Blender. |
| Activación de `Data Logger 3D` sin errores en consola | No validado en este entorno | Captura del panel lateral o salida de consola sin errores. |
| Inicio y parada del logger desde el panel | No validado en este entorno | Captura del estado activo/detenido. |
| Exportación de CSV con cabecera v2 | No validado en este entorno | CSV generado y comprobación de cabecera según `docs/CSV_SCHEMA.md`. |
| Exportación anónima sin `UserID` | No validado en este entorno | CSV exportado verificando la eliminación del identificador. |
| Instalación y activación de `Analysis_3D` | No validado en este entorno | Captura del add-on activo. |
| Carga de CSV generado por el logger | No validado en este entorno | Captura del panel de análisis tras cargar el CSV. |
| Cálculo de métricas sobre el CSV | No validado en este entorno | Captura o registro de métricas calculadas. |
| Generación de visualizaciones/gráficos | No validado en este entorno | Captura de gráfico o visualización 3D. |
| Recarga de Blender con el add-on activado | No validado en este entorno | Verificar que no se duplican handlers, keymaps ni errores de registro. |


## Compatibilidad

* **Blender**: 4.0 o superior.
* **SO**: Windows, Linux y macOS.

## Privacidad

El `UserID` es un identificador seudónimo generado mediante UUID. No se almacenan datos personales (nombres de usuario o rutas locales). El proyecto proporciona herramientas específicas para la eliminación de datos y la gestión del consentimiento dentro del archivo `.blend`.



## Estructura de entrega final

La entrega conserva una estructura doble para facilitar tanto la evaluación automática como la instalación manual en Blender:

```text
ActualV4/
├── Data_Logger_3D.py                 # Copia en raíz para pruebas automáticas
├── Analysis_3D/                      # Paquete extraído para pruebas automáticas
├── historial_desarrollo/             # Versiones antiguas
│   ├── addon_deteccion_datos/
│   │   ├── Deteccion_Datos.py
│   │   ├── Deteccion_DatosV2.py
│   │   ├── Deteccion_DatosV3.py
│   │   ├── DeteccionDatosV4.py
│   │   ├── DeteccionDatosV5.py
│   │   └── DeteccionDatosV6.py
│   ├── addon_analisis_datos/
│   │   ├── analisisV1
│   │   ├── analisisV2
│   │   ├── analisisV3.zip
│   │   ├── analisisV4.zip
│   │   ├── analisisV5.zip
│   │   ├── analisisV6.zip
│   │   └── analisisV7.zip
├── core/
├── tests/
├── docs/
├── datos_analisis/
├── requirements.txt
├── README.md
├── LICENSE
└── TEST_RESULTS.txt
```

Para ejecutar las pruebas desde Windows PowerShell:

```powershell
$env:PYTHONPATH="."; python -m unittest discover -s tests -v
```

En Linux/macOS:

```bash
PYTHONPATH=. python -m unittest discover -s tests -v
```

Resultado esperado fuera de Blender:

```text
Ran 51 tests
OK (skipped=3)
```

Las pruebas omitidas dependen de `mathutils`, disponible en el entorno Python de Blender.

## Vídeo demostrativo

La entrega incluye un vídeo demostrativo del flujo completo de uso del proyecto: instalación/activación de los add-ons, registro de una sesión, exportación CSV, carga en Analysis 3D, cálculo de métricas y generación de gráficos.

