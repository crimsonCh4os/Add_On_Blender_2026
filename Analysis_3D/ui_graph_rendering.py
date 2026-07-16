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

"""Matplotlib-to-Blender rendering helpers for graph backgrounds."""

import os

import bpy
import numpy as np

try:
    from .analytics import clamp_outliers, sanitize_name, series_to_array
    from .graphs import get_color_for_csv
except ImportError:  # pragma: no cover - direct execution in Blender scripts
    from analytics import clamp_outliers, sanitize_name, series_to_array
    from graphs import get_color_for_csv



def _local_series_to_array(values):
    """Small local fallback so rendering never depends on wildcard imports/cache."""
    if values is None:
        return np.asarray([], dtype=float)
    arr = np.asarray(list(values), dtype=float)
    return arr[np.isfinite(arr)] if arr.size else arr
if "series_to_array" not in globals():
    series_to_array = _local_series_to_array

def _figure_to_blender_image(fig, image_name):
    """Convierte una figura Matplotlib a imagen Blender sin escribir PNG temporal."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

    canvas = FigureCanvas(fig)
    canvas.draw()
    width, height = canvas.get_width_height()
    rgba = np.asarray(canvas.buffer_rgba(), dtype=np.float32) / 255.0

    # Evita que iteraciones sucesivas de Matplotlib dejen imágenes huérfanas
    # empaquetadas en el .blend. Las imágenes Graph_* sin usuarios pertenecen
    # a renders anteriores y pueden eliminarse.
    for old_img in list(bpy.data.images):
        if old_img.name.startswith("Graph_") and old_img.users == 0:
            bpy.data.images.remove(old_img)

    img = bpy.data.images.get(image_name)
    if img is None or img.size[0] != width or img.size[1] != height:
        if img is not None:
            bpy.data.images.remove(img)
        img = bpy.data.images.new(image_name, width=width, height=height, alpha=True)
    img.pixels.foreach_set(rgba.ravel())
    img.pack()
    img.update()
    return img

def create_matplotlib_graph(values_x, values_y=None, csv_name="CSV", metric_name="Metric", graph_type="G1"):
    import matplotlib.pyplot as plt

    to_array = globals().get("series_to_array", _local_series_to_array)
    values_x = to_array(values_x)
    values_y = to_array(values_y)
    metric_name = metric_name or "Metric"

    if graph_type == "G1" and (values_x.size == 0 or values_y.size == 0):
        return None
    if graph_type in {"G2", "G3"} and values_x.size == 0:
        return None

    color = get_color_for_csv(csv_name)
    fig = plt.figure(figsize=(6.8, 5.2), dpi=150, facecolor="#f6f3eb")
    ax = fig.add_subplot(111, polar=(graph_type == "G3"))
    ax.set_facecolor("#fffaf0")

    try:
        if graph_type == "G1":
            values_x = clamp_outliers(values_x)
            values_y = clamp_outliers(values_y)
            ax.plot(values_x, values_y, linewidth=2.2, color=color[:3])
            ax.fill_between(values_x, values_y, alpha=0.18, color=color[:3])
            ax.scatter(values_x, values_y, s=12, color=color[:3])
            ax.set_xlabel("Frame / fila CSV")
            ax.set_ylabel(metric_name)
        elif graph_type == "G2":
            mean_val = float(np.mean(values_x))
            std_val = float(np.std(values_x, ddof=1)) if len(values_x) > 1 else 0.0
            ci = 1.96 * std_val / np.sqrt(max(len(values_x), 1))
            ax.errorbar(mean_val, 0, xerr=ci, fmt="o", color=color[:3], capsize=6)
            ax.axvline(mean_val, linestyle="--", color="black")
            ax.set_yticks([0])
            ax.set_yticklabels([metric_name])
        elif graph_type == "G3":
            vals = values_x.copy()
            angles = np.linspace(0, 2 * np.pi, len(vals), endpoint=False)
            angles = np.append(angles, angles[0])
            vals = np.append(vals, vals[0])
            ax.plot(angles, vals, color=color[:3])
            ax.fill(angles, vals, color=color[:3], alpha=0.25)
        else:
            return None

        ax.set_title(f"{metric_name} ({csv_name})", fontsize=16, pad=18)
        ax.tick_params(axis="both", labelsize=12)
        ax.xaxis.label.set_size(13)
        ax.yaxis.label.set_size(13)
        if graph_type != "G3":
            ax.grid(True)

        x_min = float(np.min(values_x)) if values_x.size else 0.0
        x_max = float(np.max(values_x)) if values_x.size else 1.0
        if x_min == x_max:
            x_ticks = [x_min]
        else:
            x_ticks = list(np.linspace(x_min, x_max, 5))

        y_source = values_y if values_y.size else np.asarray([0.0, 1.0])
        y_min = float(np.min(y_source))
        y_max = float(np.max(y_source))
        if y_min == y_max:
            y_ticks = [y_min]
        else:
            y_ticks = list(np.linspace(y_min, y_max, 5))

        safe_csv = sanitize_name(csv_name)
        safe_metric = sanitize_name(metric_name)
        fig.tight_layout(pad=2.2)
        img = _figure_to_blender_image(fig, f"Graph_{safe_csv}_{safe_metric}_{graph_type}")
        plt.close(fig)
        return {
            "image": img,
            "x_range": (x_min, x_max),
            "y_range": (y_min, y_max),
            "x_ticks": x_ticks,
            "y_ticks": y_ticks,
        }
    except Exception as exc:
        print(f"[create_matplotlib_graph] {exc}")
        plt.close(fig)
        return None



def create_comparative_interaction_matplotlib(series, metric_name="Metric"):
    """Create one Matplotlib image containing all selected CSV interaction curves."""
    import matplotlib.pyplot as plt

    to_array = globals().get("series_to_array", _local_series_to_array)
    clean_series = []
    for item in series or []:
        x = to_array(item.get("x"))
        y = to_array(item.get("y"))
        if x.size == 0 or y.size == 0:
            continue
        n = min(x.size, y.size)
        clean_series.append({
            "name": item.get("name", "CSV"),
            "x": x[:n],
            "y": y[:n],
            "color": item.get("color", (0.2, 0.6, 1.0, 1.0)),
        })

    if not clean_series:
        return None

    fig = plt.figure(figsize=(7.2, 5.4), dpi=150, facecolor="#f6f3eb")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#fffaf0")

    all_x = []
    all_y = []
    for item in clean_series:
        color = item["color"][:3]
        x_clamped = clamp_outliers(item["x"])
        y_clamped = clamp_outliers(item["y"])
        ax.plot(x_clamped, y_clamped, linewidth=2.0, color=color, label=os.path.basename(item["name"]))
        ax.fill_between(x_clamped, y_clamped, alpha=0.10, color=color)
        all_x.extend(x_clamped.tolist())
        all_y.extend(y_clamped.tolist())

    ax.set_title(f"{metric_name} · Interaction comparison", fontsize=16, pad=18)
    ax.set_xlabel("Frame / fila CSV")
    ax.set_ylabel(metric_name)
    ax.grid(True)
    ax.tick_params(axis="both", labelsize=12)
    ax.xaxis.label.set_size(13)
    ax.yaxis.label.set_size(13)
    ax.legend(loc="best", fontsize=10, frameon=True)

    x_min = float(np.min(all_x)) if all_x else 0.0
    x_max = float(np.max(all_x)) if all_x else 1.0
    y_min = float(np.min(all_y)) if all_y else 0.0
    y_max = float(np.max(all_y)) if all_y else 1.0
    x_ticks = [x_min] if x_min == x_max else list(np.linspace(x_min, x_max, 5))
    y_ticks = [y_min] if y_min == y_max else list(np.linspace(y_min, y_max, 5))

    try:
        safe_metric = sanitize_name(metric_name)
        fig.tight_layout(pad=2.2)
        img = _figure_to_blender_image(fig, f"Graph_InteractionComparative_{safe_metric}")
        plt.close(fig)
        return {
            "image": img,
            "x_range": (x_min, x_max),
            "y_range": (y_min, y_max),
            "x_ticks": x_ticks,
            "y_ticks": y_ticks,
        }
    except Exception as exc:
        print(f"[create_comparative_interaction_matplotlib] {exc}")
        plt.close(fig)
        return None
