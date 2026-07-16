# Herramientas para la monitorización y análisis de procesos de modelado 3D en Blender

Suite de *add-ons* para Blender orientada al registro (*logging*), análisis y visualización de procesos de modelado 3D.

El proyecto se divide en dos componentes principales:

1. **Data Logger 3D**: *add-on* encargado de registrar eventos técnicos de una sesión de modelado 3D en Blender.
2. **Analysis 3D**: *add-on* encargado de procesar los archivos CSV generados y calcular métricas sobre la sesión registrada.

## Estructura del repositorio

```text
GitHub/
├── Data_Loggers/            # Versiones normal y Debug de Data Logger 3D
│   ├── Data_Logger_3D.py
│   └── Data_Logger_3D_Debug.py
├── Analysis_3D.zip          # ZIP instalable del add-on de análisis
├── core/                    # Lógica desacoplada (agnóstica a Blender)
├── tests/                   # Pruebas automatizadas (unittest)
├── docs/                    # Memoria, manuales y documentación técnica
├── historial_desarrollo/    # Versiones antiguas
├── scripts/                 # Instaladores del entorno de Blender
├── requirements.txt         # Dependencias para Analysis 3D
├── CONTRIBUTING.md          # Normas para colaborar
├── README.md
└── LICENSE
```

## Licencia

Este software se distribuye bajo la licencia **GNU General Public License v3.0 or later** (`GPL-3.0-or-later`). Consulta el archivo `LICENSE` incluido en el repositorio.

## Compatibilidad

* **Blender**: 4.0 o superior.
* **Python de Blender**: versión incluida con Blender 4.x.
* **Sistemas operativos**: Windows, Linux y macOS.

## Instalación

Antes de instalar los *add-ons*, se recomienda activar la ejecución automática de scripts de Python en Blender:

1. Abre Blender.
2. Ve a `Edit > Preferences > File Paths`.
3. Activa la opción `Auto Run Python Scripts`.
4. Guarda las preferencias si Blender lo solicita.

Esta opción es necesaria para que Blender pueda ejecutar correctamente scripts y *add-ons* de Python al abrir archivos `.blend` o al cargar extensiones instaladas.

### Data Logger 3D

1. Abre Blender.
2. Ve a `Edit > Preferences > Add-ons`.
3. Pulsa el botón `Install...`.
   * En algunas versiones de Blender, el botón `Install...` está oculto dentro del menú de configuración de *add-ons*, situado en la esquina superior derecha del panel de *Add-ons*. Se accede mediante el icono con una flecha o menú desplegable.
4. Selecciona `Data_Loggers/Data_Logger_3D.py` para uso normal. Para diagnóstico, puedes instalar `Data_Loggers/Data_Logger_3D_Debug.py` en su lugar.
5. Activa el *add-on* **Data Logger 3D**. No actives simultáneamente las dos variantes, ya que registran las mismas clases y operadores.
6. En la Vista 3D, presiona `N` para abrir la barra lateral y accede a la pestaña **Data Logger**.

### Analysis 3D

1. Abre Blender.
2. Ve a `Edit > Preferences > Add-ons`.
3. Pulsa `Install...`.
   * Si el botón no aparece directamente, abre el menú de configuración de *add-ons* situado en la esquina superior derecha del panel.
4. Selecciona siempre el archivo ZIP instalable de `Analysis_3D`, por ejemplo `Analysis_3D.zip`.
5. Activa el *add-on* **Analysis 3D**.

No debe seleccionarse la carpeta `Analysis_3D` para instalar el *add-on*, ya que Blender solo abrirá el directorio. La instalación debe realizarse siempre a partir del archivo ZIP.

## Dependencias de entorno

Las librerías externas no se incluyen dentro del add-on ni se versionan en el repositorio. `Analysis 3D` necesita NumPy y Matplotlib instalados en el Python interno de Blender.

Antes de activar el add-on, instala el entorno desde la raíz del repositorio:

* **Windows:**

```powershell
.\scripts\install_environment.bat "C:\Ruta\A\blender.exe"
```

* **Linux/macOS:**

```bash
./scripts/install_environment.sh /ruta/al/ejecutable/blender
```

El instalador usa `requirements.txt`, instala las dependencias de forma explícita y verifica que Blender puede importarlas. Reinicia Blender después de ejecutarlo. No copies una carpeta `site-packages` dentro de `Analysis_3D`.

Consulta [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md) para instalación manual, estructura interna, pruebas y construcción del ZIP. Las normas de colaboración se encuentran en [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Uso básico

### Data Logger 3D

Desde el panel **Data Logger** puedes:

* **Start/Stop Logger**: inicia o detiene la captura de la sesión.
* **Export to CSV**: guarda el registro en un archivo CSV externo.
* **Export anonymous CSV**: exporta una copia sin `UserID`.
* **Privacy**: permite regenerar el identificador, borrar el consentimiento o eliminar datos incrustados.

El *add-on* guarda los datos dentro del propio archivo `.blend` como un bloque de texto interno. Por tanto, aunque no se exporte el CSV inmediatamente, el registro puede quedar incrustado en el archivo de Blender si la sesión se ha guardado correctamente.

### Extracción de CSV incrustados en el `.blend`

Además de usar los botones de exportación del *add-on*, los CSV pueden recuperarse manualmente desde Blender porque se almacenan como bloques de texto internos.

Para extraerlos:

1. Abre el archivo `.blend` que contiene la sesión registrada.
2. Cambia un área de Blender al editor `Text Editor`.
3. En el selector de textos, busca el bloque `data_log_internal.csv`.
4. Abre ese bloque de texto.
5. Usa `Text > Save As...` para guardarlo como archivo `.csv` externo.

También puede aparecer el bloque `data_logger_warnings.txt`, que contiene advertencias recuperables del sistema de captura.

### Analysis 3D

1. Selecciona un archivo CSV generado por **Data Logger 3D**.
2. Carga el archivo desde el panel de **Analysis 3D**.
3. Ejecuta el cálculo de métricas.
4. Revisa los resultados y, si procede, genera visualizaciones.

### Variante Debug

`Data_Loggers/Data_Logger_3D_Debug.py` incluye el panel **Data Logger Debug**, que ofrece telemetría en tiempo real: último operador detectado, razón del último registro, estado de UV, advertencias y logs almacenados en el bloque de texto `data_logger_warnings.txt`.

## Formato CSV

El proyecto soporta dos esquemas:

* **v1**: formato heredado, con `USER_ID`.
* **v2**: formato actual, con `SchemaVersion`, `LoggerVersion`, `SessionID` y `UserID`.

`Analysis 3D` normaliza automáticamente los archivos v1. Las especificaciones completas se encuentran en [`docs/CSV_SCHEMA.md`](docs/CSV_SCHEMA.md).

## Datos CSV de ejemplo

La entrega incluye CSV de ejemplo anonimizados para permitir la comprobación del funcionamiento de las herramientas sin utilizar datos identificables de participantes.

Estos ficheros se han revisado para evitar la inclusión de nombres propios, rutas locales, identificadores personales u otros valores que puedan vincular directa o indirectamente los registros con una persona concreta.

## Pruebas automatizadas

El proyecto utiliza `unittest` para validar la lógica desacoplada (`core/` y lógica de análisis).

Ejecución desde la raíz del proyecto:

* **Linux/macOS:**

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

* **Windows PowerShell:**

```powershell
$env:PYTHONPATH="."
python -m unittest discover -s tests -v
```

Resultado esperado fuera de Blender:

```text
Ran 51 tests
OK (skipped=3)
```

Las pruebas omitidas dependen de `mathutils`, disponible en el entorno Python de Blender. Para ejecutar correctamente las pruebas, `Analysis_3D` debe estar extraído en la raíz del proyecto.

## Entorno de validación

Las pruebas automatizadas del proyecto se ejecutan fuera de Blender mediante `unittest`. La funcionalidad integrada con la interfaz, los operadores, los paneles y el ciclo de vida de los *add-ons* debe comprobarse además dentro de Blender.

La siguiente tabla resume el entorno utilizado o pendiente de validación, separando las pruebas automáticas externas de la validación manual en Blender:

| Componente | Estado | Observaciones |
|---|---|---|
| Python externo | Validado con Python 3.13.5 | Usado para ejecutar `unittest` fuera de Blender. |
| NumPy externo | Validado con NumPy 2.3.5 | Disponible en el entorno de pruebas externo. |
| Matplotlib externo | Validado con Matplotlib 3.10.8 | Disponible en el entorno de pruebas externo. |
| Pruebas automatizadas | 51 OK, 3 omitidas | Las 3 omitidas dependen de `mathutils`/Blender. |
| Blender 4.x | Requiere validación manual | Debe comprobarse en el equipo donde se instalen los *add-ons*. |
| Python interno de Blender | Requiere comprobación local | Obtener con `blender --background --python-expr "import sys; print(sys.version)"`. |
| NumPy y Matplotlib en Blender | Requiere comprobación local | Verificar desde el Python interno de Blender. |

## Desinstalación

### Desinstalar Data Logger 3D

1. Abre Blender.
2. Ve a `Edit > Preferences > Add-ons`.
3. Busca **Data Logger 3D**.
4. Desactiva el *add-on*.
5. Pulsa `Remove` si quieres eliminarlo de la instalación de Blender.

Los datos incrustados en archivos `.blend` existentes no se eliminan automáticamente al desinstalar el *add-on*. Para borrarlos dentro de una escena, usa el botón de borrado de datos del panel o elimina manualmente los bloques de texto `data_log_internal.csv`, `data_logger_user_id`, `consent_flag` y `data_logger_warnings.txt` desde el `Text Editor`.

### Desinstalar Analysis 3D

1. Abre Blender.
2. Ve a `Edit > Preferences > Add-ons`.
3. Busca **Analysis 3D**.
4. Desactiva el *add-on*.
5. Pulsa `Remove` si quieres eliminarlo de la instalación de Blender.

## Privacidad

El `UserID` es un identificador seudónimo generado mediante UUID. No se almacenan datos personales como nombres de usuario o rutas locales. El proyecto proporciona herramientas específicas para la eliminación de datos, la exportación anónima y la gestión del consentimiento dentro del archivo `.blend`.

## Estructura de entrega final

La entrega conserva una estructura doble para facilitar tanto la evaluación automática como la instalación manual en Blender:

```text
ActualV4/
├── Data_Logger_3D.py                 # Copia en raíz para pruebas automáticas
├── Analysis_3D.zip                   # ZIP instalable en Blender
├── Analysis_3D/                      # Paquete extraído para pruebas automáticas
├── core/
├── tests/
├── docs/
├── datos_analisis/
├── scripts/
├── requirements.txt
├── CONTRIBUTING.md
├── README.md
├── LICENSE
└── TEST_RESULTS.txt
```
