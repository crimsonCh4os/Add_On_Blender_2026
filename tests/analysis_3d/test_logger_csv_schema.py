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

import csv
import io
import pathlib
import sys
import unittest

TEST_DIR = pathlib.Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.append(str(TEST_DIR))

from _logger_test_utils import load_logger_module


class TestLoggerCSVSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.logger = load_logger_module()

    def test_detect_csv_schema_v1_and_v2(self):
        self.assertEqual(self.logger.detect_csv_schema(["USER_ID", "TimeStamp"]), 1)
        self.assertEqual(self.logger.detect_csv_schema(["SchemaVersion", "UserID", "TimeStamp"]), 2)
        self.assertEqual(self.logger.detect_csv_schema(["TimeStamp", "UserX"]), 0)

    def test_empty_csv_content_upgrades_to_v2_header(self):
        content = self.logger.upgrade_csv_content_to_v2("")
        header = content.splitlines()[0].split(",")
        self.assertEqual(header, self.logger.CSV_HEADER)
        self.assertIn("SchemaVersion", header)
        self.assertIn("LoggerVersion", header)
        self.assertIn("SessionID", header)
        self.assertIn("UserID", header)

    def test_upgrade_v1_content_to_v2_preserves_user_and_time(self):
        content = "USER_ID,TimeStamp,Minute,Second,UserX,UserY,UserZ\nold-user,12.5,0,12.5,1,2,3\n"
        upgraded = self.logger.upgrade_csv_content_to_v2(content)
        rows = list(csv.DictReader(io.StringIO(upgraded)))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["SchemaVersion"], "1")
        self.assertEqual(rows[0]["UserID"], "old-user")
        self.assertEqual(rows[0]["TimeStamp"], "12.5")
        self.assertNotIn("USER_ID", rows[0])

    def test_v2_content_is_preserved_and_normalized_with_newline(self):
        header = ",".join(self.logger.CSV_HEADER)
        row = ",".join(["2", "1.1.0", "session", "user"] + ["0"] * (len(self.logger.CSV_HEADER) - 4))
        out = self.logger.upgrade_csv_content_to_v2(header + "\n" + row)
        self.assertTrue(out.endswith("\n"))
        self.assertEqual(out.splitlines()[0], header)


if __name__ == "__main__":
    unittest.main()
