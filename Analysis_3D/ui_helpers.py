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
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from mathutils import Vector

try:
    from .utils import (
        detect_csvs,
        read_csv,
        count_uv_islands,
        calculate_topology_similarity,
        calculate_similarity,
        calculate_uv_texel_density,
        calculate_normal_percentage,
        calculate_angle_median,
        object_has_applied_transforms,
        object_is_at_origin,
        calculate_model_metrics,
    )
    from .constants import DEFAULT_BREAK_SPEED, DEFAULT_MAX_REASONABLE_SPEED
    from .analytics import ANALYSIS, compute_metrics_for_csv, series_to_array, clamp_outliers, sanitize_name, _row_time, _row_object_local_size, _csv_float
    from .graphs import (
        clear_previous_graphs,
        clear_axes_objects,
        get_color_for_csv,
        csv_color_by_index,
        metric_color_for_csv,
        draw_axes1,
        create_plane_with_image_memory,
        draw_correlation_graph_fast,
        create_scatter_points_fast,
        create_time_graph,
        draw_forest_plot_3d,
        draw_multi_csv_forest_plot_3d,
        draw_surface_graph,
        draw_multi_csv_surface_graph,
        create_interaction_graph_3d,
        draw_radar_graph_3d_filled,
        draw_csv_color_legend,
    )
except ImportError:
    from utils import (
        detect_csvs,
        read_csv,
        count_uv_islands,
        calculate_topology_similarity,
        calculate_similarity,
        calculate_uv_texel_density,
        calculate_normal_percentage,
        calculate_angle_median,
        object_has_applied_transforms,
        object_is_at_origin,
        calculate_model_metrics,
    )
    from constants import DEFAULT_BREAK_SPEED, DEFAULT_MAX_REASONABLE_SPEED
    from analytics import ANALYSIS, compute_metrics_for_csv, series_to_array, clamp_outliers, sanitize_name, _row_time, _row_object_local_size, _csv_float
    from graphs import (
        clear_previous_graphs,
        clear_axes_objects,
        get_color_for_csv,
        csv_color_by_index,
        metric_color_for_csv,
        draw_axes1,
        create_plane_with_image_memory,
        draw_correlation_graph_fast,
        create_scatter_points_fast,
        create_time_graph,
        draw_forest_plot_3d,
        draw_multi_csv_forest_plot_3d,
        draw_surface_graph,
        draw_multi_csv_surface_graph,
        create_interaction_graph_3d,
        draw_radar_graph_3d_filled,
        draw_csv_color_legend,
    )

try:
    from .ui_graph_rendering import (
        _figure_to_blender_image,
        create_matplotlib_graph,
        create_comparative_interaction_matplotlib,
    )
except ImportError:
    from ui_graph_rendering import (
        _figure_to_blender_image,
        create_matplotlib_graph,
        create_comparative_interaction_matplotlib,
    )
GRAPH_TYPES = {
    "G1": {"label": "Interaction (experimental)", "roles": {"Y": 1}, "allow_mix": True, "compatible_typologies": ["Temporal", "Spatial", "Strategy"]},
    "G2": {"label": "Forest plot (experimental)", "roles": {"Y": 1}, "allow_mix": False, "compatible_typologies": ["Temporal", "Spatial", "Strategy"], "requires_multi_csv": True},
    "G3": {"label": "Radar plot (experimental)", "roles": {"Y": 3}, "allow_mix": False, "compatible_typologies": ["Temporal", "Spatial", "Strategy"], "requires_multi_csv": True},
}

# Helpers

def _clean_vals(values):
    if values is None:
        return []
    out = []
    for v in values:
        try:
            out.append(float(v))
        except (ValueError, TypeError) as exc:
            print(f"[_clean_vals] Valor descartado: {exc}")
    return out


def _safe_mean(values):
    vals = _clean_vals(values)
    return float(np.mean(vals)) if vals else 0.0


def _safe_std(values):
    vals = _clean_vals(values)
    return float(np.std(vals)) if vals else 0.0


def _safe_min(values):
    vals = _clean_vals(values)
    return float(np.min(vals)) if vals else 0.0


def _safe_max(values):
    vals = _clean_vals(values)
    return float(np.max(vals)) if vals else 0.0


def _safe_sum(values):
    vals = _clean_vals(values)
    return float(np.sum(vals)) if vals else 0.0


def _safe_last(values):
    vals = _clean_vals(values)
    return float(vals[-1]) if vals else 0.0


def _safe_weighted_mean(values):
    vals = _clean_vals(values)
    if not vals:
        return 0.0
    weights = np.arange(1, len(vals) + 1, dtype=float)
    return float(np.average(vals, weights=weights))


def _rate_per_min(values, total_time):
    total = _safe_sum(values)
    if total_time <= 0:
        return 0.0
    return float(total / (total_time / 60.0))


def _delta_total(values):
    vals = _clean_vals(values)
    if len(vals) < 2:
        return 0.0
    return float(vals[-1] - vals[0])


def _delta_per_sec(values, total_time):
    if total_time <= 0:
        return 0.0
    return float(_delta_total(values) / total_time)


def _quartile_means(values):
    vals = _clean_vals(values)
    if not vals:
        return (0.0, 0.0, 0.0, 0.0)

    n = len(vals)
    q = max(1, int(np.ceil(n / 4.0)))
    chunks = [
        vals[0:q],
        vals[q:2*q],
        vals[2*q:3*q],
        vals[3*q:]
    ]

    while len(chunks) < 4:
        chunks.append([])

    return tuple(float(np.mean(c)) if c else 0.0 for c in chunks[:4])


def _quartile_sums(values):
    vals = _clean_vals(values)
    if not vals:
        return (0.0, 0.0, 0.0, 0.0)

    n = len(vals)
    q = max(1, int(np.ceil(n / 4.0)))
    chunks = [
        vals[0:q],
        vals[q:2*q],
        vals[2*q:3*q],
        vals[3*q:]
    ]

    while len(chunks) < 4:
        chunks.append([])

    return tuple(float(np.sum(c)) if c else 0.0 for c in chunks[:4])


def _quartile_last_values(values):
    vals = _clean_vals(values)
    if not vals:
        return (0.0, 0.0, 0.0, 0.0)
    n = len(vals)
    q = max(1, int(np.ceil(n / 4.0)))
    chunks = [vals[0:q], vals[q:2*q], vals[2*q:3*q], vals[3*q:]]
    while len(chunks) < 4:
        chunks.append([])
    last = vals[0]
    out = []
    for chunk in chunks[:4]:
        if chunk:
            last = chunk[-1]
        out.append(float(last))
    return tuple(out)


def _row_mesh_count(row, running_count):
    keys = (
        "MeshCount", "Meshes", "NMeshes", "ObjectCount", "Objects",
        "ModelCount", "Models", "Mallas", "NumMeshes", "NumObjects"
    )
    for key in keys:
        value = _csv_float(row, key, default=None)
        if value is not None:
            return max(float(value), 0.0)
    return running_count


def _mesh_count_series(data, object_deltas):
    counts = []
    running = 0.0
    for i, row in enumerate(data or []):
        explicit = _row_mesh_count(row, None)
        if explicit is not None:
            running = explicit
        else:
            delta = object_deltas[i] if i < len(object_deltas) else 0.0
            running = max(running + float(delta), 0.0)
        counts.append(running)
    return counts
        
# CLASE: OBJECT_OT_CalculateMetrics

def summarise_series(values):
    arr = series_to_array(values)
    if arr.size == 0:
        return {"count": 0, "min": 0.0, "max": 0.0, "mean": 0.0, "last": 0.0}
    return {
        "count": int(arr.size),
        "min": round(float(np.min(arr)), 4),
        "max": round(float(np.max(arr)), 4),
        "mean": round(float(np.mean(arr)), 4),
        "last": round(float(arr[-1]), 4),
    }

def validate_selection(context):
    scn = context.scene
    graph = GRAPH_TYPES[scn.selected_graph]
    selected = [item for item in scn.analysis_items if item.enabled]
    if not selected:
        return False, "No variables selected"
    for role, count in graph["roles"].items():
        role_items = [item for item in selected if item.role == role]
        if len(role_items) < count:
            return False, f"{graph['label']} requires at least {count} selected metric(s)"
    return True, "OK"


def refresh_analysis_list(self, context):
    scn = getattr(context, "scene", None)
    if scn is None:
        return
    previous = {item.key: {"enabled": item.enabled, "role": item.role} for item in scn.analysis_items}
    scn.analysis_items.clear()
    graph = GRAPH_TYPES[scn.selected_graph]
    for aid, info in ANALYSIS.items():
        if info["typology"] in graph["compatible_typologies"]:
            item = scn.analysis_items.add()
            item.key = aid
            item.label = info["label"]
            item.typology = info["typology"]
            item.enabled = previous.get(aid, {}).get("enabled", False)
            item.role = 'Y'


def update_csv_analysis_store(scene):
    csv_store = {}
    for item in scene.csv_items:
        if not item.selected:
            continue
        try:
            _, data = read_csv(item.name)
            metrics = compute_metrics_for_csv(data, max_reasonable_speed=getattr(scene, "max_reasonable_speed", DEFAULT_MAX_REASONABLE_SPEED))
            key = os.path.basename(item.name)
            csv_store[key] = metrics
        except Exception as exc:
            print(f"[update_csv_analysis_store] {item.name}: {exc}")
    scene["csv_metrics_data"] = csv_store
    if "csv_summary_data" in scene:
        del scene["csv_summary_data"]


def get_or_create_graph_scene(csv_name):
    """Use the current scene so graph generation does not reset the add-on state.

    Generated graph objects are removed with clear_previous_graphs(), which only
    targets add-on object prefixes and leaves user meshes in the scene.
    """
    return bpy.context.scene


def switch_to_scene(scene):
    return None


def hide_non_graph_objects(scene):
    """Hide user objects while a graph is being inspected.

    This avoids the startup cube / imported meshes from sitting behind the graph.
    Objects are hidden, not deleted, so the modelling scene is preserved.
    """
    prefixes = (
        "GraphPlane_", "GraphLineMesh_", "Scatter_", "Corr_", "Surface_", "Time_",
        "Forest", "Radar", "Axis_", "Tick_", "Label_", "TickLabel_", "Num_",
        "InteractionBar_", "InteractionLine_", "InteractionPts_", "InteractionLabel_", "TimePts_",
        "DataTable", "TableGrid_", "TableText_", "TableTitle_", "TableSubtitle_"
    )
    for obj in scene.objects:
        if obj.name.startswith(prefixes):
            obj.hide_set(False)
            obj.hide_viewport = False
            continue
        if obj.type in {'LIGHT', 'CAMERA'}:
            continue
        obj.hide_set(True)
        obj.hide_viewport = True


def hide_viewport_guides(context=None):
    """Hide Blender floor grid, world axes and 3D cursor in every 3D View."""
    ctx = context or bpy.context
    window_manager = getattr(ctx, "window_manager", None)
    windows = list(getattr(window_manager, "windows", []) or [])
    if not windows:
        screen = getattr(ctx, "screen", None)
        screens = [screen] if screen is not None else []
    else:
        screens = [getattr(window, "screen", None) for window in windows]

    seen = set()
    for screen in screens:
        if screen is None or id(screen) in seen:
            continue
        seen.add(id(screen))
        for area in screen.areas:
            if area.type != 'VIEW_3D':
                continue
            space = area.spaces.active
            overlay = getattr(space, 'overlay', None)
            if overlay is None:
                continue
            overlay.show_overlays = True
            overlay.show_floor = False
            overlay.show_axis_x = False
            overlay.show_axis_y = False
            overlay.show_axis_z = False
            overlay.show_cursor = False
            if hasattr(overlay, 'show_ortho_grid'):
                overlay.show_ortho_grid = False


def restore_hidden_scene_objects(scene, context=None):
    """Show hidden objects and restore Blender viewport guides.

    Graph visualization can hide the floor grid, world axes and 3D cursor to
    reduce visual noise. Restoring the scene must return those viewport aids as
    well, in every open 3D View rather than only in the currently active area.
    """
    for obj in scene.objects:
        obj.hide_set(False)
        obj.hide_viewport = False

    ctx = context or bpy.context
    window_manager = getattr(ctx, "window_manager", None)
    windows = list(getattr(window_manager, "windows", []) or [])

    # Fallback for unusual contexts without a WindowManager window list.
    if not windows:
        screen = getattr(ctx, "screen", None)
        screens = [screen] if screen is not None else []
    else:
        screens = [getattr(window, "screen", None) for window in windows]

    seen = set()
    for screen in screens:
        if screen is None or id(screen) in seen:
            continue
        seen.add(id(screen))
        for area in screen.areas:
            if area.type != 'VIEW_3D':
                continue
            space = area.spaces.active
            overlay = getattr(space, 'overlay', None)
            if overlay is None:
                continue
            overlay.show_overlays = True
            overlay.show_floor = True
            overlay.show_axis_x = True
            overlay.show_axis_y = True
            overlay.show_axis_z = True
            overlay.show_cursor = True
            # These improve parity with Blender's default viewport presentation.
            if hasattr(overlay, 'show_ortho_grid'):
                overlay.show_ortho_grid = True
            if hasattr(overlay, 'show_text'):
                overlay.show_text = True


def frame_graph_camera(scene, scn):
    """Centra el viewport en vista superior ortográfica sin crear cámaras."""
    bpy.context.view_layer.update()
    prefixes = (
        "GraphPlane_", "GraphLineMesh_", "Scatter_", "Corr_", "Surface_", "Time_",
        "Forest", "Radar", "Axis_", "Tick_", "Label_", "TickLabel_", "Num_",
        "InteractionBar_", "InteractionLine_", "InteractionPts_", "InteractionLabel_", "TimePts_",
        "DataTable", "TableGrid_", "TableText_", "TableTitle_", "TableSubtitle_"
    )

    coords = []
    for obj in scene.objects:
        if not obj.name.startswith(prefixes):
            continue
        try:
            for corner in obj.bound_box:
                coords.append(obj.matrix_world @ Vector(corner))
        except Exception:
            coords.append(obj.location.copy())

    if coords:
        min_x = min(v.x for v in coords); max_x = max(v.x for v in coords)
        min_y = min(v.y for v in coords); max_y = max(v.y for v in coords)
        min_z = min(v.z for v in coords); max_z = max(v.z for v in coords)
    else:
        min_x, min_y, min_z = 0.0, 0.0, 0.0
        max_x, max_y, max_z = float(scn.axis_scale_x), float(scn.axis_scale_y), float(scn.axis_scale_z)

    center = Vector(((min_x + max_x) / 2.0, (min_y + max_y) / 2.0, (min_z + max_z) / 2.0))
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    depth = max(max_z - min_z, 1.0)
    ortho_scale = max(width, height) * 1.25
    camera_height = max_z + max(width, height, depth, float(scn.axis_scale_z), 1.0) * 2.0 + 5.0


    # Ajusta también la vista activa de los Viewports 3D para que al visualizar se vea desde arriba.
    screen = getattr(bpy.context, "screen", None)
    if screen:
        for area in screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for space in area.spaces:
                if space.type == 'VIEW_3D' and space.region_3d:
                    space.region_3d.view_perspective = 'ORTHO'
                    space.region_3d.view_location = center
                    space.region_3d.view_rotation = (1.0, 0.0, 0.0, 0.0)
                    space.region_3d.view_distance = max(width, height, depth) * 1.5 + 1.0


def draw_axes_for_graph(scn, labels, graph_data=None, z_range=None):
    clear_axes_objects(bpy.context.scene)
    graph_data = graph_data or {
        "x_range": (0.0, 1.0),
        "y_range": (0.0, 1.0),
        "x_ticks": [0.0, 0.25, 0.5, 0.75, 1.0],
        "y_ticks": [0.0, 0.25, 0.5, 0.75, 1.0],
    }
    labels = list(labels[:3]) if labels else ["X", "Y", "Z"]
    while len(labels) < 3:
        labels.append(["X", "Y", "Z"][len(labels)])
    draw_axes1(
        length_x=scn.axis_scale_x,
        length_y=scn.axis_scale_y,
        length_z=scn.axis_scale_z,
        labels=labels,
        x_range=graph_data.get("x_range", (0, 1)),
        y_range=graph_data.get("y_range", (0, 1)),
        z_range=z_range or (0, scn.axis_scale_z),
        x_ticks=graph_data.get("x_ticks"),
        y_ticks=graph_data.get("y_ticks"),
        z_ticks=[0, scn.axis_scale_z] if labels[2] else [],
        tick_size=0.12,
        text_size=0.30,
    )

def update_scene_metric_stats(context):
    scn = context.scene
    scn.metric_stats.clear()

    selected_csvs = [item.name for item in scn.csv_items if item.selected]

    for csv_path in selected_csvs:
        try:
            _, data = read_csv(csv_path)
            metrics = compute_metrics_for_csv(data, max_reasonable_speed=getattr(context.scene, "max_reasonable_speed", DEFAULT_MAX_REASONABLE_SPEED))
        except Exception as exc:
            print(f"[update_scene_metric_stats] {csv_path}: {exc}")
            continue

        csv_name = os.path.basename(csv_path)

        times_abs = [_row_time(row) for row in data] if data else []
        raw_duration = max(times_abs[-1] - times_abs[0], 0.0) if len(times_abs) > 1 else 0.0
        a1_vals = _clean_vals(metrics.get("A1", []))
        total_time_hour = _safe_last(a1_vals) if a1_vals else 0.0
        total_time_min = total_time_hour * 60.0
        total_time_sec = total_time_hour * 3600.0
        object_local_sizes = [_row_object_local_size(row) for row in data] if data else []
        object_local_size_mean = _safe_mean([v for v in object_local_sizes if v > 0.0])
        speed_values = _clean_vals(metrics.get("A4", []))
        peak_flags = _clean_vals(metrics.get("A6", []))
        peak_speeds = [speed_values[i] for i, flag in enumerate(peak_flags) if i < len(speed_values) and abs(flag) > 0.0]
        peak_speed_mean = _safe_mean(peak_speeds) if peak_speeds else _safe_mean(speed_values)
        ngon_errors = [abs(_csv_float(row, "NgonDelta", "NGonDelta", "NgonsDelta", default=0.0)) for row in data]
        tri_errors = [abs(_csv_float(row, "TriDelta", "TriangleDelta", "TrianglesDelta", default=0.0)) for row in data]
        normal_errors = [abs(_csv_float(row, "NormalDelta", "NormalsDelta", default=0.0)) for row in data]
        object_deltas = _clean_vals(metrics.get("A16", []))
        mesh_counts = _mesh_count_series(data, object_deltas)

        for key, values in metrics.items():
            vals = _clean_vals(values)
            abs_vals = [abs(v) for v in vals]

            st = scn.metric_stats.add()
            st.csv_name = csv_name
            st.key = key
            st.label = ANALYSIS.get(key, {}).get("label", key)
            st.object_local_size = object_local_size_mean
            st.peak_speed_mean = peak_speed_mean
            if key == "A13":
                st.ngon_error_total = _safe_sum(ngon_errors)
                st.tri_error_total = _safe_sum(tri_errors)
                st.normal_error_total = _safe_sum(normal_errors)
            if key == "A16":
                st.mesh_count_q1, st.mesh_count_q2, st.mesh_count_q3, st.mesh_count_q4 = _quartile_last_values(mesh_counts)

            st.value = _safe_mean(vals)
            st.mean = _safe_mean(vals)
            st.weighted_mean = _safe_weighted_mean(vals)
            st.std = _safe_std(vals)
            st.min = _safe_min(vals)
            st.max = _safe_max(vals)

            st.total = _safe_sum(vals)
            st.abs_total = _safe_sum(abs_vals)

            event_count = float(sum(1 for v in abs_vals if v > 0.0))

            st.count = event_count

            # Métricas de events discretos
            if key in {"A2", "A3", "A6", "A7", "A8", "A9", "A10", "A11", "A15"}:
                st.rate_per_min = event_count / total_time_min if total_time_min > 0 else 0.0
                st.rate_per_hour = event_count / total_time_hour if total_time_hour > 0 else 0.0

            # Métricas acumulativas/intensidad
            else:
                st.rate_per_min = st.abs_total / total_time_min if total_time_min > 0 else 0.0
                st.rate_per_hour = st.abs_total / total_time_hour if total_time_hour > 0 else 0.0

            st.delta_total = _delta_total(vals)
            st.delta_per_sec = _delta_per_sec(vals, total_time_sec)

            if key in {"A2", "A3", "A6", "A7", "A8", "A9"}:
                event_vals = [1.0 if abs(v) > 0.0 else 0.0 for v in vals]
                st.q1, st.q2, st.q3, st.q4 = _quartile_sums(event_vals)
            else:
                st.q1, st.q2, st.q3, st.q4 = _quartile_sums(abs_vals)

            if key == "A1":
                st.total = _safe_last(vals)
                st.rate_per_min = 0.0
                st.rate_per_hour = 0.0

            if key == "A14" and data:
                mode_vals = vals
                time_object = 0.0
                time_edit = 0.0
                switches = 0.0
                q_object = [0.0, 0.0, 0.0, 0.0]
                q_edit = [0.0, 0.0, 0.0, 0.0]
                q_switches = [0.0, 0.0, 0.0, 0.0]

                scale = (total_time_sec / raw_duration) if raw_duration > 0 and total_time_sec > 0 else 0.0
                first_time = times_abs[0] if times_abs else 0.0

                for i in range(len(data) - 1):
                    dt_raw = max(times_abs[i + 1] - times_abs[i], 0.0)
                    dt = dt_raw * scale if scale > 0 else 0.0
                    start_scaled = max((times_abs[i] - first_time) * scale, 0.0) if scale > 0 else 0.0
                    mid_scaled = start_scaled + dt * 0.5
                    if total_time_sec > 0:
                        q_idx = min(max(int((mid_scaled / total_time_sec) * 4.0), 0), 3)
                    else:
                        q_idx = min(i * 4 // max(len(data) - 1, 1), 3)

                    mode = mode_vals[i] if i < len(mode_vals) else 0.0

                    if mode == 1.0:
                        time_object += dt
                        q_object[q_idx] += dt
                    elif mode == 2.0:
                        time_edit += dt
                        q_edit[q_idx] += dt

                    next_mode = mode_vals[i + 1] if i + 1 < len(mode_vals) else mode
                    if next_mode != mode:
                        switches += 1.0
                        end_scaled = start_scaled + dt
                        if total_time_sec > 0:
                            switch_q = min(max(int((end_scaled / total_time_sec) * 4.0), 0), 3)
                        else:
                            switch_q = q_idx
                        q_switches[switch_q] += 1.0

                q_totals = [max(q_object[i] + q_edit[i], 1e-9) for i in range(4)]
                q_obj_pct = [(q_object[i] / q_totals[i]) * 100.0 if q_totals[i] > 0 else 0.0 for i in range(4)]
                q_edit_pct = [(q_edit[i] / q_totals[i]) * 100.0 if q_totals[i] > 0 else 0.0 for i in range(4)]

                st.time_object = time_object
                st.time_edit = time_edit
                st.pct_object = time_object / total_time_sec * 100.0 if total_time_sec > 0 else 0.0
                st.pct_edit = time_edit / total_time_sec * 100.0 if total_time_sec > 0 else 0.0
                st.switches = switches
                st.pct_object_q1, st.pct_object_q2, st.pct_object_q3, st.pct_object_q4 = q_obj_pct
                st.pct_edit_q1, st.pct_edit_q2, st.pct_edit_q3, st.pct_edit_q4 = q_edit_pct
                st.mode_switch_q1, st.mode_switch_q2, st.mode_switch_q3, st.mode_switch_q4 = q_switches
                # Keep q1-q4 meaningful for generic displays: they now hold mode switches per quartile.
                st.q1, st.q2, st.q3, st.q4 = q_switches
   
def radar_summary_value(metric_key, values):
    vals = series_to_array(values)
    if vals.size == 0:
        return None

    if metric_key == "A1":
        return float(vals[-1])

    if metric_key in {"A2", "A3", "A6", "A7", "A8", "A9"}:
        return float(np.sum(vals > 0.0))

    if metric_key in {"A10", "A11", "A12", "A13", "A15", "A16"}:
        return float(np.sum(np.abs(vals)))

    if metric_key == "A14":
        return float(np.mean(vals))

    return float(np.mean(vals))
             
# Properties and Operators

def radar_summary_value(metric_key, values):
    vals = series_to_array(values)
    if vals.size == 0:
        return None, ""

    if metric_key == "A1":
        return float(vals[-1]), "h"

    if metric_key in {"A2", "A3"}:
        return float(np.sum(vals > 0.0)), "stops"

    if metric_key == "A4":
        return float(np.mean(vals)), "m/h"

    if metric_key == "A5":
        return float(np.mean(vals)), "m"

    if metric_key in {"A6", "A7", "A8", "A9"}:
        return float(np.sum(vals > 0.0)), "peaks"

    if metric_key in {"A10", "A11", "A12", "A13", "A15", "A16"}:
        return float(np.sum(np.abs(vals))), "events"

    if metric_key == "A14":
        return float(np.mean(vals)), "mode"

    return float(np.mean(vals)), "units"

def normalize_radar_values(raw_values):
    if not raw_values:
        return []

    vals = np.asarray(raw_values, dtype=float)
    vals = np.nan_to_num(vals, nan=0.0, posinf=0.0, neginf=0.0)

    min_v = float(np.min(vals))
    max_v = float(np.max(vals))
    rng = max(max_v - min_v, 1e-9)

    return [0.05 + 0.95 * ((float(v) - min_v) / rng) for v in vals]


def _signed_log10_1p(values):
    """Compress numeric values while preserving sign and zeros."""
    arr = np.asarray(values, dtype=float)
    return np.sign(arr) * np.log10(1.0 + np.abs(arr))


def _forest_t_critical_95(df):
    """Two-sided 95% Student-t critical value without requiring SciPy."""
    df = max(int(df), 1)
    table = {
        1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
        6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
        16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
        21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
        26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
        40: 2.021, 60: 2.000, 120: 1.980,
    }
    if df in table:
        return table[df]
    if df > 120:
        return 1.960
    keys = sorted(table)
    lo = max(k for k in keys if k < df)
    hi = min(k for k in keys if k > df)
    fraction = (df - lo) / float(hi - lo)
    return table[lo] + fraction * (table[hi] - table[lo])


def forest_row_stats(metric_key, metrics, csv_name, use_log_scale=False):
    """Summarise one CSV series as a mean with a two-sided 95% t interval.

    The returned standard error is used by the comparative forest plot for a
    random-effects meta-analysis. On the optional transformed view, all
    calculations are explicitly performed on signed log10(1+|x|) values.
    """
    values = series_to_array(metrics.get(metric_key, []))
    values = values[np.isfinite(values)]
    if values.size == 0:
        return None

    original_values = values.copy()
    if use_log_scale:
        values = _signed_log10_1p(values)

    n = int(values.size)
    mean = float(np.mean(values))
    if n > 1:
        std = float(np.std(values, ddof=1))
        se = std / float(np.sqrt(n))
        critical = _forest_t_critical_95(n - 1)
        ci = critical * se
    else:
        std = 0.0
        se = float("nan")
        ci = 0.0

    return {
        "csv_name": csv_name,
        "mean": mean,
        "ci_low": mean - ci,
        "ci_high": mean + ci,
        "n": n,
        "std": std,
        "se": se,
        "scale": "signed log10(1+|x|)" if use_log_scale else "linear",
        "raw_mean": float(np.mean(original_values)),
    }


def forest_paired_difference_stats(reference_key, comparison_key, metrics, csv_name, use_log_scale=False):
    """Paired mean difference (comparison - reference) with a 95% t CI.

    Values are paired by row index. Only rows where both metrics are finite are
    retained. This is the correct within-user contrast when both metrics were
    recorded on the same observations/trials.
    """
    ref = series_to_array(metrics.get(reference_key, []))
    cmp = series_to_array(metrics.get(comparison_key, []))
    n_common = min(ref.size, cmp.size)
    if n_common <= 0:
        return None
    ref = np.asarray(ref[:n_common], dtype=float)
    cmp = np.asarray(cmp[:n_common], dtype=float)
    valid = np.isfinite(ref) & np.isfinite(cmp)
    ref = ref[valid]
    cmp = cmp[valid]
    if ref.size < 2:
        return None
    if use_log_scale:
        ref = _signed_log10_1p(ref)
        cmp = _signed_log10_1p(cmp)
    differences = cmp - ref
    n = int(differences.size)
    mean = float(np.mean(differences))
    std = float(np.std(differences, ddof=1))
    se = std / float(np.sqrt(n))
    critical = _forest_t_critical_95(n - 1)
    ci = critical * se
    return {
        "csv_name": csv_name,
        "mean": mean,
        "ci_low": mean - ci,
        "ci_high": mean + ci,
        "n": n,
        "std": std,
        "se": se,
        "scale": "paired signed-log difference" if use_log_scale else "paired difference",
    }


def forest_zscore_reference(metric_key, metrics_by_csv):
    """Return the reference distribution of user-level means for one metric.

    Every CSV/user contributes one mean, regardless of how many observations it
    contains. Standardising user means (rather than pooling every raw sample)
    prevents long sessions from dominating the reference and avoids shrinking
    all displayed effects towards zero.
    """
    user_means = []
    user_ns = []
    for metrics in metrics_by_csv:
        values = series_to_array(metrics.get(metric_key, []))
        values = values[np.isfinite(values)]
        if values.size:
            user_means.append(float(np.mean(values)))
            user_ns.append(int(values.size))
    if len(user_means) < 2:
        return None
    means = np.asarray(user_means, dtype=float)
    mean = float(np.mean(means))
    std = float(np.std(means, ddof=1))
    if not np.isfinite(std) or std <= 1e-12:
        return None
    return {
        "metric_key": metric_key,
        "mean": mean,
        "std": std,
        "n_total": int(len(user_means)),
        "observation_count": int(sum(user_ns)),
    }


def forest_zscore_row_stats(metric_key, metrics, csv_name, reference_mean, reference_std):
    """Return a descriptive user-mean z-score with autocorrelation-adjusted CI.

    Consecutive interaction samples are usually serially correlated. Treating
    every CSV row as independent would make confidence intervals unrealistically
    narrow. We therefore estimate a lag-1 effective sample size and use it for
    the standard error and Student-t degrees of freedom. This remains a
    descriptive approximation, not proof that the raw metric is normally
    distributed.
    """
    values = series_to_array(metrics.get(metric_key, []))
    values = values[np.isfinite(values)]
    if values.size < 3:
        return None
    if not np.isfinite(reference_std) or abs(float(reference_std)) <= 1e-12:
        return None

    n_raw = int(values.size)
    raw_mean = float(np.mean(values))
    raw_std = float(np.std(values, ddof=1))
    if not np.isfinite(raw_std) or raw_std <= 1e-15:
        return None

    # Lag-1 autocorrelation. Clamp negative correlation to zero so that the
    # effective sample size never exceeds the observed number of rows.
    x0 = values[:-1] - float(np.mean(values[:-1]))
    x1 = values[1:] - float(np.mean(values[1:]))
    denom = float(np.sqrt(np.sum(x0 * x0) * np.sum(x1 * x1)))
    rho1 = float(np.sum(x0 * x1) / denom) if denom > 1e-15 else 0.0
    rho1 = min(max(rho1, 0.0), 0.99)
    n_eff = float(n_raw * (1.0 - rho1) / (1.0 + rho1))
    n_eff = min(float(n_raw), max(2.0, n_eff))

    raw_se = raw_std / float(np.sqrt(n_eff))
    mean = (raw_mean - float(reference_mean)) / float(reference_std)
    se = raw_se / float(reference_std)
    if not np.isfinite(se) or se <= 0.0:
        return None

    df_eff = max(1, int(np.floor(n_eff)) - 1)
    critical = _forest_t_critical_95(df_eff)
    ci = critical * se
    return {
        "csv_name": csv_name,
        "mean": float(mean),
        "ci_low": float(mean - ci),
        "ci_high": float(mean + ci),
        "n": n_raw,
        "n_eff": n_eff,
        "rho1": rho1,
        "std": float(raw_std / reference_std),
        "se": float(se),
        "scale": "descriptive z-score of user mean",
        "raw_mean": raw_mean,
        "raw_std": raw_std,
        "reference_mean": float(reference_mean),
        "reference_std": float(reference_std),
    }
