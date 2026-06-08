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

from __future__ import annotations

import math
import hashlib
import warnings
from collections.abc import Mapping, Sequence
from typing import Any
import bmesh
import bpy
import numpy as np
from math import pi, cos, sin
from mathutils import Vector, Matrix

try:
    from .constants import COLORBLIND_SAFE_PALETTE, COLOR_FAMILIES, SPHERE_INSTANCING_THRESHOLD, get_color_families
except ImportError:
    from constants import COLORBLIND_SAFE_PALETTE, COLOR_FAMILIES, SPHERE_INSTANCING_THRESHOLD, get_color_families


def create_emission_material(name: str, color: tuple[float, float, float, float], strength: float = 3.0) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    emission.inputs["Strength"].default_value = strength
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    mat.diffuse_color = color
    return mat


def _stable_palette_index(value: object, modulo: int) -> int:
    digest = hashlib.sha256(str(value or "CSV").encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % max(int(modulo), 1)


def _active_color_families(palette_name: str | None = None) -> list[list[tuple[float, float, float, float]]]:
    """Return color families for the selected palette.

    When no palette is provided, the module-level COLOR_FAMILIES keeps backward
    compatibility with older calls.
    """
    if palette_name:
        return get_color_families(palette_name, family_size=4)
    return COLOR_FAMILIES


def get_color_for_csv(csv_name: object, palette_name: str | None = None) -> tuple[float, float, float, float]:
    """Color estable y reproducible para un CSV."""
    families = _active_color_families(palette_name)
    fam = families[_stable_palette_index(csv_name, len(families))]
    return fam[1 % len(fam)]


def csv_color_by_index(index: int, palette_name: str | None = None) -> tuple[float, float, float, float]:
    families = _active_color_families(palette_name)
    family = families[int(index) % len(families)]
    return family[min(1, len(family) - 1)]


def metric_color_for_csv(csv_index: int, metric_index: int, palette_name: str | None = None) -> tuple[float, float, float, float]:
    families = _active_color_families(palette_name)
    family = families[int(csv_index) % len(families)]
    return family[int(metric_index) % len(family)]


GRAPH_OBJECT_PREFIXES = (
    "GraphPlane_", "GraphLineMesh_", "Scatter_", "Corr_", "Surface_", "Time_",
    "Forest", "Radar", "RadarFill_", "RadarRing_", "RadarAxis_", "RadarPoint_", "RadarLabel_",
    "Axis_", "Tick_", "Label_", "TickLabel_", "Num_",
    "InteractionBar_", "InteractionLine_", "InteractionPts_", "InteractionLabel_",
    "GraphTitle_", "TimePts_",
)

AXIS_OBJECT_PREFIXES = ("Axis_", "Tick_", "Label_", "TickLabel_", "Num_")


def _purge_unused_graph_datablocks() -> None:
    """Elimina datablocks huérfanos generados por las gráficas.

    La pasada incluye materiales antes que imágenes para liberar referencias de
    texturas Graph_* asociadas a planos ya borrados. Así se evita que el .blend
    crezca tras muchas regeneraciones de gráficas.
    """
    for collection in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.images):
        for datablock in list(collection):
            if datablock.users == 0:
                collection.remove(datablock)


def clear_previous_graphs(scene: bpy.types.Scene | None = None) -> None:
    """Remove generated graph objects before drawing a new graph.

    When a graph is regenerated for the same CSV, Blender keeps the graph scene in
    the .blend file. This cleanup prevents old objects from accumulating in that
    scene. If a scene is supplied, only objects in that graph scene are removed.
    """
    objects = list(scene.objects) if scene is not None else list(bpy.data.objects)
    for obj in objects:
        if obj.name.startswith(GRAPH_OBJECT_PREFIXES) or bool(obj.get("analysis3d_generated", False)):
            bpy.data.objects.remove(obj, do_unlink=True)
    _purge_unused_graph_datablocks()


def clear_scene(scene: bpy.types.Scene | None = None) -> None:
    """Compatibility alias used by older analisisV6 imports."""
    clear_previous_graphs(scene)


def clear_axes_objects(scene: bpy.types.Scene | None = None) -> None:
    """Remove only generated axes, ticks and text labels before redrawing axis values."""
    objects = list(scene.objects) if scene is not None else list(bpy.data.objects)
    for obj in objects:
        if obj.name.startswith(AXIS_OBJECT_PREFIXES):
            bpy.data.objects.remove(obj, do_unlink=True)
    _purge_unused_graph_datablocks()


def create_axis(start: Vector, end: Vector, color: tuple[float, float, float, float], name: str, radius: float = 0.03, vertices: int = 8) -> bpy.types.Object | None:
    """Crea un cilindro-eje sin bpy.ops para no depender del contexto activo."""
    vec = end - start
    length = vec.length
    if length <= 1e-9:
        return None

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=max(int(vertices), 3),
        radius1=radius,
        radius2=radius,
        depth=length,
    )
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    obj.location = (start + end) / 2
    obj.rotation_mode = 'QUATERNION'
    # El cilindro de bmesh nace alineado en Z; to_track_quat rota su eje local Z
    # hasta el vector destino y usa Y como eje de referencia para evitar roll aleatorio.
    obj.rotation_quaternion = vec.to_track_quat('Z', 'Y')
    mat = create_emission_material(f"{name}_Mat", color, 2.0)
    obj.data.materials.append(mat)
    obj["analysis3d_generated"] = True
    bpy.context.collection.objects.link(obj)
    return obj


def create_text_label(text: str, location: Vector | tuple[float, float, float], size: float, name: str, color: tuple[float, float, float, float] = (0.92, 0.92, 0.92, 1.0), align_x: str = "CENTER", align_y: str = "CENTER") -> bpy.types.Object:
    """Crea etiquetas de texto 3D compactas sin bpy.ops.object.text_add.

    Las etiquetas de los gráficos deben ser discretas: si son grandes se
    superponen con las curvas, la leyenda y la cámara ortográfica.
    """
    curve = bpy.data.curves.new(f"{name}_Curve", type='FONT')
    curve.body = str(text)
    curve.align_x = align_x
    curve.align_y = align_y
    # Blender no siempre trae una variante Bold disponible para el font interno.
    # Para que el texto sea legible desde la vista superior se simula negrita
    # con un pequeño grosor/extrusión en la propia curva de texto.
    curve.extrude = 0.004
    curve.bevel_depth = 0.006
    curve.bevel_resolution = 1
    curve.resolution_u = 2
    obj = bpy.data.objects.new(name, curve)
    obj.location = location
    obj.scale = (size, size, size)
    mat = create_emission_material(f"{name}_Mat", color, 1.8)
    obj.data.materials.append(mat)
    obj["analysis3d_generated"] = True
    bpy.context.collection.objects.link(obj)
    return obj


def _normalize(values: Sequence[float] | np.ndarray | None, scale: float) -> list[float]:
    values = list(values) if values is not None else []
    if len(values) == 0:
        return []
    min_v = min(values)
    max_v = max(values)
    rng = max(max_v - min_v, 1e-9)
    return [((v - min_v) / rng) * scale for v in values]


def _make_single_sphere_mesh(name: str, radius: float = 0.05, segments: int = 10, rings: int = 6) -> bpy.types.Mesh:
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=radius)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def _build_spheres_object(points: Sequence[Vector], name: str, color: tuple[float, float, float, float], radius: float = 0.05, segments: int = 10, rings: int = 6) -> bpy.types.Object | None:
    """Crea puntos 3D.

    Para datasets grandes usa instanciación de una única malla de esfera: reduce de
    forma drástica vertices duplicados, memoria y tiempo de bloqueo en Blender.
    Para datasets pequeños mantiene una malla unificada, que es cómoda para edición.
    """
    if not points:
        return None
    mat = create_emission_material(f"{name}_Mat", color, 2.0)

    if len(points) >= SPHERE_INSTANCING_THRESHOLD:
        mesh = _make_single_sphere_mesh(name, radius=radius, segments=segments, rings=rings)
        mesh.materials.append(mat)
        empty = bpy.data.objects.new(name, None)
        bpy.context.collection.objects.link(empty)
        empty.empty_display_type = 'SPHERE'
        empty.empty_display_size = radius
        empty["analysis3d_generated"] = True
        for idx, point in enumerate(points):
            obj = bpy.data.objects.new(f"{name}_inst_{idx:04d}", mesh)
            obj.location = point
            obj["analysis3d_generated"] = True
            bpy.context.collection.objects.link(obj)
            obj.parent = empty
        return empty

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    for point in points:
        ret = bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=radius)
        verts = ret.get('verts', [])
        if verts:
            bmesh.ops.translate(bm, verts=verts, vec=point)
    bm.to_mesh(mesh)
    bm.free()
    obj.data.materials.append(mat)
    obj["analysis3d_generated"] = True
    return obj


def draw_metric_line(name: str, values_x: Sequence[float], values_y: Sequence[float], values_z: Sequence[float] | None = None, color: tuple[float, float, float, float] | None = None, thickness: float = 0.02, axis_scale_x: float = 5, axis_scale_y: float = 5, axis_scale_z: float = 5, x_range: tuple[float, float] | None = None, y_range: tuple[float, float] | None = None, z_offset: float = 0, csv_name: str | None = None) -> bpy.types.Object | None:
    values_x = list(values_x) if values_x is not None else []
    values_y = list(values_y) if values_y is not None else []
    if len(values_x) == 0 or len(values_y) == 0:
        return None
    if color is None:
        color = get_color_for_csv(csv_name or name)
    if x_range is not None:
        min_x, max_x = x_range
        denom = max(max_x - min_x, 1e-9)
        values_x = [((v - min_x) / denom) * axis_scale_x for v in values_x]
    if y_range is not None:
        min_y, max_y = y_range
        denom = max(max_y - min_y, 1e-9)
        values_y = [((v - min_y) / denom) * axis_scale_y for v in values_y]
    if values_z is None:
        values_z = [z_offset for _ in values_x]
    else:
        values_z = [float(v) + z_offset for v in values_z]
    curve_data = bpy.data.curves.new(name=f"{name}_curve", type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = thickness
    spline = curve_data.splines.new('POLY')
    spline.points.add(len(values_x) - 1)
    for i, (x, y, z) in enumerate(zip(values_x, values_y, values_z)):
        spline.points[i].co = (x, y, z, 1)
    curve_obj = bpy.data.objects.new(name, curve_data)
    bpy.context.collection.objects.link(curve_obj)
    mat = create_emission_material(f"{name}_Mat", color, 2.0)
    curve_obj.data.materials.append(mat)
    curve_obj["analysis3d_generated"] = True
    return curve_obj


def draw_axes1(length_x: float = 5, length_y: float = 5, length_z: float = 5, labels: tuple[str, str, str] = ("X", "Y", "Z"), x_range: tuple[float, float] = (0, 1), y_range: tuple[float, float] = (0, 1), z_range: tuple[float, float] = (0, 1), x_ticks: Sequence[float] | None = None, y_ticks: Sequence[float] | None = None, z_ticks: Sequence[float] | None = None, tick_size: float = 0.1, text_size: float = 0.30) -> None:
    create_axis(Vector((0, 0, 0)), Vector((length_x, 0, 0)), (1, 0, 0, 1), "Axis_X")
    create_axis(Vector((0, 0, 0)), Vector((0, length_y, 0)), (0, 1, 0, 1), "Axis_Y")
    create_axis(Vector((0, 0, 0)), Vector((0, 0, length_z)), (0, 0, 1, 1), "Axis_Z")

    def map_value(value, rng, axis_len):
        vmin, vmax = rng
        denom = max(vmax - vmin, 1e-9)
        return ((value - vmin) / denom) * axis_len

    def draw_ticks(ticks, axis_index, rng, axis_len):
        if not ticks:
            return
        for idx, tick in enumerate(ticks):
            pos = map_value(tick, rng, axis_len)
            label = f"{tick:g}"
            if axis_index == 0:
                start = Vector((pos, -tick_size, 0)); end = Vector((pos, tick_size, 0)); text_loc = Vector((pos, -tick_size * 5.8, 0))
            elif axis_index == 1:
                start = Vector((-tick_size, pos, 0)); end = Vector((tick_size, pos, 0)); text_loc = Vector((-tick_size * 7.0, pos, 0))
            else:
                start = Vector((-tick_size, 0, pos)); end = Vector((tick_size, 0, pos)); text_loc = Vector((-tick_size * 6.0, 0, pos))
            create_axis(start, end, (0.2, 0.2, 0.2, 1), f"Tick_{axis_index}_{idx}", radius=0.01, vertices=6)
            create_text_label(label, text_loc, text_size, f"TickLabel_{axis_index}_{idx}")

    draw_ticks(x_ticks, 0, x_range, length_x)
    draw_ticks(y_ticks, 1, y_range, length_y)
    if z_ticks and labels[2]:
        draw_ticks(z_ticks, 2, z_range, length_z)

    axis_label_size = max(text_size * 1.45, 0.40)
    if labels[0]:
        create_text_label(labels[0], (length_x * 0.5, -tick_size * 9.2, 0), axis_label_size, "Label_X", (1, 0.35, 0.35, 1))
    if labels[1]:
        create_text_label(labels[1], (-tick_size * 10.0, length_y * 0.5, 0), axis_label_size, "Label_Y", (0.45, 1, 0.45, 1))
    if labels[2]:
        create_text_label(labels[2], (-tick_size * 8.8, 0, length_z), axis_label_size, "Label_Z", (0.45, 0.65, 1, 1))


def create_plane_with_image_memory(blender_img: bpy.types.Image, plane_name: str = "GraphPlane", axis_x: float = 5.0, axis_y: float = 5.0, z_pos: float = 0.0) -> bpy.types.Object:
    bpy.ops.mesh.primitive_plane_add(size=2, location=(axis_x / 2, axis_y / 2, z_pos))
    plane = bpy.context.active_object
    plane.name = plane_name
    plane.rotation_euler[0] = math.pi
    plane.scale.x = axis_x / 2
    plane.scale.y = -axis_y / 2
    mat = bpy.data.materials.new(name=f"{plane_name}_Mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = blender_img
    emission = nodes.new("ShaderNodeEmission")
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(tex.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    plane.data.materials.append(mat)
    plane["analysis3d_generated"] = True
    return plane


def _clean_numeric_xy(values_x: Sequence[float] | None, values_y: Sequence[float] | None, max_points: int | None = None) -> tuple[list[float], list[float]]:
    """Return finite X/Y arrays with optional decimation to keep Blender stable."""
    x = np.asarray(list(values_x) if values_x is not None else [], dtype=float)
    y = np.asarray(list(values_y) if values_y is not None else [], dtype=float)
    if x.size == 0 or y.size == 0:
        return [], []
    n = min(x.size, y.size)
    x = x[:n]
    y = y[:n]
    finite = np.isfinite(x) & np.isfinite(y)
    x = x[finite]
    y = y[finite]
    if max_points and x.size > max_points:
        idx = np.linspace(0, x.size - 1, int(max_points)).astype(int)
        x = x[idx]
        y = y[idx]
    return x.tolist(), y.tolist()


def draw_surface_graph(name: str, values_x: Sequence[float], values_y: Sequence[float], axis_scale_x: float = 5, axis_scale_y: float = 5, axis_scale_z: float = 5, z_offset: float = 0, csv_name: str | None = None, color: tuple[float, float, float, float] | None = None, thickness: float = 0.03, max_points: int = 350, x_range: tuple[float, float] | None = None, y_range: tuple[float, float] | None = None) -> bpy.types.Object | None:
    """Draw only the interaction curve and lightweight markers.

    x_range/y_range can be supplied by the comparative graph so every CSV uses
    the same scale. Without that shared range, different CSVs with different
    values can appear as the same line after per-series normalization.
    """
    values_x, values_y = _clean_numeric_xy(values_x, values_y, max_points=max_points)
    if len(values_x) == 0 or len(values_y) == 0:
        return None

    if x_range is None:
        x_range = (min(values_x), max(values_x))
    if y_range is None:
        y_range = (min(values_y), max(values_y))

    line = draw_metric_line(
        name, values_x, values_y,
        values_z=[z_offset] * len(values_x),
        axis_scale_x=axis_scale_x,
        axis_scale_y=axis_scale_y,
        axis_scale_z=axis_scale_z,
        x_range=x_range,
        y_range=y_range,
        thickness=thickness,
        csv_name=csv_name,
        color=color,
    )

    min_x, max_x = x_range
    min_y, max_y = y_range
    den_x = max(max_x - min_x, 1e-9)
    den_y = max(max_y - min_y, 1e-9)
    px = [((float(v) - min_x) / den_x) * axis_scale_x for v in values_x]
    py = [((float(v) - min_y) / den_y) * axis_scale_y for v in values_y]

    marker_step = max(1, len(px) // 80)
    pts = [Vector((float(x), float(y), z_offset)) for x, y in zip(px[::marker_step], py[::marker_step])]
    _build_spheres_object(pts, f"{name}_Points", color or get_color_for_csv(csv_name or name), radius=max(thickness*1.6,0.035), segments=6, rings=4)
    return line



def draw_multi_csv_surface_graph(name: str, series: Sequence[Mapping[str, Any]], axis_scale_x: float = 5, axis_scale_y: float = 5, axis_scale_z: float = 5, thickness: float = 0.035, max_points: int = 350) -> list[bpy.types.Object]:
    """Draw several CSV interaction curves in the same scene.

    This intentionally behaves like calling draw_surface_graph for the
    descriptive interaction graph of each CSV, but without clearing the scene
    between CSVs. Each CSV keeps its own descriptive normalization and is only
    moved along Z, like the comparative radar view.

    Expected series item keys: name, x, y, color.
    """
    if not series:
        return []

    count = len(series)
    z_step = axis_scale_z / max(1, count - 1)
    objects = []

    for idx, item in enumerate(series):
        csv_name = item.get("name", f"CSV_{idx + 1}")
        safe_csv = str(csv_name).replace(" ", "_").replace(".", "_")
        obj = draw_surface_graph(
            name=f"{name}_{idx}_{safe_csv}",
            values_x=item.get("x", []),
            values_y=item.get("y", []),
            axis_scale_x=axis_scale_x,
            axis_scale_y=axis_scale_y,
            axis_scale_z=axis_scale_z,
            z_offset=idx * z_step,
            csv_name=csv_name,
            color=item.get("color"),
            thickness=thickness,
            max_points=max_points,
            x_range=None,
            y_range=None,
        )
        if obj is not None:
            objects.append(obj)
    return objects

def draw_correlation_graph_fast(name: str, values_x: Sequence[float], values_y: Sequence[float], axis_scale_x: float = 5, axis_scale_y: float = 5, z_offset: float = 0, csv_name: str | None = None, color: tuple[float, float, float, float] | None = None, max_points: int = 300) -> bpy.types.Object | None:
    values_x = np.asarray(list(values_x) if values_x is not None else [], dtype=float)
    values_y = np.asarray(list(values_y) if values_y is not None else [], dtype=float)
    if values_x.size == 0 or values_y.size == 0:
        return None
    n = min(values_x.size, values_y.size)
    values_x = values_x[:n]
    values_y = values_y[:n]
    if n > max_points:
        idx = np.linspace(0, n - 1, max_points).astype(int)
        values_x = values_x[idx]
        values_y = values_y[idx]
    px = _normalize(values_x, axis_scale_x)
    py = _normalize(values_y, axis_scale_y)
    points = [Vector((float(x), float(y), z_offset)) for x, y in zip(px, py)]
    obj = _build_spheres_object(points, name, color or get_color_for_csv(csv_name or name), radius=0.035, segments=8, rings=5)
    if len(values_x) > 1:
        rank_warning = getattr(np, "RankWarning", RuntimeWarning)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", rank_warning)
                m, b = np.polyfit(values_x, values_y, 1)
            xs = np.linspace(float(np.min(values_x)), float(np.max(values_x)), 64)
            ys = m * xs + b
            draw_metric_line(f"{name}_Trend", xs, ys, [z_offset] * len(xs), color=(0, 0, 0, 1), thickness=0.018, axis_scale_x=axis_scale_x, axis_scale_y=axis_scale_y, x_range=(float(np.min(values_x)), float(np.max(values_x))), y_range=(float(np.min(values_y)), float(np.max(values_y))))
        except (np.linalg.LinAlgError, ValueError, FloatingPointError, RuntimeWarning) as exc:
            print(f"[draw_correlation_graph_fast] Trend line skipped: {exc}")
    return obj


def create_scatter_points_fast(values_x: Sequence[float], values_y: Sequence[float], z_pos: float, scale_x: float, scale_y: float, csv_name: str = "scatter", color: tuple[float, float, float, float] | None = None, max_points: int = 300) -> bpy.types.Object | None:
    values_x = np.asarray(list(values_x) if values_x is not None else [], dtype=float)
    values_y = np.asarray(list(values_y) if values_y is not None else [], dtype=float)
    if values_x.size == 0 or values_y.size == 0:
        return None
    n = min(values_x.size, values_y.size)
    values_x = values_x[:n]
    values_y = values_y[:n]
    if n > max_points:
        idx = np.linspace(0, n - 1, max_points).astype(int)
        values_x = values_x[idx]
        values_y = values_y[idx]
    px = _normalize(values_x, scale_x)
    py = _normalize(values_y, scale_y)
    points = [Vector((float(x), float(y), z_pos)) for x, y in zip(px, py)]
    return _build_spheres_object(points, f"Scatter_{csv_name}", color or get_color_for_csv(csv_name), radius=0.035, segments=8, rings=5)


def create_time_graph(values_x: Sequence[float], values_y: Sequence[float], z_pos: float, scale_x: float, scale_y: float, csv_name: str = "time", metric_name: str = "metric", color: tuple[float, float, float, float] | None = None) -> bpy.types.Object | None:
    values_x = list(values_x) if values_x is not None else []
    values_y = list(values_y) if values_y is not None else []
    if len(values_x) == 0 or len(values_y) == 0:
        return None
    line = draw_metric_line(f"Time_{csv_name}_{metric_name}", values_x, values_y, [z_pos] * len(values_x), color=color or get_color_for_csv(csv_name), thickness=0.03, axis_scale_x=scale_x, axis_scale_y=scale_y, x_range=(min(values_x), max(values_x)), y_range=(min(values_y), max(values_y)))
    px = _normalize(values_x, scale_x)
    py = _normalize(values_y, scale_y)
    pts = [Vector((float(x), float(y), z_pos)) for x, y in zip(px, py)]
    _build_spheres_object(pts, f"TimePts_{csv_name}_{metric_name}", color or get_color_for_csv(csv_name), radius=0.03, segments=8, rings=5)
    return line



def create_interaction_graph_3d(values_x: Sequence[float], values_y: Sequence[float], z_pos: float, scale_x: float, scale_y: float, csv_name: str = "interaction", metric_name: str = "metric", color: tuple[float, float, float, float] | None = None, max_bars: int = 120, x_range: tuple[float, float] | None = None, y_range: tuple[float, float] | None = None) -> bpy.types.Object | None:
    """Create the interaction graph using the stable V5-style surface/line implementation.

    The previous V6 bar version used vertical cylinders that looked odd from the
    top camera. This version keeps the interaction readable on the XY plane and
    lets draw_surface_graph normalize values consistently with the axes.
    """
    values_x = list(values_x) if values_x is not None else []
    values_y = list(values_y) if values_y is not None else []
    if len(values_x) == 0 or len(values_y) == 0:
        return None

    n = min(len(values_x), len(values_y))
    values_x = values_x[:n]
    values_y = values_y[:n]
    safe_csv = str(csv_name).replace(" ", "_").replace(".", "_")
    safe_metric = str(metric_name).replace(" ", "_").replace(".", "_")

    graph = draw_surface_graph(
        name=f"Surface_{safe_csv}_{safe_metric}",
        values_x=values_x,
        values_y=values_y,
        axis_scale_x=scale_x,
        axis_scale_y=scale_y,
        z_offset=z_pos,
        csv_name=csv_name,
        color=color,
        thickness=0.035,
        max_points=max_bars,
        x_range=x_range,
        y_range=y_range,
    )
    return graph

def draw_forest_plot_3d(values: Sequence[float], csv_name: str = "CSV", metric_name: str = "Metric", axis_scale_x: float = 5.0, axis_scale_y: float = 5.0, z_pos: float = 0.0, point_radius: float = 0.06, line_thickness: float = 0.03) -> bpy.types.Object | None:
    if values is None or len(values) == 0:
        return None

    values = np.asarray(values, dtype=float)
    color = get_color_for_csv(csv_name)

    mean_val = float(np.mean(values))
    std_val = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    ci = 1.96 * std_val / np.sqrt(max(len(values), 1))

    min_v = float(np.min(values))
    max_v = float(np.max(values))
    rng = max(max_v - min_v, 1e-9)

    y = axis_scale_y * 0.5
    x_mean = ((mean_val - min_v) / rng) * axis_scale_x
    x0 = ((mean_val - ci - min_v) / rng) * axis_scale_x
    x1 = ((mean_val + ci - min_v) / rng) * axis_scale_x

    create_axis(Vector((x0, y, z_pos)), Vector((x1, y, z_pos)), color, f"ForestCI_{csv_name}_{metric_name}", radius=line_thickness, vertices=8)
    create_axis(Vector((x0, y - 0.12, z_pos)), Vector((x0, y + 0.12, z_pos)), color, f"ForestCapL_{csv_name}_{metric_name}", radius=line_thickness * 0.5, vertices=8)
    create_axis(Vector((x1, y - 0.12, z_pos)), Vector((x1, y + 0.12, z_pos)), color, f"ForestCapR_{csv_name}_{metric_name}", radius=line_thickness * 0.5, vertices=8)

    _build_spheres_object(
        [Vector((x_mean, y, z_pos))],
        f"ForestPoint_{csv_name}_{metric_name}",
        color,
        radius=point_radius,
        segments=12,
        rings=8,
    )

    create_text_label(metric_name, (0, y + 0.38, z_pos), 0.34, f"ForestLabel_{csv_name}_{metric_name}")

    return bpy.data.objects.get(f"ForestPoint_{csv_name}_{metric_name}")

def _forest_safe_name(value):
    return str(value).replace(" ", "_").replace(".", "_").replace("/", "_").replace("\\", "_")


def _forest_map_value(value, value_range, axis_scale_x):
    min_v, max_v = value_range
    denom = max(max_v - min_v, 1e-9)
    return ((float(value) - min_v) / denom) * axis_scale_x


def _create_forest_square_marker(location, name, color, size=0.14):
    bpy.ops.mesh.primitive_cube_add(size=size, location=location)
    obj = bpy.context.active_object
    obj.name = name
    mat = create_emission_material(f"{name}_Mat", color, 2.5)
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    obj["analysis3d_generated"] = True
    return obj


def draw_multi_csv_forest_plot_3d(rows: Sequence[Mapping[str, Any]], metric_label: str = "Metric", axis_scale_x: float = 7.0, axis_scale_y: float = 5.0, z_pos: float = 0.0, point_size: float = 0.16, line_thickness: float = 0.025, compact_labels: bool = False, scale_label: str = "linear") -> dict[str, object] | None:
    if not rows:
        return None

    rows = [r for r in rows if np.isfinite(float(r.get("mean", 0.0)))]
    if not rows:
        return None

    lows = [float(r.get("ci_low", r["mean"])) for r in rows]
    highs = [float(r.get("ci_high", r["mean"])) for r in rows]
    means = [float(r["mean"]) for r in rows]

    min_v = min(lows + means)
    max_v = max(highs + means)

    if abs(max_v - min_v) < 1e-9:
        pad = max(abs(max_v), 1.0) * 0.1
    else:
        pad = (max_v - min_v) * 0.08

    low_bound = min_v - pad
    high_bound = max_v + pad
    if low_bound >= 0.0:
        low_bound = 0.0
    elif high_bound <= 0.0:
        high_bound = 0.0
    value_range = (low_bound, high_bound)

    safe_metric = _forest_safe_name(metric_label)

    light = (0.28, 0.28, 0.32, 1.0)
    white = (1.0, 1.0, 1.0, 1.0)
    ref_col = (0.75, 0.75, 0.75, 1.0)

    row_count = len(rows)
    row_gap = axis_scale_y / max(row_count, 1)
    top_y = axis_scale_y - row_gap * 0.65
    left_x = -5.70
    right_x = axis_scale_x + 0.55

    title_suffix = "" if scale_label == "linear" else f" · {scale_label}"
    create_text_label(f"Forest plot · {metric_label}{title_suffix}", (0, axis_scale_y + 0.62, z_pos), 0.42, f"ForestTitle_{safe_metric}")
    create_text_label("CSV file", (left_x, axis_scale_y + 0.22, z_pos), 0.28, f"ForestHeaderCSV_{safe_metric}", align_x="LEFT")
    create_text_label("Mean", (right_x, axis_scale_y + 0.22, z_pos), 0.30, f"ForestHeaderMean_{safe_metric}")
    create_text_label("N", (right_x + 0.9, axis_scale_y + 0.22, z_pos), 0.30, f"ForestHeaderN_{safe_metric}")

    axis_y = -0.25
    create_axis(Vector((0, axis_y, z_pos)), Vector((axis_scale_x, axis_y, z_pos)), white, f"ForestAxisX_{safe_metric}", radius=0.012, vertices=8)

    tick_values = np.linspace(value_range[0], value_range[1], 6)
    for idx, tick in enumerate(tick_values):
        x = _forest_map_value(tick, value_range, axis_scale_x)
        create_axis(Vector((x, axis_y - 0.08, z_pos)), Vector((x, axis_y + 0.08, z_pos)), white, f"ForestTick_{safe_metric}_{idx}", radius=0.008, vertices=6)
        create_text_label(f"{tick:.2g}", (x - 0.1, axis_y - 0.42, z_pos), 0.26, f"ForestTickLabel_{safe_metric}_{idx}")

    ref_value = float(np.mean(means))
    ref_x = _forest_map_value(ref_value, value_range, axis_scale_x)
    create_axis(Vector((ref_x, axis_y, z_pos)), Vector((ref_x, axis_scale_y, z_pos)), ref_col, f"ForestReference_{safe_metric}", radius=0.01, vertices=8)
    create_text_label("Group mean", (ref_x + 0.08, axis_scale_y + 0.22, z_pos), 0.24, f"ForestReferenceLabel_{safe_metric}")

    for idx, row in enumerate(rows):
        y = top_y - idx * row_gap

        csv_name = str(row.get("csv_name", f"CSV_{idx + 1}"))
        short_name = _short_csv_label(csv_name, max_len=24 if compact_labels else 42)
        safe_csv = _forest_safe_name(csv_name)
        csv_color = csv_color_by_index(idx)

        mean = float(row["mean"])
        ci_low = float(row.get("ci_low", mean))
        ci_high = float(row.get("ci_high", mean))
        n = int(row.get("n", 0))

        x0 = _forest_map_value(ci_low, value_range, axis_scale_x)
        x1 = _forest_map_value(ci_high, value_range, axis_scale_x)
        xm = _forest_map_value(mean, value_range, axis_scale_x)

        create_axis(Vector((0, y, z_pos - 0.01)), Vector((axis_scale_x, y, z_pos - 0.01)), light, f"ForestRowGuide_{safe_metric}_{idx}", radius=0.004, vertices=6)

        create_text_label(short_name, (left_x, y - 0.08, z_pos), 0.18 if not compact_labels else 0.16, f"ForestCSVLabel_{safe_metric}_{safe_csv}_{idx}", align_x="LEFT")

        create_axis(Vector((x0, y, z_pos)), Vector((x1, y, z_pos)), csv_color, f"ForestCI_{safe_metric}_{safe_csv}_{idx}", radius=line_thickness, vertices=8)
        create_axis(Vector((x0, y - 0.09, z_pos)), Vector((x0, y + 0.09, z_pos)), csv_color, f"ForestCapL_{safe_metric}_{safe_csv}_{idx}", radius=line_thickness * 0.55, vertices=8)
        create_axis(Vector((x1, y - 0.09, z_pos)), Vector((x1, y + 0.09, z_pos)), csv_color, f"ForestCapR_{safe_metric}_{safe_csv}_{idx}", radius=line_thickness * 0.55, vertices=8)

        _create_forest_square_marker(
            Vector((xm, y, z_pos)),
            f"ForestPoint_{safe_metric}_{safe_csv}_{idx}",
            csv_color,
            size=point_size,
        )

        create_text_label(f"{mean:.3g}", (right_x, y - 0.08, z_pos), 0.26, f"ForestMean_{safe_metric}_{safe_csv}_{idx}")
        create_text_label(str(n), (right_x + 0.9, y - 0.08, z_pos), 0.26, f"ForestN_{safe_metric}_{safe_csv}_{idx}")

    return {
        "x_range": value_range,
        "y_range": (0, row_count),
        "x_ticks": [float(v) for v in tick_values],
        "y_ticks": list(range(row_count)),
    }

def _short_csv_label(value, max_len=16):
    import os
    name = os.path.basename(str(value or "CSV"))
    name = name.replace("_data.csv", "").replace(".csv", "")
    if len(name) <= max_len:
        return name
    return name[:max_len - 3] + "..."


def draw_csv_color_legend(csv_items: Sequence[object] | None = None, csv_names: Sequence[str] | None = None, axis_scale_x: float = 5.0, axis_scale_y: float = 5.0, z_pos: float = 0.0, title: str = "Leyenda") -> bool | None:
    items = []

    if csv_items:
        for idx, item in enumerate(csv_items):
            if isinstance(item, dict):
                name = item.get("name", f"CSV_{idx + 1}")
                color = item.get("color", csv_color_by_index(idx))
            else:
                name = str(item)
                color = csv_color_by_index(idx)
            items.append((name, color))
    elif csv_names:
        for idx, name in enumerate(csv_names):
            items.append((name, csv_color_by_index(idx)))

    if not items:
        return None

    legend_x = -4.6
    legend_y = axis_scale_y - 0.15
    gap = 0.72

    create_text_label(title, (legend_x, legend_y + 0.48, z_pos), 0.36, "RadarLegendTitle", align_x="LEFT")

    for idx, (name, color) in enumerate(items):
        y = legend_y - idx * gap
        safe_csv = _forest_safe_name(name)

        _build_spheres_object(
            [Vector((legend_x, y, z_pos))],
            f"RadarLegendDot_{safe_csv}_{idx}",
            color,
            radius=0.085,
            segments=12,
            rings=8,
        )

        create_text_label(
            _short_csv_label(name),
            (legend_x + 0.50, y - 0.05, z_pos),
            0.30,
            f"RadarLegendLabel_{safe_csv}_{idx}",
            align_x="LEFT",
        )

    return True

def draw_radar_graph_3d_filled(values: Sequence[float], axis_scale_x: float = 5, axis_scale_y: float = 5, z_pos: float = 0, labels: Sequence[str] | None = None, color: tuple[float, float, float, float] = (0.2, 0.8, 0.4, 1), csv_name: str = "radar", line_thickness: float = 0.04) -> bpy.types.Object | None:
    if values is None or len(values) == 0:
        return None
    values = [float(v) for v in values if np.isfinite(float(v))]
    labels = labels or []
    n = len(values)

    if n == 0:
        return None

    center = Vector((axis_scale_x / 2, axis_scale_y / 2, z_pos + 0.2))
    radius = min(axis_scale_x, axis_scale_y) * 0.42

    min_val = min(values)
    max_val = max(values)
    rng = max(max_val - min_val, 1e-9)

    # Valores normalizados entre 0.05 y 1.0 para que nada desaparezca visualmente.
    norm_values = [0.05 + 0.95 * ((v - min_val) / rng) for v in values]
    for ring_idx, frac in enumerate((0.25, 0.5, 0.75, 1.0), start=1):
        ring_pts = []
        for i in range(n):
            ang = i / n * 2 * pi
            ring_pts.append((center.x + radius * frac * cos(ang), center.y + radius * frac * sin(ang), center.z))
        ring_pts.append(ring_pts[0])
        draw_metric_line(f"RadarRing_{csv_name}_{ring_idx}", [p[0] for p in ring_pts], [p[1] for p in ring_pts], [center.z] * len(ring_pts), color=(0.7, 0.7, 0.7, 1), thickness=0.01)
    valid_points = []
    for i, value in enumerate(values):
        ang = i / n * 2 * pi
        edge = Vector((center.x + radius * cos(ang), center.y + radius * sin(ang), center.z))
        create_axis(center, edge, (0.6, 0.6, 0.6, 1), f"RadarAxis_{csv_name}_{i}", radius=0.01, vertices=6)
        norm_value = norm_values[i]
        point = Vector((center.x + norm_value * radius * cos(ang), center.y + norm_value * radius * sin(ang), center.z))
        valid_points.append(point)
        _build_spheres_object([point], f"RadarPoint_{csv_name}_{i}", color, radius=0.06, segments=10, rings=6)
        if i < len(labels):
            create_text_label(labels[i], edge + Vector((0.32 * cos(ang), 0.32 * sin(ang), 0.0)), 0.32, f"RadarLabel_{csv_name}_{i}")
    pts = valid_points + [valid_points[0]]
    draw_metric_line(f"Radar_{csv_name}", [p.x for p in pts], [p.y for p in pts], [p.z for p in pts], color=color, thickness=line_thickness)
    mesh = bpy.data.meshes.new(f"RadarMesh_{csv_name}")
    obj = bpy.data.objects.new(f"RadarFill_{csv_name}", mesh)
    obj["analysis3d_generated"] = True
    bpy.context.collection.objects.link(obj)
    bm = bmesh.new()
    c = bm.verts.new(center)
    verts = [bm.verts.new(p) for p in valid_points]
    for i in range(len(verts)):
        try:
            bm.faces.new([c, verts[i], verts[(i + 1) % len(verts)]])
        except ValueError:
            pass
    bm.to_mesh(mesh)
    bm.free()
    mat = bpy.data.materials.new(name=f"RadarMat_{csv_name}")
    mat.use_nodes = True
    mat.blend_method = 'BLEND'
    mat.diffuse_color = (color[0], color[1], color[2], 0.28)

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    transparent = nodes.new("ShaderNodeBsdfTransparent")
    emission = nodes.new("ShaderNodeEmission")
    mix = nodes.new("ShaderNodeMixShader")
    output = nodes.new("ShaderNodeOutputMaterial")

    emission.inputs["Color"].default_value = (color[0], color[1], color[2], 1.0)
    emission.inputs["Strength"].default_value = 1.2

    mix.inputs["Fac"].default_value = 0.28

    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs["Surface"])

    obj.data.materials.append(mat)
    obj.show_transparent = True
    
    return obj



def register():
    pass


def unregister():
    pass
