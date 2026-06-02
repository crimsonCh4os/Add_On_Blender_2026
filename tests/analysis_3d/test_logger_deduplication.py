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
import tempfile
import pathlib
import sys
import unittest

TEST_DIR = pathlib.Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.append(str(TEST_DIR))

from _logger_test_utils import load_logger_module


class TestLoggerDeduplicationAndFileIO(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.logger = load_logger_module()

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.original_path = self.logger.TEMP_CSV_PATH
        self.logger.TEMP_CSV_PATH = os.path.join(self.tmpdir.name, "logger_test.csv")

    def tearDown(self):
        self.logger.TEMP_CSV_PATH = self.original_path
        self.tmpdir.cleanup()

    def test_init_csv_writes_v2_header(self):
        self.logger.init_csv()
        with open(self.logger.TEMP_CSV_PATH, "r", encoding="utf-8") as fh:
            header = fh.readline().strip().split(",")
        self.assertEqual(header, self.logger.CSV_HEADER)

    def test_append_csv_preserves_newline_between_rows(self):
        self.logger.init_csv()
        self.logger.append_csv("2,1.1.0,session,user")
        self.logger.append_csv("2,1.1.0,session,user2")

        with open(self.logger.TEMP_CSV_PATH, "r", encoding="utf-8") as fh:
            lines = fh.readlines()

        self.assertEqual(len(lines), 3)
        self.assertTrue(all(line.endswith("\n") for line in lines))

    def test_remove_duplicate_rows_preserves_header_and_removes_exact_duplicates(self):
        with open(self.logger.TEMP_CSV_PATH, "w", encoding="utf-8") as fh:
            fh.write("A,B\n")
            fh.write("1,2\n")
            fh.write("1,2\n")
            fh.write("3,4\n")

        self.logger.remove_duplicate_rows()

        with open(self.logger.TEMP_CSV_PATH, "r", encoding="utf-8") as fh:
            lines = fh.readlines()

        self.assertEqual(lines, ["A,B\n", "1,2\n", "3,4\n"])

    def test_ensure_file_ends_with_newline_adds_missing_newline(self):
        with open(self.logger.TEMP_CSV_PATH, "w", encoding="utf-8") as fh:
            fh.write("A,B")

        self.logger.ensure_file_ends_with_newline(self.logger.TEMP_CSV_PATH)

        with open(self.logger.TEMP_CSV_PATH, "rb") as fh:
            self.assertTrue(fh.read().endswith(b"\n"))


if __name__ == "__main__":
    unittest.main()
