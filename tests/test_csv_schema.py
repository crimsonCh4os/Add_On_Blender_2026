import pytest

from tests._project_loader import load_project_module

csv_schema = load_project_module(
    "csv_schema",
    "csv_schema.py",
    preferred_roots=("Analysis_3D", "Analysis3D"),
)


def test_detect_v1():
    assert csv_schema.detect_schema_version(["USER_ID", "TimeStamp"]) == 1


def test_detect_v2():
    assert csv_schema.detect_schema_version(["SchemaVersion", "UserID", "TimeStamp"]) == 2


def test_validate_missing_required():
    result = csv_schema.validate_header(
        ["SchemaVersion", "LoggerVersion", "SessionID", "UserID"]
    )
    assert "TimeStamp" in result["missing"]


def test_validate_extra_columns():
    header = [*csv_schema.CSV_HEADER_V2, "ExtraColumn"]
    result = csv_schema.validate_header(header)
    assert "ExtraColumn" in result["extra"]


def test_normalize_v1_to_v2():
    row = {"USER_ID": "old", "TimeStamp": "1", "Minute": "0", "Second": "1"}
    output = csv_schema.normalize_row(row)
    assert output["SchemaVersion"] == "1"
    assert output["UserID"] == "old"
    assert "SessionID" in output


def test_normalize_v2_keeps_user_id():
    row = {
        "SchemaVersion": "2",
        "LoggerVersion": "1.1.0",
        "SessionID": "s",
        "UserID": "u",
        "TimeStamp": "1",
    }
    output = csv_schema.normalize_row(row)
    assert output["SchemaVersion"] == "2"
    assert output["UserID"] == "u"


def test_coerce_numeric_bad_value():
    output = csv_schema.coerce_numeric_row({"TimeStamp": "bad"})
    assert output["TimeStamp"] == 0.0


def test_unknown_schema_raises():
    with pytest.raises(ValueError):
        csv_schema.detect_schema_version(["TimeStamp"])
