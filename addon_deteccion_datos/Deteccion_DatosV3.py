bl_info = {
    "name": "Data Logger 3D",
    "author": "Maria",
    "version": (0, 3),
    "blender": (3, 0, 0),
    "location": "View3D",
    "category": "3D View",
}

import bpy
import time
import os
import tempfile
import hashlib
import mathutils
from bpy.app.handlers import persistent



# -------------------------------------------------------
# USER ID
# -------------------------------------------------------

USER_ID = hashlib.md5(os.path.expanduser("~").encode()).hexdigest()[:8]

# -------------------------------------------------------
# OPERADOR TRACKING (NUEVO SISTEMA ROBUSTO)
# -------------------------------------------------------

last_operator = None

operator_flags = {
    "shift_d": 0,
    "alt_d": 0,
    "ctrl_v": 0,
    "merge": 0
}

# -------------------------------------------------------
# ESTADO GLOBAL
# -------------------------------------------------------


global uv_menu_flag
uv_menu_flag = 1
_last_timestamp = -1
timer_running = False
start_time = None
frame_counter = 0
_last_elapsed = -1

_last_transform_hash = {}
_last_obj_hash = {}
_last_obj_data_ref = {}
_last_uv_hash = {}
_last_mod_state = {}

prev_total_mods = 0
prev_vert_count = 0
prev_ngon_count = 0
prev_tri_count = 0
prev_object_count = 0
prev_inverted_normals = 0
prev_mode = None

undo_flag = 0
uv_menu_flag = 0

handlers_registered = False

LAST_PERSISTENT_STATE = None
LAST_WRITE_TIME = 0.0
MIN_EVENT_INTERVAL = 0

# -------------------------------------------------------
# CSV
# -------------------------------------------------------

TEMP_CSV_PATH = os.path.join(tempfile.gettempdir(), "blender_data_log.csv")

CSV_HEADER = [
    "USER_ID","TimeStamp","Minute","Second",
    "UserX","UserY","UserZ",
    "SceneRadius",
    "ObjX","ObjY","ObjZ","ObjRadius",
    "VertexDelta","NgonDelta","TriDelta","NormalDelta",
    "ObjModeState","EditModeState","ModeChanged","UV",
    "ObjectDelta","ModifierDelta",
    "CtrlV","ShiftD","AltD","Merge",
    "UndoAction"
]

def init_csv():
    with open(TEMP_CSV_PATH,"w",encoding="utf-8") as f:
        f.write(",".join(CSV_HEADER)+"\n")

def append_csv(row):
    with open(TEMP_CSV_PATH,"a",encoding="utf-8") as f:
        f.write(row+"\n")
    
def import_csv_to_blend():
    """Incrusta el CSV temporal como TextBlock en el .blend."""
    if not os.path.exists(TEMP_CSV_PATH):
        return
    text_name = "data_log_internal.csv"
    if text_name in bpy.data.texts:
        txt = bpy.data.texts[text_name]
        txt.clear()
    else:
        txt = bpy.data.texts.new(text_name)
    with open(TEMP_CSV_PATH, "r", encoding="utf-8") as f:
        txt.write(f.read())
    txt.use_fake_user = True
    txt.use_module = False
    txt.filepath = ""
    print(f"CSV temporal incrustado en el .blend como '{text_name}'")
    
def remove_duplicate_rows():

    if not os.path.exists(TEMP_CSV_PATH):
        return

    with open(TEMP_CSV_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    header = lines[0]
    unique_rows = list(dict.fromkeys(lines[1:]))

    with open(TEMP_CSV_PATH, "w", encoding="utf-8") as f:
        f.write(header)
        f.writelines(unique_rows)


# -------------------------------------------------------
# UTILITIES
# -------------------------------------------------------
def hash_data(data):
    return hashlib.sha256(str(data).encode()).hexdigest()

def round_all(vals):
    return [round(v,4) if isinstance(v,float) else v for v in vals]

def count_inverted_normals(mesh_obj):
    if mesh_obj.type != "MESH":
        return 0
    return sum(1 for p in mesh_obj.data.polygons if p.normal.dot(p.center) < 0)

# -------------------------------------------------------
# SCENE METRICS
# -------------------------------------------------------

def get_camera_pos():
    for a in bpy.context.screen.areas:
        if a.type == "VIEW_3D":
            r3d = a.spaces.active.region_3d
            pos = r3d.view_matrix.inverted().translation
            return tuple(pos)
    return (0,0,0)

def get_active_object_data():
    obj = bpy.context.object
    if not obj:
        return (0,0,0,0)
    bbox = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    center = sum(bbox, mathutils.Vector())/8
    radius = max((v-center).length for v in bbox)
    return center.x,center.y,center.z,radius

def get_scene_radius():
    objs = [o for o in bpy.context.scene.objects if o.type=="MESH"]
    if not objs:
        return 0.0
    centers=[]
    radii=[]
    for o in objs:
        bbox=[o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
        center=sum(bbox,mathutils.Vector())/8
        radius=max((v-center).length for v in bbox)
        centers.append(center)
        radii.append(radius)
    global_center=sum(centers,mathutils.Vector())/len(centers)
    return max((c-global_center).length+r for c,r in zip(centers,radii))


# -------------------------------------------------------
# HASH INICIAL
# -------------------------------------------------------

def init_hashes():

    _last_obj_hash.clear()
    _last_obj_data_ref.clear()

    for obj in bpy.context.scene.objects:

        _last_transform_hash[obj.name] = hash_data((
            tuple(obj.location),
            tuple(obj.rotation_euler),
            tuple(obj.scale)
        ))

        if obj.type == "MESH":

            _last_obj_hash[obj.name] = (
                len(obj.data.vertices),
                len(obj.data.polygons)
            )

            _last_obj_data_ref[obj.name] = obj.data



# -------------------------------------------------------
# OPERATOR TRACKER
# -------------------------------------------------------

@persistent
def uv_transform_tracker(scene, depsgraph):

    # Verificar si estamos en el modo de edición de UV
    if bpy.context.object.mode != 'EDIT' or bpy.context.active_object.type != 'MESH':
        return

    # Comprobar si el espacio UV es el activo
    if bpy.context.space_data.type == 'IMAGE_EDITOR':
        # Si se realiza una transformación en UV, actualizar el flag
        if bpy.context.tool_settings.use_transform:
            # Aquí podrías rastrear rotación y escalado, por ejemplo:
            uv_menu_flag = 1
        
@persistent
def operator_tracker(scene, depsgraph):

    global last_operator
    global operator_flags

    wm = bpy.context.window_manager

    if not wm.operators:
        return

    op = wm.operators[-1].bl_idname

    if op == last_operator:
        return

    last_operator = op

    if op == "OBJECT_OT_duplicate":
        operator_flags["shift_d"] = 1

    elif op == "OBJECT_OT_duplicate_linked":
        operator_flags["alt_d"] = 1

    elif op == "VIEW3D_OT_pastebuffer":
        operator_flags["ctrl_v"] = 1

    elif "merge" in op.lower():
        operator_flags["merge"] = 1
        
    if "transform" in op.lower():
        uv_menu_flag = 1
        

# -------------------------------------------------------
# UV MAPING
# -------------------------------------------------------

class UV_MAPPING_OT_Operator(bpy.types.Operator):
    bl_idname = "uv.mapping_operator"
    bl_label = "UV Mapping Operator"

    def execute(self, context):
        # Aquí defines las transformaciones que deseas habilitar
        bpy.ops.transform.resize(value=(1.2, 1.2, 1.2))  # Ejemplo de escala
        bpy.ops.transform.rotate(value=0.1)  # Ejemplo de rotación
        uv_menu_flag = 1  # Actualiza el flag de la acción UV
        return {'FINISHED'}

def uv_menu_callback(self, context):
    self.layout.operator(UV_MAPPING_OT_Operator.bl_idname)

# -------------------------------------------------------
# DATA COLLECTION
# -------------------------------------------------------

def collect_data():
    global _last_timestamp
    global prev_vert_count,prev_ngon_count,prev_tri_count
    global prev_object_count,prev_inverted_normals
    global prev_total_mods,prev_mode
    global undo_flag,uv_menu_flag,operator_flags

    timestamp=round(time.time(),2)
    if timestamp==_last_timestamp:
        return None
    _last_timestamp=timestamp

    scene=bpy.context.scene
    minute=int((timestamp-start_time)//60)
    second=(timestamp-start_time)%60

    user=get_camera_pos()
    scene_radius=get_scene_radius()
    ox,oy,oz,orad=get_active_object_data()

    meshes=[o for o in scene.objects if o.type=="MESH"]

    total_verts=sum(len(o.data.vertices) for o in meshes)
    ngons=sum(1 for o in meshes for p in o.data.polygons if len(p.vertices)>4)
    tris=sum(1 for o in meshes for p in o.data.polygons if len(p.vertices)==3)
    total_inverted=sum(count_inverted_normals(o) for o in meshes)
    total_mods=sum(len(o.modifiers) for o in scene.objects)

    v_delta=total_verts-prev_vert_count
    n_delta=ngons-prev_ngon_count
    t_delta=tris-prev_tri_count
    normal_delta=total_inverted-prev_inverted_normals
    obj_delta=len(scene.objects)-prev_object_count
    mod_delta=total_mods-prev_total_mods

    prev_vert_count=total_verts
    prev_ngon_count=ngons
    prev_tri_count=tris
    prev_inverted_normals=total_inverted
    prev_object_count=len(scene.objects)
    prev_total_mods=total_mods

    mode=bpy.context.mode
    obj_mode_state=int(mode=="OBJECT")
    edit_mode_state=int(mode=="EDIT_MESH")
    mode_changed=int(prev_mode!=mode)
    prev_mode=mode

    record=round_all([
        USER_ID,timestamp,minute,second,
        user[0],user[1],user[2],
        scene_radius,
        ox,oy,oz,orad,
        v_delta,n_delta,t_delta,normal_delta,
        obj_mode_state,edit_mode_state,mode_changed,uv_menu_flag,
        obj_delta,mod_delta,
        operator_flags["ctrl_v"],
        operator_flags["shift_d"],
        operator_flags["alt_d"],
        operator_flags["merge"],
        undo_flag
    ])

    operator_flags={"shift_d":0,"alt_d":0,"ctrl_v":0,"merge":0}
    undo_flag=0
    uv_menu_flag=0

    return ",".join(str(v) for v in record)


# -------------------------------------------------------
# TIMER
# -------------------------------------------------------

def logger_timer():

    if not timer_running:
        return None

    row = collect_data()

    if row:
        append_csv(row)
        remove_duplicate_rows()
        import_csv_to_blend()

    return 1.0


# -------------------------------------------------------
# CONTROL LOGGER
# -------------------------------------------------------

def start_logger():
    global timer_running,start_time,_last_elapsed

    if timer_running:
        return

    start_time=time.time()
    _last_elapsed=-1

    init_hashes()

    restored = restore_csv_from_blend()
    if not restored:
        init_csv()


    timer_running=True
    bpy.app.timers.register(logger_timer)

def stop_logger():
    global timer_running
    timer_running=False

def restore_csv_from_blend():
    """Restaura el CSV incrustado en el .blend al CSV temporal si existe."""
    if "data_log_internal.csv" not in bpy.data.texts:
        return False

    content = bpy.data.texts["data_log_internal.csv"].as_string().strip()
    if not content:
        return False

    with open(TEMP_CSV_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print("CSV restaurado desde el .blend.")
    return True

# -------------------------------------------------------
# KEYMAPS
# -------------------------------------------------------

addon_keymaps=[]

def register_keymaps():
    wm=bpy.context.window_manager
    kc=wm.keyconfigs.addon

    if kc:
        km=kc.keymaps.new(name="3D View",space_type="VIEW_3D")

        kmi=km.keymap_items.new("object.duplicate_logger",'D','PRESS',shift=True)
        addon_keymaps.append((km,kmi))

        kmi=km.keymap_items.new("object.duplicate_linked_logger",'D','PRESS',alt=True)
        addon_keymaps.append((km,kmi))

        kmi=km.keymap_items.new("view3d.paste_logger",'V','PRESS',ctrl=True)
        addon_keymaps.append((km,kmi))


# =========================================================
# POPUPS DE CONSENTIMIENTO Y AUTORUN
# =========================================================

class DATA_LOGGER_OT_ConsentPopup(bpy.types.Operator):
    bl_idname = "wm.data_logger_consent"
    bl_label = "Consentimiento de recopilación de datos"

    def execute(self, context):
        consent_text = get_consent_textblock()
        consent_text.clear()
        consent_text.write("ACCEPTED")
        start_logger()
        self.report({'INFO'}, "Consentimiento aceptado EXECUTE.")
        return {'FINISHED'}

    def cancel(self, context):
        bpy.ops.wm.data_logger_consent('INVOKE_DEFAULT')
        return {'CANCELLED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.label(text="¿Aceptas la recopilación de datos técnicos?")
        layout.label(text="(Transformaciones, tiempo de uso, etc.)")
        layout.label(text="Si rechazas, esta ventana se repetirá hasta aceptar.")

class DATA_LOGGER_OT_AutoRunWarning(bpy.types.Operator):
    bl_idname = "wm.data_logger_autorun_warning"
    bl_label = "Auto Run desactivado"
    _timer = None

    def modal(self, context, event):
        if bpy.context.preferences.filepaths.use_scripts_auto_execute:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)
            self.report({'INFO'}, "Auto Run activado correctamente.")
            bpy.ops.wm.data_logger_consent('INVOKE_DEFAULT')
            return {'FINISHED'}
        return {'PASS_THROUGH'}

    def execute(self, context):
        bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
        self.report({'INFO'}, "Abriendo las Preferencias de Blender...")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        return {'CANCELLED'}

    def invoke(self, context, event):
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        wm.modal_handler_add(self)
        return wm.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Auto Run no está activado.", icon='ERROR')
        layout.separator()
        layout.label(text="Edit → Preferences → File Paths → Auto Run Python Scripts")
        layout.separator()
        layout.label(text="Esta ventana permanecerá abierta hasta que lo actives.")

# =========================================================
# HANDLERS PERSISTENTES
# =========================================================
@persistent
def check_consent_on_load(dummy):
    prefs = bpy.context.preferences.filepaths

    if not prefs.use_scripts_auto_execute:
        print("Auto Run desactivado. Mostrando aviso.")
        # Mostrar aviso con retardo
        bpy.app.timers.register(lambda: bpy.ops.wm.data_logger_autorun_warning('INVOKE_DEFAULT'), first_interval=0.5)
        return

    consent_text = get_consent_textblock()
    if "ACCEPTED" in consent_text.as_string():
        start_logger()
    else:
        # Abrir popup de consentimiento con retardo
        bpy.app.timers.register(lambda: bpy.ops.wm.data_logger_consent('INVOKE_DEFAULT'), first_interval=0.5)

# -------------------------------------------------------
# HANDLERS
# -------------------------------------------------------


@persistent
def handle_undo(dummy):
    if not os.path.exists(TEMP_CSV_PATH):
        return
    with open(TEMP_CSV_PATH, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    if len(lines) > 1:
        lines = lines[:-1]
        with open(TEMP_CSV_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        import_csv_to_blend()
        print("↩ Último registro eliminado tras deshacer.")

@persistent
def handle_save(dummy):
    import_csv_to_blend()
    print("CSV incrustado en el archivo .blend al guardar.")

# =========================================================
# EXPORTACIÓN A CSV (Panel)
# =========================================================

class DATA_LOGGER_PT_Panel(bpy.types.Panel):
    bl_label = "Data Logger"
    bl_idname = "DATA_LOGGER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Data Logger"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Exportar registros a CSV:")
        layout.operator("wm.data_logger_export_csv", icon="EXPORT")

class DATA_LOGGER_OT_ExportCSV(bpy.types.Operator):
    bl_idname = "wm.data_logger_export_csv"
    bl_label = "Exportar a CSV"

    def execute(self, context):
        blend_path = bpy.data.filepath
        if not blend_path:
            self.report({'ERROR'}, "Guarda el archivo .blend antes de exportar.")
            return {'CANCELLED'}
        if "data_log_internal.csv" not in bpy.data.texts:
            self.report({'ERROR'}, "No hay CSV incrustado para exportar.")
            return {'CANCELLED'}
        textblock = bpy.data.texts["data_log_internal.csv"]
        content = textblock.as_string()
        if not content.strip():
            self.report({'WARNING'}, "El CSV está vacío, nada que exportar.")
            return {'CANCELLED'}
        directory = os.path.dirname(blend_path)
        filename = os.path.splitext(os.path.basename(blend_path))[0] + "_data.csv"
        csv_path = os.path.join(directory, filename)
        try:
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            self.report({'ERROR'}, f"No se pudo guardar el CSV: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Datos exportados correctamente: {csv_path}")
        return {'FINISHED'}
    
# =========================================================
# UTILIDAD DE CONSENTIMIENTO
# =========================================================
def get_consent_textblock():
    if "consent_flag" not in bpy.data.texts:
        bpy.data.texts.new("consent_flag")
    return bpy.data.texts["consent_flag"]


# =========================================================
# REGISTRO DEL ADDON
# =========================================================

classes = [
    DATA_LOGGER_OT_ConsentPopup,
    DATA_LOGGER_OT_AutoRunWarning,
    DATA_LOGGER_PT_Panel,
    DATA_LOGGER_OT_ExportCSV
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.load_post.append(check_consent_on_load)
    bpy.app.handlers.undo_post.append(handle_undo)
    bpy.app.handlers.save_post.append(handle_save)
    bpy.app.handlers.depsgraph_update_post.append(operator_tracker)
    bpy.utils.register_class(UV_MAPPING_OT_Operator)
    bpy.types.VIEW3D_MT_mesh_add.append(uv_menu_callback)

    print("Data Logger cargado y escuchando eventos.")

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    if check_consent_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(check_consent_on_load)
    if handle_undo in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(handle_undo)
    if handle_save in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(handle_save)
    if operator_tracker in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(operator_tracker)
    bpy.utils.unregister_class(UV_MAPPING_OT_Operator)
    bpy.types.VIEW3D_MT_mesh_add.remove(uv_menu_callback)


if __name__=="__main__":
    register()