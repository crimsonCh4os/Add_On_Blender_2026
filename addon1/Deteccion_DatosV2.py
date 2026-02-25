bl_info = {
    "name": "Data Logger 3D - Research Safe",
    "author": "Maria",
    "version": (0, 2),
    "blender": (3, 0, 0),
    "location": "View3D > N Panel > Data Logger",
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
# VERSION
# -------------------------------------------------------

SCRIPT_VERSION = "2.2"

# -------------------------------------------------------
# USER ID
# -------------------------------------------------------

USER_ID = hashlib.md5(os.path.expanduser("~").encode()).hexdigest()[:8]

# -------------------------------------------------------
# GLOBAL STATE
# -------------------------------------------------------

timer_running = False
start_time = None
_last_timestamp = -1

prev_vert_count = 0
prev_ngon_count = 0
prev_tri_count = 0
prev_object_count = 0
prev_inverted_normals = 0
prev_total_mods = 0
prev_mode = None

undo_flag = 0
uv_menu_flag = 0

handlers_registered = False

# -------------------------------------------------------
# CSV
# -------------------------------------------------------

TEMP_CSV_PATH = os.path.join(tempfile.gettempdir(), "blender_data_log.csv")

CSV_HEADER = [
    "ScriptVersion","USER_ID","TimeStamp","Minute","Second",
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

# -------------------------------------------------------
# UTILITIES
# -------------------------------------------------------

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
# OPERATOR TRACKING
# -------------------------------------------------------

last_operator=None
operator_flags={"shift_d":0,"alt_d":0,"ctrl_v":0,"merge":0}

@persistent
def operator_tracker(scene,depsgraph):
    global last_operator,operator_flags,uv_menu_flag
    wm=bpy.context.window_manager
    if not wm.operators:
        return
    op=wm.operators[-1].bl_idname
    if op==last_operator:
        return
    last_operator=op
    if op=="OBJECT_OT_duplicate":
        operator_flags["shift_d"]=1
    elif op=="OBJECT_OT_duplicate_linked":
        operator_flags["alt_d"]=1
    elif op=="VIEW3D_OT_pastebuffer":
        operator_flags["ctrl_v"]=1
    elif "merge" in op.lower():
        operator_flags["merge"]=1
    elif op=="UV_OT_unwrap":
        uv_menu_flag=1

@persistent
def handle_undo(dummy):
    global undo_flag
    undo_flag=1

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
        SCRIPT_VERSION,USER_ID,timestamp,minute,second,
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
    row=collect_data()
    if row:
        append_csv(row)
    return 1.0

# -------------------------------------------------------
# OPERATORS START / STOP
# -------------------------------------------------------

class DATA_LOGGER_OT_Start(bpy.types.Operator):
    bl_idname="data_logger.start"
    bl_label="Start Logging"

    def execute(self,context):
        global timer_running,start_time
        global prev_vert_count,prev_ngon_count,prev_tri_count
        global prev_object_count,prev_inverted_normals
        global prev_total_mods

        if timer_running:
            return {'CANCELLED'}

        start_time=time.time()
        scene=bpy.context.scene
        meshes=[o for o in scene.objects if o.type=="MESH"]

        prev_vert_count=sum(len(o.data.vertices) for o in meshes)
        prev_ngon_count=sum(1 for o in meshes for p in o.data.polygons if len(p.vertices)>4)
        prev_tri_count=sum(1 for o in meshes for p in o.data.polygons if len(p.vertices)==3)
        prev_inverted_normals=sum(count_inverted_normals(o) for o in meshes)
        prev_object_count=len(scene.objects)
        prev_total_mods=sum(len(o.modifiers) for o in scene.objects)

        init_csv()

        timer_running=True
        bpy.app.timers.register(logger_timer)

        self.report({'INFO'}, "Data Logger Started")
        return {'FINISHED'}

class DATA_LOGGER_OT_Stop(bpy.types.Operator):
    bl_idname="data_logger.stop"
    bl_label="Stop Logging"

    def execute(self,context):
        global timer_running
        timer_running=False
        import_csv_to_blend()
        self.report({'INFO'}, "Data Logger Stopped")
        return {'FINISHED'}

# -------------------------------------------------------
# PANEL UI
# -------------------------------------------------------

class DATA_LOGGER_PT_Panel(bpy.types.Panel):
    bl_label="Data Logger"
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='Data Logger'

    def draw(self,context):
        layout=self.layout
        if timer_running:
            layout.label(text="● Recording...",icon='REC')
            layout.operator("data_logger.stop",icon='CANCEL')
        else:
            layout.operator("data_logger.start",icon='PLAY')

# -------------------------------------------------------
# AUTORUN WARNING
# -------------------------------------------------------

class DATA_LOGGER_OT_AutoRunWarning(bpy.types.Operator):
    bl_idname="wm.data_logger_autorun_warning"
    bl_label="Auto Run Required"

    def execute(self,context):
        bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
        bpy.context.preferences.active_section='SAVE_LOAD'
        return {'FINISHED'}

    def invoke(self,context,event):
        return context.window_manager.invoke_props_dialog(self,width=420)

    def draw(self,context):
        layout=self.layout
        layout.label(text="Auto Run Python Scripts is disabled.",icon='ERROR')
        layout.label(text="Enable it in:")
        layout.label(text="Edit → Preferences → Save & Load")

# -------------------------------------------------------
# REGISTER
# -------------------------------------------------------

classes=[
    DATA_LOGGER_OT_Start,
    DATA_LOGGER_OT_Stop,
    DATA_LOGGER_PT_Panel,
    DATA_LOGGER_OT_AutoRunWarning
]

def register():
    global handlers_registered
    for cls in classes:
        bpy.utils.register_class(cls)

    if not handlers_registered:
        bpy.app.handlers.undo_post.append(handle_undo)
        bpy.app.handlers.depsgraph_update_post.append(operator_tracker)
        handlers_registered=True

    if not bpy.context.preferences.filepaths.use_scripts_auto_execute:
        bpy.ops.wm.data_logger_autorun_warning('INVOKE_DEFAULT')

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__=="__main__":
    register()
