# Herramientas para la monitorización y análisis de procesos de modelado 3D en Blender
# Copyright (C) 2026 María Molina Goyena
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

import pytest

from ._logger_test_utils import load_logger_module


@pytest.fixture(scope="module")
def logger():
    return load_logger_module()


@pytest.fixture
def logger_csv_path(logger, tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / "logger_test.csv"
    monkeypatch.setattr(logger, "TEMP_CSV_PATH", str(path))
    return path


def test_init_csv_writes_v2_header(logger, logger_csv_path):
    logger.init_csv()

    with logger_csv_path.open("r", encoding="utf-8") as file:
        header = file.readline().strip().split(",")

    assert header == logger.CSV_HEADER


def test_append_csv_preserves_newline_between_rows(logger, logger_csv_path):
    logger.init_csv()
    logger.append_csv("2,1.1.0,session,user")
    logger.append_csv("2,1.1.0,session,user2")

    with logger_csv_path.open("r", encoding="utf-8") as file:
        lines = file.readlines()

    assert len(lines) == 3
    assert all(line.endswith("\n") for line in lines)


def test_remove_duplicate_rows_preserves_header_and_removes_exact_duplicates(
    logger, logger_csv_path
):
    logger_csv_path.write_text("A,B\n1,2\n1,2\n3,4\n", encoding="utf-8")

    logger.remove_duplicate_rows()

    with logger_csv_path.open("r", encoding="utf-8") as file:
        lines = file.readlines()

    assert lines == ["A,B\n", "1,2\n", "3,4\n"]


def test_ensure_file_ends_with_newline_adds_missing_newline(logger, logger_csv_path):
    logger_csv_path.write_text("A,B", encoding="utf-8")

    logger.ensure_file_ends_with_newline(str(logger_csv_path))

    assert logger_csv_path.read_bytes().endswith(b"\n")
