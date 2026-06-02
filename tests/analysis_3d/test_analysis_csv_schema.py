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

import csv_schema


class TestAnalysisCSVSchema(unittest.TestCase):
    def test_full_v2_header_has_no_missing_columns(self):
        result = csv_schema.validate_header(csv_schema.CSV_HEADER_V2)
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["missing"], [])

    def test_normalize_csv_rows_accepts_mixed_legacy_rows(self):
        rows = [
            {"USER_ID": "old", "TimeStamp": "1"},
            {"SchemaVersion": "2", "LoggerVersion": "1.1.0", "SessionID": "s", "UserID": "new", "TimeStamp": "2"},
        ]
        out = csv_schema.normalize_csv_rows(rows)

        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["SchemaVersion"], "1")
        self.assertEqual(out[0]["UserID"], "old")
        self.assertEqual(out[1]["SchemaVersion"], "2")
        self.assertEqual(out[1]["SessionID"], "s")

    def test_coerce_numeric_row_accepts_decimal_comma(self):
        out = csv_schema.coerce_numeric_row({"TimeStamp": "1,25", "VertexDelta": "3"})
        self.assertEqual(out["TimeStamp"], 1.25)
        self.assertEqual(out["VertexDelta"], 3.0)

    def test_coerce_numeric_row_keeps_metadata_as_text(self):
        out = csv_schema.coerce_numeric_row({"UserID": "abc", "SessionID": "session", "TimeStamp": "1"})
        self.assertEqual(out["UserID"], "abc")
        self.assertEqual(out["SessionID"], "session")
        self.assertEqual(out["TimeStamp"], 1.0)


if __name__ == "__main__":
    unittest.main()
