
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

"""Unit tests for decoupled geometric logic.
Run with unittest outside Blender for the decoupled parts, or inside Blender for geometry tests.
"""
import math
import pathlib
import sys
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
ADDON_ROOT = PROJECT_ROOT / "Analysis_3D"
if str(ADDON_ROOT) not in sys.path:
    sys.path.append(str(ADDON_ROOT))

try:
    from mathutils import Vector
    from utils import calculate_hausdorff_distance_from_coords, calculate_similarity_from_coords
except Exception as exc:  
    Vector = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


@unittest.skipIf(IMPORT_ERROR is not None, f"Blender mathutils unavailable: {IMPORT_ERROR}")
class TestGeometryLogic(unittest.TestCase):
    def test_identical_triangle_similarity_is_100(self):
        coords = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((0, 1, 0))]
        self.assertEqual(calculate_hausdorff_distance_from_coords(coords, coords), 0.0)
        self.assertEqual(calculate_similarity_from_coords(coords, coords), 100.0)

    def test_single_offset_segment_hausdorff(self):
        a = [Vector((0, 0, 0)), Vector((1, 0, 0))]
        b = [Vector((0, 1, 0)), Vector((1, 1, 0))]
        self.assertAlmostEqual(calculate_hausdorff_distance_from_coords(a, b), 1.0, places=5)

    def test_empty_geometry_similarity_is_zero(self):
        coords = [Vector((0, 0, 0)), Vector((1, 0, 0))]
        self.assertEqual(calculate_similarity_from_coords([], coords), 0.0)


class TestCSVAnalytics(unittest.TestCase):
    def test_compute_metrics_for_csv_isolated_temporal_pause_and_speed(self):
        try:
            from analytics import compute_metrics_for_csv
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"analytics unavailable: {exc}")

        rows = []
        for t in list(range(10)) + [109]:
            rows.append({
                "USER_ID": "test",
                "TimeStamp": str(t),
                "UserX": str(t),
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
            })

        metrics = compute_metrics_for_csv(rows, max_reasonable_speed=10_000.0)

        self.assertAlmostEqual(metrics["A1"][-1], 109 / 3600.0, places=6)
        self.assertEqual(metrics["A2"][-1], 100.0)
        self.assertEqual(metrics["A3"], metrics["A2"])
        self.assertEqual(len(metrics["A4"]), len(rows))
        self.assertAlmostEqual(metrics["A4"][1], 3600.0, places=6)


    def test_clamp_outliers_uses_simple_iqr_without_dropping_samples(self):
        try:
            from analytics import clamp_outliers
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"analytics unavailable: {exc}")

        values = [10, 11, 12, 13, 1000]
        clamped = clamp_outliers(values)

        self.assertEqual(len(clamped), len(values))
        self.assertLess(clamped[-1], 1000)
        self.assertEqual(clamped[0], 10)

    def test_compute_metrics_for_csv_isolated_strategy_counts(self):
        try:
            from analytics import compute_metrics_for_csv
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"analytics unavailable: {exc}")

        rows = [
            {"USER_ID": "test", "TimeStamp": "0", "UserX": "0", "UserY": "0", "UserZ": "0", "ObjX": "0", "ObjY": "0", "ObjZ": "0"},
            {
                "USER_ID": "test",
                "TimeStamp": "1", "UserX": "0", "UserY": "0", "UserZ": "0",
                "ObjX": "0", "ObjY": "0", "ObjZ": "0",
                "CtrlV": "1", "ShiftD": "2", "AltD": "3",
                "ModifierDelta": "4", "ObjectDelta": "5", "UV": "6",
                "ObjModeState": "0", "EditModeState": "1",
            },
        ]

        metrics = compute_metrics_for_csv(rows)
        self.assertEqual(metrics["A10"][1], 6.0)
        self.assertEqual(metrics["A11"][1], 4.0)
        self.assertEqual(metrics["A14"][1], 2.0)
        self.assertEqual(metrics["A15"][1], 6.0)
        self.assertEqual(metrics["A17"][1], 5.0)


if __name__ == "__main__":
    unittest.main()
