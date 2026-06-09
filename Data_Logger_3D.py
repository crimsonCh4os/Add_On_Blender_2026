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

bl_info = {
    "name": "Data Logger 3D",
    "author": "Maria",
    "version": (1, 1, 2),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Data Logger",
    "category": "3D View",
}

import bpy
import bmesh
import time
import os
import tempfile
import hashlib
import uuid
import csv
import io
import math
import mathutils
from bpy.app.handlers import persistent


# PRIVACIDAD / IDENTIFICADORES

# Se genera un UUID aleatorio y se persiste dentro del .blend como Text Block.
USER_ID_TEXTBLOCK = "data_logger_user_id"
CONSENT_TEXTBLOCK = "consent_flag"
DATA_TEXTBLOCK = "data_log_internal.csv"
WARNINGS_TEXTBLOCK = "data_logger_warnings.txt"

SCHEMA_VERSION = "2"
LOGGER_VERSION = ".".join(str(v) for v in bl_info.get("version", (1, 1, 0)))
SESSION_ID = str(uuid.uuid4())

_WARNINGS = []
MAX_WARNINGS = 50

# UV coordinate hashing is disabled by default because continuous UV scanning in
# Edit Mode can slow down Blender and, in large scenes, may cause instability.
# UV-related UI/debug fields are kept for schema compatibility, but the logger
# will not compute the expensive UV hash unless this flag is set to True.
ENABLE_UV_CHANGE_TRACKING = False


def log_warning(context, exc=None):
    """Registra advertencias recuperables sin romper la sesión de Blender."""
    message = f"[Data Logger] {context}"
    if exc is not None:
        message += f": {type(exc).__name__}: {exc}"

    print(message)
    _WARNINGS.append(message)
    del _WARNINGS[:-MAX_WARNINGS]

    try:
        if WARNINGS_TEXTBLOCK in bpy.data.texts:
            txt = bpy.data.texts[WARNINGS_TEXTBLOCK]
        else:
            txt = bpy.data.texts.new(WARNINGS_TEXTBLOCK)
        txt.use_fake_user = True
        txt.use_module = False
        txt.filepath = ""
        txt.clear()
        txt.write("\n".join(_WARNINGS))
    except Exception as inner_exc:
        print(f"[Data Logger] Could not update {WARNINGS_TEXTBLOCK}: {inner_exc}")


def get_or_create_textblock(name):
    if name in bpy.data.texts:
        txt = bpy.data.texts[name]
    else:
        txt = bpy.data.texts.new(name)
    txt.use_fake_user = True
    txt.use_module = False
    txt.filepath = ""
    return txt


def get_or_create_user_id():
    txt = get_or_create_textblock(USER_ID_TEXTBLOCK)
    value = txt.as_string().strip()
    if value:
        return value

    new_id = str(uuid.uuid4())
    txt.clear()
    txt.write(new_id)
    txt.use_fake_user = True
    return new_id


def reset_user_id():
    txt = get_or_create_textblock(USER_ID_TEXTBLOCK)
    new_id = str(uuid.uuid4())
    txt.clear()
    txt.write(new_id)
    txt.use_fake_user = True
    return new_id


def clear_consent():
    if CONSENT_TEXTBLOCK in bpy.data.texts:
        bpy.data.texts.remove(bpy.data.texts[CONSENT_TEXTBLOCK])


def clear_logged_data():
    if DATA_TEXTBLOCK in bpy.data.texts:
        bpy.data.texts.remove(bpy.data.texts[DATA_TEXTBLOCK])
    if os.path.exists(TEMP_CSV_PATH):
        try:
            os.remove(TEMP_CSV_PATH)
        except Exception as exc:
            log_warning("Could not delete the temporary CSV", exc)



# ESTADO GLOBAL

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
prev_object_state = (0.0, 0.0, 0.0, 0.0)

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


# CSV

TEMP_CSV_PATH = os.path.join(tempfile.gettempdir(), "blender_data_log.csv")

CSV_HEADER_V1 = [
    "USER_ID", "TimeStamp", "Minute", "Second",
    "UserX", "UserY", "UserZ",
    "SceneRadius",
    "ObjX", "ObjY", "ObjZ", "ObjRadius",
    "ObjDeltaX", "ObjDeltaY", "ObjDeltaZ", "ObjDeltaRadius",
    "VertexDelta", "NgonDelta", "TriDelta", "NormalDelta",
    "ObjModeState", "EditModeState", "ModeChanged", "UV",
    "ObjectDelta", "ModifierDelta",
    "CtrlV", "ShiftD", "AltD", "Merge", "Occlusion"
]

CSV_HEADER = [
    "SchemaVersion", "LoggerVersion", "SessionID", "UserID",
    "TimeStamp", "Minute", "Second",
    "UserX", "UserY", "UserZ",
    "SceneRadius",
    "ObjX", "ObjY", "ObjZ", "ObjRadius",
    "ObjDeltaX", "ObjDeltaY", "ObjDeltaZ", "ObjDeltaRadius",
    "VertexDelta", "NgonDelta", "TriDelta", "NormalDelta",
    "ObjModeState", "EditModeState", "ModeChanged", "UV",
    "ObjectDelta", "ModifierDelta",
    "CtrlV", "ShiftD", "AltD", "Merge", "Occlusion"
]


def detect_csv_schema(header):
    normalized = [str(h).strip().lstrip("\ufeff") for h in header]
    if "SchemaVersion" in normalized:
        return 2
    if "USER_ID" in normalized:
        return 1
    return 0


def upgrade_csv_content_to_v2(content):
    """Convierte contenido CSV v1 a v2. Si ya es v2, lo devuelve normalizado."""
    if not content.strip():
        return ",".join(CSV_HEADER) + "\n"

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return ",".join(CSV_HEADER) + "\n"

    schema = detect_csv_schema(reader.fieldnames)
    if schema == 2:
        return content if content.endswith("\n") else content + "\n"

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=CSV_HEADER, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()

    if schema == 1:
        for row in reader:
            new_row = {key: row.get(key, "") for key in CSV_HEADER}
            new_row["SchemaVersion"] = "1"
            new_row["LoggerVersion"] = ""
            new_row["SessionID"] = ""
            new_row["UserID"] = row.get("USER_ID", "")
            writer.writerow(new_row)

    return out.getvalue()


def strip_user_id_from_csv(content):
    """Devuelve una copia del CSV sin identificador de usuario para exportaciones anonimizadas."""
    if not content.strip():
        return content
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return content
    fieldnames = [f for f in reader.fieldnames if f not in {"UserID", "USER_ID"}]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in reader:
        writer.writerow(row)
    return out.getvalue()


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

    text_name = DATA_TEXTBLOCK
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
    if DATA_TEXTBLOCK not in bpy.data.texts:
        return False

    content = bpy.data.texts[DATA_TEXTBLOCK].as_string()
    if not content.strip():
        return False

    content = upgrade_csv_content_to_v2(content)

    with open(TEMP_CSV_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    ensure_file_ends_with_newline(TEMP_CSV_PATH)
    return True

# UTILIDADES

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
    except Exception as exc:
        log_warning("Could not get the camera position", exc)

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
        except Exception as exc:
            log_warning(f"Could not calculate scene radius for {getattr(o, 'name', '?')}", exc)
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
    except Exception as exc:
        log_warning("Could not count inverted normals in Object Mode", exc)
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
            except Exception as exc:
                log_warning("Could not evaluate a face in Edit Mode", exc)
        return total
    except Exception as exc:
        log_warning("Could not count inverted normals in Edit Mode", exc)
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
        except Exception as exc:
            log_warning("Could not get mesh statistics in Edit Mode", exc)

    try:
        verts = len(obj.data.vertices)
        ngons = sum(1 for p in obj.data.polygons if len(p.vertices) > 4)
        tris = sum(1 for p in obj.data.polygons if len(p.vertices) == 3)
        inverted = count_inverted_normals_object_mode(obj)
        return (verts, ngons, tris, inverted)
    except Exception as exc:
        log_warning("Could not get mesh statistics in Object Mode", exc)
        return (0, 0, 0, 0)


def get_global_uv_hash():
    if not ENABLE_UV_CHANGE_TRACKING:
        return "UV_TRACKING_DISABLED"

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

        except Exception as exc:
            log_warning(f"Could not calculate UV hash for {getattr(obj, 'name', '?')}", exc)
            chunks.append((obj.name, "UV_ERROR"))

    return hashlib.sha256(str(chunks).encode()).hexdigest()

def get_occlusion_state():
    try:
        for area in bpy.context.screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces.active

                # Wireframe
                is_wireframe = (space.shading.type == 'WIREFRAME')

                # X-Ray
                is_xray = bool(space.shading.show_xray)

                return int(is_wireframe or is_xray)
    except Exception as exc:
        log_warning("Could not read occlusion state", exc)

    return 0

# DETECCIÓN DE OPERADORES

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

    if not ENABLE_UV_CHANGE_TRACKING:
        _uv_action_pending = 0
        DEBUG_UV_PENDING = 0
        return False

    _uv_action_pending = 1
    _uv_last_action_time = time.time()
    DEBUG_UV_PENDING = 1
    return True


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

    if op in UV_DEPLOY_OPS or op in UV_ASSOCIATED_OPS or op.startswith("uv."):
        if mark_uv_pending():
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
            except Exception as exc:
                log_warning("Could not read a recent operator", exc)
                continue

            if detect_flags_from_operator(bl_id):
                changed = True

        _last_operator_index = count
    except Exception as exc:
        log_warning("Could not process new operators", exc)
        return False

    return changed


@persistent
def operator_tracker(scene, depsgraph):
    if process_new_operators():
        force_log_soon()


# WRAPPER SOLO PARA CTRL+V

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
            self.report({'WARNING'}, f"Could not paste from the clipboard: {e}")
            return {'CANCELLED'}


# SNAPSHOT DE ESTADO

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
        "occlusion": get_occlusion_state(),
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
        snapshot["occlusion"],
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
    global prev_object_state

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
    prev_object_state = snapshot["object"]


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
    except Exception as exc:
        log_warning("Could not initialize the operator index", exc)
        _last_operator_index = 0

# CONTROL LOGGER

def has_accepted_consent():
    """Comprueba el consentimiento sin crear el Text Block si no existe."""
    if CONSENT_TEXTBLOCK not in bpy.data.texts:
        return False
    return "ACCEPTED" in bpy.data.texts[CONSENT_TEXTBLOCK].as_string()


def should_prompt_for_consent_on_load():
    """Solo pedimos consentimiento al abrir un archivo .blend real.

    Esto evita que el popup aparezca al instalar o activar el addon en Blender.
    El flujo previsto es: instalar addon -> guardar .blend -> cerrar -> reabrir -> mostrar consentimiento.
    """
    return bool(bpy.data.filepath) and not has_accepted_consent()


def request_consent_popup(delay=0.5, only_if_saved_file=False):
    """Muestra el consentimiento de forma diferida para que Blender ya tenga ventana activa."""
    def _show():
        if only_if_saved_file and not should_prompt_for_consent_on_load():
            return None

        if not has_accepted_consent() and not timer_running:
            try:
                bpy.ops.wm.data_logger_consent('INVOKE_DEFAULT')
            except Exception as exc:
                log_warning("Could not show the consent dialog", exc)
        return None

    bpy.app.timers.register(_show, first_interval=delay)


def start_logger():
    global timer_running
    global start_time

    # Bloqueo de seguridad: aunque alguien llame a start_logger() directamente,
    # no se inicia la captura sin consentimiento aceptado.
    if not has_accepted_consent():
        print("Data Logger blocked: consent is required before starting.")
        request_consent_popup()
        return

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
    print("Data Logger started.")


def stop_logger():
    global timer_running
    timer_running = False
    if has_accepted_consent():
        import_csv_to_blend()
    print("Data Logger stopped.")


def hard_stop_logger_on_file_load():
    """Detiene cualquier temporizador anterior al abrir otro .blend.

    Evita que una sesión que estaba grabando en otro archivo siga escribiendo
    en el archivo recién abierto antes de que se confirme el consentimiento.
    """
    global timer_running, start_time, _force_log_pending
    timer_running = False
    start_time = None
    _force_log_pending = False


class WM_OT_data_logger_toggle(bpy.types.Operator):
    bl_idname = "wm.data_logger_toggle"
    bl_label = "Start / Stop Logger"

    def execute(self, context):
        if timer_running:
            stop_logger()
            self.report({'INFO'}, "Logger stopped.")
            return {'FINISHED'}

        # No se permite iniciar la captura sin consentimiento aceptado.
        if not has_accepted_consent():
            bpy.ops.wm.data_logger_consent('INVOKE_DEFAULT')
            self.report({'WARNING'}, "Consent is required before starting the logger.")
            return {'CANCELLED'}

        start_logger()
        self.report({'INFO'}, "Logger started.")
        return {'FINISHED'}


# DATA COLLECTION

def collect_data(force=False):
    global _last_timestamp
    global prev_mode, prev_active_object_name, prev_object_state
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

    ox, oy, oz, orad = snapshot["object"]
    prev_ox, prev_oy, prev_oz, prev_orad = prev_object_state

    # Si cambia el objeto activo, no mezclamos deltas de transformación entre objetos distintos.
    if active_object_changed:
        obj_dx = 0.0
        obj_dy = 0.0
        obj_dz = 0.0
        obj_drad = 0.0
    else:
        obj_dx = ox - prev_ox
        obj_dy = oy - prev_oy
        obj_dz = oz - prev_oz
        obj_drad = orad - prev_orad

    # Solo rebaseamos por cambio de modo.
    if mode_changed_now:
        reasons = ["mode_change"]
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

        record = trunc_all([
            SCHEMA_VERSION, LOGGER_VERSION, SESSION_ID, get_or_create_user_id(),
            timestamp, minute, second,
            user[0], user[1], user[2],
            snapshot["scene_radius"],
            ox, oy, oz, orad,
            0, 0, 0, 0,
            0, 0, 0, 0,
            obj_mode_state, edit_mode_state, mode_changed, uv_action,
            0, 0,
            operator_flags["ctrl_v"],
            operator_flags["shift_d"],
            operator_flags["alt_d"],
            operator_flags["merge"],
            snapshot["occlusion"],
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
        SCHEMA_VERSION, LOGGER_VERSION, SESSION_ID, get_or_create_user_id(),
        timestamp, minute, second,
        user[0], user[1], user[2],
        snapshot["scene_radius"],
        ox, oy, oz, orad,
        obj_dx, obj_dy, obj_dz, obj_drad,
        v_delta, n_delta, t_delta, normal_delta,
        obj_mode_state, edit_mode_state, mode_changed, uv_action,
        obj_delta, mod_delta,
        operator_flags["ctrl_v"],
        operator_flags["shift_d"],
        operator_flags["alt_d"],
        operator_flags["merge"],
        snapshot["occlusion"],
    ])

    reasons = []
    if state_changed:
        reasons.append("state_changed")
    if active_object_changed:
        reasons.append("active_object_change")
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
    if obj_dx or obj_dy or obj_dz or obj_drad:
        reasons.append("object_transform")

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


# KEYMAPS

def register_keymaps():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon

    if not kc:
        return

    # Recuperamos el comportamiento normal de Shift+D y Alt+D:
    # no los sobreescribimos. Se detectan por operator_tracker().
    km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
    kmi = km.keymap_items.new("view3d.paste_logger", 'V', 'PRESS', ctrl=True)
    addon_keymaps.append((km, kmi))


def unregister_keymaps():
    for km, kmi in addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception as exc:
            log_warning("Could not remove a logger keymap", exc)
    addon_keymaps.clear()


# CONSENTIMIENTO / AUTORUN

def get_consent_textblock():
    return get_or_create_textblock(CONSENT_TEXTBLOCK)


class DATA_LOGGER_OT_ConsentPopup(bpy.types.Operator):
    bl_idname = "wm.data_logger_consent"
    bl_label = "Data Collection Consent"

    def execute(self, context):
        consent_text = get_consent_textblock()
        consent_text.clear()
        consent_text.write("ACCEPTED")
        consent_text.use_fake_user = True
        start_logger()
        self.report({'INFO'}, "Consent accepted.")
        return {'FINISHED'}

    def cancel(self, context):
        # Si el usuario cancela, no se guarda consentimiento
        # y no se inicia la captura.
        clear_consent()
        self.report({'INFO'}, "Consent cancelled. Logger not started.")
        return {'CANCELLED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=430)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Do you accept technical data collection?")
        layout.label(text="(Transforms, duplicates, modifiers, etc.)")
        layout.label(text="Save the .blend file to remember this consent.")


class DATA_LOGGER_OT_AutoRunWarning(bpy.types.Operator):
    bl_idname = "wm.data_logger_autorun_warning"
    bl_label = "Auto Run Disabled"
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
        layout.label(text="Auto Run is not enabled.", icon='ERROR')
        layout.separator()
        layout.label(text="Edit → Preferences → File Paths → Auto Run Python Scripts")
        layout.separator()
        layout.label(text="This window will stay open until you enable it.")


@persistent
def check_consent_on_load(dummy):
    # Al abrir un .blend se corta cualquier captura anterior antes de decidir
    # si este archivo tiene consentimiento.
    hard_stop_logger_on_file_load()

    # No mostrar nada al instalar/activar el addon ni en el archivo inicial sin guardar.
    # El consentimiento se pide únicamente al abrir un .blend guardado.
    if not bpy.data.filepath:
        return

    prefs = bpy.context.preferences.filepaths

    if not prefs.use_scripts_auto_execute:
        bpy.app.timers.register(
            lambda: bpy.ops.wm.data_logger_autorun_warning('INVOKE_DEFAULT'),
            first_interval=0.5
        )
        return

    if has_accepted_consent():
        start_logger()
    else:
        request_consent_popup(delay=0.5, only_if_saved_file=True)


# HANDLERS

@persistent
def handle_save(dummy):
    import_csv_to_blend()


# PANEL Y EXPORT

class DATA_LOGGER_PT_Panel(bpy.types.Panel):
    bl_label = "Data Logger"
    bl_idname = "DATA_LOGGER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Data Logger"

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Logger status:")
        box.label(text="Running" if timer_running else "Stopped")

        button_text = "Stop Logger" if timer_running else "Start Logger"
        button_icon = "PAUSE" if timer_running else "PLAY"
        box.operator("wm.data_logger_toggle", text=button_text, icon=button_icon)

        layout.separator()
        layout.label(text="Export logs to CSV:")
        layout.operator("wm.data_logger_export_csv", icon="EXPORT")
        layout.operator("wm.data_logger_export_csv_anonymous", icon="EXPORT")

        layout.separator()
        layout.label(text="Privacy:")
        layout.operator("wm.data_logger_reset_user_id", icon="FILE_REFRESH")
        layout.operator("wm.data_logger_clear_consent", icon="X")
        layout.operator("wm.data_logger_clear_logged_data", icon="TRASH")


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
        col.label(text=f"UV tracking: {'ON' if ENABLE_UV_CHANGE_TRACKING else 'OFF'}")
        col.label(text=f"UV pending: {DEBUG_UV_PENDING}")
        col.label(text=f"UV hash changed: {DEBUG_UV_HASH_CHANGED}")
        col.separator()
        col.label(text=DEBUG_LAST_FLAGS)
        col.separator()
        col.label(text=f"Active object: {get_active_object_name() or '-'}")
        col.label(text=f"Mode: {bpy.context.mode}")
        col.separator()
        col.label(text="Latest warnings:")
        for warning in _WARNINGS[-5:]:
            col.label(text=warning[:90])


def _export_csv_content(context, operator, anonymize=False):
    blend_path = bpy.data.filepath

    if not blend_path:
        operator.report({'ERROR'}, "Save the .blend file before exporting.")
        return {'CANCELLED'}

    if DATA_TEXTBLOCK not in bpy.data.texts:
        operator.report({'ERROR'}, "There is no embedded CSV to export.")
        return {'CANCELLED'}

    content = bpy.data.texts[DATA_TEXTBLOCK].as_string()
    if not content.strip():
        operator.report({'WARNING'}, "The CSV is empty.")
        return {'CANCELLED'}

    content = upgrade_csv_content_to_v2(content)
    if anonymize:
        content = strip_user_id_from_csv(content)

    directory = os.path.dirname(blend_path)
    suffix = "_data_anon.csv" if anonymize else "_data.csv"
    filename = os.path.splitext(os.path.basename(blend_path))[0] + suffix
    csv_path = os.path.join(directory, filename)

    try:
        with open(csv_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    except Exception as exc:
        log_warning("Could not save the exported CSV", exc)
        operator.report({'ERROR'}, f"Could not save the CSV: {exc}")
        return {'CANCELLED'}

    operator.report({'INFO'}, f"Data exported successfully: {csv_path}")
    return {'FINISHED'}


class DATA_LOGGER_OT_ExportCSV(bpy.types.Operator):
    bl_idname = "wm.data_logger_export_csv"
    bl_label = "Export to CSV"

    def execute(self, context):
        return _export_csv_content(context, self, anonymize=False)


class DATA_LOGGER_OT_ExportCSVAnonymous(bpy.types.Operator):
    bl_idname = "wm.data_logger_export_csv_anonymous"
    bl_label = "Export CSV without UserID"

    def execute(self, context):
        return _export_csv_content(context, self, anonymize=True)


class DATA_LOGGER_OT_ResetUserID(bpy.types.Operator):
    bl_idname = "wm.data_logger_reset_user_id"
    bl_label = "Regenerate UserID"

    def execute(self, context):
        new_id = reset_user_id()
        self.report({'INFO'}, f"New UserID generated: {new_id[:8]}...")
        return {'FINISHED'}


class DATA_LOGGER_OT_ClearConsent(bpy.types.Operator):
    bl_idname = "wm.data_logger_clear_consent"
    bl_label = "Clear Consent"

    def execute(self, context):
        clear_consent()
        self.report({'INFO'}, "Consent cleared.")
        return {'FINISHED'}


class DATA_LOGGER_OT_ClearLoggedData(bpy.types.Operator):
    bl_idname = "wm.data_logger_clear_logged_data"
    bl_label = "Clear Embedded Data"

    def execute(self, context):
        clear_logged_data()
        self.report({'INFO'}, "Logger data cleared.")
        return {'FINISHED'}


# REGISTRO

classes = [
    VIEW3D_OT_paste_logger,
    WM_OT_data_logger_toggle,
    DATA_LOGGER_OT_ConsentPopup,
    DATA_LOGGER_OT_AutoRunWarning,
    DATA_LOGGER_PT_Panel,
    DATA_LOGGER_PT_DebugPanel,
    DATA_LOGGER_OT_ExportCSV,
    DATA_LOGGER_OT_ExportCSVAnonymous,
    DATA_LOGGER_OT_ResetUserID,
    DATA_LOGGER_OT_ClearConsent,
    DATA_LOGGER_OT_ClearLoggedData,
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

    # No llamamos a check_consent_on_load() durante register().
    # Así, al instalar o activar el addon no aparece el consentimiento todavía.
    # El popup se mostrará en load_post, es decir, al volver a abrir un .blend guardado.

    print("Data Logger loaded successfully.")


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
        except Exception as exc:
            log_warning(f"Could not unregister class {getattr(cls, '__name__', cls)}", exc)


if __name__ == "__main__":
    register()