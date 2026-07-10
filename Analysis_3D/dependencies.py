# Herramientas para la monitorización y análisis de procesos de modelado 3D en Blender
# Copyright (C) 2026 María Molina Goyena
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Comprobación de dependencias externas instaladas en el Python de Blender."""
from __future__ import annotations

import importlib
from collections.abc import Iterable

REQUIRED_MODULES = ("numpy", "matplotlib")


def missing_modules(modules: Iterable[str] = REQUIRED_MODULES) -> list[str]:
    """Devuelve los módulos que no pueden importarse en el entorno actual."""
    missing: list[str] = []
    for module in modules:
        try:
            importlib.import_module(module)
        except (ImportError, OSError):
            missing.append(module)
    return missing


def dependency_error_message(missing: Iterable[str]) -> str:
    """Construye un mensaje útil para Blender y para la consola."""
    names = ", ".join(missing)
    return (
        f"Faltan dependencias de Analysis 3D: {names}. "
        "Ejecuta scripts/install_environment.bat en Windows o "
        "scripts/install_environment.sh en Linux/macOS, indicando la ruta "
        "al ejecutable de Blender. Después reinicia Blender."
    )
