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
from mathutils import Vector

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
        create_axis,
        create_interaction_graph_3d,
        draw_forest_plot_3d,
        draw_multi_csv_forest_plot_3d,
        draw_multi_metric_forest_plot_3d,
        draw_radar_graph_3d_filled,
        draw_csv_color_legend,
    )
    from .utils import read_csv
    from .texts import tr
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
        create_axis,
        create_interaction_graph_3d,
        draw_forest_plot_3d,
        draw_multi_csv_forest_plot_3d,
        draw_multi_metric_forest_plot_3d,
        draw_radar_graph_3d_filled,
        draw_csv_color_legend,
    )
    from utils import read_csv
    from texts import tr


def _signed_log10_1p(values):
    """Signed log10(1+x) transform used by graph rendering.

    Defined locally because wildcard imports intentionally do not bring private
    helpers from ui_helpers into this module.
    """
    arr = np.asarray(values, dtype=float)
    return np.sign(arr) * np.log10(1.0 + np.abs(arr))


def _metric_context_range(metric_key, arrays):
    """Return a readable, metric-specific range shared by all compared CSVs."""
    clean = []
    for values in arrays:
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size:
            clean.append(arr)
    if not clean:
        return (0.0, 1.0)

    values = np.concatenate(clean)
    if values.size >= 4:
        low, high = np.percentile(values, [2.0, 98.0])
    else:
        low, high = float(np.min(values)), float(np.max(values))

    # Binary/event-state metrics.
    if metric_key in {"A2", "A3", "A6", "A7", "A8", "A9", "A15"}:
        return (0.0, max(1.0, float(high)))

    # Work mode is encoded as discrete states.
    if metric_key == "A14":
        return (0.0, max(2.0, float(high)))

    # Signed deltas should be visually balanced around zero.
    if metric_key in {"A12", "A13", "A16"} or low < 0.0:
        bound = max(abs(float(low)), abs(float(high)), 1e-9)
        return (-bound, bound)

    # Speeds, distances and counts are non-negative and benefit from a zero base.
    low = 0.0
    high = max(float(high), float(np.max(values)), 1e-9)
    pad = high * 0.05
    return (low, high + pad)


def _normalize_context(values, value_range):
    arr = np.asarray(values, dtype=float)
    low, high = value_range
    denom = max(float(high) - float(low), 1e-12)
    return np.clip((arr - float(low)) / denom, 0.0, 1.0)


def _format_context_range(value_range):
    low, high = value_range
    return f"{low:.3g}–{high:.3g}"




def _g1_series_array(values):
    """Return a float array without removing NaNs so X/Y row alignment is preserved."""
    if values is None:
        return np.asarray([], dtype=float)
    return np.asarray(list(values), dtype=float)


def _g1_progress_x(values_x):
    """Map visible samples to 0–100 % while preserving missing rows.

    Using sample progress prevents irregular timestamps or very different CSV
    durations from compressing most points against one edge of the graph.
    """
    x = np.asarray(values_x, dtype=float)
    result = np.full(x.shape, np.nan, dtype=float)
    finite = np.isfinite(x)
    if not np.any(finite):
        return result
    valid = x[finite]
    low = float(np.min(valid))
    high = float(np.max(valid))
    if abs(high - low) <= 1e-12:
        finite_indices = np.flatnonzero(finite)
        if finite_indices.size == 1:
            result[finite_indices[0]] = 50.0
        else:
            result[finite_indices] = np.linspace(0.0, 100.0, finite_indices.size)
        return result
    result[finite] = ((valid - low) / (high - low)) * 100.0
    return result


def _g1_global_sample_progress_x(values_x):
    """Map the full recording to 0–100 % by row position, not timestamp value.

    This is intentionally used only by the Global view. It guarantees that all
    rows occupy the complete horizontal width even when timestamps are highly
    irregular, duplicated, or contain a large jump near the end.
    """
    x = np.asarray(values_x, dtype=float)
    result = np.full(x.shape, np.nan, dtype=float)
    n = int(x.size)
    if n <= 0:
        return result
    finite = np.isfinite(x)
    if not np.any(finite):
        return result
    if n == 1:
        result[finite] = 50.0
        return result
    row_progress = np.linspace(0.0, 100.0, n)
    result[finite] = row_progress[finite]
    return result


def _g1_window(values_x, values_y, start, size, global_view=False):
    """Return the visible finite X/Y pairs for one contiguous G1 data window."""
    x = np.asarray(values_x, dtype=float)
    y = np.asarray(values_y, dtype=float)
    n = min(x.size, y.size)
    if n <= 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    if global_view:
        x = x[:n]
        y = y[:n]
    else:
        start = max(0, int(start))
        size = max(1, int(size))
        if start >= n:
            return np.asarray([], dtype=float), np.asarray([], dtype=float)
        end = min(n, start + size)
        x = x[start:end]
        y = y[start:end]
    finite = np.isfinite(x) & np.isfinite(y)
    return x[finite], y[finite]


def _g1_window_segments(values_x, values_y, start, size, global_view=False):
    """Return all contiguous finite segments inside the active G1 window.

    This preserves row alignment and splits the polyline whenever a metric has
    gaps/NaNs, so later valid samples are still drawn as additional segments
    instead of being visually lost.
    """
    x = np.asarray(values_x, dtype=float)
    y = np.asarray(values_y, dtype=float)
    n = min(x.size, y.size)
    if n <= 0:
        return []
    if global_view:
        x = x[:n]
        y = y[:n]
    else:
        start = max(0, int(start))
        size = max(1, int(size))
        if start >= n:
            return []
        end = min(n, start + size)
        x = x[start:end]
        y = y[start:end]

    finite = np.isfinite(x) & np.isfinite(y)
    if not np.any(finite):
        return []

    segments = []
    seg_start = None
    for idx, ok in enumerate(finite):
        if ok and seg_start is None:
            seg_start = idx
        elif (not ok) and seg_start is not None:
            xs = x[seg_start:idx]
            ys = y[seg_start:idx]
            if xs.size:
                segments.append((xs, ys))
            seg_start = None
    if seg_start is not None:
        xs = x[seg_start:]
        ys = y[seg_start:]
        if xs.size:
            segments.append((xs, ys))
    return segments


def _g1_active_x_range(window_x_arrays):
    """Return the visible X domain with a small padding for readability."""
    clean = []
    for values in window_x_arrays:
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size:
            clean.append(arr)
    if not clean:
        return (0.0, 1.0)
    values = np.concatenate(clean)
    low = float(np.min(values))
    high = float(np.max(values))
    if low == high:
        pad = max(abs(low) * 0.01, 1e-6)
        return (low - pad, high + pad)
    span = high - low
    pad = span * 0.04
    return (low - pad, high + pad)


def _g1_window_tick_data(x_range, real_x_values, count=5):
    """Return evenly spaced plot positions with labels from real visible X values."""
    real = np.asarray(real_x_values, dtype=float)
    real = real[np.isfinite(real)]
    if real.size == 0:
        ticks = _g1_ticks(x_range, count)
        return ticks, [_g1_format_value(value, x_range[1] - x_range[0]) for value in ticks]
    count = max(3, min(5, int(count)))
    indices = np.linspace(0, real.size - 1, min(count, real.size)).astype(int)
    indices = sorted(set(int(i) for i in indices))
    x0, x1 = map(float, x_range)
    if real.size == 1:
        positions = [(x0 + x1) * 0.5]
    else:
        positions = [x0 + (idx / float(real.size - 1)) * (x1 - x0) for idx in indices]
    labels = [_g1_format_value(real[idx], float(np.max(real) - np.min(real)) if real.size > 1 else abs(float(real[idx]))) for idx in indices]
    return positions, labels


def _g1_ticks(value_range, count=4):
    """Generate between three and five readable ticks for a metric band."""
    low, high = map(float, value_range)
    if not np.isfinite(low) or not np.isfinite(high):
        return []
    count = max(3, min(5, int(count)))
    if abs(high - low) <= 1e-12:
        return [low]
    return list(np.linspace(low, high, count))


def _g1_format_value(value, span=None):
    value = float(value)
    if not np.isfinite(value):
        return "–"
    magnitude = abs(value)
    span = abs(float(span)) if span is not None and np.isfinite(span) else magnitude
    if magnitude >= 1e5 or (0 < magnitude < 1e-4):
        return f"{value:.2e}"
    if span >= 100:
        return f"{value:.0f}"
    if span >= 10:
        return f"{value:.1f}".rstrip('0').rstrip('.')
    if span >= 1:
        return f"{value:.2f}".rstrip('0').rstrip('.')
    if span >= 0.01:
        return f"{value:.3f}".rstrip('0').rstrip('.')
    return f"{value:.4g}"



def _g1_semantic_info(scn, metric_key, arrays):
    """Return bilingual meaning, categorical ticks, and a useful window summary."""
    clean = []
    for values in arrays or []:
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size:
            clean.extend(float(v) for v in arr)

    info = {"description": "", "ticks": None, "summary": "", "mean_label": None}

    if metric_key == "A14":
        total = max(1, len(clean))
        object_count = sum(1 for value in clean if abs(value - 1.0) <= 0.25)
        edit_count = sum(1 for value in clean if abs(value - 2.0) <= 0.25)
        other_count = max(0, len(clean) - object_count - edit_count)
        info["description"] = tr(scn, "0 = Other · 1 = Object Mode · 2 = Edit Mode")
        info["ticks"] = [(0.0, tr(scn, "Other")), (1.0, tr(scn, "Object")), (2.0, tr(scn, "Edit"))]
        info["summary"] = tr(scn, "Object {object_pct}% · Edit {edit_pct}% · Other {other_pct}%").format(
            object_pct=round(100.0 * object_count / total),
            edit_pct=round(100.0 * edit_count / total),
            other_pct=round(100.0 * other_count / total),
        )
        info["mean_label"] = tr(scn, "Average state")
        return info

    if metric_key == "A15":
        events = sum(1 for value in clean if value >= 0.5)
        info["description"] = tr(scn, "0 = No UV topology change · 1 = UV topology change")
        info["ticks"] = [(0.0, tr(scn, "No change")), (1.0, tr(scn, "UV change"))]
        info["summary"] = tr(scn, "UV changes in visible data: {count}").format(count=events)
        return info

    if metric_key in {"A6", "A7", "A8", "A9"}:
        events = sum(1 for value in clean if value >= 0.5)
        info["description"] = tr(scn, "0 = No peak · 1 = Detected peak")
        info["ticks"] = [(0.0, tr(scn, "No peak")), (1.0, tr(scn, "Peak"))]
        info["summary"] = tr(scn, "Detected peaks in visible data: {count}").format(count=events)
        return info

    if metric_key == "A10":
        info["description"] = tr(scn, "Shortcut events per row: Ctrl+V, Shift+D and Alt+D")
        info["summary"] = tr(scn, "Shortcut events in visible data: {count}").format(count=_g1_format_value(sum(clean), 10.0))
    elif metric_key == "A11":
        info["description"] = tr(scn, "Absolute number of modifier changes recorded in each row")
        info["summary"] = tr(scn, "Modifier changes in visible data: {count}").format(count=_g1_format_value(sum(abs(v) for v in clean), 10.0))
    elif metric_key == "A12":
        info["description"] = tr(scn, "Negative = vertices removed · Positive = vertices added")
        info["summary"] = tr(scn, "Net vertex change: {value}").format(value=_g1_format_value(sum(clean), 10.0))
    elif metric_key == "A13":
        info["description"] = tr(scn, "Absolute changes in n-gons, triangles and inverted normals")
        info["summary"] = tr(scn, "Mesh issue changes in visible data: {count}").format(count=_g1_format_value(sum(abs(v) for v in clean), 10.0))
    elif metric_key == "A16":
        info["description"] = tr(scn, "Negative = objects removed · Positive = objects added")
        info["summary"] = tr(scn, "Net object change: {value}").format(value=_g1_format_value(sum(clean), 10.0))
    elif metric_key in {"A2", "A3"}:
        info["description"] = tr(scn, "0 = No pause · 1 = Detected pause")
        info["ticks"] = [(0.0, tr(scn, "No pause")), (1.0, tr(scn, "Pause"))]
        info["summary"] = tr(scn, "Detected pauses in visible data: {count}").format(count=sum(1 for value in clean if value >= 0.5))

    return info

def _g1_real_range(arrays):
    clean = []
    for values in arrays:
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size:
            clean.append(arr)
    if not clean:
        return (0.0, 1.0)
    values = np.concatenate(clean)
    low = float(np.min(values)); high = float(np.max(values))
    if low == high:
        pad = max(abs(low) * 0.05, 0.5)
        return (low - pad, high + pad)
    pad = (high - low) * 0.08
    return (low - pad, high + pad)


def _g1_band_y(values, value_range, band_bottom, band_top):
    low, high = value_range
    denom = max(float(high) - float(low), 1e-12)
    arr = np.asarray(values, dtype=float)
    return band_bottom + ((arr - float(low)) / denom) * (band_top - band_bottom)


def _g1_map_x_to_axis(values, x_range, axis_x):
    x0, x1 = map(float, x_range)
    denom = max(x1 - x0, 1e-12)
    arr = np.asarray(values, dtype=float)
    return ((arr - x0) / denom) * float(axis_x)


def _draw_g1_gap_markers(scn, segments, band, x_range, z_offset, name_prefix):
    """Draw a small visual break marker wherever a G1 line has internal gaps."""
    if not segments or len(segments) < 2:
        return
    gap_color = (0.55, 0.55, 0.55, 1.0)
    axis_x = float(scn.axis_scale_x)
    for idx in range(len(segments) - 1):
        left_x, left_y = segments[idx]
        right_x, right_y = segments[idx + 1]
        if left_x.size == 0 or right_x.size == 0:
            continue
        left_px = _g1_map_x_to_axis([left_x[-1]], x_range, axis_x)[0]
        right_px = _g1_map_x_to_axis([right_x[0]], x_range, axis_x)[0]
        mid_x = (float(left_px) + float(right_px)) * 0.5
        left_py = _g1_band_y([left_y[-1]], band['range'], band['bottom'], band['top'])[0]
        right_py = _g1_band_y([right_y[0]], band['range'], band['bottom'], band['top'])[0]
        mid_y = (float(left_py) + float(right_py)) * 0.5
        dx = 0.025 * max(1.0, axis_x)
        dy = 0.035 * max(1.0, band['top'] - band['bottom'])
        create_axis(Vector((mid_x - dx, mid_y - dy, z_offset + 0.001)), Vector((mid_x + dx, mid_y + dy, z_offset + 0.001)), gap_color, f'{name_prefix}_GapA_{idx}', radius=0.0028, vertices=6)
        create_axis(Vector((mid_x - dx, mid_y + dy, z_offset + 0.001)), Vector((mid_x + dx, mid_y - dy, z_offset + 0.001)), gap_color, f'{name_prefix}_GapB_{idx}', radius=0.0028, vertices=6)


def _g1_reduce_viewport_noise(context):
    screen = getattr(context, 'screen', None)
    if screen is None:
        return
    for area in screen.areas:
        if area.type != 'VIEW_3D':
            continue
        overlay = getattr(area.spaces.active, 'overlay', None)
        if overlay is not None:
            overlay.show_floor = False
            overlay.show_axis_x = False
            overlay.show_axis_y = False
            overlay.show_axis_z = False
            overlay.show_cursor = False


def _draw_g1_axes_and_bands(scn, x_range, bands, show_mean=False, csv_spans=None, x_label='Session duration (h)', x_tick_data=None):
    """Draw a common real X axis and independent real-value Y scales per band."""
    white = (0.92, 0.92, 0.92, 1.0)
    muted = (0.30, 0.30, 0.30, 1.0)
    grid = (0.22, 0.22, 0.22, 1.0)
    mean_color = (0.55, 0.55, 0.55, 1.0)
    axis_x = float(scn.axis_scale_x)
    x0, x1 = x_range
    x_span = x1 - x0
    if x_tick_data:
        ticks_x, tick_labels_x = x_tick_data
    else:
        ticks_x = _g1_ticks(x_range, 5)
        tick_labels_x = [_g1_format_value(tick, x_span) for tick in ticks_x]
    create_axis(Vector((0, 0, 0.02)), Vector((axis_x, 0, 0.02)), white, 'G1_Axis_X', radius=0.010, vertices=8)
    for idx, tick in enumerate(ticks_x):
        px = 0.0 if x1 == x0 else ((tick - x0) / (x1 - x0)) * axis_x
        create_axis(Vector((px, -0.045, 0.02)), Vector((px, 0.045, 0.02)), white, f'G1_XTick_{idx}', radius=0.006, vertices=6)
        label_x = tick_labels_x[idx] if idx < len(tick_labels_x) else _g1_format_value(tick, x_span)
        create_text_label(label_x, (px, -0.30, 0.02), 0.20, f'G1_XTickLabel_{idx}', align_x='CENTER')
        create_axis(Vector((px, 0.0, -0.018)), Vector((px, float(scn.axis_scale_y), -0.018)), grid, f'G1_XGrid_{idx}', radius=0.0020, vertices=6)
    create_text_label(x_label, (axis_x * 0.5, -0.62, 0.02), 0.25, 'G1_Label_X', align_x='CENTER')

    if csv_spans and len(csv_spans) > 1:
        ordered = sorted(csv_spans, key=lambda item: item[0])
        for idx in range(len(ordered) - 1):
            left_end = ordered[idx][1]
            right_start = ordered[idx + 1][0]
            if right_start > left_end:
                divider_x = ((left_end + right_start) * 0.5 - x0) / max(x_span, 1e-12) * axis_x
                create_axis(Vector((divider_x, 0.0, -0.01)), Vector((divider_x, float(scn.axis_scale_y), -0.01)), grid, f'G1_CSVDivider_{idx}', radius=0.004, vertices=6)

    for idx, band in enumerate(bands):
        bottom, top = band['bottom'], band['top']
        low, high = band['range']
        span = high - low
        create_axis(Vector((0, bottom, -0.01)), Vector((axis_x, bottom, -0.01)), muted, f'G1_BandBase_{idx}', radius=0.004, vertices=6)
        center_y = (bottom + top) * 0.5
        info_x = axis_x + 0.55
        create_text_label(band['label'], (info_x, center_y + 0.20, 0.02), 0.23, f'G1_BandLabel_{idx}', color=white, align_x='LEFT')
        semantic = band.get('semantic') or {}
        range_text = f"{_g1_format_value(low, span)} – {_g1_format_value(high, span)}"
        create_text_label(range_text, (info_x, center_y - 0.02, 0.02), 0.16, f'G1_BandRange_{idx}', color=white, align_x='LEFT')
        if semantic.get('description'):
            create_text_label(semantic['description'], (info_x, center_y - 0.23, 0.02), 0.145, f'G1_BandMeaning_{idx}', color=white, align_x='LEFT')
        if semantic.get('summary'):
            create_text_label(semantic['summary'], (info_x, center_y - 0.43, 0.02), 0.14, f'G1_BandSummary_{idx}', color=white, align_x='LEFT')
        tick_items = semantic.get('ticks') or [(tick, _g1_format_value(tick, span)) for tick in _g1_ticks((low, high), 4)]
        for tick_idx, tick_item in enumerate(tick_items):
            tick, tick_label = tick_item
            if tick < low - 1e-9 or tick > high + 1e-9:
                continue
            py = bottom + ((tick - low) / max(high - low, 1e-12)) * (top - bottom)
            create_axis(Vector((0, py, -0.015)), Vector((axis_x, py, -0.015)), grid, f'G1_YGrid_{idx}_{tick_idx}', radius=0.0025, vertices=6)
            create_axis(Vector((-0.045, py, 0.02)), Vector((0.045, py, 0.02)), white, f'G1_YTick_{idx}_{tick_idx}', radius=0.005, vertices=6)
            create_text_label(str(tick_label), (-0.10, py, 0.02), 0.17, f'G1_YTickLabel_{idx}_{tick_idx}', align_x='RIGHT')
        if band.get('constant'):
            create_text_label(f"Constant: {_g1_format_value(band.get('raw_mean', 0.0), span)}", (axis_x - 0.08, top - 0.16, 0.02), 0.17, f'G1_ConstantLabel_{idx}', align_x='RIGHT')
        if show_mean and band.get('mean') is not None:
            mean = float(band['mean'])
            py = bottom + ((mean - low) / max(high - low, 1e-12)) * (top - bottom)
            create_axis(Vector((0, py, 0.005)), Vector((axis_x, py, 0.005)), mean_color, f'G1_Mean_{idx}', radius=0.0035, vertices=6)
            create_text_label(f"{(band.get('semantic') or {}).get('mean_label') or tr(scn, 'Mean')}: {_g1_format_value(mean, span)}", (axis_x - 0.06, py + 0.10, 0.02), 0.16, f'G1_MeanLabel_{idx}', align_x='RIGHT')


def _draw_g1_overlay_axes(scn, x_range, metrics, show_mean=False, csv_spans=None, x_label='Session duration (h)', x_tick_data=None):
    """Draw one shared plot area with an explicitly independent real range per metric."""
    white = (0.92, 0.92, 0.92, 1.0)
    muted = (0.34, 0.34, 0.34, 1.0)
    grid = (0.20, 0.20, 0.20, 1.0)
    mean_color = (0.55, 0.55, 0.55, 1.0)
    axis_x = float(scn.axis_scale_x)
    axis_y = float(scn.axis_scale_y)
    bottom = axis_y * 0.06
    top = axis_y * 0.96
    x0, x1 = x_range
    x_span = x1 - x0

    if x_tick_data:
        ticks_x, tick_labels_x = x_tick_data
    else:
        ticks_x = _g1_ticks(x_range, 5)
        tick_labels_x = [_g1_format_value(tick, x_span) for tick in ticks_x]
    create_axis(Vector((0, bottom, 0.02)), Vector((axis_x, bottom, 0.02)), white, 'G1_Axis_X', radius=0.010, vertices=8)
    for idx, tick in enumerate(ticks_x):
        px = 0.0 if x1 == x0 else ((tick - x0) / (x1 - x0)) * axis_x
        create_axis(Vector((px, bottom - 0.045, 0.02)), Vector((px, bottom + 0.045, 0.02)), white, f'G1_XTick_{idx}', radius=0.006, vertices=6)
        label_x = tick_labels_x[idx] if idx < len(tick_labels_x) else _g1_format_value(tick, x_span)
        create_text_label(label_x, (px, bottom - 0.30, 0.02), 0.20, f'G1_XTickLabel_{idx}', align_x='CENTER')
        create_axis(Vector((px, bottom, -0.018)), Vector((px, top, -0.018)), grid, f'G1_XGrid_{idx}', radius=0.0020, vertices=6)
    create_text_label(x_label, (axis_x * 0.5, bottom - 0.62, 0.02), 0.25, 'G1_Label_X', align_x='CENTER')

    # A neutral normalized guide only; numeric values are listed per metric.
    for idx, fraction in enumerate((0.0, 1/3, 2/3, 1.0)):
        py = bottom + fraction * (top - bottom)
        create_axis(Vector((0, py, -0.015)), Vector((axis_x, py, -0.015)), grid, f'G1_OverlayGrid_{idx}', radius=0.0025, vertices=6)

    if csv_spans and len(csv_spans) > 1:
        ordered = sorted(csv_spans, key=lambda item: item[0])
        for idx in range(len(ordered) - 1):
            left_end, right_start = ordered[idx][1], ordered[idx + 1][0]
            if right_start > left_end:
                divider_x = ((left_end + right_start) * 0.5 - x0) / max(x_span, 1e-12) * axis_x
                create_axis(Vector((divider_x, bottom, -0.01)), Vector((divider_x, top, -0.01)), grid, f'G1_CSVDivider_{idx}', radius=0.004, vertices=6)

    # Independent scale/help cards on the right.  In overlay mode every metric
    # may have up to four text lines, so a compact row_step causes collisions.
    # Cards are therefore laid out in one or two columns with a fixed block
    # height.  The viewport framing includes these objects automatically.
    card_start_x = axis_x + 0.45
    column_gap = 4.85
    card_height = 0.92
    max_rows_per_column = 4
    column_count = 1 if len(metrics) <= max_rows_per_column else 2
    create_text_label('Independent Y ranges', (card_start_x, top + 0.16, 0.02), 0.22, 'G1_OverlayScaleTitle', color=white, align_x='LEFT')

    for idx, metric in enumerate(metrics):
        column = idx // max_rows_per_column if column_count > 1 else 0
        row = idx % max_rows_per_column if column_count > 1 else idx
        card_x = card_start_x + column * column_gap
        y = top - 0.18 - row * card_height
        low, high = metric['range']
        span = high - low
        label = metric['label']
        range_text = f"{_g1_format_value(low, span)} … {_g1_format_value(high, span)}"

        # A subtle separator makes every metric read as an independent card.
        create_axis(
            Vector((card_x - 0.08, y + 0.16, -0.015)),
            Vector((card_x + 4.25, y + 0.16, -0.015)),
            grid,
            f'G1_OverlayCardSeparator_{idx}',
            radius=0.0025,
            vertices=6,
        )
        create_text_label(label, (card_x, y, 0.02), 0.19, f'G1_OverlayMetric_{idx}', color=white, align_x='LEFT')
        create_text_label(range_text, (card_x, y - 0.20, 0.02), 0.15, f'G1_OverlayRange_{idx}', color=white, align_x='LEFT')

        semantic = metric.get('semantic') or {}
        next_line_y = y - 0.39
        if semantic.get('description'):
            create_text_label(semantic['description'], (card_x, next_line_y, 0.02), 0.125, f'G1_OverlayMeaning_{idx}', color=white, align_x='LEFT')
            next_line_y -= 0.19
        if semantic.get('summary'):
            create_text_label(semantic['summary'], (card_x, next_line_y, 0.02), 0.125, f'G1_OverlaySummary_{idx}', color=white, align_x='LEFT')
            next_line_y -= 0.19

        if metric.get('constant'):
            create_text_label(
                f"Constant: {_g1_format_value(metric.get('raw_mean', 0.0), span)}",
                (card_x, next_line_y, 0.02),
                0.13,
                f'G1_OverlayConstant_{idx}',
                color=white,
                align_x='LEFT',
            )
        elif show_mean and metric.get('mean') is not None:
            mean = float(metric['mean'])
            py = bottom + ((mean - low) / max(high - low, 1e-12)) * (top - bottom)
            # Short reference segment, not a full-width line, to avoid confusing scales.
            create_axis(Vector((axis_x * 0.86, py, 0.005 + idx * 0.001)), Vector((axis_x, py, 0.005 + idx * 0.001)), mean_color, f'G1_OverlayMean_{idx}', radius=0.0035, vertices=6)
            create_text_label(
                f"Mean {_g1_format_value(mean, span)}",
                (card_x, next_line_y, 0.02),
                0.13,
                f'G1_OverlayMeanLabel_{idx}',
                color=white,
                align_x='LEFT',
            )

    create_text_label('Overlay · independent Y scale per metric', (axis_x * 0.5, top + 0.10, 0.02), 0.18, 'G1_OverlayNotice', color=muted, align_x='CENTER')
    return bottom, top

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
        if not y_metrics:
            report({'ERROR'}, "Interaction needs at least one selected Y metric; X is always time")
            return {'CANCELLED'}

        window_size = max(1, int(getattr(scn, "anali_g1_window_size", 20)))
        window_start = max(0, int(getattr(scn, "anali_g1_window_start", 0)))
        global_view = bool(getattr(scn, "anali_g1_global_view", True))
        show_mean = bool(getattr(scn, "anali_g1_show_mean", False))
        display_mode = getattr(scn, "anali_g1_display_mode", "BANDS")
        target_scene = get_or_create_graph_scene("Interaction_Comparative")
        switch_to_scene(target_scene); clear_previous_graphs(target_scene); hide_non_graph_objects(target_scene)

        prepared, window_x_arrays, window_real_x_arrays = [], [], []
        metric_values = {key: [] for key in y_metrics}
        for csv_idx, csv_path in enumerate(selected_csvs):
            csv_name = os.path.basename(csv_path)
            try:
                _, data = read_csv(csv_path)
                metrics = compute_metrics_for_csv(data, max_reasonable_speed=getattr(context.scene, "max_reasonable_speed", DEFAULT_MAX_REASONABLE_SPEED))
                x_base = _g1_series_array(metrics.get(key_x, []))
                if global_view:
                    display_x_base = _g1_global_sample_progress_x(x_base)
                    real_x_window = np.asarray(x_base, dtype=float)
                else:
                    # Window curves use row positions for spacing, while tick labels
                    # preserve the real session-duration values from visible rows.
                    display_x_base = np.arange(x_base.size, dtype=float)
                    real_x_window = np.asarray(x_base[window_start:window_start + window_size], dtype=float)
                x_window = np.asarray(display_x_base if global_view else display_x_base[window_start:window_start + window_size], dtype=float)
                x_window = x_window[np.isfinite(x_window)]
                real_x_window = real_x_window[np.isfinite(real_x_window)]
                if x_window.size:
                    window_x_arrays.append(x_window)
                if real_x_window.size:
                    window_real_x_arrays.append(real_x_window)
            except Exception as exc:
                print(f"[interaction comparative] {csv_path}: {exc}"); continue
            for metric_idx, key_y in enumerate(y_metrics):
                segments = _g1_window_segments(display_x_base, _g1_series_array(metrics.get(key_y, [])), window_start, window_size, global_view)
                if not segments:
                    continue
                y_concat = np.concatenate([seg[1] for seg in segments])
                metric_values[key_y].append(y_concat)
                prepared.append({
                    "csv_name": csv_name,
                    "csv_index": csv_idx,
                    "metric_key": key_y,
                    "metric_index": metric_idx,
                    "segments": segments,
                    "x_all": np.concatenate([seg[0] for seg in segments]),
                    "y_all": y_concat,
                })

        if not prepared:
            report({'ERROR'}, "Interaction comparison could not generate data for this window")
            return {'CANCELLED'}
        plotted_x_arrays = [item["x_all"] for item in prepared if np.asarray(item["x_all"]).size]
        if global_view:
            x_range = _g1_active_x_range(window_x_arrays or plotted_x_arrays)
            x_tick_data = None
        else:
            shown_count = max((len(arr) for arr in window_x_arrays), default=1)
            x_range = (float(window_start), float(window_start + max(1, shown_count - 1)))
            x_tick_data = _g1_window_tick_data(x_range, window_real_x_arrays[0] if window_real_x_arrays else [])
        ranges = {key: _g1_real_range(arrays) for key, arrays in metric_values.items()}
        bands=[]
        if display_mode == 'OVERLAY':
            overlay_bottom = float(scn.axis_scale_y) * 0.06
            overlay_top = float(scn.axis_scale_y) * 0.96
            for metric_idx, key in enumerate(y_metrics):
                vals=np.concatenate(metric_values[key]) if metric_values[key] else np.asarray([])
                bands.append({"label": tr(scn, ANALYSIS.get(key, {}).get("label", key)), "bottom": overlay_bottom, "top": overlay_top, "range": ranges[key], "mean": float(np.mean(vals)) if vals.size else None, "raw_mean": float(np.mean(vals)) if vals.size else None, "constant": bool(vals.size and float(np.max(vals) - np.min(vals)) <= 1e-12), "semantic": _g1_semantic_info(scn, key, [item.get('y_all', item.get('y', [])) for item in prepared if item['metric_key'] == key])})
        else:
            band_gap = float(scn.axis_scale_y) * 0.09
            band_height = (float(scn.axis_scale_y) - band_gap * max(0, len(y_metrics)-1)) / len(y_metrics)
            for metric_idx, key in enumerate(y_metrics):
                bottom = metric_idx * (band_height + band_gap); top = bottom + band_height
                vals=np.concatenate(metric_values[key]) if metric_values[key] else np.asarray([])
                bands.append({"label": tr(scn, ANALYSIS.get(key, {}).get("label", key)), "bottom": bottom + band_height * 0.08, "top": top - band_height * 0.08, "range": ranges[key], "mean": float(np.mean(vals)) if vals.size else None, "raw_mean": float(np.mean(vals)) if vals.size else None, "constant": bool(vals.size and float(np.max(vals) - np.min(vals)) <= 1e-12), "semantic": _g1_semantic_info(scn, key, [item.get('y_all', item.get('y', [])) for item in prepared if item['metric_key'] == key])})
        for item in prepared:
            band=bands[item['metric_index']]
            z_offset = item['csv_index'] * 0.08 + (item['metric_index'] * 0.006 if display_mode == 'OVERLAY' else 0.0)
            for seg_idx, (seg_x, seg_y) in enumerate(item['segments']):
                display_y = _g1_band_y(seg_y, band['range'], band['bottom'], band['top'])
                create_interaction_graph_3d(seg_x, display_y, z_offset, scn.axis_scale_x, scn.axis_scale_y,
                    csv_name=item['csv_name'], metric_name=f"{key_x}_{item['metric_key']}_{seg_idx}", color=csv_color_by_index(item['csv_index'], palette_name),
                    x_range=x_range, y_range=(0.0, float(scn.axis_scale_y)))
            _draw_g1_gap_markers(scn, item['segments'], band, x_range, z_offset, f"G1Gap_{item['csv_index']}_{item['metric_index']}")
        csv_spans = []
        for csv_idx in sorted({item['csv_index'] for item in prepared}):
            xs = np.concatenate([item['x_all'] for item in prepared if item['csv_index'] == csv_idx])
            if xs.size:
                csv_spans.append((float(np.min(xs)), float(np.max(xs))))
        x_axis_label = tr(scn, "Session progress (%)") if global_view else tr(scn, "Session duration (h)")
        if display_mode == 'OVERLAY':
            _draw_g1_overlay_axes(scn, x_range, bands, show_mean=show_mean, csv_spans=csv_spans, x_label=x_axis_label, x_tick_data=x_tick_data)
        else:
            _draw_g1_axes_and_bands(scn, x_range, bands, show_mean=show_mean, csv_spans=csv_spans, x_label=x_axis_label, x_tick_data=x_tick_data)
        shown = max((len(arr) for arr in (window_x_arrays or plotted_x_arrays)), default=0)
        create_text_label("Interaction", (scn.axis_scale_x * 0.5, scn.axis_scale_y + 0.68, 0.12), 0.40, "GraphTitle_G1", align_x="CENTER")
        subtitle = f"{tr(scn, 'All data')} · {shown} {tr(scn, 'samples')}" if global_view else f"Rows {window_start + 1}–{window_start + shown} · {shown} {tr(scn, 'samples')}"
        create_text_label(subtitle, (scn.axis_scale_x * 0.5, scn.axis_scale_y + 0.38, 0.12), 0.22, "GraphSubtitle_G1", align_x="CENTER")
        _g1_reduce_viewport_noise(context)
        draw_csv_color_legend(csv_items=[{"name": os.path.basename(path), "color": csv_color_by_index(i, palette_name)} for i, path in enumerate(selected_csvs)], axis_scale_x=scn.axis_scale_x, axis_scale_y=scn.axis_scale_y, z_pos=0.15, title="CSV")
        frame_graph_camera(target_scene, scn)
        return {'FINISHED'}

    # FOREST COMPARATIVE

    if graph_type == "G2":

        if len(selected_csvs) < 2:
            report({'ERROR'}, "Forest plot needs at least two selected CSV files")
            return {'CANCELLED'}

        metric_keys = [item.key for item in selected_items]

        if len(metric_keys) < 1:
            report({'ERROR'}, "Forest plot needs at least one selected metric")
            return {'CANCELLED'}

        target_scene = get_or_create_graph_scene("Forest_ZScore")

        switch_to_scene(target_scene)
        clear_previous_graphs(target_scene)
        hide_non_graph_objects(target_scene)

        computed_metrics = []
        for csv_path in selected_csvs:
            csv_name = os.path.basename(csv_path)
            try:
                _, data = read_csv(csv_path)
                metrics = compute_metrics_for_csv(
                    data,
                    max_reasonable_speed=getattr(context.scene, "max_reasonable_speed", DEFAULT_MAX_REASONABLE_SPEED),
                )
                computed_metrics.append((csv_name, metrics))
            except Exception as exc:
                print(f"[forest plot z-score] {csv_path}: {exc}")

        if len(computed_metrics) < 2:
            report({'ERROR'}, "Forest plot needs at least two readable CSV files")
            return {'CANCELLED'}

        groups = []
        for metric_key in metric_keys:
            metric_label = ANALYSIS.get(metric_key, {}).get("label", metric_key)
            reference = forest_zscore_reference(metric_key, [metrics for _csv_name, metrics in computed_metrics])
            if reference is None:
                continue
            rows = []
            for csv_idx, (csv_name, metrics) in enumerate(computed_metrics):
                try:
                    row = forest_zscore_row_stats(
                        metric_key,
                        metrics,
                        csv_name,
                        reference_mean=reference["mean"],
                        reference_std=reference["std"],
                    )
                except Exception as exc:
                    print(f"[forest plot z-score row] {csv_name} / {metric_key}: {exc}")
                    row = None
                if row is not None:
                    row["color_index"] = csv_idx
                    rows.append(row)
            if len(rows) >= 2:
                groups.append({
                    "label": metric_label,
                    "rows": rows,
                    "reference_mean": reference["mean"],
                    "reference_std": reference["std"],
                    "reference_n": reference["n_total"],
                })

        if not groups:
            report({'ERROR'}, "Forest plot needs at least one metric with data in at least two CSV files and non-zero variance")
            return {'CANCELLED'}

        total_rows = sum(len(group["rows"]) + 1 for group in groups)
        graph_data = draw_multi_metric_forest_plot_3d(
            groups,
            axis_scale_x=scn.axis_scale_x,
            axis_scale_y=max(scn.axis_scale_y, total_rows * 0.48),
            z_pos=0.0,
            scale_label="z-score",
            palette_name=palette_name,
        )

        # Forest plots already contain their own statistical axis and reference
        # line. Hide Blender's floor grid, world axes and 3D cursor so they do
        # not compete visually with the plot.
        _g1_reduce_viewport_noise(context)
        frame_graph_camera(target_scene, scn)

        metric_word = "metric" if len(groups) == 1 else "metrics"
        report({'INFO'}, f"Forest z-score plot generated for {len(groups)} {metric_word}")
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

        labels = [
            tr(scn, ANALYSIS.get(key, {}).get("label", key))
            for key in metric_keys
        ]
        raw_series = []

        for idx, csv_path in enumerate(selected_csvs):
            csv_name = os.path.basename(csv_path)
            try:
                _, data = read_csv(csv_path)
                metrics = compute_metrics_for_csv(
                    data,
                    max_reasonable_speed=getattr(
                        context.scene,
                        "max_reasonable_speed",
                        DEFAULT_MAX_REASONABLE_SPEED,
                    ),
                )
            except Exception as exc:
                print(f"[radar comparative] {csv_path}: {exc}")
                continue

            values = []
            valid = True
            for key in metric_keys:
                value, unit = radar_summary_value(key, metrics.get(key, []))
                if value is None or not np.isfinite(value):
                    valid = False
                    break
                values.append(float(value))

            if valid and values:
                raw_series.append({
                    "idx": idx,
                    "name": csv_name,
                    "values": np.asarray(values, dtype=float),
                })

        if raw_series:
            matrix = np.vstack([item["values"] for item in raw_series])
            if use_log_scale:
                matrix = _signed_log10_1p(matrix)

            # Each radar axis is normalized independently using the real
            # minimum and maximum observed for that metric across all selected
            # CSV files. This keeps 0–1 metrics readable beside 0–2000 metrics
            # without mixing incompatible units or magnitude groups.
            margin = float(getattr(scn, "anali_radar_margin", 0.10))
            margin = min(max(margin, 0.0), 0.20)
            usable_radius = max(1.0 - 2.0 * margin, 0.0)

            normalized = np.zeros_like(matrix, dtype=float)
            radar_ranges = []
            for col_idx, key in enumerate(metric_keys):
                column = np.asarray(matrix[:, col_idx], dtype=float)
                finite_column = column[np.isfinite(column)]
                if finite_column.size == 0:
                    minimum, maximum = 0.0, 1.0
                    column_normalized = np.full(column.shape, 0.5, dtype=float)
                else:
                    minimum = float(np.min(finite_column))
                    maximum = float(np.max(finite_column))
                    span = maximum - minimum
                    if abs(span) <= 1e-12:
                        column_normalized = np.full(column.shape, 0.5, dtype=float)
                    else:
                        column_normalized = np.clip(
                            (column - minimum) / span,
                            0.0,
                            1.0,
                        )
                normalized[:, col_idx] = margin + column_normalized * usable_radius
                radar_ranges.append((minimum, maximum))

            normalized = np.clip(normalized, margin, 1.0 - margin)

            radar_series = []
            for row_idx, item in enumerate(raw_series):
                color = csv_color_by_index(item["idx"], palette_name)
                draw_radar_graph_3d_filled(
                    normalized[row_idx].tolist(),
                    axis_scale_x=scn.axis_scale_x,
                    axis_scale_y=scn.axis_scale_y,
                    z_pos=row_idx * 0.03,
                    labels=labels if row_idx == 0 else [],
                    color=color,
                    csv_name=f"radar_{row_idx}_{sanitize_name(item['name'])}",
                    values_are_normalized=True,
                    radar_margin=margin,
                    draw_margin_guides=(row_idx == 0),
                    margin_labels=None,
                )
                radar_series.append({
                    "name": item["name"],
                    "color": color,
                })
        else:
            radar_series = []

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
        radar_margin_pct = int(round(float(getattr(scn, "anali_radar_margin", 0.10)) * 100.0))
        scale_name = "log10(1+x)" if use_log_scale else "per-metric min-max"
        create_text_label(
            f"Radar plot · CSV comparison · {scale_name} · margin {radar_margin_pct}%",
            (scn.axis_scale_x * 0.5, scn.axis_scale_y + 0.85, 0.12),
            0.42,
            "GraphTitle_G3",
            align_x="CENTER",
        )

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
            if not y_metrics:
                report({'ERROR'}, "Interaction needs at least one selected Y metric; X is always time")
                return {'CANCELLED'}
            window_size=max(1, int(getattr(scn, "anali_g1_window_size", 20)))
            window_start=max(0, int(getattr(scn, "anali_g1_window_start", 0)))
            global_view=bool(getattr(scn, "anali_g1_global_view", True))
            show_mean=bool(getattr(scn, "anali_g1_show_mean", False))
            display_mode=getattr(scn, "anali_g1_display_mode", "BANDS")
            x_base=_g1_series_array(metrics.get(key_x, [])); prepared=[]; metric_values={}
            if global_view:
                display_x_base=_g1_global_sample_progress_x(x_base)
                real_x_window=np.asarray(x_base,dtype=float)
            else:
                # Plot visible rows at equal horizontal distances and keep their
                # real time values only as X-axis labels.
                display_x_base=np.arange(x_base.size,dtype=float)
                real_x_window=np.asarray(x_base[window_start:window_start+window_size],dtype=float)
            x_window=np.asarray(display_x_base if global_view else display_x_base[window_start:window_start+window_size],dtype=float)
            x_window=x_window[np.isfinite(x_window)]
            real_x_window=real_x_window[np.isfinite(real_x_window)]
            for metric_idx,key_y in enumerate(y_metrics):
                segments=_g1_window_segments(display_x_base, _g1_series_array(metrics.get(key_y, [])), window_start, window_size, global_view)
                if not segments: continue
                y_concat=np.concatenate([seg[1] for seg in segments])
                metric_values[key_y]=[y_concat]
                prepared.append({"metric_key":key_y,"metric_index":metric_idx,"segments":segments,"x_all":np.concatenate([seg[0] for seg in segments]),"y_all":y_concat})
            if not prepared:
                report({'ERROR'}, "Interaction could not generate valid data for this window"); return {'CANCELLED'}
            plotted_x_arrays=[item["x_all"] for item in prepared if np.asarray(item["x_all"]).size]
            if global_view:
                x_range=_g1_active_x_range(([x_window] if x_window.size else []) or plotted_x_arrays)
                x_tick_data=None
            else:
                shown_count=max(1, int(x_window.size))
                x_range=(float(window_start), float(window_start + max(1, shown_count - 1)))
                x_tick_data=_g1_window_tick_data(x_range, real_x_window)
            ranges={key:_g1_real_range(arrays) for key,arrays in metric_values.items()}
            bands=[]
            if display_mode == 'OVERLAY':
                overlay_bottom=float(scn.axis_scale_y)*0.06; overlay_top=float(scn.axis_scale_y)*0.96
                for idx,key in enumerate(y_metrics):
                    vals=metric_values.get(key,[np.asarray([])])[0]
                    bands.append({"label":tr(scn, ANALYSIS.get(key,{}).get("label",key)),"bottom":overlay_bottom,"top":overlay_top,"range":ranges.get(key,(0,1)),"mean":float(np.mean(vals)) if vals.size else None,"raw_mean":float(np.mean(vals)) if vals.size else None,"constant":bool(vals.size and float(np.max(vals)-np.min(vals)) <= 1e-12),"semantic":_g1_semantic_info(scn,key,[item.get('y_all', item.get('y', [])) for item in prepared if item['metric_key']==key])})
            else:
                gap=float(scn.axis_scale_y)*0.09
                height=(float(scn.axis_scale_y)-gap*max(0,len(y_metrics)-1))/len(y_metrics)
                for idx,key in enumerate(y_metrics):
                    bottom=idx*(height+gap); top=bottom+height; vals=metric_values.get(key,[np.asarray([])])[0]
                    bands.append({"label":tr(scn, ANALYSIS.get(key,{}).get("label",key)),"bottom":bottom+height*0.08,"top":top-height*0.08,"range":ranges.get(key,(0,1)),"mean":float(np.mean(vals)) if vals.size else None,"raw_mean":float(np.mean(vals)) if vals.size else None,"constant":bool(vals.size and float(np.max(vals)-np.min(vals)) <= 1e-12),"semantic":_g1_semantic_info(scn,key,[item.get('y_all', item.get('y', [])) for item in prepared if item['metric_key']==key])})
            for item in prepared:
                band=bands[item['metric_index']]
                z_offset=item['metric_index']*0.012 if display_mode == 'OVERLAY' else item['metric_index']*0.02
                for seg_idx,(seg_x,seg_y) in enumerate(item['segments']):
                    display_y=_g1_band_y(seg_y,band['range'],band['bottom'],band['top'])
                    create_interaction_graph_3d(seg_x,display_y,z_offset,scn.axis_scale_x,scn.axis_scale_y,csv_name=csv_name,metric_name=f"{key_x}_{item['metric_key']}_{seg_idx}",color=color,x_range=x_range,y_range=(0.0,float(scn.axis_scale_y)))
                _draw_g1_gap_markers(scn, item['segments'], band, x_range, z_offset, f"G1Gap_single_{item['metric_index']}")
            x_axis_label=tr(scn, "Session progress (%)") if global_view else tr(scn, "Session duration (h)")
            if display_mode == 'OVERLAY':
                _draw_g1_overlay_axes(scn,x_range,bands,show_mean=show_mean,csv_spans=None,x_label=x_axis_label,x_tick_data=x_tick_data)
            else:
                _draw_g1_axes_and_bands(scn,x_range,bands,show_mean=show_mean,csv_spans=None,x_label=x_axis_label,x_tick_data=x_tick_data)
            shown=max(([len(x_window)] if x_window.size else []) + [len(item['x_all']) for item in prepared])
            create_text_label("Interaction",(scn.axis_scale_x*0.5,scn.axis_scale_y+0.68,0.12),0.40,"GraphTitle_G1",align_x="CENTER")
            subtitle=f"{tr(scn, 'All data')} · {shown} {tr(scn, 'samples')}" if global_view else f"Rows {window_start+1}–{window_start+shown} · {shown} {tr(scn, 'samples')}"
            create_text_label(subtitle,(scn.axis_scale_x*0.5,scn.axis_scale_y+0.38,0.12),0.22,"GraphSubtitle_G1",align_x="CENTER")
            _g1_reduce_viewport_noise(context)
            draw_csv_color_legend(csv_items=[{"name":csv_name,"color":color}],axis_scale_x=scn.axis_scale_x,axis_scale_y=scn.axis_scale_y,z_pos=0.15,title="CSV")
            frame_graph_camera(target_scene,scn)
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
