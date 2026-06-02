import unittest
from core.data_logger_core import trunc_2, trunc_all, normalize_operator_name, detect_flags_from_operator_name, OperatorDetectionState


class TestCore(unittest.TestCase):
    def test_trunc_2_float(self):
        self.assertEqual(trunc_2(1.239), 1.23)

    def test_trunc_2_bool(self):
        self.assertEqual(trunc_2(True), 1)

    def test_trunc_all(self):
        self.assertEqual(trunc_all([1.239, False, "x"]), [1.23, 0, "x"])

    def test_normalize_operator_name(self):
        self.assertEqual(normalize_operator_name("MESH_OT_merge"), "mesh.merge")

    def test_detect_ctrl_v(self):
        state, changed = detect_flags_from_operator_name("VIEW3D_OT_pastebuffer")
        self.assertTrue(changed)
        self.assertEqual(state.flags["ctrl_v"], 1)

    def test_detect_shift_d(self):
        state, changed = detect_flags_from_operator_name("OBJECT_OT_duplicate_move")
        self.assertTrue(changed)
        self.assertEqual(state.flags["shift_d"], 1)

    def test_detect_alt_d(self):
        state, changed = detect_flags_from_operator_name("OBJECT_OT_duplicate_move_linked")
        self.assertTrue(changed)
        self.assertEqual(state.flags["alt_d"], 1)

    def test_detect_merge(self):
        state, changed = detect_flags_from_operator_name("MESH_OT_merge")
        self.assertTrue(changed)
        self.assertEqual(state.flags["merge"], 1)

    def test_detect_uv_pending(self):
        state, changed = detect_flags_from_operator_name("UV_OT_unwrap")
        self.assertTrue(changed)
        self.assertEqual(state.uv_action_pending, 1)

    def test_repeated_operator_not_changed_twice(self):
        state = OperatorDetectionState()
        state, changed1 = detect_flags_from_operator_name("MESH_OT_merge", state)
        state, changed2 = detect_flags_from_operator_name("MESH_OT_merge", state)
        self.assertTrue(changed1)
        self.assertFalse(changed2)


if __name__ == "__main__":
    unittest.main()
