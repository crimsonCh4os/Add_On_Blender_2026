# Herramientas para la monitorización y análisis de procesos de modelado 3D en Blender
# Copyright (C) 2026 María Molina Goyena
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from ._logger_test_utils import load_logger_module


@pytest.fixture(scope="module")
def logger():
    return load_logger_module()


@pytest.fixture
def clean_logger_state(logger, monkeypatch):
    monkeypatch.setattr(
        logger,
        "operator_flags",
        {"ctrl_v": 0, "shift_d": 0, "alt_d": 0, "merge": 0},
        raising=False,
    )
    monkeypatch.setattr(logger, "_uv_action_pending", 0, raising=False)
    monkeypatch.setattr(logger, "DEBUG_LAST_OPERATOR", "", raising=False)
    monkeypatch.setattr(logger, "ENABLE_UV_CHANGE_TRACKING", False, raising=False)
    return logger


def test_normalize_operator_name_matches_blender_style(clean_logger_state):
    assert (
        clean_logger_state.normalize_operator_name("OBJECT_OT_duplicate_move")
        == "object.duplicate_move"
    )


def test_detect_ctrl_v_pastebuffer(clean_logger_state):
    changed = clean_logger_state.detect_flags_from_operator("VIEW3D_OT_pastebuffer")

    assert changed is True
    assert clean_logger_state.operator_flags["ctrl_v"] == 1


def test_detect_shift_d_duplicate(clean_logger_state):
    changed = clean_logger_state.detect_flags_from_operator("OBJECT_OT_duplicate_move")

    assert changed is True
    assert clean_logger_state.operator_flags["shift_d"] == 1
    assert clean_logger_state.operator_flags["alt_d"] == 0


def test_detect_alt_d_linked_duplicate(clean_logger_state):
    changed = clean_logger_state.detect_flags_from_operator(
        "OBJECT_OT_duplicate_move_linked"
    )

    assert changed is True
    assert clean_logger_state.operator_flags["alt_d"] == 1
    assert clean_logger_state.operator_flags["shift_d"] == 0


def test_detect_merge_sets_merge_flag(clean_logger_state):
    changed = clean_logger_state.detect_flags_from_operator("MESH_OT_merge")

    assert changed is True
    assert clean_logger_state.operator_flags["merge"] == 1


def test_detect_uv_marks_pending_without_forcing_log(clean_logger_state):
    clean_logger_state.ENABLE_UV_CHANGE_TRACKING = True

    changed = clean_logger_state.detect_flags_from_operator("UV_OT_unwrap")

    # En Data_Logger_3D.py el valor de retorno solo indica cambios no UV que
    # deben forzar una fila inmediata. Las operaciones UV se registran como
    # actividad pendiente y se validan después mediante el hash de topología.
    assert changed is False
    assert clean_logger_state._uv_action_pending == 1
    assert clean_logger_state._uv_transform_pending is False
    assert clean_logger_state.operator_flags == {
        "ctrl_v": 0,
        "shift_d": 0,
        "alt_d": 0,
        "merge": 0,
    }
