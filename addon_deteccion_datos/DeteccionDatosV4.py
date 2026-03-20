bl_info = {
    "name": "Data Logger 3D",
    "author": "Maria",
    "version": (0, 8, 1),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Data Logger",
    "category": "3D View",
}

import bpy
import bmesh
import time
import os
import tempfile
import hashlib
import math
import mathutils
from bpy.app.handlers import persistent


# =======================================================
# USER
# =======================================================

USER_ID = hashlib.md5(os.path.expanduser("~").encode()).hexdigest()[:8]


# =======================================================
# ESTADO GLOBAL
# =======================================================

timer_running = False
start_time = None

_last_timestamp = -1.0
_force_log_pending = False
_last_operator_index = 0

prev_vert_count = 0
prev_ngon_count = 0
prev_tri_count = 0
prev_inverted_normals = 0
prev_object_count = 0
prev_total_mods = 0
prev_mode = None
prev_uv_hash = ""
prev_snapshot_signature = None
prev_active_object_name = None

operator_flags = {
    "ctrl_v": 0,
    "shift_d": 0,
    "alt_d": 0,
    "merge": 0,
}

_uv_action_pending = 0
_uv_last_action_time = 0.0
addon_keymaps = []

DEBUG_ENABLED = True
DEBUG_LAST_OPERATOR = ""
DEBUG_LAST_LOG_REASON = ""
DEBUG_LAST_REBASE_REASON = ""
DEBUG_UV_HASH_CHANGED = 0
DEBUG_UV_PENDING = 0
DEBUG_LAST_FLAGS = "CtrlV=0 ShiftD=0 AltD=0 Merge=0"


# =======================================================
# CSV
# =======================================================

TEMP_CSV_PATH = os.path.join(tempfile.gettempdir(), "blender_data_log.csv")

CSV_HEADER = [
    "USER_ID", "TimeStamp", "Minute", "Second",
    "UserX", "UserY", "UserZ",
    "SceneRadius",
    "ObjX", "ObjY", "ObjZ", "ObjRadius",
    "VertexDelta", "NgonDelta", "TriDelta", "NormalDelta",
    "ObjModeState", "EditModeState", "ModeChanged", "UV",
    "ObjectDelta", "ModifierDelta",
    "CtrlV", "ShiftD", "AltD", "Merge"
]


def ensure_file_ends_with_newline(path):
    if not os.path.exists(path):
        return

    with open(path, "rb+") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        if size == 0:
            return
        f.seek(-1, os.SEEK_END)
        last = f.read(1)
        if last != b"\n":
            f.seek(0, os.SEEK_END)
            f.write(b"\n")


def init_csv():
    with open(TEMP_CSV_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(",".join(CSV_HEADER) + "\n")


def append_csv(row):
    ensure_file_ends_with_newline(TEMP_CSV_PATH)
    with open(TEMP_CSV_PATH, "a", encoding="utf-8", newline="\n") as f:
        f.write(row + "\n")


def remove_duplicate_rows():
    if not os.path.exists(TEMP_CSV_PATH):
        return

    with open(TEMP_CSV_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        return

    header = lines[0]
    unique_rows = list(dict.fromkeys(lines[1:]))

    with open(TEMP_CSV_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(header)
        f.writelines(unique_rows)

    ensure_file_ends_with_newline(TEMP_CSV_PATH)


def import_csv_to_blend():
    if not os.path.exists(TEMP_CSV_PATH):
        return

    ensure_file_ends_with_newline(TEMP_CSV_PATH)

    text_name = "data_log_internal.csv"
    if text_name in bpy.data.texts:
        txt = bpy.data.texts[text_name]
        txt.clear()
    else:
        txt = bpy.data.texts.new(text_name)

    with open(TEMP_CSV_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if content and not content.endswith("\n"):
        content += "\n"

    txt.write(content)
    txt.use_fake_user = True
    txt.use_module = False
    txt.filepath = ""


def restore_csv_from_blend():
    if "data_log_internal.csv" not in bpy.data.texts:
        return False

    content = bpy.data.texts["data_log_internal.csv"].as_string()
    if not content.strip():
        return False

    if not content.endswith("\n"):
        content += "\n"

    with open(TEMP_CSV_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    ensure_file_ends_with_newline(TEMP_CSV_PATH)
    return True


# =======================================================
# UTILIDADES
# =======================================================

def trunc_2(value):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return math.trunc(value * 100.0) / 100.0
    return value


def trunc_all(values):
    return [trunc_2(v) for v in values]


def force_log_soon():
    global _force_log_pending
    _force_log_pending = True


def safe_mode_of_object(obj):
    try:
        return obj.mode
    except Exception:
        return "OBJECT"


def get_camera_pos():
    try:
        screen = bpy.context.screen
        if not screen:
            return (0.0, 0.0, 0.0)

        for area in screen.areas:
            if area.type == "VIEW_3D":
                r3d = area.spaces.active.region_3d
                pos = r3d.view_matrix.inverted().translation
                return (float(pos.x), float(pos.y), float(pos.z))
    except Exception:
        pass

    return (0.0, 0.0, 0.0)


def get_active_object_name():
    obj = bpy.context.object
    return obj.name if obj else ""


def get_active_object_data():
    obj = bpy.context.object
    if not obj:
        return (0.0, 0.0, 0.0, 0.0)

    try:
        bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
        center = sum(bbox, mathutils.Vector()) / 8
        radius = max((v - center).length for v in bbox)
        return (float(center.x), float(center.y), float(center.z), float(radius))
    except Exception:
        return (0.0, 0.0, 0.0, 0.0)


def get_scene_radius():
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not objs:
        return 0.0

    centers = []
    radii = []

    for o in objs:
        try:
            bbox = [o.matrix_world @ mathutils.Vector(corner) for corner in o.bound_box]
            center = sum(bbox, mathutils.Vector()) / 8
            radius = max((v - center).length for v in bbox)
            centers.append(center)
            radii.append(radius)
        except Exception:
            continue

    if not centers:
        return 0.0

    global_center = sum(centers, mathutils.Vector()) / len(centers)
    return float(max((c - global_center).length + r for c, r in zip(centers, radii)))


def count_inverted_normals_object_mode(mesh_obj):
    if mesh_obj.type != "MESH":
        return 0

    try:
        return sum(1 for p in mesh_obj.data.polygons if p.normal.dot(p.center) < 0)
    except Exception:
        return 0


def count_inverted_normals_edit_mode(obj):
    if obj.type != "MESH":
        return 0

    try:
        bm = bmesh.from_edit_mesh(obj.data)
        total = 0
        for f in bm.faces:
            try:
                if f.normal.dot(f.calc_center_median()) < 0:
                    total += 1
            except Exception:
                pass
        return total
    except Exception:
        return 0


def get_mesh_stats(obj):
    if obj.type != "MESH":
        return (0, 0, 0, 0)

    mode = safe_mode_of_object(obj)

    if mode == "EDIT":
        try:
            bm = bmesh.from_edit_mesh(obj.data)

            verts = len(bm.verts)
            ngons = 0
            tris = 0

            for f in bm.faces:
                vcount = len(f.verts)
                if vcount > 4:
                    ngons += 1
                elif vcount == 3:
                    tris += 1

            inverted = count_inverted_normals_edit_mode(obj)
            return (verts, ngons, tris, inverted)
        except Exception:
            pass

    try:
        verts = len(obj.data.vertices)
        ngons = sum(1 for p in obj.data.polygons if len(p.vertices) > 4)
        tris = sum(1 for p in obj.data.polygons if len(p.vertices) == 3)
        inverted = count_inverted_normals_object_mode(obj)
        return (verts, ngons, tris, inverted)
    except Exception:
        return (0, 0, 0, 0)


def get_global_uv_hash():
    chunks = []

    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue

        try:
            mode = safe_mode_of_object(obj)

            if mode == "EDIT":
                bm = bmesh.from_edit_mesh(obj.data)
                uv_layer = bm.loops.layers.uv.active

                if uv_layer is None:
                    chunks.append((obj.name, "NO_UV_EDIT"))
                    continue

                uv_data = []
                for face in bm.faces:
                    for loop in face.loops:
                        uv = loop[uv_layer].uv
                        uv_data.append((round(float(uv.x), 5), round(float(uv.y), 5)))
                chunks.append((obj.name, tuple(uv_data)))

            else:
                mesh = obj.data
                if not mesh.uv_layers.active:
                    chunks.append((obj.name, "NO_UV_OBJ"))
                    continue

                uv_data = []
                for uv_loop in mesh.uv_layers.active.data:
                    uv = uv_loop.uv
                    uv_data.append((round(float(uv.x), 5), round(float(uv.y), 5)))
                chunks.append((obj.name, tuple(uv_data)))

        except Exception:
            chunks.append((obj.name, "UV_ERROR"))

    return hashlib.sha256(str(chunks).encode()).hexdigest()


# =======================================================
# DETECCIÓN DE OPERADORES
# =======================================================

UV_DEPLOY_OPS = {
    "uv.unwrap",
    "uv.smart_project",
    "uv.lightmap_pack",
    "uv.follow_active_quads",
    "uv.cube_project",
    "uv.cylinder_project",
    "uv.sphere_project",
    "uv.project_from_view",
    "uv.reset",
}

UV_ASSOCIATED_OPS = {
    "uv.pack_islands",
    "uv.average_islands_scale",
    "uv.minimize_stretch",
    "uv.seams_from_islands",
}

MERGE_OPS = {
    "mesh.merge",
    "mesh.remove_doubles",
    "mesh.merge_by_distance",
    "mesh.edge_collapse",
    "mesh.dissolve_verts",
    "mesh.dissolve_edges",
    "mesh.dissolve_faces",
}


def normalize_operator_name(bl_idname):
    return bl_idname.replace("_OT_", ".").lower()


def mark_uv_pending():
    global _uv_action_pending, _uv_last_action_time, DEBUG_UV_PENDING
    _uv_action_pending = 1
    _uv_last_action_time = time.time()
    DEBUG_UV_PENDING = 1


def detect_flags_from_operator(bl_idname):
    global operator_flags
    global DEBUG_LAST_OPERATOR, DEBUG_LAST_FLAGS

    op = normalize_operator_name(bl_idname)
    DEBUG_LAST_OPERATOR = op

    changed = False

    if (
        "view3d.pastebuffer" in op or
        "wm.paste" in op or
        "pastebuffer" in op or
        op.endswith(".paste")
    ):
        if operator_flags["ctrl_v"] == 0:
            operator_flags["ctrl_v"] = 1
            changed = True

    if (
        "object.duplicate_move" in op or
        op == "object.duplicate" or
        "mesh.duplicate_move" in op or
        op == "mesh.duplicate"
    ):
        if "linked" not in op:
            if operator_flags["shift_d"] == 0:
                operator_flags["shift_d"] = 1
                changed = True

    if (
        "object.duplicate_move_linked" in op or
        "object.duplicate_linked" in op
    ):
        if operator_flags["alt_d"] == 0:
            operator_flags["alt_d"] = 1
            changed = True

    if op in MERGE_OPS or "merge" in op:
        if operator_flags["merge"] == 0:
            operator_flags["merge"] = 1
            changed = True

    if op in UV_DEPLOY_OPS or op in UV_ASSOCIATED_OPS:
        mark_uv_pending()
        changed = True

    DEBUG_LAST_FLAGS = (
        f"CtrlV={operator_flags['ctrl_v']} "
        f"ShiftD={operator_flags['shift_d']} "
        f"AltD={operator_flags['alt_d']} "
        f"Merge={operator_flags['merge']}"
    )

    return changed


def process_new_operators():
    global _last_operator_index

    changed = False

    try:
        wm = bpy.context.window_manager
        ops = wm.operators
        count = len(ops)

        if count < _last_operator_index:
            _last_operator_index = 0

        if count == _last_operator_index:
            return False

        for i in range(_last_operator_index, count):
            try:
                bl_id = ops[i].bl_idname
            except Exception:
                continue

            if detect_flags_from_operator(bl_id):
                changed = True

        _last_operator_index = count
    except Exception:
        return False

    return changed


@persistent
def operator_tracker(scene, depsgraph):
    if process_new_operators():
        force_log_soon()


# =======================================================
# WRAPPERS DE ATAJOS
# =======================================================

class OBJECT_OT_duplicate_logger(bpy.types.Operator):
    bl_idname = "object.duplicate_logger"
    bl_label = "Duplicate with Logging"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global operator_flags

        try:
            bpy.ops.object.duplicate_move()
        except Exception:
            try:
                bpy.ops.object.duplicate()
            except Exception:
                self.report({'WARNING'}, "No se pudo ejecutar Shift+D en Object Mode.")
                return {'CANCELLED'}

        operator_flags["shift_d"] = 1
        force_log_soon()
        return {'FINISHED'}


class MESH_OT_duplicate_logger(bpy.types.Operator):
    bl_idname = "mesh.duplicate_logger"
    bl_label = "Mesh Duplicate with Logging"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global operator_flags

        try:
            bpy.ops.mesh.duplicate_move()
        except Exception:
            try:
                bpy.ops.mesh.duplicate()
            except Exception:
                self.report({'WARNING'}, "No se pudo ejecutar Shift+D en Edit Mode.")
                return {'CANCELLED'}

        operator_flags["shift_d"] = 1
        force_log_soon()
        return {'FINISHED'}


class OBJECT_OT_duplicate_linked_logger(bpy.types.Operator):
    bl_idname = "object.duplicate_linked_logger"
    bl_label = "Linked Duplicate with Logging"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global operator_flags

        try:
            bpy.ops.object.duplicate_move_linked()
        except Exception:
            try:
                bpy.ops.object.duplicate(linked=True)
            except Exception:
                self.report({'WARNING'}, "No se pudo ejecutar Alt+D.")
                return {'CANCELLED'}

        operator_flags["alt_d"] = 1
        force_log_soon()
        return {'FINISHED'}


class VIEW3D_OT_paste_logger(bpy.types.Operator):
    bl_idname = "view3d.paste_logger"
    bl_label = "Paste with Logging"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global operator_flags

        try:
            bpy.ops.view3d.pastebuffer()
            operator_flags["ctrl_v"] = 1
            force_log_soon()
            return {'FINISHED'}
        except Exception as e:
            self.report({'WARNING'}, f"No se pudo pegar desde el portapapeles: {e}")
            return {'CANCELLED'}


# =======================================================
# SNAPSHOT DE ESTADO
# =======================================================

def build_snapshot():
    scene = bpy.context.scene
    meshes = [o for o in scene.objects if o.type == "MESH"]

    user = get_camera_pos()
    scene_radius = get_scene_radius()
    ox, oy, oz, orad = get_active_object_data()
    active_name = get_active_object_name()

    total_verts = 0
    ngons = 0
    tris = 0
    total_inverted = 0

    for obj in meshes:
        v, n, t, inv = get_mesh_stats(obj)
        total_verts += v
        ngons += n
        tris += t
        total_inverted += inv

    total_mods = sum(len(o.modifiers) for o in scene.objects)
    mode = bpy.context.mode
    uv_hash = get_global_uv_hash()

    snapshot = {
        "user": (user[0], user[1], user[2]),
        "scene_radius": scene_radius,
        "object": (ox, oy, oz, orad),
        "active_name": active_name,
        "verts": total_verts,
        "ngons": ngons,
        "tris": tris,
        "inverted": total_inverted,
        "obj_count": len(scene.objects),
        "mods": total_mods,
        "mode": mode,
        "uv_hash": uv_hash,
    }

    signature = (
        tuple(trunc_all(snapshot["user"])),
        trunc_2(snapshot["scene_radius"]),
        tuple(trunc_all(snapshot["object"])),
        snapshot["active_name"],
        snapshot["verts"],
        snapshot["ngons"],
        snapshot["tris"],
        snapshot["inverted"],
        snapshot["obj_count"],
        snapshot["mods"],
        snapshot["mode"],
        snapshot["uv_hash"],
    )

    return snapshot, signature


def apply_snapshot_as_baseline(snapshot, signature):
    global prev_vert_count
    global prev_ngon_count
    global prev_tri_count
    global prev_inverted_normals
    global prev_object_count
    global prev_total_mods
    global prev_mode
    global prev_uv_hash
    global prev_snapshot_signature
    global prev_active_object_name

    prev_vert_count = snapshot["verts"]
    prev_ngon_count = snapshot["ngons"]
    prev_tri_count = snapshot["tris"]
    prev_inverted_normals = snapshot["inverted"]
    prev_object_count = snapshot["obj_count"]
    prev_total_mods = snapshot["mods"]
    prev_mode = snapshot["mode"]
    prev_uv_hash = snapshot["uv_hash"]
    prev_snapshot_signature = signature
    prev_active_object_name = snapshot["active_name"]


def init_state():
    global _last_operator_index
    global _last_timestamp
    global _uv_action_pending
    global operator_flags
    global DEBUG_LAST_LOG_REASON, DEBUG_LAST_REBASE_REASON, DEBUG_UV_HASH_CHANGED, DEBUG_UV_PENDING

    snapshot, signature = build_snapshot()
    apply_snapshot_as_baseline(snapshot, signature)

    _last_timestamp = -1.0
    _uv_action_pending = 0
    operator_flags = {
        "ctrl_v": 0,
        "shift_d": 0,
        "alt_d": 0,
        "merge": 0,
    }

    DEBUG_LAST_LOG_REASON = ""
    DEBUG_LAST_REBASE_REASON = ""
    DEBUG_UV_HASH_CHANGED = 0
    DEBUG_UV_PENDING = 0

    try:
        _last_operator_index = len(bpy.context.window_manager.operators)
    except Exception:
        _last_operator_index = 0


# =======================================================
# CONTROL LOGGER
# =======================================================

def start_logger():
    global timer_running
    global start_time

    if timer_running:
        return

    restored = restore_csv_from_blend()
    if not restored:
        init_csv()
    else:
        ensure_file_ends_with_newline(TEMP_CSV_PATH)

    init_state()
    start_time = time.time()

    timer_running = True
    bpy.app.timers.register(logger_timer)
    print("Data Logger iniciado.")


def stop_logger():
    global timer_running
    timer_running = False
    import_csv_to_blend()
    print("Data Logger detenido.")


class WM_OT_data_logger_toggle(bpy.types.Operator):
    bl_idname = "wm.data_logger_toggle"
    bl_label = "Start / Stop Logger"

    def execute(self, context):
        if timer_running:
            stop_logger()
            self.report({'INFO'}, "Logger detenido.")
        else:
            start_logger()
            self.report({'INFO'}, "Logger iniciado.")
        return {'FINISHED'}


# =======================================================
# DATA COLLECTION
# =======================================================

def collect_data(force=False):
    global _last_timestamp
    global prev_mode, prev_active_object_name
    global operator_flags, _uv_action_pending, prev_uv_hash, prev_snapshot_signature
    global DEBUG_LAST_LOG_REASON, DEBUG_LAST_REBASE_REASON, DEBUG_UV_HASH_CHANGED, DEBUG_UV_PENDING

    process_new_operators()
    snapshot, signature = build_snapshot()

    mode_changed_now = (prev_mode != snapshot["mode"])
    active_object_changed = (prev_active_object_name != snapshot["active_name"])

    uv_hash_changed = int(snapshot["uv_hash"] != prev_uv_hash)
    DEBUG_UV_HASH_CHANGED = uv_hash_changed

    recent_uv = (time.time() - _uv_last_action_time) <= 1.0
    uv_action = 1 if (_uv_action_pending and (uv_hash_changed or recent_uv)) else 0

    if mode_changed_now or active_object_changed:
        reasons = []
        if mode_changed_now:
            reasons.append("mode_change")
        if active_object_changed:
            reasons.append("active_object_change")
        DEBUG_LAST_REBASE_REASON = ",".join(reasons)

        obj_mode_state = int(snapshot["mode"] == "OBJECT")
        edit_mode_state = int(snapshot["mode"] == "EDIT_MESH")
        mode_changed = int(mode_changed_now)

        now = time.time()
        timestamp = trunc_2(now)
        if timestamp == _last_timestamp and not force:
            return None
        _last_timestamp = timestamp

        elapsed = now - start_time if start_time is not None else 0.0
        minute = int(elapsed // 60)
        second = trunc_2(elapsed % 60)

        user = snapshot["user"]
        ox, oy, oz, orad = snapshot["object"]

        record = trunc_all([
            USER_ID, timestamp, minute, second,
            user[0], user[1], user[2],
            snapshot["scene_radius"],
            ox, oy, oz, orad,
            0, 0, 0, 0,
            obj_mode_state, edit_mode_state, mode_changed, uv_action,
            0, 0,
            operator_flags["ctrl_v"],
            operator_flags["shift_d"],
            operator_flags["alt_d"],
            operator_flags["merge"],
        ])

        DEBUG_LAST_LOG_REASON = "rebase"
        apply_snapshot_as_baseline(snapshot, signature)

        operator_flags = {
            "ctrl_v": 0,
            "shift_d": 0,
            "alt_d": 0,
            "merge": 0,
        }
        _uv_action_pending = 0
        DEBUG_UV_PENDING = 0

        return ",".join(str(v) for v in record)

    any_operator_flag = (
        operator_flags["ctrl_v"] or
        operator_flags["shift_d"] or
        operator_flags["alt_d"] or
        operator_flags["merge"] or
        uv_action
    )

    state_changed = (signature != prev_snapshot_signature)

    if not force and not state_changed and not any_operator_flag:
        return None

    now = time.time()
    timestamp = trunc_2(now)

    if timestamp == _last_timestamp and not force:
        return None

    _last_timestamp = timestamp

    elapsed = now - start_time if start_time is not None else 0.0
    minute = int(elapsed // 60)
    second = trunc_2(elapsed % 60)

    user = snapshot["user"]
    ox, oy, oz, orad = snapshot["object"]

    v_delta = snapshot["verts"] - prev_vert_count
    n_delta = snapshot["ngons"] - prev_ngon_count
    t_delta = snapshot["tris"] - prev_tri_count
    normal_delta = snapshot["inverted"] - prev_inverted_normals
    obj_delta = snapshot["obj_count"] - prev_object_count
    mod_delta = snapshot["mods"] - prev_total_mods

    if uv_action:
        v_delta = 0
        n_delta = 0
        t_delta = 0
        normal_delta = 0

    obj_mode_state = int(snapshot["mode"] == "OBJECT")
    edit_mode_state = int(snapshot["mode"] == "EDIT_MESH")
    mode_changed = int(prev_mode != snapshot["mode"])

    record = trunc_all([
        USER_ID, timestamp, minute, second,
        user[0], user[1], user[2],
        snapshot["scene_radius"],
        ox, oy, oz, orad,
        v_delta, n_delta, t_delta, normal_delta,
        obj_mode_state, edit_mode_state, mode_changed, uv_action,
        obj_delta, mod_delta,
        operator_flags["ctrl_v"],
        operator_flags["shift_d"],
        operator_flags["alt_d"],
        operator_flags["merge"],
    ])

    reasons = []
    if state_changed:
        reasons.append("state_changed")
    if uv_action:
        reasons.append("uv_action")
    if operator_flags["ctrl_v"]:
        reasons.append("ctrl_v")
    if operator_flags["shift_d"]:
        reasons.append("shift_d")
    if operator_flags["alt_d"]:
        reasons.append("alt_d")
    if operator_flags["merge"]:
        reasons.append("merge")

    DEBUG_LAST_LOG_REASON = ",".join(reasons) if reasons else "unknown"
    DEBUG_LAST_REBASE_REASON = ""

    apply_snapshot_as_baseline(snapshot, signature)

    operator_flags = {
        "ctrl_v": 0,
        "shift_d": 0,
        "alt_d": 0,
        "merge": 0,
    }
    _uv_action_pending = 0
    DEBUG_UV_PENDING = 0

    return ",".join(str(v) for v in record)


def write_log_row(force=False):
    row = collect_data(force=force)
    if row:
        append_csv(row)
        remove_duplicate_rows()
        import_csv_to_blend()


def logger_timer():
    global _force_log_pending

    if not timer_running:
        return None

    if _force_log_pending:
        _force_log_pending = False
        write_log_row(force=True)
    else:
        write_log_row(force=False)

    return 0.25


# =======================================================
# KEYMAPS
# =======================================================

def register_keymaps():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon

    if not kc:
        return

    km = kc.keymaps.new(name="Object Mode", space_type="EMPTY")
    kmi = km.keymap_items.new("object.duplicate_logger", 'D', 'PRESS', shift=True)
    addon_keymaps.append((km, kmi))

    kmi = km.keymap_items.new("object.duplicate_linked_logger", 'D', 'PRESS', alt=True)
    addon_keymaps.append((km, kmi))

    km = kc.keymaps.new(name="Mesh", space_type="EMPTY")
    kmi = km.keymap_items.new("mesh.duplicate_logger", 'D', 'PRESS', shift=True)
    addon_keymaps.append((km, kmi))

    km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
    kmi = km.keymap_items.new("view3d.paste_logger", 'V', 'PRESS', ctrl=True)
    addon_keymaps.append((km, kmi))


def unregister_keymaps():
    for km, kmi in addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    addon_keymaps.clear()


# =======================================================
# CONSENTIMIENTO / AUTORUN
# =======================================================

def get_consent_textblock():
    if "consent_flag" not in bpy.data.texts:
        txt = bpy.data.texts.new("consent_flag")
    else:
        txt = bpy.data.texts["consent_flag"]

    txt.use_fake_user = True
    txt.use_module = False
    txt.filepath = ""
    return txt


class DATA_LOGGER_OT_ConsentPopup(bpy.types.Operator):
    bl_idname = "wm.data_logger_consent"
    bl_label = "Consentimiento de recopilación de datos"

    def execute(self, context):
        consent_text = get_consent_textblock()
        consent_text.clear()
        consent_text.write("ACCEPTED")
        consent_text.use_fake_user = True
        start_logger()
        self.report({'INFO'}, "Consentimiento aceptado.")
        return {'FINISHED'}

    def cancel(self, context):
        bpy.ops.wm.data_logger_consent('INVOKE_DEFAULT')
        return {'CANCELLED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=430)

    def draw(self, context):
        layout = self.layout
        layout.label(text="¿Aceptas la recopilación de datos técnicos?")
        layout.label(text="(Transformaciones, UV, duplicados, modificadores, etc.)")
        layout.label(text="Debes guardar el .blend para recordar este consentimiento.")


class DATA_LOGGER_OT_AutoRunWarning(bpy.types.Operator):
    bl_idname = "wm.data_logger_autorun_warning"
    bl_label = "Auto Run desactivado"
    _timer = None

    def modal(self, context, event):
        if bpy.context.preferences.filepaths.use_scripts_auto_execute:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)
            bpy.ops.wm.data_logger_consent('INVOKE_DEFAULT')
            return {'FINISHED'}
        return {'PASS_THROUGH'}

    def execute(self, context):
        bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        return {'CANCELLED'}

    def invoke(self, context, event):
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        wm.modal_handler_add(self)
        return wm.invoke_props_dialog(self, width=450)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Auto Run no está activado.", icon='ERROR')
        layout.separator()
        layout.label(text="Edit → Preferences → File Paths → Auto Run Python Scripts")
        layout.separator()
        layout.label(text="Esta ventana permanecerá abierta hasta que lo actives.")


@persistent
def check_consent_on_load(dummy):
    prefs = bpy.context.preferences.filepaths

    if not prefs.use_scripts_auto_execute:
        bpy.app.timers.register(
            lambda: bpy.ops.wm.data_logger_autorun_warning('INVOKE_DEFAULT'),
            first_interval=0.5
        )
        return

    consent_text = get_consent_textblock()
    if "ACCEPTED" in consent_text.as_string():
        start_logger()
    else:
        bpy.app.timers.register(
            lambda: bpy.ops.wm.data_logger_consent('INVOKE_DEFAULT'),
            first_interval=0.5
        )


# =======================================================
# HANDLERS
# =======================================================

@persistent
def handle_save(dummy):
    import_csv_to_blend()


# =======================================================
# PANEL Y EXPORT
# =======================================================

class DATA_LOGGER_PT_Panel(bpy.types.Panel):
    bl_label = "Data Logger"
    bl_idname = "DATA_LOGGER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Data Logger"

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Estado del logger:")
        box.label(text="Activo" if timer_running else "Detenido")

        button_text = "Stop Logger" if timer_running else "Start Logger"
        button_icon = "PAUSE" if timer_running else "PLAY"
        box.operator("wm.data_logger_toggle", text=button_text, icon=button_icon)

        layout.separator()
        layout.label(text="Exportar registros a CSV:")
        layout.operator("wm.data_logger_export_csv", icon="EXPORT")


class DATA_LOGGER_PT_DebugPanel(bpy.types.Panel):
    bl_label = "Data Logger Debug"
    bl_idname = "DATA_LOGGER_PT_debug_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Data Logger"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.label(text=f"Timer: {'ON' if timer_running else 'OFF'}")
        col.label(text=f"Last operator: {DEBUG_LAST_OPERATOR or '-'}")
        col.label(text=f"Last log reason: {DEBUG_LAST_LOG_REASON or '-'}")
        col.label(text=f"Last rebase: {DEBUG_LAST_REBASE_REASON or '-'}")
        col.separator()
        col.label(text=f"UV pending: {DEBUG_UV_PENDING}")
        col.label(text=f"UV hash changed: {DEBUG_UV_HASH_CHANGED}")
        col.separator()
        col.label(text=DEBUG_LAST_FLAGS)
        col.separator()
        col.label(text=f"Active object: {get_active_object_name() or '-'}")
        col.label(text=f"Mode: {bpy.context.mode}")


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
            self.report({'WARNING'}, "El CSV está vacío.")
            return {'CANCELLED'}

        if not content.endswith("\n"):
            content += "\n"

        directory = os.path.dirname(blend_path)
        filename = os.path.splitext(os.path.basename(blend_path))[0] + "_data.csv"
        csv_path = os.path.join(directory, filename)

        try:
            with open(csv_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
        except Exception as e:
            self.report({'ERROR'}, f"No se pudo guardar el CSV: {e}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Datos exportados correctamente: {csv_path}")
        return {'FINISHED'}


# =======================================================
# REGISTRO
# =======================================================

classes = [
    OBJECT_OT_duplicate_logger,
    MESH_OT_duplicate_logger,
    OBJECT_OT_duplicate_linked_logger,
    VIEW3D_OT_paste_logger,
    WM_OT_data_logger_toggle,
    DATA_LOGGER_OT_ConsentPopup,
    DATA_LOGGER_OT_AutoRunWarning,
    DATA_LOGGER_PT_Panel,
    DATA_LOGGER_PT_DebugPanel,
    DATA_LOGGER_OT_ExportCSV,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    register_keymaps()

    if check_consent_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(check_consent_on_load)

    if handle_save not in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.append(handle_save)

    if operator_tracker not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(operator_tracker)

    print("Data Logger cargado correctamente.")


def unregister():
    unregister_keymaps()

    if check_consent_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(check_consent_on_load)

    if handle_save in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(handle_save)

    if operator_tracker in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(operator_tracker)

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


if __name__ == "__main__":
    register()