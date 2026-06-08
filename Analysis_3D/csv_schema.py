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

"""Compatibilidad y validación de CSV para Data Logger 3D.

Acepta CSV v1 (cabecera antigua con USER_ID) y CSV v2 (SchemaVersion,
LoggerVersion, SessionID, UserID). La salida normalizada usa nombres v2.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

SCHEMA_VERSION_V1 = 1
SCHEMA_VERSION_V2 = 2

CSV_REQUIRED_COMMON = [
    "TimeStamp", "Minute", "Second",
    "UserX", "UserY", "UserZ",
    "SceneRadius",
    "ObjX", "ObjY", "ObjZ", "ObjRadius",
    "ObjDeltaX", "ObjDeltaY", "ObjDeltaZ", "ObjDeltaRadius",
    "VertexDelta", "NgonDelta", "TriDelta", "NormalDelta",
    "ObjModeState", "EditModeState", "ModeChanged", "UV",
    "ObjectDelta", "ModifierDelta",
    "CtrlV", "ShiftD", "AltD", "Merge", "Occlusion",
]

CSV_HEADER_V2 = [
    "SchemaVersion", "LoggerVersion", "SessionID", "UserID",
    *CSV_REQUIRED_COMMON,
]

NUMERIC_COLUMNS = set(CSV_REQUIRED_COMMON)


def _norm(name: Any) -> str:
    return str(name).strip().lstrip("\ufeff")


def detect_schema_version(fieldnames: Iterable[str] | None) -> int:
    names = {_norm(name) for name in (fieldnames or [])}
    if "SchemaVersion" in names:
        return SCHEMA_VERSION_V2
    if "USER_ID" in names:
        return SCHEMA_VERSION_V1
    raise ValueError("CSV no reconocido: falta SchemaVersion o USER_ID")


def validate_header(fieldnames: Iterable[str] | None) -> dict[str, list[str] | int]:
    names = [_norm(name) for name in (fieldnames or [])]
    version = detect_schema_version(names)
    required = list(CSV_REQUIRED_COMMON)
    if version == SCHEMA_VERSION_V1:
        required = ["USER_ID", *required]
    else:
        required = ["SchemaVersion", "LoggerVersion", "SessionID", "UserID", *required]

    missing = [name for name in required if name not in names]
    extra = [name for name in names if name not in required]
    return {"schema_version": version, "missing": missing, "extra": extra}


def normalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized_keys = {_norm(k): v for k, v in row.items()}
    fieldnames = list(normalized_keys.keys())
    version = detect_schema_version(fieldnames)

    if version == SCHEMA_VERSION_V2:
        result = {name: normalized_keys.get(name, "") for name in CSV_HEADER_V2}
        result["SchemaVersion"] = str(result.get("SchemaVersion") or "2")
        return result

    result = {name: normalized_keys.get(name, "") for name in CSV_REQUIRED_COMMON}
    result["SchemaVersion"] = "1"
    result["LoggerVersion"] = ""
    result["SessionID"] = ""
    result["UserID"] = normalized_keys.get("USER_ID", "")
    return {name: result.get(name, "") for name in CSV_HEADER_V2}


def normalize_csv_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_row(row) for row in rows]


def coerce_numeric_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Convierte columnas numéricas cuando sea posible; conserva metadatos como texto."""
    out = dict(row)
    for key in NUMERIC_COLUMNS:
        value = out.get(key, "")
        if value in (None, ""):
            out[key] = 0.0
            continue
        try:
            out[key] = float(str(value).strip().replace(",", "."))
        except (TypeError, ValueError):
            out[key] = 0.0
    return out
