# Validación funcional en Blender

Este documento debe completarse en el equipo real donde se prepare la defensa. No sustituye a las pruebas automatizadas; sirve para demostrar que los add-ons funcionan dentro de Blender.

## Entorno usado

| Componente | Valor |
|---|---|
| Sistema operativo |  |
| Versión de Blender |  |
| Python de Blender |  |
| NumPy en Blender |  |
| Matplotlib en Blender |  |
| Fecha de validación |  |

Comandos útiles:

```bash
blender --background --python-expr "import sys; print(sys.version)"
blender --background --python-expr "import numpy; print(numpy.__version__)"
blender --background --python-expr "import matplotlib; print(matplotlib.__version__)"
```

## Checklist de validación manual

| Nº | Prueba | Resultado esperado | Resultado obtenido | Evidencia |
|---:|---|---|---|---|
| 1 | Instalar `Data_Logger_3D.py` desde `Edit > Preferences > Add-ons > Install...` | El add-on aparece instalado |  | Captura |
| 2 | Activar `Data Logger 3D` | No aparecen errores en consola |  | Captura/consola |
| 3 | Abrir panel lateral con `N` | Aparece la pestaña del logger |  | Captura |
| 4 | Iniciar el logger | El estado cambia a activo |  | Captura |
| 5 | Realizar operaciones de modelado | Se registran eventos |  | CSV/log |
| 6 | Detener el logger | El estado cambia a detenido |  | Captura |
| 7 | Exportar CSV | Se genera CSV con cabecera v2 |  | CSV |
| 8 | Exportar CSV anónimo | El CSV no contiene `UserID` |  | CSV revisado |
| 9 | Instalar `Analysis_3D` | El add-on aparece instalado |  | Captura |
| 10 | Activar `Analysis 3D` | No aparecen errores en consola |  | Captura/consola |
| 11 | Cargar CSV generado | El CSV se carga sin errores |  | Captura |
| 12 | Calcular métricas | Se calculan las métricas esperadas |  | Captura |
| 13 | Generar gráficos/visualizaciones | Se generan visualizaciones |  | Captura |
| 14 | Reiniciar Blender y reactivar add-ons | No se duplican handlers/keymaps ni aparecen errores |  | Captura/consola |

## Observaciones

Anotar aquí cualquier error encontrado, solución aplicada o limitación observada.
