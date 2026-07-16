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
import heapq
from itertools import product
from typing import Iterable, Sequence, Tuple, List, Optional

import bpy
import bmesh
from collections import deque
import numpy as np
from mathutils import Vector

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


class _OctreeNode:
    """Compact point octree used for nearest-neighbour queries."""

    __slots__ = (
        "minimum", "maximum", "points", "children", "depth",
        "max_depth", "max_items", "limit_mode",
    )

    def __init__(
        self,
        points: Sequence[Vector],
        minimum: Vector,
        maximum: Vector,
        *,
        depth: int,
        max_depth: int,
        max_items: int,
        limit_mode: str,
    ) -> None:
        self.minimum = minimum
        self.maximum = maximum
        self.points: list[Vector] = list(points)
        self.children: list[_OctreeNode] = []
        self.depth = depth
        self.max_depth = max(1, int(max_depth))
        self.max_items = max(1, int(max_items))
        self.limit_mode = str(limit_mode or "BOTH").upper()
        self._subdivide_if_needed()

    def _must_stop(self) -> bool:
        depth_reached = self.depth >= self.max_depth
        item_limit_reached = len(self.points) <= self.max_items

        if self.limit_mode == "DEPTH":
            return depth_reached
        if self.limit_mode == "ELEMENTS":
            # A hard safety depth prevents pathological duplicate-point recursion.
            return item_limit_reached or self.depth >= 32
        return depth_reached or item_limit_reached

    def _subdivide_if_needed(self) -> None:
        if len(self.points) <= 1 or self._must_stop():
            return

        center = (self.minimum + self.maximum) * 0.5
        buckets: list[list[Vector]] = [[] for _ in range(8)]

        for point in self.points:
            index = (
                (1 if point.x >= center.x else 0)
                | (2 if point.y >= center.y else 0)
                | (4 if point.z >= center.z else 0)
            )
            buckets[index].append(point)

        non_empty = [bucket for bucket in buckets if bucket]
        if len(non_empty) <= 1:
            return

        children: list[_OctreeNode] = []
        for index, bucket in enumerate(buckets):
            if not bucket:
                continue
            child_min = Vector((
                center.x if index & 1 else self.minimum.x,
                center.y if index & 2 else self.minimum.y,
                center.z if index & 4 else self.minimum.z,
            ))
            child_max = Vector((
                self.maximum.x if index & 1 else center.x,
                self.maximum.y if index & 2 else center.y,
                self.maximum.z if index & 4 else center.z,
            ))
            children.append(_OctreeNode(
                bucket,
                child_min,
                child_max,
                depth=self.depth + 1,
                max_depth=self.max_depth,
                max_items=self.max_items,
                limit_mode=self.limit_mode,
            ))

        if children:
            self.children = children
            self.points = []

    def bbox_distance_squared(self, point: Vector) -> float:
        dx = max(self.minimum.x - point.x, 0.0, point.x - self.maximum.x)
        dy = max(self.minimum.y - point.y, 0.0, point.y - self.maximum.y)
        dz = max(self.minimum.z - point.z, 0.0, point.z - self.maximum.z)
        return dx * dx + dy * dy + dz * dz


class PointOctree:
    """Point octree supporting exact nearest-neighbour distance queries."""

    def __init__(
        self,
        points: Sequence[Vector],
        *,
        max_depth: int = 8,
        max_items: int = 32,
        limit_mode: str = "BOTH",
    ) -> None:
        clean = [point.copy() for point in points]
        if not clean:
            self.root = None
            return

        minimum = Vector((
            min(point.x for point in clean),
            min(point.y for point in clean),
            min(point.z for point in clean),
        ))
        maximum = Vector((
            max(point.x for point in clean),
            max(point.y for point in clean),
            max(point.z for point in clean),
        ))

        # Give zero-size axes a tiny extent so all child boxes remain valid.
        epsilon = 1e-9
        for axis in range(3):
            if maximum[axis] - minimum[axis] < epsilon:
                minimum[axis] -= epsilon
                maximum[axis] += epsilon

        self.root = _OctreeNode(
            clean,
            minimum,
            maximum,
            depth=0,
            max_depth=max_depth,
            max_items=max_items,
            limit_mode=limit_mode,
        )

    def nearest_distance(self, point: Vector) -> float:
        if self.root is None:
            return 0.0

        best_squared = math.inf
        queue: list[tuple[float, int, _OctreeNode]] = []
        serial = 0
        heapq.heappush(queue, (self.root.bbox_distance_squared(point), serial, self.root))

        while queue:
            box_distance, _, node = heapq.heappop(queue)
            if box_distance >= best_squared:
                continue

            if node.children:
                for child in node.children:
                    child_distance = child.bbox_distance_squared(point)
                    if child_distance < best_squared:
                        serial += 1
                        heapq.heappush(queue, (child_distance, serial, child))
            else:
                for candidate in node.points:
                    distance_squared = (point - candidate).length_squared
                    if distance_squared < best_squared:
                        best_squared = distance_squared

        return math.sqrt(best_squared) if math.isfinite(best_squared) else 0.0


def _nearest_distances_octree(
    source: Sequence[Vector],
    target: Sequence[Vector],
    *,
    max_depth: int = 8,
    max_items: int = 32,
    limit_mode: str = "BOTH",
) -> list[float]:
    if not source or not target:
        return []
    tree = PointOctree(
        target,
        max_depth=max_depth,
        max_items=max_items,
        limit_mode=limit_mode,
    )
    return [tree.nearest_distance(vertex) for vertex in source]


def _principal_frame(coords: Sequence[Vector]) -> tuple[np.ndarray, np.ndarray]:
    """Return centroid and a right-handed PCA frame for a point cloud."""
    array = np.asarray([[v.x, v.y, v.z] for v in coords], dtype=float)
    centroid = np.mean(array, axis=0)
    centered = array - centroid

    if len(array) < 3 or np.allclose(centered, 0.0):
        return centroid, np.eye(3, dtype=float)

    covariance = np.cov(centered, rowvar=False, bias=True)
    values, vectors = np.linalg.eigh(covariance)
    order = np.argsort(values)[::-1]
    frame = vectors[:, order]

    if np.linalg.det(frame) < 0.0:
        frame[:, 2] *= -1.0
    return centroid, frame


def _coords_in_frame(
    coords: Sequence[Vector],
    centroid: np.ndarray,
    frame: np.ndarray,
    signs: tuple[int, int, int] = (1, 1, 1),
) -> list[Vector]:
    array = np.asarray([[v.x, v.y, v.z] for v in coords], dtype=float)
    aligned = (array - centroid) @ frame
    aligned *= np.asarray(signs, dtype=float)
    return [Vector(row) for row in aligned]


def align_coordinate_sets(
    reference_coords: Iterable[object],
    target_coords: Iterable[object],
    *,
    max_depth: int = 8,
    max_items: int = 32,
    limit_mode: str = "BOTH",
) -> tuple[list[Vector], list[Vector]]:
    """Virtually align two point sets by centre of mass and PCA rotation.

    No Blender object transform is modified. The function works only with copied
    coordinates. PCA axis signs are ambiguous, so the four right-handed sign
    combinations are tested and the closest target orientation is retained.
    """
    refs = _as_vector_list(reference_coords)
    targets = _as_vector_list(target_coords)
    if not refs or not targets:
        return refs, targets

    ref_centroid, ref_frame = _principal_frame(refs)
    target_centroid, target_frame = _principal_frame(targets)
    aligned_refs = _coords_in_frame(refs, ref_centroid, ref_frame)

    sign_options = (
        (1, 1, 1),
        (1, -1, -1),
        (-1, 1, -1),
        (-1, -1, 1),
    )
    best_targets: list[Vector] | None = None
    best_score = math.inf

    # Use a bounded sample only to choose the PCA sign; the final Hausdorff
    # distance still uses every point.
    sample_step_ref = max(1, len(aligned_refs) // 512)
    sample_refs = aligned_refs[::sample_step_ref]

    for signs in sign_options:
        candidate = _coords_in_frame(targets, target_centroid, target_frame, signs)
        sample_step_target = max(1, len(candidate) // 512)
        sample_targets = candidate[::sample_step_target]
        distances = _nearest_distances_octree(
            sample_targets,
            sample_refs,
            max_depth=max_depth,
            max_items=max_items,
            limit_mode=limit_mode,
        )
        score = max(distances, default=0.0)
        if score < best_score:
            best_score = score
            best_targets = candidate

    return aligned_refs, best_targets or targets


def calculate_hausdorff_distance_from_coords(
    reference_coords: Iterable[object],
    target_coords: Iterable[object],
    *,
    octree_max_depth: int = 8,
    octree_max_items: int = 32,
    octree_limit_mode: str = "BOTH",
    align: bool = False,
) -> float:
    """Symmetric Hausdorff distance using an exact point octree."""
    refs = _as_vector_list(reference_coords)
    targets = _as_vector_list(target_coords)
    if not refs or not targets:
        return 0.0

    if align:
        refs, targets = align_coordinate_sets(
            refs,
            targets,
            max_depth=octree_max_depth,
            max_items=octree_max_items,
            limit_mode=octree_limit_mode,
        )

    target_to_ref = _nearest_distances_octree(
        targets,
        refs,
        max_depth=octree_max_depth,
        max_items=octree_max_items,
        limit_mode=octree_limit_mode,
    )
    ref_to_target = _nearest_distances_octree(
        refs,
        targets,
        max_depth=octree_max_depth,
        max_items=octree_max_items,
        limit_mode=octree_limit_mode,
    )
    return max(max(target_to_ref, default=0.0), max(ref_to_target, default=0.0))


def _bbox_diag(coords: Sequence[Vector]) -> float:
    if not coords:
        return 1e-8
    dx = max(v.x for v in coords) - min(v.x for v in coords)
    dy = max(v.y for v in coords) - min(v.y for v in coords)
    dz = max(v.z for v in coords) - min(v.z for v in coords)
    return max(math.sqrt(dx ** 2 + dy ** 2 + dz ** 2), 1e-8)


def _ordered_rigid_match(
    reference_coords: Sequence[Vector],
    target_coords: Sequence[Vector],
    *,
    relative_tolerance: float = 1e-7,
) -> bool:
    """Return True when ordered points differ only by a rigid transform.

    Mesh copies preserve vertex order. A Kabsch alignment therefore provides a
    deterministic identity check that is not affected by PCA ambiguity in
    symmetric shapes such as spheres or Suzanne. No Blender object is moved.
    """
    if len(reference_coords) != len(target_coords) or not reference_coords:
        return False

    ref = np.asarray([[v.x, v.y, v.z] for v in reference_coords], dtype=float)
    target = np.asarray([[v.x, v.y, v.z] for v in target_coords], dtype=float)

    ref_centered = ref - ref.mean(axis=0)
    target_centered = target - target.mean(axis=0)

    try:
        covariance = target_centered.T @ ref_centered
        u, _singular, vt = np.linalg.svd(covariance)
        rotation = u @ vt
        if np.linalg.det(rotation) < 0.0:
            u[:, -1] *= -1.0
            rotation = u @ vt
    except np.linalg.LinAlgError:
        return False

    aligned = target_centered @ rotation
    max_error = float(np.linalg.norm(aligned - ref_centered, axis=1).max(initial=0.0))
    scale = max(_bbox_diag(reference_coords), _bbox_diag(target_coords), 1.0)
    return max_error <= relative_tolerance * scale


def calculate_similarity_from_coords(
    reference_coords: Iterable[object],
    target_coords: Iterable[object],
    obj_metrics: Optional[dict[str, float]] = None,
    *,
    octree_max_depth: int = 8,
    octree_max_items: int = 32,
    octree_limit_mode: str = "BOTH",
    align: bool = True,
) -> float:
    """Calculate similarity after an invisible rigid point-cloud alignment."""
    refs = _as_vector_list(reference_coords)
    targets = _as_vector_list(target_coords)
    if not refs or not targets:
        return 0.0

    if align:
        refs, targets = align_coordinate_sets(
            refs,
            targets,
            max_depth=octree_max_depth,
            max_items=octree_max_items,
            limit_mode=octree_limit_mode,
        )

    hausdorff_dist = calculate_hausdorff_distance_from_coords(
        refs,
        targets,
        octree_max_depth=octree_max_depth,
        octree_max_items=octree_max_items,
        octree_limit_mode=octree_limit_mode,
        align=False,
    )
    bbox_diag = _bbox_diag(refs)

    # Mesh-quality metrics are reported separately and must not reduce the
    # similarity of two identical shapes. Similarity measures only difference
    # between the reference and target.
    similarity = max(0.0, 100.0 * (1.0 - hausdorff_dist / bbox_diag))

    # Coordinate sets do not carry Blender object identity. Reserve exactly
    # 100 for calculate_similarity(reference_obj, target_obj) when both
    # arguments are the very same Blender object. Distinct objects, even exact
    # duplicates, remain strictly below 100.
    return round(min(similarity, 99.99), 2)


def object_world_coordinates(obj) -> list[Vector]:
    if not obj or getattr(obj, "type", None) != 'MESH':
        return []
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def calculate_similarity(
    reference_obj,
    target_obj,
    obj_metrics=None,
    *,
    octree_max_depth: int = 8,
    octree_max_items: int = 32,
    octree_limit_mode: str = "BOTH",
    align: bool = True,
) -> float:
    if not reference_obj or not target_obj:
        return 0.0
    if reference_obj is target_obj:
        return 100.0
    return calculate_similarity_from_coords(
        object_world_coordinates(reference_obj),
        object_world_coordinates(target_obj),
        obj_metrics=obj_metrics,
        octree_max_depth=octree_max_depth,
        octree_max_items=octree_max_items,
        octree_limit_mode=octree_limit_mode,
        align=align,
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


def calculate_model_metrics(
    obj,
    reference_obj=None,
    *,
    octree_max_depth: int = 8,
    octree_max_items: int = 32,
    octree_limit_mode: str = "BOTH",
    align_similarity: bool = True,
) -> dict[str, object]:
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

        similarity_geom = calculate_similarity(
            reference_obj,
            obj,
            None,
            octree_max_depth=octree_max_depth,
            octree_max_items=octree_max_items,
            octree_limit_mode=octree_limit_mode,
            align=align_similarity,
        ) if reference_obj else 0.0
        similarity_topo = calculate_topology_similarity(reference_obj, obj) if reference_obj else 0.0

        if reference_obj is obj and reference_obj is not None:
            combined_similarity = 100.0
        elif reference_obj is not None:
            combined_similarity = min(
                99.99,
                0.7 * similarity_geom + 0.3 * similarity_topo,
            )
        else:
            combined_similarity = 0.0

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
            "Similarity": round(combined_similarity, 2),
        }
        return {key: (round(value, 4) if isinstance(value, float) else value) for key, value in result.items()}
    finally:
        bm.free()


def register():
    print("Registrando funciones de utils")


def unregister():
    print("Desregistrando funciones de utils")
