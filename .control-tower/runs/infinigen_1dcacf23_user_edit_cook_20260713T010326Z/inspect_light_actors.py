import argparse
import json

import unreal


parser = argparse.ArgumentParser()
parser.add_argument("--map-path", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()


def load_map(map_path):
    if not unreal.EditorLoadingAndSavingUtils.load_map(map_path):
        raise RuntimeError(f"Failed to load map: {map_path}")


def get_component(actor, class_name):
    cls = getattr(unreal, class_name, None)
    if cls is None:
        return None
    try:
        return actor.get_component_by_class(cls)
    except Exception:
        return None


def get_light_component(actor):
    for class_name in (
        "RectLightComponent",
        "PointLightComponent",
        "DirectionalLightComponent",
        "SkyLightComponent",
        "SpotLightComponent",
        "LightComponent",
    ):
        comp = get_component(actor, class_name)
        if comp is not None:
            return comp
    return None


def prop(obj, name):
    try:
        value = obj.get_editor_property(name)
    except Exception as exc:
        return {"error": str(exc)}
    if hasattr(value, "name"):
        return value.name
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        return {
            "x": round(float(value.x), 3),
            "y": round(float(value.y), 3),
            "z": round(float(value.z), 3),
        }
    return value if isinstance(value, (str, int, float, bool)) or value is None else str(value)


def vector(v):
    return {"x": round(v.x, 3), "y": round(v.y, 3), "z": round(v.z, 3)}


load_map(args.map_path)
report = {"map_path": args.map_path, "light_actors": [], "ceiling_mesh_actors": []}

for actor in unreal.EditorLevelLibrary.get_all_level_actors():
    label = actor.get_actor_label()
    cls = actor.get_class().get_name()
    comp = get_light_component(actor)
    if comp is not None or "Light" in cls:
        root = actor.get_root_component()
        report["light_actors"].append(
            {
                "label": label,
                "class": cls,
                "actor_hidden": actor.is_hidden_ed(),
                "location": vector(actor.get_actor_location()),
                "component_class": comp.get_class().get_name() if comp else None,
                "component_visible": prop(comp, "visible") if comp else None,
                "intensity": prop(comp, "intensity") if comp else None,
                "indirect_lighting_intensity": prop(comp, "indirect_lighting_intensity") if comp else None,
                "affects_world": prop(comp, "affects_world") if comp else None,
                "cast_shadows": prop(comp, "cast_shadows") if comp else None,
                "mobility": prop(comp, "mobility") if comp else None,
                "root_visible": prop(root, "visible") if root else None,
            }
        )
    if "CeilingLight" in label:
        sm = get_component(actor, "StaticMeshComponent")
        report["ceiling_mesh_actors"].append(
            {
                "label": label,
                "class": cls,
                "actor_hidden": actor.is_hidden_ed(),
                "location": vector(actor.get_actor_location()),
                "component_visible": prop(sm, "visible") if sm else None,
                "static_mesh": str(prop(sm, "static_mesh")) if sm else None,
            }
        )

report["light_actors"].sort(key=lambda x: x["label"])
report["ceiling_mesh_actors"].sort(key=lambda x: x["label"])
with open(args.output, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)
unreal.log(f"Wrote light actor report: {args.output}")
unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
