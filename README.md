# Herramientas para la monitorización y análisis de procesos de modelado 3D en Blender

Suite de *add-ons* para Blender orientada al registro, análisis y visualización de procesos de modelado 3D.

El proyecto se divide en dos componentes principales:

1. **Data Logger 3D**: *add-on* encargado de registrar eventos técnicos de una sesión de modelado 3D en Blender.
2. **Analysis 3D**: *add-on* encargado de procesar los archivos CSV generados, calcular métricas y visualizar los resultados de la sesión registrada.

## Estructura del repositorio

```text
GitHub/
├── Analysis_3D/                  # Código fuente y archivos del add-on Analysis 3D
├── Data_Loggers/                 # Versiones normal y Debug de Data Logger 3D
│   ├── Data_Logger_3D.py
│   └── Data_Logger_3D_Debug.py
├── core/                         # Lógica desacoplada y agnóstica a Blender
├── datos_analisis/               # Archivos y datos utilizados para los análisis
├── docs/                         # Memoria, manuales y documentación técnica
├── scripts/                      # Scripts e instaladores para el entorno de Blender
├── tests/                        # Pruebas automatizadas desarrolladas con pytest
├── .gitignore                    # Archivos y carpetas excluidos del repositorio
├── Analysis_3D.zip               # ZIP instalable del add-on Analysis 3D
├── CONTRIBUTING.md               # Normas y recomendaciones para colaborar
├── LICENSE                       # Licencia del proyecto
├── README.md                     # Descripción e instrucciones generales
├── pytest.ini                    # Configuración de pytest
├── requirements-test.txt         # Dependencias necesarias para ejecutar los tests
├── requirements.txt              # Dependencias generales de Analysis 3D
└── run_tests_windows.bat         # Ejecución automática de los tests en Windows
```

## Licencia

Este software se distribuye bajo la licencia **GNU General Public License v3.0 or later** (`GPL-3.0-or-later`).

Consulta el archivo [`LICENSE`](LICENSE) incluido en el repositorio.

## Compatibilidad

- **Blender**: 4.0 o superior.
- **Python de Blender**: versión incluida con Blender 4.x.
- **Sistemas operativos**: Windows, Linux y macOS.
- **Analysis 3D**: versión actual 1.0.5.

La compatibilidad completa debe comprobarse en la versión concreta de Blender utilizada, especialmente después de actualizar Blender, NumPy o Matplotlib.

## Instalación

### Ejecución automática de scripts

Para que **Data Logger 3D** pueda reanudar automáticamente el registro al abrir un archivo `.blend` previamente guardado, debe estar activada la ejecución automática de scripts de Python:

1. Abre Blender.
2. Ve a `Edit > Preferences > File Paths`.
3. Activa `Auto Run Python Scripts`.
4. Guarda las preferencias si Blender lo solicita.

Esta opción no es necesaria para instalar el *add-on*, pero sí para permitir su ejecución automática al abrir archivos `.blend`.

### Data Logger 3D

1. Abre Blender.
2. Ve a `Edit > Preferences > Add-ons`.
3. Pulsa `Install...`.
   - En algunas versiones de Blender, esta opción aparece dentro del menú situado en la esquina superior derecha del panel.
4. Selecciona uno de los siguientes archivos:
   - `Data_Loggers/Data_Logger_3D.py` para uso normal.
   - `Data_Loggers/Data_Logger_3D_Debug.py` para diagnóstico.
5. Activa el *add-on* **Data Logger 3D**.
6. En la Vista 3D, pulsa `N` para abrir la barra lateral.
7. Accede a la pestaña **Data Logger**.

No deben activarse simultáneamente las versiones normal y Debug, ya que ambas registran clases y operadores con identificadores compartidos.

### Analysis 3D

1. Abre Blender.
2. Ve a `Edit > Preferences`.
3. Abre la sección `Add-ons` o `Get Extensions`, según la versión de Blender.
4. Selecciona `Install...` o `Install from Disk`.
5. Elige el archivo `Analysis_3D.zip`.
6. Activa el *add-on* **Analysis 3D**.

Debe seleccionarse directamente el ZIP instalable del *add-on*. No debe seleccionarse:

- La carpeta `Analysis_3D/`.
- Un ZIP general que contenga otros archivos ZIP.
- Una carpeta de entrega completa.

El paquete instalable de Analysis 3D 1.0.5 debe contener `blender_manifest.toml` en la raíz del ZIP. Si Blender muestra el error `Missing manifest`, se ha seleccionado un paquete incorrecto o el manifiesto no está situado en la raíz.

## Dependencias de Analysis 3D

Las librerías externas no se incluyen dentro del *add-on* ni se versionan en el repositorio.

Analysis 3D necesita:

- NumPy.
- Matplotlib.

Estas dependencias deben instalarse utilizando el Python interno de Blender.

### Instalación desde los scripts del repositorio

Desde la raíz del proyecto:

#### Windows

```powershell
.\scripts\install_environment.bat "C:\Ruta\A\blender.exe"
```

#### Linux o macOS

```bash
./scripts/install_environment.sh /ruta/al/ejecutable/blender
```

El instalador:

- Utiliza `requirements.txt`.
- Ejecuta `pip` con el Python interno de Blender.
- Instala las dependencias necesarias.
- Verifica que Blender puede importar NumPy y Matplotlib.

Después de la instalación, reinicia Blender.

No debe copiarse manualmente una carpeta `site-packages` dentro de `Analysis_3D`, ya que puede aumentar innecesariamente el tamaño del repositorio y provocar incompatibilidades con la versión de Python incluida en Blender.

Para más información, consulta:

- [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Uso básico

### Data Logger 3D

Desde el panel **Data Logger** se puede:

- Iniciar o detener el registro de la sesión.
- Exportar el registro completo a CSV.
- Exportar una copia anónima sin `UserID`.
- Regenerar el identificador seudónimo del usuario.
- Borrar el consentimiento almacenado.
- Eliminar los datos incrustados en el archivo `.blend`.

El *add-on* guarda los datos dentro del propio archivo `.blend` mediante bloques de texto internos. Por tanto, el registro puede conservarse aunque no se exporte inmediatamente a un archivo CSV externo.

El inicio de la captura requiere consentimiento. Cuando se abre un archivo `.blend` guardado, el *add-on* comprueba el estado del consentimiento antes de iniciar automáticamente el registro.

### Indicador de grabación

Mientras Data Logger 3D está registrando una sesión, Blender muestra un indicador `REC` en la barra superior.

Este indicador permite comprobar visualmente si el registro está activo.

### Extracción manual del CSV incrustado

Los datos pueden recuperarse manualmente desde Blender:

1. Abre el archivo `.blend` que contiene la sesión.
2. Cambia un área de Blender al `Text Editor`.
3. Busca el bloque `data_log_internal.csv`.
4. Ábrelo.
5. Selecciona `Text > Save As...`.
6. Guarda el contenido como archivo `.csv`.

También puede aparecer el bloque:

```text
data_logger_warnings.txt
```

Este bloque contiene advertencias recuperables generadas durante la captura.

Otros bloques internos utilizados son:

```text
data_logger_user_id
consent_flag
```

### Analysis 3D

1. Abre el panel de **Analysis 3D**.
2. Selecciona un archivo CSV generado por Data Logger 3D.
3. Carga el archivo.
4. Ejecuta el cálculo de métricas.
5. Revisa las tablas y los resultados.
6. Genera las visualizaciones disponibles.

Analysis 3D admite archivos CSV de los esquemas v1 y v2.

## Funcionalidades principales de Analysis 3D

Analysis 3D incluye, entre otras, las siguientes funciones:

- Lectura y normalización de registros CSV.
- Compatibilidad con los esquemas CSV v1 y v2.
- Cálculo de métricas temporales y de velocidad.
- Cálculo de métricas asociadas a estrategias de modelado.
- Visualización independiente de los gráficos G1, G2 y G3.
- Normalización mediante puntuaciones Z en el gráfico G2.
- Ajuste de márgenes y presentación del gráfico G3.
- Comparación de geometrías mediante una estructura Octree.
- Cálculo y análisis de normales invertidas.
- Filtrado y tratamiento de valores no válidos o extremos.
- Visualización de resultados en tablas y ventanas independientes.

## Variante Debug de Data Logger 3D

`Data_Loggers/Data_Logger_3D_Debug.py` incluye herramientas adicionales de diagnóstico, como:

- Último operador detectado.
- Motivo del último registro.
- Estado del seguimiento UV.
- Advertencias recuperables.
- Información sobre eventos y cambios detectados.
- Consulta del bloque `data_logger_warnings.txt`.

Esta variante está destinada a pruebas y diagnóstico. Para uso normal debe instalarse `Data_Logger_3D.py`.

## Formato CSV

El proyecto soporta dos esquemas.

### Esquema v1

Formato heredado que utiliza la columna:

```text
USER_ID
```

### Esquema v2

Formato actual que incorpora:

```text
SchemaVersion
LoggerVersion
SessionID
UserID
```

Analysis 3D normaliza automáticamente los archivos v1 antes de realizar los cálculos.

Las especificaciones completas se encuentran en:

[`docs/CSV_SCHEMA.md`](docs/CSV_SCHEMA.md)

## Datos CSV de ejemplo

El repositorio incluye CSV de ejemplo anonimizados para comprobar el funcionamiento de las herramientas sin utilizar datos identificables de participantes.

Estos archivos deben revisarse para evitar la inclusión de:

- Nombres propios.
- Rutas locales.
- Identificadores personales.
- Nombres de usuario del sistema.
- Información que permita relacionar una sesión con una persona concreta.

## Privacidad

Data Logger 3D utiliza un `UserID` seudónimo generado mediante UUID.

El sistema no está diseñado para registrar nombres personales ni rutas locales como parte del esquema CSV.

El proyecto proporciona herramientas para:

- Regenerar el identificador.
- Borrar el consentimiento.
- Eliminar los datos incrustados.
- Exportar una copia anónima sin `UserID`.

El consentimiento se almacena dentro del archivo `.blend`. Los datos de una escena no se eliminan automáticamente al desinstalar el *add-on*.

## Pruebas automatizadas

El proyecto utiliza `pytest` para validar:

- La lógica desacoplada de `core/`.
- La detección de operadores.
- El esquema CSV.
- La migración de CSV v1 a v2.
- La privacidad y gestión de identificadores.
- La escritura y deduplicación de registros.
- Las métricas de Analysis 3D.
- Parte de la lógica geométrica fuera de Blender.

### Instalación de dependencias de prueba

Desde la raíz del repositorio:

```bash
python -m pip install -r requirements-test.txt
```

### Ejecución

#### Cualquier sistema

```bash
python -m pytest -v
```

#### Windows

También puede ejecutarse:

```powershell
.\run_tests_windows.bat
```

La configuración se encuentra en:

```text
pytest.ini
```

Los tests utilizan utilidades propias para localizar los módulos del proyecto y simulaciones mínimas de componentes de Blender cuando es necesario. No requieren configurar manualmente `PYTHONPATH`.

La ejecución correcta debe finalizar sin errores ni fallos:

```text
passed
```

El número total de pruebas puede variar cuando se añadan nuevos casos.

## Entorno de validación

Las pruebas automatizadas se ejecutan fuera de Blender mediante `pytest`.

La funcionalidad relacionada con la interfaz, los paneles, los operadores, los temporizadores, los *handlers* y el ciclo de vida de los *add-ons* debe comprobarse además dentro de Blender.

| Componente | Estado | Observaciones |
|---|---|---|
| Python externo | Validado con Python 3.11.9 | Entorno utilizado para ejecutar pytest fuera de Blender. |
| Pytest | Validado con pytest 9.0.2 | Configurado mediante `pytest.ini`. |
| Pruebas automatizadas | Validado | Se ejecutan desde la raíz mediante `python -m pytest -v`. |
| Blender 4.x | Requiere validación manual | Deben comprobarse paneles, operadores, temporizadores y registro de clases. |
| Python interno de Blender | Requiere comprobación local | Puede consultarse desde Blender o mediante ejecución en segundo plano. |
| NumPy y Matplotlib en Blender | Requiere comprobación local | Deben verificarse utilizando el Python interno de Blender. |

Para consultar la versión del Python interno de Blender:

```powershell
blender --background --python-expr "import sys; print(sys.version)"
```

Para comprobar NumPy y Matplotlib:

```powershell
blender --background --python-expr "import numpy, matplotlib; print(numpy.__version__); print(matplotlib.__version__)"
```

Si `blender` no está incluido en la variable `PATH`, debe utilizarse la ruta completa al ejecutable.

## Construcción del ZIP de Analysis 3D

El archivo `Analysis_3D.zip` debe construirse a partir del paquete de Analysis 3D, manteniendo en la raíz del ZIP los archivos principales de la extensión.

La estructura interna esperada es similar a:

```text
Analysis_3D.zip
├── blender_manifest.toml
├── __init__.py
├── analytics.py
├── constants.py
├── csv_schema.py
├── dependencies.py
├── dependency_ui.py
├── graphs.py
├── texts.py
├── ui.py
├── ui_graph_rendering.py
├── ui_graph_service.py
├── ui_helpers.py
├── ui_operators.py
├── ui_panels.py
├── ui_properties.py
├── ui_table_service.py
└── utils.py
```

No debe incluir:

- Blender.
- Una instalación completa de Python.
- Carpetas `site-packages`.
- Archivos `.pyc`.
- Carpetas `__pycache__`.
- Entornos virtuales.
- Datos personales.
- Otros paquetes ZIP innecesarios.

## Desinstalación

### Data Logger 3D

1. Abre Blender.
2. Ve a `Edit > Preferences > Add-ons`.
3. Busca **Data Logger 3D**.
4. Desactiva el *add-on*.
5. Pulsa `Remove` si deseas eliminarlo.

Los datos ya incrustados en archivos `.blend` no se eliminan automáticamente.

Para borrarlos manualmente, elimina desde el `Text Editor` los bloques:

```text
data_log_internal.csv
data_logger_user_id
consent_flag
data_logger_warnings.txt
```

También pueden eliminarse desde las opciones de privacidad del panel de Data Logger 3D.

### Analysis 3D

1. Abre Blender.
2. Ve a `Edit > Preferences`.
3. Abre `Add-ons` o `Get Extensions`.
4. Busca **Analysis 3D**.
5. Desactiva o desinstala la extensión.

La desinstalación del *add-on* no elimina los archivos CSV guardados por el usuario.

## Desarrollo y colaboración

Antes de enviar cambios:

1. Instala las dependencias de prueba.
2. Ejecuta:

```bash
python -m pytest -v
```

3. Comprueba manualmente los *add-ons* dentro de Blender.
4. Verifica que `Analysis_3D.zip` puede instalarse directamente.
5. Comprueba que el ZIP contiene `blender_manifest.toml` en la raíz.
6. Evita incluir cachés, dependencias binarias o datos personales.

Las normas completas de colaboración están disponibles en:

[`CONTRIBUTING.md`](CONTRIBUTING.md)

## Paquetes instalables

Los principales archivos de instalación son:

- `Analysis_3D.zip`: paquete instalable de Analysis 3D.
- `Data_Loggers/Data_Logger_3D.py`: versión normal de Data Logger 3D.
- `Data_Loggers/Data_Logger_3D_Debug.py`: versión de diagnóstico.

La carpeta `Analysis_3D/` contiene el código fuente utilizado para desarrollo, pruebas y construcción del ZIP.
