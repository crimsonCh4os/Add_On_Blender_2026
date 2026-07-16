"""Carga módulos del proyecto sin depender de PYTHONPATH.

La estructura esperada es, como mínimo::

    proyecto/
    ├── Analysis_3D/
    ├── core/
    ├── Data_Loggers/
    └── tests/

También admite que los archivos Python estén dentro de una subcarpeta adicional,
por ejemplo ``Analysis_3D/Analysis3D/analytics.py``.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import types
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_IGNORED_PARTS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "venv",
    "__pycache__",
    "site-packages",
    "build",
    "dist",
    "tests",
}


def _is_allowed(path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(PROJECT_ROOT.resolve())
    except (OSError, ValueError):
        return False
    return not any(part in _IGNORED_PARTS for part in relative.parts[:-1])


def _candidate_roots(preferred_roots: Iterable[str] = ()) -> list[Path]:
    roots: list[Path] = []

    env_root = os.environ.get("ANALYSIS3D_PROJECT_ROOT")
    if env_root:
        roots.append(Path(env_root).expanduser())

    for name in preferred_roots:
        roots.append(PROJECT_ROOT / name)

    roots.extend(
        [
            PROJECT_ROOT / "Analysis_3D",
            PROJECT_ROOT / "Analysis3D",
            PROJECT_ROOT / "core",
            PROJECT_ROOT / "Data_Loggers",
            PROJECT_ROOT,
        ]
    )

    unique: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        try:
            resolved = root.resolve()
        except OSError:
            continue
        if resolved.exists() and resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def find_project_file(filename: str, preferred_roots: Iterable[str] = ()) -> Path:
    """Encuentra un archivo del proyecto dando prioridad a la nueva estructura."""
    candidates: list[Path] = []

    for root in _candidate_roots(preferred_roots):
        direct = root / filename
        if direct.is_file() and _is_allowed(direct):
            candidates.append(direct)

        try:
            for path in root.rglob(filename):
                if path.is_file() and _is_allowed(path):
                    candidates.append(path)
        except OSError:
            continue

    unique: dict[Path, Path] = {}
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        unique.setdefault(resolved, candidate)

    if not unique:
        searched = ", ".join(str(root) for root in _candidate_roots(preferred_roots))
        raise FileNotFoundError(
            f"No se encontró {filename!r}. Rutas examinadas: {searched}"
        )

    def score(path: Path) -> tuple[int, int, str]:
        relative = path.relative_to(PROJECT_ROOT.resolve())
        preferred = 0
        if preferred_roots and relative.parts:
            preferred = 0 if relative.parts[0] in set(preferred_roots) else 1
        return preferred, len(relative.parts), str(relative).lower()

    return min(unique, key=score)


def add_import_path(path: Path) -> None:
    value = str(path.resolve())
    if value in sys.path:
        sys.path.remove(value)
    sys.path.insert(0, value)


def prepare_project_paths() -> None:
    """Añade las carpetas relevantes para imports internos de los módulos."""
    add_import_path(PROJECT_ROOT)
    for folder_name in ("Analysis_3D", "Analysis3D", "core", "Data_Loggers"):
        folder = PROJECT_ROOT / folder_name
        if folder.is_dir():
            add_import_path(folder)

    for filename in ("analytics.py", "csv_schema.py", "utils.py", "constants.py"):
        try:
            add_import_path(find_project_file(filename).parent)
        except FileNotFoundError:
            pass


def load_project_module(
    module_name: str,
    filename: str | None = None,
    preferred_roots: Iterable[str] = (),
):
    """Carga un módulo desde el repositorio y evita paquetes homónimos externos."""
    filename = filename or f"{module_name.rsplit('.', 1)[-1]}.py"
    path = find_project_file(filename, preferred_roots)
    prepare_project_paths()
    add_import_path(path.parent)

    existing = sys.modules.get(module_name)
    if existing is not None:
        existing_file = getattr(existing, "__file__", None)
        if existing_file:
            try:
                if Path(existing_file).resolve() == path.resolve():
                    return existing
            except OSError:
                pass
        sys.modules.pop(module_name, None)

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo crear el cargador para {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


class FakeVector:
    """Vector mínimo suficiente para las funciones geométricas probadas."""

    def __init__(self, values=(0.0, 0.0, 0.0)):
        values = tuple(values)
        self.x = float(values[0]) if len(values) > 0 else 0.0
        self.y = float(values[1]) if len(values) > 1 else 0.0
        self.z = float(values[2]) if len(values) > 2 else 0.0

    def __add__(self, other):
        return FakeVector((self.x + other.x, self.y + other.y, self.z + other.z))

    def __sub__(self, other):
        return FakeVector((self.x - other.x, self.y - other.y, self.z - other.z))

    def __mul__(self, value):
        return FakeVector((self.x * value, self.y * value, self.z * value))

    __rmul__ = __mul__

    def __truediv__(self, value):
        return FakeVector((self.x / value, self.y / value, self.z / value))

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def __getitem__(self, index):
        return (self.x, self.y, self.z)[index]

    def __setitem__(self, index, value):
        if index == 0:
            self.x = float(value)
        elif index == 1:
            self.y = float(value)
        elif index == 2:
            self.z = float(value)
        else:
            raise IndexError(index)

    def copy(self):
        return FakeVector((self.x, self.y, self.z))

    @property
    def length_squared(self) -> float:
        return self.x**2 + self.y**2 + self.z**2

    @property
    def length(self) -> float:
        return self.length_squared**0.5


def install_minimal_blender_stubs() -> None:
    """Instala sustitutos mínimos para importar lógica pura fuera de Blender."""
    bpy = sys.modules.get("bpy")
    if bpy is None:
        bpy = types.ModuleType("bpy")
        sys.modules["bpy"] = bpy
    if not hasattr(bpy, "path"):
        bpy.path = types.SimpleNamespace(abspath=lambda value: value)
    if not hasattr(bpy, "types"):
        bpy.types = types.SimpleNamespace(Operator=object, Panel=object)
    if not hasattr(bpy, "utils"):
        bpy.utils = types.SimpleNamespace(
            register_class=lambda cls: None,
            unregister_class=lambda cls: None,
        )

    if "bmesh" not in sys.modules:
        bmesh = types.ModuleType("bmesh")
        bmesh.from_edit_mesh = lambda data: None
        bmesh.new = lambda: None
        bmesh.ops = types.SimpleNamespace()
        sys.modules["bmesh"] = bmesh

    if "mathutils" not in sys.modules:
        mathutils = types.ModuleType("mathutils")
        mathutils.Vector = FakeVector
        sys.modules["mathutils"] = mathutils
