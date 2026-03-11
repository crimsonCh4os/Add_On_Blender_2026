# utils.py

import os
import csv
import bpy
import numpy as np
import math
import random
from mathutils import Vector  # Para la clase Vector de Blender
from io import BytesIO
from PIL import Image
import matplotlib.pyplot as plt
import colorsys
import bmesh  # Para operaciones en mallas
import matplotlib.pyplot as plt

# ------------------- Funciones -------------------
def detect_csvs(folder):
    if not folder or not os.path.isdir(folder): return []
    return [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".csv")]


def read_csv(file_path):
    data = []
    with open(file_path, newline='', encoding='latin-1') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames  # Esto devuelve la lista de nombres de columnas
        for row in reader:
            data.append(row)  # Cada fila es un diccionario {header: value}
    return headers, data

def create_3d_points_from_csv(file_path):
    headers, data = read_csv(file_path)
    
    # Asegurarse de que las columnas X, Y, Z existen
    if 'X' not in headers or 'Y' not in headers or 'Z' not in headers:
        print("El archivo CSV no contiene las columnas 'X', 'Y', 'Z'")
        return
    
    x_idx = headers.index('X')
    y_idx = headers.index('Y')
    z_idx = headers.index('Z')
    
    # Crear un objeto en Blender para cada punto
    for row in data:
        x = float(row[x_idx])
        y = float(row[y_idx])
        z = float(row[z_idx])
        
        # Crear un vértice en Blender
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.05, location=(x, y, z))



# ───────────────────────────────────────────────────
# FUNCIONES AUXILIARES
# ───────────────────────────────────────────────────

def almost_equal(v1, v2, tol=1e-4):
    """Compara dos vectores con una tolerancia dada"""
    return all(abs(a - b) <= tol for a, b in zip(v1, v2))


def count_uv_islands(bm):
    """Cuenta el número de islas UV en la malla"""
    uv_layer = bm.loops.layers.uv.active
    if not uv_layer:
        return 0
    visited_faces = set()
    islands = 0
    for f in bm.faces:
        if f.index in visited_faces:
            continue
        stack = [f]
        while stack:
            face = stack.pop()
            if face.index in visited_faces:
                continue
            visited_faces.add(face.index)
            for e in face.edges:
                for lf in e.link_faces:
                    if lf.index in visited_faces:
                        continue
                    shared_uv = False
                    for l1 in face.loops:
                        uv1 = l1[uv_layer].uv
                        for l2 in lf.loops:
                            uv2 = l2[uv_layer].uv
                            if almost_equal(uv1, uv2):
                                shared_uv = True
                                break
                        if shared_uv:
                            break
                    if shared_uv:
                        stack.append(lf)
        islands += 1
    return islands


def normal_flipped(f, obj):
    """Detecta si una cara está invertida respecto a la normal"""
    world_normal = f.normal @ obj.matrix_world.to_3x3()
    return world_normal.dot((0, 0, 1)) < 0


def calculate_topology_similarity(reference_obj, target_obj):
    """Calcula la similitud topológica entre dos objetos de malla"""
    if not reference_obj or not target_obj:
        return 0.0

    # Comprobar si alguno de los objetos tiene 0 caras
    ref_faces = len(reference_obj.data.polygons)
    target_faces = len(target_obj.data.polygons)

    if ref_faces == 0 or target_faces == 0:
        return 0.0  # Si alguno de los objetos no tiene caras, devolver 0.0

    verts_sim = min(len(reference_obj.data.vertices), len(target_obj.data.vertices)) / max(len(reference_obj.data.vertices), len(target_obj.data.vertices))
    edges_sim = min(len(reference_obj.data.edges), len(target_obj.data.edges)) / max(len(reference_obj.data.edges), len(target_obj.data.edges))
    faces_sim = min(ref_faces, target_faces) / max(ref_faces, target_faces)

    return round(100 * (verts_sim + edges_sim + faces_sim) / 3, 2)

def calculate_similarity(reference_obj, target_obj, obj_metrics=None):
    if not reference_obj or reference_obj.type != 'MESH' or not target_obj or target_obj.type != 'MESH':
        return 0.0
    verts_ref = [v.co @ reference_obj.matrix_world for v in reference_obj.data.vertices]
    verts_target = [v.co @ target_obj.matrix_world for v in target_obj.data.vertices]
    if not verts_ref or not verts_target: return 0.0
    def distance(v1,v2): return ((v1.x-v2.x)**2+(v1.y-v2.y)**2+(v1.z-v2.z)**2)**0.5
    min_dists_target = [min(distance(vt, vr) for vr in verts_ref) for vt in verts_target]
    min_dists_ref = [min(distance(vr, vt) for vt in verts_target) for vr in verts_ref]
    hausdorff_dist = max(max(min_dists_target), max(min_dists_ref))
    bbox_diag = ((max(v.x for v in verts_ref)-min(v.x for v in verts_ref))**2 +
                 (max(v.y for v in verts_ref)-min(v.y for v in verts_ref))**2 +
                 (max(v.z for v in verts_ref)-min(v.z for v in verts_ref))**2) ** 0.5
    penalty = 0.0
    if obj_metrics:
        penalty += obj_metrics.get("Non_quads_percentage",0)/100
        penalty += obj_metrics.get("Vertex_duplicate",0)/100
    similarity = max(0.0, 100.0*(1 - hausdorff_dist/bbox_diag - penalty*0.5))
    return round(similarity,2)


def calculate_median(values):
    """Calcula la mediana de una lista de valores"""
    if not values:
        return 0
    values.sort()
    n = len(values)
    middle = n // 2
    if n % 2 == 1:  # Si la cantidad de elementos es impar
        return round(values[middle], 2)
    else:  # Si la cantidad de elementos es par
        return round((values[middle - 1] + values[middle]) / 2, 2)

# ──────────────────────────────────────────────
# Normalizar valores al rango de Blender
# ──────────────────────────────────────────────
def normalize_to_blender(values, axis_length, axis_min=None, axis_max=None):
    min_val = axis_min if axis_min is not None else np.min(values)
    max_val = axis_max if axis_max is not None else np.max(values)
    if max_val == min_val:
        return [axis_length/2] * len(values)
    return [(v - min_val)/(max_val - min_val)*axis_length for v in values]

# ──────────────────────────────────────────────
# Crear plano con imagen en +Z con escala correcta
# ──────────────────────────────────────────────
def create_plane_with_image_scaled(img, plane_name="GraphPlane", x_range=None, y_range=None, axis_x=5.0, axis_y=5.0, z_pos=0.0):

    # Crear plano
    bpy.ops.mesh.primitive_plane_add(size=2, location=(0,0,z_pos))
    plane = bpy.context.active_object
    plane.name = plane_name

    # Calcular escala según rango
    if x_range:
        plane.scale.x = axis_x / 2
    else:
        plane.scale.x = axis_x / 2

    if y_range:
        plane.scale.y = axis_y / 2
    else:
        plane.scale.y = axis_y / 2

    # Crear imagen Blender
    width, height = img.size
    blender_img = bpy.data.images.new(
        name=f"{plane_name}_Img",
        width=width,
        height=height
    )

    # Convertir PIL a array de píxeles
    pixels = np.array(img).astype(np.float32)/255.0
    # Blender necesita un array 1D RGBA
    if pixels.shape[2] == 3:
        # agregar canal alpha
        alpha = np.ones((pixels.shape[0], pixels.shape[1], 1), dtype=np.float32)
        pixels = np.concatenate([pixels, alpha], axis=2)
    blender_img.pixels = pixels.flatten()
    blender_img.update()

    # Crear material con la imagen
    mat = bpy.data.materials.new(name=f"{plane_name}_Mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for n in list(nodes): nodes.remove(n)

    tex = nodes.new("ShaderNodeTexImage")
    tex.image = blender_img
    emission = nodes.new("ShaderNodeEmission")
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(tex.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])

    plane.data.materials.append(mat)

    # Rotar plano para mirar +Z (si no está ya)
    plane.rotation_euler[0] = 0  # X
    plane.rotation_euler[1] = 0  # Y
    plane.rotation_euler[2] = 0  # Z

    return plane

# ──────────────────────────────────────────────
# Visualizar gráfico 3D con escala y orientación correctas
# ──────────────────────────────────────────────
def visualize_graph_3d(csv_name, metric_key, values_x, values_y, axis_scale_x=5, axis_scale_y=5, z_pos=0.0):

    # Calcular rangos de Matplotlib
    x_min, x_max = np.min(values_x), np.max(values_x)
    y_min, y_max = np.min(values_y), np.max(values_y)

    # Normalizar valores a Blender
    values_x_bl = normalize_to_blender(values_x, axis_scale_x, x_min, x_max)
    values_y_bl = normalize_to_blender(values_y, axis_scale_y, y_min, y_max)

    # Crear gráfico en memoria con Matplotlib
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(4,4))
    ax.plot(values_x, values_y, marker='o')
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.grid(True)
    ax.set_title(f"{metric_key} ({csv_name})")

    # Guardar a PIL
    from io import BytesIO
    buf = BytesIO()
    fig.savefig(buf, format='PNG', bbox_inches='tight')
    buf.seek(0)
    pil_img = Image.open(buf).convert("RGBA")
    plt.close(fig)

    # Crear plano en Blender
    create_plane_with_image_scaled(
        pil_img,
        plane_name=f"GraphPlane_{csv_name}_{metric_key}",
        x_range=(x_min,x_max),
        y_range=(y_min,y_max),
        axis_x=axis_scale_x,
        axis_y=axis_scale_y,
        z_pos=z_pos
    )


def register():
    # Aquí puedes registrar algunas propiedades o cualquier otra cosa
    print("Registrando funciones de utils")

def unregister():
    # Aquí puedes desregistrar las propiedades o limpiar lo que sea necesario
    print("Desregistrando funciones de utils")