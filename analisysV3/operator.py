import bpy
import numpy as np
import matplotlib.pyplot as plt

class OBJECT_OT_MiOperador(bpy.types.Operator):
    bl_idname = "object.mi_operador"
    bl_label = "Mostrar Gráfica Matplotlib"
    bl_description = "Ejemplo de matplotlib dentro de Blender"

    def execute(self, context):
        x = np.linspace(0, 10, 100)
        y = np.sin(x)

        plt.figure()
        plt.plot(x, y)
        plt.title("Seno dentro de Blender")
        plt.show()

        self.report({'INFO'}, "Gráfica mostrada con matplotlib")
        return {'FINISHED'}