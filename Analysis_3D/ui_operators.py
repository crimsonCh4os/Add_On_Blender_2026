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

import os
import re
import bpy
import numpy as np

try:
    from .ui_helpers import *
    from .ui_properties import *
    from .ui_graph_service import visualize_graph
    from .texts import tr, wrap_lines, region_character_width
except ImportError:
    from ui_helpers import *
    from ui_properties import *
    from ui_graph_service import visualize_graph
    from texts import tr, wrap_lines, region_character_width

class ANALI_OT_SelectCSVPath(bpy.types.Operator):
    """Open the file selector to choose a folder or a specific CSV.

    If a CSV is selected, the working folder is updated, the list is refreshed,
    and only that file is selected. If a folder is selected, all compatible CSV
    files inside it are scanned.
    """
    bl_idname = "anali.select_csv_path"
    bl_label = "Select folder or CSV"
    bl_description = "Select a folder or CSV and update the analyzable file list"

    @classmethod
    def description(cls, context, properties):
        if context is not None and getattr(context, "scene", None) is not None:
            return tr(context.scene, cls.bl_description)
        return cls.bl_description

    filepath: StringProperty(subtype="FILE_PATH")
    directory: StringProperty(subtype="DIR_PATH")
    filename: StringProperty()
    filter_glob: StringProperty(default="*.csv", options={'HIDDEN'})

    def execute(self, context):
        scn = context.scene
        path = bpy.path.abspath(self.filepath or self.directory)
        if os.path.isfile(path) and path.lower().endswith('.csv'):
            scn.csv_folder = os.path.dirname(path)
            bpy.ops.anali.detect_csv()
            for item in scn.csv_items:
                item.selected = os.path.abspath(item.name) == os.path.abspath(path)
        else:
            scn.csv_folder = path
            bpy.ops.anali.detect_csv()
        update_csv_analysis_store(scn)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class ANALI_OT_DetectCSV(bpy.types.Operator):
    """Scan the configured folder and rebuild the CSV list.

    Existing file selections are preserved, and the internal metric store is
    recalculated so the UI and graphs use synchronized data.
    """
    bl_idname = "anali.detect_csv"
    bl_label = "Scan CSV"
    bl_description = "Find CSV files in the selected folder and refresh the list while keeping prior selections"

    @classmethod
    def description(cls, context, properties):
        if context is not None and getattr(context, "scene", None) is not None:
            return tr(context.scene, cls.bl_description)
        return cls.bl_description

    def execute(self, context):
        scn = context.scene
        prev_state = {item.name: item.selected for item in scn.csv_items}
        scn.csv_items.clear()
        for path in detect_csvs(scn.csv_folder):
            item = scn.csv_items.add()
            item.name = path
            item.selected = prev_state.get(path, False)
        update_csv_analysis_store(scn)
        self.report({'INFO'}, f"{len(scn.csv_items)} CSV files detected")
        return {'FINISHED'}




class ANALI_OT_ContextHelp(bpy.types.Operator):
    """Display long contextual help in a responsive dialog."""
    bl_idname = "anali.context_help"
    bl_label = "Context Help"
    bl_description = "Open detailed contextual help"

    message: StringProperty(default="")

    @classmethod
    def description(cls, context, properties):
        if context is not None:
            return tr(context.scene, getattr(properties, "message", "") or cls.bl_description)
        return getattr(properties, "message", "") or cls.bl_description

    def invoke(self, context, event):
        # The dialog width follows the available window width but remains usable
        # on small screens. Text is wrapped again on every draw call.
        region_width = getattr(context.region, "width", 420)
        window_width = getattr(context.window, "width", region_width)
        dialog_width = max(360, min(760, int(max(region_width, window_width * 0.45))))
        return context.window_manager.invoke_props_dialog(self, width=dialog_width)

    def draw(self, context):
        layout = self.layout
        text = tr(context.scene, self.message or self.bl_description)
        for paragraph_index, paragraph in enumerate(text.splitlines() or [text]):
            if paragraph_index:
                layout.separator(factor=0.35)
            for index, line in enumerate(wrap_lines(context, paragraph)):
                layout.label(text=line, icon='INFO' if paragraph_index == 0 and index == 0 else 'NONE')

    def execute(self, context):
        return {'FINISHED'}


class ANALI_OT_CalculateCSVMetricStats(bpy.types.Operator):
    """Calculate descriptive statistics for CSV metrics in selected CSV files.

    This operator only analyzes CSV interaction data. It does not modify meshes
    or invoke the model-metrics operator. It generates totals, means, rates,
    quartiles, duration in hours, and contextual data such as speed associated
    with peaks and local object size.
    """
    bl_idname = "anali.calculate_csv_metric_stats"
    bl_label = "Calculate CSV Metric Stats"
    bl_description = "Calculate CSV metrics for selected CSV files with descriptions, quartiles, and per-block context"

    @classmethod
    def description(cls, context, properties):
        if context is not None and getattr(context, "scene", None) is not None:
            return tr(context.scene, cls.bl_description)
        return cls.bl_description

    def execute(self, context):
        scn = context.scene

        selected_csvs = [i.name for i in scn.csv_items if i.selected]
        if not selected_csvs:
            self.report({'WARNING'}, tr(scn, "No CSV selected"))
            return {'CANCELLED'}

        update_scene_metric_stats(context)
        self.report({'INFO'}, tr(scn, "Metric statistics calculated"))
        return {'FINISHED'}


class OBJECT_OT_CalculateMetrics(bpy.types.Operator):
    """Calculate metrics for the active mesh and compare them with an optional reference.

    Requires the active object to be a MESH. Results are stored in
    scene["metrics_data"] so the mesh panel can display them without
    recalculating until the user requests it again.
    """
    bl_idname = "object.calculate_metrics"
    bl_label = "Calculate Metrics"
    bl_description = "Calculate geometric metrics for the active mesh and, if available, compare them with a reference"

    @classmethod
    def description(cls, context, properties):
        if context is not None and getattr(context, "scene", None) is not None:
            return tr(context.scene, cls.bl_description)
        return cls.bl_description

    def execute(self, context):
        scn = context.scene
        obj = context.active_object
        reference_obj = scn.reference_obj
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, tr(scn, "Select a MESH object"))
            return {'CANCELLED'}
        metrics = calculate_model_metrics(obj, reference_obj if reference_obj and reference_obj.type == 'MESH' else None)
        store = dict(scn.get("metrics_data", {}))
        store[obj.name] = metrics
        scn["metrics_data"] = store
        return {'FINISHED'}



class ANALI_OT_ClearGraphs(bpy.types.Operator):
    """Remove the 3D graphs generated by the add-on in the current scene.

    This does not delete CSV files, calculated metrics, or user objects outside
    the visualization layer generated by the add-on.
    """
    bl_idname = "anali.clear_graphs"
    bl_label = "Clear graphs"
    bl_description = "Clear the 3D graphs generated by the add-on from the scene"

    @classmethod
    def description(cls, context, properties):
        if context is not None and getattr(context, "scene", None) is not None:
            return tr(context.scene, cls.bl_description)
        return cls.bl_description

    def execute(self, context):
        clear_previous_graphs(context.scene)
        return {'FINISHED'}


class ANALI_OT_RestoreSceneObjects(bpy.types.Operator):
    """Show objects hidden while inspecting graphs."""
    bl_idname = "anali.restore_scene_objects"
    bl_label = "Restore scene objects"
    bl_description = "Unhide meshes and other scene objects hidden by graph visualization"

    @classmethod
    def description(cls, context, properties):
        if context is not None and getattr(context, "scene", None) is not None:
            return tr(context.scene, cls.bl_description)
        return cls.bl_description

    def execute(self, context):
        restore_hidden_scene_objects(context.scene)
        self.report({'INFO'}, tr(context.scene, "Hidden scene objects restored"))
        return {'FINISHED'}

class ANALI_OT_VisualizeGraph(bpy.types.Operator):
    """Generate the selected 3D visualization from the active CSV metrics.

    Logic is delegated to ui_graph_service.visualize_graph so this operator
    stays as a thin Blender layer: it validates context, runs generation, and
    returns status messages to the user.
    """
    bl_idname = "anali.visualize_graph"
    bl_label = "Visualize Graph"
    bl_description = "Create the configured 3D graph using the selected CSV files and metrics"

    @classmethod
    def description(cls, context, properties):
        if context is not None and getattr(context, "scene", None) is not None:
            return tr(context.scene, cls.bl_description)
        return cls.bl_description

    def execute(self, context):
        return visualize_graph(context, self.report)
