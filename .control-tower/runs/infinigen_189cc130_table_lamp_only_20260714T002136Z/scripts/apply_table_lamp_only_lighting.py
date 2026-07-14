import argparse
import json
import math

import unreal


parser = argparse.ArgumentParser()
parser.add_argument("--map-path", required=True)
parser.add_argument("--report", required=True)
args = parser.parse_args()


GENERATED_PREFIX = "Infinigen189cc130_"
TABLE_LAMP_MESH_LABEL = "Infinigen_DeskLampFactory_8507126__spawn_asset_7901138_"
TABLE_LAMP_LIGHT_LABEL = f"{GENERATED_PREFIX}TableLamp_650lm_PointLight"
SPAWN_LABEL = "Setup_PlayerStart"
SPAWN_LOCATION = unreal.Vector(300.0, -1000.0, 120.0)
SPAWN_TARGET = unreal.Vector(369.27, -1243.399, 115.0)


def as_dict(vector):
    return {"x": round(vector.x, 3), "y": round(vector.y, 3), "z": round(vector.z, 3)}


def rot_dict(rotator):
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


def set_prop(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception as exc:
        unreal.log_warning(f"Could not set {obj.get_class().get_name()}.{name}: {exc}")
        return False


def get_prop(obj, name):
    try:
        return json_value(obj.get_editor_property(name))
    except Exception:
        return None


def call_if_exists(obj, name, *call_args):
    fn = getattr(obj, name, None)
    if fn is None:
        return False
    try:
        fn(*call_args)
        return True
    except Exception:
        return False


def make_rotator(pitch=0.0, yaw=0.0, roll=0.0):
    rotator = unreal.Rotator()
    rotator.pitch = float(pitch)
    rotator.yaw = float(yaw)
    rotator.roll = float(roll)
    return rotator


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


def mesh_component(actor):
    return component_by_class(actor, "StaticMeshComponent")


def actor_class_name(actor):
    return actor.get_class().get_name()


def destroy_prior_generated_actors():
    destroyed = []
    for actor in list(unreal.EditorLevelLibrary.get_all_level_actors()):
        label = actor.get_actor_label()
        if label.startswith(GENERATED_PREFIX):
            destroyed.append(label)
            unreal.EditorLevelLibrary.destroy_actor(actor)
    return sorted(destroyed)


def disable_light_actor(actor):
    component = light_component(actor)
    entry = {
        "label": actor.get_actor_label(),
        "class": actor_class_name(actor),
        "location": as_dict(actor.get_actor_location()),
        "component_class": component.get_class().get_name() if component is not None else None,
    }
    actor.set_actor_hidden_in_game(True)
    actor.set_is_temporarily_hidden_in_editor(True)
    if component is not None:
        call_if_exists(component, "set_visibility", False, True)
        call_if_exists(component, "SetVisibility", False, True)
        for name, value in (
            ("visible", False),
            ("intensity", 0.0),
            ("indirect_lighting_intensity", 0.0),
            ("affects_world", False),
            ("cast_shadows", False),
            ("cast_dynamic_shadows", False),
            ("cast_static_shadows", False),
        ):
            set_prop(component, name, value)
        for name in (
            "visible",
            "intensity",
            "indirect_lighting_intensity",
            "affects_world",
            "cast_shadows",
            "cast_dynamic_shadows",
        ):
            entry[name] = get_prop(component, name)
    return entry


def yaw_toward(start, target):
    delta = target - start
    return math.degrees(math.atan2(delta.y, delta.x))


def raytraced_shadow_enabled_value():
    for enum_name in ("CastRayTracedShadow", "ECastRayTracedShadow"):
        enum_cls = getattr(unreal, enum_name, None)
        if enum_cls is None:
            continue
        for member in ("ENABLED", "Enabled", "CAST_RAY_TRACED_SHADOW_ENABLED"):
            if hasattr(enum_cls, member):
                return getattr(enum_cls, member)
    return None


def set_raytraced_shadow_enabled(component):
    enum_value = raytraced_shadow_enabled_value()
    candidates = []
    if enum_value is not None:
        candidates.append(enum_value)
    candidates.extend(("ENABLED", "Enabled", 2))

    for candidate in candidates:
        if set_prop(component, "cast_raytraced_shadow", candidate):
            return True
    return False


def ensure_player_start():
    existing = []
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if actor_class_name(actor) == "PlayerStart" or actor.get_actor_label() == SPAWN_LABEL:
            existing.append(actor)
    if existing:
        player_start = existing[0]
    else:
        player_start = unreal.EditorLevelLibrary.spawn_actor_from_class(
            actor_class=unreal.PlayerStart,
            location=SPAWN_LOCATION,
            rotation=make_rotator(pitch=0.0, yaw=yaw_toward(SPAWN_LOCATION, SPAWN_TARGET), roll=0.0),
        )
    old_location = player_start.get_actor_location()
    old_rotation = player_start.get_actor_rotation()
    player_start.set_actor_label(SPAWN_LABEL)
    player_start.set_actor_location(SPAWN_LOCATION, False, False)
    player_start.set_actor_rotation(
        make_rotator(pitch=0.0, yaw=yaw_toward(SPAWN_LOCATION, SPAWN_TARGET), roll=0.0),
        False,
    )
    return {
        "label": player_start.get_actor_label(),
        "old_location": as_dict(old_location),
        "new_location": as_dict(player_start.get_actor_location()),
        "old_rotation": rot_dict(old_rotation),
        "new_rotation": rot_dict(player_start.get_actor_rotation()),
    }


def find_table_lamp_mesh():
    candidates = []
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        label = actor.get_actor_label()
        if label == TABLE_LAMP_MESH_LABEL:
            candidates.insert(0, actor)
        elif "desklamp" in label.lower() or "tablelamp" in label.lower():
            candidates.append(actor)
    if not candidates:
        raise RuntimeError("Could not find table/desk lamp mesh actor")
    return candidates[0]


def configure_table_lamp_light(lamp_mesh_actor):
    origin, extent = lamp_mesh_actor.get_actor_bounds(False)
    light_location = unreal.Vector(origin.x, origin.y, origin.z + extent.z * 0.8)
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.PointLight,
        location=light_location,
        rotation=make_rotator(),
    )
    actor.set_actor_label(TABLE_LAMP_LIGHT_LABEL)
    component = light_component(actor)
    if component is None:
        raise RuntimeError("Spawned table lamp point light has no light component")

    set_prop(component, "mobility", unreal.ComponentMobility.MOVABLE)
    set_prop(component, "visible", True)
    set_prop(component, "affects_world", True)
    set_prop(component, "intensity", 650.0)
    set_prop(component, "attenuation_radius", 500.0)
    set_prop(component, "source_radius", 7.5)
    set_prop(component, "soft_source_radius", 18.0)
    set_prop(component, "source_length", 3.0)
    set_prop(component, "use_temperature", True)
    set_prop(component, "temperature", 2700.0)
    set_prop(component, "light_color", unreal.Color(255, 209, 148, 255))
    set_prop(component, "indirect_lighting_intensity", 1.0)
    set_prop(component, "volumetric_scattering_intensity", 0.8)
    set_prop(component, "use_inverse_squared_falloff", True)
    set_prop(component, "cast_shadows", True)
    set_prop(component, "cast_dynamic_shadows", True)
    set_prop(component, "cast_static_shadows", True)
    set_prop(component, "cast_translucent_shadows", True)
    set_prop(component, "contact_shadow_length", 0.12)
    raytraced_shadow_set = set_raytraced_shadow_enabled(component)

    light_units = getattr(unreal, "LightUnits", None)
    if light_units is not None:
        for member in ("LUMENS", "Lumens", "ELUMens"):
            if hasattr(light_units, member):
                if set_prop(component, "intensity_units", getattr(light_units, member)):
                    break

    return {
        "label": actor.get_actor_label(),
        "class": actor_class_name(actor),
        "location": as_dict(actor.get_actor_location()),
        "lamp_mesh_label": lamp_mesh_actor.get_actor_label(),
        "lamp_mesh_bounds_origin": as_dict(origin),
        "lamp_mesh_bounds_extent": as_dict(extent),
        "component_class": component.get_class().get_name(),
        "intensity": get_prop(component, "intensity"),
        "intensity_units": get_prop(component, "intensity_units"),
        "attenuation_radius": get_prop(component, "attenuation_radius"),
        "source_radius": get_prop(component, "source_radius"),
        "soft_source_radius": get_prop(component, "soft_source_radius"),
        "use_inverse_squared_falloff": get_prop(component, "use_inverse_squared_falloff"),
        "indirect_lighting_intensity": get_prop(component, "indirect_lighting_intensity"),
        "cast_shadows": get_prop(component, "cast_shadows"),
        "cast_dynamic_shadows": get_prop(component, "cast_dynamic_shadows"),
        "cast_raytraced_shadow": get_prop(component, "cast_raytraced_shadow"),
        "cast_raytraced_shadow_set": raytraced_shadow_set,
        "temperature": get_prop(component, "temperature"),
        "use_temperature": get_prop(component, "use_temperature"),
        "light_color": get_prop(component, "light_color"),
    }


if not unreal.EditorLoadingAndSavingUtils.load_map(args.map_path):
    raise RuntimeError(f"Failed to load map: {args.map_path}")

report = {
    "map_path": args.map_path,
    "destroyed_prior_generated_actors": destroy_prior_generated_actors(),
    "disabled_light_actors": [],
    "player_start": None,
    "table_lamp_light": None,
}

for actor in list(unreal.EditorLevelLibrary.get_all_level_actors()):
    component = light_component(actor)
    if component is None:
        continue
    report["disabled_light_actors"].append(disable_light_actor(actor))

lamp_mesh_actor = find_table_lamp_mesh()
report["table_lamp_light"] = configure_table_lamp_light(lamp_mesh_actor=lamp_mesh_actor)
report["player_start"] = ensure_player_start()

saved = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
report["saved"] = bool(saved)

with open(args.report, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

unreal.log(f"Wrote table-lamp-only lighting report: {args.report}")
unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
