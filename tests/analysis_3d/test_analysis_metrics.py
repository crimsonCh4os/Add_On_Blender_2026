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

import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
ADDON_ROOT = PROJECT_ROOT / "Analysis_3D"
if str(ADDON_ROOT) not in sys.path:
    sys.path.append(str(ADDON_ROOT))

from analytics import compute_metrics_for_csv, safe_float, sanitize_name, series_to_array


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
    row.update({k: str(v) for k, v in overrides.items()})
    return row


class TestAnalysisMetrics(unittest.TestCase):
    def test_compute_metrics_accepts_v2_rows_and_calculates_time_and_speed(self):
        rows = [
            _base_v2_row(0, x=0),
            _base_v2_row(1, x=1),
            _base_v2_row(2, x=3),
        ]
        metrics = compute_metrics_for_csv(rows, max_reasonable_speed=10_000.0)

        self.assertAlmostEqual(metrics["A1"][-1], 2 / 3600.0, places=6)

        self.assertEqual(len(metrics["A4"]), 3)
        self.assertAlmostEqual(metrics["A4"][1], 3600.0, places=6)
        self.assertAlmostEqual(metrics["A4"][2], 7200.0, places=6)

    def test_compute_metrics_counts_strategy_columns(self):
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

        self.assertEqual(metrics["A10"][1], 6.0)
        self.assertEqual(metrics["A11"][1], 4.0)
        self.assertEqual(metrics["A14"][1], 2.0)
        self.assertEqual(metrics["A15"][1], 6.0)

        # A17 se eliminó porque duplicaba la información de A16.
        self.assertNotIn("A17", metrics)

    def test_compute_metrics_returns_empty_metric_lists_for_empty_input(self):
        metrics = compute_metrics_for_csv([])

        self.assertIn("A1", metrics)
        self.assertEqual(metrics["A1"], [])

        # A17 ya no debe generarse.
        self.assertNotIn("A17", metrics)

    def test_safe_float_reports_bad_values_and_returns_default(self):
        reports = []
        value = safe_float(
            {"TimeStamp": "bad"},
            "TimeStamp",
            default=7.5,
            report=lambda level, msg: reports.append((level, msg)),
        )
        self.assertEqual(value, 7.5)
        self.assertTrue(reports)

    def test_helpers_sanitize_name_and_filter_non_finite_series(self):
        self.assertEqual(sanitize_name("A/B C"), "A_B_C")
        arr = series_to_array([1, float("nan"), 2, float("inf")])
        self.assertEqual(arr.tolist(), [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()
