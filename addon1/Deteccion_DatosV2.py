bl_info = {
    "name": "Data Logger 3D",
    "author": "Maria",
    "version": (0, 2),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar",
    "category": "3D View",
}

import bpy
import os
import tempfile
import hashlib
import mathutils
import time
from bpy.app.handlers import persistent

# =========================================================
# USER ID
# =========================================================

USER_ID = hashlib.md5(os.path.expanduser("~").encode()).hexdigest()[:8]

# =========================================================
# GLOBAL STATE
# =========================================================

start_time = None
prev_state = {}
undo_flag = 0
uv_menu_flag = 0

operator_flags = {
    "shift_d": 0,
    "alt_d": 0,
    "ctrl_v": 0,
    "merge": 0
}

# =========================================================
# CSV CONFIG
# =========================================================

TEMP_CSV_PATH = os.path.join(tempfile.gettempdir(), "blender_data_log.csv")

CSV_HEADER = [
    "USER_ID","Timestamp","Minute","Second",
    "UserX","UserY","UserZ",
    "SceneRadius",
    "ObjX","ObjY","ObjZ","ObjRadius",
    "VertexDelta","NgonDelta","TriDelta","NormalDelta",
    "ObjMode","EditMode","UV",
    "ObjectDelta","ModifierDelta",
    "CtrlV","ShiftD","AltD","Merge",
    "UndoAction"
]

def init_csv():
    if os.path.exists(TEMP_CSV_PATH):
        return
    with open(TEMP_CSV_PATH,"w",encoding="utf-8") as f:
        f.write(",".join(CSV_HEADER)+"\n")

def append_csv(row):
    with open(TEMP_CSV_PATH,"a",encoding="utf-8") as f:
        f.write(row+"\n")

def import_csv_to_blend():
    if not os.path.exists(TEMP_CSV_PATH):
        return
    name = "data_log_internal.csv"
    if name in bpy.data.texts:
        txt = bpy.data.texts[name]
        txt.clear()
    else:
        txt = bpy.data.texts.new(name)
    with open(TEMP_CSV_PATH,"r",encoding="utf-8") as f:
        txt.write(f.read())
    txt.use_fake_user = True

def restore_csv_from_blend():
    if "data_log_internal.csv" not in bpy.data.texts:
        return False
    content = bpy.data.texts["data_log_internal.csv"].as_string()
    if not content.strip():
        return False
    with open(TEMP_CSV_PATH,"w",encoding="utf-8") as f:
        f.write(content)
    return True

# =========================================================
# METRICS
# =========================================================

def get_camera_pos():
    if not bpy.context.screen:
        return mathutils.Vector((0,0,0))
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            r3d = area.spaces.active.region_3d
            return r3d.view_matrix.inverted().translation
    return mathutils.Vector((0,0,0))

def get_object_center_radius(obj):
    bbox = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    center = sum(bbox, mathutils.Vector()) / 8
    radius = max((v-center).length for v in bbox)
    return center, radius

def get_scene_metrics():
    scene = bpy.context.scene
    meshes = [o for o in scene.objects if o.type == "MESH"]

    verts = sum(len(o.data.vertices) for o in meshes)
    ngons = sum(1 for o in meshes for p in o.data.polygons if len(p.vertices) > 4)
    tris = sum(1 for o in meshes for p in o.data.polygons if len(p.vertices) == 3)
    normals = sum(1 for o in meshes for p in o.data.polygons if p.normal.dot(p.center) < 0)
    modifiers = sum(len(o.modifiers) for o in scene.objects)
    obj_count = len(scene.objects)

    if meshes:
        centers = []
        radii = []
        for o in meshes:
            c, r = get_object_center_radius(o)
            centers.append(c)
            radii.append(r)
        global_center = sum(centers, mathutils.Vector()) / len(centers)
        scene_radius = max((c - global_center).length + r for c, r in zip(centers, radii))
    else:
        scene_radius = 0

    return {
        "verts": verts,
        "ngons": ngons,
        "tris": tris,
        "normals": normals,
        "modifiers": modifiers,
        "obj_count": obj_count,
        "scene_radius": scene_radius
    }

# =========================================================
# EVENT LOGGER
# =========================================================

def log_event():
    global prev_state, undo_flag, uv_menu_flag

    current = get_scene_metrics()

    if not prev_state:
        prev_state = current.copy()
        return

    deltas = {k: current[k] - prev_state.get(k, 0) for k in current}

    if all(v == 0 for v in deltas.values()) and undo_flag == 0 and uv_menu_flag == 0:
        return

    timestamp = time.time()
    elapsed = timestamp - start_time
    minute = int(elapsed // 60)
    second = elapsed % 60

    user = get_camera_pos()
    ao = bpy.context.object

    if ao:
        center, radius = get_object_center_radius(ao)
        ox, oy, oz = center
        orad = radius
    else:
        ox = oy = oz = orad = 0

    mode = bpy.context.mode
    obj_mode = int(mode == "OBJECT")
    edit_mode = int(mode == "EDIT_MESH")

    row = [
        USER_ID, timestamp, minute, second,
        user.x, user.y, user.z,
        current["scene_radius"],
        ox, oy, oz, orad,
        deltas["verts"],
        deltas["ngons"],
        deltas["tris"],
        deltas["normals"],
        obj_mode, edit_mode,
        uv_menu_flag,
        deltas["obj_count"],
        deltas["modifiers"],
        operator_flags["ctrl_v"],
        operator_flags["shift_d"],
        operator_flags["alt_d"],
        operator_flags["merge"],
        undo_flag
    ]

    formatted = ",".join(str(round(v,4)) if isinstance(v,float) else str(v) for v in row)
    append_csv(formatted)
    import_csv_to_blend()

    prev_state = current.copy()
    undo_flag = 0
    uv_menu_flag = 0
    for k in operator_flags:
        operator_flags[k] = 0

# =========================================================
# HANDLERS
# =========================================================

@persistent
def depsgraph_handler(scene, depsgraph):
    log_event()

@persistent
def undo_handler(dummy):
    global undo_flag
    undo_flag = 1

@persistent
def operator_tracker(scene, depsgraph):
    global uv_menu_flag
    wm = bpy.context.window_manager
    if not wm.operators:
        return
    op = wm.operators[-1].bl_idname

    if op == "OBJECT_OT_duplicate":
        operator_flags["shift_d"] = 1
    elif op == "OBJECT_OT_duplicate_linked":
        operator_flags["alt_d"] = 1
    elif op == "VIEW3D_OT_pastebuffer":
        operator_flags["ctrl_v"] = 1
    elif "merge" in op.lower():
        operator_flags["merge"] = 1
    elif op == "UV_OT_unwrap":
        uv_menu_flag = 1

@persistent
def save_handler(dummy):
    import_csv_to_blend()

# =========================================================
# CONSENT SYSTEM
# =========================================================

def get_consent_textblock():
    if "consent_flag" not in bpy.data.texts:
        bpy.data.texts.new("consent_flag")
    return bpy.data.texts["consent_flag"]

class DATA_LOGGER_OT_ConsentPopup(bpy.types.Operator):
    bl_idname = "wm.data_logger_consent"
    bl_label = "Consentimiento de recopilación de datos"

    def execute(self, context):
        txt = get_consent_textblock()
        txt.clear()
        txt.write("ACCEPTED")
        self.report({'INFO'}, "Consentimiento aceptado.")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.label(text="¿Aceptas la recopilación de datos técnicos?")
        layout.label(text="(Transformaciones, geometría, acciones, etc.)")

class DATA_LOGGER_OT_AutoRunWarning(bpy.types.Operator):
    bl_idname = "wm.data_logger_autorun_warning"
    bl_label = "Auto Run desactivado"

    def execute(self, context):
        bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
        bpy.context.preferences.active_section = 'SAVE_LOAD'
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Activa Auto Run Python Scripts en:")
        layout.label(text="Edit → Preferences → Save & Load")

@persistent
def check_consent_on_load(dummy):
    prefs = bpy.context.preferences.filepaths
    if not prefs.use_scripts_auto_execute:
        bpy.app.timers.register(lambda: bpy.ops.wm.data_logger_autorun_warning('INVOKE_DEFAULT'), first_interval=0.5)
        return

    consent = get_consent_textblock()
    if "ACCEPTED" not in consent.as_string():
        bpy.app.timers.register(lambda: bpy.ops.wm.data_logger_consent('INVOKE_DEFAULT'), first_interval=0.5)

# =========================================================
# PANEL EXPORT
# =========================================================

class DATA_LOGGER_PT_Panel(bpy.types.Panel):
    bl_label = "Data Logger"
    bl_idname = "DATA_LOGGER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Data Logger"

    def draw(self, context):
        layout = self.layout
        layout.operator("wm.data_logger_export_csv", icon="EXPORT")

class DATA_LOGGER_OT_ExportCSV(bpy.types.Operator):
    bl_idname = "wm.data_logger_export_csv"
    bl_label = "Exportar a CSV"

    def execute(self, context):
        blend_path = bpy.data.filepath
        if not blend_path:
            self.report({'ERROR'}, "Guarda el archivo .blend primero.")
            return {'CANCELLED'}

        if "data_log_internal.csv" not in bpy.data.texts:
            self.report({'ERROR'}, "No hay CSV incrustado.")
            return {'CANCELLED'}

        content = bpy.data.texts["data_log_internal.csv"].as_string()
        directory = os.path.dirname(blend_path)
        filename = os.path.splitext(os.path.basename(blend_path))[0] + "_data.csv"
        path = os.path.join(directory, filename)

        with open(path,"w",encoding="utf-8") as f:
            f.write(content)

        self.report({'INFO'}, f"Exportado: {path}")
        return {'FINISHED'}

# =========================================================
# REGISTER
# =========================================================

classes = [
    DATA_LOGGER_OT_ConsentPopup,
    DATA_LOGGER_OT_AutoRunWarning,
    DATA_LOGGER_PT_Panel,
    DATA_LOGGER_OT_ExportCSV
]

def register():
    global start_time
    for c in classes:
        bpy.utils.register_class(c)

    restore_csv_from_blend()
    init_csv()

    start_time = time.time()

    bpy.app.handlers.load_post.append(check_consent_on_load)
    bpy.app.handlers.depsgraph_update_post.append(depsgraph_handler)
    bpy.app.handlers.depsgraph_update_post.append(operator_tracker)
    bpy.app.handlers.undo_post.append(undo_handler)
    bpy.app.handlers.save_post.append(save_handler)

def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register()