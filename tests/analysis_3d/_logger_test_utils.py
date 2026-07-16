# Herramientas para la monitorización y análisis de procesos de modelado 3D en Blender
# Copyright (C) 2026 María Molina Goyena
# SPDX-License-Identifier: GPL-3.0-or-later

"""Carga de ``Data_Logger_3D.py`` fuera de Blender para los tests."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import types

import pytest


class _FakeText:
    def __init__(self, name: str):
        self.name = name
        self._content = ""
        self.use_fake_user = False
        self.use_module = False
        self.filepath = ""

    def as_string(self) -> str:
        return self._content

    def clear(self) -> None:
        self._content = ""

    def write(self, value: str) -> None:
        self._content += str(value)


class _FakeTexts(dict):
    def new(self, name: str) -> _FakeText:
        text = _FakeText(name)
        self[name] = text
        return text

    def remove(self, text: object) -> None:
        name = getattr(text, "name", None)
        if name in self:
            del self[name]


class _Vector:
    def __init__(self, values=(0.0, 0.0, 0.0)):
        values = tuple(values)
        self.x = float(values[0]) if len(values) > 0 else 0.0
        self.y = float(values[1]) if len(values) > 1 else 0.0
        self.z = float(values[2]) if len(values) > 2 else 0.0

    def __add__(self, other):
        return _Vector((self.x + other.x, self.y + other.y, self.z + other.z))

    def __sub__(self, other):
        return _Vector((self.x - other.x, self.y - other.y, self.z - other.z))

    def __mul__(self, value):
        return _Vector((self.x * value, self.y * value, self.z * value))

    __rmul__ = __mul__

    def __truediv__(self, value):
        return _Vector((self.x / value, self.y / value, self.z / value))

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
        return _Vector((self.x, self.y, self.z))

    @property
    def length_squared(self) -> float:
        return self.x**2 + self.y**2 + self.z**2

    @property
    def length(self) -> float:
        return self.length_squared**0.5


def _install_fake_blender_modules() -> None:
    """Instala dobles mínimos de Blender si los módulos reales no existen."""
    bpy = sys.modules.get("bpy")
    if bpy is None:
        bpy = types.ModuleType("bpy")
        sys.modules["bpy"] = bpy

    if not hasattr(bpy, "data"):
        bpy.data = types.SimpleNamespace(texts=_FakeTexts(), filepath="/tmp/test_scene.blend")
    if not hasattr(bpy, "context"):
        bpy.context = types.SimpleNamespace(
            screen=None,
            scene=types.SimpleNamespace(objects=[]),
            object=None,
            mode="OBJECT",
            window_manager=types.SimpleNamespace(operators=[]),
        )
    if not hasattr(bpy, "types"):
        bpy.types = types.SimpleNamespace(Operator=object, Panel=object)
    if not hasattr(bpy, "utils"):
        bpy.utils = types.SimpleNamespace(
            register_class=lambda cls: None,
            unregister_class=lambda cls: None,
        )

    handlers_mod = sys.modules.get("bpy.app.handlers")
    if handlers_mod is None:
        handlers_mod = types.ModuleType("bpy.app.handlers")
        handlers_mod.load_post = []
        handlers_mod.save_post = []
        handlers_mod.depsgraph_update_post = []
        handlers_mod.persistent = lambda fn: fn
        sys.modules["bpy.app.handlers"] = handlers_mod

    app_mod = sys.modules.get("bpy.app")
    if app_mod is None:
        app_mod = types.ModuleType("bpy.app")
        sys.modules["bpy.app"] = app_mod
    app_mod.handlers = handlers_mod
    if not hasattr(app_mod, "timers"):
        app_mod.timers = types.SimpleNamespace(register=lambda fn: None)
    bpy.app = app_mod

    if "bmesh" not in sys.modules:
        bmesh = types.ModuleType("bmesh")
        bmesh.from_edit_mesh = lambda data: None
        sys.modules["bmesh"] = bmesh

    if "mathutils" not in sys.modules:
        mathutils = types.ModuleType("mathutils")
        mathutils.Vector = _Vector
        sys.modules["mathutils"] = mathutils


def _candidate_logger_paths() -> list[Path]:
    """Busca el logger en ``Data_Loggers`` y admite una ruta por variable."""
    project_root = Path(__file__).resolve().parents[2]
    candidates: list[Path] = []

    env_path = os.environ.get("DATA_LOGGER_PATH")
    if env_path:
        candidates.append(Path(env_path).expanduser())

    search_roots = (
        project_root / "Data_Loggers",
        project_root,
    )
    patterns = (
        "Data_Logger_3D.py",
        "Data_Logger_3D*.py",
        "*Data*Logger*3D*.py",
    )

    for root in search_roots:
        if not root.exists():
            continue
        for pattern in patterns:
            candidates.extend(root.rglob(pattern))

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_file() and resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)

    return unique


def load_logger_module():
    _install_fake_blender_modules()
    candidates = _candidate_logger_paths()
    if not candidates:
        pytest.skip(
            "No se encontró Data_Logger_3D.py dentro de Data_Loggers. "
            "También puedes definir DATA_LOGGER_PATH con su ruta completa."
        )

    path = candidates[0]
    module_name = f"data_logger_under_test_{abs(hash(str(path)))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.fail(f"No se pudo crear el cargador para {path}", pytrace=False)

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
