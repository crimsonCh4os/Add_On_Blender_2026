import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "Analysis_3D" / "csv_schema.py"
spec = importlib.util.spec_from_file_location("analysis_csv_schema", MODULE_PATH)
csv_schema = importlib.util.module_from_spec(spec)
spec.loader.exec_module(csv_schema)


class TestCSVSchema(unittest.TestCase):
    def test_detect_v1(self):
        self.assertEqual(csv_schema.detect_schema_version(["USER_ID", "TimeStamp"]), 1)

    def test_detect_v2(self):
        self.assertEqual(csv_schema.detect_schema_version(["SchemaVersion", "UserID", "TimeStamp"]), 2)

    def test_validate_missing_required(self):
        result = csv_schema.validate_header(["SchemaVersion", "LoggerVersion", "SessionID", "UserID"])
        self.assertIn("TimeStamp", result["missing"])

    def test_validate_extra_columns(self):
        header = [*csv_schema.CSV_HEADER_V2, "ExtraColumn"]
        result = csv_schema.validate_header(header)
        self.assertIn("ExtraColumn", result["extra"])

    def test_normalize_v1_to_v2(self):
        row = {"USER_ID": "old", "TimeStamp": "1", "Minute": "0", "Second": "1"}
        out = csv_schema.normalize_row(row)
        self.assertEqual(out["SchemaVersion"], "1")
        self.assertEqual(out["UserID"], "old")
        self.assertIn("SessionID", out)

    def test_normalize_v2_keeps_user_id(self):
        row = {"SchemaVersion": "2", "LoggerVersion": "1.1.0", "SessionID": "s", "UserID": "u", "TimeStamp": "1"}
        out = csv_schema.normalize_row(row)
        self.assertEqual(out["SchemaVersion"], "2")
        self.assertEqual(out["UserID"], "u")

    def test_coerce_numeric_bad_value(self):
        out = csv_schema.coerce_numeric_row({"TimeStamp": "bad"})
        self.assertEqual(out["TimeStamp"], 0.0)

    def test_unknown_schema_raises(self):
        with self.assertRaises(ValueError):
            csv_schema.detect_schema_version(["TimeStamp"])


if __name__ == "__main__":
    unittest.main()
