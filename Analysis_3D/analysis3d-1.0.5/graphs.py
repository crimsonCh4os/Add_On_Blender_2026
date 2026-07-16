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
    return fam[0]


def csv_color_by_index(index: int, palette_name: str | None = None) -> tuple[float, float, float, float]:
    families = _active_color_families(palette_name)
    family = families[int(index) % len(families)]
    return family[0]


def metric_color_for_csv(csv_index: int, metric_index: int, palette_name: str | None = None) -> tuple[float, float, float, float]:
    families = _active_color_families(palette_name)
    family = families[int(csv_index) % len(families)]
    return family[int(metric_index) % len(family)]


GRAPH_OBJECT_PREFIXES = (
    "GraphPlane_", "GraphLineMesh_", "Scatter_", "Corr_", "Surface_", "Time_",
    "Forest", "Radar", "RadarFill_", "RadarRing_", "RadarAxis_", "RadarPoint_", "RadarLabel_",
    "DataTable", "TableGrid_", "TableText_", "TableTitle_", "TableSubtitle_",
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


def _create_forest_diamond(x_center, x_low, x_high, y, z, name, color, height=0.22):
    verts = [
        (float(x_low), float(y), float(z)),
        (float(x_center), float(y + height), float(z)),
        (float(x_high), float(y), float(z)),
        (float(x_center), float(y - height), float(z)),
    ]
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mat = create_emission_material(f"{name}_Mat", color, 2.5)
    obj.data.materials.append(mat)
    obj["analysis3d_generated"] = True
    return obj




def _forest_format_value(value: float) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    abs_v = abs(value)
    if abs_v >= 1000000.0:
        return f"{value/1000000.0:.2f}M"
    if abs_v >= 10000.0:
        return f"{value/1000.0:.1f}k"
    if abs_v >= 1000.0:
        return f"{value/1000.0:.2f}k"
    if abs_v >= 100.0:
        return f"{value:.0f}"
    if abs_v >= 10.0:
        return f"{value:.1f}"
    if abs_v >= 1.0:
        return f"{value:.2f}"
    if abs_v >= 0.1:
        return f"{value:.3f}"
    if abs_v >= 0.01:
        return f"{value:.4f}"
    return f"{value:.2g}"


def _forest_superscript_int(value: int) -> str:
    table = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
    return str(int(value)).translate(table)


def _forest_display_scale_power(values: Sequence[float]) -> int:
    finite = [abs(float(v)) for v in values if np.isfinite(v) and abs(float(v)) > 1e-15]
    if not finite:
        return 0
    max_abs = max(finite)
    power = int(math.floor(math.log10(max_abs)))
    eng = int(math.floor(power / 3.0) * 3)
    if -3 <= eng <= 3:
        return eng
    return eng


def _forest_scaled_value(value: float, scale_power: int = 0) -> float:
    return float(value) / (10.0 ** scale_power) if scale_power else float(value)


def _forest_effect_label(mean: float, ci_low: float, ci_high: float, scale_power: int = 0) -> str:
    m = _forest_scaled_value(mean, scale_power)
    lo = _forest_scaled_value(ci_low, scale_power)
    hi = _forest_scaled_value(ci_high, scale_power)
    return f"{_forest_format_value(m)} [{_forest_format_value(lo)}–{_forest_format_value(hi)}]"


def _forest_tick_values(value_range: tuple[float, float], desired: int = 4) -> list[float]:
    lo, hi = value_range
    if not np.isfinite(lo) or not np.isfinite(hi):
        return [0.0]
    if abs(hi - lo) < 1e-12:
        return [lo]
    ticks = np.linspace(lo, hi, max(int(desired), 2))
    return [float(v) for v in ticks]


def _forest_lang_text(label: str) -> str:
    try:
        from .texts import tr
        return tr(getattr(bpy.context, "scene", None), label)
    except Exception:
        return label


def _forest_t_critical_95(df: int) -> float:
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


def draw_multi_csv_forest_plot_3d(
    rows: Sequence[Mapping[str, Any]],
    metric_label: str = "Metric",
    axis_scale_x: float = 7.0,
    axis_scale_y: float = 5.0,
    z_pos: float = 0.0,
    point_size: float = 0.16,
    line_thickness: float = 0.025,
    compact_labels: bool = False,
    scale_label: str = "linear",
    null_value: float | None = None,
    palette_name: str | None = None,
) -> dict[str, object] | None:
    """Draw study means with 95% CIs and a random-effects pooled estimate.

    Each CSV is treated as an independent group/study. Individual intervals
    use the standard errors supplied by ``forest_row_stats``. The pooled
    estimate uses a DerSimonian-Laird random-effects model; its interval uses
    a modified Hartung-Knapp adjustment when at least three groups exist.

    A no-effect line is drawn only when the caller explicitly supplies a
    meaningful ``null_value``. Raw means do not inherently have a null of 0.
    """
    if not rows:
        return None

    clean_rows = []
    for row in rows:
        try:
            mean = float(row.get("mean", 0.0))
            low = float(row.get("ci_low", mean))
            high = float(row.get("ci_high", mean))
            n = max(int(row.get("n", 0)), 1)
            se = float(row.get("se", float("nan")))
        except (TypeError, ValueError):
            continue
        if not all(np.isfinite(v) for v in (mean, low, high)):
            continue
        if not np.isfinite(se) or se <= 0.0:
            half_width = max(abs(high - low) * 0.5, 0.0)
            se = half_width / 1.96 if half_width > 1e-12 else float("nan")
        if not np.isfinite(se) or se <= 0.0:
            # A one-observation group has no estimable sampling variance and
            # cannot receive an inverse-variance meta-analytic weight.
            continue

        clean = dict(row)
        clean.update({
            "mean": mean,
            "ci_low": min(low, high),
            "ci_high": max(low, high),
            "n": n,
            "se": se,
            "variance": se * se,
        })
        clean_rows.append(clean)

    if len(clean_rows) < 2:
        return None

    means = np.asarray([r["mean"] for r in clean_rows], dtype=float)
    variances = np.asarray([r["variance"] for r in clean_rows], dtype=float)
    fixed_weights = 1.0 / variances
    fixed_mean = float(np.sum(fixed_weights * means) / np.sum(fixed_weights))
    q = float(np.sum(fixed_weights * (means - fixed_mean) ** 2))
    k = len(clean_rows)
    df_q = k - 1
    c = float(np.sum(fixed_weights) - np.sum(fixed_weights ** 2) / np.sum(fixed_weights))
    tau2 = max(0.0, (q - df_q) / c) if c > 1e-15 else 0.0

    random_weights = 1.0 / (variances + tau2)
    pooled_mean = float(np.sum(random_weights * means) / np.sum(random_weights))
    conventional_se = float(np.sqrt(1.0 / np.sum(random_weights)))

    if k >= 3:
        hk_scale = float(np.sum(random_weights * (means - pooled_mean) ** 2) / df_q)
        # Modified Hartung-Knapp avoids an interval narrower than the
        # conventional random-effects interval when heterogeneity is tiny.
        pooled_se = conventional_se * math.sqrt(max(hk_scale, 1.0))
        critical = _forest_t_critical_95(df_q)
        pooling_method = "Random effects (DL + modified HK)"
    else:
        pooled_se = conventional_se
        critical = 1.96
        pooling_method = "Random effects (DL)"

    pooled_low = pooled_mean - critical * pooled_se
    pooled_high = pooled_mean + critical * pooled_se
    i2 = max(0.0, (q - df_q) / q * 100.0) if q > 1e-15 else 0.0

    total_weight = float(np.sum(random_weights))
    for row, weight in zip(clean_rows, random_weights):
        row["weight"] = float(weight)
        row["weight_pct"] = float(100.0 * weight / total_weight)

    lows = [r["ci_low"] for r in clean_rows] + [pooled_low]
    highs = [r["ci_high"] for r in clean_rows] + [pooled_high]
    if null_value is not None and np.isfinite(null_value):
        lows.append(float(null_value))
        highs.append(float(null_value))
    min_v = min(lows)
    max_v = max(highs)
    span = max(max_v - min_v, 1e-9)
    pad = span * 0.12
    value_range = (min_v - pad, max_v + pad)

    safe_metric = _forest_safe_name(metric_label)
    light = (0.23, 0.23, 0.27, 1.0)
    light_2 = (0.18, 0.18, 0.22, 1.0)
    white = (1.0, 1.0, 1.0, 1.0)
    subtle = (0.82, 0.82, 0.86, 1.0)
    null_col = (0.86, 0.86, 0.90, 1.0)
    pooled_col = (1.0, 0.72, 0.20, 1.0)

    display_scale_power = _forest_display_scale_power([*lows, *highs])

    row_count = len(clean_rows)
    total_rows = row_count + 1
    top_margin = 0.95
    bottom_margin = 0.55
    usable_y = max(axis_scale_y - top_margin - bottom_margin, 0.8)
    row_gap = usable_y / max(total_rows, 1)
    top_y = axis_scale_y - top_margin
    pooled_y = top_y - row_count * row_gap
    left_x = -3.55
    plot_left = 0.0
    plot_right = axis_scale_x
    right_x = axis_scale_x + 0.55
    n_x = axis_scale_x + 3.05
    weight_x = axis_scale_x + 4.05

    create_text_label(
        f"Forest plot · {metric_label}",
        (axis_scale_x * 0.5, axis_scale_y + 0.94, z_pos),
        0.46,
        f"ForestTitle_{safe_metric}",
    )
    subtitle = f"{pooling_method} · I² = {i2:.1f}% · τ² = {_forest_format_value(tau2)}"
    if scale_label != "linear":
        subtitle = f"{scale_label} · {subtitle}"
    create_text_label(
        subtitle,
        (axis_scale_x * 0.5, axis_scale_y + 0.57, z_pos),
        0.20,
        f"ForestSubtitle_{safe_metric}",
        color=subtle,
    )

    effect_header = "Mean [95% CI]"
    if display_scale_power:
        effect_header = f"{effect_header} (×10{_forest_superscript_int(display_scale_power)})"
    create_text_label(_forest_lang_text("CSV file"), (left_x, axis_scale_y + 0.22, z_pos), 0.30, f"ForestHeaderCSV_{safe_metric}", align_x="LEFT", color=subtle)
    create_text_label(effect_header, (right_x, axis_scale_y + 0.22, z_pos), 0.25, f"ForestHeaderMean_{safe_metric}", align_x="LEFT", color=subtle)
    create_text_label("N", (n_x, axis_scale_y + 0.22, z_pos), 0.28, f"ForestHeaderN_{safe_metric}", color=subtle, align_x="LEFT")
    create_text_label("Weight", (weight_x, axis_scale_y + 0.22, z_pos), 0.24, f"ForestHeaderWeight_{safe_metric}", color=subtle, align_x="LEFT")

    axis_y = 0.02
    create_axis(Vector((plot_left, axis_y, z_pos)), Vector((plot_right, axis_y, z_pos)), white, f"ForestAxisX_{safe_metric}", radius=0.012, vertices=8)

    tick_values = _forest_tick_values(value_range, desired=5)
    for idx, tick in enumerate(tick_values):
        x = _forest_map_value(tick, value_range, axis_scale_x)
        create_axis(Vector((x, axis_y - 0.07, z_pos)), Vector((x, axis_y + 0.07, z_pos)), subtle, f"ForestTick_{safe_metric}_{idx}", radius=0.008, vertices=6)
        create_text_label(_forest_format_value(_forest_scaled_value(tick, display_scale_power)), (x, axis_y - 0.34, z_pos), 0.26, f"ForestTickLabel_{safe_metric}_{idx}", color=subtle)

    null_x = None
    if null_value is not None and np.isfinite(null_value):
        null_x = _forest_map_value(float(null_value), value_range, axis_scale_x)
        create_axis(
            Vector((null_x, axis_y, z_pos)),
            Vector((null_x, top_y + row_gap * 0.45, z_pos)),
            null_col,
            f"ForestNoEffect_{safe_metric}",
            radius=0.010,
            vertices=8,
        )
        create_text_label(
            f"{_forest_lang_text('No effect')} = {_forest_format_value(_forest_scaled_value(float(null_value), display_scale_power))}",
            (null_x, axis_scale_y + 0.02, z_pos),
            0.21,
            f"ForestNoEffectLabel_{safe_metric}",
            color=subtle,
            align_x="CENTER",
        )

    create_axis(Vector((plot_left, axis_y, z_pos - 0.01)), Vector((plot_left, top_y + row_gap * 0.45, z_pos - 0.01)), light_2, f"ForestColumnL_{safe_metric}", radius=0.006, vertices=6)
    create_axis(Vector((plot_right, axis_y, z_pos - 0.01)), Vector((plot_right, top_y + row_gap * 0.45, z_pos - 0.01)), light_2, f"ForestColumnR_{safe_metric}", radius=0.006, vertices=6)

    max_weight_pct = max(r["weight_pct"] for r in clean_rows)
    for idx, row in enumerate(clean_rows):
        y = top_y - idx * row_gap
        csv_name = str(row.get("csv_name", f"CSV_{idx + 1}"))
        short_name = _short_csv_label(csv_name, max_len=16 if compact_labels else 22)
        safe_csv = _forest_safe_name(csv_name)
        color_index = int(row.get("color_index", idx))
        csv_color = csv_color_by_index(color_index, palette_name=palette_name)

        mean = row["mean"]
        ci_low = row["ci_low"]
        ci_high = row["ci_high"]
        n = row["n"]
        marker_size = point_size * (0.55 + 1.25 * math.sqrt(row["weight_pct"] / max_weight_pct))

        x0 = _forest_map_value(ci_low, value_range, axis_scale_x)
        x1 = _forest_map_value(ci_high, value_range, axis_scale_x)
        xm = _forest_map_value(mean, value_range, axis_scale_x)

        create_axis(Vector((plot_left, y, z_pos - 0.01)), Vector((plot_right, y, z_pos - 0.01)), light, f"ForestRowGuide_{safe_metric}_{idx}", radius=0.0035, vertices=6)
        create_text_label(short_name, (left_x, y - 0.03, z_pos), 0.24 if not compact_labels else 0.20, f"ForestCSVLabel_{safe_metric}_{safe_csv}_{idx}", align_x="LEFT", color=csv_color)
        create_axis(Vector((x0, y, z_pos)), Vector((x1, y, z_pos)), csv_color, f"ForestCI_{safe_metric}_{safe_csv}_{idx}", radius=line_thickness * 1.1, vertices=8)
        create_axis(Vector((x0, y - 0.10, z_pos)), Vector((x0, y + 0.10, z_pos)), csv_color, f"ForestCapL_{safe_metric}_{safe_csv}_{idx}", radius=line_thickness * 0.60, vertices=8)
        create_axis(Vector((x1, y - 0.10, z_pos)), Vector((x1, y + 0.10, z_pos)), csv_color, f"ForestCapR_{safe_metric}_{safe_csv}_{idx}", radius=line_thickness * 0.60, vertices=8)
        _create_forest_square_marker(Vector((xm, y, z_pos)), f"ForestPoint_{safe_metric}_{safe_csv}_{idx}", csv_color, size=marker_size)

        create_text_label(_forest_effect_label(mean, ci_low, ci_high, display_scale_power), (right_x, y - 0.03, z_pos), 0.22, f"ForestMean_{safe_metric}_{safe_csv}_{idx}", align_x="LEFT", color=white)
        create_text_label(str(n), (n_x, y - 0.03, z_pos), 0.24, f"ForestN_{safe_metric}_{safe_csv}_{idx}", color=subtle, align_x="LEFT")
        create_text_label(f"{row['weight_pct']:.1f}%", (weight_x, y - 0.03, z_pos), 0.22, f"ForestWeight_{safe_metric}_{safe_csv}_{idx}", color=subtle, align_x="LEFT")

    separator_y = pooled_y + row_gap * 0.52
    create_axis(Vector((plot_left, separator_y, z_pos - 0.01)), Vector((plot_right, separator_y, z_pos - 0.01)), white, f"ForestPooledSeparator_{safe_metric}", radius=0.007, vertices=8)
    create_text_label(_forest_lang_text("Overall"), (left_x, pooled_y - 0.03, z_pos), 0.26, f"ForestOverallLabel_{safe_metric}", align_x="LEFT", color=pooled_col)

    pooled_x = _forest_map_value(pooled_mean, value_range, axis_scale_x)
    pooled_x0 = _forest_map_value(pooled_low, value_range, axis_scale_x)
    pooled_x1 = _forest_map_value(pooled_high, value_range, axis_scale_x)
    _create_forest_diamond(pooled_x, pooled_x0, pooled_x1, pooled_y, z_pos, f"ForestDiamond_{safe_metric}", pooled_col, height=min(row_gap * 0.34, 0.24))
    create_text_label(_forest_effect_label(pooled_mean, pooled_low, pooled_high, display_scale_power), (right_x, pooled_y - 0.03, z_pos), 0.22, f"ForestOverallValue_{safe_metric}", align_x="LEFT", color=pooled_col)
    create_text_label(str(int(sum(r["n"] for r in clean_rows))), (n_x, pooled_y - 0.03, z_pos), 0.24, f"ForestOverallN_{safe_metric}", color=pooled_col, align_x="LEFT")
    create_text_label("100.0%", (weight_x, pooled_y - 0.03, z_pos), 0.22, f"ForestOverallWeight_{safe_metric}", color=pooled_col, align_x="LEFT")

    return {
        "x_range": value_range,
        "y_range": (0, total_rows),
        "x_ticks": [float(v) for v in tick_values],
        "y_ticks": [],
        "null_value": null_value,
        "pooled_mean": pooled_mean,
        "pooled_ci": (pooled_low, pooled_high),
        "tau2": tau2,
        "i2": i2,
        "q": q,
        "pooling_method": pooling_method,
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

def draw_radar_graph_3d_filled(values: Sequence[float], axis_scale_x: float = 5, axis_scale_y: float = 5, z_pos: float = 0, labels: Sequence[str] | None = None, color: tuple[float, float, float, float] = (0.2, 0.8, 0.4, 1), csv_name: str = "radar", line_thickness: float = 0.04, values_are_normalized: bool = False, radar_margin: float = 0.0, draw_margin_guides: bool = False, margin_labels: Sequence[str] | None = None) -> bpy.types.Object | None:
    if values is None or len(values) == 0:
        return None
    values = [float(v) for v in values if np.isfinite(float(v))]
    labels = labels or []
    n = len(values)

    if n == 0:
        return None

    center = Vector((axis_scale_x / 2, axis_scale_y / 2, z_pos + 0.2))
    radius = min(axis_scale_x, axis_scale_y) * 0.42

    if values_are_normalized:
        norm_values = [min(max(float(v), 0.0), 1.0) for v in values]
    else:
        min_val = min(values)
        max_val = max(values)
        rng = max(max_val - min_val, 1e-9)
        norm_values = [0.05 + 0.95 * ((v - min_val) / rng) for v in values]

    for ring_idx, frac in enumerate((0.25, 0.5, 0.75, 1.0), start=1):
        ring_pts = []
        for i in range(n):
            ang = i / n * 2 * pi
            ring_pts.append((center.x + radius * frac * cos(ang), center.y + radius * frac * sin(ang), center.z))
        ring_pts.append(ring_pts[0])
        draw_metric_line(f"RadarRing_{csv_name}_{ring_idx}", [p[0] for p in ring_pts], [p[1] for p in ring_pts], [center.z] * len(ring_pts), color=(0.7, 0.7, 0.7, 1), thickness=0.01)

    if draw_margin_guides and values_are_normalized and radar_margin > 0.0:
        margin = min(max(float(radar_margin), 0.0), 0.49)
        guide_labels = list(margin_labels or [])
        for guide_idx, frac in enumerate((margin, 1.0 - margin)):
            guide_pts = []
            for i in range(n):
                ang = i / n * 2 * pi
                guide_pts.append((center.x + radius * frac * cos(ang), center.y + radius * frac * sin(ang), center.z + 0.004))
            guide_pts.append(guide_pts[0])
            draw_metric_line(
                f"RadarMarginGuide_{csv_name}_{guide_idx}",
                [p[0] for p in guide_pts],
                [p[1] for p in guide_pts],
                [p[2] for p in guide_pts],
                color=(1.0, 1.0, 1.0, 1.0),
                thickness=0.025,
            )
            if guide_idx < len(guide_labels):
                label_pos = Vector((center.x + radius * frac + 0.12, center.y + 0.08, center.z + 0.01))
                create_text_label(
                    guide_labels[guide_idx],
                    label_pos,
                    0.22,
                    f"RadarMarginLabel_{csv_name}_{guide_idx}",
                    color=(1.0, 1.0, 1.0, 1.0),
                    align_x="LEFT",
                )
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


def _forest_random_effects_summary(rows):
    """Return a DL random-effects summary with modified HK CI."""
    clean = []
    for row in rows:
        try:
            mean = float(row["mean"])
            se = float(row["se"])
        except (KeyError, TypeError, ValueError):
            continue
        if np.isfinite(mean) and np.isfinite(se) and se > 0:
            clean.append((mean, se))
    if len(clean) < 2:
        return None
    means = np.asarray([x[0] for x in clean], dtype=float)
    variances = np.asarray([x[1] ** 2 for x in clean], dtype=float)
    wf = 1.0 / variances
    fixed = float(np.sum(wf * means) / np.sum(wf))
    q = float(np.sum(wf * (means - fixed) ** 2))
    k = len(clean)
    df = k - 1
    c = float(np.sum(wf) - np.sum(wf ** 2) / np.sum(wf))
    tau2 = max(0.0, (q - df) / c) if c > 1e-15 else 0.0
    wr = 1.0 / (variances + tau2)
    pooled = float(np.sum(wr * means) / np.sum(wr))
    conventional_se = float(np.sqrt(1.0 / np.sum(wr)))
    if k >= 3:
        hk = float(np.sum(wr * (means - pooled) ** 2) / df)
        pooled_se = conventional_se * math.sqrt(max(hk, 1.0))
        critical = _forest_t_critical_95(df)
    else:
        pooled_se = conventional_se
        critical = 1.96
    low = pooled - critical * pooled_se
    high = pooled + critical * pooled_se
    i2 = max(0.0, (q - df) / q * 100.0) if q > 1e-15 else 0.0
    total = float(np.sum(wr))
    return {"mean": pooled, "ci_low": low, "ci_high": high, "tau2": tau2,
            "i2": i2, "weights": [float(100.0 * w / total) for w in wr]}


def draw_multi_metric_forest_plot_3d(
    groups,
    axis_scale_x=5.0,
    axis_scale_y=7.0,
    z_pos=0.0,
    point_size=0.14,
    line_thickness=0.025,
    scale_label="z-score",
    palette_name=None,
):
    """Draw a descriptive z-score forest plot for one or more metrics.

    Rows are users/CSVs. Intervals use an effective sample size adjusted for
    lag-1 serial correlation. No meta-analytic weights, heterogeneity statistics
    or pooled diamond are drawn because one session per user does not constitute
    a conventional set of independent studies.
    """
    prepared = []
    total_lines = 0
    for g_idx, group in enumerate(groups):
        rows = []
        for row in group.get("rows", []):
            try:
                mean = float(row["mean"])
                low = float(row["ci_low"])
                high = float(row["ci_high"])
                se = float(row["se"])
                n_eff = float(row.get("n_eff", row.get("n", 0)))
            except (KeyError, TypeError, ValueError):
                continue
            if all(np.isfinite(v) for v in (mean, low, high, se, n_eff)) and se > 0 and n_eff >= 2:
                item = dict(row)
                item.update(mean=mean, ci_low=min(low, high), ci_high=max(low, high), se=se, n_eff=n_eff)
                rows.append(item)
        if not rows:
            continue
        prepared.append({
            "label": str(group.get("label", f"Metric {g_idx + 1}")),
            "rows": rows,
            "color_index": g_idx,
            "reference_mean": float(group.get("reference_mean", 0.0)),
            "reference_std": float(group.get("reference_std", 1.0)),
            "reference_n": int(group.get("reference_n", 0)),
        })
        total_lines += len(rows) + 1
    if not prepared:
        return None

    value_range = (-3.0, 3.0)
    safe = _forest_safe_name("ZScoreDescriptive")
    white = (0.94, 0.94, 0.97, 1.0)
    subtle = (0.72, 0.74, 0.80, 1.0)
    null_col = (0.88, 0.88, 0.92, 1.0)
    left_x, right_x, n_x = -2.45, axis_scale_x + 0.55, axis_scale_x + 3.25
    top = axis_scale_y - 0.15
    bottom = 0.45
    gap = max((top - bottom) / max(total_lines, 1), 0.25)

    def _clip(value):
        return min(max(float(value), value_range[0]), value_range[1])

    def _draw_truncation_arrow(x, y, direction, name, color):
        """Small chevron indicating that a confidence interval continues off-axis."""
        dx = 0.12 * (1.0 if direction > 0 else -1.0)
        create_axis(Vector((x - dx, y - 0.07, z_pos)), Vector((x, y, z_pos)), color, f"{name}A", radius=line_thickness * 0.55, vertices=6)
        create_axis(Vector((x - dx, y + 0.07, z_pos)), Vector((x, y, z_pos)), color, f"{name}B", radius=line_thickness * 0.55, vertices=6)

    metric_count = len(prepared)
    create_text_label(
        "Descriptive forest plot · z-score normalized metrics",
        (axis_scale_x * 0.5, axis_scale_y + 1.02, z_pos),
        0.39,
        f"ForestMultiTitle_{safe}",
    )
    subtitle = (
        "Per-metric user-mean z-scores · 0 = reference mean · CI adjusted for serial correlation · z-score does not imply normality"
        if metric_count > 1
        else "User-mean z-scores · 0 = reference mean · CI adjusted for serial correlation · z-score does not imply normality"
    )
    create_text_label(subtitle, (axis_scale_x * 0.5, axis_scale_y + 0.68, z_pos), 0.19, f"ForestMultiSub_{safe}", color=subtle)
    create_text_label("User / CSV", (left_x, axis_scale_y + 0.27, z_pos), 0.28, f"ForestMultiHeaderUser_{safe}", align_x="LEFT", color=subtle)
    create_text_label("Mean z-score [adjusted 95% CI]", (right_x, axis_scale_y + 0.27, z_pos), 0.20, f"ForestMultiHeaderEffect_{safe}", align_x="LEFT", color=subtle)
    create_text_label("N eff.", (n_x, axis_scale_y + 0.27, z_pos), 0.22, f"ForestMultiHeaderN_{safe}", align_x="LEFT", color=subtle)

    axis_y = 0.05
    create_axis(Vector((0, axis_y, z_pos)), Vector((axis_scale_x, axis_y, z_pos)), white, f"ForestMultiAxis_{safe}", radius=0.012, vertices=8)
    for idx, tick in enumerate([-3, -2, -1, 0, 1, 2, 3]):
        x = _forest_map_value(float(tick), value_range, axis_scale_x)
        create_axis(Vector((x, axis_y - 0.06, z_pos)), Vector((x, axis_y + 0.06, z_pos)), subtle, f"ForestMultiTick_{safe}_{idx}", radius=0.008, vertices=6)
        create_text_label(_forest_format_value(float(tick)), (x, axis_y - 0.31, z_pos), 0.23, f"ForestMultiTickLabel_{safe}_{idx}", color=subtle)
    null_x = _forest_map_value(0.0, value_range, axis_scale_x)
    create_axis(Vector((null_x, axis_y, z_pos)), Vector((null_x, top + gap * 0.4, z_pos)), null_col, f"ForestMultiNull_{safe}", radius=0.011, vertices=8)
    create_text_label("Reference mean", (null_x, top + gap * 0.57, z_pos), 0.16, f"ForestMultiNullLabel_{safe}", color=subtle)

    y = top
    for g_idx, group in enumerate(prepared):
        color = csv_color_by_index(g_idx, palette_name)
        label = group["label"]
        ref_n = int(group.get("reference_n", 0))
        ref_mean = group.get("reference_mean", 0.0)
        ref_std = group.get("reference_std", 1.0)
        group_label = f"{label} · user-mean μ={_forest_format_value(ref_mean)} · between-user σ={_forest_format_value(ref_std)} · users={ref_n}"
        create_text_label(group_label, (left_x, y, z_pos), 0.24, f"ForestMultiGroup_{safe}_{g_idx}", align_x="LEFT", color=color)
        y -= gap
        for r_idx, row in enumerate(group["rows"]):
            low_truncated = row["ci_low"] < value_range[0]
            high_truncated = row["ci_high"] > value_range[1]
            x0 = _forest_map_value(_clip(row["ci_low"]), value_range, axis_scale_x)
            x1 = _forest_map_value(_clip(row["ci_high"]), value_range, axis_scale_x)
            xm = _forest_map_value(_clip(row["mean"]), value_range, axis_scale_x)
            create_axis(Vector((x0, y, z_pos)), Vector((x1, y, z_pos)), color, f"ForestMultiCI_{safe}_{g_idx}_{r_idx}", radius=line_thickness, vertices=8)
            if low_truncated:
                _draw_truncation_arrow(x0, y, -1, f"ForestMultiArrowL_{safe}_{g_idx}_{r_idx}", color)
            else:
                create_axis(Vector((x0, y-0.075, z_pos)), Vector((x0, y+0.075, z_pos)), color, f"ForestMultiCapL_{safe}_{g_idx}_{r_idx}", radius=line_thickness*0.55, vertices=6)
            if high_truncated:
                _draw_truncation_arrow(x1, y, 1, f"ForestMultiArrowR_{safe}_{g_idx}_{r_idx}", color)
            else:
                create_axis(Vector((x1, y-0.075, z_pos)), Vector((x1, y+0.075, z_pos)), color, f"ForestMultiCapR_{safe}_{g_idx}_{r_idx}", radius=line_thickness*0.55, vertices=6)
            _create_forest_square_marker(Vector((xm, y, z_pos)), f"ForestMultiPoint_{safe}_{g_idx}_{r_idx}", color, size=point_size)
            create_text_label(str(row.get("csv_name", f"User {r_idx+1}")), (left_x, y-0.02, z_pos), 0.21, f"ForestMultiUser_{safe}_{g_idx}_{r_idx}", align_x="LEFT", color=white)
            create_text_label(_forest_effect_label(row["mean"], row["ci_low"], row["ci_high"], 0), (right_x, y-0.02, z_pos), 0.20, f"ForestMultiEffect_{safe}_{g_idx}_{r_idx}", align_x="LEFT", color=white)
            n_eff_text = f"{row['n_eff']:.1f}" if row["n_eff"] < 100 else f"{row['n_eff']:.0f}"
            create_text_label(n_eff_text, (n_x, y-0.02, z_pos), 0.20, f"ForestMultiN_{safe}_{g_idx}_{r_idx}", align_x="LEFT", color=white)
            y -= gap

    return {"groups": prepared, "value_range": value_range, "null_value": 0.0, "scale": scale_label, "descriptive": True}
