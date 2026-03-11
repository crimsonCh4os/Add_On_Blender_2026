import bpy  # Blender Python API
import math
from math import pi, cos, sin  # Para las operaciones trigonométricas
from mathutils import Vector  # Para el manejo de vectores 3D
import bmesh  # Para crear y manipular mallas con el sistema BMesh de Blender
import random  # Para generar colores aleatorios en algunos casos
import colorsys  # Para convertir valores H, S, V en colores RGB
import numpy as np  # Para trabajar con matrices y operaciones matemáticas si es necesario

def draw_radar_graph_3d_filled(values, axis_scale_x=5, axis_scale_y=5, z_pos=0,
                                     color=(0.2,0.8,0.4,1), csv_name="radar", line_thickness=0.05):
    """
    Radar 3D:
    - Un punto por métrica
    - Curva cerrada con grosor
    - Polígono rellenado correctamente (triangulado)
    - Color visible en layout
    """
    if not values or all(v is None or (isinstance(v,float) and math.isnan(v)) for v in values):
        print(f"Radar vacío para {csv_name}")
        return

    # Limpiar objetos previos
    object_names = [f"Radar_{csv_name}", f"RadarFill_{csv_name}"] + [f"RadarPoint_{csv_name}_{i}" for i in range(len(values))]
    for name in object_names:
        obj = bpy.data.objects.get(name)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)

    n = len(values)
    center = Vector((axis_scale_x/2, axis_scale_y/2, z_pos+1))
    valid_points = []

    # Calcular puntos radar
    max_val = max([v for v in values if v is not None and not (isinstance(v,float) and math.isnan(v))], default=1)
    for i, v in enumerate(values):
        if v is None or (isinstance(v,float) and math.isnan(v)):
            valid_points.append(None)
        else:
            angle = i / n * 2 * pi
            x = center.x + (v / max_val) * (axis_scale_x/2) * cos(angle)
            y = center.y + (v / max_val) * (axis_scale_y/2) * sin(angle)
            valid_points.append(Vector((x, y, z_pos+1)))

    points_for_curve = [p for p in valid_points if p is not None]
    if len(points_for_curve) < 2:
        return
    points_for_curve.append(points_for_curve[0])  # cerrar polígono

    # ----------------------------
    # CURVA
    # ----------------------------
    curve_data = bpy.data.curves.new(f"RadarCurve_{csv_name}", type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = line_thickness
    curve_data.bevel_resolution = 4

    spline = curve_data.splines.new('POLY')
    spline.points.add(len(points_for_curve)-1)
    for j, p in enumerate(points_for_curve):
        spline.points[j].co = (p.x, p.y, p.z, 1)

    curve_obj = bpy.data.objects.new(f"Radar_{csv_name}", curve_data)
    bpy.context.collection.objects.link(curve_obj)

    # ----------------------------
    # RELLENO CON BMESH TRIANGULADO
    # ----------------------------
    mesh_data = bpy.data.meshes.new(f"RadarMesh_{csv_name}")
    mesh_obj = bpy.data.objects.new(f"RadarFill_{csv_name}", mesh_data)
    bpy.context.collection.objects.link(mesh_obj)

    bm = bmesh.new()
    center_v = bm.verts.new(center)
    verts = [bm.verts.new(p) for p in points_for_curve[:-1]]  # sin repetir el primero

    # Crear caras trianguladas
    for i, v in enumerate(verts):
        v_next = verts[(i+1)%len(verts)]
        bm.faces.new([center_v, v, v_next])

    bm.to_mesh(mesh_data)
    bm.free()

    # ----------------------------
    # MATERIAL EMISIVO
    # ----------------------------
    def create_emission_mat(name, color):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        emission = nodes.new("ShaderNodeEmission")
        emission.inputs['Color'].default_value = color
        emission.inputs['Strength'].default_value = 5
        output = nodes.new("ShaderNodeOutputMaterial")
        links.new(emission.outputs[0], output.inputs[0])
        return mat

    mat_curve = create_emission_mat(f"RadarMatCurve_{csv_name}", color)
    curve_obj.data.materials.append(mat_curve)
    curve_obj.active_material.diffuse_color = color[:3] + (1.0,)
    curve_obj.show_wire = True
    curve_obj.show_all_edges = True

    mat_fill = create_emission_mat(f"RadarMatFill_{csv_name}", color)
    mesh_obj.data.materials.append(mat_fill)
    mesh_obj.active_material.diffuse_color = color[:3] + (1.0,)
    mesh_obj.show_wire = True
    mesh_obj.show_all_edges = True

    # ----------------------------
    # PUNTOS
    # ----------------------------
    for idx, p in enumerate(valid_points):
        if p is None:
            continue
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, location=p)
        sphere = bpy.context.active_object
        sphere.name = f"RadarPoint_{csv_name}_{idx}"
        sphere.data.materials.append(mat_curve.copy())
        sphere.active_material.diffuse_color = color[:3] + (1.0,)
# ------------------- Registro -------------------

# ----------------------------
# Limpiar gráficos anteriores
# ----------------------------
def clear_previous_graphs():
    for obj in list(bpy.data.objects):
        if obj.name.startswith("GraphPlane_") or obj.name.startswith("GraphLineMesh_"):
            bpy.data.objects.remove(obj, do_unlink=True)
    for mat in list(bpy.data.materials):
        if mat.name.startswith("GraphMaterial_") or mat.name.startswith("GraphLineMat_"):
            bpy.data.materials.remove(mat, do_unlink=True)
    for img in list(bpy.data.images):
        if img.name.startswith("graph_"):
            bpy.data.images.remove(img, do_unlink=True)


def clear_scene():
    # Selecciona todos los objetos
    bpy.ops.object.select_all(action='SELECT')
    # Elimina los seleccionados
    bpy.ops.object.delete(use_global=False)
    # Limpia también los datos huérfanos de mallas, curvas, materiales, etc.
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.curves:
        if block.users == 0:
            bpy.data.curves.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)
            


# ─────────────────────────────────────────
# UTILIDADES DE COLOR
# ─────────────────────────────────────────

def get_color_for_csv(csv_name):
    import random
    random.seed(hash(csv_name))
    h = random.random()
    s = 0.7 + random.random()*0.3
    v = 0.7 + random.random()*0.3
    r,g,b = colorsys.hsv_to_rgb(h,s,v)
    return (r,g,b,1)


# ─────────────────────────────────────────
# CREACIÓN DE GRÁFICOS MATPLOTLIB
# ─────────────────────────────────────────

    
def create_plane_with_image_memory(img, plane_name="GraphPlane", axis_x=5.0, axis_y=5.0, z_pos=0.0):
    import bpy
    import numpy as np

    # Crear plano
    bpy.ops.mesh.primitive_plane_add(size=2, location=(axis_x/2, axis_y/2, z_pos))
    plane = bpy.context.active_object
    plane.name = plane_name

    # Girar plano 180° en X para que la normal mire hacia +Z
    plane.rotation_euler[0] = math.pi

    # Escalar al tamaño deseado
    plane.scale.x = axis_x/2
    plane.scale.y = axis_y/2

    width, height = img.size

    # Crear imagen Blender
    blender_img = bpy.data.images.new(
        name=f"{plane_name}_Img",
        width=width,
        height=height
    )

    pixels = np.array(img).astype(np.float32) / 255.0
    blender_img.pixels = pixels.flatten()
    blender_img.update()

    # Crear material
    mat = bpy.data.materials.new(name=f"{plane_name}_Mat")
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    nodes.clear()

    tex = nodes.new("ShaderNodeTexImage")
    tex.image = blender_img

    emission = nodes.new("ShaderNodeEmission")
    output = nodes.new("ShaderNodeOutputMaterial")

    links.new(tex.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])

    plane.data.materials.append(mat)

    return plane
import bpy
from mathutils import Vector
















import bpy
from mathutils import Vector
import numpy as np  # Asegúrate de importar NumPy si vas a trabajar con arrays

def create_material(color):
    mat_name = f"AxisMat_{color}"
    mat = bpy.data.materials.get(mat_name)

    if mat is None:
        mat = bpy.data.materials.new(mat_name)
        mat.use_nodes = True

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        emission = nodes.new("ShaderNodeEmission")
        emission.inputs["Color"].default_value = (*color, 1)
        emission.inputs["Strength"].default_value = 3

        output = nodes.new("ShaderNodeOutputMaterial")
        links.new(emission.outputs["Emission"], output.inputs["Surface"])

    return mat


def create_axis(start, end, color, name):

    vec = end - start
    length = vec.length

    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.05,
        depth=length,
        location=(start + end) / 2
    )

    obj = bpy.context.active_object
    obj.name = name

    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = vec.to_track_quat('Z', 'Y')

    mat = create_material(color)

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def create_text_label(text, loc, size, name):

    bpy.ops.object.text_add(location=loc)
    label = bpy.context.active_object

    label.name = name
    label.data.body = str(text)
    label.scale = (size, size, size)

    mat = create_material((1, 1, 1))

    if label.data.materials:
        label.data.materials[0] = mat
    else:
        label.data.materials.append(mat)

    return label


# -------- AXES --------

def draw_axes_real_only(values_x=None, values_y=None, values_z=None,
                         length_x=5, length_y=5, length_z=5,
                         labels=("X", "Y", "Z"),
                         max_ticks_x=5, max_ticks_y=5, max_ticks_z=5):

    # Ejes principales
    create_axis(Vector((0, 0, 0)), Vector((length_x, 0, 0)), (1, 0, 0), "Axis_X")
    create_axis(Vector((0, 0, 0)), Vector((0, length_y, 0)), (0, 1, 0), "Axis_Y")
    create_axis(Vector((0, 0, 0)), Vector((0, 0, length_z)), (0, 0, 1), "Axis_Z")

    def draw_uniform_ticks(values, axis_idx, axis_length, max_ticks):
        if values is None or len(values) == 0:
            return

        values = sorted(values)

        min_val = min(values)
        max_val = max(values)

        if max_val == min_val:
            selected_values = [min_val]
        else:
            n_ticks = min(len(values), max_ticks)

            step = (len(values) - 1) / (n_ticks - 1) if n_ticks > 1 else 1

            selected_values = [
                values[round(i * step)]
                for i in range(n_ticks)
            ]

        for i, v in enumerate(selected_values):

            if abs(v) < 1e-8:
                continue

            fraction = (v - min_val) / (max_val - min_val) if max_val != min_val else 0.5
            pos = fraction * axis_length

            value_str = f"{v:.3f}"

            if axis_idx == 0:
                mark_start = Vector((pos, -0.1, 0))
                mark_end = Vector((pos, 0.1, 0))
                text_loc = Vector((pos, -0.5, 0))

            elif axis_idx == 1:
                mark_start = Vector((-0.1, pos, 0))
                mark_end = Vector((0.1, pos, 0))
                text_loc = Vector((-0.5, pos, 0))

            else:
                mark_start = Vector((-0.1, 0, pos))
                mark_end = Vector((0.1, 0, pos))
                text_loc = Vector((-0.5, 0, pos))

            create_axis(mark_start, mark_end, (0, 0, 0), f"Tick_{axis_idx}_{i}")
            create_text_label(value_str, text_loc, 0.25, f"Num_{axis_idx}_{i}")

    # Llamada para dibujar las marcas de ticks
    draw_uniform_ticks(values_x, 0, length_x, max_ticks_x)
    draw_uniform_ticks(values_y, 1, length_y, max_ticks_y)
    draw_uniform_ticks(values_z, 2, length_z, max_ticks_z)

    # Etiquetas finales
    create_text_label(labels[0], (length_x + 0.5, 0, 0), 0.5, "Label_X")
    create_text_label(labels[1], (0, length_y + 0.5, 0), 0.5, "Label_Y")
    create_text_label(labels[2], (0, 0, length_z + 0.5), 0.5, "Label_Z")
    
    
    
    
    
    
    
    
    
    
    
    
    
def draw_metric_line(
    name, 
    values_x, 
    values_y, 
    values_z=None, 
    color=None,
    thickness=0.01,
    axis_scale_x=5, 
    axis_scale_y=5, 
    axis_scale_z=5,
    x_range=None, 
    y_range=None,
    z_offset=0,
    csv_name=None
):
    import bpy, colorsys, random

    if color is None:
        if csv_name is None: csv_name = name
        random.seed(hash(csv_name))
        h = random.random()
        s = 0.7 + random.random()*0.3
        v = 0.7 + random.random()*0.3
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        color = (r, g, b, 1.0)

    # Normalizar X e Y al tamaño del eje usando los rangos reales
    if x_range: 
        min_x, max_x = x_range
        values_x = [((v - min_x)/(max_x - min_x)*axis_scale_x) if max_x != min_x else axis_scale_x/2 for v in values_x]
    if y_range:
        min_y, max_y = y_range
        values_y = [((v - min_y)/(max_y - min_y)*axis_scale_y) if max_y != min_y else axis_scale_y/2 for v in values_y]

    if values_z is None:
        values_z = [z_offset for _ in values_x]
    else:
        values_z = [v + z_offset for v in values_z]

    curve_data = bpy.data.curves.new(name=f"{name}_curve", type='CURVE')
    curve_data.dimensions = '3D'
    polyline = curve_data.splines.new('POLY')
    polyline.points.add(len(values_x)-1)

    for i, (x, y, z) in enumerate(zip(values_x, values_y, values_z)):
        polyline.points[i].co = (x, y, z, 1)

    curve_data.bevel_depth = thickness

    mat = bpy.data.materials.get(f"{name}_mat") or bpy.data.materials.new(name=f"{name}_mat")
    mat.use_nodes = False
    mat.diffuse_color = color[:4]

    curve_obj = bpy.data.objects.new(name, curve_data)
    bpy.context.scene.collection.objects.link(curve_obj)
    curve_obj.data.materials.append(mat)
    return curve_obj



# ------------------- Ejes 3D -------------------

def draw_axes(length_x=5, length_y=5, length_z=5, steps=5, labels=["X","Y","Z"],
              x_range=(0,1), y_range=(0,1), z_range=(0,1)):

    def create_material(color):
        mat = bpy.data.materials.get(f"AxisMat_{color}")
        if not mat:
            mat = bpy.data.materials.new(name=f"AxisMat_{color}")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()
            emission = nodes.new("ShaderNodeEmission")
            emission.inputs["Color"].default_value = (*color,1)
            emission.inputs["Strength"].default_value = 3
            output = nodes.new("ShaderNodeOutputMaterial")
            links.new(emission.outputs["Emission"], output.inputs["Surface"])
        return mat

    def create_axis(start, end, color, name):
        vec = end - start
        l = vec.length
        bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=l, location=(start+end)/2)
        obj = bpy.context.active_object
        obj.name = name
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = vec.to_track_quat('Z','Y')
        mat = create_material(color)
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

    def create_text_label(text, loc, size, name):
        bpy.ops.object.text_add(location=loc)
        label = bpy.context.active_object
        label.name = name
        label.data.body = str(text)
        label.scale = (size, size, size)
        mat = create_material((1,1,1))
        if label.data.materials:
            label.data.materials[0] = mat
        else:
            label.data.materials.append(mat)
        return label

    # Ejes principales
    create_axis(Vector((0,0,0)), Vector((length_x,0,0)), (1,0,0), "Axis_X")
    create_axis(Vector((0,0,0)), Vector((0,length_y,0)), (0,1,0), "Axis_Y")
    create_axis(Vector((0,0,0)), Vector((0,0,length_z)), (0,0,1), "Axis_Z")

    
    # Marcas y números con valores reales
    for axis_idx, (axis_length, axis_rng) in enumerate(zip([length_x,length_y,length_z],
                                                          [x_range,y_range,z_range])):
        min_val, max_val = axis_rng
        for i in range(1, steps+1):
            fraction = i / steps
            pos = fraction * axis_length
            value = min_val + fraction * (max_val - min_val)
            value_str = f"{value:.2f}"

            if axis_idx==0:
                mark_start, mark_end = Vector((pos,-0.1,0)), Vector((pos,0.1,0))
                text_loc = Vector((pos,-0.5,0))
            elif axis_idx==1:
                mark_start, mark_end = Vector((-0.1,pos,0)), Vector((0.1,pos,0))
                text_loc = Vector((-0.5,pos,0))
            else:
                mark_start, mark_end = Vector((-0.1,0,pos)), Vector((0.1,0,pos))
                text_loc = Vector((-0.5,0,pos))

            create_axis(mark_start, mark_end, (0,0,0), f"Mark_{axis_idx}_{i}")
            create_text_label(value_str, text_loc, 0.25, f"Num_{axis_idx}_{i}")
    

    # Etiquetas finales
    create_text_label(labels[0], (length_x+0.5,0,0), 0.5, "Label_X")
    create_text_label(labels[1], (0,length_y+0.5,0), 0.5, "Label_Y")
    create_text_label(labels[2], (0,0,length_z+0.5), 0.5, "Label_Z")


def register():
    # Registro de clases, operadores, etc.
    pass

def unregister():
    # Desregistro de clases, operadores, etc.
    pass