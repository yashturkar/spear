import argparse
import json
import os
import posixpath

import unreal


parser = argparse.ArgumentParser()
parser.add_argument("--map-path", required=True)
parser.add_argument("--mesh-dir", required=True)
parser.add_argument("--validation-report", required=True)
args = parser.parse_args()


def try_set(obj, name, value):
    try:
        obj.set_editor_property(name=name, value=value)
        return True
    except Exception as exc:
        unreal.log_warning(f"Could not set {obj.get_class().get_name()}.{name}: {exc}")
        return False


def vector_to_dict(vector):
    if vector is None:
        return None
    return {"x": round(vector.x, 3), "y": round(vector.y, 3), "z": round(vector.z, 3)}


def rotation_to_dict(rotator):
    return {
        "pitch": round(rotator.pitch, 3),
        "yaw": round(rotator.yaw, 3),
        "roll": round(rotator.roll, 3),
    }


def value_to_json(value):
    if hasattr(value, "name"):
        return value.name
    return str(value)


def get_light_component(actor):
    for class_name in [
        "RectLightComponent",
        "DirectionalLightComponent",
        "SkyLightComponent",
        "PointLightComponent",
        "SpotLightComponent",
        "LightComponent",
    ]:
        component_class = getattr(unreal, class_name, None)
        if component_class is None:
            continue
        try:
            component = actor.get_component_by_class(component_class)
            if component is not None:
                return component
        except Exception:
            pass
    return None


def get_component_property(component, name):
    try:
        value = component.get_editor_property(name)
        if isinstance(value, (int, float, str, bool)) or value is None:
            return value
        return value_to_json(value)
    except Exception:
        return None


def actor_class_name(actor):
    return actor.get_class().get_name()


def is_light_actor(actor):
    return "Light" in actor_class_name(actor) or get_light_component(actor) is not None


def configure_component(component, intensity=None, attenuation_radius=None, source_width=None, source_height=None, temperature=None, indirect=None):
    if intensity is not None:
        try_set(component, "intensity", float(intensity))
    if attenuation_radius is not None:
        try_set(component, "attenuation_radius", float(attenuation_radius))
    if source_width is not None:
        try_set(component, "source_width", float(source_width))
    if source_height is not None:
        try_set(component, "source_height", float(source_height))
    if temperature is not None:
        try_set(component, "use_temperature", True)
        try_set(component, "temperature", float(temperature))
    if indirect is not None:
        try_set(component, "indirect_lighting_intensity", float(indirect))
    try_set(component, "mobility", unreal.ComponentMobility.MOVABLE)


def tune_setup_lights():
    tuned = []
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        label = actor.get_actor_label()
        component = get_light_component(actor)
        if component is None:
            continue
        if label == "Setup_DirectionalLight":
            configure_component(
                component=component,
                intensity=0.12,
                temperature=4000.0,
                indirect=0.02,
            )
            tuned.append({"label": label, "intensity": get_component_property(component, "intensity")})
        elif label == "Setup_SkyLight":
            configure_component(
                component=component,
                intensity=0.02,
                indirect=0.02,
            )
            tuned.append({"label": label, "intensity": get_component_property(component, "intensity")})
    return tuned


def destroy_prior_generated_actors():
    destroyed = []
    for actor in list(unreal.EditorLevelLibrary.get_all_level_actors()):
        label = actor.get_actor_label()
        if label.startswith("InfinigenKitchen_"):
            destroyed.append(label)
            unreal.EditorLevelLibrary.destroy_actor(actor)
    return sorted(destroyed)


def spawn_rect_light(label, location):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.RectLight,
        location=unreal.Vector(*location),
        rotation=unreal.Rotator(-90.0, 0.0, 0.0),
    )
    actor.set_actor_label(label)
    component = get_light_component(actor)
    assert component is not None, f"No light component found on {label}"
    configure_component(
        component=component,
        intensity=1400.0,
        attenuation_radius=700.0,
        source_width=160.0,
        source_height=24.0,
        temperature=4000.0,
        indirect=0.25,
    )
    return actor


def spawn_bright_ceiling_lights():
    xs = [-450.0, -87.5, 275.0, 637.5, 1000.0]
    ys = [-1450.0, 250.0]
    spawned = []
    for y in ys:
        for x in xs:
            index = len(spawned)
            spawned.append(spawn_rect_light(
                label=f"InfinigenKitchen_BrightCeiling_RectLight_{index}",
                location=(x, y, 315.0),
            ))
    return spawned


def light_detail(actor):
    component = get_light_component(actor)
    detail = {
        "label": actor.get_actor_label(),
        "class": actor_class_name(actor),
        "component_class": component.get_class().get_name() if component else None,
        "location": vector_to_dict(actor.get_actor_location()),
        "rotation": rotation_to_dict(actor.get_actor_rotation()),
    }
    if component is not None:
        detail.update({
            "intensity": get_component_property(component, "intensity"),
            "attenuation_radius": get_component_property(component, "attenuation_radius"),
            "source_width": get_component_property(component, "source_width"),
            "source_height": get_component_property(component, "source_height"),
            "mobility": get_component_property(component, "mobility"),
            "use_temperature": get_component_property(component, "use_temperature"),
            "temperature": get_component_property(component, "temperature"),
            "indirect_lighting_intensity": get_component_property(component, "indirect_lighting_intensity"),
        })
    return detail


def compute_static_mesh_bounds(static_mesh_actors):
    bounds_min = None
    bounds_max = None
    for actor in static_mesh_actors:
        origin, extent = actor.get_actor_bounds(only_colliding_components=False)
        current_min = unreal.Vector(origin.x - extent.x, origin.y - extent.y, origin.z - extent.z)
        current_max = unreal.Vector(origin.x + extent.x, origin.y + extent.y, origin.z + extent.z)
        if bounds_min is None:
            bounds_min = current_min
            bounds_max = current_max
        else:
            bounds_min.x = min(bounds_min.x, current_min.x)
            bounds_min.y = min(bounds_min.y, current_min.y)
            bounds_min.z = min(bounds_min.z, current_min.z)
            bounds_max.x = max(bounds_max.x, current_max.x)
            bounds_max.y = max(bounds_max.y, current_max.y)
            bounds_max.z = max(bounds_max.z, current_max.z)
    return bounds_min, bounds_max


def count_mesh_assets():
    if not unreal.EditorAssetLibrary.does_directory_exist(directory_path=args.mesh_dir):
        return 0
    count = 0
    for asset_path in unreal.EditorAssetLibrary.list_assets(directory_path=args.mesh_dir, recursive=True, include_folder=False):
        asset = unreal.load_asset(name=asset_path)
        if isinstance(asset, unreal.StaticMesh):
            count += 1
    return count


def write_report(destroyed_labels, spawned, tuned_setup_lights, saved):
    actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
    static_mesh_actors = [actor for actor in actors if actor_class_name(actor) == "StaticMeshActor"]
    light_actors = [actor for actor in actors if is_light_actor(actor)]
    bounds_min, bounds_max = compute_static_mesh_bounds(static_mesh_actors)
    spawned_details = sorted([light_detail(actor) for actor in spawned], key=lambda item: item["label"])
    report = {
        "map_path": args.map_path,
        "mesh_dir": args.mesh_dir,
        "map_exists": unreal.EditorAssetLibrary.does_asset_exist(asset_path=args.map_path),
        "saved": bool(saved),
        "destroyed_infinigen_kitchen_actor_count": len(destroyed_labels),
        "destroyed_infinigen_kitchen_actor_labels": destroyed_labels,
        "spawned_bright_ceiling_light_count": len(spawned_details),
        "spawned_bright_ceiling_lights": spawned_details,
        "spawned_bright_ceiling_light_labels": [item["label"] for item in spawned_details],
        "tuned_setup_lights": tuned_setup_lights,
        "static_mesh_actor_count": len(static_mesh_actors),
        "mesh_asset_count": count_mesh_assets(),
        "light_actor_count": len(light_actors),
        "light_labels": sorted([actor.get_actor_label() for actor in light_actors]),
        "bounds_min": vector_to_dict(bounds_min),
        "bounds_max": vector_to_dict(bounds_max),
    }
    os.makedirs(os.path.dirname(args.validation_report), exist_ok=True)
    with open(args.validation_report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    unreal.log(f"Wrote validation report: {args.validation_report}")
    unreal.log(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    level_editor_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    loaded = level_editor_subsystem.load_level(asset_path=args.map_path)
    assert loaded, f"Could not load level: {args.map_path}"
    destroyed = destroy_prior_generated_actors()
    tuned = tune_setup_lights()
    spawned_lights = spawn_bright_ceiling_lights()
    saved_level = level_editor_subsystem.save_current_level()
    assert saved_level, f"Could not save current level: {args.map_path}"
    unreal.EditorAssetLibrary.save_directory(directory_path=posixpath.dirname(args.map_path), only_if_is_dirty=False, recursive=True)
    write_report(destroyed_labels=destroyed, spawned=spawned_lights, tuned_setup_lights=tuned, saved=saved_level)
