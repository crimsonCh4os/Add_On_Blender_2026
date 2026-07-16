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

import bpy

try:
    from .ui_helpers import *
    from .ui_properties import *
    from .texts import tr, get_language, region_character_width, wrap_lines, label_value_lines
    from .dependencies import dependencies_available, missing_dependencies
except ImportError:
    from ui_helpers import *
    from ui_properties import *
    from texts import tr, get_language, region_character_width, wrap_lines, label_value_lines
    from dependencies import dependencies_available, missing_dependencies

class ANALI_UL_CSVList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "selected", text="")
        row.label(text=os.path.basename(item.name))


class ANALI_UL_AnalysisList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text=tr(context.scene, item.label))
        row.label(text=f"[{tr(context.scene, item.typology)}]")

class ANALI_PT_MainPanel(bpy.types.Panel):
    bl_label = "3D CSV Analysis + Metrics"
    bl_category = "3D Analysis"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        scn = context.scene
        layout = self.layout

        language_box = layout.box()
        language_row = language_box.row(align=True)
        language_row.label(text=tr(scn, "Language"), icon='WORLD')
        language_row.prop(scn, "anali_language", text="")

        dependency_box = layout.box()
        if dependencies_available():
            dependency_box.label(text=tr(scn, "Dependencies installed"), icon='CHECKMARK')
        else:
            missing = ", ".join(missing_dependencies())
            dependency_box.label(text=tr(scn, "Required libraries are missing"), icon='ERROR')
            dependency_box.label(text=f"{tr(scn, 'Missing')}: {missing}")
            dependency_box.operator(
                "anali.install_dependencies",
                text=tr(scn, "Install dependencies"),
                icon='IMPORT',
            )
            dependency_box.label(
                text=tr(scn, "Internet connection required. Restart Blender afterwards."),
                icon='INFO',
            )

        row = layout.row(align=True)
        row.prop(scn, "anali_ui_tab", expand=True)

        if scn.anali_ui_tab == 'DATA':
            self._draw_data_tab(context, layout, scn)
        elif scn.anali_ui_tab == 'MESH':
            self._draw_mesh_tab(context, layout, scn)
        elif scn.anali_ui_tab == 'TABLES':
            self._draw_tables_tab(context, layout, scn)
        else:
            self._draw_graphs_tab(context, layout, scn)

    def _wrap_lines(self, context, text, width=None):
        return wrap_lines(context, text, width=width)

    def _label_wrap(self, context, layout, text, icon='NONE', width=None):
        lines = self._wrap_lines(context, text, width)
        for i, line in enumerate(lines):
            layout.label(text=line, icon=icon if i == 0 else 'NONE')

    def _info_box(self, context, parent, lines, icon='INFO', width=None):
        """Draw fixed explanatory text with live N-panel width wrapping."""
        ib = parent.box()
        # Rebuild one translated paragraph on every draw. This avoids three
        # independently wrapped fragments and responds correctly when the
        # sidebar is resized, opened, or closed.
        paragraph = " ".join(tr(context.scene, text).strip() for text in lines if text)
        wrapped = wrap_lines(
            context, paragraph, width=width, reserve_px=82,
        )
        for idx, line in enumerate(wrapped):
            ib.label(text=line, icon=icon if idx == 0 else 'NONE')
        return ib

    def _metric_row_wrap(self, context, parent, label, value, help_text=""):
        """Draw one metric without contextual-help icons.

        Contextual help is intentionally attached only to group titles.
        """
        col = parent.column(align=True)
        for i, line in enumerate(label_value_lines(context, tr(context.scene, label), str(value))):
            col.label(text=line, icon='DOT' if i == 0 else 'NONE')

    def _draw_data_tab(self, context, layout, scn):
        box = layout.box()
        row = box.row(align=True)
        row.prop(scn, "anali_show_csv_import", text="", icon='TRIA_DOWN' if scn.anali_show_csv_import else 'TRIA_RIGHT', emboss=False)
        row.label(text=tr(scn, "1. CSV / Import"), icon='FILE_FOLDER')
        if scn.anali_show_csv_import:
            row = box.row(align=True)
            row.prop(scn, "csv_folder", text="")
            row.operator("anali.select_csv_path", text=tr(scn, "Select"))
            box.template_list("ANALI_UL_CSVList", "", scn, "csv_items", scn, "csv_index")
            box.operator("anali.detect_csv", text=tr(scn, "Refresh list"))


        box = layout.box()
        row = box.row(align=True)
        row.prop(scn, "anali_show_global_metrics", text="", icon='TRIA_DOWN' if scn.anali_show_global_metrics else 'TRIA_RIGHT', emboss=False)
        row.label(text=tr(scn, "2. Global CSV Metrics"), icon='SPREADSHEET')
        if scn.anali_show_global_metrics:
            box.operator("anali.calculate_csv_metric_stats", text=tr(scn, "Calculate CSV Metric Stats"))

            if len(scn.metric_stats) > 0:
                self._draw_csv_metric_stats(context, box, scn)
            else:
                box.label(text=tr(scn, "No metrics calculated yet."), icon='INFO')

    def _draw_csv_metric_stats(self, context, layout, scn):
        """Draw CSV metrics statistics with short visible text.

        Long explanations are shown as tooltips when hovering over
        the info icon. Visible labels are wrapped into 18-20 character
        lines to avoid overly long horizontal rows.
        """
        box_stats = layout.box()
        box_stats.label(text=tr(scn, "CSV Metric Stats"))

        def _find_stat(csv_name, key):
            for st in scn.metric_stats:
                if getattr(st, "csv_name", "") == csv_name and getattr(st, "key", "") == key:
                    return st
            return None

        csv_names = []
        for st in scn.metric_stats:
            name = getattr(st, "csv_name", "")
            if name not in csv_names:
                csv_names.append(name)

        def _num(v, decimals=0):
            try:
                if decimals <= 0:
                    return f"{float(v):.0f}"
                return f"{float(v):.{decimals}f}"
            except Exception:
                return "0"

        def _wrap(text, width=None):
            return wrap_lines(context, tr(scn, str(text or "")), width=width)

        def _label(box, text, icon='NONE', width=None):
            lines = _wrap(text, width)
            for i, line in enumerate(lines):
                box.label(text=line, icon=icon if (i == 0 and icon != 'NONE') else 'NONE')


        def _header(box, text, tooltip="", icon='NONE'):
            """Draw a compact, visually strong block title.

            Blender UI labels do not support true bold text, so metric titles
            are emphasized with a short boxed heading, an icon, and a separator.
            Longer explanations stay in the info-icon tooltip.
            """
            box.separator(factor=0.25)
            row = box.row(align=True)
            row.scale_y = 1.12
            title_col = row.column(align=True)
            lines = _wrap(text)
            for i, line in enumerate(lines):
                line_icon = icon if (i == 0 and icon != 'NONE') else ('TRIA_RIGHT' if i == 0 else 'NONE')
                if i == 0 and tooltip:
                    title_op = title_col.operator("anali.context_help", text=line, icon=line_icon, emboss=True)
                    title_op.message = tr(scn, tooltip)
                else:
                    title_col.label(text=line, icon=line_icon)
            box.separator(factor=0.20)

        def _section(parent, title, tooltip="", icon='NONE'):
            b = parent.box()
            _header(b, title, tooltip, icon=icon)
            return b

        def _q_lines(box, q1, q2, q3, q4, unit="events", decimals=0):
            _metric_value(box, "Distribution", tr(scn, "Quartiles"))
            for label, value in (("Q1", q1), ("Q2", q2), ("Q3", q3), ("Q4", q4)):
                _metric_value(box, label, value, unit, decimals)

        def _metric_value(box, title, value, unit="", decimals=0):
            suffix = f" {tr(scn, unit)}" if unit else ""
            value_text = f"{_num(value, decimals)}{suffix}"
            for line in label_value_lines(context, tr(scn, title), value_text):
                box.label(text=line)

        def _rate_block(box, title, abs_value, rate_value, rate_unit, rate_decimals=2):
            _label(box, title)
            _metric_value(box, "Total", abs_value, "", 0)
            _metric_value(box, "Frequency", rate_value, rate_unit, rate_decimals)

        for csv_name in csv_names:
            file_box = box_stats.box()
            clean_name = os.path.basename(csv_name).replace("_data.csv", "").replace(".csv", "")
            _label(file_box, clean_name, icon='FILE')

            details = file_box.box()
            _header(
                details,
                "Metric detail",
                "CSV_METRICS_LONG_HELP",
                icon='SPREADSHEET',
            )

            a1 = _find_stat(csv_name, "A1")
            if a1:
                b = _section(details, "Session duration", "Total duration of the CSV recording, expressed in hours.", icon='INFO')
                _metric_value(b, "Duration", a1.total, "min", 3)

            a2 = _find_stat(csv_name, "A2")
            a3 = _find_stat(csv_name, "A3")
            if a2 or a3:
                b = _section(
                    details,
                    "Pauses",
                    "Pauses are detected from unusually long intervals without edit events. Quartiles show when they occur during the recording.",
                    icon='INFO',
                )
                pause_stat = a2 or a3
                if pause_stat:
                    _metric_value(b, "Total pauses", pause_stat.count, "pauses", 0)
                    _metric_value(b, "Frequency", pause_stat.rate_per_hour, "pauses/h", 2)
                if a3:
                    _q_lines(b, a3.q1, a3.q2, a3.q3, a3.q4, "pauses")

            a4 = _find_stat(csv_name, "A4")
            if a4:
                b = _section(
                    details,
                    "View speed",
                    "Average user speed calculated from displacement and time between rows. Local size, when present in the CSV, is the object's local bounding size/scale used as contextual reference.",
                    icon='INFO',
                )
                local_size = getattr(a4, "object_local_size", 0.0)
                # Convert m/h divided by object size to object sizes per second.
                normalized_speed = (
                    (a4.mean / local_size) / 3600.0
                    if local_size and local_size > 0.0
                    else 0.0
                )

                _metric_value(b, "Mean", a4.mean, "m/h", 1)
                _metric_value(b, "Std. dev.", a4.std, "m/h", 1)
                _metric_value(b, "Local size", local_size, "u.local", 3)
                _metric_value(
                    b,
                    "Normalized speed",
                    normalized_speed,
                    "obj. sizes/s",
                    2,
                )

            a5 = _find_stat(csv_name, "A5")
            if a5:
                b = _section(
                    details,
                    "Distance to object",
                    "Average distance between user and object, subtracting the available object radius or size. Local size is the object's local bounding size/scale if the CSV provides it.",
                    icon='INFO',
                )
                local_size = getattr(a5, "object_local_size", 0.0)
                relative_distance = (
                    a5.mean / local_size
                    if local_size and local_size > 0.0
                    else 0.0
                )

                _metric_value(b, "Mean", a5.mean, "m", 2)
                _metric_value(b, "Std. dev.", a5.std, "m", 2)
                _metric_value(b, "Local size", local_size, "u.local", 3)
                _metric_value(
                    b,
                    "Relative distance",
                    relative_distance,
                    "x obj. size",
                    2,
                )

            speed_stats = [_find_stat(csv_name, key) for key in ("A6", "A7", "A8", "A9")]
            available_speed_stats = [st for st in speed_stats if st]
            if available_speed_stats:
                representative_stat = available_speed_stats[0]
                b = _section(
                    details,
                    "Movement peaks",
                    "Detects unusually high movement speed during the session.",
                    icon='INFO',
                )
                _metric_value(b, "Total peaks", representative_stat.count, "peaks", 0)
                _metric_value(b, "Frequency", representative_stat.rate_per_min, "peaks/min", 2)
                _metric_value(b, "Mean peak speed", getattr(representative_stat, "peak_speed_mean", 0.0), "m/h", 1)
                _q_lines(
                    b,
                    representative_stat.q1,
                    representative_stat.q2,
                    representative_stat.q3,
                    representative_stat.q4,
                    "peaks",
                )

            a10 = _find_stat(csv_name, "A10")
            a11 = _find_stat(csv_name, "A11")
            if a10 or a11:
                b = _section(
                    details,
                    "Operations",
                    "Counts shortcut reuse and modifier changes recorded in the CSV.",
                    icon='INFO',
                )
                if a10:
                    sub = _section(b, "Shortcut reuse", "Counts the exact CSV fields CtrlV, ShiftD and AltD.")
                    _rate_block(sub, "Events", a10.abs_total, a10.rate_per_hour, "events/h", 2)
                    _q_lines(sub, a10.q1, a10.q2, a10.q3, a10.q4, "events")
                if a11:
                    sub = _section(b, "Modifier changes", "Modifier use or equivalent row-level changes detected per row.")
                    _rate_block(sub, "Events", a11.abs_total, a11.rate_per_hour, "events/h", 2)
                    _q_lines(sub, a11.q1, a11.q2, a11.q3, a11.q4, "events")

            a12 = _find_stat(csv_name, "A12")
            a13 = _find_stat(csv_name, "A13")
            a16 = _find_stat(csv_name, "A16")
            if a12 or a13 or a16:
                b = _section(
                    details,
                    "Geometry and object changes",
                    "Vertices, mesh errors, and mesh/object changes are separated; each part has its own quartiles.",
                    icon='MESH_DATA',
                )
                if a12:
                    sub = _section(b, "Vertex changes", "Vertex evolution shown as total delta, rate, and quartiles.")
                    _metric_value(sub, "Total delta", a12.abs_total, "vertices", 0)
                    _metric_value(sub, "Rate", a12.rate_per_min, "verts/min", 2)
                    _q_lines(sub, a12.q1, a12.q2, a12.q3, a12.q4, "vertices")
                if a13:
                    sub = _section(b, "Mesh issue changes", "Mesh error evolution separated by registered error type: ngons, triangles, and normals.")
                    _metric_value(sub, "Total errors", a13.abs_total, "errors", 0)
                    _metric_value(sub, "Ngons", getattr(a13, "ngon_error_total", 0.0), "errors", 0)
                    _metric_value(sub, "Triangles", getattr(a13, "tri_error_total", 0.0), "errors", 0)
                    _metric_value(sub, "Normals", getattr(a13, "normal_error_total", 0.0), "errors", 0)
                    _metric_value(sub, "Rate", a13.rate_per_min, "err/min", 2)
                    _q_lines(sub, a13.q1, a13.q2, a13.q3, a13.q4, "errors")
                if a16:
                    sub = _section(b, "Object changes", "Mesh/object change events plus estimated mesh/object count at the end of each quartile.")
                    _metric_value(sub, "Changes", a16.abs_total, "changes", 0)
                    _metric_value(sub, "Rate", a16.rate_per_min, "chg/min", 2)
                    _q_lines(sub, a16.mesh_count_q1, a16.mesh_count_q2, a16.mesh_count_q3, a16.mesh_count_q4, "models")

            a14 = _find_stat(csv_name, "A14")
            a15 = _find_stat(csv_name, "A15")
            if a14 or a15:
                b = _section(
                    details,
                    "Mode and UV work",
                    "Summarizes Object Mode, Edit Mode and UV activity.",
                    icon='INFO',
                )
                if a14:
                    sub = _section(b, "Work mode", "Percentage in Object Mode, Edit Mode, and mode-switch frequency.")
                    total_mode_min = max((a14.time_object + a14.time_edit) / 60, 0.000001)
                    _metric_value(sub, "Object Mode", a14.pct_object, "%", 2)
                    _metric_value(sub, "Edit Mode", a14.pct_edit, "%", 2)
                    _metric_value(sub, "Mode changes", a14.switches / total_mode_min, "chg/min", 2)
                    _label(sub, "Quartiles")
                    for label, obj_pct, edit_pct, changes in (
                        ("Q1", a14.pct_object_q1, a14.pct_edit_q1, a14.mode_switch_q1),
                        ("Q2", a14.pct_object_q2, a14.pct_edit_q2, a14.mode_switch_q2),
                        ("Q3", a14.pct_object_q3, a14.pct_edit_q3, a14.mode_switch_q3),
                        ("Q4", a14.pct_object_q4, a14.pct_edit_q4, a14.mode_switch_q4),
                    ):
                        _label(sub, f"{label}: Object {obj_pct:.1f}%")
                        _label(sub, f"    Edit {edit_pct:.1f}%")
                        _label(sub, f"    Changes {changes:.0f}")
                if a15:
                    sub = _section(b, "UV work", "UV work events calculated as total, rate, and quartiles.")
                    _rate_block(sub, "Events", a15.abs_total, a15.rate_per_min, "events/min", 2)
                    _q_lines(sub, a15.q1, a15.q2, a15.q3, a15.q4, "events")


    def _draw_mesh_tab(self, context, layout, scn):
        # --- 1. CSV Mesh Link ---
        box = layout.box()
        row = box.row(align=True)
        row.prop(scn, "anali_show_mesh_binding", text="", icon='TRIA_DOWN' if scn.anali_show_mesh_binding else 'TRIA_RIGHT', emboss=False)
        row.label(text=tr(scn, "1. CSV ↔ Mesh Link"), icon='MESH_DATA')
        if scn.anali_show_mesh_binding:
            self._info_box(
                context, box,
                [
                    "Link the CSV data to a mesh object.",
                    "The 'Object mesh' is the model being analyzed.",
                    "The 'Reference mesh' is optional: only needed for the Similarity metric. Leave it empty if you do not need a comparison.",
                ],
                icon='INFO',
            )
            box.prop(scn, "anali_target_obj", text=tr(scn, "Object mesh"))
            box.prop(scn, "reference_obj", text=tr(scn, "Reference mesh"))

        # --- 2. Mesh Metrics ---
        box = layout.box()
        row = box.row(align=True)
        row.prop(scn, "anali_show_model_metrics", text="", icon='TRIA_DOWN' if scn.anali_show_model_metrics else 'TRIA_RIGHT', emboss=False)
        row.label(text=tr(scn, "2. Mesh Metrics"), icon='MODIFIER')
        if scn.anali_show_model_metrics:
            box.operator("object.calculate_metrics", text=tr(scn, "Calculate model metrics"))
            # Display metrics for the object chosen in the panel, not for the
            # currently active object in the 3D scene.
            obj = scn.anali_target_obj
            if obj and obj.type == 'MESH':
                metrics_data = scn.get("metrics_data", {})
                if obj.name in metrics_data:
                    inner = box.box()
                    self._label_wrap(context, inner, f"{tr(scn, 'Object mesh')}:  {obj.name}", icon='MESH_DATA')

                    # Definiciones de ayuda contextuales
                    mesh_help = {
                        "UV_area": (
                            "UV area",
                            "Total UV area calculated by triangulating each UV polygon. "
                            "It represents how much of the 0-1 UV space the mesh occupies. "
                            "Values near 1.0 mean the UV layout fills the texture space efficiently.",
                        ),
                        "UV_islands": (
                            "UV islands",
                            "Number of UV islands: groups of UV faces connected by shared UV edges. "
                            "More islands generally means more seams and more draw calls. "
                            "Fewer islands are usually preferred for game assets.",
                        ),
                        "UV_stretch": (
                            "UV stretch",
                            "Average stretch between local 3D edge lengths and UV edge lengths after scaling. "
                            "High stretch (>0.5) indicates areas where the texture will appear distorted. "
                            "Values close to 0 mean uniform UV mapping.",
                        ),
                        "UV_textel_density": (
                            "Texel density",
                            "Global texel density: square root of total UV area divided by total local 3D surface area. "
                            "A uniform density means every face receives a similar number of texture pixels per unit. "
                            "Large differences across meshes in the same scene indicate inconsistent texture resolution.",
                        ),
                        "Normal_percentage": (
                            "Inverted normals (%)",
                            "Percentage of faces whose normal appears inverted according to the local face center test. "
                            "This follows the same criterion used by the data logger for normal changes, adapted to the active mesh. "
                            "A high percentage may indicate flipped or incorrectly oriented faces.",
                        ),
                        "Transformations": (
                            "Transforms applied",
                            "True (1) when the object's world scale is 1.0 and rotation is 0. "
                            "Unapplied transforms can cause unexpected behavior in modifiers, physics, and export. "
                            "Apply all transforms with Ctrl+A before final delivery.",
                        ),
                        "Position": (
                            "At world origin",
                            "True (1) when the object's origin (location) is at world coordinates (0, 0, 0). "
                            "Off-origin objects can cause issues in animations, rigging, and game engines.",
                        ),
                        "Non_quads_percentage": (
                            "Non-quad faces (%)",
                            "Percentage of faces that are NOT quads (4-sided polygons). "
                            "Triangles and n-gons can cause shading artifacts and subdivision problems. "
                            "Target below 5% for clean subdivision-ready topology.",
                        ),
                        "Vertex_duplicate": (
                            "Duplicate vertices (count)",
                            "Number of vertices that would be removed by 'Merge by Distance' at the default threshold (0.0001 units). "
                            "These are overlapping vertices that appear merged visually but are disconnected in the mesh data. "
                            "This metric reports the absolute count of duplicates, not a percentage. "
                            "Use Remove Doubles in Edit Mode to clean them.",
                        ),
                        "Vertex_duplicate_percentage": (
                            "Duplicate vertices (%)",
                            "Percentage of total vertices that are duplicates (see 'Duplicate vertices count' above). "
                            "This is a mesh-quality metric and does not reduce the Similarity score. "
                            "Values above 5% indicate a mesh with many unmerged vertices.",
                        ),
                        "N_faces": (
                            "Face count",
                            "Total number of faces in the mesh. "
                            "Includes triangles, quads, and n-gons. "
                            "High face count combined with a high non-quad percentage is a topology warning sign.",
                        ),
                        "N_meshes": (
                            "Connected parts",
                            "Number of connected components (separate shells) in the mesh. "
                            "A value of 1 means the mesh is a single connected piece. "
                            "Higher values indicate separate parts that may need to be joined or checked.",
                        ),
                        "Face_by_mesh": (
                            "Faces per connected part",
                            "Average number of faces per connected component. "
                            "Very low values (e.g. 1-5) may indicate stray geometry or leftover vertices.",
                        ),
                        "Angle": (
                            "Mean edge angle",
                            "Mean of the smaller dihedral angle between adjacent faces across all shared edges. "
                            "Very low mean angles indicate overly flat geometry; very high values suggest sharp hard-surface topology.",
                        ),
                        "Similarity": (
                            "Similarity vs. reference",
                            "Combined similarity against the reference object. "
                            "Geometric distance uses an octree after an internal centre-of-mass and PCA rotation alignment. "
                            "The alignment is calculated on copied coordinates and never changes visible scene transforms. "
                            "Topological similarity compares vertex, edge, and face counts.",
                        ),
                    }

                    uv_keys = ["UV_area", "UV_islands", "UV_stretch", "UV_textel_density"]
                    normal_keys = ["Normal_percentage"]
                    transform_keys = ["Transformations", "Position"]
                    topo_keys = ["Non_quads_percentage", "Vertex_duplicate", "Vertex_duplicate_percentage",
                                 "N_faces", "N_meshes", "Face_by_mesh", "Angle"]
                    similarity_keys = ["Similarity"]

                    data_dict = metrics_data[obj.name]

                    def _format_mesh_metric(key, value):
                        # Every UV-mapping result is presented with exactly two
                        # decimal places, including island counts, for a
                        # consistent visual format across the whole UV block.
                        if key in uv_keys:
                            try:
                                return f"{float(value):.2f}"
                            except (TypeError, ValueError):
                                return "0.00"
                        return str(value)

                    def _draw_metric_group(parent, title, tooltip, icon, keys):
                        group_keys = [k for k in keys if k in data_dict]
                        if not group_keys:
                            return
                        gb = parent.box()
                        gb.separator(factor=0.2)
                        hrow = gb.row(align=True)
                        hrow.scale_y = 1.1
                        if tooltip:
                            op = hrow.operator("anali.context_help", text=tr(scn, title), icon=icon, emboss=True)
                            op.message = tr(scn, tooltip)
                        else:
                            hrow.label(text=tr(scn, title), icon=icon)
                        gb.separator(factor=0.15)
                        for k in group_keys:
                            label, _help_text = mesh_help.get(k, (k.replace('_', ' '), ""))
                            self._metric_row_wrap(context, gb, label, _format_mesh_metric(k, data_dict[k]))

                    _draw_metric_group(
                        inner, "UV Mapping",
                        "UV_MAPPING_LONG_HELP",
                        'UV', uv_keys,
                    )
                    _draw_metric_group(
                        inner, "Normals",
                        "NORMALS_LONG_HELP",
                        'NORMALS_FACE', normal_keys,
                    )
                    _draw_metric_group(
                        inner, "Transforms & Position",
                        "TRANSFORMS_LONG_HELP",
                        'OBJECT_ORIGIN', transform_keys,
                    )
                    _draw_metric_group(
                        inner, "Topology",
                        "TOPOLOGY_LONG_HELP",
                        'MESH_DATA', topo_keys,
                    )
                    _draw_metric_group(
                        inner, "Similarity",
                        "SIMILARITY_LONG_HELP",
                        'LIBRARY_DATA_DIRECT', similarity_keys,
                    )

                    covered = set(uv_keys + normal_keys + transform_keys + topo_keys + similarity_keys)
                    extra = [k for k in data_dict if k not in covered]
                    for k in extra:
                        label, _help_text = mesh_help.get(k, (k.replace('_', ' '), ""))
                        self._metric_row_wrap(context, inner, label, _format_mesh_metric(k, data_dict[k]))
                else:
                    box.label(text=tr(scn, "Select a mesh and calculate metrics."), icon='INFO')
            else:
                box.label(text=tr(scn, "No active mesh found."), icon='ERROR')

    def _draw_tables_tab(self, context, layout, scn):
        if len(scn.analysis_items) == 0:
            try:
                refresh_analysis_list(None, context)
            except Exception as exc:
                print(f"[tables] Could not initialise metric list: {exc}")
        selected_csv_count = sum(1 for item in scn.csv_items if item.selected)
        selected_metric_count = sum(1 for item in scn.analysis_items if item.enabled)

        box = layout.box()
        row = box.row(align=True)
        row.prop(scn, "anali_show_table_config", text="", icon='TRIA_DOWN' if scn.anali_show_table_config else 'TRIA_RIGHT', emboss=False)
        row.label(text=tr(scn, "1. Table content"), icon='SPREADSHEET')
        if scn.anali_show_table_config:
            status = box.box()
            status.label(text=f"{tr(scn, 'CSV files selected')}: {selected_csv_count}", icon='FILE')
            status.label(text=f"{tr(scn, 'Metrics selected')}: {selected_metric_count}", icon='CHECKMARK')
            if selected_csv_count == 0:
                status.label(text=tr(scn, "Select CSV files in the Data tab"), icon='ERROR')

            box.prop(scn, "anali_table_statistic", text=tr(scn, "Displayed value"))
            box.template_list("ANALI_UL_AnalysisList", "TABLE_METRICS", scn, "analysis_items", scn, "analysis_index", rows=7)

        box = layout.box()
        box.label(text=tr(scn, "2. Layout and pagination"), icon='ALIGN_JUSTIFY')
        row = box.row(align=True)
        row.prop(scn, "anali_table_rows_per_page", text=tr(scn, "Rows"))
        row.prop(scn, "anali_table_cols_per_page", text=tr(scn, "Metrics"))

        nav = box.column(align=True)
        row = nav.row(align=True)
        op = row.operator("anali.table_change_page", text="", icon='TRIA_LEFT')
        op.direction = 'ROW_PREV'
        row.prop(scn, "anali_table_row_page", text=tr(scn, "CSV page"), slider=True)
        op = row.operator("anali.table_change_page", text="", icon='TRIA_RIGHT')
        op.direction = 'ROW_NEXT'

        row = nav.row(align=True)
        op = row.operator("anali.table_change_page", text="", icon='TRIA_LEFT')
        op.direction = 'COL_PREV'
        row.prop(scn, "anali_table_col_page", text=tr(scn, "Metric page"), slider=True)
        op = row.operator("anali.table_change_page", text="", icon='TRIA_RIGHT')
        op.direction = 'COL_NEXT'
        actions = layout.box()
        actions.label(text=tr(scn, "3. Create / Control"), icon='RENDER_STILL')
        row = actions.row(align=True)
        row.scale_y = 1.25
        row.operator("anali.visualize_table", text=tr(scn, "Create 3D table"), icon='SPREADSHEET')
        row = actions.row(align=True)
        row.operator("anali.clear_tables", text=tr(scn, "Clear table"), icon='TRASH')
        row.operator("anali.restore_scene_objects", text=tr(scn, "Restore objects"), icon='HIDE_OFF')

    def _draw_graphs_tab(self, context, layout, scn):
        box = layout.box()
        row = box.row(align=True)
        row.prop(scn, "anali_show_graph_config", text="", icon='TRIA_DOWN' if scn.anali_show_graph_config else 'TRIA_RIGHT', emboss=False)
        title_op = row.operator("anali.context_help", text=tr(scn, "1. Visual Settings"), icon='GRAPH', emboss=True)
        title_op.message = tr(scn, "GRAPH_SETTINGS_LONG_HELP")
        if scn.anali_show_graph_config:
            row = box.row(align=True)
            row.prop(scn, "selected_graph", text=tr(scn, "Graph"))
            box.prop(scn, "anali_color_palette", text=tr(scn, "Color palette"))
            opts = box.row(align=True)
            opts.scale_y = 1.08
            opts.prop(scn, "anali_use_log_scale", text=tr(scn, "Log scale"), toggle=True, icon='IPO_EXPO')
            opts.prop(scn, "anali_use_compact_labels", text=tr(scn, "Compact labels"), toggle=True, icon='FONT_DATA')
            if scn.selected_graph == 'G3':
                radar_box = box.box()
                radar_box.prop(scn, "anali_radar_margin", text=tr(scn, "Radar margin"), slider=True)
                radar_box.label(text=tr(scn, "Per-metric min-max normalization"), icon='IPO_EASE_IN_OUT')
            if scn.selected_graph == 'G1':
                window = box.box()
                window.label(text=tr(scn, "G1 data window"), icon='PREVIEW_RANGE')
                nav = window.row(align=True)
                prev_op = nav.operator("anali.g1_change_window", text="", icon='TRIA_LEFT')
                prev_op.direction = 'PREV'
                start = max(0, int(scn.anali_g1_window_start))
                size = max(1, int(scn.anali_g1_window_size))
                is_global = bool(getattr(scn, "anali_g1_global_view", True))
                nav.label(text=tr(scn, "Global") if is_global else f"{start + 1}–{start + size}", icon='WORLD' if is_global else 'PREVIEW_RANGE')
                next_op = nav.operator("anali.g1_change_window", text="", icon='TRIA_RIGHT')
                next_op.direction = 'NEXT'
                window.label(text=tr(scn, "Display"))
                mode_row = window.row(align=True)
                mode_row.prop_enum(scn, "anali_g1_display_mode", 'BANDS', text=tr(scn, "Bands"))
                mode_row.prop_enum(scn, "anali_g1_display_mode", 'OVERLAY', text=tr(scn, "Overlay"))
                window.prop(scn, "anali_g1_window_size", text=tr(scn, "Rows per window"))
            self._label_wrap(context, box, tr(scn, "Select metrics"), icon='CHECKMARK')
            box.template_list("ANALI_UL_AnalysisList", "", scn, "analysis_items", scn, "analysis_index")
        box = layout.box()
        row = box.row(align=True)
        row.prop(scn, "anali_show_render_controls", text="", icon='TRIA_DOWN' if scn.anali_show_render_controls else 'TRIA_RIGHT', emboss=False)
        title_op = row.operator("anali.context_help", text=tr(scn, "2. Render / Control"), icon='RENDER_STILL', emboss=True)
        title_op.message = tr(scn, "RENDER_CONTROLS_LONG_HELP")
        if scn.anali_show_render_controls:
            row = box.row(align=True)
            row.prop(scn, "axis_scale_x", text=tr(scn, "Scale X"))
            row.prop(scn, "axis_scale_y", text=tr(scn, "Scale Y"))
            row.prop(scn, "axis_scale_z", text=tr(scn, "Scale Z"))
            row = box.row(align=True)
            row.operator("anali.clear_graphs", text=tr(scn, "Clear graphs"))
            row.operator("anali.restore_scene_objects", text=tr(scn, "Restore objects"))
            row = box.row(align=True)
            row.operator("anali.visualize_graph", text=tr(scn, "Visualize 3D graph"))
