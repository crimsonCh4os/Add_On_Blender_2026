# Tools for monitoring and analysing 3D modelling processes in Blender
# Copyright (C) 2026 María Molina Goyena
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# at your option any later version.

"""Centralised bilingual user-interface text and responsive text helpers."""

from __future__ import annotations

import textwrap
from typing import Any

try:
    import bpy
except ModuleNotFoundError:
    bpy = None

LANG_EN = "EN"
LANG_ES = "ES"

# Exact English source strings used by the add-on mapped to Spanish.
ES = {
    "Dependencies": "Dependencias",
    "Dependencies installed": "Dependencias instaladas",
    "Required libraries are missing": "Faltan bibliotecas necesarias",
    "Missing": "Faltan",
    "Install dependencies": "Instalar dependencias",
    "Internet connection required. Restart Blender afterwards.": "Se necesita conexión a Internet. Reinicia Blender después.",
    "Dependencies installed. Restart Blender.": "Dependencias instaladas. Reinicia Blender.",
    "Dependency installation failed": "La instalación de dependencias ha fallado",
    "Language": "Idioma",
    "Automatic": "Automático",
    "English": "Inglés",
    "Spanish": "Español",
    "Data": "Datos",
    "Meshes": "Mallas",
    "Graphs": "Gráficos",
    "G1 data window": "Ventana de datos G1",
    "Display": "Visualización",
    "Bands": "Bandas",
    "Overlay": "Solapado",
    "Rows per window": "Filas por ventana",
    "All data": "Todos los datos",
    "samples": "muestras",
    "Overlay uses one independent real Y range per metric.": "El modo solapado usa un rango Y real independiente para cada métrica.",
    "Bands use real linear Y values and an independent scale per metric.": "Las bandas usan valores Y lineales reales y una escala independiente para cada métrica.",
    "1. CSV / Import": "1. CSV / Importación",
    "2. Global CSV Metrics": "2. Métricas globales CSV",
    "CSV Metric Stats": "Estadísticas de métricas CSV",
    "Calculate CSV Metric Stats": "Calcular estadísticas CSV",
    "No metrics calculated yet.": "Todavía no se han calculado métricas.",
    "Select": "Seleccionar",
    "Refresh list": "Actualizar lista",
    "Metric detail": "Detalle de métricas",
    "Session duration": "Duración de la sesión",
    "Session progress (%)": "Progreso de la sesión (%)",
    "Window progress (%)": "Progreso de la ventana (%)",
    "Duration": "Duración",
    "Pauses": "Pausas",
    "Total pauses": "Pausas totales",
    "Frequency": "Frecuencia",
    "Distribution": "Distribución",
    "Quartiles": "Cuartiles",
    "View speed": "Velocidad de vista",
    "Mean": "Media",
    "Std. dev.": "Desv. estándar",
    "Local size": "Tamaño local",
    "Normalized speed": "Velocidad normalizada",
    "Relative distance": "Distancia relativa",
    "obj. sizes/s": "tamaños/s",
    "x obj. size": "x tamaño",
    "Distance to object": "Distancia al objeto",
    "Movement peaks": "Picos de movimiento",
    "Total peaks": "Picos totales",
    "Mean peak speed": "Velocidad media de pico",
    "Operations": "Operaciones",
    "Shortcut reuse": "Reutilización de atajos",
    "Modifier changes": "Cambios de modificadores",
    "Events": "Eventos",
    "Total": "Total",
    "Geometry and object changes": "Cambios de geometría y objetos",
    "Vertex changes": "Cambios de vértices",
    "Total delta": "Delta total",
    "Rate": "Tasa",
    "Mesh issue changes": "Cambios de problemas de malla",
    "Total errors": "Errores totales",
    "Ngons": "N-gons",
    "Triangles": "Triángulos",
    "Normals": "Normales",
    "Object changes": "Cambios de objetos",
    "Pauses by phase": "Pausas por fase",
    "View movement peaks": "Picos de movimiento de vista",
    "Idle movement peaks": "Picos de movimiento en pausa",
    "Active movement peaks": "Picos de movimiento activo",
    "Travel peaks": "Picos de desplazamiento",
    "Temporal": "Temporal",
    "Spatial": "Espacial",
    "Strategy": "Estrategia",
    "Changes": "Cambios",
    "Mode and UV work": "Trabajo de modos y UV",
    "Work mode": "Modo de trabajo",
    "0 = Other · 1 = Object Mode · 2 = Edit Mode": "0 = Otro · 1 = Modo Objeto · 2 = Modo Edición",
    "Other": "Otro",
    "Object": "Objeto",
    "Edit": "Edición",
    "Object {object_pct}% · Edit {edit_pct}% · Other {other_pct}%": "Objeto {object_pct}% · Edición {edit_pct}% · Otro {other_pct}%",
    "Average state": "Estado medio",
    "0 = No UV topology change · 1 = UV topology change": "0 = Sin cambio de topología UV · 1 = Cambio de topología UV",
    "No change": "Sin cambio",
    "UV change": "Cambio UV",
    "UV changes in visible data: {count}": "Cambios UV en los datos visibles: {count}",
    "0 = No peak · 1 = Detected peak": "0 = Sin pico · 1 = Pico detectado",
    "No peak": "Sin pico",
    "Peak": "Pico",
    "Detected peaks in visible data: {count}": "Picos detectados en los datos visibles: {count}",
    "Shortcut events per row: Ctrl+V, Shift+D and Alt+D": "Eventos de atajo por fila: Ctrl+V, Shift+D y Alt+D",
    "Shortcut events in visible data: {count}": "Eventos de atajo en los datos visibles: {count}",
    "Absolute number of modifier changes recorded in each row": "Número absoluto de cambios de modificadores registrados en cada fila",
    "Modifier changes in visible data: {count}": "Cambios de modificadores en los datos visibles: {count}",
    "Negative = vertices removed · Positive = vertices added": "Negativo = vértices eliminados · Positivo = vértices añadidos",
    "Net vertex change: {value}": "Cambio neto de vértices: {value}",
    "Absolute changes in n-gons, triangles and inverted normals": "Cambios absolutos en n-gons, triángulos y normales invertidas",
    "Mesh issue changes in visible data: {count}": "Cambios de problemas de malla en los datos visibles: {count}",
    "Negative = objects removed · Positive = objects added": "Negativo = objetos eliminados · Positivo = objetos añadidos",
    "Net object change: {value}": "Cambio neto de objetos: {value}",
    "0 = No pause · 1 = Detected pause": "0 = Sin pausa · 1 = Pausa detectada",
    "No pause": "Sin pausa",
    "Pause": "Pausa",
    "Detected pauses in visible data: {count}": "Pausas detectadas en los datos visibles: {count}",
    "Object Mode": "Modo Objeto",
    "Edit Mode": "Modo Edición",
    "Mode changes": "Cambios de modo",
    "UV work": "Trabajo UV",
    "1. CSV ↔ Mesh Link": "1. Enlace CSV ↔ Malla",
    "2. Mesh Metrics": "2. Métricas de malla",
    "Object mesh": "Malla del objeto",
    "Reference mesh": "Malla de referencia",
    "Calculate model metrics": "Calcular métricas del modelo",
    "Mesh metrics help": "Ayuda de métricas de malla",
    "Select a mesh and calculate metrics.": "Selecciona una malla y calcula las métricas.",
    "No active mesh found.": "No se encontró una malla activa.",
    "No CSV selected": "No se ha seleccionado ningún CSV",
    "Metric statistics calculated": "Estadísticas de métricas calculadas",
    "Select a MESH object": "Selecciona un objeto de tipo MALLA",
    "Hidden scene objects restored": "Objetos ocultos de la escena restaurados",
    "Link the CSV data to a mesh object.": "Vincula los datos CSV con un objeto de malla para analizar conjuntamente la sesión y el modelo.",
    "The 'Object mesh' is the model being analyzed.": "La 'Malla del objeto' es el modelo principal que se analizará.",
    "The 'Reference mesh' is optional: only needed for the Similarity metric. Leave it empty if you do not need a comparison.": "La 'Malla de referencia' es opcional y solo se necesita para calcular la similitud. Déjala vacía cuando no quieras comparar modelos.",
    "UV Mapping": "Mapeado UV",
    "Transforms & Position": "Transformaciones y posición",
    "Topology": "Topología",
    "Similarity": "Similitud",
    "1. Visual Settings": "1. Ajustes visuales",
    "2. Render / Control": "2. Renderizado / Control",
    "Scale and labels help": "Ayuda de escala y etiquetas",
    "Render controls help": "Ayuda de controles de renderizado",
    "Select metrics": "Seleccionar métricas",
    "Color palette": "Paleta de colores",
    "Log scale": "Escala logarítmica",
    "Compact labels": "Etiquetas compactas",
    "Scale X": "Escala X",
    "Scale Y": "Escala Y",
    "Scale Z": "Escala Z",
    "Clear graphs": "Borrar gráficos",
    "Restore objects": "Restaurar objetos",
    "Restore scene objects": "Restaurar objetos de escena",
    "Visualize 3D graph": "Visualizar gráfico 3D",
    "Graph": "Gráfico",
    "Section": "Sección",
    "Reference Object": "Objeto de referencia",
    "Object": "Objeto",
    "pauses": "pausas",
    "pauses/h": "pausas/h",
    "peaks": "picos",
    "peaks/min": "picos/min",
    "events": "eventos",
    "events/h": "eventos/h",
    "events/min": "eventos/min",
    "vertices": "vértices",
    "verts/min": "vértices/min",
    "errors": "errores",
    "err/min": "errores/min",
    "changes": "cambios",
    "chg/min": "cambios/min",
    "models": "modelos",
    "min": "min",
    "m/h": "m/h",
    "m": "m",
    "u.local": "u. local",
    "%": "%",
    "UV area": "Área UV",
    "UV islands": "Islas UV",
    "UV stretch": "Estiramiento UV",
    "Texel density": "Densidad de téxel",
    "Inverted normals (%)": "Normales invertidas (%)",
    "Transforms applied": "Transformaciones aplicadas",
    "At world origin": "En el origen global",
    "Non-quad faces (%)": "Caras no cuadrangulares (%)",
    "Duplicate vertices (count)": "Vértices duplicados (cantidad)",
    "Duplicate vertices (%)": "Vértices duplicados (%)",
    "Face count": "Cantidad de caras",
    "Connected parts": "Partes conectadas",
    "Faces per connected part": "Caras por parte conectada",
    "Mean edge angle": "Ángulo medio de aristas",
    "Similarity vs. reference": "Similitud con la referencia",
    "Normals": "Normales",

    "Select folder or CSV": "Seleccionar carpeta o CSV",
    "Scan CSV": "Buscar CSV",
    "Context Help": "Ayuda contextual",
    "Calculate Metrics": "Calcular métricas",
    "Clear graphs": "Borrar gráficos",
    "Restore scene objects": "Restaurar objetos de escena",
    "Visualize Graph": "Visualizar gráfico",
    "Select a folder or CSV and update the analyzable file list": "Selecciona una carpeta o un archivo CSV y actualiza la lista de archivos disponibles para el análisis.",
    "Find CSV files in the selected folder and refresh the list while keeping prior selections": "Busca archivos CSV en la carpeta seleccionada y actualiza la lista conservando las selecciones existentes.",
    "Open detailed contextual help": "Abre una ayuda contextual detallada para la sección seleccionada.",
    "Calculate CSV metrics for selected CSV files with descriptions, quartiles, and per-block context": "Calcula las métricas de los archivos CSV seleccionados e incluye estadísticas, cuartiles y contexto organizado por bloques.",
    "Calculate geometric metrics for the active mesh and, if available, compare them with a reference": "Calcula métricas geométricas de la malla activa y, cuando existe una referencia, compara ambos modelos.",
    "Clear the 3D graphs generated by the add-on from the scene": "Elimina de la escena los gráficos 3D generados por el complemento.",
    "Unhide meshes and other scene objects hidden by graph visualization": "Vuelve a mostrar las mallas y otros objetos ocultados durante la visualización de gráficos.",
    "Create the configured 3D graph using the selected CSV files and metrics": "Crea el gráfico 3D configurado utilizando los archivos CSV y las métricas seleccionadas.",
    "Show a test sine graph to validate Matplotlib inside Blender": "Muestra un gráfico sinusoidal de prueba para comprobar Matplotlib dentro de Blender.",
    "CSV file": "Archivo CSV",
    "Effect [95% CI]": "Efecto [IC 95%]",
    "Overall": "Global",
    "No effect": "Sin efecto",
}


ES.update({
    "Octree similarity": "Similitud con octree",
    "Limit criterion": "Criterio de límite",
    "Maximum subdivisions": "Máximo de subdivisiones",
    "Elements per node": "Elementos por nodo",
    "Objects are aligned internally by centre of mass and rotation. Scene transforms are not changed.":
        "Los objetos se alinean internamente por centro de masa y rotación. Las transformaciones de la escena no cambian.",
    "Radar margin": "Margen del radar",
    "Usable radar area": "Área útil del radar",
    "Per-metric min-max normalization": "Normalización mínimo-máximo por métrica",
    "Radar data margin": "Margen de datos del radar",
})


HELP_EN = {'Total duration of the CSV recording, expressed in hours.': 'This section shows the total time covered by '
                                                             'the selected CSV recording. It provides the '
                                                             'temporal reference for the rest of the '
                                                             'analysis and helps place event totals, rates, '
                                                             'pauses, navigation activity, and editing '
                                                             'changes within the length of the session.',
 'Pauses are detected from unusually long intervals without edit events. Quartiles show when they occur during the recording.': 'This '
                                                                                                                                'section '
                                                                                                                                'identifies '
                                                                                                                                'unusually '
                                                                                                                                'long '
                                                                                                                                'intervals '
                                                                                                                                'between '
                                                                                                                                'recorded '
                                                                                                                                'editing '
                                                                                                                                'events. '
                                                                                                                                'It '
                                                                                                                                'reports '
                                                                                                                                'the '
                                                                                                                                'total '
                                                                                                                                'number '
                                                                                                                                'of '
                                                                                                                                'detected '
                                                                                                                                'pauses, '
                                                                                                                                'their '
                                                                                                                                'frequency '
                                                                                                                                'relative '
                                                                                                                                'to '
                                                                                                                                'session '
                                                                                                                                'duration, '
                                                                                                                                'and '
                                                                                                                                'their '
                                                                                                                                'distribution '
                                                                                                                                'across '
                                                                                                                                'the '
                                                                                                                                'four '
                                                                                                                                'temporal '
                                                                                                                                'quartiles '
                                                                                                                                'of '
                                                                                                                                'the '
                                                                                                                                'recording.',
 "Average user speed calculated from displacement and time between rows. Local size, when present in the CSV, is the object's local bounding size/scale used as contextual reference.": 'This '
                                                                                                                                                                                        'section '
                                                                                                                                                                                        'summarizes '
                                                                                                                                                                                        'viewport '
                                                                                                                                                                                        'movement '
                                                                                                                                                                                        'speed '
                                                                                                                                                                                        'using '
                                                                                                                                                                                        'the '
                                                                                                                                                                                        'displacement '
                                                                                                                                                                                        'and '
                                                                                                                                                                                        'elapsed '
                                                                                                                                                                                        'time '
                                                                                                                                                                                        'between '
                                                                                                                                                                                        'consecutive '
                                                                                                                                                                                        'CSV '
                                                                                                                                                                                        'rows. '
                                                                                                                                                                                        'It '
                                                                                                                                                                                        'includes '
                                                                                                                                                                                        'the '
                                                                                                                                                                                        'mean '
                                                                                                                                                                                        'speed, '
                                                                                                                                                                                        'its '
                                                                                                                                                                                        'standard '
                                                                                                                                                                                        'deviation, '
                                                                                                                                                                                        'and '
                                                                                                                                                                                        'the '
                                                                                                                                                                                        'available '
                                                                                                                                                                                        'local '
                                                                                                                                                                                        'object '
                                                                                                                                                                                        'size '
                                                                                                                                                                                        'as '
                                                                                                                                                                                        'a '
                                                                                                                                                                                        'scale '
                                                                                                                                                                                        'reference '
                                                                                                                                                                                        'for '
                                                                                                                                                                                        'understanding '
                                                                                                                                                                                        'the '
                                                                                                                                                                                        'recorded '
                                                                                                                                                                                        'navigation.',
 "Average distance between user and object, subtracting the available object radius or size. Local size is the object's local bounding size/scale if the CSV provides it.": 'This '
                                                                                                                                                                            'section '
                                                                                                                                                                            'estimates '
                                                                                                                                                                            'the '
                                                                                                                                                                            'average '
                                                                                                                                                                            'distance '
                                                                                                                                                                            'between '
                                                                                                                                                                            'the '
                                                                                                                                                                            'recorded '
                                                                                                                                                                            'viewpoint '
                                                                                                                                                                            'and '
                                                                                                                                                                            'the '
                                                                                                                                                                            'analyzed '
                                                                                                                                                                            'object. '
                                                                                                                                                                            'When '
                                                                                                                                                                            'object '
                                                                                                                                                                            'radius '
                                                                                                                                                                            'or '
                                                                                                                                                                            'local '
                                                                                                                                                                            'size '
                                                                                                                                                                            'is '
                                                                                                                                                                            'available, '
                                                                                                                                                                            'it '
                                                                                                                                                                            'is '
                                                                                                                                                                            'used '
                                                                                                                                                                            'to '
                                                                                                                                                                            'express '
                                                                                                                                                                            'the '
                                                                                                                                                                            'distance '
                                                                                                                                                                            'in '
                                                                                                                                                                            'relation '
                                                                                                                                                                            'to '
                                                                                                                                                                            'the '
                                                                                                                                                                            'object '
                                                                                                                                                                            'rather '
                                                                                                                                                                            'than '
                                                                                                                                                                            'only '
                                                                                                                                                                            'to '
                                                                                                                                                                            'its '
                                                                                                                                                                            'center.',
 'Detects unusually high movement speed during the session.': 'This section counts unusually fast viewport '
                                                              'movements detected during the session. It '
                                                              'reports the number of peaks, their rate over '
                                                              'time, the average speed of those peaks, and '
                                                              'where they occur across the recording '
                                                              'quartiles.',
 'Counts shortcut reuse and modifier changes recorded in the CSV.': 'This section summarizes repeated '
                                                                    'shortcut use and modifier-related '
                                                                    'activity recorded in the CSV. It groups '
                                                                    'these interaction events so the main '
                                                                    'editing operations can be reviewed '
                                                                    'without examining every row '
                                                                    'individually.',
 'Counts the exact CSV fields CtrlV, ShiftD and AltD.': 'This section counts the recorded uses of Ctrl+V, '
                                                        'Shift+D, and Alt+D. It presents the total '
                                                        'occurrences of these shortcuts and their temporal '
                                                        'distribution during the session.',
 'Modifier use or equivalent row-level changes detected per row.': 'This section reports modifier operations '
                                                                   'or equivalent modifier-count changes '
                                                                   'detected in the CSV rows. It summarizes '
                                                                   'the total activity, its rate, and its '
                                                                   'distribution throughout the session.',
 'Vertices, mesh errors, and mesh/object changes are separated; each part has its own quartiles.': 'This '
                                                                                                   'section '
                                                                                                   'groups '
                                                                                                   'structural '
                                                                                                   'changes '
                                                                                                   'into '
                                                                                                   'separate '
                                                                                                   'categories '
                                                                                                   'for '
                                                                                                   'vertices, '
                                                                                                   'mesh '
                                                                                                   'issues, '
                                                                                                   'and mesh '
                                                                                                   'or '
                                                                                                   'object '
                                                                                                   'events. '
                                                                                                   'Each '
                                                                                                   'category '
                                                                                                   'includes '
                                                                                                   'totals, '
                                                                                                   'normalized '
                                                                                                   'rates, '
                                                                                                   'and '
                                                                                                   'quartile '
                                                                                                   'information '
                                                                                                   'so its '
                                                                                                   'evolution '
                                                                                                   'can be '
                                                                                                   'read '
                                                                                                   'independently.',
 'Vertex evolution shown as total delta, rate, and quartiles.': 'This section describes how the vertex count '
                                                                'changed during the recording. It includes '
                                                                'the accumulated vertex delta, the rate of '
                                                                'change over time, and the distribution of '
                                                                'those changes across the session quartiles.',
 'Mesh error evolution separated by registered error type: ngons, triangles, and normals.': 'This section '
                                                                                            'summarizes '
                                                                                            'changes '
                                                                                            'associated with '
                                                                                            'n-gons, '
                                                                                            'triangles, and '
                                                                                            'normal-orientation '
                                                                                            'records. Each '
                                                                                            'type is shown '
                                                                                            'separately with '
                                                                                            'its accumulated '
                                                                                            'amount, rate, '
                                                                                            'and temporal '
                                                                                            'distribution.',
 'Mesh/object change events plus estimated mesh/object count at the end of each quartile.': 'This section '
                                                                                            'reports object '
                                                                                            'and mesh change '
                                                                                            'events detected '
                                                                                            'in the '
                                                                                            'recording. It '
                                                                                            'also shows the '
                                                                                            'estimated '
                                                                                            'object or mesh '
                                                                                            'count at the '
                                                                                            'end of each '
                                                                                            'quartile to '
                                                                                            'describe how '
                                                                                            'scene structure '
                                                                                            'evolved over '
                                                                                            'time.',
 'Summarizes Object Mode, Edit Mode and UV activity.': 'This section brings together the main working-state '
                                                       'information from the session. It summarizes time '
                                                       'spent in Object Mode and Edit Mode, mode '
                                                       'transitions, and recorded UV-related activity.',
 'Percentage in Object Mode, Edit Mode, and mode-switch frequency.': 'This section shows the proportion of '
                                                                     'the recording spent in Object Mode and '
                                                                     'Edit Mode, together with the number '
                                                                     'and frequency of transitions between '
                                                                     'them.',
 'UV work events calculated as total, rate, and quartiles.': 'This section counts recorded UV-related '
                                                             'operations and presents their total, rate over '
                                                             'time, and distribution across the four session '
                                                             'quartiles.',
 'CSV_METRICS_LONG_HELP': 'This section converts the selected CSV recordings into a structured summary of '
                          'the modeling process. It includes session duration, pauses, viewport movement, '
                          'distance to the object, movement peaks, shortcuts, modifiers, geometry changes, '
                          'object changes, working modes, and UV activity. Totals, averages, rates, standard '
                          'deviations, and quartiles are used where appropriate so each part of the session '
                          'can be described in a consistent way.',
 'UV_MAPPING_LONG_HELP': 'This section summarizes the UV organization of the active mesh. It includes total '
                         'UV area, number of UV islands, estimated UV stretch, and texel density, providing '
                         'a compact description of how the three-dimensional surface has been unfolded and '
                         'distributed in two-dimensional texture space.',
 'NORMALS_LONG_HELP': 'This section examines the orientation of the mesh faces and reports the percentage of '
                      'normals detected as inverted. Face normals define the outward direction used by '
                      'shading, culling, modifiers, exports, and many geometry operations.',
 'TRANSFORMS_LONG_HELP': 'This section checks the transform state and position of the analyzed object. It '
                         'indicates whether location, rotation, and scale are applied according to the '
                         'add-on criteria and whether the object is located at the world origin.',
 'TOPOLOGY_LONG_HELP': 'This section summarizes the structural organization of the active mesh. It includes '
                       'non-quad faces, duplicate vertices, total face count, connected components, faces '
                       'per component, and mean edge angle to provide an overview of mesh composition and '
                       'connectivity.',
 'SIMILARITY_LONG_HELP': 'This section compares the active mesh with the selected reference mesh and '
                         'produces a combined similarity score. The comparison uses the geometric and '
                         'topological characteristics implemented by the add-on to summarize how closely '
                         'both models match according to those measurements.',
 'GRAPH_SETTINGS_LONG_HELP': 'This section defines what information will be shown in the generated 3D graph '
                             'and how it will be presented. It includes metric selection, graph type, color '
                             'palette, logarithmic scaling, compact labels, and other display options used '
                             'to organize the visualization.',
 'RENDER_CONTROLS_LONG_HELP': 'This section contains the controls used to create, scale, clear, and restore '
                              'the 3D graph inside Blender. The X, Y, and Z scale values control the '
                              'physical dimensions of the visualization, while the action buttons generate '
                              'the graph or manage previously created scene elements.'}

HELP_ES = {'Total duration of the CSV recording, expressed in hours.': 'Esta sección muestra el tiempo total cubierto '
                                                             'por la grabación CSV seleccionada. Proporciona '
                                                             'la referencia temporal para el resto del '
                                                             'análisis y permite situar los totales de '
                                                             'eventos, las tasas, las pausas, la navegación '
                                                             'y los cambios de edición dentro de la duración '
                                                             'de la sesión.',
 'Pauses are detected from unusually long intervals without edit events. Quartiles show when they occur during the recording.': 'Esta '
                                                                                                                                'sección '
                                                                                                                                'identifica '
                                                                                                                                'intervalos '
                                                                                                                                'inusualmente '
                                                                                                                                'largos '
                                                                                                                                'entre '
                                                                                                                                'eventos '
                                                                                                                                'de '
                                                                                                                                'edición '
                                                                                                                                'registrados. '
                                                                                                                                'Muestra '
                                                                                                                                'el '
                                                                                                                                'número '
                                                                                                                                'total '
                                                                                                                                'de '
                                                                                                                                'pausas '
                                                                                                                                'detectadas, '
                                                                                                                                'su '
                                                                                                                                'frecuencia '
                                                                                                                                'respecto '
                                                                                                                                'a '
                                                                                                                                'la '
                                                                                                                                'duración '
                                                                                                                                'de '
                                                                                                                                'la '
                                                                                                                                'sesión '
                                                                                                                                'y '
                                                                                                                                'su '
                                                                                                                                'distribución '
                                                                                                                                'entre '
                                                                                                                                'los '
                                                                                                                                'cuatro '
                                                                                                                                'cuartiles '
                                                                                                                                'temporales '
                                                                                                                                'de '
                                                                                                                                'la '
                                                                                                                                'grabación.',
 "Average user speed calculated from displacement and time between rows. Local size, when present in the CSV, is the object's local bounding size/scale used as contextual reference.": 'Esta '
                                                                                                                                                                                        'sección '
                                                                                                                                                                                        'resume '
                                                                                                                                                                                        'la '
                                                                                                                                                                                        'velocidad '
                                                                                                                                                                                        'de '
                                                                                                                                                                                        'movimiento '
                                                                                                                                                                                        'de '
                                                                                                                                                                                        'la '
                                                                                                                                                                                        'vista '
                                                                                                                                                                                        'utilizando '
                                                                                                                                                                                        'el '
                                                                                                                                                                                        'desplazamiento '
                                                                                                                                                                                        'y '
                                                                                                                                                                                        'el '
                                                                                                                                                                                        'tiempo '
                                                                                                                                                                                        'transcurrido '
                                                                                                                                                                                        'entre '
                                                                                                                                                                                        'filas '
                                                                                                                                                                                        'consecutivas '
                                                                                                                                                                                        'del '
                                                                                                                                                                                        'CSV. '
                                                                                                                                                                                        'Incluye '
                                                                                                                                                                                        'la '
                                                                                                                                                                                        'velocidad '
                                                                                                                                                                                        'media, '
                                                                                                                                                                                        'su '
                                                                                                                                                                                        'desviación '
                                                                                                                                                                                        'estándar '
                                                                                                                                                                                        'y '
                                                                                                                                                                                        'el '
                                                                                                                                                                                        'tamaño '
                                                                                                                                                                                        'local '
                                                                                                                                                                                        'disponible '
                                                                                                                                                                                        'del '
                                                                                                                                                                                        'objeto '
                                                                                                                                                                                        'como '
                                                                                                                                                                                        'referencia '
                                                                                                                                                                                        'de '
                                                                                                                                                                                        'escala '
                                                                                                                                                                                        'para '
                                                                                                                                                                                        'comprender '
                                                                                                                                                                                        'la '
                                                                                                                                                                                        'navegación '
                                                                                                                                                                                        'registrada.',
 "Average distance between user and object, subtracting the available object radius or size. Local size is the object's local bounding size/scale if the CSV provides it.": 'Esta '
                                                                                                                                                                            'sección '
                                                                                                                                                                            'estima '
                                                                                                                                                                            'la '
                                                                                                                                                                            'distancia '
                                                                                                                                                                            'media '
                                                                                                                                                                            'entre '
                                                                                                                                                                            'el '
                                                                                                                                                                            'punto '
                                                                                                                                                                            'de '
                                                                                                                                                                            'vista '
                                                                                                                                                                            'registrado '
                                                                                                                                                                            'y '
                                                                                                                                                                            'el '
                                                                                                                                                                            'objeto '
                                                                                                                                                                            'analizado. '
                                                                                                                                                                            'Cuando '
                                                                                                                                                                            'se '
                                                                                                                                                                            'dispone '
                                                                                                                                                                            'del '
                                                                                                                                                                            'radio '
                                                                                                                                                                            'o '
                                                                                                                                                                            'del '
                                                                                                                                                                            'tamaño '
                                                                                                                                                                            'local '
                                                                                                                                                                            'del '
                                                                                                                                                                            'objeto, '
                                                                                                                                                                            'se '
                                                                                                                                                                            'utiliza '
                                                                                                                                                                            'para '
                                                                                                                                                                            'expresar '
                                                                                                                                                                            'la '
                                                                                                                                                                            'distancia '
                                                                                                                                                                            'en '
                                                                                                                                                                            'relación '
                                                                                                                                                                            'con '
                                                                                                                                                                            'el '
                                                                                                                                                                            'propio '
                                                                                                                                                                            'objeto '
                                                                                                                                                                            'y '
                                                                                                                                                                            'no '
                                                                                                                                                                            'únicamente '
                                                                                                                                                                            'con '
                                                                                                                                                                            'su '
                                                                                                                                                                            'centro.',
 'Detects unusually high movement speed during the session.': 'Esta sección cuenta los movimientos de vista '
                                                              'inusualmente rápidos detectados durante la '
                                                              'sesión. Muestra el número de picos, su tasa '
                                                              'temporal, la velocidad media de esos picos y '
                                                              'su distribución entre los cuartiles de la '
                                                              'grabación.',
 'Counts shortcut reuse and modifier changes recorded in the CSV.': 'Esta sección resume la reutilización de '
                                                                    'atajos y la actividad relacionada con '
                                                                    'modificadores registrada en el CSV. '
                                                                    'Agrupa estos eventos de interacción '
                                                                    'para revisar las principales '
                                                                    'operaciones de edición sin tener que '
                                                                    'examinar cada fila individualmente.',
 'Counts the exact CSV fields CtrlV, ShiftD and AltD.': 'Esta sección cuenta los usos registrados de Ctrl+V, '
                                                        'Shift+D y Alt+D. Presenta el total de apariciones '
                                                        'de estos atajos y su distribución temporal durante '
                                                        'la sesión.',
 'Modifier use or equivalent row-level changes detected per row.': 'Esta sección muestra las operaciones de '
                                                                   'modificadores o los cambios equivalentes '
                                                                   'en su cantidad detectados en las filas '
                                                                   'del CSV. Resume la actividad total, su '
                                                                   'tasa y su distribución a lo largo de la '
                                                                   'sesión.',
 'Vertices, mesh errors, and mesh/object changes are separated; each part has its own quartiles.': 'Esta '
                                                                                                   'sección '
                                                                                                   'agrupa '
                                                                                                   'los '
                                                                                                   'cambios '
                                                                                                   'estructurales '
                                                                                                   'en '
                                                                                                   'categorías '
                                                                                                   'separadas '
                                                                                                   'para '
                                                                                                   'vértices, '
                                                                                                   'problemas '
                                                                                                   'de malla '
                                                                                                   'y '
                                                                                                   'eventos '
                                                                                                   'de malla '
                                                                                                   'u '
                                                                                                   'objetos. '
                                                                                                   'Cada '
                                                                                                   'categoría '
                                                                                                   'incluye '
                                                                                                   'totales, '
                                                                                                   'tasas '
                                                                                                   'normalizadas '
                                                                                                   'e '
                                                                                                   'información '
                                                                                                   'por '
                                                                                                   'cuartiles '
                                                                                                   'para '
                                                                                                   'describir '
                                                                                                   'su '
                                                                                                   'evolución '
                                                                                                   'de forma '
                                                                                                   'independiente.',
 'Vertex evolution shown as total delta, rate, and quartiles.': 'Esta sección describe cómo cambió la '
                                                                'cantidad de vértices durante la grabación. '
                                                                'Incluye el delta acumulado de vértices, la '
                                                                'tasa de cambio y la distribución de esas '
                                                                'modificaciones entre los cuartiles de la '
                                                                'sesión.',
 'Mesh error evolution separated by registered error type: ngons, triangles, and normals.': 'Esta sección '
                                                                                            'resume los '
                                                                                            'cambios '
                                                                                            'asociados con '
                                                                                            'n-gons, '
                                                                                            'triángulos y '
                                                                                            'registros de '
                                                                                            'orientación de '
                                                                                            'normales. Cada '
                                                                                            'tipo se '
                                                                                            'presenta por '
                                                                                            'separado con su '
                                                                                            'cantidad '
                                                                                            'acumulada, su '
                                                                                            'tasa y su '
                                                                                            'distribución '
                                                                                            'temporal.',
 'Mesh/object change events plus estimated mesh/object count at the end of each quartile.': 'Esta sección '
                                                                                            'muestra los '
                                                                                            'eventos de '
                                                                                            'cambio de '
                                                                                            'objetos y '
                                                                                            'mallas '
                                                                                            'detectados en '
                                                                                            'la grabación. '
                                                                                            'También '
                                                                                            'presenta la '
                                                                                            'cantidad '
                                                                                            'estimada de '
                                                                                            'objetos o '
                                                                                            'mallas al final '
                                                                                            'de cada cuartil '
                                                                                            'para describir '
                                                                                            'cómo evolucionó '
                                                                                            'la estructura '
                                                                                            'de la escena.',
 'Summarizes Object Mode, Edit Mode and UV activity.': 'Esta sección reúne la información principal sobre '
                                                       'los estados de trabajo de la sesión. Resume el '
                                                       'tiempo en Modo Objeto y Modo Edición, los cambios de '
                                                       'modo y la actividad UV registrada.',
 'Percentage in Object Mode, Edit Mode, and mode-switch frequency.': 'Esta sección muestra la proporción de '
                                                                     'la grabación realizada en Modo Objeto '
                                                                     'y Modo Edición, junto con la cantidad '
                                                                     'y frecuencia de los cambios entre '
                                                                     'ambos modos.',
 'UV work events calculated as total, rate, and quartiles.': 'Esta sección cuenta las operaciones '
                                                             'relacionadas con UV registradas y presenta su '
                                                             'total, su tasa temporal y su distribución '
                                                             'entre los cuatro cuartiles de la sesión.',
 'CSV_METRICS_LONG_HELP': 'Esta sección convierte las grabaciones CSV seleccionadas en un resumen '
                          'estructurado del proceso de modelado. Incluye duración de la sesión, pausas, '
                          'movimiento de la vista, distancia al objeto, picos de movimiento, atajos, '
                          'modificadores, cambios de geometría, cambios de objetos, modos de trabajo y '
                          'actividad UV. Se utilizan totales, medias, tasas, desviaciones estándar y '
                          'cuartiles cuando corresponde para describir cada parte de la sesión de forma '
                          'coherente.',
 'UV_MAPPING_LONG_HELP': 'Esta sección resume la organización UV de la malla activa. Incluye el área UV '
                         'total, el número de islas UV, el estiramiento estimado y la densidad de téxel, '
                         'ofreciendo una descripción compacta de cómo se ha desplegado y distribuido la '
                         'superficie tridimensional en el espacio bidimensional de las texturas.',
 'NORMALS_LONG_HELP': 'Esta sección examina la orientación de las caras de la malla y muestra el porcentaje '
                      'de normales detectadas como invertidas. Las normales definen la dirección exterior '
                      'utilizada por el sombreado, el descarte de caras, los modificadores, las '
                      'exportaciones y muchas operaciones geométricas.',
 'TRANSFORMS_LONG_HELP': 'Esta sección comprueba el estado de las transformaciones y la posición del objeto '
                         'analizado. Indica si la localización, la rotación y la escala están aplicadas '
                         'según los criterios del complemento y si el objeto se encuentra en el origen '
                         'global.',
 'TOPOLOGY_LONG_HELP': 'Esta sección resume la organización estructural de la malla activa. Incluye caras no '
                       'cuadrangulares, vértices duplicados, cantidad total de caras, componentes '
                       'conectados, caras por componente y ángulo medio de aristas para ofrecer una visión '
                       'general de la composición y conectividad de la malla.',
 'SIMILARITY_LONG_HELP': 'Esta sección compara la malla activa con la malla de referencia seleccionada y '
                         'genera una puntuación combinada de similitud. La comparación utiliza las '
                         'características geométricas y topológicas implementadas por el complemento para '
                         'resumir cuánto se parecen ambos modelos según esas mediciones.',
 'GRAPH_SETTINGS_LONG_HELP': 'Esta sección define qué información aparecerá en el gráfico 3D generado y cómo '
                             'se presentará. Incluye la selección de métricas, el tipo de gráfico, la paleta '
                             'de colores, la escala logarítmica, las etiquetas compactas y otras opciones de '
                             'visualización utilizadas para organizar la representación.',
 'RENDER_CONTROLS_LONG_HELP': 'Esta sección contiene los controles utilizados para crear, escalar, borrar y '
                              'restaurar el gráfico 3D dentro de Blender. Los valores de escala X, Y y Z '
                              'controlan las dimensiones físicas de la visualización, mientras que los '
                              'botones de acción generan el gráfico o gestionan los elementos creados '
                              'anteriormente.'}


# Tables and navigation additions. Kept in one central map so both the N-panel
# and text objects generated inside the 3D scene follow the selected language.
ES.update({
    "CSV files selected": "Archivos CSV seleccionados",
    "Metrics selected": "Métricas seleccionadas",
    "1. Table content": "1. Contenido de la tabla",
    "2. Layout and pagination": "2. Diseño y paginación",
    "3. Create / Control": "3. Crear / Controlar",
    "Displayed value": "Valor mostrado",
    "Rows": "Filas",
    "Metrics": "Métricas",
    "CSV page": "Página CSV",
    "Metric page": "Página de métricas",
    "Create 3D table": "Crear tabla 3D",
    "Clear table": "Borrar tabla",
    "Restore objects": "Restaurar objetos",
    "Select CSV files in the Data tab": "Selecciona archivos CSV en la pestaña Datos",
    "Select at least one CSV file": "Selecciona al menos un archivo CSV",
    "Select at least one metric": "Selecciona al menos una métrica",
    "No valid data could be loaded for the table": "No se pudieron cargar datos válidos para la tabla",
    "The selected metrics contain no valid values": "Las métricas seleccionadas no contienen valores válidos",
    "Raw data table · selected CSV metrics": "Tabla de datos brutos · métricas CSV seleccionadas",
    "Data table · selected CSV metrics": "Tabla de datos · métricas CSV seleccionadas",
    "All recorded values": "Todos los valores registrados",
    "no aggregation": "sin agregación",
    "two decimals": "dos decimales",
    "values shown with two decimals": "valores mostrados con dos decimales",
    "rows": "filas",
    "columns": "columnas",
    "CSV / User": "CSV / Usuario",
    "Row": "Fila",
    "raw observations": "observaciones brutas",
    "CSV files": "archivos CSV",
    "Showing": "Mostrando",
    "of": "de",
    "and": "y",
    "metrics": "métricas",
    "Data table generated": "Tabla de datos generada",
    "Mean": "Media",
    "Median": "Mediana",
    "Standard deviation": "Desviación típica",
    "Minimum": "Mínimo",
    "Maximum": "Máximo",
    "Sum": "Suma",
    "Count": "Recuento",
    "Last value": "Último valor",
    "All raw values": "Todos los valores brutos",
})

def get_language(scene: Any = None) -> str:
    """Return the language explicitly selected by the user."""
    selected = getattr(scene, "anali_language", LANG_EN) if scene is not None else LANG_EN
    return selected if selected in {LANG_EN, LANG_ES} else LANG_EN


def tr(scene: Any, text: str) -> str:
    if get_language(scene) == LANG_ES:
        return ES.get(text, HELP_ES.get(text, text))
    return HELP_EN.get(text, text)


def format_text(scene: Any, text: str, **values: Any) -> str:
    return tr(scene, text).format(**values)


def _ui_scale(context: Any) -> float:
    try:
        return max(float(context.preferences.system.ui_scale), 0.5)
    except Exception:
        return 1.0


def _available_region_pixels(context: Any, reserve_px: int = 58) -> int:
    """Return the usable horizontal space of the current Blender region.

    This is evaluated every time the panel is drawn, so changing the width of
    the N-panel immediately changes the wrapping on the next redraw.
    """
    width_px = 320
    try:
        width_px = int(context.region.width)
    except Exception:
        pass
    scaled_reserve = int(reserve_px * _ui_scale(context))
    return max(80, width_px - scaled_reserve)


def region_character_width(context: Any, *, reserve_px: int = 58, minimum: int = 12, maximum: int = 90) -> int:
    """Estimate a conservative character count from the live region width."""
    usable_px = _available_region_pixels(context, reserve_px=reserve_px)
    # A conservative average avoids clipping in nested boxes and with accented text.
    chars = int(usable_px / (8.2 * _ui_scale(context)))
    return max(minimum, min(maximum, chars))


def _pixel_wrap(context: Any, text: str, *, reserve_px: int = 58, indent_px: int = 0) -> list[str]:
    """Wrap text using Blender font measurements when available."""
    raw = str(text or "")
    if not raw:
        return [""]

    max_px = max(70, _available_region_pixels(context, reserve_px=reserve_px) - indent_px)
    try:
        import blf
        font_id = 0
        blf.size(font_id, max(9, round(11 * _ui_scale(context))))

        lines: list[str] = []
        for paragraph in raw.splitlines() or [raw]:
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                candidate = f"{current} {word}"
                if blf.dimensions(font_id, candidate)[0] <= max_px:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines or [""]
    except Exception:
        width = region_character_width(context, reserve_px=reserve_px)
        return textwrap.wrap(
            raw, width=max(8, width),
            break_long_words=False, break_on_hyphens=False,
        ) or [""]


def wrap_lines(
    context: Any,
    text: str,
    *,
    indent: int = 0,
    width: int | None = None,
    reserve_px: int = 58,
) -> list[str]:
    if width is not None:
        available = max(8, width - indent)
        return textwrap.wrap(
            str(text or ""), width=available,
            break_long_words=False, break_on_hyphens=False,
        ) or [""]
    return _pixel_wrap(
        context, text, reserve_px=reserve_px,
        indent_px=max(0, indent) * int(8.2 * _ui_scale(context)),
    )


def label_value_lines(context: Any, label: str, value: str) -> list[str]:
    """Return responsive ``Label:  value`` lines without separate columns."""
    prefix = f"{label}:  "
    raw_value = str(value)
    try:
        import blf
        font_id = 0
        blf.size(font_id, max(9, round(11 * _ui_scale(context))))
        prefix_px = int(blf.dimensions(font_id, prefix)[0])
    except Exception:
        prefix_px = int(len(prefix) * 8.2 * _ui_scale(context))

    chunks = _pixel_wrap(
        context, raw_value, reserve_px=58, indent_px=prefix_px,
    )
    lines = [prefix + chunks[0]]
    # Blender labels do not preserve tab stops reliably. Spaces keep all
    # continuation lines visually aligned with the value in the same label.
    continuation = " " * len(prefix)
    lines.extend(continuation + chunk for chunk in chunks[1:])
    return lines

