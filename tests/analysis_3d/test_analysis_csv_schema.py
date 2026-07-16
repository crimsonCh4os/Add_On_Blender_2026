# Herramientas para la monitorización y análisis de procesos de modelado 3D en Blender
# Copyright (C) 2026 María Molina Goyena
# SPDX-License-Identifier: GPL-3.0-or-later

from tests._project_loader import load_project_module

csv_schema = load_project_module(
    "csv_schema",
    "csv_schema.py",
    preferred_roots=("Analysis_3D", "Analysis3D"),
)


def test_full_v2_header_has_no_missing_columns():
    result = csv_schema.validate_header(csv_schema.CSV_HEADER_V2)
    assert result["schema_version"] == 2
    assert result["missing"] == []


def test_normalize_csv_rows_accepts_mixed_legacy_rows():
    rows = [
        {"USER_ID": "old", "TimeStamp": "1"},
        {
            "SchemaVersion": "2",
            "LoggerVersion": "1.1.0",
            "SessionID": "s",
            "UserID": "new",
            "TimeStamp": "2",
        },
    ]
    output = csv_schema.normalize_csv_rows(rows)
    assert len(output) == 2
    assert output[0]["SchemaVersion"] == "1"
    assert output[0]["UserID"] == "old"
    assert output[1]["SchemaVersion"] == "2"
    assert output[1]["SessionID"] == "s"


def test_coerce_numeric_row_accepts_decimal_comma():
    output = csv_schema.coerce_numeric_row({"TimeStamp": "1,25", "VertexDelta": "3"})
    assert output["TimeStamp"] == 1.25
    assert output["VertexDelta"] == 3.0


def test_coerce_numeric_row_keeps_metadata_as_text():
    output = csv_schema.coerce_numeric_row(
        {"UserID": "abc", "SessionID": "session", "TimeStamp": "1"}
    )
    assert output["UserID"] == "abc"
    assert output["SessionID"] == "session"
    assert output["TimeStamp"] == 1.0
