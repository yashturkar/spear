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

GENERATED_PREFIX = "Infinigen1dcacf23_"


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


def json_value(value):
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    if hasattr(value, "name"):
        return value.name
    return str(value)


def actor_class_name(actor):
    return actor.get_class().get_name()


def get_light_component(actor):
    for class_name in [
        "RectLightComponent",
        "PointLightComponent",
        "DirectionalLightComponent",
        "SkyLightComponent",
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
        return json_value(component.get_editor_property(name))
    except Exception:
        return None


def configure_component(
    component,
    intensity=None,
    attenuation_radius=None,
    source_width=None,
    source_height=None,
    source_radius=None,
    soft_source_radius=None,
    temperature=None,
    indirect=None,
    color=None,
):
    if intensity is not None:
        try_set(component, "intensity", float(intensity))
    if attenuation_radius is not None:
        try_set(component, "attenuation_radius", float(attenuation_radius))
    if source_width is not None:
        try_set(component, "source_width", float(source_width))
    if source_height is not None:
        try_set(component, "source_height", float(source_height))
    if source_radius is not None:
        try_set(component, "source_radius", float(source_radius))
    if soft_source_radius is not None:
        try_set(component, "soft_source_radius", float(soft_source_radius))
    if temperature is not None:
        try_set(component, "use_temperature", True)
        try_set(component, "temperature", float(temperature))
    if indirect is not None:
        try_set(component, "indirect_lighting_intensity", float(indirect))
    if color is not None:
        try_set(component, "light_color", color)
    try_set(component, "mobility", unreal.ComponentMobility.MOVABLE)
    try_set(component, "cast_shadows", True)
    try_set(component, "cast_dynamic_shadows", True)
    try_set(component, "cast_static_shadows", True)
    try_set(component, "cast_raytraced_shadow", True)


def is_light_actor(actor):
    return "Light" in actor_class_name(actor) or get_light_component(actor) is not None


def actor_bounds(actor):
    origin, extent = actor.get_actor_bounds(only_colliding_components=False)
    return {
        "origin": origin,
        "extent": extent,
        "min": unreal.Vector(origin.x - extent.x, origin.y - extent.y, origin.z - extent.z),
        "max": unreal.Vector(origin.x + extent.x, origin.y + extent.y, origin.z + extent.z),
    }


def bounds_to_dict(bounds):
    return {
        "origin": vector_to_dict(bounds["origin"]),
        "extent": vector_to_dict(bounds["extent"]),
        "min": vector_to_dict(bounds["min"]),
        "max": vector_to_dict(bounds["max"]),
    }


def find_static_mesh_actors(keyword):
    results = []
    keyword = keyword.lower()
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if actor_class_name(actor) != "StaticMeshActor":
            continue
        label = actor.get_actor_label()
        if keyword in label.lower():
            results.append(actor)
    return sorted(results, key=lambda actor: actor.get_actor_label())


def destroy_prior_generated_actors():
    destroyed = []
    for actor in list(unreal.EditorLevelLibrary.get_all_level_actors()):
        label = actor.get_actor_label()
        if label.startswith(GENERATED_PREFIX):
            destroyed.append(label)
            unreal.EditorLevelLibrary.destroy_actor(actor)
    return sorted(destroyed)


def tune_setup_lights():
    tuned = []
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        label = actor.get_actor_label()
        component = get_light_component(actor)
        if component is None:
            continue
        if label == "Setup_DirectionalLight":
            configure_component(component, intensity=0.0, indirect=0.0, temperature=5500.0)
            tuned.append({"label": label, "intensity": get_component_property(component, "intensity")})
        elif label == "Setup_SkyLight":
            configure_component(component, intensity=0.06, indirect=0.08)
            tuned.append({"label": label, "intensity": get_component_property(component, "intensity")})
    return tuned


def spawn_point_light(label, location, intensity=650.0):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.PointLight,
        location=location,
        rotation=unreal.Rotator(0.0, 0.0, 0.0),
    )
    actor.set_actor_label(label)
    component = get_light_component(actor)
    assert component is not None, f"No light component found on {label}"
    configure_component(
        component=component,
        intensity=intensity,
        attenuation_radius=340.0,
        source_radius=8.0,
        soft_source_radius=16.0,
        temperature=2700.0,
        indirect=0.35,
        color=unreal.LinearColor(1.0, 0.82, 0.58, 1.0),
    )
    return actor


def spawn_rect_light(label, location, rotation, intensity=950.0, width=58.0, height=58.0):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.RectLight,
        location=location,
        rotation=rotation,
    )
    actor.set_actor_label(label)
    component = get_light_component(actor)
    assert component is not None, f"No light component found on {label}"
    configure_component(
        component=component,
        intensity=intensity,
        attenuation_radius=720.0,
        source_width=width,
        source_height=height,
        temperature=3600.0,
        indirect=0.25,
        color=unreal.LinearColor(1.0, 0.9, 0.74, 1.0),
    )
    return actor


def spawn_directional_light(label):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.DirectionalLight,
        location=unreal.Vector(-900.0, 1950.0, 780.0),
        rotation=unreal.Rotator(-26.0, -42.0, 0.0),
    )
    actor.set_actor_label(label)
    component = get_light_component(actor)
    assert component is not None, f"No light component found on {label}"
    configure_component(
        component=component,
        intensity=2.0,
        temperature=5600.0,
        indirect=0.18,
        color=unreal.LinearColor(1.0, 0.93, 0.82, 1.0),
    )
    try_set(component, "use_atmosphere_sun_light", True)
    return actor


def spawn_sky_light(label):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.SkyLight,
        location=unreal.Vector(0.0, 0.0, 300.0),
        rotation=unreal.Rotator(0.0, 0.0, 0.0),
    )
    actor.set_actor_label(label)
    component = get_light_component(actor)
    assert component is not None, f"No light component found on {label}"
    configure_component(component=component, intensity=0.08, indirect=0.08)
    try_set(component, "real_time_capture", True)
    return actor


def spawn_sky_atmosphere(label):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.SkyAtmosphere,
        location=unreal.Vector(0.0, 0.0, 0.0),
        rotation=unreal.Rotator(0.0, 0.0, 0.0),
    )
    actor.set_actor_label(label)
    for component in actor.get_components_by_class(unreal.SkyAtmosphereComponent):
        try_set(component, "mobility", unreal.ComponentMobility.MOVABLE)
    return actor


def spawn_lights_from_meshes():
    spawned = []
    lamp_actors = find_static_mesh_actors("DeskLampFactory")
    ceiling_actors = find_static_mesh_actors("CeilingLightFactory")

    for index, actor in enumerate(lamp_actors):
        bounds = actor_bounds(actor)
        origin = bounds["origin"]
        extent = bounds["extent"]
        location = unreal.Vector(origin.x, origin.y, origin.z + extent.z * 0.25)
        spawned.append(spawn_point_light(f"{GENERATED_PREFIX}TableLamp_PointLight_{index}", location))

    for index, actor in enumerate(ceiling_actors):
        bounds = actor_bounds(actor)
        origin = bounds["origin"]
        extent = bounds["extent"]
        location = unreal.Vector(origin.x, origin.y, origin.z - max(8.0, extent.z * 0.2))
        spawned.append(spawn_rect_light(
            label=f"{GENERATED_PREFIX}Ceiling_RectLight_{index}",
            location=location,
            rotation=unreal.Rotator(-90.0, 0.0, 0.0),
        ))

    spawned.append(spawn_directional_light(f"{GENERATED_PREFIX}Sun_DirectionalLight"))
    spawned.append(spawn_sky_light(f"{GENERATED_PREFIX}Ambient_SkyLight"))
    spawned.append(spawn_sky_atmosphere(f"{GENERATED_PREFIX}SkyAtmosphere"))
    return spawned, lamp_actors, ceiling_actors


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
        for name in [
            "intensity",
            "attenuation_radius",
            "source_width",
            "source_height",
            "source_radius",
            "soft_source_radius",
            "temperature",
            "use_temperature",
            "indirect_lighting_intensity",
            "mobility",
            "cast_shadows",
            "cast_dynamic_shadows",
            "cast_raytraced_shadow",
        ]:
            detail[name] = get_component_property(component, name)
    return detail


def count_mesh_assets():
    if not unreal.EditorAssetLibrary.does_directory_exist(directory_path=args.mesh_dir):
        return 0
    count = 0
    for asset_path in unreal.EditorAssetLibrary.list_assets(directory_path=args.mesh_dir, recursive=True, include_folder=False):
        asset = unreal.load_asset(name=asset_path)
        if isinstance(asset, unreal.StaticMesh):
            count += 1
    return count


def compute_static_mesh_bounds(static_mesh_actors):
    bounds_min = None
    bounds_max = None
    for actor in static_mesh_actors:
        bounds = actor_bounds(actor)
        current_min = bounds["min"]
        current_max = bounds["max"]
        if bounds_min is None:
            bounds_min = unreal.Vector(current_min.x, current_min.y, current_min.z)
            bounds_max = unreal.Vector(current_max.x, current_max.y, current_max.z)
        else:
            bounds_min.x = min(bounds_min.x, current_min.x)
            bounds_min.y = min(bounds_min.y, current_min.y)
            bounds_min.z = min(bounds_min.z, current_min.z)
            bounds_max.x = max(bounds_max.x, current_max.x)
            bounds_max.y = max(bounds_max.y, current_max.y)
            bounds_max.z = max(bounds_max.z, current_max.z)
    return bounds_min, bounds_max


def actor_bounds_report(actors):
    return [
        {
            "label": actor.get_actor_label(),
            "class": actor_class_name(actor),
            "bounds": bounds_to_dict(actor_bounds(actor)),
        }
        for actor in actors
    ]


def write_report(destroyed_labels, tuned_setup_lights, spawned, lamp_actors, ceiling_actors, saved):
    actors = list(unreal.EditorLevelLibrary.get_all_level_actors())
    static_mesh_actors = [actor for actor in actors if actor_class_name(actor) == "StaticMeshActor"]
    light_actors = [actor for actor in actors if is_light_actor(actor)]
    window_actors = find_static_mesh_actors("WindowFactory")
    door_actors = find_static_mesh_actors("DoorFactory")
    bounds_min, bounds_max = compute_static_mesh_bounds(static_mesh_actors)
    spawned_details = sorted([light_detail(actor) for actor in spawned], key=lambda item: item["label"])
    sky_atmosphere_actors = [
        actor
        for actor in actors
        if actor_class_name(actor) == "SkyAtmosphere"
    ]

    report = {
        "map_path": args.map_path,
        "mesh_dir": args.mesh_dir,
        "map_exists": unreal.EditorAssetLibrary.does_asset_exist(asset_path=args.map_path),
        "saved": bool(saved),
        "mesh_asset_count": count_mesh_assets(),
        "static_mesh_actor_count": len(static_mesh_actors),
        "light_actor_count": len(light_actors),
        "destroyed_generated_actor_count": len(destroyed_labels),
        "destroyed_generated_actor_labels": destroyed_labels,
        "tuned_setup_lights": tuned_setup_lights,
        "matched_table_lamp_count": len(lamp_actors),
        "matched_table_lamps": actor_bounds_report(lamp_actors),
        "matched_ceiling_light_count": len(ceiling_actors),
        "matched_ceiling_lights": actor_bounds_report(ceiling_actors),
        "matched_window_count": len(window_actors),
        "matched_door_count": len(door_actors),
        "spawned_light_count": len(spawned_details),
        "spawned_lights": spawned_details,
        "spawned_light_labels": [item["label"] for item in spawned_details],
        "sky_atmosphere_actor_count": len(sky_atmosphere_actors),
        "sky_atmosphere_labels": sorted(actor.get_actor_label() for actor in sky_atmosphere_actors),
        "bounds_min": vector_to_dict(bounds_min),
        "bounds_max": vector_to_dict(bounds_max),
        "lighting_note": (
            "Imported original Infinigen fine blend export and added movable physical-light approximations: "
            "warm point lights at both DeskLampFactory meshes, warm rect lights at all CeilingLightFactory meshes, "
            "a low-angle sun directional light for window/door daylight, a SkyAtmosphere component for the atmosphere sun, "
            "and a low ambient skylight. "
            "Runtime scene-light-intensity-scale can still dim these scene lights for flashlight tests."
        ),
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
    spawned_lights, lamp_meshes, ceiling_meshes = spawn_lights_from_meshes()
    assert len(lamp_meshes) >= 2, f"Expected at least 2 desk lamps, found {len(lamp_meshes)}"
    assert len(ceiling_meshes) >= 4, f"Expected at least 4 ceiling light meshes, found {len(ceiling_meshes)}"

    saved_level = level_editor_subsystem.save_current_level()
    assert saved_level, f"Could not save level: {args.map_path}"
    unreal.EditorAssetLibrary.save_directory(directory_path=posixpath.dirname(args.map_path), only_if_is_dirty=False, recursive=True)
    write_report(
        destroyed_labels=destroyed,
        tuned_setup_lights=tuned,
        spawned=spawned_lights,
        lamp_actors=lamp_meshes,
        ceiling_actors=ceiling_meshes,
        saved=saved_level,
    )
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
