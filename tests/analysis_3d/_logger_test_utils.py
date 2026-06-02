# Herramientas para la monitorización y análisis de procesos de modelado 3D en Blender
# Copyright (C) 2026 María Molina Goyena
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# at your option any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

"""Helpers for importing Data_Logger_3D.py outside Blender during tests."""
from __future__ import annotations

import importlib.util
import os
import pathlib
import sys
import types


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
    def new(self, name: str):
        txt = _FakeText(name)
        self[name] = txt
        return txt

    def remove(self, text):
        name = getattr(text, "name", None)
        if name in self:
            del self[name]


class _Vector:
    def __init__(self, values=(0.0, 0.0, 0.0)):
        self.x = float(values[0]) if len(values) > 0 else 0.0
        self.y = float(values[1]) if len(values) > 1 else 0.0
        self.z = float(values[2]) if len(values) > 2 else 0.0

    def __add__(self, other):
        return _Vector((self.x + other.x, self.y + other.y, self.z + other.z))

    def __sub__(self, other):
        return _Vector((self.x - other.x, self.y - other.y, self.z - other.z))

    def __truediv__(self, value):
        return _Vector((self.x / value, self.y / value, self.z / value))

    @property
    def length(self):
        return (self.x ** 2 + self.y ** 2 + self.z ** 2) ** 0.5


def _install_fake_blender_modules() -> None:
    if "bpy" in sys.modules:
        return

    bpy = types.ModuleType("bpy")
    bpy.data = types.SimpleNamespace(texts=_FakeTexts(), filepath="/tmp/test_scene.blend")
    bpy.context = types.SimpleNamespace(
        screen=None,
        scene=types.SimpleNamespace(objects=[]),
        object=None,
        mode="OBJECT",
        window_manager=types.SimpleNamespace(operators=[]),
    )
    bpy.types = types.SimpleNamespace(Operator=object, Panel=object)
    bpy.utils = types.SimpleNamespace(register_class=lambda cls: None, unregister_class=lambda cls: None)

    handlers_mod = types.ModuleType("bpy.app.handlers")
    handlers_mod.load_post = []
    handlers_mod.save_post = []
    handlers_mod.depsgraph_update_post = []
    handlers_mod.persistent = lambda fn: fn

    app_mod = types.ModuleType("bpy.app")
    app_mod.handlers = handlers_mod
    app_mod.timers = types.SimpleNamespace(register=lambda fn: None)
    bpy.app = app_mod

    bmesh = types.ModuleType("bmesh")
    bmesh.from_edit_mesh = lambda data: None

    mathutils = types.ModuleType("mathutils")
    mathutils.Vector = _Vector

    sys.modules["bpy"] = bpy
    sys.modules["bpy.app"] = app_mod
    sys.modules["bpy.app.handlers"] = handlers_mod
    sys.modules["bmesh"] = bmesh
    sys.modules["mathutils"] = mathutils


def _candidate_logger_paths() -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    env_path = os.environ.get("DATA_LOGGER_PATH")
    if env_path:
        paths.append(pathlib.Path(env_path))

    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        paths.extend(parent.glob("Data_Logger_3D*.py"))
        paths.extend(parent.glob("../Data_Logger_3D*.py"))
        paths.extend(parent.glob("../../Data_Logger_3D*.py"))

    paths.extend(pathlib.Path("/mnt/data").glob("Data_Logger_3D*.py"))

    unique = []
    seen = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen and resolved.exists():
            seen.add(resolved)
            unique.append(resolved)
    return unique


def load_logger_module():
    _install_fake_blender_modules()
    candidates = _candidate_logger_paths()
    if not candidates:
        raise unittest.SkipTest("No se encontró Data_Logger_3D.py; define DATA_LOGGER_PATH o colócalo junto al add-on.")

    path = candidates[0]
    module_name = f"data_logger_under_test_{abs(hash(str(path))) }"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Import at end to keep SkipTest local to load_logger_module.
import unittest
