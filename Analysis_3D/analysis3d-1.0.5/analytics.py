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

"""Lógica analítica pura para CSVs de interacción.

Este módulo no depende de Blender UI ni registra clases/paneles. Está diseñado
para poder probarse con unittest/pytest fuera de la capa de presentación.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np

try:  # Blender runtime
    from mathutils import Vector as _BlenderVector
except Exception:  # CPython tests
    _BlenderVector = None

try:
    from .constants import DEFAULT_BREAK_SPEED, DEFAULT_MAX_REASONABLE_SPEED
except ImportError:  # pragma: no cover
    from constants import DEFAULT_BREAK_SPEED, DEFAULT_MAX_REASONABLE_SPEED

logger = logging.getLogger(__name__)
ReportFn = Callable[[set[str], str], None]


@dataclass(frozen=True)
class _Vec3:
    x: float
    y: float
    z: float

    def __sub__(self, other: "_Vec3") -> "_Vec3":
        return _Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    @property
    def length(self) -> float:
        return float((self.x ** 2 + self.y ** 2 + self.z ** 2) ** 0.5)


def _vector3(values: Sequence[float]):
    if _BlenderVector is not None:
        return _BlenderVector(values)
    return _Vec3(float(values[0]), float(values[1]), float(values[2]))

ANALYSIS = {
    "A1": {"label": "Session duration", "typology": "Temporal"},
    "A2": {"label": "Pauses", "typology": "Temporal"},
    "A3": {"label": "Pauses by phase", "typology": "Temporal"},
    "A4": {"label": "View speed", "typology": "Spatial"},
    "A5": {"label": "Distance to object", "typology": "Spatial"},
    "A6": {"label": "View movement peaks", "typology": "Spatial"},
    "A7": {"label": "Idle movement peaks", "typology": "Spatial"},
    "A8": {"label": "Active movement peaks", "typology": "Spatial"},
    "A9": {"label": "Travel peaks", "typology": "Spatial"},
    "A10": {"label": "Shortcut reuse", "typology": "Strategy"},
    "A11": {"label": "Modifier changes", "typology": "Strategy"},
    "A12": {"label": "Vertex changes", "typology": "Strategy"},
    "A13": {"label": "Mesh issue changes", "typology": "Strategy"},
    "A14": {"label": "Work mode", "typology": "Strategy"},
    "A15": {"label": "UV work", "typology": "Strategy"},
    "A16": {"label": "Object changes", "typology": "Strategy"},
}


def safe_float(row: Mapping[str, Any], key: str, default: float = 0.0, report: ReportFn | None = None) -> float:
    try:
        raw = row.get(key, default)
        if raw in (None, "", "None"):
            return default
        return float(raw)
    except (ValueError, TypeError) as exc:
        msg = f"[safe_float] No se pudo convertir '{key}': {exc}"
        logger.warning(msg)
        if report is not None:
            report({"ERROR"}, msg)
        return default


def sanitize_name(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", str(value or "item"))


def series_to_array(values: Iterable[Any] | None) -> np.ndarray:
    if values is None:
        return np.asarray([], dtype=float)
    arr = np.asarray(list(values), dtype=float)
    return arr[np.isfinite(arr)] if arr.size else arr


def clamp_outliers(values: Iterable[Any] | None) -> np.ndarray:
    """Clamp outliers with a simple IQR rule, preserving the original sample count.

    G1 uses this to keep interaction curves readable when a CSV contains a few
    extreme spikes. Values are clipped to the Tukey fences instead of removed,
    so X/Y arrays stay aligned and no UI option is needed.
    """
    arr = series_to_array(values)
    if arr.size < 4:
        return arr

    q1, q3 = np.percentile(arr, [25.0, 75.0])
    iqr = q3 - q1
    if not np.isfinite(q1) or not np.isfinite(q3) or not np.isfinite(iqr) or iqr <= 0:
        return arr

    low = q1 - 1.5 * iqr
    high = q3 + 1.5 * iqr
    if low >= high:
        return arr
    return np.clip(arr, low, high)


def _csv_float(row: Mapping[str, Any], *keys: str, default: float = 0.0, report: ReportFn | None = None) -> float:
    """Lee un número aceptando varios nombres de columna y encabezados con espacios/BOM."""
    if not hasattr(row, "items"):
        return default
    normalized = {str(k).strip().lstrip("\ufeff").lower(): v for k, v in row.items()}
    for key in keys:
        norm_key = str(key).strip().lstrip("\ufeff").lower()
        if norm_key in normalized and normalized.get(norm_key) not in (None, ""):
            try:
                return float(str(normalized.get(norm_key)).strip().replace(",", "."))
            except (ValueError, TypeError) as exc:
                msg = f"[_csv_float] No se pudo convertir '{key}': {exc}"
                logger.warning(msg)
                if report is not None:
                    report({"ERROR"}, msg)
    return default

def _row_time(row: Mapping[str, Any]) -> float:
    ts = _csv_float(row, "TimeStamp", "Timestamp", "timestamp", default=None)

    if ts is not None:
        # Detecta timestamps UNIX en milisegundos
        if ts > 1e12:
            ts /= 1000.0

        # Detecta timestamps UNIX absolutos
        if ts > 1e9:
            return ts

        return ts

    minute = _csv_float(row, "Minute", "Minutes", default=0.0)
    second = _csv_float(row, "Second", "Seconds", default=0.0)

    return minute * 60.0 + second


def _row_edit_event(row: Mapping[str, Any]) -> float:
    """Active de edición/modelado registrada en la fila."""
    keys = (
        "VertexDelta", "NgonDelta", "TriDelta", "NormalDelta",
        "ObjectDelta", "ObjDeltaRadius", "ModifierDelta",
        "CtrlV", "ShiftD", "AltD", "Merge", "UV", "ModeChanged"
    )
    return sum(abs(_csv_float(row, k, default=0.0)) for k in keys)


def _row_object_local_size(row: Mapping[str, Any]) -> float:
    """Devuelve el tamaño local del objeto en unidades del CSV.

    Se aceptan varios nombres habituales de columna. La prioridad es:
    dimensiones locales X/Y/Z, escala local X/Y/Z, tamaño escalar y radio.
    Si solo hay radio, se informa diámetro local.
    """
    dim_x = _csv_float(row, "ObjDimX", "ObjDimensionX", "ObjectDimX", "ObjectDimensionX", "ObjSizeX", "ObjectSizeX", default=0.0)
    dim_y = _csv_float(row, "ObjDimY", "ObjDimensionY", "ObjectDimY", "ObjectDimensionY", "ObjSizeY", "ObjectSizeY", default=0.0)
    dim_z = _csv_float(row, "ObjDimZ", "ObjDimensionZ", "ObjectDimZ", "ObjectDimensionZ", "ObjSizeZ", "ObjectSizeZ", default=0.0)
    dims = [abs(v) for v in (dim_x, dim_y, dim_z) if abs(v) > 0.0]
    if dims:
        return float(max(dims))

    scale_x = _csv_float(row, "ObjScaleX", "ObjectScaleX", "LocalScaleX", "ScaleX", default=0.0)
    scale_y = _csv_float(row, "ObjScaleY", "ObjectScaleY", "LocalScaleY", "ScaleY", default=0.0)
    scale_z = _csv_float(row, "ObjScaleZ", "ObjectScaleZ", "LocalScaleZ", "ScaleZ", default=0.0)
    scales = [abs(v) for v in (scale_x, scale_y, scale_z) if abs(v) > 0.0]
    if scales:
        return float(max(scales))

    size = _csv_float(row, "ObjSize", "ObjectSize", "LocalSize", "BoundingBoxSize", default=0.0)
    if abs(size) > 0.0:
        return abs(size)

    radius = _csv_float(row, "ObjRadius", "ObjectRadius", "SceneRadius", default=0.0)
    return abs(radius) * 2.0 if abs(radius) > 0.0 else 0.0



def compute_metrics_for_csv(data: Sequence[Mapping[str, Any]], BREAK_SPEED: float = DEFAULT_BREAK_SPEED, max_reasonable_speed: float = DEFAULT_MAX_REASONABLE_SPEED) -> dict[str, list[float]]:
    """
    Calcula las métricas del botón 'Calculate CSV Metric Stats' para CSVs con columnas:
    TimeStamp/Minute/Second, UserX/Y/Z, ObjX/Y/Z, ObjRadius, dimensiones/escala local, *Delta, ObjModeState/EditModeState, etc.
    No toca el operador 'Calculate Metrics' de mallas.
    """
    metrics = {mid: [] for mid in ANALYSIS.keys()}
    if not data:
        return metrics

    times_abs = [_row_time(row) for row in data]
    first_time = times_abs[0]
    elapsed = [max(t - first_time, 0.0) for t in times_abs]
    total_time = elapsed[-1] if elapsed else 0.0

    positions = [_vector3((
        _csv_float(row, "UserX", "X"),
        _csv_float(row, "UserY", "Y"),
        _csv_float(row, "UserZ", "Z")
    )) for row in data]
    obj_positions = [_vector3((
        _csv_float(row, "ObjX"),
        _csv_float(row, "ObjY"),
        _csv_float(row, "ObjZ")
    )) for row in data]

    dts = [0.0]
    distances = [0.0]
    speeds = [0.0]
    for i in range(1, len(data)):
        dt = max(times_abs[i] - times_abs[i-1], 0.0)
        dist = (positions[i] - positions[i-1]).length
        dts.append(dt)
        distances.append(dist)
        speed = dist / dt if dt > 0 else 0.0

        # Filtra glitches absurdos
        if speed > float(max_reasonable_speed):
            speed = 0.0

        speeds.append(speed)

    positive_dts = [dt for dt in dts[1:] if dt > 0]
    # A2: parada larga = intervalo temporal por encima de media + 2 desviaciones típicas.
    pause_threshold = float(np.mean(positive_dts) + 2.0 * np.std(positive_dts)) if positive_dts else 0.0

    positive_speeds = [v for v in speeds[1:] if v > 0]
    # A6-A9: peaks espaciales = velocidad por encima de media + 2 desviaciones típicas.
    speed_threshold = float(np.mean(positive_speeds) + 2.0 * np.std(positive_speeds)) if positive_speeds else 0.0

    # A1: serie de tiempo transcurrido en horas; la vista de detalle usa el último valor.
    metrics["A1"] = [t / 3600.0 for t in elapsed]

    # A2: pausas largas sin events de edición; duración de cada pausa, 0 si no es pausa.
    # Si el CSV tiene saltos grandes de tiempo, esto los detecta aunque la posición cambie poco.
    metrics["A2"] = [0.0]
    for i in range(1, len(data)):
        no_edit = _row_edit_event(data[i]) <= 0.0
        is_pause = dts[i] >= pause_threshold and no_edit
        metrics["A2"].append(dts[i] if is_pause else 0.0)

    # A3: pausas por cuartiles temporales. Guardamos la duración de pausa por fila;
    # summarize_metric la parte en cuartiles.
    metrics["A3"] = metrics["A2"][:]

    # Espaciales.
    for i, row in enumerate(data):
        obj_radius = _csv_float(row, "ObjRadius", "SceneRadius", default=0.0)
        dist_to_obj = max((positions[i] - obj_positions[i]).length - obj_radius, 0.0)
        speed_m_per_hour = speeds[i] * 3600.0
        is_speed_peak = 1.0 if speed_threshold > 0 and speeds[i] >= speed_threshold else 0.0
        metrics["A4"].append(speed_m_per_hour)
        metrics["A5"].append(dist_to_obj)
        metrics["A6"].append(is_speed_peak)
        metrics["A7"].append(is_speed_peak)
        metrics["A8"].append(is_speed_peak)
        metrics["A9"].append(is_speed_peak)

        # A10: CtrlV + ShiftD + AltD, conteo de estrategias de aceleración.
        metrics["A10"].append(
            abs(_csv_float(row, "CtrlV", "ControlV", "Ctrl_V", "Ctrl+V"))
            + abs(_csv_float(row, "ShiftD", "Shift_D", "Shift+D"))
            + abs(_csv_float(row, "AltD", "Alt_D", "Alt+D"))
        )
        # A11: modificadores. Es un delta/evento por fila; usamos abs para contar changes.
        metrics["A11"].append(abs(_csv_float(row, "ModifierDelta", "Modifier", "Modifier actionsDelta", "Modifier actions")))
        # A12: evolución de vertices. Es delta/evento por fila.
        metrics["A12"].append(_csv_float(row, "VertexDelta", "VerticesDelta", "VertDelta", "Vertex"))
        # A13: evolución de errors de malla. Son delta/evento por fila; usamos abs para contar changes.
        metrics["A13"].append(
            abs(_csv_float(row, "NgonDelta", "NGonDelta", "NgonsDelta"))
            + abs(_csv_float(row, "TriDelta", "TriangleDelta", "TrianglesDelta"))
            + abs(_csv_float(row, "NormalDelta", "NormalsDelta"))
        )
        # A14: modo de trabajo. Columnas reales: ObjModeState/EditModeState.
        obj_mode = _csv_float(row, "ObjModeState", "ObjMode")
        edit_mode = _csv_float(row, "EditModeState", "EditMode")
        if edit_mode > 0:
            metrics["A14"].append(2.0)
        elif obj_mode > 0:
            metrics["A14"].append(1.0)
        else:
            metrics["A14"].append(0.0)
        # A15: trabajo UV.
        metrics["A15"].append(abs(_csv_float(row, "UV", "UVDelta", "UvDelta", "UVWork", "UVState")))
        # A16: evolución de objetos/mallas.
        metrics["A16"].append(_csv_float(row, "ObjectDelta"))


    return metrics

