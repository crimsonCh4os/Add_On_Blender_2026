bl_info = { 
    "name": "Análisis 3D",
    "author": "María",
    "version": (0, 3),
    "blender": (2, 8, 0),
    "location": "3D View > Sidebar > Análisis 3D",
    "description": "Sistema avanzado de análisis CSV con métricas automáticas y visualización 3D",
    "category": "3D View",
}

import bpy
import sys
import os

# ──────────────
# Matplotlib / Numpy
# ──────────────
site_packages_path = os.path.join(os.path.dirname(__file__), "site-packages")
if os.path.exists(site_packages_path):
    sys.path.insert(0, site_packages_path)

try:
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
except ImportError as e:
    print("Error cargando matplotlib o numpy:", e)


import sys
import os
sys.path.append(os.path.dirname(__file__))

# ──────────────
# __init__.py
import bpy

from . import utils
from . import graphs # Tu UI y operadores de métricas
from . import ui

def register():
    # Propiedades de Scene
    bpy.types.Scene.reference_obj = bpy.props.PointerProperty(
        name="Reference Object",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
    )


    utils.register()# Registra tus clases del UI
    graphs.register()
    ui.register()

def unregister():
    ui.unregister()
    graphs.unregister()
    utils.unregister()
    if hasattr(bpy.types.Scene, "reference_obj"):
        del bpy.types.Scene.reference_obj