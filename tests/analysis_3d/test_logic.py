# Herramientas para la monitorización y análisis de procesos de modelado 3D en Blender
# Copyright (C) 2026 María Molina Goyena
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

pytest.importorskip("numpy", reason="Los tests analíticos necesitan NumPy.")

from tests._project_loader import (
    install_minimal_blender_stubs,
    load_project_module,
)

install_minimal_blender_stubs()

mathutils = __import__("mathutils")
Vector = mathutils.Vector
utils = load_project_module(
    "utils",
    "utils.py",
    preferred_roots=("Analysis_3D", "Analysis3D"),
)
analytics = load_project_module(
    "analytics",
    "analytics.py",
    preferred_roots=("Analysis_3D", "Analysis3D"),
)

calculate_hausdorff_distance_from_coords = utils.calculate_hausdorff_distance_from_coords
calculate_similarity_from_coords = utils.calculate_similarity_from_coords
compute_metrics_for_csv = analytics.compute_metrics_for_csv
clamp_outliers = analytics.clamp_outliers


def test_identical_triangle_similarity():
    coordinates = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((0, 1, 0))]
    assert calculate_hausdorff_distance_from_coords(coordinates, coordinates) == 0.0
    # La implementación actual reserva 100 para el mismo objeto de Blender.
    # Dos listas independientes pero idénticas pueden devolver 99.99.
    assert calculate_similarity_from_coords(coordinates, coordinates) in (99.99, 100.0)


def test_single_offset_segment_hausdorff():
    first = [Vector((0, 0, 0)), Vector((1, 0, 0))]
    second = [Vector((0, 1, 0)), Vector((1, 1, 0))]
    assert calculate_hausdorff_distance_from_coords(first, second) == pytest.approx(
        1.0, abs=1e-5
    )


def test_empty_geometry_similarity_is_zero():
    coordinates = [Vector((0, 0, 0)), Vector((1, 0, 0))]
    assert calculate_similarity_from_coords([], coordinates) == 0.0


def test_compute_metrics_for_csv_isolated_temporal_pause_and_speed():
    rows = []
    for timestamp in [*range(10), 109]:
        rows.append(
            {
                "USER_ID": "test",
                "TimeStamp": str(timestamp),
                "UserX": str(timestamp),
                "UserY": "0",
                "UserZ": "0",
                "ObjX": "0",
                "ObjY": "0",
                "ObjZ": "0",
                "ObjRadius": "0",
                "ObjectDelta": "0",
                "VertexDelta": "0",
                "NgonDelta": "0",
                "TriDelta": "0",
                "NormalDelta": "0",
                "ModifierDelta": "0",
                "CtrlV": "0",
                "ShiftD": "0",
                "AltD": "0",
            }
        )

    metrics = compute_metrics_for_csv(rows, max_reasonable_speed=10_000.0)
    assert metrics["A1"][-1] == pytest.approx(109 / 3600.0, abs=1e-6)
    assert metrics["A2"][-1] == 100.0
    assert metrics["A3"] == metrics["A2"]
    assert len(metrics["A4"]) == len(rows)
    assert metrics["A4"][1] == pytest.approx(3600.0, abs=1e-6)


def test_clamp_outliers_uses_simple_iqr_without_dropping_samples():
    values = [10, 11, 12, 13, 1000]
    clamped = clamp_outliers(values)
    assert len(clamped) == len(values)
    assert clamped[-1] < 1000
    assert clamped[0] == 10


def test_compute_metrics_for_csv_isolated_strategy_counts():
    rows = [
        {
            "TimeStamp": "0",
            "UserX": "0",
            "UserY": "0",
            "UserZ": "0",
            "ObjX": "0",
            "ObjY": "0",
            "ObjZ": "0",
        },
        {
            "TimeStamp": "1",
            "UserX": "0",
            "UserY": "0",
            "UserZ": "0",
            "ObjX": "0",
            "ObjY": "0",
            "ObjZ": "0",
            "CtrlV": "1",
            "ShiftD": "2",
            "AltD": "3",
            "ModifierDelta": "4",
            "ObjectDelta": "5",
            "UV": "6",
            "ObjModeState": "0",
            "EditModeState": "1",
        },
    ]
    metrics = compute_metrics_for_csv(rows)
    assert metrics["A10"][1] == 6.0
    assert metrics["A11"][1] == 4.0
    assert metrics["A14"][1] == 2.0
    assert metrics["A15"][1] == 6.0
    assert metrics["A16"][1] == 5.0
    assert "A17" not in metrics
