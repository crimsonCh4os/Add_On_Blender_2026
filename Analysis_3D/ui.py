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
    from .ui_operators import (
        ANALI_OT_SelectCSVPath,
        ANALI_OT_DetectCSV,
        ANALI_OT_CalculateCSVMetricStats,
        ANALI_OT_ContextHelp,
        OBJECT_OT_CalculateMetrics,
        ANALI_OT_ClearGraphs,
        ANALI_OT_RestoreSceneObjects,
        ANALI_OT_VisualizeGraph,
    )
    from .ui_panels import ANALI_UL_CSVList, ANALI_UL_AnalysisList, ANALI_PT_MainPanel
except ImportError:
    from ui_properties import MetricStatItem, CSVItem, AnalysisItem
    from ui_helpers import GRAPH_TYPES, refresh_analysis_list
    from analytics import ANALYSIS
    from ui_operators import (
        ANALI_OT_SelectCSVPath,
        ANALI_OT_DetectCSV,
        ANALI_OT_CalculateCSVMetricStats,
        ANALI_OT_ContextHelp,
        OBJECT_OT_CalculateMetrics,
        ANALI_OT_ClearGraphs,
        ANALI_OT_RestoreSceneObjects,
        ANALI_OT_VisualizeGraph,
    )
    from ui_panels import ANALI_UL_CSVList, ANALI_UL_AnalysisList, ANALI_PT_MainPanel




def _update_log_scale(self, context):
    if getattr(self, "anali_use_log_scale", False):
        self.anali_use_compact_labels = False


def _update_compact_labels(self, context):
    if getattr(self, "anali_use_compact_labels", False):
        self.anali_use_log_scale = False

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
    ANALI_OT_VisualizeGraph,
    ANALI_UL_CSVList,
    ANALI_UL_AnalysisList,
    ANALI_PT_MainPanel,
)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)

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
    bpy.types.Scene.axis_scale_x = FloatProperty(name="Scale X", default=5.0, min=0.1)
    bpy.types.Scene.axis_scale_y = FloatProperty(name="Scale Y", default=5.0, min=0.1)
    bpy.types.Scene.axis_scale_z = FloatProperty(name="Scale Z", default=1.5, min=0.1)
    bpy.types.Scene.anali_use_log_scale = BoolProperty(
        name="Log scale",
        description="Compress numeric values with a logarithmic scale. Useful when one metric dominates the others. Cannot be active at the same time as Compact labels.",
        default=False,
        update=_update_log_scale,
    )
    bpy.types.Scene.anali_use_compact_labels = BoolProperty(
        name="Compact labels",
        description="Shorten CSV and metric labels to reduce overlap in legends and panels. Does not change the data. Cannot be active at the same time as Log scale.",
        default=False,
        update=_update_compact_labels,
    )

    bpy.types.Scene.anali_color_palette = EnumProperty(
        name="Color palette",
        description="Palette used for graph colors",
        items=[
            ('ibm_color_blind_safe', 'IBM Color Blind Safe', 'Accessible categorical palette'),
            ('viridis', 'Viridis', 'Perceptually uniform palette'),
            ('inferno', 'Inferno', 'High-contrast perceptually uniform palette'),
        ],
        default='ibm_color_blind_safe',
    )
    bpy.types.Scene.anali_ui_tab = EnumProperty(
        name="Section",
        items=[('DATA', '📊 Data', ''), ('MESH', '📐 Meshes', ''), ('GRAPHS', '🎨 Graphs', '')],
        default='DATA',
    )
    bpy.types.Scene.anali_show_csv_import = BoolProperty(name="Show CSV Import", default=True)
    bpy.types.Scene.anali_show_global_metrics = BoolProperty(name="Show Global Metrics", default=True)
    bpy.types.Scene.anali_show_mesh_binding = BoolProperty(name="Show Binding", default=True)
    bpy.types.Scene.anali_show_model_metrics = BoolProperty(name="Show Mesh Metrics", default=True)
    bpy.types.Scene.anali_show_graph_config = BoolProperty(name="Show Visual Settings", default=True)
    bpy.types.Scene.anali_show_render_controls = BoolProperty(name="Show Render Controls", default=True)
    bpy.types.Scene.anali_target_obj = PointerProperty(name="Object", type=bpy.types.Object, poll=lambda self, obj: obj.type == 'MESH')
    metric_binding_items = [(key, value['label'], '') for key, value in ANALYSIS.items()]
    bpy.types.Scene.anali_bind_x_metric = EnumProperty(name="CSV X", items=metric_binding_items, default='A1')
    bpy.types.Scene.anali_bind_y_metric = EnumProperty(name="CSV Y", items=metric_binding_items, default='A4')
    bpy.types.Scene.anali_bind_z_metric = EnumProperty(name="CSV Z", items=metric_binding_items, default='A5')
    bpy.types.Scene.anali_bind_size_metric = EnumProperty(name="CSV Size", items=metric_binding_items, default='A16')

    if getattr(bpy.context, "scene", None) is not None:
        refresh_analysis_list(None, bpy.context)

def unregister() -> None:
    for prop in [
        "csv_items", "analysis_items", "metric_stats", "csv_index", "analysis_index",
        "csv_folder", "selected_graph", "analysis_mode", "reference_obj",
        "axis_scale_x", "axis_scale_y", "axis_scale_z", "anali_use_log_scale", "anali_use_compact_labels", "anali_color_palette", "anali_ui_tab",
        "anali_show_csv_import", "anali_show_global_metrics", "anali_show_mesh_binding",
        "anali_show_model_metrics", "anali_show_graph_config", "anali_show_render_controls",
        "anali_target_obj", "anali_bind_x_metric", "anali_bind_y_metric",
        "anali_bind_z_metric", "anali_bind_size_metric",
    ]:
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
