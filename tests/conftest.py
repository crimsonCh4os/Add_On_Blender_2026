"""Preparación común de pytest para la estructura del TFG."""
from __future__ import annotations

from pathlib import Path
import pytest

from tests._project_loader import PROJECT_ROOT, prepare_project_paths

# Se ejecuta antes de importar los módulos de prueba.
prepare_project_paths()


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT
