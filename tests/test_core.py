from tests._project_loader import load_project_module

core_module = load_project_module(
    "data_logger_core",
    "data_logger_core.py",
    preferred_roots=("core",),
)

OperatorDetectionState = core_module.OperatorDetectionState
detect_flags_from_operator_name = core_module.detect_flags_from_operator_name
normalize_operator_name = core_module.normalize_operator_name
trunc_2 = core_module.trunc_2
trunc_all = core_module.trunc_all


def test_trunc_2_float():
    assert trunc_2(1.239) == 1.23


def test_trunc_2_bool():
    assert trunc_2(True) == 1


def test_trunc_all():
    assert trunc_all([1.239, False, "x"]) == [1.23, 0, "x"]


def test_normalize_operator_name():
    assert normalize_operator_name("MESH_OT_merge") == "mesh.merge"


def test_detect_ctrl_v():
    state, changed = detect_flags_from_operator_name("VIEW3D_OT_pastebuffer")
    assert changed is True
    assert state.flags["ctrl_v"] == 1


def test_detect_shift_d():
    state, changed = detect_flags_from_operator_name("OBJECT_OT_duplicate_move")
    assert changed is True
    assert state.flags["shift_d"] == 1


def test_detect_alt_d():
    state, changed = detect_flags_from_operator_name("OBJECT_OT_duplicate_move_linked")
    assert changed is True
    assert state.flags["alt_d"] == 1


def test_detect_merge():
    state, changed = detect_flags_from_operator_name("MESH_OT_merge")
    assert changed is True
    assert state.flags["merge"] == 1


def test_detect_uv_pending():
    state, changed = detect_flags_from_operator_name("UV_OT_unwrap")
    assert changed is True
    assert state.uv_action_pending == 1


def test_repeated_operator_not_changed_twice():
    state = OperatorDetectionState()
    state, first_changed = detect_flags_from_operator_name("MESH_OT_merge", state)
    state, second_changed = detect_flags_from_operator_name("MESH_OT_merge", state)
    assert first_changed is True
    assert second_changed is False
