"""Funciones puras extraídas para pruebas fuera de Blender."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

UV_DEPLOY_OPS = {
    "uv.unwrap", "uv.smart_project", "uv.lightmap_pack", "uv.follow_active_quads",
    "uv.cube_project", "uv.cylinder_project", "uv.sphere_project",
    "uv.project_from_view", "uv.reset",
}
UV_ASSOCIATED_OPS = {
    "uv.pack_islands", "uv.average_islands_scale", "uv.minimize_stretch", "uv.seams_from_islands",
}
MERGE_OPS = {
    "mesh.merge", "mesh.remove_doubles", "mesh.merge_by_distance", "mesh.edge_collapse",
    "mesh.dissolve_verts", "mesh.dissolve_edges", "mesh.dissolve_faces",
}


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


def normalize_operator_name(bl_idname: str) -> str:
    return str(bl_idname).replace("_OT_", ".").lower()


@dataclass
class OperatorDetectionState:
    flags: dict[str, int] = field(default_factory=lambda: {
        "ctrl_v": 0, "shift_d": 0, "alt_d": 0, "merge": 0,
    })
    uv_action_pending: int = 0
    last_operator: str = ""


def detect_flags_from_operator_name(bl_idname: str, state: OperatorDetectionState | None = None) -> tuple[OperatorDetectionState, bool]:
    state = state or OperatorDetectionState()
    op = normalize_operator_name(bl_idname)
    state.last_operator = op
    changed = False

    if "view3d.pastebuffer" in op or "wm.paste" in op or "pastebuffer" in op or op.endswith(".paste"):
        if state.flags["ctrl_v"] == 0:
            state.flags["ctrl_v"] = 1
            changed = True

    if "object.duplicate_move" in op or op == "object.duplicate" or "mesh.duplicate_move" in op or op == "mesh.duplicate":
        if "linked" not in op and state.flags["shift_d"] == 0:
            state.flags["shift_d"] = 1
            changed = True

    if "object.duplicate_move_linked" in op or "object.duplicate_linked" in op:
        if state.flags["alt_d"] == 0:
            state.flags["alt_d"] = 1
            changed = True

    if op in MERGE_OPS or "merge" in op:
        if state.flags["merge"] == 0:
            state.flags["merge"] = 1
            changed = True

    if op in UV_DEPLOY_OPS or op in UV_ASSOCIATED_OPS:
        state.uv_action_pending = 1
        changed = True

    return state, changed
