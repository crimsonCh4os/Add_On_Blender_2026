bl_info = {
    "name": "Data Logger 3D",
    "author": "Maria",
    "version": (1, 5),
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

timer_running = False
start_time = None
frame_counter = 0
_last_elapsed = -1

_last_transform_hash = {}
_last_obj_hash = {}
_last_obj_data_ref = {}
_last_uv_hash = {}
_last_mod_state = {}

prev_vert_count = 0
prev_ngon_count = 0
prev_tri_count = 0
prev_object_count = 0
prev_inverted_normals = 0
prev_mode = None

LAST_PERSISTENT_STATE = None
LAST_WRITE_TIME = 0.0
MIN_EVENT_INTERVAL = 0

# -------------------------------------------------------
# CSV
# -------------------------------------------------------

TEMP_CSV_PATH = os.path.join(tempfile.gettempdir(), "blender_data_log.csv")

CSV_HEADER = [
    "USER_ID","Elapsed","Minute","Second",
    "UserX","UserY","UserZ",
    "SceneRadius",
    "ObjX","ObjY","ObjZ","ObjRadius",
    "VertexDelta","NgonDelta","TriDelta","NormalDelta",
    "ObjMode","EditMode","UV",
    "ObjectDelta","ModifierDelta",
    "CtrlV","ShiftD","AltD","Merge"
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
# UTILIDADES
# -------------------------------------------------------

def hash_data(data):
    return hashlib.sha256(str(data).encode()).hexdigest()

def normalize_delta(v):
    return 1 if v>0 else -1 if v<0 else 0

def round_all(vals):
    return [round(v,2) if isinstance(v,float) else v for v in vals]

def hash_uv_layer(obj):
    if not obj or obj.type != "MESH":
        return None

    uv_layer = obj.data.uv_layers.active
    if not uv_layer:
        return None

    return hash_data(tuple(
        (round(l.uv.x, 5), round(l.uv.y, 5))
        for l in uv_layer.data
    ))

import bmesh

def count_inverted_normals(mesh_obj):
    if mesh_obj.type != "MESH":
        return 0

    mesh = mesh_obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    
    original_normals = [f.normal.copy() for f in bm.faces]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    
    inverted = 0

    for f, orig_n in zip(bm.faces, original_normals):
        if orig_n.dot(f.normal) < 0:
            inverted += 1

    bm.free()

    return inverted


# -------------------------------------------------------
# ESCENA INFO
# -------------------------------------------------------

def get_camera_pos():

    if not bpy.context.screen:
        return (0,0,0)

    for a in bpy.context.screen.areas:
        if a.type == "VIEW_3D":
            r3d = a.spaces.active.region_3d
            pos = r3d.view_matrix.inverted().translation
            return tuple(round(x,4) for x in pos)

    return (0,0,0)

def get_scene_radius():

    objs = bpy.context.scene.objects
    if not objs:
        return 0.0

    coords = [o.location for o in objs]
    center = sum(coords, mathutils.Vector()) / len(coords)
    return max((o.location-center).length for o in objs)

def get_active_object_data():

    obj = bpy.context.object
    if not obj:
        return (0,0,0,0)

    bbox = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    center = sum(bbox, mathutils.Vector()) / 8
    radius = max((v-center).length for v in bbox)

    return center.x,center.y,center.z,radius

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

# -------------------------------------------------------
# DATA COLLECTION
# -------------------------------------------------------

def collect_object_data():

    global frame_counter,_last_elapsed
    global prev_vert_count,prev_ngon_count,prev_tri_count
    global prev_object_count,prev_mode
    global operator_flags

    if start_time is None:
        return None

    elapsed = round(time.time()-start_time,2)

    if elapsed == _last_elapsed:
        return None

    _last_elapsed = elapsed

    scene = bpy.context.scene

    minute = int(elapsed//60)
    second = elapsed % 60

    user = get_camera_pos()
    scene_radius = get_scene_radius()
    ox,oy,oz,orad = get_active_object_data()

    meshes = [o for o in scene.objects if o.type=="MESH"]

    # ---------------------------
    # FLAGS (NO RESETEAR DESPUÉS)
    # ---------------------------

    shift_d = 0
    alt_d = 0
    merge = 0
    ctrl_v = operator_flags["ctrl_v"]

    # ---------------------------
    # DETECTAR DUPLICADOS
    # ---------------------------

    for obj in scene.objects:

        if obj.type != "MESH":
            continue

        if obj.name not in _last_obj_hash:

            linked_found = False

            for prev_name, prev_data in _last_obj_data_ref.items():
                if obj.data == prev_data:
                    linked_found = True
                    break

            if linked_found:
                alt_d = 1
            else:
                shift_d = 1

            _last_obj_hash[obj.name] = (
                len(obj.data.vertices),
                len(obj.data.polygons)
            )

            _last_obj_data_ref[obj.name] = obj.data

    # ---------------------------
    # DETECTAR MERGE
    # ---------------------------

    for obj in meshes:

        prev_data = _last_obj_hash.get(obj.name)

        if prev_data:

            prev_verts, prev_polys = prev_data

            if (
                len(obj.data.vertices) < prev_verts or
                len(obj.data.polygons) < prev_polys
            ):
                merge = 1

        _last_obj_hash[obj.name] = (
            len(obj.data.vertices),
            len(obj.data.polygons)
        )

    # ---------------------------
    # GEOMETRÍA GLOBAL
    # ---------------------------

    total_verts = sum(len(o.data.vertices) for o in meshes)
    ngons = sum(1 for o in meshes for p in o.data.polygons if len(p.vertices)>4)
    tris = sum(1 for o in meshes for p in o.data.polygons if len(p.vertices)==3)

    v_delta = normalize_delta(total_verts-prev_vert_count)
    n_delta = normalize_delta(ngons-prev_ngon_count)
    t_delta = normalize_delta(tris-prev_tri_count)

    prev_vert_count = total_verts
    prev_ngon_count = ngons
    prev_tri_count = tris
    
    # ---------------------------
    # NORMALES INVERTIDAS
    # ---------------------------

    global prev_inverted_normals

    total_inverted = sum(
        count_inverted_normals(o)
        for o in meshes
    )

    normal_delta = normalize_delta(total_inverted - prev_inverted_normals)
    prev_inverted_normals = total_inverted


    # ---------------------------
    # OBJETOS
    # ---------------------------

    obj_delta = normalize_delta(len(scene.objects)-prev_object_count)
    prev_object_count = len(scene.objects)

    # ---------------------------
    # MODIFICADORES
    # ---------------------------

    mod_delta = 0

    for obj in scene.objects:

        mods = len(obj.modifiers)
        prev = _last_mod_state.get(obj.name,mods)

        if mods != prev:
            mod_delta = normalize_delta(mods-prev)
            _last_mod_state[obj.name] = mods
            break

    # ---------------------------
    # MODOS
    # ---------------------------

    mode = bpy.context.mode
    obj_mode = int(prev_mode!=mode and mode=="OBJECT")
    edit_mode = int(prev_mode!=mode and mode=="EDIT_MESH")
    prev_mode = mode

    '''
    # ---------------------------
    # TRANSFORM
    # ---------------------------

    transform_delta = 0

    for obj in scene.objects:

        h = hash_data((
            tuple(obj.location),
            tuple(obj.rotation_euler),
            tuple(obj.scale)
        ))

        if _last_transform_hash.get(obj.name) != h:
            transform_delta = 1

        _last_transform_hash[obj.name] = h
    '''

    # ---------------------------
    # UV (CAMBIO REAL)
    # ---------------------------

    uv = 0
    ao = bpy.context.object

    if ao and ao.type == "MESH" and ao.data.uv_layers.active:
        h = hash_uv_layer(ao)
        prev = _last_uv_hash.get(ao.name)

        if prev is not None and h != prev:
            uv = 1

        _last_uv_hash[ao.name] = h


    # ---------------------------
    # RECORD
    # ---------------------------

    record = round_all([
        USER_ID,elapsed,minute,second,
        user[0],user[1],user[2],
        scene_radius,
        ox,oy,oz,orad,
        v_delta,n_delta,t_delta,normal_delta,
        obj_mode,edit_mode,uv,
        obj_delta,mod_delta,
        ctrl_v,shift_d,alt_d,merge
    ])

    frame_counter += 1

    # reset SOLO ctrl_v
    operator_flags["ctrl_v"] = 0

    return ",".join(str(v) for v in record)


# -------------------------------------------------------
# TIMER
# -------------------------------------------------------

def logger_timer():

    if not timer_running:
        return None

    row = collect_object_data()

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


if __name__=="__main__":
    register()
