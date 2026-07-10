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
import csv
import math
from typing import Iterable, Sequence, Tuple, List, Optional

import bpy
import bmesh
from collections import deque
import numpy as np
from mathutils import Vector
try:
    from mathutils.kdtree import KDTree
except ImportError:  # Permite importar parte del módulo fuera de Blender.
    KDTree = None


def detect_csvs(folder: str) -> list[str]:
    if not folder:
        return []
    folder = bpy.path.abspath(folder)
    if os.path.isfile(folder) and folder.lower().endswith(".csv"):
        return [folder]
    if not os.path.isdir(folder):
        return []
    return [os.path.join(folder, f) for f in sorted(os.listdir(folder)) if f.lower().endswith(".csv")]


def _row_has_invalid_numbers(row: dict[str, str], row_number: int) -> None:
    """Abort CSV import if a numeric cell contains NaN or infinite values."""
    for key, raw in row.items():
        if raw in (None, ""):
            continue
        value = str(raw).strip().replace(",", ".")
        try:
            number = float(value)
        except ValueError:
            continue
        if not math.isfinite(number):
            raise ValueError(f"CSV inválido: valor no finito en fila {row_number}, columna '{key}': {raw}")


def read_csv(file_path: str) -> tuple[list[str], list[dict[str, str]]]:
    """Read CSV using UTF-8 first and Latin-1 as compatibility fallback.

    The function validates numeric cells so corrupted NaN/Inf values never reach
    the 3D viewport or metric calculation layer.
    """
    last_error: Optional[UnicodeDecodeError] = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            data: list[dict[str, str]] = []
            with open(file_path, newline='', encoding=encoding) as f:
                reader = csv.DictReader(f)
                headers = [str(h).strip().lstrip("\ufeff") for h in (reader.fieldnames or [])]
                for row_number, row in enumerate(reader, start=2):
                    clean_row = {str(k).strip().lstrip("\ufeff"): v for k, v in dict(row).items()}
                    _row_has_invalid_numbers(clean_row, row_number)
                    data.append(clean_row)
            return headers, data
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    return [], []


def almost_equal(v1, v2, tol=1e-4):
    return all(abs(a - b) <= tol for a, b in zip(v1, v2))


def count_uv_islands(bm):
    uv_layer = bm.loops.layers.uv.active
    if not uv_layer:
        return 0
    visited_faces = set()
    islands = 0
    for f in bm.faces:
        if f.index in visited_faces:
            continue
        stack = [f]
        while stack:
            face = stack.pop()
            if face.index in visited_faces:
                continue
            visited_faces.add(face.index)
            for e in face.edges:
                for lf in e.link_faces:
                    if lf.index in visited_faces:
                        continue
                    shared_uv = False
                    for l1 in face.loops:
                        uv1 = l1[uv_layer].uv
                        for l2 in lf.loops:
                            uv2 = l2[uv_layer].uv
                            if almost_equal(uv1, uv2):
                                shared_uv = True
                                break
                        if shared_uv:
                            break
                    if shared_uv:
                        stack.append(lf)
        islands += 1
    return islands




def calculate_normal_percentage(obj, bm=None):
    """
    Calcula el porcentaje de caras cuya orientación difiere de la
    orientación obtenida por Blender al recalcular las normales hacia fuera.

    Es mucho más fiable que comparar las normales con el centro geométrico,
    especialmente en mallas cóncavas como Lucy.

    La malla original no se modifica.
    """

    if obj is None or obj.type != 'MESH':
        return 0.0

    source_bm = None
    check_bm = None

    try:
        if bm is None:
            source_bm = bmesh.new()
            source_bm.from_mesh(obj.data)
        else:
            source_bm = bm

        source_bm.normal_update()
        source_bm.faces.ensure_lookup_table()

        total_faces = len(source_bm.faces)

        if total_faces == 0:
            return 0.0

        # Trabajamos sobre una copia para no modificar la malla original.
        check_bm = source_bm.copy()
        check_bm.normal_update()
        check_bm.faces.ensure_lookup_table()

        # Guardamos las normales antes de recalcularlas.
        original_normals = [
            face.normal.copy()
            for face in check_bm.faces
        ]

        # Equivalente a recalcular las normales consistentemente hacia fuera
        # en una malla cerrada.
        bmesh.ops.recalc_face_normals(
            check_bm,
            faces=list(check_bm.faces),
        )

        check_bm.normal_update()
        check_bm.faces.ensure_lookup_table()

        flipped = 0

        for original_normal, recalculated_face in zip(
            original_normals,
            check_bm.faces,
        ):
            # Una normal opuesta produce un producto escalar cercano a -1.
            if original_normal.dot(recalculated_face.normal) < 0.0:
                flipped += 1

        return round(100.0 * flipped / total_faces, 2)

    finally:
        if check_bm is not None:
            check_bm.free()

        if bm is None and source_bm is not None:
            source_bm.free()


def _uv_polygon_area(uvs) -> float:
    """Triangulated area of one UV polygon using the same method as UVR_Analysis."""
    if len(uvs) < 3:
        return 0.0
    area = 0.0
    for i in range(1, len(uvs) - 1):
        area += abs((uvs[i] - uvs[0]).cross(uvs[i + 1] - uvs[0])) * 0.5
    return area


def calculate_uv_area(bm, uv_layer=None) -> float:
    """Total UV area from real UV polygons, not from the UV bounding box."""
    if uv_layer is None:
        uv_layer = bm.loops.layers.uv.active
    if not uv_layer:
        return 0.0
    total_area = 0.0
    for face in bm.faces:
        uvs = [loop[uv_layer].uv.copy() for loop in face.loops]
        total_area += _uv_polygon_area(uvs)
    return round(total_area, 4)


def calculate_uv_stretch(obj, bm=None, uv_layer=None) -> float:
    """Average UV stretch using per-face 3D/UV area scaling and edge ratios.

    Adapted from the reference UVR_Analysis operator: each face computes a UV
    scale factor from 3D area and UV area, then averages edge length deviation.
    """
    owns_bm = False
    if bm is None:
        bm = bmesh.new()
        owns_bm = True
        try:
            bm.from_mesh(obj.data)
        except Exception:
            bm.free()
            raise
    try:
        if uv_layer is None:
            uv_layer = bm.loops.layers.uv.active
        if not uv_layer:
            return 0.0

        stretch_values = []
        for face in bm.faces:
            verts = [loop.vert for loop in face.loops]
            uvs = [loop[uv_layer].uv.copy() for loop in face.loops]
            area_3d = face.calc_area()
            area_uv = _uv_polygon_area(uvs)
            scale_factor = (area_3d ** 0.5) / (area_uv ** 0.5) if area_uv > 1e-8 else 1.0

            edge_stretches = []
            for i in range(len(verts)):
                v1 = verts[i]
                v2 = verts[(i + 1) % len(verts)]
                uv1 = uvs[i] * scale_factor
                uv2 = uvs[(i + 1) % len(uvs)] * scale_factor
                length_3d = (v1.co - v2.co).length
                if length_3d > 1e-5:
                    length_uv = (uv1 - uv2).length
                    edge_stretches.append(abs(length_uv / length_3d - 1.0))
            if edge_stretches:
                stretch_values.append(sum(edge_stretches) / len(edge_stretches))

        return round(float(np.mean(stretch_values)) if stretch_values else 0.0, 4)
    finally:
        if owns_bm:
            bm.free()


def calculate_uv_texel_density(obj, bm=None, uv_layer=None) -> float:
    """Global UV texel density from total UV area over total local 3D area.

    Uses triangulated UV area and local mesh surface area. Aggregating before
    dividing avoids small faces dominating the result and makes the value stable
    against topology density.
    """
    owns_bm = False
    if bm is None:
        bm = bmesh.new()
        owns_bm = True
        try:
            bm.from_mesh(obj.data)
        except Exception:
            bm.free()
            raise
    try:
        if uv_layer is None:
            uv_layer = bm.loops.layers.uv.active
        if not uv_layer:
            return 0.0

        total_uv_area = 0.0
        total_3d_area = 0.0
        for face in bm.faces:
            area_3d = face.calc_area()
            if area_3d <= 1e-12:
                continue
            uvs = [loop[uv_layer].uv.copy() for loop in face.loops]
            area_uv = _uv_polygon_area(uvs)
            if area_uv > 0.0:
                total_uv_area += area_uv
                total_3d_area += area_3d

        if total_3d_area <= 1e-12 or total_uv_area <= 0.0:
            return 0.0
        return round(math.sqrt(total_uv_area / total_3d_area), 4)
    finally:
        if owns_bm:
            bm.free()


def calculate_angle_median(bm):
    """Mean 3D edge angle, matching the reference UVR_Analysis behavior.

    Two-sided face angles above 90 degrees are folded with 180-angle, so the
    reported value represents the smaller visible angle between adjacent faces.
    """
    angles = []
    bm.normal_update()
    for edge in bm.edges:
        if edge.is_valid and len(edge.link_faces) == 2:
            try:
                angle = abs(math.degrees(edge.calc_face_angle()))
            except ValueError:
                continue
            if angle > 90.0:
                angle = 180.0 - angle
            angles.append(angle)
    return round(float(np.mean(angles)) if angles else 0.0, 2)


def object_has_applied_transforms(obj, tol=1e-5):
    scale_ok = all(abs(s - 1.0) <= tol for s in obj.scale)
    rot_ok = all(abs(r) <= tol for r in obj.rotation_euler)
    return scale_ok and rot_ok


def object_is_at_origin(obj, tol=1e-5):
    return all(abs(v) <= tol for v in obj.location)


def calculate_topology_similarity(reference_obj, target_obj):
    if not reference_obj or not target_obj:
        return 0.0
    ref_faces = len(reference_obj.data.polygons)
    target_faces = len(target_obj.data.polygons)
    if ref_faces == 0 or target_faces == 0:
        return 0.0
    verts_sim = min(len(reference_obj.data.vertices), len(target_obj.data.vertices)) / max(len(reference_obj.data.vertices), len(target_obj.data.vertices))
    edges_sim = min(len(reference_obj.data.edges), len(target_obj.data.edges)) / max(len(reference_obj.data.edges), len(target_obj.data.edges))
    faces_sim = min(ref_faces, target_faces) / max(ref_faces, target_faces)
    return round(100 * (verts_sim + edges_sim + faces_sim) / 3, 2)


def _as_vector_list(coords: Iterable[object]) -> list[Vector]:
    result: list[Vector] = []
    for coord in coords or []:
        v = coord if isinstance(coord, Vector) else Vector(coord)
        if math.isfinite(v.x) and math.isfinite(v.y) and math.isfinite(v.z):
            result.append(v.copy())
    return result


def _nearest_distances_kdtree(source: Sequence[Vector], target: Sequence[Vector]) -> list[float]:
    """Nearest-neighbour distances using Blender KDTree: O(N log M) instead of O(N*M)."""
    if not source or not target:
        return []
    if KDTree is None:
        # Conservative fallback outside Blender; tests can still validate logic.
        return [min((s - t).length for t in target) for s in source]
    tree = KDTree(len(target))
    for index, vertex in enumerate(target):
        tree.insert(vertex, index)
    tree.balance()
    return [float(tree.find(vertex)[2]) for vertex in source]


def calculate_hausdorff_distance_from_coords(reference_coords: Iterable[object], target_coords: Iterable[object]) -> float:
    """Symmetric Hausdorff distance between two coordinate sets."""
    refs = _as_vector_list(reference_coords)
    targets = _as_vector_list(target_coords)
    if not refs or not targets:
        return 0.0
    target_to_ref = _nearest_distances_kdtree(targets, refs)
    ref_to_target = _nearest_distances_kdtree(refs, targets)
    return max(max(target_to_ref, default=0.0), max(ref_to_target, default=0.0))


def _bbox_diag(coords: Sequence[Vector]) -> float:
    if not coords:
        return 1e-8
    dx = max(v.x for v in coords) - min(v.x for v in coords)
    dy = max(v.y for v in coords) - min(v.y for v in coords)
    dz = max(v.z for v in coords) - min(v.z for v in coords)
    return max(math.sqrt(dx ** 2 + dy ** 2 + dz ** 2), 1e-8)


def calculate_similarity_from_coords(reference_coords: Iterable[object], target_coords: Iterable[object], obj_metrics: Optional[dict[str, float]] = None) -> float:
    """Calculate mesh similarity from raw coordinates, decoupled from bpy objects."""
    refs = _as_vector_list(reference_coords)
    targets = _as_vector_list(target_coords)
    if not refs or not targets:
        return 0.0

    hausdorff_dist = calculate_hausdorff_distance_from_coords(refs, targets)
    bbox_diag = _bbox_diag(refs)

    penalty = 0.0
    if obj_metrics:
        penalty += float(obj_metrics.get("Non_quads_percentage", 0.0)) / 100.0
        penalty += float(obj_metrics.get("Vertex_duplicate_percentage", obj_metrics.get("Vertex_duplicate", 0.0))) / 100.0

    similarity = max(0.0, 100.0 * (1 - hausdorff_dist / bbox_diag - penalty * 0.5))
    return round(similarity, 2)


def object_world_coordinates(obj) -> list[Vector]:
    if not obj or getattr(obj, "type", None) != 'MESH':
        return []
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def calculate_similarity(reference_obj, target_obj, obj_metrics=None) -> float:
    if not reference_obj or not target_obj:
        return 0.0
    return calculate_similarity_from_coords(
        object_world_coordinates(reference_obj),
        object_world_coordinates(target_obj),
        obj_metrics=obj_metrics,
    )


def calculate_median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    n = len(values)
    middle = n // 2
    if n % 2 == 1:
        return round(values[middle], 4)
    return round((values[middle - 1] + values[middle]) / 2.0, 4)


def calculate_model_metrics(obj, reference_obj=None) -> dict[str, object]:
    """Calcula métricas geométricas de una malla Blender.

    Mantiene la lógica de negocio fuera de la UI para que los operadores solo
    coordinen la selección de objetos y el almacenamiento del resultado.
    """
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.normal_update()
        total_faces = len(bm.faces)
        total_verts = len(bm.verts)
        non_quads = round((len([f for f in bm.faces if len(f.verts) != 4]) / total_faces * 100.0) if total_faces else 0.0, 2)

        temp_bm = bm.copy()
        try:
            bmesh.ops.remove_doubles(temp_bm, verts=temp_bm.verts, dist=0.0001)
            vertex_dup_count = max(total_verts - len(temp_bm.verts), 0)
            vertex_dup_percentage = round((vertex_dup_count / total_verts * 100.0) if total_verts else 0.0, 2)
        finally:
            temp_bm.free()

        visited: set[int] = set()
        parts = 0
        for face in bm.faces:
            if face.index in visited:
                continue
            stack = [face]
            while stack:
                current = stack.pop()
                if current.index in visited:
                    continue
                visited.add(current.index)
                for edge in current.edges:
                    for linked in edge.link_faces:
                        if linked.index not in visited:
                            stack.append(linked)
            parts += 1

        uv_layer = bm.loops.layers.uv.active
        if uv_layer:
            uv_coords = [loop[uv_layer].uv.copy() for face in bm.faces for loop in face.loops]
            if uv_coords:
                uv_area = calculate_uv_area(bm, uv_layer)
                uv_islands = count_uv_islands(bm)
                uv_stretch = calculate_uv_stretch(obj, bm, uv_layer)
                uv_textel_density = calculate_uv_texel_density(obj, bm, uv_layer)
            else:
                uv_area = uv_islands = uv_stretch = uv_textel_density = 0.0
        else:
            uv_area = uv_islands = uv_stretch = uv_textel_density = 0.0

        temp_metrics = {"Non_quads_percentage": non_quads, "Vertex_duplicate_percentage": vertex_dup_percentage}
        similarity_geom = calculate_similarity(reference_obj, obj, temp_metrics) if reference_obj else 0.0
        similarity_topo = calculate_topology_similarity(reference_obj, obj) if reference_obj else 0.0

        result = {
            "UV_area": uv_area,
            "UV_islands": int(uv_islands),
            "UV_stretch": uv_stretch,
            "UV_textel_density": uv_textel_density,
            "Normal_percentage": calculate_normal_percentage(obj, bm),
            "Transformations": object_has_applied_transforms(obj),
            "Position": object_is_at_origin(obj),
            "Non_quads_percentage": non_quads,
            "Vertex_duplicate": int(vertex_dup_count),
            "Vertex_duplicate_percentage": vertex_dup_percentage,
            "N_faces": total_faces,
            "N_meshes": parts,
            "Face_by_mesh": round((total_faces / parts) if parts else 0.0, 2),
            "Angle": calculate_angle_median(bm),
            "Similarity": round(0.7 * similarity_geom + 0.3 * similarity_topo, 2) if reference_obj else 0.0,
        }
        return {key: (round(value, 4) if isinstance(value, float) else value) for key, value in result.items()}
    finally:
        bm.free()


def register():
    print("Registrando funciones de utils")


def unregister():
    print("Desregistrando funciones de utils")
