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

try:
    import bpy
    from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
except ImportError:
    import bpy
    from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty

class MetricStatItem(bpy.types.PropertyGroup):
    csv_name: StringProperty()
    key: StringProperty()
    label: StringProperty()

    value: FloatProperty(default=0.0)
    mean: FloatProperty(default=0.0)
    weighted_mean: FloatProperty(default=0.0)
    std: FloatProperty(default=0.0)
    min: FloatProperty(default=0.0)
    max: FloatProperty(default=0.0)

    total: FloatProperty(default=0.0)
    count: FloatProperty(default=0.0)
    rate_per_min: FloatProperty(default=0.0)

    delta_total: FloatProperty(default=0.0)
    delta_per_sec: FloatProperty(default=0.0)

    q1: FloatProperty(default=0.0)
    q2: FloatProperty(default=0.0)
    q3: FloatProperty(default=0.0)
    q4: FloatProperty(default=0.0)

    time_object: FloatProperty(default=0.0)
    time_edit: FloatProperty(default=0.0)
    pct_object: FloatProperty(default=0.0)
    pct_edit: FloatProperty(default=0.0)
    switches: FloatProperty(default=0.0)
    pct_object_q1: FloatProperty(default=0.0)
    pct_object_q2: FloatProperty(default=0.0)
    pct_object_q3: FloatProperty(default=0.0)
    pct_object_q4: FloatProperty(default=0.0)
    pct_edit_q1: FloatProperty(default=0.0)
    pct_edit_q2: FloatProperty(default=0.0)
    pct_edit_q3: FloatProperty(default=0.0)
    pct_edit_q4: FloatProperty(default=0.0)
    mode_switch_q1: FloatProperty(default=0.0)
    mode_switch_q2: FloatProperty(default=0.0)
    mode_switch_q3: FloatProperty(default=0.0)
    mode_switch_q4: FloatProperty(default=0.0)

    active_count: FloatProperty(default=0.0)
    inactive_count: FloatProperty(default=0.0)
    mean_active_duration: FloatProperty(default=0.0)
    mean_inactive_duration: FloatProperty(default=0.0)
    abs_total: FloatProperty(default=0.0)
    rate_per_hour: FloatProperty(default=0.0)
    object_local_size: FloatProperty(default=0.0)
    peak_speed_mean: FloatProperty(default=0.0)
    ngon_error_total: FloatProperty(default=0.0)
    tri_error_total: FloatProperty(default=0.0)
    normal_error_total: FloatProperty(default=0.0)
    mesh_count_q1: FloatProperty(default=0.0)
    mesh_count_q2: FloatProperty(default=0.0)
    mesh_count_q3: FloatProperty(default=0.0)
    mesh_count_q4: FloatProperty(default=0.0)
    
class CSVItem(bpy.types.PropertyGroup):
    name: StringProperty()
    selected: BoolProperty(default=True, update=lambda self, ctx: update_csv_analysis_store(ctx.scene) if getattr(ctx, "scene", None) else None)


class AnalysisItem(bpy.types.PropertyGroup):
    key: StringProperty()
    label: StringProperty()
    typology: StringProperty()
    enabled: BoolProperty(default=False)
    role: EnumProperty(items=[('Y', 'Metric', '')], default='Y')
