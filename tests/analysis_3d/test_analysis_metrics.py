# Herramientas para la monitorización y análisis de procesos de modelado 3D en Blender
# Copyright (C) 2026 María Molina Goyena
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

pytest.importorskip("numpy", reason="Los tests analíticos necesitan NumPy.")

from tests._project_loader import load_project_module

analytics = load_project_module(
    "analytics",
    "analytics.py",
    preferred_roots=("Analysis_3D", "Analysis3D"),
)
compute_metrics_for_csv = analytics.compute_metrics_for_csv
safe_float = analytics.safe_float
sanitize_name = analytics.sanitize_name
series_to_array = analytics.series_to_array


def _base_v2_row(timestamp, x=0, y=0, z=0, **overrides):
    row = {
        "SchemaVersion": "2",
        "LoggerVersion": "1.1.0",
        "SessionID": "session-1",
        "UserID": "user-1",
        "TimeStamp": str(timestamp),
        "Minute": "0",
        "Second": str(timestamp),
        "UserX": str(x),
        "UserY": str(y),
        "UserZ": str(z),
        "SceneRadius": "0",
        "ObjX": "0",
        "ObjY": "0",
        "ObjZ": "0",
        "ObjRadius": "0",
        "ObjDeltaX": "0",
        "ObjDeltaY": "0",
        "ObjDeltaZ": "0",
        "ObjDeltaRadius": "0",
        "VertexDelta": "0",
        "NgonDelta": "0",
        "TriDelta": "0",
        "NormalDelta": "0",
        "ObjModeState": "1",
        "EditModeState": "0",
        "ModeChanged": "0",
        "UV": "0",
        "ObjectDelta": "0",
        "ModifierDelta": "0",
        "CtrlV": "0",
        "ShiftD": "0",
        "AltD": "0",
        "Merge": "0",
        "Occlusion": "0",
    }
    row.update({key: str(value) for key, value in overrides.items()})
    return row


def test_compute_metrics_accepts_v2_rows_and_calculates_time_and_speed():
    rows = [
        _base_v2_row(0, x=0),
        _base_v2_row(1, x=1),
        _base_v2_row(2, x=3),
    ]

    metrics = compute_metrics_for_csv(rows, max_reasonable_speed=10_000.0)

    assert metrics["A1"][-1] == pytest.approx(2 / 3600.0, abs=1e-6)
    assert len(metrics["A4"]) == 3
    assert metrics["A4"][1] == pytest.approx(3600.0, abs=1e-6)
    assert metrics["A4"][2] == pytest.approx(7200.0, abs=1e-6)


def test_compute_metrics_counts_strategy_columns():
    rows = [
        _base_v2_row(0),
        _base_v2_row(
            1,
            CtrlV=1,
            ShiftD=2,
            AltD=3,
            ModifierDelta=4,
            ObjectDelta=5,
            UV=6,
            EditModeState=1,
            ObjModeState=0,
        ),
    ]

    metrics = compute_metrics_for_csv(rows)

    assert metrics["A10"][1] == 6.0
    assert metrics["A11"][1] == 4.0
    assert metrics["A14"][1] == 2.0
    assert metrics["A15"][1] == 6.0
    assert "A17" not in metrics


def test_compute_metrics_returns_empty_metric_lists_for_empty_input():
    metrics = compute_metrics_for_csv([])

    assert "A1" in metrics
    assert metrics["A1"] == []
    assert "A17" not in metrics


def test_safe_float_reports_bad_values_and_returns_default():
    reports = []

    value = safe_float(
        {"TimeStamp": "bad"},
        "TimeStamp",
        default=7.5,
        report=lambda level, message: reports.append((level, message)),
    )

    assert value == 7.5
    assert reports


def test_helpers_sanitize_name_and_filter_non_finite_series():
    assert sanitize_name("A/B C") == "A_B_C"
    array = series_to_array([1, float("nan"), 2, float("inf")])
    assert array.tolist() == [1.0, 2.0]
