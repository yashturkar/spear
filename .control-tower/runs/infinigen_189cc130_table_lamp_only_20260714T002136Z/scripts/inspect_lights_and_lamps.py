import argparse
import json

import unreal


parser = argparse.ArgumentParser()
parser.add_argument("--map-path", required=True)
parser.add_argument("--report", required=True)
args = parser.parse_args()


LIGHT_COMPONENT_CLASSES = [
    "PointLightComponent",
    "SpotLightComponent",
    "RectLightComponent",
    "DirectionalLightComponent",
    "SkyLightComponent",
    "LightComponent",
]


def as_dict(vector):
    return {"x": round(vector.x, 3), "y": round(vector.y, 3), "z": round(vector.z, 3)}


def value(obj, name):
    try:
        result = obj.get_editor_property(name)
    except Exception:
        return None
    if hasattr(result, "name"):
        return result.name
    return result


def component_by_class(actor, class_name):
    cls = getattr(unreal, class_name, None)
    if cls is None:
        return None
    try:
        return actor.get_component_by_class(cls)
    except Exception:
        return None


def light_component(actor):
    for class_name in LIGHT_COMPONENT_CLASSES:
        component = component_by_class(actor, class_name)
        if component is not None:
            return component
    return None


if not unreal.EditorLoadingAndSavingUtils.load_map(args.map_path):
    raise RuntimeError(f"Failed to load map: {args.map_path}")

report = {
    "map_path": args.map_path,
    "lights": [],
    "lamp_like_actors": [],
    "player_starts": [],
}

for actor in unreal.EditorLevelLibrary.get_all_level_actors():
    label = actor.get_actor_label()
    class_name = actor.get_class().get_name()
    location = actor.get_actor_location()
    component = light_component(actor)

    if component is not None or "Light" in class_name:
        report["lights"].append(
            {
                "label": label,
                "class": class_name,
                "component_class": component.get_class().get_name() if component is not None else None,
                "location": as_dict(location),
                "hidden_in_game": actor.is_hidden_ed(),
                "intensity": value(component, "intensity") if component is not None else None,
                "intensity_units": value(component, "intensity_units") if component is not None else None,
                "attenuation_radius": value(component, "attenuation_radius") if component is not None else None,
                "indirect_lighting_intensity": value(component, "indirect_lighting_intensity") if component is not None else None,
                "visible": value(component, "visible") if component is not None else None,
                "affects_world": value(component, "affects_world") if component is not None else None,
                "cast_shadows": value(component, "cast_shadows") if component is not None else None,
                "cast_dynamic_shadows": value(component, "cast_dynamic_shadows") if component is not None else None,
                "cast_raytraced_shadow": value(component, "cast_raytraced_shadow") if component is not None else None,
            }
        )

    lowered = label.lower()
    if any(token in lowered for token in ("lamp", "tablelamp", "table_lamp", "desk", "light")):
        origin, extent = actor.get_actor_bounds(False)
        report["lamp_like_actors"].append(
            {
                "label": label,
                "class": class_name,
                "location": as_dict(location),
                "bounds_origin": as_dict(origin),
                "bounds_extent": as_dict(extent),
                "has_light_component": component is not None,
            }
        )

    if class_name == "PlayerStart" or label == "PlayerStart":
        report["player_starts"].append(
            {
                "label": label,
                "class": class_name,
                "location": as_dict(location),
                "rotation": {
                    "pitch": actor.get_actor_rotation().pitch,
                    "yaw": actor.get_actor_rotation().yaw,
                    "roll": actor.get_actor_rotation().roll,
                },
            }
        )

with open(args.report, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

unreal.log(f"Wrote light/lamp inspection report: {args.report}")
unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
