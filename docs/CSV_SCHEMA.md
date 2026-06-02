# Esquema CSV de Data Logger 3D

Este documento describe el formato CSV generado por `Data_Logger_3D.py` y aceptado por `Analysis_3D/csv_schema.py`.

La versión actual del esquema es `SchemaVersion = 2`.

## Cabecera exacta del esquema v2

La cabecera v2 debe aparecer exactamente en este orden:

```csv
SchemaVersion,LoggerVersion,SessionID,UserID,TimeStamp,Minute,Second,UserX,UserY,UserZ,SceneRadius,ObjX,ObjY,ObjZ,ObjRadius,ObjDeltaX,ObjDeltaY,ObjDeltaZ,ObjDeltaRadius,VertexDelta,NgonDelta,TriDelta,NormalDelta,ObjModeState,EditModeState,ModeChanged,UV,ObjectDelta,ModifierDelta,CtrlV,ShiftD,AltD,Merge,Occlusion
```

## Columnas del esquema v2

| Orden | Columna | Tipo esperado | Obligatoria | Descripción |
|---:|---|---|---:|---|
| 1 | `SchemaVersion` | entero | Sí | Versión del esquema CSV. En la versión actual vale `2`. |
| 2 | `LoggerVersion` | texto | Sí | Versión del add-on que generó el registro. |
| 3 | `SessionID` | texto | Sí | Identificador de la sesión de captura. |
| 4 | `UserID` | texto | Sí | Identificador seudónimo persistente asociado al usuario dentro del archivo `.blend`. |
| 5 | `TimeStamp` | numérico | Sí | Tiempo absoluto de la muestra dentro de la sesión, en segundos. |
| 6 | `Minute` | numérico | Sí | Minuto de la sesión derivado del tiempo registrado. |
| 7 | `Second` | numérico | Sí | Segundo de la sesión derivado del tiempo registrado. |
| 8 | `UserX` | numérico | Sí | Coordenada X de la vista o posición registrada del usuario/cámara. |
| 9 | `UserY` | numérico | Sí | Coordenada Y de la vista o posición registrada del usuario/cámara. |
| 10 | `UserZ` | numérico | Sí | Coordenada Z de la vista o posición registrada del usuario/cámara. |
| 11 | `SceneRadius` | numérico | Sí | Radio estimado de la escena. |
| 12 | `ObjX` | numérico | Sí | Coordenada X del objeto activo o seleccionado. |
| 13 | `ObjY` | numérico | Sí | Coordenada Y del objeto activo o seleccionado. |
| 14 | `ObjZ` | numérico | Sí | Coordenada Z del objeto activo o seleccionado. |
| 15 | `ObjRadius` | numérico | Sí | Radio estimado del objeto activo o seleccionado. |
| 16 | `ObjDeltaX` | numérico | Sí | Variación de la coordenada X del objeto respecto al estado anterior. |
| 17 | `ObjDeltaY` | numérico | Sí | Variación de la coordenada Y del objeto respecto al estado anterior. |
| 18 | `ObjDeltaZ` | numérico | Sí | Variación de la coordenada Z del objeto respecto al estado anterior. |
| 19 | `ObjDeltaRadius` | numérico | Sí | Variación del radio del objeto respecto al estado anterior. |
| 20 | `VertexDelta` | numérico | Sí | Variación del número de vértices respecto al estado anterior. |
| 21 | `NgonDelta` | numérico | Sí | Variación del número de caras n-gon respecto al estado anterior. |
| 22 | `TriDelta` | numérico | Sí | Variación del número de triángulos respecto al estado anterior. |
| 23 | `NormalDelta` | numérico | Sí | Indicador o variación asociada a cambios en normales. |
| 24 | `ObjModeState` | numérico | Sí | Estado relacionado con el modo objeto. |
| 25 | `EditModeState` | numérico | Sí | Estado relacionado con el modo edición. |
| 26 | `ModeChanged` | numérico | Sí | Indicador de cambio de modo desde la muestra anterior. |
| 27 | `UV` | numérico | Sí | Indicador asociado a cambios o actividad UV. |
| 28 | `ObjectDelta` | numérico | Sí | Variación en el conjunto de objetos de la escena. |
| 29 | `ModifierDelta` | numérico | Sí | Variación en modificadores detectados. |
| 30 | `CtrlV` | numérico | Sí | Indicador de operación de pegado detectada. |
| 31 | `ShiftD` | numérico | Sí | Indicador de duplicado con `Shift+D`. |
| 32 | `AltD` | numérico | Sí | Indicador de duplicado enlazado con `Alt+D`. |
| 33 | `Merge` | numérico | Sí | Indicador de operación de fusión geométrica. |
| 34 | `Occlusion` | numérico | Sí | Indicador relacionado con cambios de oclusión o visibilidad relevante. |

> Nota: `Analysis_3D/csv_schema.py` trata como numéricas todas las columnas comunes desde `TimeStamp` hasta `Occlusion`. Las columnas `SchemaVersion`, `LoggerVersion`, `SessionID` y `UserID` se interpretan como metadatos del registro.

## Columnas no implementadas

Las columnas `ObjectName`, `Operator`, `VertexCount`, `EdgeCount` y `FaceCount` no forman parte del esquema CSV v2 implementado actualmente.

Pueden considerarse posibles extensiones futuras, pero no deben documentarse como campos disponibles ni utilizarse como requisitos de entrada mientras no se añadan de forma explícita a:

- `Data_Logger_3D.py`, en la constante `CSV_HEADER`.
- `Analysis_3D/csv_schema.py`, en la constante `CSV_HEADER_V2`.
- Las pruebas automatizadas de compatibilidad del esquema.

## Compatibilidad con v1

La versión v1 utilizaba la columna `USER_ID` y no incluía los metadatos `SchemaVersion`, `LoggerVersion`, `SessionID` ni `UserID` con la nomenclatura actual.

`Analysis 3D` detecta automáticamente archivos v1 y los normaliza internamente al esquema v2.

| v1 | Normalización interna a v2 |
|---|---|
| `USER_ID` | `UserID` |
| Sin `SchemaVersion` | `SchemaVersion = 1` asumido |
| Sin `LoggerVersion` | Valor vacío si no está disponible |
| Sin `SessionID` | Valor vacío si no está disponible |

## Privacidad

El campo `UserID` es un identificador seudónimo generado mediante UUID. No debe interpretarse como anonimización absoluta, ya que el comportamiento registrado podría permitir inferencias indirectas sobre una sesión concreta.

Por este motivo, el logger incluye una opción de exportación sin `UserID` y operaciones para regenerar identificadores o borrar datos incrustados en el archivo `.blend`.

## CSV de ejemplo procedente de la EASD

La entrega limpia no incluye CSV reales de participantes para evitar riesgos de identificación indirecta. Para validar el esquema se recomienda generar un CSV nuevo durante la demostración o añadir únicamente una versión revisada y anonimizada.

Este archivo se utiliza como evidencia de validación funcional del flujo de trabajo, no como base suficiente para afirmar una evaluación experimental completa con usuarios. Antes de publicar el repositorio, el CSV debe revisarse o anonimizarse para evitar la exposición de identificadores o patrones que puedan asociarse a una persona concreta.
