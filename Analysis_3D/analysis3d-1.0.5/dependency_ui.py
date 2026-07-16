# SPDX-License-Identifier: GPL-3.0-or-later
"""Dependency installer UI that can load before NumPy/Matplotlib exist."""
from __future__ import annotations

import bpy

from .dependencies import dependencies_available, install_dependencies, missing_dependencies


class ANALI_OT_InstallDependencies(bpy.types.Operator):
    bl_idname = "anali.install_dependencies"
    bl_label = "Install dependencies / Instalar dependencias"
    bl_description = "Download NumPy and Matplotlib from PyPI into the private add-on folder"
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            install_dependencies()
        except Exception as exc:
            self.report({'ERROR'}, f"Installation failed / Instalación fallida: {exc}")
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            "Dependencies installed. Restart Blender. / Dependencias instaladas. Reinicia Blender.",
        )
        return {'FINISHED'}


class ANALI_PT_DependencyBootstrap(bpy.types.Panel):
    bl_label = "Analysis 3D — Dependencies / Dependencias"
    bl_category = "3D Analysis"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        missing = missing_dependencies()
        if not missing:
            layout.label(text="Dependencies installed / Dependencias instaladas", icon='CHECKMARK')
            layout.label(text="Restart Blender to load Analysis 3D / Reinicia Blender", icon='INFO')
            return

        box = layout.box()
        box.label(text="Required libraries are missing", icon='ERROR')
        box.label(text="Faltan bibliotecas necesarias")
        box.label(text="Missing / Faltan: " + ", ".join(missing))
        box.operator(ANALI_OT_InstallDependencies.bl_idname, icon='IMPORT')
        box.label(text="Internet connection required / Requiere Internet", icon='URL')
        box.label(text="Restart Blender afterwards / Reinicia Blender después")


_BOOTSTRAP_CLASSES = (
    ANALI_OT_InstallDependencies,
    ANALI_PT_DependencyBootstrap,
)


def register_bootstrap() -> None:
    for cls in _BOOTSTRAP_CLASSES:
        try:
            bpy.utils.register_class(cls)
        except RuntimeError:
            pass


def unregister_bootstrap() -> None:
    for cls in reversed(_BOOTSTRAP_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


def register_operator_only() -> None:
    try:
        bpy.utils.register_class(ANALI_OT_InstallDependencies)
    except RuntimeError:
        pass


def unregister_operator_only() -> None:
    try:
        bpy.utils.unregister_class(ANALI_OT_InstallDependencies)
    except RuntimeError:
        pass
