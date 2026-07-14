import argparse
import json
import math

import unreal


parser = argparse.ArgumentParser()
parser.add_argument("--map-path", required=True)
parser.add_argument("--report", required=True)
args = parser.parse_args()


TABLE_LAMP_MESH_LABEL = "Infinigen_DeskLampFactory_8507126__spawn_asset_7901138_"
MONITOR_MESH_LABEL = "Infinigen_MonitorFactory_1148210__spawn_asset_4488226_"
TABLE_LAMP_LIGHT_LABEL = "Infinigen189cc130_TableLamp_650lm_PointLight"


def as_dict(vector):
    return {"x": round(vector.x, 3), "y": round(vector.y, 3), "z": round(vector.z, 3)}


def json_value(value):
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    if hasattr(value, "name"):
        return value.name
    return str(value)


def get_prop(obj, name):
    try:
        return json_value(obj.get_editor_property(name))
    except Exception:
        return None


def set_prop(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception:
        return False


def component_by_class(actor, class_name):
    cls = getattr(unreal, class_name, None)
    if cls is None:
        return None
    try:
        return actor.get_component_by_class(cls)
    except Exception:
        return None


def light_component(actor):
    for class_name in (
        "PointLightComponent",
        "SpotLightComponent",
        "RectLightComponent",
        "DirectionalLightComponent",
        "SkyLightComponent",
        "LightComponent",
    ):
        component = component_by_class(actor, class_name)
        if component is not None:
            return component
    return None


def actor_by_label(label):
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if actor.get_actor_label() == label:
            return actor
    return None


def bounds(actor):
    origin, extent = actor.get_actor_bounds(False)
    return origin, extent


def bounds_entry(actor):
    origin, extent = bounds(actor)
    return {
        "label": actor.get_actor_label(),
        "origin": as_dict(origin),
        "extent": as_dict(extent),
        "min": as_dict(unreal.Vector(origin.x - extent.x, origin.y - extent.y, origin.z - extent.z)),
        "max": as_dict(unreal.Vector(origin.x + extent.x, origin.y + extent.y, origin.z + extent.z)),
    }


def distance(a, b):
    delta = a - b
    return math.sqrt(delta.x * delta.x + delta.y * delta.y + delta.z * delta.z)


if not unreal.EditorLoadingAndSavingUtils.load_map(args.map_path):
    raise RuntimeError(f"Failed to load map: {args.map_path}")

lamp = actor_by_label(TABLE_LAMP_MESH_LABEL)
monitor = actor_by_label(MONITOR_MESH_LABEL)
light = actor_by_label(TABLE_LAMP_LIGHT_LABEL)
if lamp is None:
    raise RuntimeError(f"Missing lamp actor: {TABLE_LAMP_MESH_LABEL}")
if monitor is None:
    raise RuntimeError(f"Missing monitor actor: {MONITOR_MESH_LABEL}")
if light is None:
    raise RuntimeError(f"Missing table lamp light actor: {TABLE_LAMP_LIGHT_LABEL}")

lamp_origin, lamp_extent = bounds(lamp)
monitor_origin, monitor_extent = bounds(monitor)

# Put the light on the lamp half farthest from the monitor and slightly forward
# of the lamp mesh. This keeps the source visually associated with the lamp, not
# the adjacent monitor face.
x_direction = 1.0 if lamp_origin.x >= monitor_origin.x else -1.0
y_direction = 1.0 if lamp_origin.y >= monitor_origin.y else -1.0
new_location = unreal.Vector(
    lamp_origin.x + x_direction * lamp_extent.x * 0.65,
    lamp_origin.y + y_direction * lamp_extent.y * 0.95,
    lamp_origin.z + lamp_extent.z * 0.78,
)

old_location = light.get_actor_location()
light.set_actor_location(new_location, False, False)
component = light_component(light)
if component is None:
    raise RuntimeError(f"Table lamp light has no light component: {TABLE_LAMP_LIGHT_LABEL}")

set_prop(component, "intensity", 650.0)
set_prop(component, "attenuation_radius", 500.0)
set_prop(component, "source_radius", 4.0)
set_prop(component, "soft_source_radius", 10.0)
set_prop(component, "indirect_lighting_intensity", 1.0)
set_prop(component, "visible", True)
set_prop(component, "affects_world", True)
set_prop(component, "cast_shadows", True)
set_prop(component, "cast_dynamic_shadows", True)

report = {
    "map_path": args.map_path,
    "lamp_bounds": bounds_entry(lamp),
    "monitor_bounds": bounds_entry(monitor),
    "light_label": light.get_actor_label(),
    "old_light_location": as_dict(old_location),
    "new_light_location": as_dict(light.get_actor_location()),
    "distance_to_lamp_origin": round(distance(light.get_actor_location(), lamp_origin), 3),
    "distance_to_monitor_origin": round(distance(light.get_actor_location(), monitor_origin), 3),
    "component": {
        "intensity": get_prop(component, "intensity"),
        "intensity_units": get_prop(component, "intensity_units"),
        "attenuation_radius": get_prop(component, "attenuation_radius"),
        "source_radius": get_prop(component, "source_radius"),
        "soft_source_radius": get_prop(component, "soft_source_radius"),
        "indirect_lighting_intensity": get_prop(component, "indirect_lighting_intensity"),
        "visible": get_prop(component, "visible"),
        "affects_world": get_prop(component, "affects_world"),
        "cast_shadows": get_prop(component, "cast_shadows"),
        "cast_dynamic_shadows": get_prop(component, "cast_dynamic_shadows"),
        "cast_raytraced_shadow": get_prop(component, "cast_raytraced_shadow"),
    },
}

saved = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
report["saved"] = bool(saved)

with open(args.report, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

unreal.log(f"Wrote repositioned table-lamp light report: {args.report}")
unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
