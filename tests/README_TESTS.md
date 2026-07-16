# Tests con pytest

Estructura admitida:

```text
Add_On_Blender_2026/
├── Analysis_3D/       # analytics.py, csv_schema.py y utils.py, directos o anidados
├── core/              # data_logger_core.py
├── Data_Loggers/      # Data_Logger_3D.py, directo o anidado
├── tests/
├── pytest.ini
└── run_tests_windows.bat
```

Los tests ya no dependen de `PYTHONPATH`. El cargador de `tests/_project_loader.py`
busca recursivamente los módulos dentro de la estructura anterior y evita importar
por error paquetes externos con nombres como `analytics`.

## Ejecutar

```powershell
python -m pip install pytest numpy
python -m pytest -v
```

También se puede ejecutar `run_tests_windows.bat`.

Si `Data_Logger_3D.py` está fuera de `Data_Loggers`, puede indicarse así:

```powershell
$env:DATA_LOGGER_PATH="C:\ruta\Data_Logger_3D.py"
python -m pytest -v
```

## Semántica de operaciones UV en Data_Logger_3D.py

`detect_flags_from_operator("UV_OT_unwrap")` devuelve `False` de forma intencionada:
el retorno solo indica eventos no UV que fuerzan una fila inmediata. La operación UV
se refleja poniendo `_uv_action_pending = 1` y se valida posteriormente mediante el
hash de topología UV. El test del logger comprueba este comportamiento sin modificar
el código de producción.
