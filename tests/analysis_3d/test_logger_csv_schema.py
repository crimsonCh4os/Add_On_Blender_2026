# Herramientas para la monitorización y análisis de procesos de modelado 3D en Blender
# Copyright (C) 2026 María Molina Goyena
# SPDX-License-Identifier: GPL-3.0-or-later

import csv
import io

import pytest

from ._logger_test_utils import load_logger_module


@pytest.fixture(scope="module")
def logger():
    return load_logger_module()


def test_detect_csv_schema_v1_and_v2(logger):
    assert logger.detect_csv_schema(["USER_ID", "TimeStamp"]) == 1
    assert logger.detect_csv_schema(["SchemaVersion", "UserID", "TimeStamp"]) == 2
    assert logger.detect_csv_schema(["TimeStamp", "UserX"]) == 0


def test_empty_csv_content_upgrades_to_v2_header(logger):
    content = logger.upgrade_csv_content_to_v2("")
    header = content.splitlines()[0].split(",")

    assert header == logger.CSV_HEADER
    assert "SchemaVersion" in header
    assert "LoggerVersion" in header
    assert "SessionID" in header
    assert "UserID" in header


def test_upgrade_v1_content_to_v2_preserves_user_and_time(logger):
    content = (
        "USER_ID,TimeStamp,Minute,Second,UserX,UserY,UserZ\n"
        "old-user,12.5,0,12.5,1,2,3\n"
    )

    upgraded = logger.upgrade_csv_content_to_v2(content)
    rows = list(csv.DictReader(io.StringIO(upgraded)))

    assert len(rows) == 1
    assert rows[0]["SchemaVersion"] == "1"
    assert rows[0]["UserID"] == "old-user"
    assert rows[0]["TimeStamp"] == "12.5"
    assert "USER_ID" not in rows[0]


def test_v2_content_is_preserved_and_normalized_with_newline(logger):
    header = ",".join(logger.CSV_HEADER)
    row = ",".join(
        ["2", "1.1.0", "session", "user"]
        + ["0"] * (len(logger.CSV_HEADER) - 4)
    )

    output = logger.upgrade_csv_content_to_v2(header + "\n" + row)

    assert output.endswith("\n")
    assert output.splitlines()[0] == header
