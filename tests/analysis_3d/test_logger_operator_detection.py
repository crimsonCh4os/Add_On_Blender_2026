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

TEST_DIR = pathlib.Path(__file__).resolve().parent
if str(TEST_DIR) not in sys.path:
    sys.path.append(str(TEST_DIR))

from _logger_test_utils import load_logger_module


class TestLoggerOperatorDetection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.logger = load_logger_module()

    def setUp(self):
        self.logger.operator_flags = {
            "ctrl_v": 0,
            "shift_d": 0,
            "alt_d": 0,
            "merge": 0,
        }
        self.logger._uv_action_pending = 0
        self.logger.DEBUG_LAST_OPERATOR = ""

        # Guardamos el valor original para restaurarlo después de cada test.
        self._original_uv_tracking = self.logger.ENABLE_UV_CHANGE_TRACKING

    def tearDown(self):
        self.logger.ENABLE_UV_CHANGE_TRACKING = self._original_uv_tracking

    def test_normalize_operator_name_matches_blender_style(self):
        self.assertEqual(
            self.logger.normalize_operator_name("OBJECT_OT_duplicate_move"),
            "object.duplicate_move",
        )

    def test_detect_ctrl_v_pastebuffer(self):
        changed = self.logger.detect_flags_from_operator("VIEW3D_OT_pastebuffer")
        self.assertTrue(changed)
        self.assertEqual(self.logger.operator_flags["ctrl_v"], 1)

    def test_detect_shift_d_duplicate(self):
        changed = self.logger.detect_flags_from_operator("OBJECT_OT_duplicate_move")
        self.assertTrue(changed)
        self.assertEqual(self.logger.operator_flags["shift_d"], 1)
        self.assertEqual(self.logger.operator_flags["alt_d"], 0)

    def test_detect_alt_d_linked_duplicate(self):
        changed = self.logger.detect_flags_from_operator("OBJECT_OT_duplicate_move_linked")
        self.assertTrue(changed)
        self.assertEqual(self.logger.operator_flags["alt_d"], 1)
        self.assertEqual(self.logger.operator_flags["shift_d"], 0)

    def test_detect_merge_and_uv(self):
        self.assertTrue(self.logger.detect_flags_from_operator("MESH_OT_merge"))
        self.assertEqual(self.logger.operator_flags["merge"], 1)

        self.logger.ENABLE_UV_CHANGE_TRACKING = True

        self.assertTrue(self.logger.detect_flags_from_operator("UV_OT_unwrap"))
        self.assertEqual(self.logger._uv_action_pending, 1)


if __name__ == "__main__":
    unittest.main()