# SPDX-License-Identifier: GPL-3.0-or-later
"""3D data-table generation for selected CSV metrics."""
from __future__ import annotations

import math
import os
import bpy
import numpy as np
from mathutils import Vector

try:
    from .analytics import ANALYSIS, compute_metrics_for_csv, series_to_array
    from .constants import DEFAULT_MAX_REASONABLE_SPEED
    from .graphs import create_axis, create_text_label, clear_previous_graphs, csv_color_by_index
    from .ui_helpers import hide_non_graph_objects, frame_graph_camera, hide_viewport_guides
    from .utils import read_csv
    from .texts import tr
except ImportError:
    from analytics import ANALYSIS, compute_metrics_for_csv, series_to_array
    from constants import DEFAULT_MAX_REASONABLE_SPEED
    from graphs import create_axis, create_text_label, clear_previous_graphs, csv_color_by_index
    from ui_helpers import hide_non_graph_objects, frame_graph_camera, hide_viewport_guides
    from utils import read_csv
    from texts import tr


def _stat_value(values, statistic: str):
    arr = series_to_array(values)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None
    if statistic == 'MEDIAN':
        return float(np.median(arr))
    if statistic == 'STD':
        return float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0
    if statistic == 'MIN':
        return float(np.min(arr))
    if statistic == 'MAX':
        return float(np.max(arr))
    if statistic == 'SUM':
        return float(np.sum(arr))
    if statistic == 'COUNT':
        return float(arr.size)
    if statistic == 'LAST':
        return float(arr[-1])
    return float(np.mean(arr))


def _stat_label(statistic: str, scene=None) -> str:
    label = {
        'MEAN': 'Mean', 'MEDIAN': 'Median', 'STD': 'Standard deviation',
        'MIN': 'Minimum', 'MAX': 'Maximum', 'SUM': 'Sum',
        'COUNT': 'Count', 'LAST': 'Last value', 'RAW': 'All raw values',
    }.get(statistic, statistic.title())
    return tr(scene, label) if scene is not None else label


def _format_cell(value) -> str:
    if value is None or not np.isfinite(value):
        return '—'
    return f"{float(value):.2f}"


def _safe_name(value) -> str:
    return ''.join(ch if ch.isalnum() or ch in '_-' else '_' for ch in str(value))


def _table_prefix_cleanup(scene):
    for obj in list(scene.objects):
        if obj.name.startswith(('DataTable', 'TableGrid_', 'TableText_', 'TableTitle_', 'TableSubtitle_')):
            bpy.data.objects.remove(obj, do_unlink=True)


def clear_data_tables(scene):
    _table_prefix_cleanup(scene)


def _draw_line(x0, y0, x1, y1, name, color, z=0.0, thickness=0.008):
    create_axis(Vector((x0, y0, z)), Vector((x1, y1, z)), color, name, radius=thickness, vertices=6)


def generate_data_table(context, report):
    scn = context.scene

    # The list can be empty immediately after enabling the add-on or opening a
    # saved file. Initialise it here as a final safety net, without requiring
    # the user to change a graph option first.
    if len(scn.analysis_items) == 0:
        try:
            from .ui_helpers import refresh_analysis_list
        except ImportError:
            from ui_helpers import refresh_analysis_list
        refresh_analysis_list(None, context)

    selected_csvs = [item.name for item in scn.csv_items if item.selected]
    metric_keys = [item.key for item in scn.analysis_items if item.enabled]
    if not selected_csvs:
        report({'ERROR'}, tr(scn, 'Select at least one CSV file'))
        return {'CANCELLED'}
    if not metric_keys:
        report({'ERROR'}, tr(scn, 'Select at least one metric'))
        return {'CANCELLED'}

    statistic = getattr(scn, 'anali_table_statistic', 'MEAN')
    rows_per_page = max(1, int(getattr(scn, 'anali_table_rows_per_page', 10)))
    cols_per_page = max(1, int(getattr(scn, 'anali_table_cols_per_page', 4)))
    row_page = max(0, int(getattr(scn, 'anali_table_row_page', 1)) - 1)
    col_page = max(0, int(getattr(scn, 'anali_table_col_page', 1)) - 1)

    # Load all selected CSVs once. This supports both summary and raw modes.
    loaded = []
    for csv_idx, csv_path in enumerate(selected_csvs):
        try:
            _, data = read_csv(csv_path)
            metrics = compute_metrics_for_csv(
                data,
                max_reasonable_speed=getattr(scn, 'max_reasonable_speed', DEFAULT_MAX_REASONABLE_SPEED),
            )
            loaded.append((os.path.basename(csv_path), metrics, csv_idx))
        except Exception as exc:
            print(f'[data table] {csv_path}: {exc}')

    if not loaded:
        report({'ERROR'}, tr(scn, 'No valid data could be loaded for the table'))
        return {'CANCELLED'}

    max_col_page = max(0, math.ceil(len(metric_keys) / cols_per_page) - 1)
    col_page = min(col_page, max_col_page)
    metric_slice = metric_keys[col_page * cols_per_page:(col_page + 1) * cols_per_page]

    raw_mode = statistic == 'RAW'
    all_rows = []
    if raw_mode:
        # One row per original observation index. Metrics with shorter series
        # show an em dash for missing positions; no mean or other aggregation is
        # performed.
        for csv_name, metrics, csv_idx in loaded:
            arrays = {key: series_to_array(metrics.get(key, [])) for key in metric_slice}
            max_len = max((arr.size for arr in arrays.values()), default=0)
            for sample_idx in range(max_len):
                values = [float(arr[sample_idx]) if sample_idx < arr.size else None for arr in arrays.values()]
                all_rows.append((csv_name, sample_idx + 1, values, csv_idx))
    else:
        for csv_name, metrics, csv_idx in loaded:
            values = [_stat_value(metrics.get(key, []), statistic) for key in metric_slice]
            all_rows.append((csv_name, None, values, csv_idx))

    if not all_rows:
        report({'ERROR'}, tr(scn, 'The selected metrics contain no valid values'))
        return {'CANCELLED'}

    max_row_page = max(0, math.ceil(len(all_rows) / rows_per_page) - 1)
    row_page = min(row_page, max_row_page)
    scn.anali_table_row_page = row_page + 1
    scn.anali_table_col_page = col_page + 1
    data_rows = all_rows[row_page * rows_per_page:(row_page + 1) * rows_per_page]

    # Tables and graphs are mutually exclusive visualisations. Remove every
    # previously generated Analysis3D graph/table object before drawing the
    # new table, while preserving the user's modelling objects.
    clear_previous_graphs(scn)
    hide_non_graph_objects(scn)
    hide_viewport_guides(context)

    white = (0.94, 0.94, 0.97, 1.0)
    subtle = (0.66, 0.69, 0.76, 1.0)
    grid = (0.28, 0.31, 0.38, 1.0)
    header = (0.80, 0.84, 0.92, 1.0)

    first_col_w = 3.0
    index_col_w = 1.15 if raw_mode else 0.0
    metric_col_w = 2.35
    row_h = 0.62
    table_w = first_col_w + index_col_w + metric_col_w * len(metric_slice)
    table_h = row_h * (len(data_rows) + 1)
    x0 = -table_w / 2.0
    y_top = table_h / 2.0
    z = 0.0

    title = tr(scn, 'Raw data table · selected CSV metrics') if raw_mode else tr(scn, 'Data table · selected CSV metrics')
    create_text_label(title, (0.0, y_top + 1.15, z), 0.42, 'TableTitle_Main', align_x='CENTER', color=white)
    if raw_mode:
        subtitle = f"{tr(scn, 'All recorded values')} · {tr(scn, 'no aggregation')} · {tr(scn, 'two decimals')} · {tr(scn, 'rows')} {row_page + 1}/{max_row_page + 1} · {tr(scn, 'columns')} {col_page + 1}/{max_col_page + 1}"
    else:
        subtitle = f"{_stat_label(statistic, scn)} · {tr(scn, 'values shown with two decimals')} · {tr(scn, 'rows')} {row_page + 1}/{max_row_page + 1} · {tr(scn, 'columns')} {col_page + 1}/{max_col_page + 1}"
    create_text_label(subtitle, (0.0, y_top + 0.78, z), 0.22, 'TableSubtitle_Main', align_x='CENTER', color=subtle)

    for r in range(len(data_rows) + 2):
        y = y_top - r * row_h
        _draw_line(x0, y, x0 + table_w, y, f'TableGrid_H_{r}', grid, z=z)

    x_positions = [x0, x0 + first_col_w]
    if raw_mode:
        x_positions.append(x0 + first_col_w + index_col_w)
    metric_start = x0 + first_col_w + index_col_w
    x_positions.extend(metric_start + metric_col_w * i for i in range(1, len(metric_slice) + 1))
    for c, x in enumerate(x_positions):
        _draw_line(x, y_top, x, y_top - row_h * (len(data_rows) + 1), f'TableGrid_V_{c}', grid, z=z)

    create_text_label(tr(scn, 'CSV / User'), (x0 + 0.14, y_top - row_h * 0.66, z), 0.25, 'TableText_Header_CSV', align_x='LEFT', color=header)
    if raw_mode:
        create_text_label(tr(scn, 'Row'), (x0 + first_col_w + index_col_w * 0.5, y_top - row_h * 0.66, z), 0.22, 'TableText_Header_Row', align_x='CENTER', color=header)
    for idx, key in enumerate(metric_slice):
        label = tr(scn, ANALYSIS.get(key, {}).get('label', key))
        cx = metric_start + metric_col_w * (idx + 0.5)
        short = label if len(label) <= 23 else label[:21] + '…'
        create_text_label(short, (cx, y_top - row_h * 0.66, z), 0.21, f'TableText_Header_{_safe_name(key)}', align_x='CENTER', color=header)

    for row_idx, (csv_name, sample_idx, values, csv_idx) in enumerate(data_rows):
        y = y_top - row_h * (row_idx + 1.66)
        color = csv_color_by_index(csv_idx, getattr(scn, 'anali_color_palette', None))
        shown_name = csv_name if len(csv_name) <= 31 else csv_name[:29] + '…'
        create_text_label(shown_name, (x0 + 0.14, y, z), 0.22, f'TableText_Row_{row_idx}', align_x='LEFT', color=color)
        if raw_mode:
            create_text_label(str(sample_idx), (x0 + first_col_w + index_col_w * 0.5, y, z), 0.22, f'TableText_Index_{row_idx}', align_x='CENTER', color=subtle)
        for col_idx, value in enumerate(values):
            cx = metric_start + metric_col_w * (col_idx + 0.5)
            create_text_label(_format_cell(value), (cx, y, z), 0.24, f'TableText_Cell_{row_idx}_{col_idx}', align_x='CENTER', color=white)

    footer_y = y_top - row_h * (len(data_rows) + 1) - 0.42
    row_description = tr(scn, 'raw observations') if raw_mode else tr(scn, 'CSV files')
    create_text_label(
        f"{tr(scn, 'Showing')} {len(data_rows)} {tr(scn, 'of')} {len(all_rows)} {row_description} {tr(scn, 'and')} {len(metric_slice)} {tr(scn, 'of')} {len(metric_keys)} {tr(scn, 'metrics')}",
        (0.0, footer_y, z), 0.20, 'TableSubtitle_Footer', align_x='CENTER', color=subtle,
    )

    frame_graph_camera(scn, scn)
    report({'INFO'}, f"{tr(scn, 'Data table generated')}: {len(data_rows)} {tr(scn, 'rows')} × {len(metric_slice)} {tr(scn, 'metrics')}")
    return {'FINISHED'}

