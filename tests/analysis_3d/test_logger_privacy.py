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
import uuid
import pathlib
import sys
import unittest

TEST_DIR = pathlib.Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.append(str(TEST_DIR))

from _logger_test_utils import load_logger_module


class TestLoggerPrivacy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.logger = load_logger_module()

    def setUp(self):
        self.logger.bpy.data.texts.clear()

    def test_get_or_create_user_id_generates_persistent_uuid(self):
        first = self.logger.get_or_create_user_id()
        second = self.logger.get_or_create_user_id()

        self.assertEqual(first, second)
        self.assertEqual(str(uuid.UUID(first)), first)
        self.assertIn(self.logger.USER_ID_TEXTBLOCK, self.logger.bpy.data.texts)

    def test_reset_user_id_changes_persisted_uuid(self):
        first = self.logger.get_or_create_user_id()
        second = self.logger.reset_user_id()

        self.assertNotEqual(first, second)
        self.assertEqual(str(uuid.UUID(second)), second)
        self.assertEqual(self.logger.get_or_create_user_id(), second)

    def test_strip_user_id_from_csv_removes_v2_identifier(self):
        content = "SchemaVersion,UserID,TimeStamp\n2,user-1,10\n"
        out = self.logger.strip_user_id_from_csv(content)
        rows = list(csv.DictReader(io.StringIO(out)))

        self.assertNotIn("UserID", rows[0])
        self.assertNotIn("user-1", out)
        self.assertEqual(rows[0]["TimeStamp"], "10")

    def test_strip_user_id_from_csv_removes_v1_identifier(self):
        content = "USER_ID,TimeStamp\nlegacy-user,10\n"
        out = self.logger.strip_user_id_from_csv(content)

        self.assertNotIn("USER_ID", out.splitlines()[0])
        self.assertNotIn("legacy-user", out)

    def test_clear_consent_removes_only_consent_textblock(self):
        self.logger.get_or_create_textblock(self.logger.CONSENT_TEXTBLOCK).write("ACCEPTED")
        self.logger.get_or_create_textblock(self.logger.DATA_TEXTBLOCK).write("data")

        self.logger.clear_consent()

        self.assertNotIn(self.logger.CONSENT_TEXTBLOCK, self.logger.bpy.data.texts)
        self.assertIn(self.logger.DATA_TEXTBLOCK, self.logger.bpy.data.texts)


if __name__ == "__main__":
    unittest.main()
