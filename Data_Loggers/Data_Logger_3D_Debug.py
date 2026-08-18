# Tools for monitoring and analyzing 3D modeling workflows in Blender
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
    "version": (1, 6, 0),
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
import json
import mathutils
from bpy.app.handlers import persistent



# LOCALIZATION

TRANSLATIONS = {
    "en": {
        "language": "Language", "english": "English", "spanish": "Spanish",
        "title": "Data Logger 3D", "help": "Open detailed help",
        "status": "Logger status:", "running": "Running", "stopped": "Stopped",
        "start": "Start Logger", "stop": "Stop Logger",
        "export": "Export logs to CSV:", "export_csv": "Export to CSV",
        "export_anon": "Export CSV without UserID", "privacy": "Privacy:",
        "reset_id": "Regenerate UserID", "clear_consent": "Clear Consent",
        "clear_data": "Clear Embedded Data", "debug": "Data Logger Debug",
        "timer": "Timer", "last_operator": "Last operator",
        "last_reason": "Last log reason", "last_rebase": "Last rebase",
        "uv_tracking": "UV tracking", "uv_pending": "UV pending",
        "uv_changed": "UV hash changed", "active_object": "Active object",
        "mode": "Mode", "warnings": "Latest warnings:",
        "help_title": "Data Logger 3D — Detailed Help",
        "help_intro": "Records supported Blender workflow events and embeds the log in the .blend file.",
        "help_save": "Ctrl+S: before saving, temporarily combines all geometry except cameras and lights, calculates one set of mesh metrics, restores the scene unchanged, and embeds the result as data_logger_mesh_metrics.csv.",
        "help_metrics": "Metrics: UV area, UV islands, UV stretch, relative UV density that updates when UV islands are scaled, inverted normals, transforms, origin position, non-quads, duplicate vertices, face count, connected components, faces per component, and mean face angle. Similarity is not calculated.",
        "help_privacy": "Pressing Start Logger records consent directly without a popup. UserID can be regenerated and exports can omit it.",
        "help_manual_start": "Recording starts only when Start Logger is pressed. No consent dialog is shown.",
        "close": "Close",
    },
    "es": {
        "language": "Idioma", "english": "Inglés", "spanish": "Español",
        "title": "Data Logger 3D", "help": "Abrir ayuda detallada",
        "status": "Estado del registro:", "running": "En ejecución", "stopped": "Detenido",
        "start": "Iniciar registro", "stop": "Detener registro",
        "export": "Exportar registros a CSV:", "export_csv": "Exportar a CSV",
        "export_anon": "Exportar CSV sin UserID", "privacy": "Privacidad:",
        "reset_id": "Regenerar UserID", "clear_consent": "Borrar consentimiento",
        "clear_data": "Borrar datos incrustados", "debug": "Depuración de Data Logger",
        "timer": "Temporizador", "last_operator": "Último operador",
        "last_reason": "Último motivo de registro", "last_rebase": "Último reajuste",
        "uv_tracking": "Seguimiento UV", "uv_pending": "UV pendiente",
        "uv_changed": "Hash UV modificado", "active_object": "Objeto activo",
        "mode": "Modo", "warnings": "Últimos avisos:",
        "help_title": "Data Logger 3D — Ayuda detallada",
        "help_intro": "Registra eventos compatibles del flujo de trabajo de Blender e incrusta el registro en el archivo .blend.",
        "help_save": "Ctrl+S: antes de guardar, combina temporalmente toda la geometría excepto cámaras y luces, calcula un único conjunto de métricas, restaura la escena sin cambios e incrusta el resultado como data_logger_mesh_metrics.csv.",
        "help_metrics": "Métricas: área UV, islas UV, estiramiento UV, densidad UV relativa que se actualiza al escalar las islas UV, normales invertidas, transformaciones, posición en el origen, no-quads, vértices duplicados, caras, componentes conectados, caras por componente y ángulo medio entre caras. No se calcula similitud.",
        "help_privacy": "Pulsar Start Logger registra el consentimiento directamente sin mostrar un popup. El UserID puede regenerarse y las exportaciones pueden omitirlo.",
        "help_manual_start": "La grabación solo comienza al pulsar Start Logger. No se muestra ningún diálogo de consentimiento.",
        "close": "Cerrar",
    },
}

def current_language(context=None):
    scene = getattr(context, "scene", None) if context else getattr(bpy.context, "scene", None)
    return getattr(scene, "data_logger_language", "en") if scene else "en"

def tr(key, context=None):
    language = current_language(context)
    return TRANSLATIONS.get(language, TRANSLATIONS["en"]).get(key, key)


# PRIVACY / IDENTIFIERS

# A random UUID is generated and stored inside the .blend file as a Text Block.
USER_ID_TEXTBLOCK = "data_logger_user_id"
CONSENT_TEXTBLOCK = "consent_flag"

# Internal developer switch. This is intentionally not exposed in Blender UI.
# True: keep the current consent workflow and automatic restart on file load.
# False: disable consent popups/UI and allow recording only after pressing Start Logger.
ENABLE_CONSENT_FLOW = False
DATA_TEXTBLOCK = "data_log_internal.csv"
WARNINGS_TEXTBLOCK = "data_logger_warnings.txt"
LEGACY_MESH_METRICS_JSON_TEXTBLOCK = "data_logger_mesh_metrics.json"
MESH_METRICS_CSV_TEXTBLOCK = "data_logger_mesh_metrics.csv"

SCHEMA_VERSION = "2"
LOGGER_VERSION = ".".join(str(v) for v in bl_info.get("version", (1, 1, 0)))
SESSION_ID = str(uuid.uuid4())

_WARNINGS = []
MAX_WARNINGS = 50

# UV tracking uses a topology-only signature. It ignores UV coordinates, so
# moving, rotating, scaling, relaxing, stitching or packing UV islands does not create rows.
# The signature changes only when mesh topology, seams, or UV-layer presence change.
ENABLE_UV_CHANGE_TRACKING = True


def log_warning(context, exc=None):
    """Log recoverable warnings without interrupting the Blender session."""
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



# GLOBAL STATE

timer_running = False
start_time = None
_baseline_ready = False
LOGGER_INITIAL_DELAY = 1.0
LOGGER_POLL_INTERVAL = 0.15
LOGGER_IDLE_FULL_CHECK_INTERVAL = 5.0

# Fixed recording indicator shown in Blender's top bar.

_last_timestamp = -1.0
_force_log_pending = False
_last_lightweight_signature = None
_last_idle_full_check = 0.0
_last_operator_index = 0

prev_vert_count = 0
prev_ngon_count = 0
prev_tri_count = 0
prev_inverted_normals = 0
prev_object_count = 0
prev_total_mods = 0
prev_mode = None
prev_geometry_hash = ""
prev_uv_coordinate_hash = ""
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

# Internal developer switch. It is intentionally not exposed in Blender UI.
# True: show the Debug panel. False: keep it completely hidden.
SHOW_DEBUG_PANEL = True

DEBUG_ENABLED = True
DEBUG_LAST_OPERATOR = ""
DEBUG_LAST_LOG_REASON = ""
DEBUG_LAST_REBASE_REASON = ""
DEBUG_UV_HASH_CHANGED = 0
DEBUG_UV_PENDING = 0
DEBUG_LAST_FLAGS = "CtrlV=0 ShiftD=0 AltD=0 Merge=0"
_uv_transform_pending = False


# CSV

TEMP_CSV_PATH = os.path.join(tempfile.gettempdir(), "blender_data_log.csv")
TEMP_MESH_METRICS_CSV_PATH = os.path.join(tempfile.gettempdir(), "blender_mesh_metrics.csv")

CSV_HEADER_V1 = [
    "USER_ID", "TimeStamp", "Minute", "Second",
    "UserX", "UserY", "UserZ",
    "SceneRadius",
    "ObjX", "ObjY", "ObjZ", "ObjRadius",
    "ObjDeltaX", "ObjDeltaY", "ObjDeltaZ", "ObjDeltaRadius",
    "VertexDelta", "NgonDelta", "TriDelta", "NormalDelta",
    "ObjModeState", "EditModeState", "ModeChanged", "UVCoordinateHash",
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
    "ObjModeState", "EditModeState", "ModeChanged", "UVCoordinateHash",
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
    """Convert CSV v1 content to v2. If it is already v2, return normalized content."""
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
    """Return a copy of the CSV without the user identifier for anonymized exports."""
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

# UTILITIES

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


def tag_blender_bars_for_redraw():
    """Redraw Blender bars so the recording indicator updates immediately."""
    try:
        wm = bpy.context.window_manager
        for window in wm.windows:
            screen = window.screen
            if screen is None:
                continue
            for area in screen.areas:
                if area.type in {'TOPBAR', 'STATUSBAR'}:
                    area.tag_redraw()
    except Exception as exc:
        log_warning("Could not redraw the recording indicator", exc)


def draw_recording_indicator(self, context):
    """Draw one red REC badge only in the right side of Blender's top bar."""
    if not timer_running:
        return

    # TOPBAR_HT_upper_bar is drawn once for each top-bar region. Restrict the
    # callback to the right-aligned region so the REC badge is not duplicated
    # on the left side.
    region = getattr(context, "region", None)
    if region is None or getattr(region, "alignment", "") != "RIGHT":
        return

    row = self.layout.row(align=True)
    row.alert = True
    row.label(text="REC", icon='REC')


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


def get_global_geometry_hash():
    """Hash actual 3D mesh geometry, excluding UV coordinates.

    This lets the logger distinguish a UV vertex move from a real mesh vertex
    move even when Blender reports both operations as transform.translate.
    """
    chunks = []

    for obj in sorted(
        (o for o in bpy.context.scene.objects if o.type == "MESH"),
        key=lambda o: o.name,
    ):
        try:
            mode = safe_mode_of_object(obj)

            if mode == "EDIT":
                bm = bmesh.from_edit_mesh(obj.data)
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()

                vertices = tuple(
                    (
                        vert.index,
                        round(float(vert.co.x), 5),
                        round(float(vert.co.y), 5),
                        round(float(vert.co.z), 5),
                    )
                    for vert in bm.verts
                )
                edges = tuple(sorted(
                    tuple(sorted(v.index for v in edge.verts))
                    for edge in bm.edges
                ))
                faces = tuple(sorted(
                    tuple(v.index for v in face.verts)
                    for face in bm.faces
                ))
            else:
                mesh = obj.data
                vertices = tuple(
                    (
                        vert.index,
                        round(float(vert.co.x), 5),
                        round(float(vert.co.y), 5),
                        round(float(vert.co.z), 5),
                    )
                    for vert in mesh.vertices
                )
                edges = tuple(sorted(
                    tuple(sorted(edge.vertices))
                    for edge in mesh.edges
                ))
                faces = tuple(sorted(
                    tuple(poly.vertices)
                    for poly in mesh.polygons
                ))

            chunks.append((
                obj.name,
                vertices,
                edges,
                faces,
            ))

        except Exception as exc:
            log_warning(
                f"Could not calculate geometry hash for "
                f"{getattr(obj, 'name', '?')}",
                exc,
            )
            chunks.append(
                (getattr(obj, "name", "?"), "GEOMETRY_HASH_ERROR")
            )

    return hashlib.sha256(
        repr(chunks).encode("utf-8")
    ).hexdigest()


def get_active_live_uv_positions():
    """Return a lightweight UV-event hash without reading every live UV coordinate.

    This avoids scanning the live Edit Mode BMesh after large UV transforms. The
    value is only an event fingerprint for the CSV row; it does not contain the
    user's UV coordinates.
    """
    obj = getattr(bpy.context, "edit_object", None)
    if obj is None:
        obj = getattr(bpy.context, "object", None)

    if obj is None or obj.type != "MESH":
        return ""

    try:
        if safe_mode_of_object(obj) == "EDIT":
            active_layer = obj.data.uv_layers.active
        else:
            active_layer = obj.data.uv_layers.active

        layer_name = active_layer.name if active_layer else "NO_UV"
        safe_object_name = obj.name.replace("|", "_").replace(";", "_").replace(",", "_")
        safe_layer_name = layer_name.replace("|", "_").replace(";", "_").replace(",", "_")

        event_payload = (
            safe_object_name,
            safe_layer_name,
            round(float(_uv_last_action_time), 3),
            DEBUG_LAST_OPERATOR,
            int(bool(_uv_action_pending)),
            int(bool(_uv_transform_pending)),
        )

        digest = hashlib.sha256(repr(event_payload).encode("utf-8")).hexdigest()
        return f"1"

    except Exception as exc:
        log_warning("Could not calculate lightweight UV event hash", exc)
        return ""


def get_global_uv_coordinate_hash():
    """Hash UV coordinates only.

    This hash never creates a row. It is used exclusively as a veto: when UV
    coordinates changed but the real 3D model did not, the event is ignored.
    """
    chunks = []

    for obj in sorted(
        (o for o in bpy.context.scene.objects if o.type == "MESH"),
        key=lambda o: o.name,
    ):
        try:
            mode = safe_mode_of_object(obj)

            if mode == "EDIT":
                bm = bmesh.from_edit_mesh(obj.data)
                uv_layer = bm.loops.layers.uv.active

                if uv_layer is None:
                    chunks.append((obj.name, "NO_UV"))
                    continue

                uv_values = []
                for face in bm.faces:
                    for loop in face.loops:
                        uv = loop[uv_layer].uv
                        uv_values.append((
                            round(float(uv.x), 6),
                            round(float(uv.y), 6),
                        ))

                chunks.append((obj.name, tuple(uv_values)))

            else:
                mesh = obj.data
                uv_layer = mesh.uv_layers.active

                if uv_layer is None:
                    chunks.append((obj.name, "NO_UV"))
                    continue

                uv_values = tuple(
                    (
                        round(float(item.uv.x), 6),
                        round(float(item.uv.y), 6),
                    )
                    for item in uv_layer.data
                )
                chunks.append((obj.name, uv_values))

        except Exception as exc:
            log_warning(
                f"Could not calculate UV coordinate hash for "
                f"{getattr(obj, 'name', '?')}",
                exc,
            )
            chunks.append(
                (getattr(obj, "name", "?"), "UV_COORDINATE_ERROR")
            )

    return hashlib.sha256(
        repr(chunks).encode("utf-8")
    ).hexdigest()


def get_global_uv_hash():
    """Return a coarse UV/topology signature.

    UV coordinates are intentionally ignored. Moving, rotating, scaling,
    relaxing, pinning, stitching or packing UVs will not change this hash.

    The hash changes only when:
    - mesh vertex/edge/face connectivity changes;
    - an edge seam flag changes;
    - a UV layer is created or removed.

    This is deliberately less precise to avoid false positives during ordinary
    UV editing.
    """
    if not ENABLE_UV_CHANGE_TRACKING:
        return "UV_TRACKING_DISABLED"

    chunks = []

    for obj in sorted(
        (o for o in bpy.context.scene.objects if o.type == "MESH"),
        key=lambda o: o.name,
    ):
        try:
            mode = safe_mode_of_object(obj)

            if mode == "EDIT":
                bm = bmesh.from_edit_mesh(obj.data)
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()

                has_uv_layer = int(bm.loops.layers.uv.active is not None)

                edges = tuple(sorted(
                    (
                        tuple(sorted(v.index for v in edge.verts)),
                        int(bool(edge.seam)),
                    )
                    for edge in bm.edges
                ))

                faces = tuple(sorted(
                    tuple(sorted(v.index for v in face.verts))
                    for face in bm.faces
                ))

                chunks.append((
                    obj.name,
                    len(bm.verts),
                    len(bm.edges),
                    len(bm.faces),
                    has_uv_layer,
                    edges,
                    faces,
                ))

            else:
                mesh = obj.data
                has_uv_layer = int(mesh.uv_layers.active is not None)

                edges = tuple(sorted(
                    (
                        tuple(sorted(edge.vertices)),
                        int(bool(edge.use_seam)),
                    )
                    for edge in mesh.edges
                ))

                faces = tuple(sorted(
                    tuple(sorted(poly.vertices))
                    for poly in mesh.polygons
                ))

                chunks.append((
                    obj.name,
                    len(mesh.vertices),
                    len(mesh.edges),
                    len(mesh.polygons),
                    has_uv_layer,
                    edges,
                    faces,
                ))

        except Exception as exc:
            log_warning(
                f"Could not calculate coarse UV topology hash for "
                f"{getattr(obj, 'name', '?')}",
                exc,
            )
            chunks.append(
                (getattr(obj, "name", "?"), "UV_TOPOLOGY_ERROR")
            )

    return hashlib.sha256(
        repr(chunks).encode("utf-8")
    ).hexdigest()


def get_realtime_mesh_stats_safe(obj):
    """Read mesh datablock only; never access edit-mode BMesh from the timer."""
    if obj is None or obj.type != "MESH":
        return (0, 0, 0, 0)
    try:
        mesh = obj.data
        verts = len(mesh.vertices)
        ngons = sum(1 for p in mesh.polygons if len(p.vertices) > 4)
        tris = sum(1 for p in mesh.polygons if len(p.vertices) == 3)
        inverted = count_inverted_normals_object_mode(obj)
        return (verts, ngons, tris, inverted)
    except Exception as exc:
        log_warning("Could not read safe real-time mesh statistics", exc)
        return (0, 0, 0, 0)


def get_realtime_geometry_hash_safe():
    """Stable hash for the live logger without bmesh.from_edit_mesh()."""
    chunks = []
    for obj in sorted((o for o in bpy.context.scene.objects if o.type == "MESH"), key=lambda o: o.name):
        try:
            mesh = obj.data
            vertices = tuple((v.index, round(float(v.co.x), 5), round(float(v.co.y), 5), round(float(v.co.z), 5)) for v in mesh.vertices)
            edges = tuple(tuple(e.vertices) for e in mesh.edges)
            faces = tuple(tuple(p.vertices) for p in mesh.polygons)
            chunks.append((obj.name, vertices, edges, faces))
        except Exception as exc:
            log_warning(f"Could not calculate safe geometry hash for {getattr(obj, 'name', '?')}", exc)
            chunks.append((getattr(obj, "name", "?"), "ERROR"))
    return hashlib.sha256(repr(chunks).encode("utf-8")).hexdigest()


def get_realtime_uv_coordinate_hash_safe():
    """Return a cheap UV-coordinate fingerprint for the timer.

    In Edit Mode this intentionally avoids reading every live UV coordinate,
    because large UV selections can make Blender unstable if the timer scans the
    edit BMesh while a transform is finishing. UV transforms are still detected
    through Blender's operator history and logged as UV actions.
    """
    hasher = hashlib.sha256()

    for obj in sorted((o for o in bpy.context.scene.objects if o.type == "MESH"), key=lambda o: o.name):
        try:
            layer = obj.data.uv_layers.active
            mode = safe_mode_of_object(obj)

            if layer is None:
                hasher.update(f"{obj.name}|NO_UV;".encode("utf-8"))
                continue

            if mode == "EDIT":
                # Do not scan live UV coordinates from the timer. Keep only a
                # structural fingerprint; the explicit UV operator flag records
                # the completed UV edit.
                hasher.update(
                    f"{obj.name}|EDIT|{layer.name}|{len(layer.data)};".encode("utf-8")
                )
                continue

            hasher.update(f"{obj.name}|OBJECT|{layer.name}|{len(layer.data)}|".encode("utf-8"))
            for item in layer.data:
                uv = item.uv
                hasher.update(f"{float(uv.x):.6f}:{float(uv.y):.6f};".encode("utf-8"))

        except Exception as exc:
            log_warning(f"Could not calculate safe UV coordinate hash for {getattr(obj, 'name', '?')}", exc)
            hasher.update(f"{getattr(obj, 'name', '?')}|ERROR;".encode("utf-8"))

    return hasher.hexdigest()


def get_realtime_uv_hash_safe():
    if not ENABLE_UV_CHANGE_TRACKING:
        return "UV_TRACKING_DISABLED"
    chunks = []
    for obj in sorted((o for o in bpy.context.scene.objects if o.type == "MESH"), key=lambda o: o.name):
        try:
            mesh = obj.data
            layer = mesh.uv_layers.active
            edges = tuple((tuple(e.vertices), int(bool(e.use_seam))) for e in mesh.edges)
            faces = tuple(tuple(sorted(p.vertices)) for p in mesh.polygons)
            chunks.append((obj.name, len(mesh.vertices), len(mesh.edges), len(mesh.polygons), int(layer is not None), edges, faces))
        except Exception as exc:
            log_warning(f"Could not calculate safe UV topology hash for {getattr(obj, 'name', '?')}", exc)
            chunks.append((getattr(obj, "name", "?"), "ERROR"))
    return hashlib.sha256(repr(chunks).encode("utf-8")).hexdigest()


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


# MESH METRICS ON SAVE

def _almost_equal_2d(v1, v2, tol=1e-4):
    return abs(v1.x - v2.x) <= tol and abs(v1.y - v2.y) <= tol


def _uv_polygon_area(uvs):
    if len(uvs) < 3:
        return 0.0
    area = 0.0
    for i in range(1, len(uvs) - 1):
        area += abs((uvs[i] - uvs[0]).cross(uvs[i + 1] - uvs[0])) * 0.5
    return area


def _count_uv_islands(bm, uv_layer):
    if uv_layer is None:
        return 0
    visited = set()
    islands = 0
    for face in bm.faces:
        if face.index in visited:
            continue
        stack = [face]
        while stack:
            current = stack.pop()
            if current.index in visited:
                continue
            visited.add(current.index)
            for edge in current.edges:
                for linked in edge.link_faces:
                    if linked.index in visited:
                        continue
                    connected = any(
                        _almost_equal_2d(loop_a[uv_layer].uv, loop_b[uv_layer].uv)
                        for loop_a in current.loops
                        for loop_b in linked.loops
                    )
                    if connected:
                        stack.append(linked)
        islands += 1
    return islands


def _normal_percentage(obj, bm):
    if not bm.faces:
        return 0.0
    check_bm = bm.copy()
    try:
        check_bm.normal_update()
        check_bm.faces.ensure_lookup_table()
        original = [face.normal.copy() for face in check_bm.faces]
        bmesh.ops.recalc_face_normals(check_bm, faces=list(check_bm.faces))
        check_bm.normal_update()
        flipped = sum(
            1 for old, face in zip(original, check_bm.faces)
            if old.dot(face.normal) < 0.0
        )
        return round(100.0 * flipped / len(check_bm.faces), 2)
    finally:
        check_bm.free()


def _mean_face_angle(bm):
    angles = []
    bm.normal_update()
    for edge in bm.edges:
        if edge.is_valid and len(edge.link_faces) == 2:
            try:
                angle = abs(math.degrees(edge.calc_face_angle()))
            except ValueError:
                continue
            if angle > 90.0:
                angle = 180.0 - angle
            angles.append(angle)
    return round(sum(angles) / len(angles), 2) if angles else 0.0


def _flush_edit_mesh_uv_data(obj):
    """Synchronize current Edit Mode geometry and UV loop data with the mesh datablock.

    UV transforms performed in the UV Editor live first in the edit BMesh. During
    save_pre, evaluated_get().to_mesh() can otherwise read the previous UV
    coordinates, making UV area and texel density appear unchanged.
    """
    if obj is None or obj.type != "MESH" or safe_mode_of_object(obj) != "EDIT":
        return

    try:
        bmesh.update_edit_mesh(
            obj.data,
            loop_triangles=False,
            destructive=False,
        )
    except Exception as exc:
        log_warning(
            f"Could not synchronize Edit Mode UV data for {getattr(obj, 'name', '?')}",
            exc,
        )

    try:
        obj.update_from_editmode()
        obj.data.update()
    except Exception as exc:
        log_warning(
            f"Could not update Edit Mode mesh data for {getattr(obj, 'name', '?')}",
            exc,
        )


def _mesh_bmesh_copy(obj):
    bm = bmesh.new()
    if safe_mode_of_object(obj) == "EDIT":
        _flush_edit_mesh_uv_data(obj)
        edit_bm = bmesh.from_edit_mesh(obj.data)
        bm.free()
        return edit_bm.copy()
    bm.from_mesh(obj.data)
    return bm


def calculate_mesh_metrics(obj):
    """Calculate Analysis3D mesh metrics, excluding similarity."""
    if obj is None or obj.type != "MESH":
        return {}

    bm = _mesh_bmesh_copy(obj)
    try:
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bm.normal_update()

        total_faces = len(bm.faces)
        total_verts = len(bm.verts)
        non_quads = round(
            100.0 * sum(1 for face in bm.faces if len(face.verts) != 4) / total_faces,
            2,
        ) if total_faces else 0.0

        merged = bm.copy()
        try:
            bmesh.ops.remove_doubles(merged, verts=list(merged.verts), dist=0.0001)
            duplicate_count = max(total_verts - len(merged.verts), 0)
        finally:
            merged.free()
        duplicate_percentage = round(
            100.0 * duplicate_count / total_verts, 2
        ) if total_verts else 0.0

        visited = set()
        parts = 0
        for face in bm.faces:
            if face.index in visited:
                continue
            stack = [face]
            while stack:
                current = stack.pop()
                if current.index in visited:
                    continue
                visited.add(current.index)
                for edge in current.edges:
                    stack.extend(
                        linked for linked in edge.link_faces
                        if linked.index not in visited
                    )
            parts += 1

        uv_layer = bm.loops.layers.uv.active
        uv_area = 0.0
        uv_islands = 0
        uv_stretch_values = []
        total_uv_area = 0.0
        total_3d_area = 0.0

        if uv_layer is not None:
            uv_islands = _count_uv_islands(bm, uv_layer)
            for face in bm.faces:
                verts = [loop.vert for loop in face.loops]
                uvs = [loop[uv_layer].uv.copy() for loop in face.loops]
                face_uv_area = _uv_polygon_area(uvs)
                face_3d_area = face.calc_area()
                uv_area += face_uv_area

                if face_3d_area > 1e-12 and face_uv_area > 0.0:
                    total_uv_area += face_uv_area
                    total_3d_area += face_3d_area

                scale_factor = (
                    math.sqrt(face_3d_area) / math.sqrt(face_uv_area)
                    if face_uv_area > 1e-8 else 1.0
                )
                edge_stretches = []
                for i, vert in enumerate(verts):
                    next_vert = verts[(i + 1) % len(verts)]
                    length_3d = (vert.co - next_vert.co).length
                    if length_3d <= 1e-5:
                        continue
                    uv_a = uvs[i] * scale_factor
                    uv_b = uvs[(i + 1) % len(uvs)] * scale_factor
                    edge_stretches.append(abs((uv_a - uv_b).length / length_3d - 1.0))
                if edge_stretches:
                    uv_stretch_values.append(sum(edge_stretches) / len(edge_stretches))

        uv_stretch = (
            round(sum(uv_stretch_values) / len(uv_stretch_values), 4)
            if uv_stretch_values else 0.0
        )
        uv_textel_density = (
            round(math.sqrt(total_uv_area / total_3d_area), 4)
            if total_uv_area > 0.0 and total_3d_area > 1e-12 else 0.0
        )

        transforms_applied = (
            all(abs(value - 1.0) <= 1e-5 for value in obj.scale)
            and all(abs(value) <= 1e-5 for value in obj.rotation_euler)
        )
        at_origin = all(abs(value) <= 1e-5 for value in obj.location)

        return {
            "UV_area": round(uv_area, 4),
            "UV_islands": int(uv_islands),
            "UV_stretch": uv_stretch,
            "UV_textel_density": uv_textel_density,
            "Normal_percentage": _normal_percentage(obj, bm),
            "Transformations": bool(transforms_applied),
            "Position": bool(at_origin),
            "Non_quads_percentage": non_quads,
            "Vertex_duplicate": int(duplicate_count),
            "Vertex_duplicate_percentage": duplicate_percentage,
            "N_faces": int(total_faces),
            "N_meshes": int(parts),
            "Face_by_mesh": round(total_faces / parts, 2) if parts else 0.0,
            "Angle": _mean_face_angle(bm),
        }
    finally:
        bm.free()


def _create_combined_scene_mesh_object():
    """Create one temporary world-space mesh from all convertible scene objects.

    Cameras and lights are excluded. Source objects are never selected, joined,
    converted, modified, or deleted. The temporary result is removed immediately
    after the metrics have been calculated, which is safer than invoking Undo from
    a save_pre handler and leaves the user's scene exactly as it was.
    """
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    combined_bm = bmesh.new()
    source_names = []

    try:
        for obj in sorted(scene.objects, key=lambda item: item.name):
            if obj.type in {'CAMERA', 'LIGHT'}:
                continue

            # Objects without renderable/convertible geometry (empties, speakers,
            # light probes, etc.) are ignored naturally.
            if obj.type not in {
                'MESH', 'CURVE', 'SURFACE', 'META', 'FONT',
                'CURVES', 'POINTCLOUD', 'VOLUME', 'GREASEPENCIL'
            }:
                continue

            temp_mesh = None
            evaluated_obj = None
            try:
                if obj.type == 'MESH' and safe_mode_of_object(obj) == 'EDIT':
                    # Synchronize current UV loop coordinates as well as geometry.
                    # update_from_editmode() alone can leave UV Editor transforms
                    # unavailable to the evaluated mesh during save_pre.
                    _flush_edit_mesh_uv_data(obj)
                    depsgraph.update()

                evaluated_obj = obj.evaluated_get(depsgraph)
                temp_mesh = evaluated_obj.to_mesh(
                    preserve_all_data_layers=True,
                    depsgraph=depsgraph,
                )
                if temp_mesh is None or len(temp_mesh.vertices) == 0:
                    continue

                before = len(combined_bm.verts)
                combined_bm.from_mesh(temp_mesh)
                combined_bm.verts.ensure_lookup_table()
                new_verts = list(combined_bm.verts[before:])
                if new_verts:
                    bmesh.ops.transform(
                        combined_bm,
                        matrix=obj.matrix_world,
                        verts=new_verts,
                    )
                source_names.append(obj.name)
            except Exception as exc:
                log_warning(f"Could not add {getattr(obj, 'name', '?')} to combined mesh", exc)
            finally:
                if evaluated_obj is not None and temp_mesh is not None:
                    try:
                        evaluated_obj.to_mesh_clear()
                    except Exception as exc:
                        log_warning(f"Could not clear temporary mesh for {getattr(obj, 'name', '?')}", exc)

        if not combined_bm.verts:
            combined_bm.free()
            return None, None, []

        combined_bm.verts.ensure_lookup_table()
        combined_bm.edges.ensure_lookup_table()
        combined_bm.faces.ensure_lookup_table()
        combined_bm.normal_update()

        combined_mesh = bpy.data.meshes.new("DataLogger_CombinedMesh_TEMP")
        combined_bm.to_mesh(combined_mesh)
        combined_bm.free()
        combined_bm = None
        combined_mesh.update()

        combined_obj = bpy.data.objects.new("DataLogger_CombinedScene_TEMP", combined_mesh)
        # Do not link it to a collection: calculations can use the datablock directly,
        # and an unlinked temporary object cannot affect the visible scene or selection.
        return combined_obj, combined_mesh, source_names
    except Exception:
        if combined_bm is not None:
            combined_bm.free()
        raise


def _remove_combined_scene_mesh_object(combined_obj, combined_mesh):
    """Delete the temporary calculation datablocks without touching scene objects."""
    try:
        if combined_obj is not None:
            bpy.data.objects.remove(combined_obj, do_unlink=True)
    except Exception as exc:
        log_warning("Could not remove temporary combined object", exc)
    try:
        if combined_mesh is not None and combined_mesh.name in bpy.data.meshes:
            bpy.data.meshes.remove(combined_mesh, do_unlink=True)
    except Exception as exc:
        log_warning("Could not remove temporary combined mesh", exc)


def save_scene_mesh_metrics():
    """Calculate one metric set from all scene geometry except cameras and lights."""
    objects = {}
    combined_obj = None
    combined_mesh = None
    source_names = []

    try:
        combined_obj, combined_mesh, source_names = _create_combined_scene_mesh_object()
        if combined_obj is None:
            objects["CombinedSceneMesh"] = {
                "error": "No convertible geometry found after excluding cameras and lights"
            }
        else:
            metrics = calculate_mesh_metrics(combined_obj)
            metrics["Source_object_count"] = len(source_names)
            metrics["Source_objects"] = source_names
            objects["CombinedSceneMesh"] = metrics
    except Exception as exc:
        log_warning("Could not calculate combined scene mesh metrics", exc)
        objects["CombinedSceneMesh"] = {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        _remove_combined_scene_mesh_object(combined_obj, combined_mesh)

    payload = {
        "schema_version": 2,
        "logger_version": LOGGER_VERSION,
        "saved_at_unix": round(time.time(), 3),
        "blend_file": bpy.data.filepath,
        "calculation_mode": "combined_scene_geometry",
        "excluded_object_types": ["CAMERA", "LIGHT"],
        "scene_restored": True,
        "objects": objects,
    }
    # Mesh metrics are stored only as CSV. Remove the legacy JSON text block so
    # old embedded data cannot be mistaken for the current export format.
    if LEGACY_MESH_METRICS_JSON_TEXTBLOCK in bpy.data.texts:
        bpy.data.texts.remove(bpy.data.texts[LEGACY_MESH_METRICS_JSON_TEXTBLOCK])

    metric_fields = [
        "SavedAtUnix", "ObjectName", "UV_area", "UV_islands",
        "UV_stretch", "UV_textel_density", "Normal_percentage",
        "Transformations", "Position", "Non_quads_percentage",
        "Vertex_duplicate", "Vertex_duplicate_percentage", "N_faces",
        "N_meshes", "Face_by_mesh", "Angle", "Source_object_count",
        "Source_objects", "Error",
    ]
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=metric_fields, lineterminator="\n")
    writer.writeheader()
    for object_name, metrics in objects.items():
        row = {field: "" for field in metric_fields}
        row["SavedAtUnix"] = payload["saved_at_unix"]
        row["ObjectName"] = object_name
        if isinstance(metrics, dict):
            for field in metric_fields:
                if field in metrics:
                    value = metrics[field]
                    if field == "Source_objects" and isinstance(value, list):
                        value = json.dumps(value, ensure_ascii=False)
                    row[field] = value
            row["Error"] = metrics.get("error", "")
        writer.writerow(row)

    csv_content = csv_buffer.getvalue()
    with open(TEMP_MESH_METRICS_CSV_PATH, "w", encoding="utf-8", newline="") as handle:
        handle.write(csv_content)
    metrics_csv_txt = get_or_create_textblock(MESH_METRICS_CSV_TEXTBLOCK)
    metrics_csv_txt.clear()
    metrics_csv_txt.write(csv_content)
    return payload

# OPERATOR DETECTION

UV_TRANSFORM_OPS = {
    "transform.translate",
    "transform.rotate",
    "transform.resize",
    "transform.transform",
    "transform.mirror",
    "transform.shear",
    "transform.vert_slide",
    "transform.edge_slide",
}


def is_uv_editor_open():
    """Return True when the current screen contains a UV editor."""
    try:
        screen = bpy.context.screen
        if screen is None:
            return False

        for area in screen.areas:
            if area.type != "IMAGE_EDITOR":
                continue

            space = area.spaces.active
            ui_type = getattr(area, "ui_type", "")
            mode = getattr(space, "mode", "")

            if ui_type == "UV" or mode == "UV":
                return True
    except Exception as exc:
        log_warning("Could not inspect UV editor state", exc)

    return False



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
    global operator_flags, _uv_transform_pending
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

    edit_obj = getattr(bpy.context, "edit_object", None)
    active_obj = getattr(bpy.context, "object", None)
    mesh_is_being_edited = bool(
        (edit_obj is not None and edit_obj.type == "MESH")
        or (
            active_obj is not None
            and active_obj.type == "MESH"
            and safe_mode_of_object(active_obj) == "EDIT"
        )
    )

    uv_editor_transform = (
        op in UV_TRANSFORM_OPS
        and is_uv_editor_open()
        and mesh_is_being_edited
    )

    if (
        op in UV_DEPLOY_OPS
        or op in UV_ASSOCIATED_OPS
        or op.startswith("uv.")
        or uv_editor_transform
    ):
        # UV operators and generic transforms executed while a UV editor is
        # open are tracked as UV activity, but never force a row by themselves.
        mark_uv_pending()
        if uv_editor_transform:
            _uv_transform_pending = True

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
    """Wake the expensive logger only for actual Blender data updates.

    Window resizing and ordinary UI redraws do not dirty mesh/object datablocks,
    so they no longer trigger complete geometry and UV hash calculations.
    """
    meaningful_update = process_new_operators()

    try:
        for update in depsgraph.updates:
            datablock = getattr(update, "id", None)
            if isinstance(datablock, (bpy.types.Mesh, bpy.types.Object)):
                meaningful_update = True
                break
    except Exception as exc:
        log_warning("Could not inspect depsgraph updates", exc)

    if meaningful_update:
        force_log_soon()


# CTRL+V WRAPPER ONLY

class VIEW3D_OT_paste_logger(bpy.types.Operator):
    """Paste in the 3D View and flag the action for logging."""
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


# STATE SNAPSHOT

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
        v, n, t, inv = get_realtime_mesh_stats_safe(obj)
        total_verts += v
        ngons += n
        tris += t
        total_inverted += inv

    total_mods = sum(len(o.modifiers) for o in scene.objects)

    active_obj = bpy.context.object
    if active_obj is not None and safe_mode_of_object(active_obj) == "EDIT":
        mode = "EDIT_MESH"
    else:
        mode = "OBJECT"

    geometry_hash = get_realtime_geometry_hash_safe()
    uv_coordinate_hash = get_realtime_uv_coordinate_hash_safe()
    uv_hash = get_realtime_uv_hash_safe()

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
        "geometry_hash": geometry_hash,
        "uv_coordinate_hash": uv_coordinate_hash,
        "uv_hash": uv_hash,
        "occlusion": get_occlusion_state(),
    }

    # Preserve the original logger sensitivity. UV coordinates themselves are
    # not included: uv_hash represents only seams/island connectivity.
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
        snapshot["geometry_hash"],
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
    global prev_geometry_hash
    global prev_uv_coordinate_hash
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
    prev_geometry_hash = snapshot["geometry_hash"]
    prev_uv_coordinate_hash = snapshot["uv_coordinate_hash"]
    prev_uv_hash = snapshot["uv_hash"]
    prev_snapshot_signature = signature
    prev_active_object_name = snapshot["active_name"]
    prev_object_state = snapshot["object"]


def init_state_full():
    global _last_operator_index
    global _last_timestamp, _force_log_pending
    global _uv_action_pending, _uv_transform_pending
    global operator_flags
    global DEBUG_LAST_LOG_REASON, DEBUG_LAST_REBASE_REASON, DEBUG_UV_HASH_CHANGED, DEBUG_UV_PENDING

    snapshot, signature = build_snapshot()
    apply_snapshot_as_baseline(snapshot, signature)

    _last_timestamp = -1.0
    _uv_action_pending = 0
    _uv_transform_pending = False
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


def init_state_deferred():
    """Reset cheap logger state without scanning every mesh immediately."""
    global _last_operator_index, _last_timestamp, _force_log_pending
    global _uv_action_pending, _uv_transform_pending, operator_flags
    global prev_snapshot_signature, _baseline_ready
    global DEBUG_LAST_LOG_REASON, DEBUG_LAST_REBASE_REASON
    global DEBUG_UV_HASH_CHANGED, DEBUG_UV_PENDING

    _last_timestamp = -1.0
    _force_log_pending = False
    _uv_action_pending = 0
    _uv_transform_pending = False
    prev_snapshot_signature = None
    _baseline_ready = False
    operator_flags = {
        "ctrl_v": 0,
        "shift_d": 0,
        "alt_d": 0,
        "merge": 0,
    }
    DEBUG_LAST_LOG_REASON = "starting"
    DEBUG_LAST_REBASE_REASON = "baseline_deferred"
    DEBUG_UV_HASH_CHANGED = 0
    DEBUG_UV_PENDING = 0

    try:
        _last_operator_index = len(bpy.context.window_manager.operators)
    except Exception as exc:
        log_warning("Could not initialize the operator index", exc)
        _last_operator_index = 0


def ensure_deferred_baseline():
    """Build the expensive baseline after recording has already started."""
    global _baseline_ready
    if _baseline_ready or not timer_running:
        return
    snapshot, signature = build_snapshot()
    apply_snapshot_as_baseline(snapshot, signature)
    _baseline_ready = True

# LOGGER CONTROL

def has_accepted_consent():
    """Return whether recording is allowed by the internal consent policy."""
    if not ENABLE_CONSENT_FLOW:
        return True
    if CONSENT_TEXTBLOCK not in bpy.data.texts:
        return False
    return "ACCEPTED" in bpy.data.texts[CONSENT_TEXTBLOCK].as_string()


def accept_consent_from_start_button():
    """Treat the explicit Start Logger action as consent without showing a popup."""
    if not ENABLE_CONSENT_FLOW:
        return
    consent_text = get_or_create_textblock(CONSENT_TEXTBLOCK)
    consent_text.clear()
    consent_text.write("ACCEPTED")
    consent_text.use_fake_user = True


def should_prompt_for_consent_on_load():
    """Request consent only when opening an actual saved .blend file.

    This prevents the popup from appearing when the add-on is installed or enabled.
    Intended flow: install add-on -> save .blend -> close -> reopen -> show consent.
    """
    if not ENABLE_CONSENT_FLOW:
        return False
    return bool(bpy.data.filepath) and not has_accepted_consent()


def request_consent_popup(delay=0.5, only_if_saved_file=False):
    """Show the consent dialog after a short delay so Blender has an active window."""
    if not ENABLE_CONSENT_FLOW:
        return

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
    global _last_lightweight_signature, _last_idle_full_check

    # Safety guard used only when the internal consent workflow is enabled.
    if ENABLE_CONSENT_FLOW and not has_accepted_consent():
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

    init_state_deferred()
    start_time = time.time()

    _last_lightweight_signature = None
    _last_idle_full_check = 0.0
    timer_running = True
    bpy.app.timers.register(logger_timer, first_interval=LOGGER_INITIAL_DELAY)
    tag_blender_bars_for_redraw()
    print("Data Logger started.")


def stop_logger():
    global timer_running, _baseline_ready
    timer_running = False
    _baseline_ready = False
    _last_lightweight_signature = None
    _last_idle_full_check = 0.0
    tag_blender_bars_for_redraw()
    if not ENABLE_CONSENT_FLOW or has_accepted_consent():
        import_csv_to_blend()
    print("Data Logger stopped.")


def hard_stop_logger_on_file_load():
    """Stop any previous timer when another .blend file is opened.

    This prevents a session that was recording another file from writing to
    the newly opened file before consent has been confirmed.
    """
    global timer_running, start_time, _force_log_pending, _baseline_ready
    global _last_lightweight_signature, _last_idle_full_check
    timer_running = False
    start_time = None
    _force_log_pending = False
    _baseline_ready = False
    tag_blender_bars_for_redraw()


class WM_OT_data_logger_toggle(bpy.types.Operator):
    """Start or stop the workflow logger without a consent popup on manual start."""
    bl_idname = "wm.data_logger_toggle"
    bl_label = "Start / Stop Logger"

    def execute(self, context):
        if timer_running:
            stop_logger()
            self.report({'INFO'}, "Logger stopped.")
            return {'FINISHED'}

        if ENABLE_CONSENT_FLOW and not has_accepted_consent():
            # Pressing Start Logger is itself an explicit user action, so record
            # consent directly and start without opening a separate dialog.
            accept_consent_from_start_button()

        start_logger()
        self.report({'INFO'}, "Logger started.")
        return {'FINISHED'}


# DATA COLLECTION

def collect_data(force=False):
    """Collect one row only when a measurable supported event occurred.

    Completed UV operators are logged once as UV actions. A lightweight event
    hash is stored with that row, so translate/rotate/scale operations are not
    sampled continuously frame by frame and UV coordinates are not exported.
    """
    global _last_timestamp, _force_log_pending
    global prev_mode, prev_active_object_name, prev_object_state
    global operator_flags, _uv_action_pending, _uv_transform_pending
    global prev_geometry_hash, prev_uv_coordinate_hash
    global prev_uv_hash, prev_snapshot_signature
    global DEBUG_LAST_LOG_REASON, DEBUG_LAST_REBASE_REASON
    global DEBUG_UV_HASH_CHANGED, DEBUG_UV_PENDING

    if not _baseline_ready:
        ensure_deferred_baseline()
        return None

    process_new_operators()
    snapshot, signature = build_snapshot()

    active_object_changed = (
        prev_active_object_name != snapshot["active_name"]
    )
    mode_changed_now = prev_mode != snapshot["mode"]

    geometry_changed = (
        snapshot["geometry_hash"] != prev_geometry_hash
    )
    uv_coordinates_changed = (
        snapshot["uv_coordinate_hash"] != prev_uv_coordinate_hash
    )
    uv_topology_changed = (
        snapshot["uv_hash"] != prev_uv_hash
    )
    DEBUG_UV_HASH_CHANGED = int(uv_topology_changed)

    current_user = tuple(trunc_all(snapshot["user"]))
    previous_user = (
        prev_snapshot_signature[0]
        if prev_snapshot_signature is not None
        else current_user
    )
    camera_changed = current_user != previous_user

    previous_occlusion = (
        prev_snapshot_signature[-1]
        if prev_snapshot_signature is not None
        else snapshot["occlusion"]
    )
    occlusion_changed = (
        snapshot["occlusion"] != previous_occlusion
    )

    ox, oy, oz, orad = snapshot["object"]
    prev_ox, prev_oy, prev_oz, prev_orad = prev_object_state

    if active_object_changed:
        obj_dx = obj_dy = obj_dz = obj_drad = 0.0
    else:
        obj_dx = ox - prev_ox
        obj_dy = oy - prev_oy
        obj_dz = oz - prev_oz
        obj_drad = orad - prev_orad

    object_transform_changed = any(
        abs(value) > 1e-6
        for value in (obj_dx, obj_dy, obj_dz, obj_drad)
    )

    v_delta = snapshot["verts"] - prev_vert_count
    n_delta = snapshot["ngons"] - prev_ngon_count
    t_delta = snapshot["tris"] - prev_tri_count
    normal_delta = snapshot["inverted"] - prev_inverted_normals
    obj_delta = snapshot["obj_count"] - prev_object_count
    mod_delta = snapshot["mods"] - prev_total_mods

    explicit_uv_operator = bool(_uv_action_pending)
    explicit_operator = bool(
        operator_flags["ctrl_v"]
        or operator_flags["shift_d"]
        or operator_flags["alt_d"]
        or operator_flags["merge"]
        or explicit_uv_operator
    )

    # Definitive UV-coordinate veto. Moving vertices in the UV editor changes
    # this hash but does not change the actual 3D geometry or coarse UV topology.
    # Ignore the whole sample, including incidental camera/mode/context noise.
    uv_coordinates_only = bool(
        uv_coordinates_changed
        and not geometry_changed
        and not uv_topology_changed
        and not object_transform_changed
        and not active_object_changed
        and v_delta == 0
        and n_delta == 0
        and t_delta == 0
        and normal_delta == 0
        and obj_delta == 0
        and mod_delta == 0
        and not explicit_operator
        and not _uv_action_pending
    )

    if uv_coordinates_only:
        DEBUG_LAST_LOG_REASON = "uv_coordinates_only_ignored"
        DEBUG_LAST_REBASE_REASON = ""

        apply_snapshot_as_baseline(snapshot, signature)

        _uv_action_pending = 0
        _uv_transform_pending = False
        DEBUG_UV_PENDING = 0
        _force_log_pending = False
        return None

    # UV=1 means a completed UV operator, UV transform, or topology/seam/layer change.
    # Blender adds modal transform operators to history after completion, so this
    # records one final action instead of one sample per redraw/frame.
    uv_action = int(bool(
        _uv_action_pending
        or uv_topology_changed
        or _uv_transform_pending
    ))
    uv_coordinate_hash = get_active_live_uv_positions() if uv_action else "0"

    meaningful_change = bool(
        camera_changed
        or geometry_changed
        or uv_topology_changed
        or object_transform_changed
        or active_object_changed
        or mode_changed_now
        or occlusion_changed
        or v_delta != 0
        or n_delta != 0
        or t_delta != 0
        or normal_delta != 0
        or obj_delta != 0
        or mod_delta != 0
        or explicit_operator
    )

    # force=True may accelerate a check, but may not invent an event.
    if not meaningful_change:
        _uv_action_pending = 0
        _uv_transform_pending = False
        DEBUG_UV_PENDING = 0
        _force_log_pending = False
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

    obj_mode_state = int(snapshot["mode"] == "OBJECT")
    edit_mode_state = int(snapshot["mode"] == "EDIT_MESH")

    record = trunc_all([
        SCHEMA_VERSION, LOGGER_VERSION, SESSION_ID,
        get_or_create_user_id(),
        timestamp, minute, second,
        user[0], user[1], user[2],
        snapshot["scene_radius"],
        ox, oy, oz, orad,
        obj_dx, obj_dy, obj_dz, obj_drad,
        v_delta, n_delta, t_delta, normal_delta,
        obj_mode_state, edit_mode_state, int(mode_changed_now), uv_action,
        uv_coordinate_hash,
        obj_delta, mod_delta,
        operator_flags["ctrl_v"],
        operator_flags["shift_d"],
        operator_flags["alt_d"],
        operator_flags["merge"],
        snapshot["occlusion"],
    ])

    reasons = []
    if camera_changed:
        reasons.append("camera_change")
    if geometry_changed:
        reasons.append("geometry_change")
    if uv_topology_changed:
        reasons.append("uv_topology_change")
    if _uv_action_pending:
        reasons.append("uv_operator")
    if _uv_transform_pending and uv_coordinates_changed:
        reasons.append("uv_transform")
    if object_transform_changed:
        reasons.append("object_transform")
    if active_object_changed:
        reasons.append("active_object_change")
    if mode_changed_now:
        reasons.append("mode_change")
    if occlusion_changed:
        reasons.append("occlusion_change")
    if obj_delta:
        reasons.append("object_count_change")
    if mod_delta:
        reasons.append("modifier_change")
    if operator_flags["ctrl_v"]:
        reasons.append("ctrl_v")
    if operator_flags["shift_d"]:
        reasons.append("shift_d")
    if operator_flags["alt_d"]:
        reasons.append("alt_d")
    if operator_flags["merge"]:
        reasons.append("merge")

    DEBUG_LAST_LOG_REASON = ",".join(reasons) or "measured_change"
    DEBUG_LAST_REBASE_REASON = ""

    apply_snapshot_as_baseline(snapshot, signature)

    operator_flags = {
        "ctrl_v": 0,
        "shift_d": 0,
        "alt_d": 0,
        "merge": 0,
    }
    _uv_action_pending = 0
    _uv_transform_pending = False
    DEBUG_UV_PENDING = 0
    _force_log_pending = False

    return ",".join(str(v) for v in record)

def build_lightweight_signature():
    """Return a cheap UI/navigation state without scanning mesh topology."""
    obj = getattr(bpy.context, "object", None)
    if obj is None:
        obj_state = ("", "", ())
    else:
        try:
            matrix_values = tuple(round(float(v), 5) for row in obj.matrix_world for v in row)
        except Exception:
            matrix_values = ()
        obj_state = (obj.name, safe_mode_of_object(obj), matrix_values)

    camera = tuple(round(float(v), 3) for v in get_camera_pos())
    return (camera, obj_state, get_occlusion_state())


def write_log_row(force=False):
    row = collect_data(force=force)
    if row:
        append_csv(row)
        remove_duplicate_rows()
        import_csv_to_blend()


def logger_timer():
    global _force_log_pending, _last_lightweight_signature, _last_idle_full_check

    if not timer_running:
        return None

    # Build the expensive baseline once, but never on every UI redraw.
    if not _baseline_ready:
        ensure_deferred_baseline()
        _last_lightweight_signature = build_lightweight_signature()
        _last_idle_full_check = time.time()
        return LOGGER_POLL_INTERVAL

    process_new_operators()

    # Cheaply detect camera, active-object transform, mode and occlusion changes.
    lightweight = build_lightweight_signature()
    lightweight_changed = (
        _last_lightweight_signature is not None
        and lightweight != _last_lightweight_signature
    )
    _last_lightweight_signature = lightweight

    now = time.time()
    idle_full_check_due = (now - _last_idle_full_check) >= LOGGER_IDLE_FULL_CHECK_INTERVAL

    if _force_log_pending or lightweight_changed:
        _force_log_pending = False
        _last_idle_full_check = now
        write_log_row(force=True)
    elif idle_full_check_due:
        # Rare safety check for changes that do not emit a depsgraph/operator event.
        _last_idle_full_check = now
        write_log_row(force=False)

    return LOGGER_POLL_INTERVAL


# KEYMAPS

def register_keymaps():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon

    if not kc:
        return

    # Preserve the normal Shift+D and Alt+D behavior:
    # do not override them. They are detected by operator_tracker().
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


# CONSENT / AUTORUN

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
        # If the user cancels, consent is not stored
        # and data capture does not start.
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
    # When a .blend file is opened, stop any previous capture before checking
    # whether this file has consent.
    hard_stop_logger_on_file_load()

    # With consent disabled, never auto-start and never show a popup.
    # Recording can begin only through the Start Logger button.
    if not ENABLE_CONSENT_FLOW:
        return

    # Show nothing while installing/enabling the add-on or in the initial unsaved file.
    # Consent is requested only when opening a saved .blend file.
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
    # save_pre: embed the latest logger CSV and mesh metrics in the same Ctrl+S.
    if not ENABLE_CONSENT_FLOW or has_accepted_consent():
        import_csv_to_blend()
    save_scene_mesh_metrics()




def _ui_scale(context):
    """Return Blender UI scale safely."""
    try:
        return max(0.5, float(context.preferences.system.ui_scale))
    except Exception:
        return 1.0


def _available_ui_width(context, fallback=420):
    """Estimate the usable width of the current region or window in UI pixels."""
    try:
        region = getattr(context, "region", None)
        if region is not None and getattr(region, "width", 0):
            return max(180, int(region.width / _ui_scale(context)))
        window = getattr(context, "window", None)
        if window is not None and getattr(window, "width", 0):
            return max(180, int(window.width / _ui_scale(context)))
    except Exception:
        pass
    return fallback


def _wrap_text(text, context, width_px=None, min_chars=18, max_chars=96):
    """Wrap UI text according to the current Blender region and interface scale."""
    if width_px is None:
        width_px = _available_ui_width(context)
    # Blender's default UI font averages roughly 7 px per character.
    chars = int(max(min_chars, min(max_chars, (width_px - 34) / 7.0)))
    words = str(text).split()
    lines, line = [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and len(candidate) > chars:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines or [""]


def _draw_wrapped(layout, text, context, icon='NONE', width_px=None):
    """Draw wrapped labels without assuming a fixed Blender window width."""
    for index, line in enumerate(_wrap_text(text, context, width_px=width_px)):
        layout.label(text=line, icon=icon if index == 0 else 'NONE')

# PANEL AND EXPORT

class DATA_LOGGER_OT_Help(bpy.types.Operator):
    """Show extensive localized documentation for the add-on."""
    bl_idname = "wm.data_logger_help"
    bl_label = "Data Logger 3D Help"
    bl_description = "Open detailed help for Data Logger 3D"

    @classmethod
    def description(cls, context, properties):
        """Return the icon tooltip in the language selected for this scene."""
        return tr("help", context)

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        
        # Keep the help usable on small windows and HiDPI displays.
        available = _available_ui_width(context, fallback=720)
        width = max(360, min(760, int(available * 0.82)))
        return context.window_manager.invoke_props_dialog(self, width=width)

    def draw(self, context):
        layout = self.layout
        layout.label(text=tr("help_title", context), icon='HELP')
        help_keys = ["help_intro", "help_save", "help_metrics"]
        help_keys.append("help_privacy" if ENABLE_CONSENT_FLOW else "help_manual_start")
        for key in help_keys:
            box = layout.box()
            col = box.column(align=True)
            col.scale_y = 0.9
            text = tr(key, context)
            _draw_wrapped(col, text, context, width_px=_available_ui_width(context, fallback=680))



class DATA_LOGGER_PT_Panel(bpy.types.Panel):
    bl_label = "Data Logger 3D"
    bl_idname = "DATA_LOGGER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Data Logger"

    def draw_header(self, context):
        self.layout.operator("wm.data_logger_help", text="", icon='QUESTION', emboss=False)

    def draw(self, context):
        layout = self.layout

        available_width = _available_ui_width(context)
        if available_width < 250:
            language_col = layout.column(align=True)
            language_col.label(text=tr("language", context), icon='WORLD')
            language_col.prop(context.scene, "data_logger_language", text="")
        else:
            language_row = layout.row(align=True)
            language_row.label(text=tr("language", context), icon='WORLD')
            language_row.prop(context.scene, "data_logger_language", text="")

        box = layout.box()
        box.label(text=tr("status", context))
        box.label(text=tr("running", context) if timer_running else tr("stopped", context))

        button_text = tr("stop", context) if timer_running else tr("start", context)
        button_icon = "PAUSE" if timer_running else "PLAY"
        box.operator("wm.data_logger_toggle", text=button_text, icon=button_icon)

        layout.separator()
        layout.label(text=tr("export", context))
        layout.operator("wm.data_logger_export_csv", text=tr("export_csv", context), icon="EXPORT")
        layout.operator("wm.data_logger_export_csv_anonymous", text=tr("export_anon", context), icon="EXPORT")

        layout.separator()
        layout.label(text=tr("privacy", context))
        layout.operator("wm.data_logger_reset_user_id", text=tr("reset_id", context), icon="FILE_REFRESH")
        if ENABLE_CONSENT_FLOW:
            layout.operator("wm.data_logger_clear_consent", text=tr("clear_consent", context), icon="X")
        layout.operator("wm.data_logger_clear_logged_data", text=tr("clear_data", context), icon="TRASH")


class DATA_LOGGER_PT_DebugPanel(bpy.types.Panel):
    bl_label = "Data Logger Debug"
    bl_idname = "DATA_LOGGER_PT_debug_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Data Logger"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return bool(SHOW_DEBUG_PANEL)

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.label(text=f"{tr('timer', context)}: {'ON' if timer_running else 'OFF'}")
        col.label(text=f"{tr('last_operator', context)}: {DEBUG_LAST_OPERATOR or '-'}")
        col.label(text=f"{tr('last_reason', context)}: {DEBUG_LAST_LOG_REASON or '-'}")
        col.label(text=f"{tr('last_rebase', context)}: {DEBUG_LAST_REBASE_REASON or '-'}")
        col.separator()
        col.label(text=f"{tr('uv_tracking', context)}: {'ON' if ENABLE_UV_CHANGE_TRACKING else 'OFF'}")
        col.label(text=f"{tr('uv_pending', context)}: {DEBUG_UV_PENDING}")
        col.label(text=f"{tr('uv_changed', context)}: {DEBUG_UV_HASH_CHANGED}")
        col.separator()
        col.label(text=DEBUG_LAST_FLAGS)
        col.separator()
        col.label(text=f"{tr('active_object', context)}: {get_active_object_name() or '-'}")
        col.label(text=f"{tr('mode', context)}: {bpy.context.mode}")
        col.separator()
        col.label(text=tr("warnings", context))
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
    """Export the embedded logger CSV beside the current .blend file."""
    bl_idname = "wm.data_logger_export_csv"
    bl_label = "Export to CSV"

    def execute(self, context):
        return _export_csv_content(context, self, anonymize=False)


class DATA_LOGGER_OT_ExportCSVAnonymous(bpy.types.Operator):
    """Export the embedded CSV after removing the UserID column."""
    bl_idname = "wm.data_logger_export_csv_anonymous"
    bl_label = "Export CSV without UserID"

    def execute(self, context):
        return _export_csv_content(context, self, anonymize=True)


class DATA_LOGGER_OT_ResetUserID(bpy.types.Operator):
    """Replace the current persistent UserID with a new random UUID."""
    bl_idname = "wm.data_logger_reset_user_id"
    bl_label = "Regenerate UserID"

    def execute(self, context):
        new_id = reset_user_id()
        self.report({'INFO'}, f"New UserID generated: {new_id[:8]}...")
        return {'FINISHED'}


class DATA_LOGGER_OT_ClearConsent(bpy.types.Operator):
    """Remove stored consent so it must be requested again."""
    bl_idname = "wm.data_logger_clear_consent"
    bl_label = "Clear Consent"

    def execute(self, context):
        clear_consent()
        self.report({'INFO'}, "Consent cleared.")
        return {'FINISHED'}


class DATA_LOGGER_OT_ClearLoggedData(bpy.types.Operator):
    """Delete the embedded log and its temporary CSV file."""
    bl_idname = "wm.data_logger_clear_logged_data"
    bl_label = "Clear Embedded Data"

    def execute(self, context):
        clear_logged_data()
        self.report({'INFO'}, "Logger data cleared.")
        return {'FINISHED'}


# REGISTRATION

classes = [
    VIEW3D_OT_paste_logger,
    WM_OT_data_logger_toggle,
    DATA_LOGGER_OT_ConsentPopup,
    DATA_LOGGER_OT_AutoRunWarning,
    DATA_LOGGER_OT_Help,
    DATA_LOGGER_PT_Panel,
    DATA_LOGGER_PT_DebugPanel,
    DATA_LOGGER_OT_ExportCSV,
    DATA_LOGGER_OT_ExportCSVAnonymous,
    DATA_LOGGER_OT_ResetUserID,
    DATA_LOGGER_OT_ClearConsent,
    DATA_LOGGER_OT_ClearLoggedData,
]


def register():
    bpy.types.Scene.data_logger_language = bpy.props.EnumProperty(
        name="Language / Idioma",
        description="Interface language / Idioma de la interfaz",
        items=[
            ('en', "English", "Use the interface in English"),
            ('es', "Español", "Usar la interfaz en español"),
        ],
        default='en',
    )

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_HT_upper_bar.append(draw_recording_indicator)
    register_keymaps()

    if check_consent_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(check_consent_on_load)

    if handle_save not in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.append(handle_save)

    if operator_tracker not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(operator_tracker)

    # Do not call check_consent_on_load() during register().
    # This prevents the consent dialog from appearing during installation or activation.
    # The popup is shown from load_post when a saved .blend file is reopened.

    print("Data Logger loaded successfully.")


def unregister():
    unregister_keymaps()

    if hasattr(bpy.types.Scene, "data_logger_language"):
        del bpy.types.Scene.data_logger_language

    try:
        bpy.types.TOPBAR_HT_upper_bar.remove(draw_recording_indicator)
    except Exception:
        pass

    if check_consent_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(check_consent_on_load)

    if handle_save in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(handle_save)

    if operator_tracker in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(operator_tracker)

    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as exc:
            log_warning(f"Could not unregister class {getattr(cls, '__name__', cls)}", exc)


if __name__ == "__main__":
    register()