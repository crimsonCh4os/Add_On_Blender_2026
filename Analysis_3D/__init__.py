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

bl_info = { 
    "name": "Analysis 3D",
    "author": "María",
    "version": (1, 2, 6),
    "blender": (4, 0, 0),
    "location": "3D View > Sidebar > 3D Analysis",
    "description": "Advanced CSV analysis system with automatic metrics and 3D visualization",
    "category": "3D View",
}

try:
    import bpy
except ModuleNotFoundError:  # Permite importar/compilar el paquete fuera de Blender.
    bpy = None

from .dependencies import dependency_error_message, missing_modules

_missing_dependencies = missing_modules()

# Los módulos funcionales importan NumPy/Matplotlib. Solo se cargan cuando el
# entorno está preparado, evitando errores poco claros durante la activación.
if bpy is not None and not _missing_dependencies:
    from . import graphs, ui, utils


def register():
    if bpy is None:
        raise RuntimeError("Analysis 3D solo puede registrarse dentro de Blender.")

    if _missing_dependencies:
        message = dependency_error_message(_missing_dependencies)
        print(f"[Analysis 3D] {message}")
        raise RuntimeError(message)

    utils.register()
    graphs.register()
    ui.register()


def unregister():
    if bpy is None or _missing_dependencies:
        return

    ui.unregister()
    graphs.unregister()
    utils.unregister()
    if hasattr(bpy.types.Scene, "reference_obj"):
        del bpy.types.Scene.reference_obj
