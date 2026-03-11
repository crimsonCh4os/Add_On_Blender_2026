
import bpy
import bmesh
import math
import os
import numpy as np
from bpy.props import *
from mathutils import Vector
import matplotlib.pyplot as plt
import mathutils
# main.py
# graficos.py
# graficos.py
from utils import (
    detect_csvs, 
    read_csv, 
    count_uv_islands, 
    normal_flipped, 
    calculate_topology_similarity, 
    calculate_similarity, 
    calculate_median
    
)

from graphs import (
    draw_radar_graph_3d_filled,
    clear_previous_graphs,
    clear_scene,
    get_color_for_csv,
    draw_axes,
    draw_axes_real_only,
    draw_metric_line,
    create_plane_with_image_memory
    
)

import bpy

def draw_surface_graph(
    name,
    values_x,
    values_y,
    axis_scale_x=5,
    axis_scale_y=5,
    axis_scale_z=5,
    z_offset=0,
    csv_name=None,
    color=None,
    thickness=0.05
):
    import numpy as np

    values_x = list(values_x)
    values_y = list(values_y)
    
     # -----------------------------
    # Limpiar objetos previos
    # -----------------------------
    clear_scene()
            

    if len(values_x) == 0 or len(values_y) == 0:
        return

    # rango real de datos
    x_range = (min(values_x), max(values_x))
    y_range = (min(values_y), max(values_y))

    # número de capas de superficie
    layers = 1

    for i in range(layers):

        z = z_offset + (i / layers) * axis_scale_z

        draw_metric_line(
            name=f"{name}_layer_{i}",
            values_x=values_x,
            values_y=values_y,
            values_z=[z] * len(values_x),
            axis_scale_x=axis_scale_x,
            axis_scale_y=axis_scale_y,
            axis_scale_z=axis_scale_z,
            x_range=x_range,
            y_range=y_range,
            thickness=thickness,
            csv_name=csv_name,
            color=color
        )
        
def draw_correlation_graph(
    name,
    values_x,
    values_y,
    axis_scale_x=5,
    axis_scale_y=5,
    axis_scale_z=5,
    z_offset=0,
    csv_name=None,
    color=None,
    radius=0.08
):

    import bpy, bmesh, colorsys, random

    values_x = list(values_x)
    values_y = list(values_y)
    
    # -----------------------------
    # Limpiar objetos previos
    # -----------------------------
    clear_scene()

    # Color automático
    if color is None:
        if csv_name is None:
            csv_name = name
        random.seed(hash(csv_name))
        h = random.random()
        s = 0.7 + random.random()*0.3
        v = 0.7 + random.random()*0.3
        r,g,b = colorsys.hsv_to_rgb(h,s,v)
        color = (r,g,b,1)

    min_x, max_x = min(values_x), max(values_x)
    min_y, max_y = min(values_y), max(values_y)

    # Material
    mat = bpy.data.materials.get(f"{name}_mat")
    if mat is None:
        mat = bpy.data.materials.new(f"{name}_mat")
        mat.use_nodes = False
        mat.diffuse_color = color

    for i,(x,y) in enumerate(zip(values_x,values_y)):

        if max_x != min_x:
            px = (x-min_x)/(max_x-min_x)*axis_scale_x
        else:
            px = axis_scale_x/2

        if max_y != min_y:
            py = (y-min_y)/(max_y-min_y)*axis_scale_y
        else:
            py = axis_scale_y/2

        pz = z_offset

        mesh = bpy.data.meshes.new(f"{name}_mesh_{i}")
        obj = bpy.data.objects.new(f"{name}_pt_{i}", mesh)

        bpy.context.collection.objects.link(obj)

        bm = bmesh.new()
        bmesh.ops.create_uvsphere(
            bm,
            u_segments=12,
            v_segments=8,
            radius=radius
        )

        bm.to_mesh(mesh)
        bm.free()

        obj.location = (px,py,pz)
        obj.data.materials.append(mat)

import bpy
import math

import bpy
import bpy
import math
import numpy as np


def create_scatter(values_x, values_y, z_pos, scale_x, scale_y):

    mesh = bpy.data.meshes.new("ScatterMesh")
    obj = bpy.data.objects.new("ScatterGraph", mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()

    min_x, max_x = min(values_x), max(values_x)
    min_y, max_y = min(values_y), max(values_y)

    range_x = max_x - min_x if max_x != min_x else 1
    range_y = max_y - min_y if max_y != min_y else 1

    for x, y in zip(values_x, values_y):

        px = (x - min_x) / range_x * scale_x
        py = (y - min_y) / range_y * scale_y

        bm.verts.new((px, py, z_pos))

    bm.to_mesh(mesh)
    bm.free()

# Ahora puedes usar las funciones en graficos.py

# ─────────────────────────────────────────
# DATA TYPES
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

GRAPH_TYPES = {
    "G1": {"label": "Interaction","roles": {"X":1},"allow_mix": False,"compatible_typologies": ["Temporal","Spatial","Strategy"]},
    "G2": {"label": "Forest plot","roles": {"X":1,"Y":1},"allow_mix": False,"compatible_typologies": ["Temporal","Strategy"]},
    "G3": {"label": "Radar plot","roles": {"X":3},"allow_mix": False,"compatible_typologies": ["Spatial","Strategy"]},
    "G4": {"label": "Correlation Plot","roles": {"X":1,"Y":1},"allow_mix": True,"compatible_typologies": ["Temporal","Spatial"]},
    "G5": {"label": "Time Lapse","roles": {"X":1},"allow_mix": False,"compatible_typologies": ["Temporal"]},
    "G6": {"label": "Scatter plot","roles": {"X":1,"Y":1},"allow_mix": True,"compatible_typologies": ["Temporal","Spatial"]},
}


def safe_float(row, key, default=0.0):
    """Convierte valores del CSV a float de forma segura."""
    try:
        return float(row.get(key, default))
    except (ValueError, TypeError):
        return default


def create_matplotlib_graph(values_x, values_y=None, csv_name="CSV", metric_name="Metric", graph_type="G1"):

    fig = plt.figure(figsize=(4,4))
    color = get_color_for_csv(csv_name)

    # INTERACTION
    if graph_type == "G1":
        ax = fig.add_subplot(111)
        ax.plot(values_x, values_y, marker='o', color=color)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")

    # FOREST PLOT
    # FOREST PLOT
    # FOREST PLOT
    elif graph_type == "G2":
        # Validar valores
        values_plot = values_y if values_y is not None else values_x
        if values_plot is None or len(values_plot) == 0:
            return None

        values_plot = np.array(values_plot, dtype=float)
        n = len(values_plot)

        # Limitar número de puntos para evitar solapamiento
        max_items = 25
        if n > max_items:
            indices = np.linspace(0, n-1, max_items, dtype=int)
            values_plot = values_plot[indices]
            n = len(values_plot)

        y_pos = np.arange(n)

        # Estadísticas globales
        mean_global = np.mean(values_plot)
        std_global = np.std(values_plot)

        # Ajustar tamaño de figura vertical según número de puntos
        fig = plt.figure(figsize=(4, max(4, n*0.25)))
        ax = fig.add_subplot(111)

        # Dibujar cada ítem con intervalo de confianza simplificado
        for i, v in enumerate(values_plot):
            ci_item = 1.96 * (std_global / np.sqrt(1))  # CI por ítem (puedes ajustar)
            ax.errorbar(
                v,
                y_pos[i],
                xerr=ci_item,
                fmt='o',
                color=color,
                capsize=4
            )

        # Línea de media global
        ax.axvline(mean_global, linestyle="--", color="black")

        # Etiquetas Y
        ax.set_yticks(y_pos)
        ax.set_yticklabels([f"Item {i+1}" for i in range(n)])

        ax.set_xlabel("Value")
        ax.set_title(f"Forest Plot ({csv_name})")
        ax.grid(axis="x")
        
    # RADAR
    elif graph_type == "G3":

        values = values_y if values_y is not None else values_x
        values = np.array(values)

        angles = np.linspace(0, 2*np.pi, len(values), endpoint=False)

        values = np.append(values, values[0])
        angles = np.append(angles, angles[0])

        ax = fig.add_subplot(111, polar=True)

        ax.plot(angles, values, color=color)
        ax.fill(angles, values, color=color, alpha=0.25)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels([f"M{i}" for i in range(len(values)-1)])

    # CORRELATION
    elif graph_type == "G4":
        ax = fig.add_subplot(111)
        ax.scatter(values_x, values_y, color=color)

        if len(values_x) > 1:
            m, b = np.polyfit(values_x, values_y, 1)
            ax.plot(values_x, m*np.array(values_x)+b, color="black")

        ax.set_xlabel("X")
        ax.set_ylabel("Y")

    # TIME LAPSE
    elif graph_type == "G5":
        ax = fig.add_subplot(111)

        time = range(len(values_x))
        ax.plot(time, values_x, color=color)

        ax.set_xlabel("Time")
        ax.set_ylabel("Value")

    # SCATTER
    elif graph_type == "G6":
        ax = fig.add_subplot(111)
        ax.scatter(values_x, values_y, color=color)

        ax.set_xlabel("X")
        ax.set_ylabel("Y")

    else:
        ax = fig.add_subplot(111)
        ax.plot(values_x, values_y, color=color)

    ax.set_title(f"{metric_name} ({csv_name})")
    ax.grid(True)

    temp_dir = bpy.app.tempdir
    file_path = os.path.join(temp_dir, f"graph_{csv_name}_{metric_name}.png")

    fig.savefig(file_path, bbox_inches='tight')
    plt.close(fig)

    if os.path.exists(file_path):
        img = bpy.data.images.load(file_path, check_existing=True)
        img.name = f"graph_{csv_name}_{metric_name}"
        return img

    return None


def validate_selection(context):
    scn = context.scene
    graph = GRAPH_TYPES[scn.selected_graph]
    selected = [i for i in scn.analysis_items if i.enabled]
    if not selected: return False, "No variables selected"
    for role,count in graph["roles"].items():
        role_items = [i for i in selected if i.role==role]
        if len(role_items)!=count:
            return False, f"{graph['label']} requires {count} variable(s) in role {role}"
    if scn.analysis_mode=="DESCRIPTIVE" and len(selected)!=2:
        return False, "Descriptive mode requires exactly 2 variable"
    if scn.analysis_mode=="COMPARATIVE" and len({i.typology for i in selected})>1:
        return False, "Comparative mode requires same typology"
    if scn.analysis_mode=="INFERENTIAL" and not graph["allow_mix"] and len({i.typology for i in selected})>1:
        return False, "This graph does not allow mixed typologies"
    return True,"OK"

def compute_metrics_for_csv(data, BREAK_SPEED=0.01):
    """
    Calcula métricas para un CSV ya leído (lista de diccionarios).
    Convierte todos los valores a float para evitar errores.
    Devuelve un diccionario con todas las métricas definidas en ANALYSIS.
    """
    metrics = {mid: [] for mid in ANALYSIS.keys()}
    
    prev_pos = None
    prev_time = None
    phase = 0
    current_phase_start = 0

    EPS = 0.001

    for idx, row in enumerate(data):
        t = safe_float(row, "Elapsed")
        pos = Vector((safe_float(row, "UserX"),
                      safe_float(row, "UserY"),
                      safe_float(row, "UserZ")))
        obj_pos = Vector((safe_float(row, "ObjX"),
                          safe_float(row, "ObjY"),
                          safe_float(row, "ObjZ")))
        scene_radius = safe_float(row, "SceneRadius", 1.0)

        # ─── Temporal ───
        metrics["A1"].append(t)

        # A2: breaks simples
        if prev_pos is not None:
            distance_moved = (pos - prev_pos).length
            if distance_moved < BREAK_SPEED:
                metrics["A2"].append(t - prev_time)
            else:
                metrics["A2"].append(0)
        else:
            metrics["A2"].append(0)

        # A3: breaks por fase
        distance_to_obj = (pos - obj_pos).length
        if distance_to_obj > scene_radius * 0.8:
            phase += 1
            current_phase_start = idx
        metrics["A3"].append(phase)

        # ─── Espacial ───
        if prev_pos is not None and prev_time is not None:
            dt = max(t - prev_time, 1e-5)
            speed = (pos - prev_pos).length / dt
            metrics["A4"].append(speed)
            metrics["A5"].append(1 - min(distance_to_obj / max(scene_radius, 1e-6), 1))
            metrics["A6"].append((pos - prev_pos).length)
            metrics["A7"].append(speed if speed < 0.1 else 0)
            metrics["A8"].append(speed if speed >= 0.1 else 0)
        else:
            metrics["A4"].append(0)
            metrics["A5"].append(0)
            metrics["A6"].append(0)
            metrics["A7"].append(0)
            metrics["A8"].append(0)

        prev_pos = pos
        prev_time = t

        # ─── Estratégica ───
        metrics["A10"].append(metrics["A4"][-1] - metrics["A4"][-2] if len(metrics["A4"]) >= 2 else 0)
        metrics["A11"].append(metrics["A5"][-1] - metrics["A5"][-2] if len(metrics["A5"]) >= 2 else 0)
        metrics["A12"].append(safe_float(row,"VertexDelta") + safe_float(row,"NgonDelta") +
                              safe_float(row,"TriDelta") + safe_float(row,"NormalDelta"))
        metrics["A13"].append(abs(safe_float(row,"ObjectDelta") - safe_float(row,"ModifierDelta")))
        metrics["A14"].append(safe_float(row,"ObjMode") + safe_float(row,"EditMode"))
        metrics["A15"].append(safe_float(row,"UV"))
        metrics["A16"].append(safe_float(row,"VertexDelta") + safe_float(row,"NgonDelta") +
                              safe_float(row,"TriDelta") + safe_float(row,"NormalDelta") +
                              safe_float(row,"ObjectDelta") + safe_float(row,"ModifierDelta"))

    return metrics


# ───────────────────────────────────────────────────
# CLASE: OBJECT_OT_CalculateMetrics
# ───────────────────────────────────────────────────

class OBJECT_OT_CalculateMetrics(bpy.types.Operator):
    bl_idname = "object.calculate_metrics"
    bl_label = "Calcular Métricas"

    def execute(self, context):
        scn = context.scene
        
        # Obtener el objeto activo y la referencia
        obj = context.active_object
        reference_obj = scn.reference_obj
        
        if not obj or obj.type != 'MESH':
            self.report({'WARNING'}, "Selecciona un objeto MESH")
            return {'CANCELLED'}
        
        if not reference_obj or reference_obj.type != 'MESH':
            self.report({'WARNING'}, "Selecciona un objeto de referencia MESH")
            return {'CANCELLED'}
        
        # Calcular las métricas
        metrics = self.calculate_model_metrics(obj, reference_obj)
        
        # Almacenar las métricas en la escena para acceso en el panel
        if "metrics_data" not in scn:
            scn["metrics_data"] = {}
        scn["metrics_data"][obj.name] = metrics
        
        self.report({'INFO'}, f"Métricas calculadas para: {obj.name}")
        
        return {'FINISHED'}

    def calculate_model_metrics(self, obj, reference_obj=None):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        total_faces = len(bm.faces)
        total_verts = len(bm.verts)

        # Non quads
        non_quads = round((len([f for f in bm.faces if len(f.verts) != 4]) / total_faces * 100) if total_faces else 0, 2)

        # Vertex duplicate
        initial = total_verts
        temp_bm = bm.copy()
        bmesh.ops.remove_doubles(temp_bm, verts=temp_bm.verts, dist=0.0001)
        vertex_dup = round(((initial - len(temp_bm.verts)) / initial * 100) if initial else 0, 2)
        temp_bm.free()

        # N_meshes y Faces_per_mesh
        visited = set()
        parts = 0
        for f in bm.faces:
            if f.index not in visited:
                stack = [f]
                while stack:
                    face = stack.pop()
                    if face.index in visited:
                        continue
                    visited.add(face.index)
                    for e in face.edges:
                        for lf in e.link_faces:
                            if lf.index not in visited:
                                stack.append(lf)
                parts += 1
        faces_per_mesh = round((total_faces / parts) if parts else total_faces, 2)

        # Angle median
        angles = []
        for e in bm.edges:
            if len(e.link_faces) == 2:
                angle_deg = math.degrees(abs(e.calc_face_angle()))
                angle_deg = angle_deg if angle_deg <= 90 else 180 - angle_deg
                angles.append(angle_deg)

        angle_median = calculate_median(angles)

        # Normales
        bm.normal_update()
        flipped = sum(1 for f in bm.faces if normal_flipped(f, obj))
        normal_percentage = round((flipped / total_faces * 100) if total_faces else 0, 2)

        # Transform & Position
        transform = obj.scale == (1, 1, 1) and obj.rotation_euler == (0, 0, 0)
        position = obj.location == (0, 0, 0)

        # UV metrics
        uv_layer = bm.loops.layers.uv.active
        if uv_layer:
            uv_coords = [l[uv_layer].uv for f in bm.faces for l in f.loops]
            if uv_coords:
                min_uv = [min(v.x for v in uv_coords), min(v.y for v in uv_coords)]
                max_uv = [max(v.x for v in uv_coords), max(v.y for v in uv_coords)]
                uv_area = round((max_uv[0] - min_uv[0]) * (max_uv[1] - min_uv[1]) * 100, 2)
                uv_islands = count_uv_islands(bm)
                uv_stretch = round((sum((l[uv_layer].uv.length - 1.0) ** 2 for f in bm.faces for l in f.loops) / len(uv_coords)) ** 0.5, 2)
                uv_textel_density = round(sum(abs(f.calc_area() - 1.0) for f in bm.faces) / len(bm.faces), 2)
            else:
                uv_area = uv_islands = uv_stretch = uv_textel_density = 0
        else:
            uv_area = uv_islands = uv_stretch = uv_textel_density = 0

        # Similarity
        metrics_temp = {"Non_quads_percentage": non_quads, "Vertex_duplicate": vertex_dup}
        similarity_geom = calculate_similarity(reference_obj, obj, metrics_temp) if reference_obj else 0.0
        similarity_topo = calculate_topology_similarity(reference_obj, obj) if reference_obj else 0.0
        similarity = round(0.7 * similarity_geom + 0.3 * similarity_topo, 2)

        bm.free()

        # Return rounded metrics
        metrics = {
            "UV_area": uv_area,
            "UV_islands": int(uv_islands),
            "UV_stretch": uv_stretch,
            "UV_textel_density": uv_textel_density,
            "Normal_percentage": normal_percentage,
            "Transform": transform,
            "Position": position,
            "Non_quads_percentage": non_quads,
            "Vertex_duplicate": vertex_dup,
            "N_faces": total_faces,
            "N_meshes": parts,
            "Faces_per_mesh": faces_per_mesh,
            "Angle": angle_median,
            "Similarity": similarity,
        }

        return {k: (round(v, 2) if isinstance(v, (int, float)) else v) for k, v in metrics.items()}
    
    

# ------------------- Clases de Propiedades -------------------
class CSVItem(bpy.types.PropertyGroup):
    name: StringProperty()
    selected: BoolProperty(default=True)

class AnalysisItem(bpy.types.PropertyGroup):
    key: StringProperty()
    label: StringProperty()
    typology: StringProperty()
    enabled: BoolProperty(default=False)
    role: EnumProperty(items=[('X', 'X', ''), ('Y', 'Y', ''), ('G', 'Group', '')], default='X')

# ------------------- Operadores -------------------
class ANALI_OT_DetectCSV(bpy.types.Operator):
    bl_idname = "anali.detect_csv"
    bl_label = "Scan CSV"
    
    def execute(self, context):
        scn = context.scene
        scn.csv_items.clear()
        for r in detect_csvs(scn.csv_folder):
            item = scn.csv_items.add()
            item.name = r
            item.selected = False
        self.report({'INFO'}, f"{len(scn.csv_items)} CSV detected")
        return {'FINISHED'}

class ANALI_OT_DrawAxes(bpy.types.Operator):
    bl_idname = "anali.draw_axes"
    bl_label = "Dibujar Ejes 3D"
    
    def execute(self, context):
        draw_axes(self)  # Llamada a la función que dibuja los ejes
        return {'FINISHED'}



# ------------------- Operador para dibujar los ejes -------------------


class ANALI_OT_DrawAxes(bpy.types.Operator):
    bl_idname = "anali.draw_axes"
    bl_label = "Dibujar Ejes 3D"

    
    def execute(self, context):
        scn = context.scene
        selected_labels = []
        for item in scn.analysis_items:
            if item.enabled:
                info = ANALYSIS.get(item.key)
                if info:
                    selected_labels.append(info["label"])
        if not selected_labels:
            selected_labels = ["X","Y","Z"]
        # Asegurarse de al menos 3
        for label in ["X","Y","Z"]:
            if label not in selected_labels:
                selected_labels.append(label)

        # Llamar a draw_axes con las escalas de X/Y/Z
        draw_axes(
            length_x = scn.axis_scale_x,
            length_y = scn.axis_scale_y,
            length_z = scn.axis_scale_z,
            steps = 5,
            labels = selected_labels
        )
        self.report({'INFO'},"Ejes 3D dibujados")
        return {'FINISHED'}

# ─────────────────────────────────────────
# CREACIÓN DE PLANOS 3D CON IMAGEN
# ─────────────────────────────────────────

def create_plane_with_image(img, plane_name="GraphPlane", axis_x=5.0, axis_y=5.0, z_pos=0.0):

    bpy.ops.mesh.primitive_plane_add(size=2, location=(axis_x/2, axis_y/2, z_pos))
    plane = bpy.context.active_object
    plane.name = plane_name
    plane.scale.x = axis_x/2
    plane.scale.y = axis_y/2

    temp_path = bpy.app.tempdir + f"{plane_name}.png"
    img.save(temp_path)

    blender_img = bpy.data.images.load(temp_path)
    blender_img.pack()

    mat = bpy.data.materials.new(f"{plane_name}_Mat")
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    for n in list(nodes):
        nodes.remove(n)

    tex = nodes.new("ShaderNodeTexImage")
    tex.image = blender_img

    emission = nodes.new("ShaderNodeEmission")
    output = nodes.new("ShaderNodeOutputMaterial")

    links.new(tex.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])

    plane.data.materials.append(mat)

    return plane


# ─────────────────────────────────────────
# GENERACIÓN DE GRÁFICOS PARA VARIOS CSV
# ─────────────────────────────────────────


# ------------------- UI -------------------

def refresh_analysis_list(self, context):
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
            
class ANALI_UL_CSVList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "selected", text="")
        layout.label(text=os.path.basename(item.name))

class ANALI_UL_AnalysisList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text=item.label)
        row.label(text=f"[{item.typology}]")
        if item.enabled: row.prop(item, "role", text="")

class ANALI_PT_MainPanel(bpy.types.Panel):
    bl_label = "Análisis 3D CSV + Métricas"
    bl_category = "Análisis 3D"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        scn = context.scene
        layout = self.layout

        # CSV
        layout.prop(scn, "csv_folder", text="CSV Folder")
        layout.template_list("ANALI_UL_CSVList","",scn,"csv_items",scn,"csv_index")
        layout.operator("anali.detect_csv")

        layout.separator()

        # Analysis
        layout.prop(scn, "analysis_mode")
        layout.prop(scn, "selected_graph")
        layout.template_list("ANALI_UL_AnalysisList","",scn,"analysis_items",scn,"analysis_index")
        #layout.operator("anali.visualize_graph")

        layout.separator()
        
        '''
        # CSVs seleccionados
        selected_csvs = [i for i in scn.csv_items if i.selected]
        if not selected_csvs:
            layout.label(text="Marca al menos un CSV para ver métricas")
            return
        '''

        # ------------------- Ejes 3D -------------------
        
        layout.label(text="Escala de ejes:")
        row = layout.row(align=True)
        row.prop(scn,"axis_scale_x")
        row.prop(scn,"axis_scale_y")
        row.prop(scn,"axis_scale_z")
        
        layout.operator("anali.draw_axes", text="Dibujar Ejes 3D")

        # ------------------- Visualización 3D -------------------
        layout.operator("anali.visualize_graph", text="Visualizar Gráfico 3D")

        layout.separator()
        
        # ------------------- Selector de referencia y cálculo de métricas -------------------
        layout.prop(scn, "reference_obj", text="Ref Object")
        
        row = layout.row()
        row.scale_y = 1.0
        row.operator("object.calculate_metrics", text="Calcular Métricas")

        # Mostrar métricas del objeto activo
        obj = context.active_object
        reference_obj = scn.reference_obj
        if obj and obj.type == 'MESH' and reference_obj and reference_obj.type == 'MESH':
            metrics = scn.get("metrics_data", {})
            if obj.name in metrics:
                box = layout.box()
                box.label(text=f"Objeto activo: {obj.name}")
                for k, v in metrics[obj.name].items():
                    box.label(text=f"{k}: {v}")
                    
def create_scatter_points(values_x, values_y, z_pos, scale_x, scale_y, point_size=0.05):

    col = bpy.context.collection

    for x, y in zip(values_x, values_y):

        px = (x - min(values_x)) / (max(values_x) - min(values_x)) * scale_x
        py = (y - min(values_y)) / (max(values_y) - min(values_y)) * scale_y

        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=point_size,
            location=(px, py, z_pos)
        )

        obj = bpy.context.active_object
        obj.name = "ScatterPoint"

# Para Blender
import bpy
import math
import os

# Para Matplotlib
import matplotlib.pyplot as plt
import numpy as np

fig = plt.figure(figsize=(4,4))
ax = fig.add_subplot(111)  # ahora sí funciona

# Para manipular imágenes (si creas planos con la textura del gráfico)
from PIL import Image

# Si usas tu función get_color_for_csv
# from tu_modulo import get_color_for_csv

class ANALI_OT_VisualizeGraph(bpy.types.Operator):
    bl_idname = "anali.visualize_graph"
    bl_label = "Visualizar Gráfico 3D"

    def execute(self, context):

        scn = context.scene

        selected_csvs = [i.name for i in scn.csv_items if i.selected]
        selected_metrics = [i.key for i in scn.analysis_items if i.enabled]

        if not selected_csvs:
            self.report({'ERROR'}, "No CSV seleccionado")
            return {'CANCELLED'}

        if not selected_metrics:
            self.report({'ERROR'}, "No métricas seleccionadas")
            return {'CANCELLED'}

        graph_type = scn.selected_graph

        if scn.analysis_mode=="COMPARATIVE" or scn.analysis_mode=="INFERENTIAL":
            # Crear nueva escena
            new_scene = bpy.data.scenes.new(name=f"Graph_{selected_csvs}")
            bpy.context.window.scene = new_scene  # Cambiar contexto
                
            # distribución vertical
            n = len(selected_csvs)
            z_positions = [i * scn.axis_scale_z/(n-1) if n>1 else 0 for i in range(n)]
            
        if scn.analysis_mode=="DESCRIPTIVE":
            z_positions = [0 for _ in selected_csvs]  # lista de ceros

        for csv_idx, csv_path in enumerate(selected_csvs):

            csv_name = os.path.basename(csv_path)
            
            if scn.analysis_mode=="DESCRIPTIVE":
                # Crear nueva escena
                new_scene = bpy.data.scenes.new(name=f"Graph_{csv_name}")
                bpy.context.window.scene = new_scene  # Cambiar contexto

            headers, data = read_csv(csv_path)
            metrics = compute_metrics_for_csv(data)

            for metric_key in selected_metrics:

                values = metrics.get(metric_key, [])

                values_x = None
                values_y = None

                if not values:
                    continue

                values = np.array(values)

                # INTERACTION
                if graph_type == "G1":

                    values_x = list(range(len(values)))
                    values_y = values
                    
                    color = get_color_for_csv(csv_name)
                    draw_surface_graph(
                        name=f"Surface_{csv_name}_{metric_key}",
                        values_x=values_x,
                        values_y=values_y,
                        axis_scale_x=scn.axis_scale_x,
                        axis_scale_y=scn.axis_scale_y,
                        axis_scale_z=scn.axis_scale_z,
                        z_offset=z_positions[csv_idx],
                        csv_name=csv_name
                    )


                # FOREST

                elif graph_type == "G2":

                
                    # Dentro del bucle de métricas
                    values = metrics.get(metric_key)

                    # Validar
                    if values is None:
                        continue

                    values = np.array(values, dtype=float)

                    if values.size == 0:
                        continue

                    # Forest
                    values_x = values
                    values_y = None

                    color = get_color_for_csv(csv_name)

                    
                # RADAR
                elif graph_type == "G3":

                    values_x = [
                        np.mean(values),
                        np.median(values),
                        np.std(values)
                    ]

                    values_y = None
                    color = get_color_for_csv(csv_name)
                 
                    draw_radar_graph_3d_filled(
                        values_x,
                        axis_scale_x=scn.axis_scale_x,
                        axis_scale_y=scn.axis_scale_y,
                        z_pos=z_positions[csv_idx],
                        color=color,
                        csv_name=csv_name
                    )

                # CORRELATION
                elif graph_type == "G4":

                    if len(selected_metrics) < 2:
                        continue

                    metric2 = selected_metrics[1]

                    values_x = metrics.get(metric_key, [])
                    values_y = metrics.get(metric2, [])
                    
                    color = get_color_for_csv(csv_name)
                    draw_correlation_graph(
                        name=f"Corr_{csv_name}_{metric_key}",
                        values_x=values_x,
                        values_y=values_y,
                        axis_scale_x=scn.axis_scale_x,
                        axis_scale_y=scn.axis_scale_y,
                        axis_scale_z=scn.axis_scale_z,
                        z_offset=z_positions[csv_idx],
                        csv_name=csv_name
                    )
                # TIME LAPSE
                elif graph_type == "G5":

                    values_x = list(range(len(values)))
                    values_y = values

                    create_time_graph(values_x, values_y,
                        z_positions[csv_idx],
                        scn.axis_scale_x,
                        scn.axis_scale_y)

                # SCATTER
                elif graph_type == "G6":

                    if len(selected_metrics) < 2:
                        continue

                    metric2 = selected_metrics[1]

                    values_x = metrics.get(metric_key, [])
                    values_y = metrics.get(metric2, [])

                    create_scatter_points(
                        values_x,
                        values_y,
                        z_positions[csv_idx],
                        scn.axis_scale_x,
                        scn.axis_scale_y
                    )

                else:
                    continue


                # Crear gráfico
                img = create_matplotlib_graph(
                    values_x,
                    values_y,
                    csv_name=csv_name,
                    metric_name=metric_key,
                    graph_type=graph_type
                )

                if not img:
                    continue

                from PIL import Image

                img_path = bpy.path.abspath(img.filepath)
                pil_img = Image.open(img_path).convert("RGBA")

                
                create_plane_with_image_memory(
                    pil_img,
                    plane_name=f"GraphPlane_{csv_name}_{metric_key}",
                    axis_x=scn.axis_scale_x,
                    axis_y=scn.axis_scale_y,
                    z_pos=z_positions[csv_idx]
                )
                

                # Dibujar ejes
                # Dibujar ejes
                labels = [ANALYSIS.get(m.key, {}).get("label", m.key) for m in scn.analysis_items if m.enabled]
                while len(labels) < 3: labels.append(f"Axis_{len(labels)+1}")
                x_min, x_max = np.min(values_x), np.max(values_x)
                y_min, y_max = np.min(values_y), np.max(values_y)
                
                draw_axes_real_only(
                    length_x=scn.axis_scale_x,
                    length_y=scn.axis_scale_y,
                    length_z=scn.axis_scale_z,
                    labels=labels,
                    values_x=values_x,
                    values_y=values_y,
                    values_z=[0]
                )
                '''
                draw_axes_with_labels(length_x=scn.axis_scale_x,
                                    length_y=scn.axis_scale_y,
                                    length_z=scn.axis_scale_z,
                                    steps=5,
                                    labels=["Time","Speed","Z"],
                                    x_range=(x_min,x_max),
                                    y_range=(y_min,y_max),
                                    z_range=(0, scn.axis_scale_z))
                '''
                
                # Preparar valores reales de las métricas
                values_x_real = values_x if 'values_x' in locals() else None
                values_y_real = values_y if 'values_y' in locals() else None
                values_z_real = [0]  # para todos los gráficos 2D en Z

        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'MATERIAL'

        self.report({'INFO'}, "Gráficos generados correctamente")

        return {'FINISHED'}



classes = [
    CSVItem, AnalysisItem,
    ANALI_OT_DetectCSV,OBJECT_OT_CalculateMetrics,
    ANALI_UL_CSVList, ANALI_UL_AnalysisList, ANALI_PT_MainPanel,
    ANALI_OT_DrawAxes, ANALI_OT_VisualizeGraph # Añadido el operador de los ejes
]

def register():
    # 1️⃣ Registrar PropertyGroups primero
    bpy.utils.register_class(CSVItem)
    bpy.utils.register_class(AnalysisItem)

    # 2️⃣ Crear CollectionProperty usando esos tipos
    bpy.types.Scene.csv_items = CollectionProperty(type=CSVItem)
    bpy.types.Scene.analysis_items = CollectionProperty(type=AnalysisItem)
    bpy.types.Scene.csv_index = IntProperty(default=0)
    bpy.types.Scene.analysis_index = IntProperty(default=0)

    # 3️⃣ Crear las demás propiedades de escena
    bpy.types.Scene.csv_folder = StringProperty(subtype='DIR_PATH')
    bpy.types.Scene.selected_graph = EnumProperty(
        name="Graph",
        items=[(k,v["label"],"") for k,v in GRAPH_TYPES.items()],
        default="G1",
        update=refresh_analysis_list
    )
    bpy.types.Scene.analysis_mode = EnumProperty(
        name="Mode",
        items=[('DESCRIPTIVE','Descriptive',''),('COMPARATIVE','Comparative',''),('INFERENTIAL','Inferential','')],
        default='DESCRIPTIVE'
    )
    bpy.types.Scene.reference_obj = PointerProperty(
        name="Reference Object",
        type=bpy.types.Object,
        poll=lambda self,obj: obj.type=='MESH'
    )
    bpy.types.Scene.axis_scale_x = FloatProperty(name="Scale X", default=5.0, min=0.1)
    bpy.types.Scene.axis_scale_y = FloatProperty(name="Scale Y", default=5.0, min=0.1)
    bpy.types.Scene.axis_scale_z = FloatProperty(name="Scale Z", default=1.0, min=0.1)

    # 4️⃣ Registrar las demás clases (Operators, Panels, UIList)
    for cls in [ANALI_OT_DetectCSV, OBJECT_OT_CalculateMetrics,
                ANALI_UL_CSVList, ANALI_UL_AnalysisList,
                ANALI_PT_MainPanel, ANALI_OT_DrawAxes, ANALI_OT_VisualizeGraph]:
        bpy.utils.register_class(cls)


def unregister():
    # Eliminar propiedades de escena
    del bpy.types.Scene.csv_items
    del bpy.types.Scene.analysis_items
    del bpy.types.Scene.csv_index
    del bpy.types.Scene.analysis_index
    del bpy.types.Scene.csv_folder
    del bpy.types.Scene.selected_graph
    del bpy.types.Scene.analysis_mode
    del bpy.types.Scene.reference_obj
    del bpy.types.Scene.axis_scale_x
    del bpy.types.Scene.axis_scale_y
    del bpy.types.Scene.axis_scale_z

    # Desregistrar Operators, Panels, UIList
    for cls in reversed([ANALI_OT_DetectCSV, OBJECT_OT_CalculateMetrics,
                         ANALI_UL_CSVList, ANALI_UL_AnalysisList,
                         ANALI_PT_MainPanel, ANALI_OT_DrawAxes, ANALI_OT_VisualizeGraph]):
        bpy.utils.unregister_class(cls)

    # Desregistrar PropertyGroups al final
    bpy.utils.unregister_class(CSVItem)
    bpy.utils.unregister_class(AnalysisItem)