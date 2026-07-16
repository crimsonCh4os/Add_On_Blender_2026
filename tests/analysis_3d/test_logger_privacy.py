# Herramientas para la monitorización y análisis de procesos de modelado 3D en Blender
# Copyright (C) 2026 María Molina Goyena
# SPDX-License-Identifier: GPL-3.0-or-later

import csv
import io
import uuid

import pytest

from ._logger_test_utils import load_logger_module


@pytest.fixture(scope="module")
def logger():
    return load_logger_module()


@pytest.fixture
def clean_textblocks(logger):
    logger.bpy.data.texts.clear()
    yield logger
    logger.bpy.data.texts.clear()


def test_get_or_create_user_id_generates_persistent_uuid(clean_textblocks):
    first = clean_textblocks.get_or_create_user_id()
    second = clean_textblocks.get_or_create_user_id()

    assert first == second
    assert str(uuid.UUID(first)) == first
    assert clean_textblocks.USER_ID_TEXTBLOCK in clean_textblocks.bpy.data.texts


def test_reset_user_id_changes_persisted_uuid(clean_textblocks):
    first = clean_textblocks.get_or_create_user_id()
    second = clean_textblocks.reset_user_id()

    assert first != second
    assert str(uuid.UUID(second)) == second
    assert clean_textblocks.get_or_create_user_id() == second


def test_strip_user_id_from_csv_removes_v2_identifier(clean_textblocks):
    content = "SchemaVersion,UserID,TimeStamp\n2,user-1,10\n"

    output = clean_textblocks.strip_user_id_from_csv(content)
    rows = list(csv.DictReader(io.StringIO(output)))

    assert "UserID" not in rows[0]
    assert "user-1" not in output
    assert rows[0]["TimeStamp"] == "10"


def test_strip_user_id_from_csv_removes_v1_identifier(clean_textblocks):
    content = "USER_ID,TimeStamp\nlegacy-user,10\n"

    output = clean_textblocks.strip_user_id_from_csv(content)

    assert "USER_ID" not in output.splitlines()[0]
    assert "legacy-user" not in output


def test_clear_consent_removes_only_consent_textblock(clean_textblocks):
    clean_textblocks.get_or_create_textblock(
        clean_textblocks.CONSENT_TEXTBLOCK
    ).write("ACCEPTED")
    clean_textblocks.get_or_create_textblock(clean_textblocks.DATA_TEXTBLOCK).write(
        "data"
    )

    clean_textblocks.clear_consent()

    assert clean_textblocks.CONSENT_TEXTBLOCK not in clean_textblocks.bpy.data.texts
    assert clean_textblocks.DATA_TEXTBLOCK in clean_textblocks.bpy.data.texts
