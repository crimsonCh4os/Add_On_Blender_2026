# Contribuir al proyecto

Gracias por colaborar en las herramientas de monitorización y análisis 3D para Blender.

## Preparación

1. Crea un fork o una rama desde la versión más reciente.
2. Instala el entorno siguiendo `docs/DEVELOPER_GUIDE.md`.
3. Comprueba que las pruebas existentes pasan antes de modificar el código.

## Ramas y commits

Usa ramas descriptivas, por ejemplo:

```text
feature/nueva-metrica
fix/exportacion-csv
refactor/ui-graficos
```

Los commits deben ser pequeños y explicar el cambio realizado. Evita mezclar refactorizaciones amplias con correcciones funcionales no relacionadas.

## Estilo de código

- Sigue PEP 8 cuando sea compatible con las convenciones de Blender.
- Usa nombres descriptivos y docstrings en funciones no triviales.
- Mantén separada la lógica de negocio de `bpy` siempre que sea posible.
- Gestiona errores recuperables sin cerrar Blender y registra mensajes comprensibles.
- Conserva correctamente el ciclo `register()` / `unregister()`.

## Archivos que no se aceptan

No deben incluirse en commits ni pull requests:

- `site-packages/` o copias de NumPy, Matplotlib, Pillow y otras dependencias.
- `.venv/`, `venv/` o cualquier entorno virtual.
- `__pycache__/`, `.pyc` o `.pyo`.
- archivos temporales, logs locales o copias de seguridad de Blender.
- CSV con nombres, rutas locales, identificadores personales o datos no anonimizados.

## Dependencias

Las dependencias externas se declaran en `requirements.txt` y se instalan mediante `scripts/install_environment.*`.

No añadas instalaciones automáticas durante la activación del add-on. Cualquier dependencia nueva debe incluir:

1. versión fijada en `requirements.txt`;
2. justificación en el pull request;
3. prueba con el Python interno de Blender;
4. actualización del manual del desarrollador.

## Pruebas obligatorias

Ejecuta antes de abrir un pull request:

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

En Windows PowerShell:

```powershell
$env:PYTHONPATH="."
python -m unittest discover -s tests -v
```

Los cambios de interfaz, operadores o integración con `bpy` deben validarse manualmente dentro de Blender siguiendo la lista de `docs/DEVELOPER_GUIDE.md`.

Toda corrección de un fallo debería añadir una prueba que falle antes del cambio y pase después.

## Compatibilidad y CSV

Los cambios del formato CSV deben mantener compatibilidad con datos antiguos cuando sea viable. Al modificar columnas o significado de valores:

- incrementa la versión del esquema;
- actualiza la normalización en `Analysis_3D/csv_schema.py`;
- añade pruebas para esquemas antiguos y nuevos;
- actualiza README y documentación técnica.

## Privacidad

No incluyas datos personales en ejemplos, pruebas, capturas o archivos `.blend`. Usa datos sintéticos o CSV anonimizados. Conserva el consentimiento explícito y la exportación sin `UserID` al modificar Data Logger 3D.

## Pull request

El pull request debe explicar:

- problema resuelto;
- archivos y comportamiento modificados;
- pruebas ejecutadas;
- versión de Blender utilizada;
- riesgos de compatibilidad o migración.

Lista final:

- [ ] No se incluyen librerías externas ni archivos generados.
- [ ] Pasan las pruebas automatizadas.
- [ ] Se ha realizado validación manual en Blender cuando corresponde.
- [ ] Se ha actualizado la documentación.
- [ ] `Analysis_3D.zip` se ha reconstruido sin `site-packages` ni cachés.
- [ ] Los datos de prueba están anonimizados.


## Variantes de Data Logger

Los cambios funcionales del registrador deben aplicarse tanto a `Data_Loggers/Data_Logger_3D.py` como a `Data_Loggers/Data_Logger_3D_Debug.py`, salvo que sean exclusivamente de diagnóstico. No actives ambas variantes simultáneamente en Blender.
