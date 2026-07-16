import argparse
import json

import unreal


parser = argparse.ArgumentParser()
parser.add_argument("--map-path", required=True)
parser.add_argument("--report", required=True)
args = parser.parse_args()


SPAWN_LOCATION = unreal.Vector(325.0, -1425.0, 120.0)
SPAWN_ROTATION = unreal.Rotator(0.0, 180.0, 0.0)


def as_dict(vector):
    return {"x": round(vector.x, 3), "y": round(vector.y, 3), "z": round(vector.z, 3)}


def get_component(actor, class_name):
    cls = getattr(unreal, class_name, None)
    if cls is None:
        return None
    try:
        return actor.get_component_by_class(cls)
    except Exception:
        return None


def set_prop(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception:
        return False


def call_if_exists(obj, name, *args):
    fn = getattr(obj, name, None)
    if fn is None:
        return False
    try:
        fn(*args)
        return True
    except Exception:
        return False


if not unreal.EditorLoadingAndSavingUtils.load_map(args.map_path):
    raise RuntimeError(f"Failed to load map: {args.map_path}")

report = {
    "map_path": args.map_path,
    "spawn_location": as_dict(SPAWN_LOCATION),
    "spawn_rotation": {"pitch": SPAWN_ROTATION.pitch, "yaw": SPAWN_ROTATION.yaw, "roll": SPAWN_ROTATION.roll},
    "player_starts": [],
    "disabled_ceiling_light_actors": [],
    "disabled_ceiling_fixture_meshes": [],
}

for actor in unreal.EditorLevelLibrary.get_all_level_actors():
    label = actor.get_actor_label()
    class_name = actor.get_class().get_name()

    if class_name == "PlayerStart" or label == "PlayerStart":
        old_location = actor.get_actor_location()
        old_rotation = actor.get_actor_rotation()
        actor.set_actor_location(SPAWN_LOCATION, False, False)
        actor.set_actor_rotation(SPAWN_ROTATION, False)
        report["player_starts"].append(
            {
                "label": label,
                "class": class_name,
                "old_location": as_dict(old_location),
                "new_location": as_dict(actor.get_actor_location()),
                "old_rotation": {"pitch": old_rotation.pitch, "yaw": old_rotation.yaw, "roll": old_rotation.roll},
                "new_rotation": {
                    "pitch": actor.get_actor_rotation().pitch,
                    "yaw": actor.get_actor_rotation().yaw,
                    "roll": actor.get_actor_rotation().roll,
                },
            }
        )

    if label.startswith("Infinigen1dcacf23_Ceiling_RectLight"):
        light_component = (
            get_component(actor, "RectLightComponent")
            or get_component(actor, "LightComponent")
        )
        actor.set_is_temporarily_hidden_in_editor(True)
        actor.set_actor_hidden_in_game(True)
        entry = {"label": label, "class": class_name, "location": as_dict(actor.get_actor_location())}
        if light_component is not None:
            call_if_exists(light_component, "set_visibility", False, True)
            call_if_exists(light_component, "SetVisibility", False, True)
            set_prop(light_component, "visible", False)
            set_prop(light_component, "intensity", 0.0)
            set_prop(light_component, "indirect_lighting_intensity", 0.0)
            set_prop(light_component, "affects_world", False)
            set_prop(light_component, "cast_shadows", False)
            entry["component_class"] = light_component.get_class().get_name()
            for prop_name in ("visible", "intensity", "indirect_lighting_intensity", "affects_world", "cast_shadows"):
                try:
                    value = light_component.get_editor_property(prop_name)
                    entry[prop_name] = value.name if hasattr(value, "name") else value
                except Exception as exc:
                    entry[prop_name] = f"unreadable: {exc}"
        report["disabled_ceiling_light_actors"].append(entry)

    if "CeilingLightFactory" in label:
        mesh_component = get_component(actor, "StaticMeshComponent")
        actor.set_is_temporarily_hidden_in_editor(True)
        actor.set_actor_hidden_in_game(True)
        entry = {"label": label, "class": class_name, "location": as_dict(actor.get_actor_location())}
        if mesh_component is not None:
            call_if_exists(mesh_component, "set_visibility", False, True)
            call_if_exists(mesh_component, "SetVisibility", False, True)
            set_prop(mesh_component, "visible", False)
            entry["component_class"] = mesh_component.get_class().get_name()
            try:
                entry["visible"] = mesh_component.get_editor_property("visible")
            except Exception as exc:
                entry["visible"] = f"unreadable: {exc}"
        report["disabled_ceiling_fixture_meshes"].append(entry)

if not report["player_starts"]:
    raise RuntimeError("No PlayerStart actor found to reposition")

saved = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
report["saved"] = bool(saved)

with open(args.report, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

unreal.log(f"Wrote fix report: {args.report}")
unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
