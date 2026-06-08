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
    from .analytics import (
        ANALYSIS,
        compute_metrics_for_csv,
        series_to_array,
        clamp_outliers,
        sanitize_name,
    )
    from .constants import DEFAULT_MAX_REASONABLE_SPEED
    from .graphs import (
        clear_previous_graphs,
        csv_color_by_index,
        metric_color_for_csv,
        create_text_label,
        create_interaction_graph_3d,
        draw_forest_plot_3d,
        draw_multi_csv_forest_plot_3d,
        draw_radar_graph_3d_filled,
        draw_csv_color_legend,
    )
    from .utils import read_csv
except ImportError:
    from ui_helpers import *
    from ui_properties import *
    from analytics import (
        ANALYSIS,
        compute_metrics_for_csv,
        series_to_array,
        clamp_outliers,
        sanitize_name,
    )
    from constants import DEFAULT_MAX_REASONABLE_SPEED
    from graphs import (
        clear_previous_graphs,
        csv_color_by_index,
        metric_color_for_csv,
        create_text_label,
        create_interaction_graph_3d,
        draw_forest_plot_3d,
        draw_multi_csv_forest_plot_3d,
        draw_radar_graph_3d_filled,
        draw_csv_color_legend,
    )
    from utils import read_csv


def _signed_log10_1p(values):
    """Signed log10(1+x) transform used by graph rendering.

    Defined locally because wildcard imports intentionally do not bring private
    helpers from ui_helpers into this module.
    """
    arr = np.asarray(values, dtype=float)
    return np.sign(arr) * np.log10(1.0 + np.abs(arr))


def visualize_graph(context, report):
    """Build the selected graph from the current Blender scene state.

    This controller function keeps the Blender operator thin: the operator only
    delegates here, while graph orchestration lives outside the UI class.
    """
    scn = context.scene

    ok, msg = validate_selection(context)
    if not ok:
        report({'ERROR'}, msg)
        return {'CANCELLED'}

    selected_csvs = [item.name for item in scn.csv_items if item.selected]
    selected_items = [item for item in scn.analysis_items if item.enabled]

    if not selected_csvs:
        report({'ERROR'}, "No CSV selected")
        return {'CANCELLED'}

    graph_type = scn.selected_graph
    use_log_scale = bool(getattr(scn, "anali_use_log_scale", False))
    use_compact_labels = bool(getattr(scn, "anali_use_compact_labels", False))
    palette_name = getattr(scn, "anali_color_palette", None)

    # INTERACTION COMPARATIVE

    if graph_type == "G1" and len(selected_csvs) > 1:

        key_x = "A1"
        y_metrics = [item.key for item in selected_items if item.key != key_x]
        if len(y_metrics) < 1:
            report({'ERROR'}, "Interaction needs at least one selected Y metric; X is always time")
            return {'CANCELLED'}

        target_scene = get_or_create_graph_scene("Interaction_Comparative")
        switch_to_scene(target_scene)
        clear_previous_graphs(target_scene)
        hide_non_graph_objects(target_scene)

        prepared = []
        all_x = []
        all_y = []
        csv_step = float(scn.axis_scale_z) / max(1, len(selected_csvs) - 1)
        metric_step = 0.14

        for csv_idx, csv_path in enumerate(selected_csvs):
            csv_name = os.path.basename(csv_path)
            try:
                _, data = read_csv(csv_path)
                metrics = compute_metrics_for_csv(data, max_reasonable_speed=getattr(context.scene, "max_reasonable_speed", DEFAULT_MAX_REASONABLE_SPEED))
                values_x_base = series_to_array(metrics.get(key_x, []))
            except Exception as exc:
                print(f"[interaction comparative] {csv_path}: {exc}")
                continue

            if values_x_base.size == 0:
                continue

            for metric_idx, key_y in enumerate(y_metrics):
                values_y = series_to_array(metrics.get(key_y, []))
                n = min(values_x_base.size, values_y.size)
                if n == 0:
                    continue
                x = values_x_base[:n]
                y = values_y[:n]
                finite = np.isfinite(x) & np.isfinite(y)
                x = clamp_outliers(x[finite])
                y = clamp_outliers(y[finite])
                if use_log_scale:
                    y = _signed_log10_1p(y)
                if x.size == 0 or y.size == 0:
                    continue
                all_x.extend(x.tolist())
                all_y.extend(y.tolist())
                prepared.append({
                    "csv_name": csv_name,
                    "metric_key": key_y,
                    "metric_label": ANALYSIS.get(key_y, {}).get("label", key_y),
                    "metric_index": metric_idx,
                    "csv_index": csv_idx,
                    "x": x,
                    "y": y,
                    "z": csv_idx * csv_step + metric_idx * metric_step,
                    "color": metric_color_for_csv(csv_idx, metric_idx, palette_name),
                })

        if not prepared:
            report({'ERROR'}, "Interaction comparison could not generate data")
            return {'CANCELLED'}

        x_range = (float(np.min(all_x)), float(np.max(all_x)))
        y_range = (float(np.min(all_y)), float(np.max(all_y)))

        for item in prepared:
            create_interaction_graph_3d(
                item["x"], item["y"], item["z"],
                scn.axis_scale_x, scn.axis_scale_y,
                csv_name=item["csv_name"],
                metric_name=f"{key_x}_{item['metric_key']}",
                color=item["color"],
                x_range=x_range,
                y_range=y_range,
            )

        x_ticks = [x_range[0]] if x_range[0] == x_range[1] else list(np.linspace(x_range[0], x_range[1], 5))
        y_ticks = [y_range[0]] if y_range[0] == y_range[1] else list(np.linspace(y_range[0], y_range[1], 5))
        draw_axes_for_graph(
            scn,
            [ANALYSIS.get(key_x, {}).get("label", key_x), "", ""],
            {"x_range": x_range, "y_range": y_range, "x_ticks": x_ticks, "y_ticks": y_ticks},
            z_range=(0.0, float(scn.axis_scale_z)),
        )
        scale_text = " · log10(1+Y)" if use_log_scale else " · linear Y"
        create_text_label(f"Interaction plot · CSV families{scale_text}", (scn.axis_scale_x * 0.5, scn.axis_scale_y + 0.85, 0.12), 0.42, "GraphTitle_G1", align_x="CENTER")
        metric_legend = []
        for csv_idx, csv_path in enumerate(selected_csvs):
            csv_base = os.path.splitext(os.path.basename(csv_path))[0]
            csv_label = csv_base[:12] if use_compact_labels else csv_base
            for idx, key in enumerate(y_metrics):
                metric_label = key if use_compact_labels else ANALYSIS.get(key, {}).get("label", key)
                metric_legend.append({
                    "name": f"{csv_label} · {metric_label}",
                    "color": metric_color_for_csv(csv_idx, idx, palette_name),
                })
        draw_csv_color_legend(
            csv_items=metric_legend,
            axis_scale_x=scn.axis_scale_x,
            axis_scale_y=scn.axis_scale_y,
            z_pos=0.15,
            title="Y metrics",
        )

        frame_graph_camera(target_scene, scn)
        report({'INFO'}, "Interaction generated")
        return {'FINISHED'}

    # FOREST COMPARATIVE

    if graph_type == "G2":

        if len(selected_csvs) < 2:
            report({'ERROR'}, "Forest plot needs at least two selected CSV files")
            return {'CANCELLED'}

        metric_keys = [item.key for item in selected_items]

        if len(metric_keys) != 1:
            report({'ERROR'}, "Forest plot needs exactly one selected metric")
            return {'CANCELLED'}

        metric_key = metric_keys[0]
        metric_label = ANALYSIS.get(metric_key, {}).get("label", metric_key)

        target_scene = get_or_create_graph_scene(f"Forest_{metric_key}")

        switch_to_scene(target_scene)
        clear_previous_graphs(target_scene)
        hide_non_graph_objects(target_scene)

        rows = []

        for csv_idx, csv_path in enumerate(selected_csvs):

            csv_name = os.path.basename(csv_path)

            try:
                _, data = read_csv(csv_path)
                metrics = compute_metrics_for_csv(data, max_reasonable_speed=getattr(context.scene, "max_reasonable_speed", DEFAULT_MAX_REASONABLE_SPEED))

                row = forest_row_stats(
                    metric_key,
                    metrics,
                    csv_name,
                    use_log_scale=use_log_scale,
                )

                if row is not None:
                    row["color_index"] = csv_idx
                    rows.append(row)

            except Exception as exc:
                print(f"[forest plot] {csv_path}: {exc}")

        if len(rows) < 2:
            report({'ERROR'}, "Forest plot could not read enough valid CSV metric series")
            return {'CANCELLED'}

        graph_data = draw_multi_csv_forest_plot_3d(
            rows,
            metric_label=metric_label,
            axis_scale_x=scn.axis_scale_x,
            axis_scale_y=max(scn.axis_scale_y, len(rows) * 0.7),
            z_pos=0.0,
            compact_labels=use_compact_labels,
            scale_label="log10(1+x)" if use_log_scale else "linear",
        )

        frame_graph_camera(target_scene, scn)

        report({'INFO'}, "Forest comparative generated")
        return {'FINISHED'}

    # RADAR COMPARATIVE

    if graph_type == "G3":

        if len(selected_csvs) < 2:
            report({'ERROR'}, "Radar plot needs at least two selected CSV files/users")
            return {'CANCELLED'}

        metric_keys = [item.key for item in selected_items]

        target_scene = get_or_create_graph_scene("Radar_Comparative")

        switch_to_scene(target_scene)
        clear_previous_graphs(target_scene)
        hide_non_graph_objects(target_scene)

        labels = []
        radar_series = []

        for idx, csv_path in enumerate(selected_csvs):

            csv_name = os.path.basename(csv_path)

            try:
                _, data = read_csv(csv_path)
                metrics = compute_metrics_for_csv(data, max_reasonable_speed=getattr(context.scene, "max_reasonable_speed", DEFAULT_MAX_REASONABLE_SPEED))

            except Exception as exc:
                print(f"[radar comparative] {csv_path}: {exc}")
                continue

            raw_values = []
            current_labels = []

            for key in metric_keys:

                value, unit = radar_summary_value(
                    key,
                    metrics.get(key, [])
                )

                if value is None:
                    continue

                raw_values.append(value)

                current_labels.append(
                    ANALYSIS[key]["label"]
                )

            radar_values = normalize_radar_values(raw_values)

            if not radar_values:
                continue

            if not labels:
                labels = current_labels

            color = csv_color_by_index(idx, palette_name)

            draw_radar_graph_3d_filled(
                radar_values,
                axis_scale_x=scn.axis_scale_x,
                axis_scale_y=scn.axis_scale_y,
                z_pos=idx * 0.03,
                labels=labels if idx == 0 else [],
                color=color,
                csv_name=f"radar_{idx}_{sanitize_name(csv_name)}",
            )

            radar_series.append({
                "name": csv_name,
                "color": color,
            })

        if not radar_series:
            report({'ERROR'}, "Radar comparative could not generate data")
            return {'CANCELLED'}

        graph_data = {
            "x_range": (0.0, 1.0),
            "y_range": (0.0, 1.0),
            "x_ticks": [],
            "y_ticks": [],
        }

        draw_axes_for_graph(
            scn,
            ["", "", ""],
            graph_data,
            z_range=(0.0, 1.0),
        )

        draw_csv_color_legend(
            csv_items=radar_series,
            axis_scale_x=scn.axis_scale_x,
            axis_scale_y=scn.axis_scale_y,
            z_pos=0.15,
            title="CSV"
        )
        create_text_label("Radar plot · CSV comparison", (scn.axis_scale_x * 0.5, scn.axis_scale_y + 0.85, 0.12), 0.42, "GraphTitle_G3", align_x="CENTER")

        frame_graph_camera(target_scene, scn)

        report({'INFO'}, "Comparative radar generated")
        return {'FINISHED'}

    # REST OF GRAPHS

    for csv_idx, csv_path in enumerate(selected_csvs):

        csv_name = os.path.basename(csv_path)

        target_scene = get_or_create_graph_scene(csv_name)

        switch_to_scene(target_scene)
        clear_previous_graphs(target_scene)
        hide_non_graph_objects(target_scene)

        _, data = read_csv(csv_path)

        metrics = compute_metrics_for_csv(data, max_reasonable_speed=getattr(context.scene, "max_reasonable_speed", DEFAULT_MAX_REASONABLE_SPEED))

        color = csv_color_by_index(csv_idx, palette_name)

        # INTERACTION PARA UN SOLO CSV
        if graph_type == "G1":
            key_x = "A1"
            y_metrics = [item.key for item in selected_items if item.key != key_x]
            if len(y_metrics) < 2:
                report({'ERROR'}, "Interaction needs at least two selected Y metrics; X is always time")
                return {'CANCELLED'}

            values_x_base = series_to_array(metrics.get(key_x, []))
            if values_x_base.size == 0:
                continue

            prepared = []
            all_x = []
            all_y = []
            for metric_idx, key_y in enumerate(y_metrics):
                values_y = series_to_array(metrics.get(key_y, []))
                n = min(values_x_base.size, values_y.size)
                if n == 0:
                    continue
                x = values_x_base[:n]
                y = values_y[:n]
                finite = np.isfinite(x) & np.isfinite(y)
                x = clamp_outliers(x[finite])
                y = clamp_outliers(y[finite])
                if use_log_scale:
                    y = _signed_log10_1p(y)
                if x.size == 0 or y.size == 0:
                    continue
                all_x.extend(x.tolist())
                all_y.extend(y.tolist())
                prepared.append({
                    "metric_key": key_y,
                    "metric_index": metric_idx,
                    "x": x,
                    "y": y,
                    "z": metric_idx * 0.14,
                    "color": metric_color_for_csv(csv_idx, metric_idx, palette_name),
                })

            if not prepared:
                report({'ERROR'}, "Interaction could not generate valid metric series")
                return {'CANCELLED'}

            x_range = (float(np.min(all_x)), float(np.max(all_x)))
            y_range = (float(np.min(all_y)), float(np.max(all_y)))
            for item in prepared:
                create_interaction_graph_3d(
                    item["x"], item["y"], item["z"],
                    scn.axis_scale_x, scn.axis_scale_y,
                    csv_name=csv_name,
                    metric_name=f"{key_x}_{item['metric_key']}",
                    color=item["color"],
                    x_range=x_range,
                    y_range=y_range,
                )

            x_ticks = [x_range[0]] if x_range[0] == x_range[1] else list(np.linspace(x_range[0], x_range[1], 5))
            y_ticks = [y_range[0]] if y_range[0] == y_range[1] else list(np.linspace(y_range[0], y_range[1], 5))
            draw_axes_for_graph(
                scn,
                [ANALYSIS[key_x]["label"], "", ""],
                {"x_range": x_range, "y_range": y_range, "x_ticks": x_ticks, "y_ticks": y_ticks},
            )
            scale_text = " · log10(1+Y)" if use_log_scale else " · linear Y"
            create_text_label(f"Interaction plot{scale_text}", (scn.axis_scale_x * 0.5, scn.axis_scale_y + 0.85, 0.12), 0.42, "GraphTitle_G1", align_x="CENTER")
            draw_csv_color_legend(
                csv_items=[
                    {"name": (key if use_compact_labels else ANALYSIS.get(key, {}).get("label", key)), "color": metric_color_for_csv(csv_idx, idx, palette_name)}
                    for idx, key in enumerate(y_metrics)
                ],
                axis_scale_x=scn.axis_scale_x,
                axis_scale_y=scn.axis_scale_y,
                z_pos=0.15,
                title="Y metrics",
            )
            frame_graph_camera(target_scene, scn)
            continue

        # STANDARD GRAPHS

        offset = 0.0

        for metric_key in [item.key for item in selected_items]:

            values = series_to_array(
                metrics.get(metric_key, [])
            )

            if values.size == 0:
                continue

            graph_data = None

            # SINGLE FOREST

            if graph_type == "G2":

                draw_forest_plot_3d(
                    values.tolist(),
                    csv_name=csv_name,
                    metric_name=metric_key,
                    axis_scale_x=scn.axis_scale_x,
                    axis_scale_y=scn.axis_scale_y,
                    z_pos=offset
                )

                v_min = float(np.min(values)) if values.size else 0.0
                v_max = float(np.max(values)) if values.size else 1.0
                # En forest el eje debe incluir 0 para no exagerar diferencias visuales.
                v_min = min(0.0, v_min)
                v_max = max(0.0, v_max)
                graph_data = {
                    "x_range": (v_min, v_max),
                    "y_range": (0.0, 1.0),
                    "x_ticks": [v_min] if v_min == v_max else list(np.linspace(v_min, v_max, 5)),
                    "y_ticks": [],
                }

            draw_axes_for_graph(
                scn,
                [
                    ANALYSIS[metric_key]["label"],
                    "Value",
                    "Z"
                ],
                graph_data
            )

            offset += max(1.5, scn.axis_scale_z)

        frame_graph_camera(target_scene, scn)

    report({'INFO'}, "Graphs generated")

    return {'FINISHED'}
