# Herramientas para la monitorización y análisis de procesos de modelado 3D en Blender
# Copyright (C) 2026 María Molina Goyena
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# at your option any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

"""Blender UI registration facade.

This module intentionally contains no business logic. The former monolithic UI
implementation has been split into helpers, property models, operators and
panels so Blender registration remains thin and maintainable.
"""

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty

try:
    from .ui_properties import MetricStatItem, CSVItem, AnalysisItem
    from .ui_helpers import GRAPH_TYPES, refresh_analysis_list
    from .analytics import ANALYSIS
    from .texts import tr, LANG_EN, LANG_ES
    from .ui_operators import (
        ANALI_OT_SelectCSVPath,
        ANALI_OT_DetectCSV,
        ANALI_OT_CalculateCSVMetricStats,
        ANALI_OT_ContextHelp,
        OBJECT_OT_CalculateMetrics,
        ANALI_OT_ClearGraphs,
        ANALI_OT_RestoreSceneObjects,
        ANALI_OT_G1ChangeWindow,
        ANALI_OT_VisualizeGraph,
        ANALI_OT_VisualizeTable,
        ANALI_OT_ClearTables,
        ANALI_OT_TableChangePage,
    )
    from .ui_panels import ANALI_UL_CSVList, ANALI_UL_AnalysisList, ANALI_PT_MainPanel
except ImportError:
    from ui_properties import MetricStatItem, CSVItem, AnalysisItem
    from ui_helpers import GRAPH_TYPES, refresh_analysis_list
    from analytics import ANALYSIS
    from texts import tr, LANG_EN, LANG_ES
    from ui_operators import (
        ANALI_OT_SelectCSVPath,
        ANALI_OT_DetectCSV,
        ANALI_OT_CalculateCSVMetricStats,
        ANALI_OT_ContextHelp,
        OBJECT_OT_CalculateMetrics,
        ANALI_OT_ClearGraphs,
        ANALI_OT_RestoreSceneObjects,
        ANALI_OT_G1ChangeWindow,
        ANALI_OT_VisualizeGraph,
        ANALI_OT_VisualizeTable,
        ANALI_OT_ClearTables,
        ANALI_OT_TableChangePage,
    )
    from ui_panels import ANALI_UL_CSVList, ANALI_UL_AnalysisList, ANALI_PT_MainPanel





LANGUAGE_ITEMS = (
    (LANG_EN, "English", "Display the add-on in English"),
    (LANG_ES, "Español", "Mostrar el complemento en español"),
)

# Enum labels are generated from the selected add-on language so every panel,
# including Tables, changes language consistently without bilingual captions.
_TAB_ITEMS_EN = (
    ('DATA', "📊 Data", "CSV data and statistics"),
    ('MESH', "📐 Meshes", "Mesh analysis"),
    ('TABLES', "▦ Tables", "3D metric tables"),
    ('GRAPHS', "🎨 Graphs", "Graph configuration"),
)
_TAB_ITEMS_ES = (
    ('DATA', "📊 Datos", "Datos CSV y estadísticas"),
    ('MESH', "📐 Mallas", "Análisis de mallas"),
    ('TABLES', "▦ Tablas", "Tablas 3D de métricas"),
    ('GRAPHS', "🎨 Gráficos", "Configuración de gráficos"),
)
_TABLE_STAT_ITEMS_EN = (
    ('MEAN', 'Mean', 'Arithmetic mean of each metric series'),
    ('RAW', 'All raw values', 'Show every recorded value without aggregation'),
    ('MEDIAN', 'Median', 'Median of each metric series'),
    ('STD', 'Standard deviation', 'Sample standard deviation'),
    ('MIN', 'Minimum', 'Smallest observed value'),
    ('MAX', 'Maximum', 'Largest observed value'),
    ('SUM', 'Sum', 'Sum of all observed values'),
    ('COUNT', 'Count', 'Number of valid observations'),
    ('LAST', 'Last value', 'Last valid observed value'),
)
_TABLE_STAT_ITEMS_ES = (
    ('MEAN', 'Media', 'Media aritmética de la serie de cada métrica'),
    ('RAW', 'Todos los valores brutos', 'Mostrar cada valor registrado sin agregación'),
    ('MEDIAN', 'Mediana', 'Mediana de la serie de cada métrica'),
    ('STD', 'Desviación típica', 'Desviación típica muestral'),
    ('MIN', 'Mínimo', 'Menor valor observado'),
    ('MAX', 'Máximo', 'Mayor valor observado'),
    ('SUM', 'Suma', 'Suma de todos los valores observados'),
    ('COUNT', 'Recuento', 'Número de observaciones válidas'),
    ('LAST', 'Último valor', 'Último valor válido observado'),
)


def _tab_items(self, context):
    return _TAB_ITEMS_ES if getattr(self, 'anali_language', LANG_EN) == LANG_ES else _TAB_ITEMS_EN


def _table_stat_items(self, context):
    return _TABLE_STAT_ITEMS_ES if getattr(self, 'anali_language', LANG_EN) == LANG_ES else _TABLE_STAT_ITEMS_EN


def _update_language(self, context):
    if context is None or context.screen is None:
        return
    for area in context.screen.areas:
        area.tag_redraw()


def _update_log_scale(self, context):
    if getattr(self, "anali_use_log_scale", False):
        self.anali_use_compact_labels = False


def _update_compact_labels(self, context):
    if getattr(self, "anali_use_compact_labels", False):
        self.anali_use_log_scale = False


def _update_ui_tab(self, context):
    """Ensure the shared metric list exists as soon as Tables or Graphs opens."""
    if context is None or getattr(context, "scene", None) is None:
        return
    scene = context.scene
    if getattr(scene, "anali_ui_tab", "") in {'TABLES', 'GRAPHS'} and len(scene.analysis_items) == 0:
        refresh_analysis_list(None, context)
    if getattr(context, "screen", None) is not None:
        for area in context.screen.areas:
            area.tag_redraw()

CLASSES = (
    MetricStatItem,
    CSVItem,
    AnalysisItem,
    ANALI_OT_SelectCSVPath,
    ANALI_OT_DetectCSV,
    ANALI_OT_CalculateCSVMetricStats,
    ANALI_OT_ContextHelp,
    OBJECT_OT_CalculateMetrics,
    ANALI_OT_ClearGraphs,
    ANALI_OT_RestoreSceneObjects,
    ANALI_OT_G1ChangeWindow,
    ANALI_OT_VisualizeGraph,
    ANALI_OT_VisualizeTable,
    ANALI_OT_ClearTables,
    ANALI_OT_TableChangePage,
    ANALI_UL_CSVList,
    ANALI_UL_AnalysisList,
    ANALI_PT_MainPanel,
)


def register() -> None:
    registered_classes = []
    try:
        for cls in CLASSES:
            bpy.utils.register_class(cls)
            registered_classes.append(cls)

        bpy.types.Scene.csv_items = CollectionProperty(type=CSVItem)
        bpy.types.Scene.analysis_items = CollectionProperty(type=AnalysisItem)
        bpy.types.Scene.metric_stats = CollectionProperty(type=MetricStatItem)
        bpy.types.Scene.csv_index = IntProperty(default=0)
        bpy.types.Scene.analysis_index = IntProperty(default=0)
        bpy.types.Scene.csv_folder = StringProperty(subtype='DIR_PATH')
        bpy.types.Scene.selected_graph = EnumProperty(
            name="Graph",
            items=[(key, value["label"], "Experimental graph type; select metrics only, axes are fixed by graph type") for key, value in GRAPH_TYPES.items()],
            default="G1",
            update=refresh_analysis_list,
        )
        bpy.types.Scene.analysis_mode = EnumProperty(
            name="Mode",
            items=[('DESCRIPTIVE', 'Descriptive', ''), ('COMPARATIVE', 'Comparative', ''), ('INFERENTIAL', 'Inferential', '')],
            default='DESCRIPTIVE',
        )
        bpy.types.Scene.reference_obj = PointerProperty(name="Reference Object", type=bpy.types.Object, poll=lambda self, obj: obj.type == 'MESH')
        bpy.types.Scene.anali_octree_limit_mode = EnumProperty(
            name="Octree limit",
            items=[
                ('DEPTH', 'Maximum subdivisions', 'Stop after the selected maximum octree depth'),
                ('ELEMENTS', 'Maximum elements', 'Subdivide until each leaf contains at most the selected number of vertices'),
                ('BOTH', 'Both limits', 'Stop when either depth or element limit is reached'),
            ],
            default='BOTH',
        )
        bpy.types.Scene.anali_octree_max_depth = IntProperty(
            name="Maximum subdivisions",
            description="Maximum octree depth used by geometric similarity",
            default=8,
            min=1,
            max=24,
        )
        bpy.types.Scene.anali_octree_max_items = IntProperty(
            name="Elements per node",
            description="Maximum vertices stored in an octree leaf",
            default=32,
            min=1,
            max=4096,
        )
        bpy.types.Scene.axis_scale_x = FloatProperty(name="Scale X", default=5.0, min=0.1)
        bpy.types.Scene.axis_scale_y = FloatProperty(name="Scale Y", default=5.0, min=0.1)
        bpy.types.Scene.axis_scale_z = FloatProperty(name="Scale Z", default=1.5, min=0.1)
        bpy.types.Scene.anali_use_log_scale = BoolProperty(
            name="Log scale",
            default=False,
            update=_update_log_scale,
        )
        bpy.types.Scene.anali_use_compact_labels = BoolProperty(
            name="Compact labels",
            default=False,
            update=_update_compact_labels,
        )
        bpy.types.Scene.anali_g1_window_size = IntProperty(
            name="G1 window size",
            description="Number of real data rows shown in each G1 window",
            default=20,
            min=1,
            max=100000,
        )
        bpy.types.Scene.anali_g1_window_start = IntProperty(
            name="G1 window start",
            description="Zero-based first row of the G1 window",
            default=0,
            min=0,
            max=100000000,
        )
        bpy.types.Scene.anali_g1_global_view = BoolProperty(
            name="G1 global view",
            description="Show all available G1 data before the numbered windows",
            default=True,
        )
        bpy.types.Scene.anali_g1_display_mode = EnumProperty(
            name="G1 display mode",
            description="Show metrics in separate bands or superimposed with an independent real range per metric",
            items=[
                ('BANDS', 'Bands', 'One independent vertical band per metric'),
                ('OVERLAY', 'Overlay', 'All metrics superimposed; each metric keeps its own real Y range'),
            ],
            default='BANDS',
        )
        bpy.types.Scene.anali_radar_margin = FloatProperty(
            name="Radar margin",
            description="Empty radial margin kept inside and outside the normalized radar data",
            default=0.10,
            min=0.0,
            max=0.20,
            subtype='PERCENTAGE',
        )

        bpy.types.Scene.anali_color_palette = EnumProperty(
            name="Color palette",
            items=[
                ('ibm_color_blind_safe', 'IBM Color Blind Safe', 'Accessible categorical palette'),
                ('viridis', 'Viridis', 'Perceptually uniform palette'),
                ('inferno', 'Inferno', 'High-contrast perceptually uniform palette'),
                ('plasma', 'Plasma', 'Vivid purple-to-yellow palette'),
                ('magma', 'Magma', 'Dark purple-to-yellow palette'),
                ('cividis', 'Cividis', 'Color-vision-friendly uniform palette'),
                ('turbo', 'Turbo', 'Broad high-contrast rainbow palette'),
                ('coolwarm', 'Coolwarm', 'Diverging blue-to-red palette'),
            ],
            default='ibm_color_blind_safe',
        )
        bpy.types.Scene.anali_language = EnumProperty(
            name="Language / Idioma",
            items=LANGUAGE_ITEMS,
            default=LANG_EN,
            update=_update_language,
        )
        bpy.types.Scene.anali_ui_tab = EnumProperty(
            name="Section",
            items=_tab_items,
            update=_update_ui_tab,
        )
        bpy.types.Scene.anali_show_csv_import = BoolProperty(name="Show CSV Import", default=True)
        bpy.types.Scene.anali_show_global_metrics = BoolProperty(name="Show Global Metrics", default=True)
        bpy.types.Scene.anali_show_mesh_binding = BoolProperty(name="Show Binding", default=True)
        bpy.types.Scene.anali_show_model_metrics = BoolProperty(name="Show Mesh Metrics", default=True)
        bpy.types.Scene.anali_show_graph_config = BoolProperty(name="Show Visual Settings", default=True)
        bpy.types.Scene.anali_show_table_config = BoolProperty(name="Show Table Settings", default=True)
        bpy.types.Scene.anali_table_statistic = EnumProperty(
            name="Value",
            items=_table_stat_items,
        )
        bpy.types.Scene.anali_table_rows_per_page = IntProperty(name="Rows per page", default=10, min=1, max=30)
        bpy.types.Scene.anali_table_cols_per_page = IntProperty(name="Metrics per page", default=4, min=1, max=8)
        bpy.types.Scene.anali_table_row_page = IntProperty(name="CSV page", default=1, min=1, max=10000, soft_max=50)
        bpy.types.Scene.anali_table_col_page = IntProperty(name="Metric page", default=1, min=1, max=10000, soft_max=50)
        bpy.types.Scene.anali_show_render_controls = BoolProperty(name="Show Render Controls", default=True)
        bpy.types.Scene.anali_target_obj = PointerProperty(name="Object", type=bpy.types.Object, poll=lambda self, obj: obj.type == 'MESH')
        metric_binding_items = [(key, value['label'], '') for key, value in ANALYSIS.items()]
        bpy.types.Scene.anali_bind_x_metric = EnumProperty(name="CSV X", items=metric_binding_items, default='A1')
        bpy.types.Scene.anali_bind_y_metric = EnumProperty(name="CSV Y", items=metric_binding_items, default='A4')
        bpy.types.Scene.anali_bind_z_metric = EnumProperty(name="CSV Z", items=metric_binding_items, default='A5')
        bpy.types.Scene.anali_bind_size_metric = EnumProperty(name="CSV Size", items=metric_binding_items, default='A16')

        if getattr(bpy.context, "scene", None) is not None:
            scene = bpy.context.scene
            if not getattr(scene, "anali_ui_tab", ""):
                scene.anali_ui_tab = 'DATA'
            if not getattr(scene, "anali_table_statistic", ""):
                scene.anali_table_statistic = 'MEAN'
            refresh_analysis_list(None, bpy.context)
    except Exception:
        # Roll back a partial registration so a failed property does not leave
        # panels active without their Scene properties.
        for prop in [
            "csv_items", "analysis_items", "metric_stats", "csv_index", "analysis_index",
            "csv_folder", "selected_graph", "analysis_mode", "reference_obj",
            "anali_octree_limit_mode", "anali_octree_max_depth", "anali_octree_max_items",
            "axis_scale_x", "axis_scale_y", "axis_scale_z", "anali_use_log_scale",
            "anali_use_compact_labels", "anali_g1_window_size", "anali_g1_window_start", "anali_g1_global_view", "anali_g1_display_mode", "anali_radar_margin", "anali_color_palette", "anali_language",
            "anali_ui_tab", "anali_show_csv_import", "anali_show_global_metrics",
            "anali_show_mesh_binding", "anali_show_model_metrics",
            "anali_show_graph_config", "anali_show_table_config", "anali_table_statistic", "anali_table_rows_per_page", "anali_table_cols_per_page", "anali_table_row_page", "anali_table_col_page", "anali_show_render_controls",
            "anali_target_obj", "anali_bind_x_metric", "anali_bind_y_metric",
            "anali_bind_z_metric", "anali_bind_size_metric",
        ]:
            if hasattr(bpy.types.Scene, prop):
                delattr(bpy.types.Scene, prop)
        for cls in reversed(registered_classes):
            try:
                bpy.utils.unregister_class(cls)
            except Exception:
                pass
        raise

def unregister() -> None:
    for prop in [
        "csv_items", "analysis_items", "metric_stats", "csv_index", "analysis_index",
        "csv_folder", "selected_graph", "analysis_mode", "reference_obj",
            "anali_octree_limit_mode", "anali_octree_max_depth", "anali_octree_max_items",
        "axis_scale_x", "axis_scale_y", "axis_scale_z", "anali_use_log_scale", "anali_use_compact_labels", "anali_g1_window_size", "anali_g1_window_start", "anali_g1_global_view", "anali_g1_display_mode", "anali_radar_margin", "anali_color_palette", "anali_language", "anali_ui_tab",
        "anali_show_csv_import", "anali_show_global_metrics", "anali_show_mesh_binding",
        "anali_show_model_metrics", "anali_show_graph_config", "anali_show_table_config", "anali_table_statistic", "anali_table_rows_per_page", "anali_table_cols_per_page", "anali_table_row_page", "anali_table_col_page", "anali_show_render_controls",
        "anali_target_obj", "anali_bind_x_metric", "anali_bind_y_metric",
        "anali_bind_z_metric", "anali_bind_size_metric",
    ]:
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
