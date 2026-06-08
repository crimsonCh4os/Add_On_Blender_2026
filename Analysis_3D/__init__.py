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
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "3D View > Sidebar > 3D Analysis",
    "description": "Advanced CSV analysis system with automatic metrics and 3D visualization",
    "category": "3D View",
}

import os

try:
    import bpy
except ModuleNotFoundError:  # Permite importar/compilar el paquete fuera de Blender.
    bpy = None

from .dependencies import add_local_site_packages, ensure_modules

# Dependencias externas.
add_local_site_packages(os.path.dirname(__file__))
_missing = ensure_modules(("numpy", "matplotlib"), install=False)
if _missing:
    print(f"[3D Analysis] Dependencias no disponibles: {_missing}. Instálalas en Blender Python o incluye site-packages local.")

if bpy is not None:
    from . import utils
    from . import graphs
    from . import ui

def register():
    if bpy is None:
        raise RuntimeError("Analysis 3D solo puede registrarse dentro de Blender.")

    bpy.types.Scene.reference_obj = bpy.props.PointerProperty(
        name="Reference Object",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
    )


    utils.register()
    graphs.register()
    ui.register()

def unregister():
    if bpy is None:
        return

    ui.unregister()
    graphs.unregister()
    utils.unregister()
    if hasattr(bpy.types.Scene, "reference_obj"):
        del bpy.types.Scene.reference_obj