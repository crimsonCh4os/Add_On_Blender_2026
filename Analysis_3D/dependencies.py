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

"""Gestión segura de dependencias externas para Blender Python."""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
from typing import Iterable


def add_local_site_packages(addon_dir: str) -> None:
    """Añade site-packages local solo si existe y no está ya registrado."""
    path = os.path.join(addon_dir, "site-packages")
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)


def ensure_modules(modules: Iterable[str], *, install: bool = False) -> list[str]:
    """Comprueba dependencias y opcionalmente intenta instalarlas con Blender Python.

    Devuelve la lista de módulos que siguen faltando. No silencia errors: imprime
    mensajes claros para que el usuario pueda depurar desde la consola de Blender.
    """
    missing: list[str] = []
    for module in modules:
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(module)

    if not install or not missing:
        return missing

    python_bin = getattr(sys, "executable", None)
    if not python_bin:
        return missing

    try:
        subprocess.check_call([python_bin, "-m", "ensurepip", "--upgrade"])
        subprocess.check_call([python_bin, "-m", "pip", "install", *missing])
    except PermissionError as exc:
        print(
            "[3D Analysis] Permisos insuficientes para instalar dependencias con pip. "
            "Instálalas manualmente en el Python de Blender o copia los paquetes a "
            "la carpeta local site-packages del addon. "
            f"Detalle: {exc}"
        )
        return missing
    except (OSError, subprocess.CalledProcessError) as exc:
        print(
            "[3D Analysis] No se pudieron instalar dependencias automáticamente. "
            "Revisa que ensurepip/pip estén disponibles y que el entorno permita "
            f"escritura. Detalle: {exc}"
        )
        return missing

    return [m for m in missing if importlib.util.find_spec(m) is None]
