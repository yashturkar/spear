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


def vector_to_dict(vector):
    return {"x": round(vector.x, 3), "y": round(vector.y, 3), "z": round(vector.z, 3)}


def try_set(obj, name, value):
    try:
        obj.set_editor_property(name=name, value=value)
        return True
    except Exception as exc:
        unreal.log_warning(f"Could not set {obj.get_class().get_name()}.{name}: {exc}")
        return False


def get_light_component(actor):
    for class_name in ["RectLightComponent", "PointLightComponent", "SpotLightComponent", "DirectionalLightComponent", "SkyLightComponent", "LightComponent"]:
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


def configure_light(actor, intensity, color, attenuation_radius=None, source_width=None, source_height=None, indirect=0.12):
    component = get_light_component(actor)
    assert component is not None, f"No light component found on {actor.get_actor_label()}"
    try_set(component, "intensity", intensity)
    try_set(component, "light_color", color)
    try_set(component, "use_temperature", True)
    try_set(component, "temperature", 3150.0)
    try_set(component, "indirect_lighting_intensity", indirect)
    if attenuation_radius is not None:
        try_set(component, "attenuation_radius", attenuation_radius)
    if source_width is not None:
        try_set(component, "source_width", source_width)
    if source_height is not None:
        try_set(component, "source_height", source_height)
    try_set(component, "mobility", unreal.ComponentMobility.MOVABLE)
    return component


def tune_setup_lights():
    tuned = []
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        label = actor.get_actor_label()
        component = get_light_component(actor)
        if component is None:
            continue
        if label == "Setup_DirectionalLight":
            configure_light(actor, 0.18, unreal.LinearColor(1.0, 0.88, 0.72, 1.0), indirect=0.03)
            tuned.append(label)
        elif label == "Setup_SkyLight":
            try_set(component, "intensity", 0.03)
            try_set(component, "mobility", unreal.ComponentMobility.MOVABLE)
            tuned.append(label)
    return tuned


def destroy_prior_generated_lights():
    for actor in list(unreal.EditorLevelLibrary.get_all_level_actors()):
        if actor.get_actor_label().startswith("RestaurantKitchen_"):
            unreal.EditorLevelLibrary.destroy_actor(actor)


def spawn_rect_light(label, location, rotation, intensity, width, height):
    actor_class = getattr(unreal, "RectLight", None)
    if actor_class is None:
        actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            actor_class=unreal.PointLight,
            location=unreal.Vector(*location),
            rotation=unreal.Rotator(0.0, 0.0, 0.0),
        )
        actor.set_actor_label(label)
        configure_light(actor, intensity, unreal.LinearColor(1.0, 0.84, 0.62, 1.0), attenuation_radius=430.0)
        return actor
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=actor_class,
        location=unreal.Vector(*location),
        rotation=unreal.Rotator(*rotation),
    )
    actor.set_actor_label(label)
    configure_light(
        actor=actor,
        intensity=intensity,
        color=unreal.LinearColor(1.0, 0.84, 0.62, 1.0),
        attenuation_radius=430.0,
        source_width=width,
        source_height=height,
        indirect=0.10,
    )
    return actor


def spawn_dim_fixture_lights():
    spawned = []
    for i, x in enumerate([-310.0, -105.0, 105.0, 310.0]):
        spawned.append(spawn_rect_light(
            label=f"RestaurantKitchen_DimLinearPrep_RectLight_{i}",
            location=(x, -55.0, 300.0),
            rotation=(-90.0, 0.0, 0.0),
            intensity=115.0,
            width=145.0,
            height=18.0,
        ))
    for i, y in enumerate([-340.0, 340.0]):
        spawned.append(spawn_rect_light(
            label=f"RestaurantKitchen_DimService_RectLight_{i}",
            location=(0.0, y, 300.0),
            rotation=(-90.0, 0.0, 0.0),
            intensity=80.0,
            width=120.0,
            height=16.0,
        ))
    spawned.append(spawn_rect_light(
        label="RestaurantKitchen_WarmPassHeatLamp_RectLight",
        location=(95.0, -438.0, 182.0),
        rotation=(0.0, 0.0, 0.0),
        intensity=55.0,
        width=235.0,
        height=12.0,
    ))
    return spawned


def actor_class_name(actor):
    return actor.get_class().get_name()


def is_light_actor(actor):
    return "Light" in actor_class_name(actor) or get_light_component(actor) is not None


def count_light_components(actors):
    count = 0
    details = []
    for actor in actors:
        component = get_light_component(actor)
        if component is not None:
            count += 1
            details.append({
                "label": actor.get_actor_label(),
                "class": actor_class_name(actor),
                "component_class": component.get_class().get_name(),
                "location": vector_to_dict(actor.get_actor_location()),
            })
    return count, sorted(details, key=lambda item: item["label"])


def make_report(spawned, tuned_setup_lights):
    actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
    static_mesh_actors = [actor for actor in actors if actor_class_name(actor) == "StaticMeshActor"]
    light_actors = [actor for actor in actors if is_light_actor(actor)]
    light_component_count, light_details = count_light_components(actors)
    asset_count = 0
    if unreal.EditorAssetLibrary.does_directory_exist(directory_path=args.mesh_dir):
        for asset_path in unreal.EditorAssetLibrary.list_assets(directory_path=args.mesh_dir, recursive=True, include_folder=False):
            asset = unreal.load_asset(name=asset_path)
            if isinstance(asset, unreal.StaticMesh):
                asset_count += 1

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

    report = {
        "map_path": args.map_path,
        "mesh_dir": args.mesh_dir,
        "map_exists": unreal.EditorAssetLibrary.does_asset_exist(asset_path=args.map_path),
        "mesh_asset_count": asset_count,
        "static_mesh_actor_count": len(static_mesh_actors),
        "light_actor_count": len(light_actors),
        "light_component_count": light_component_count,
        "spawned_fixture_light_labels": [actor.get_actor_label() for actor in spawned],
        "tuned_setup_light_labels": tuned_setup_lights,
        "light_details": light_details,
        "bounds_min": vector_to_dict(bounds_min) if bounds_min is not None else None,
        "bounds_max": vector_to_dict(bounds_max) if bounds_max is not None else None,
        "lighting_note": "Added low-intensity movable RectLight fixtures and reduced setup directional/skylight for dim live flashlight validation. Use scene-light-intensity-scale to tune lower at runtime.",
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
    destroy_prior_generated_lights()
    tuned = tune_setup_lights()
    spawned_lights = spawn_dim_fixture_lights()
    saved = level_editor_subsystem.save_current_level()
    assert saved, f"Could not save level: {args.map_path}"
    unreal.EditorAssetLibrary.save_directory(directory_path=posixpath.dirname(args.map_path), only_if_is_dirty=False, recursive=True)
    make_report(spawned=spawned_lights, tuned_setup_lights=tuned)
