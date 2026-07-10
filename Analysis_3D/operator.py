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

import bpy

try:
    from .texts import tr
except ImportError:
    from texts import tr
import numpy as np
import matplotlib.pyplot as plt

class OBJECT_OT_MiOperador(bpy.types.Operator):
    """Example operator to check Matplotlib integration in Blender.

    Draws a simple sine curve in a Matplotlib window. It is kept as a diagnostic
    utility and does not participate in CSV or mesh metric calculation.
    """
    bl_idname = "object.mi_operador"
    bl_label = "Show Matplotlib Chart"
    bl_description = "Show a test sine graph to validate Matplotlib inside Blender"

    @classmethod
    def description(cls, context, properties):
        if context is not None and getattr(context, "scene", None) is not None:
            return tr(context.scene, cls.bl_description)
        return cls.bl_description

    def execute(self, context):
        x = np.linspace(0, 10, 100)
        y = np.sin(x)

        plt.figure()
        plt.plot(x, y)
        plt.title("Sine inside Blender")
        plt.show()

        self.report({'INFO'}, "Chart shown with matplotlib")
        return {'FINISHED'}