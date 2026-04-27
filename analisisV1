
bl_info = { 
    "name": "Prueba2",
    "author": "María",
    "version": (0, 1),
    "blender": (4, 3, 0),
    "location": "3D View > Sidebar > Análisis 3D",
    "description": "Sistema avanzado de análisis CSV",
    "category": "3D View",
}

import bpy
import os
from bpy.props import *


# ─────────────────────────────────────────
# MÉTRICAS COMPLETAS
# ─────────────────────────────────────────

ANALYSIS = {
    "A1": {"label":"Total time","typology":"Temporal"},
    "A2": {"label":"Breaks","typology":"Temporal"},
    "A3": {"label":"Breaks by phase","typology":"Temporal"},
    "A4": {"label":"Movement Speed","typology":"Spatial"},
    "A5": {"label":"Proximity to object","typology":"Spatial"},
    "A6": {"label":"View manipulation","typology":"Spatial"},
    "A7": {"label":"Speed during inactivity","typology":"Spatial"},
    "A8": {"label":"Speed during activity","typology":"Spatial"},
    "A10":{"label":"Acceleration strategy 1","typology":"Strategy"},
    "A11":{"label":"Acceleration strategy 2","typology":"Strategy"},
    "A12":{"label":"Model evolution","typology":"Strategy"},
    "A13":{"label":"Error evolution","typology":"Strategy"},
    "A14":{"label":"Mode of work","typology":"Strategy"},
    "A15":{"label":"UV work","typology":"Strategy"},
    "A16":{"label":"Mesh evolution","typology":"Strategy"},
}


# ─────────────────────────────────────────
# GRÁFICOS COMPLETOS
# ─────────────────────────────────────────

GRAPH_TYPES = {
    "G1": {"label": "Interaction","roles": {"X":1},"allow_mix": False,"compatible_typologies": ["Temporal","Spatial","Strategy"]},
    "G2": {"label": "Forest plot","roles": {"X":1,"Y":1},"allow_mix": False,"compatible_typologies": ["Temporal","Strategy"]},
    "G3": {"label": "Radar plot","roles": {"X":3},"allow_mix": False,"compatible_typologies": ["Spatial","Strategy"]},
    "G4": {"label": "Correlation Plot","roles": {"X":1,"Y":1},"allow_mix": True,"compatible_typologies": ["Temporal","Spatial"]},
    "G5": {"label": "Time Lapse","roles": {"X":1},"allow_mix": False,"compatible_typologies": ["Temporal"]},
    "G6": {"label": "Scatter plot","roles": {"X":1,"Y":1},"allow_mix": True,"compatible_typologies": ["Temporal","Spatial"]},
}


# ─────────────────────────────────────────
# REFRESH LIST
# ─────────────────────────────────────────

def refresh_analysis_list(self, context):
    if context is None or context.scene is None:
        return

    scn = context.scene
    scn.analysis_items.clear()
    graph = GRAPH_TYPES[scn.selected_graph]

    for aid, info in ANALYSIS.items():
        if info["typology"] in graph["compatible_typologies"]:
            item = scn.analysis_items.add()
            item.key = aid
            item.label = info["label"]
            item.typology = info["typology"]
            item.enabled = False
            item.role = 'X'


# ─────────────────────────────────────────
# VALIDACIÓN CENTRAL
# ─────────────────────────────────────────

def validate_selection(context):
    scn = context.scene
    graph = GRAPH_TYPES[scn.selected_graph]
    selected = [i for i in scn.analysis_items if i.enabled]

    if not selected:
        return False, "No variables selected"

    # Validar roles
    for role, count in graph["roles"].items():
        role_items = [i for i in selected if i.role == role]
        if len(role_items) != count:
            return False, f"{graph['label']} requires {count} variable(s) in role {role}"

    # Validación por modo
    if scn.analysis_mode == "DESCRIPTIVE" and len(selected) != 1:
        return False, "Descriptive mode requires exactly 1 variable"
    if scn.analysis_mode == "COMPARATIVE":
        if len({i.typology for i in selected}) > 1:
            return False, "Comparative mode requires same typology"
    if scn.analysis_mode == "INFERENTIAL":
        if not graph["allow_mix"] and len({i.typology for i in selected}) > 1:
            return False, "This graph does not allow mixed typologies"

    return True, "OK"


# ─────────────────────────────────────────
# PROPERTY GROUPS
# ─────────────────────────────────────────

class CSVItem(bpy.types.PropertyGroup):
    name: StringProperty()
    selected: BoolProperty(default=True)


class AnalysisItem(bpy.types.PropertyGroup):
    key: StringProperty()
    label: StringProperty()
    typology: StringProperty()
    enabled: BoolProperty(default=False)
    role: EnumProperty(items=[('X','X',''),('Y','Y',''),('G','Group','')], default='X')


# ─────────────────────────────────────────
# FUNCIONES CSV
# ─────────────────────────────────────────

def detect_csvs(folder):
    if not folder or not os.path.isdir(folder):
        return []
    return [os.path.join(folder,f) for f in os.listdir(folder) if f.lower().endswith(".csv")]


# ─────────────────────────────────────────
# OPERADORES
# ─────────────────────────────────────────

class ANALI_OT_DetectCSV(bpy.types.Operator):
    bl_idname = "anali.detect_csv"
    bl_label = "Scan CSV"

    def execute(self, context):
        scn = context.scene
        scn.csv_items.clear()
        rutas = detect_csvs(scn.csv_folder)
        for r in rutas:
            item = scn.csv_items.add()
            item.name = r
            item.selected = True
        self.report({'INFO'}, f"{len(rutas)} CSV detected")
        return {'FINISHED'}


class ANALI_OT_RunAnalysis(bpy.types.Operator):
    bl_idname = "anali.run_analysis"
    bl_label = "Analyze CSV"

    def execute(self, context):
        scn = context.scene
        selected_csvs = [i.name for i in scn.csv_items if i.selected]
        if not selected_csvs:
            self.report({'ERROR'}, "No CSV selected")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Analyzing {len(selected_csvs)} CSV(s)")
        print("CSV:", selected_csvs)
        return {'FINISHED'}


class ANALI_OT_Visualize(bpy.types.Operator):
    bl_idname = "anali.visualize_graph"
    bl_label = "Visualize Graph"

    def execute(self, context):
        scn = context.scene
        valid, message = validate_selection(context)
        if not valid:
            self.report({'ERROR'}, message)
            return {'CANCELLED'}
        self.report({'INFO'}, "Graph visualization ready!")
        print("Graph visualization with:", [i.key for i in scn.analysis_items if i.enabled])
        return {'FINISHED'}


# ─────────────────────────────────────────
# UI LISTS
# ─────────────────────────────────────────

class ANALI_UL_CSVList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "selected", text="")
        layout.label(text=os.path.basename(item.name))


class ANALI_UL_AnalysisList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text=item.label)
        row.label(text=f"[{item.typology}]")  # <--- Typology visible
        if item.enabled:
            row.prop(item, "role", text="")


# ─────────────────────────────────────────
# PANEL
# ─────────────────────────────────────────

class ANALI_PT_MainPanel(bpy.types.Panel):
    bl_label = "Análisis 3D CSV"
    bl_category = "Análisis 3D"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        scn = context.scene
        layout = self.layout

        # CSV
        layout.prop(scn, "csv_folder", text="CSV Folder")
        layout.template_list("ANALI_UL_CSVList", "", scn, "csv_items", scn, "csv_index")

        row = layout.row(align=True)
        row.operator("anali.detect_csv")
        row.operator("anali.run_analysis")  # <--- Analyze CSV next to Scan CSV

        layout.separator()

        # Analysis
        layout.prop(scn, "analysis_mode")
        layout.prop(scn, "selected_graph")
        layout.template_list("ANALI_UL_AnalysisList", "", scn, "analysis_items", scn, "analysis_index")

        layout.separator()
        layout.operator("anali.visualize_graph")  # <--- Visualize Graph at the end


# ─────────────────────────────────────────
# REGISTRO
# ─────────────────────────────────────────

classes = [
    CSVItem,
    AnalysisItem,
    ANALI_UL_CSVList,
    ANALI_UL_AnalysisList,
    ANALI_PT_MainPanel,
    ANALI_OT_DetectCSV,
    ANALI_OT_RunAnalysis,
    ANALI_OT_Visualize
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.csv_folder = StringProperty(subtype='DIR_PATH')
    bpy.types.Scene.csv_items = CollectionProperty(type=CSVItem)
    bpy.types.Scene.csv_index = IntProperty(default=0)

    bpy.types.Scene.analysis_items = CollectionProperty(type=AnalysisItem)
    bpy.types.Scene.analysis_index = IntProperty(default=0)

    bpy.types.Scene.selected_graph = EnumProperty(
        name="Graph",
        items=[(k,v["label"],"") for k,v in GRAPH_TYPES.items()],
        default="G1",
        update=refresh_analysis_list
    )

    bpy.types.Scene.analysis_mode = EnumProperty(
        name="Mode",
        items=[
            ('DESCRIPTIVE','Descriptive',''),
            ('COMPARATIVE','Comparative',''),
            ('INFERENTIAL','Inferential',''),
        ],
        default='DESCRIPTIVE'
    )


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.csv_folder
    del bpy.types.Scene.csv_items
    del bpy.types.Scene.csv_index
    del bpy.types.Scene.analysis_items
    del bpy.types.Scene.analysis_index
    del bpy.types.Scene.selected_graph
    del bpy.types.Scene.analysis_mode


if __name__ == "__main__":
    register()
