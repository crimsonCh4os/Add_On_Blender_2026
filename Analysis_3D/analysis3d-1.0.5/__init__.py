# Tools for monitoring and analysing 3D modelling workflows in Blender
# Copyright (C) 2026 María Molina Goyena
# SPDX-License-Identifier: GPL-3.0-or-later

bl_info = {
    "name": "Analysis 3D",
    "author": "María",
    "version": (1, 0, 5),
    "blender": (4, 0, 0),
    "location": "3D View > Sidebar > 3D Analysis",
    "description": "Advanced CSV analysis system with automatic metrics and 3D visualization",
    "category": "3D View",
}


import os
import sys

try:
    import bpy
except ModuleNotFoundError:
    bpy = None


def _remove_stale_analysis3d_paths() -> None:
    """Remove private dependency folders left by older Analysis3D installs.

    Blender may preserve sys.path entries after a failed add-on activation. A
    partially installed NumPy in one of those folders can then break the next
    activation before the repair panel is shown.
    """
    current_private = os.path.normcase(os.path.abspath(os.path.join(os.path.dirname(__file__), "site-packages")))
    cleaned = []
    for entry in list(sys.path):
        try:
            normalized = os.path.normcase(os.path.abspath(entry))
        except Exception:
            cleaned.append(entry)
            continue
        lowered = normalized.lower().replace("\\", "/")
        is_analysis_private = lowered.endswith("/site-packages") and "analysis3d" in lowered
        if is_analysis_private and normalized != current_private:
            continue
        cleaned.append(entry)
    sys.path[:] = cleaned


_remove_stale_analysis3d_paths()

from . import dependency_ui
from .dependencies import add_local_site_packages, missing_dependencies

_missing = None
_full_modules = None


def _get_missing_dependencies():
    global _missing
    if _missing is None:
        _missing = missing_dependencies()
    return _missing


def _load_full_modules():
    global _full_modules
    if _full_modules is not None:
        return _full_modules
    add_local_site_packages(os.path.dirname(__file__))
    from . import utils, graphs, ui
    _full_modules = (utils, graphs, ui)
    return _full_modules


def register():
    if bpy is None:
        raise RuntimeError("Analysis 3D can only be registered inside Blender.")

    missing = _get_missing_dependencies()
    if missing:
        dependency_ui.register_bootstrap()
        print(f"[Analysis 3D] Missing dependencies / Dependencias faltantes: {missing}")
        return

    utils, graphs, ui = _load_full_modules()
    dependency_ui.register_operator_only()
    utils.register()
    graphs.register()
    ui.register()


def unregister():
    if bpy is None:
        return

    if _get_missing_dependencies():
        dependency_ui.unregister_bootstrap()
        return

    if _full_modules is not None:
        utils, graphs, ui = _full_modules
        ui.unregister()
        graphs.unregister()
        utils.unregister()
    dependency_ui.unregister_operator_only()
    if hasattr(bpy.types.Scene, "reference_obj"):
        del bpy.types.Scene.reference_obj
