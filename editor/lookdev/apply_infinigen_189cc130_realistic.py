import argparse
import json
import math
import os

import unreal


parser = argparse.ArgumentParser()
parser.add_argument(
    "--source-map-path",
    default="/Game/SPEAR/Scenes/infinigen_189cc130/Maps/infinigen_189cc130",
)
parser.add_argument(
    "--target-map-path",
    default="/Game/SPEAR/Scenes/infinigen_189cc130/Maps/infinigen_189cc130_realistic",
)
parser.add_argument("--report", required=True)
args = parser.parse_args()


GENERATED_PREFIX = "Infinigen189cc130_Realistic_"
TABLE_LAMP_MESH_LABEL = "Infinigen_DeskLampFactory_8507126__spawn_asset_7901138_"
MONITOR_MESH_LABEL = "Infinigen_MonitorFactory_1148210__spawn_asset_4488226_"
SPAWN_LABEL = "Setup_PlayerStart"
SPAWN_LOCATION = unreal.Vector(300.0, -1000.0, 120.0)
SPAWN_TARGET = unreal.Vector(369.27, -1243.399, 115.0)
MATERIAL_DIR = "/Game/SPEAR/Scenes/infinigen_189cc130/Materials"
BLACK_MATERIAL_PATH = f"{MATERIAL_DIR}/M_NonEmissive_Black_OffScreen"


LOOKDEV_MATERIALS = {
    "M_189cc130_Realistic_Neutral_Plaster": {
        "color": (0.56, 0.54, 0.50),
        "roughness": 0.86,
        "metallic": 0.0,
    },
    "M_189cc130_Realistic_Ceiling_Plaster": {
        "color": (0.62, 0.60, 0.56),
        "roughness": 0.88,
        "metallic": 0.0,
    },
    "M_189cc130_Realistic_Muted_Floor": {
        "color": (0.32, 0.28, 0.23),
        "roughness": 0.72,
        "metallic": 0.0,
    },
    "M_189cc130_Realistic_Warm_Wood": {
        "color": (0.35, 0.26, 0.18),
        "roughness": 0.58,
        "metallic": 0.0,
    },
    "M_189cc130_Realistic_Fabric_Grey": {
        "color": (0.46, 0.45, 0.42),
        "roughness": 0.92,
        "metallic": 0.0,
    },
    "M_189cc130_Realistic_Bedding_OffWhite": {
        "color": (0.66, 0.63, 0.58),
        "roughness": 0.94,
        "metallic": 0.0,
    },
    "M_189cc130_Realistic_Lampshade_Warm": {
        "color": (0.82, 0.70, 0.54),
        "roughness": 0.82,
        "metallic": 0.0,
    },
    "M_189cc130_Realistic_Rug_Muted": {
        "color": (0.34, 0.33, 0.30),
        "roughness": 0.96,
        "metallic": 0.0,
    },
}


ASSIGNMENT_RULES = [
    ("wall", "M_189cc130_Realistic_Neutral_Plaster"),
    ("ceiling", "M_189cc130_Realistic_Ceiling_Plaster"),
    ("floor", "M_189cc130_Realistic_Muted_Floor"),
    ("rugfactory", "M_189cc130_Realistic_Rug_Muted"),
    ("mattressfactory", "M_189cc130_Realistic_Bedding_OffWhite"),
    ("pillowfactory", "M_189cc130_Realistic_Bedding_OffWhite"),
    ("comforterfactory", "M_189cc130_Realistic_Fabric_Grey"),
    ("blanketfactory", "M_189cc130_Realistic_Fabric_Grey"),
    ("towelfactory", "M_189cc130_Realistic_Fabric_Grey"),
    ("bedfactory", "M_189cc130_Realistic_Warm_Wood"),
    ("deskfactory", "M_189cc130_Realistic_Warm_Wood"),
    ("shelf", "M_189cc130_Realistic_Warm_Wood"),
    ("bookcase", "M_189cc130_Realistic_Warm_Wood"),
    ("kitchencabinet", "M_189cc130_Realistic_Warm_Wood"),
    ("desklampfactory", "M_189cc130_Realistic_Lampshade_Warm"),
    ("monitorfactory", "M_NonEmissive_Black_OffScreen"),
]


def json_value(value):
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    if hasattr(value, "name"):
        return value.name
    return str(value)


def vector_dict(vector):
    return {"x": round(vector.x, 3), "y": round(vector.y, 3), "z": round(vector.z, 3)}


def rotator_dict(rotator):
    return {
        "pitch": round(rotator.pitch, 3),
        "yaw": round(rotator.yaw, 3),
        "roll": round(rotator.roll, 3),
    }


def set_prop(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception as exc:
        class_name = type(obj).__name__
        get_class = getattr(obj, "get_class", None)
        if get_class is not None:
            try:
                class_name = get_class().get_name()
            except Exception:
                pass
        unreal.log_warning(f"Could not set {class_name}.{name}: {exc}")
        return False


def get_prop(obj, name):
    try:
        return json_value(obj.get_editor_property(name))
    except Exception:
        return None


def enum_value(enum_name, members):
    enum_cls = getattr(unreal, enum_name, None)
    if enum_cls is None:
        return None
    for member in members:
        if hasattr(enum_cls, member):
            return getattr(enum_cls, member)
    return None


def material_property(name):
    return enum_value(
        "MaterialProperty",
        (name, f"MP_{name}", f"MATERIAL_PROPERTY_MP_{name}"),
    )


def actor_class_name(actor):
    return actor.get_class().get_name()


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


def component_material_count(component):
    for method_name in ("get_num_materials", "GetNumMaterials"):
        method = getattr(component, method_name, None)
        if method is None:
            continue
        try:
            return int(method())
        except Exception:
            pass
    try:
        return len(component.get_editor_property("override_materials"))
    except Exception:
        return 1


def actor_by_label(label):
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if actor.get_actor_label() == label:
            return actor
    return None


def actor_by_label_or_tokens(label, tokens):
    actor = actor_by_label(label)
    if actor is not None:
        return actor
    lowered_tokens = [token.lower() for token in tokens]
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        actor_label = actor.get_actor_label().lower()
        if all(token in actor_label for token in lowered_tokens):
            return actor
    return None


def actor_bounds(actor):
    origin, extent = actor.get_actor_bounds(False)
    return origin, extent


def bounds_entry(actor):
    origin, extent = actor_bounds(actor)
    return {
        "label": actor.get_actor_label(),
        "origin": vector_dict(origin),
        "extent": vector_dict(extent),
        "min": vector_dict(unreal.Vector(origin.x - extent.x, origin.y - extent.y, origin.z - extent.z)),
        "max": vector_dict(unreal.Vector(origin.x + extent.x, origin.y + extent.y, origin.z + extent.z)),
    }


def yaw_toward(start, target):
    delta = target - start
    return math.degrees(math.atan2(delta.y, delta.x))


def ensure_target_map():
    source_exists = unreal.EditorAssetLibrary.does_asset_exist(args.source_map_path)
    if not source_exists:
        raise RuntimeError(f"Missing source map: {args.source_map_path}")

    target_exists_before = unreal.EditorAssetLibrary.does_asset_exist(args.target_map_path)
    duplicated = False
    if not target_exists_before:
        duplicated = bool(unreal.EditorAssetLibrary.duplicate_asset(args.source_map_path, args.target_map_path))
        if not duplicated:
            raise RuntimeError(f"Failed to duplicate {args.source_map_path} to {args.target_map_path}")
        unreal.EditorAssetLibrary.save_asset(args.target_map_path, only_if_is_dirty=False)

    if not unreal.EditorLoadingAndSavingUtils.load_map(args.target_map_path):
        raise RuntimeError(f"Failed to load target map: {args.target_map_path}")

    return {
        "source_map_path": args.source_map_path,
        "target_map_path": args.target_map_path,
        "target_existed_before": target_exists_before,
        "duplicated_from_source": duplicated,
    }


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
    if component is None:
        return None
    entry = {
        "label": actor.get_actor_label(),
        "class": actor_class_name(actor),
        "component_class": component.get_class().get_name(),
        "old_intensity": get_prop(component, "intensity"),
    }
    actor.set_actor_hidden_in_game(True)
    actor.set_is_temporarily_hidden_in_editor(True)
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
    entry.update(
        {
            "visible": get_prop(component, "visible"),
            "intensity": get_prop(component, "intensity"),
            "affects_world": get_prop(component, "affects_world"),
        }
    )
    return entry


def disable_existing_lights():
    disabled = []
    for actor in list(unreal.EditorLevelLibrary.get_all_level_actors()):
        if actor.get_actor_label().startswith(GENERATED_PREFIX):
            continue
        entry = disable_light_actor(actor)
        if entry is not None:
            disabled.append(entry)
    return disabled


def set_light_units_lumens(component):
    light_units = getattr(unreal, "LightUnits", None)
    if light_units is None:
        return False
    for member in ("LUMENS", "Lumens", "ELUMens"):
        if hasattr(light_units, member):
            return set_prop(component, "intensity_units", getattr(light_units, member))
    return False


def set_raytraced_shadow_enabled(component):
    value = enum_value(
        "CastRayTracedShadow",
        ("ENABLED", "Enabled", "CAST_RAY_TRACED_SHADOW_ENABLED"),
    )
    candidates = [value] if value is not None else []
    candidates.extend(("ENABLED", "Enabled", 2, True))
    for candidate in candidates:
        if set_prop(component, "cast_raytraced_shadow", candidate):
            return True
    return False


def light_color(r, g, b, a=1.0):
    return unreal.Color(
        int(round(max(0.0, min(1.0, b)) * 255.0)),
        int(round(max(0.0, min(1.0, g)) * 255.0)),
        int(round(max(0.0, min(1.0, r)) * 255.0)),
        int(round(max(0.0, min(1.0, a)) * 255.0)),
    )


def configure_light_common(component, temperature, color, indirect):
    set_prop(component, "mobility", unreal.ComponentMobility.MOVABLE)
    set_prop(component, "visible", True)
    set_prop(component, "affects_world", True)
    set_prop(component, "use_temperature", True)
    set_prop(component, "temperature", float(temperature))
    set_prop(component, "light_color", color)
    set_prop(component, "indirect_lighting_intensity", float(indirect))
    set_prop(component, "volumetric_scattering_intensity", 0.25)
    set_prop(component, "cast_shadows", True)
    set_prop(component, "cast_dynamic_shadows", True)
    set_prop(component, "cast_static_shadows", True)
    set_prop(component, "contact_shadow_length", 0.08)
    set_raytraced_shadow_enabled(component)


def table_lamp_location():
    lamp = actor_by_label_or_tokens(TABLE_LAMP_MESH_LABEL, ("desklampfactory",))
    if lamp is None:
        raise RuntimeError(f"Missing lamp actor: {TABLE_LAMP_MESH_LABEL}")

    lamp_origin, lamp_extent = actor_bounds(lamp)
    return unreal.Vector(
        lamp_origin.x,
        lamp_origin.y,
        lamp_origin.z + lamp_extent.z * 0.78,
    )


def soften_lamp_mesh_self_shadow():
    lamp = actor_by_label_or_tokens(TABLE_LAMP_MESH_LABEL, ("desklampfactory",))
    if lamp is None:
        return {"lamp_actor_found": False}
    mesh = mesh_component(lamp)
    if mesh is None:
        return {"lamp_actor_found": True, "mesh_component_found": False}

    result = {
        "lamp_actor_found": True,
        "mesh_component_found": True,
        "actor_label": lamp.get_actor_label(),
        "old_cast_shadow": get_prop(mesh, "cast_shadow"),
    }
    # The imported shade is opaque geometry. Let authored lamp lights pass through
    # it so the practical behaves like a translucent fabric shade.
    for name, value in (
        ("cast_shadow", False),
        ("cast_dynamic_shadow", False),
        ("cast_static_shadow", False),
        ("affect_distance_field_lighting", False),
    ):
        set_prop(mesh, name, value)
    result["new_cast_shadow"] = get_prop(mesh, "cast_shadow")
    return result


def spawn_table_lamp_light():
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.PointLight,
        location=table_lamp_location(),
        rotation=make_rotator(),
    )
    actor.set_actor_label(f"{GENERATED_PREFIX}TableLamp_PointLight")
    component = light_component(actor)
    if component is None:
        raise RuntimeError("Spawned table lamp point light has no component")
    configure_light_common(component, 2850.0, light_color(1.0, 0.82, 0.62), 1.0)
    set_prop(component, "intensity", 1450.0)
    set_light_units_lumens(component)
    set_prop(component, "attenuation_radius", 860.0)
    set_prop(component, "source_radius", 18.0)
    set_prop(component, "soft_source_radius", 64.0)
    set_prop(component, "source_length", 14.0)
    set_prop(component, "use_inverse_squared_falloff", True)
    return actor


def spawn_lampshade_glow():
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.PointLight,
        location=table_lamp_location(),
        rotation=make_rotator(),
    )
    actor.set_actor_label(f"{GENERATED_PREFIX}Lampshade_Glow_PointLight")
    component = light_component(actor)
    if component is None:
        raise RuntimeError("Spawned lampshade glow point light has no component")
    configure_light_common(component, 3000.0, light_color(1.0, 0.74, 0.48), 0.35)
    set_prop(component, "intensity", 520.0)
    set_light_units_lumens(component)
    set_prop(component, "attenuation_radius", 760.0)
    set_prop(component, "source_radius", 36.0)
    set_prop(component, "soft_source_radius", 96.0)
    set_prop(component, "source_length", 24.0)
    set_prop(component, "use_inverse_squared_falloff", True)
    set_prop(component, "cast_shadows", False)
    set_prop(component, "cast_dynamic_shadows", False)
    set_prop(component, "cast_static_shadows", False)
    return actor


def spawn_sky_light():
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.SkyLight,
        location=unreal.Vector(0.0, 0.0, 300.0),
        rotation=make_rotator(),
    )
    actor.set_actor_label(f"{GENERATED_PREFIX}Ambient_SkyLight")
    component = light_component(actor)
    if component is None:
        raise RuntimeError("Spawned skylight has no component")
    set_prop(component, "mobility", unreal.ComponentMobility.MOVABLE)
    set_prop(component, "visible", True)
    set_prop(component, "affects_world", True)
    set_prop(component, "intensity", 0.16)
    set_prop(component, "indirect_lighting_intensity", 0.16)
    set_prop(component, "light_color", light_color(0.80, 0.84, 0.90))
    set_prop(component, "real_time_capture", False)
    set_prop(component, "cast_shadows", False)
    return actor


def find_window_fill_location():
    windows = []
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if "windowfactory" in actor.get_actor_label().lower():
            windows.append(actor)
    if not windows:
        return unreal.Vector(180.0, -1160.0, 150.0)
    largest = max(windows, key=lambda item: actor_bounds(item)[1].x * actor_bounds(item)[1].z)
    origin, extent = actor_bounds(largest)
    y_offset = 45.0 if origin.y < -1000.0 else -45.0
    return unreal.Vector(origin.x, origin.y + y_offset, max(115.0, origin.z))


def spawn_window_fill():
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.RectLight,
        location=find_window_fill_location(),
        rotation=make_rotator(0.0, 90.0, 0.0),
    )
    actor.set_actor_label(f"{GENERATED_PREFIX}WindowFill_RectLight")
    component = light_component(actor)
    if component is None:
        raise RuntimeError("Spawned window fill rect light has no component")
    configure_light_common(component, 5000.0, light_color(0.75, 0.78, 0.82), 0.08)
    set_prop(component, "intensity", 260.0)
    set_light_units_lumens(component)
    set_prop(component, "attenuation_radius", 760.0)
    set_prop(component, "source_width", 340.0)
    set_prop(component, "source_height", 240.0)
    set_prop(component, "barn_door_angle", 75.0)
    set_prop(component, "barn_door_length", 30.0)
    set_prop(component, "cast_shadows", False)
    set_prop(component, "cast_dynamic_shadows", False)
    return actor


def create_or_update_material(asset_name, color, roughness, metallic):
    path = f"{MATERIAL_DIR}/{asset_name}"
    material = unreal.EditorAssetLibrary.load_asset(path)
    created = False
    if material is None:
        if not unreal.EditorAssetLibrary.does_directory_exist(MATERIAL_DIR):
            unreal.EditorAssetLibrary.make_directory(MATERIAL_DIR)
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            asset_name=asset_name,
            package_path=MATERIAL_DIR,
            asset_class=unreal.Material,
            factory=unreal.MaterialFactoryNew(),
        )
        if material is None:
            raise RuntimeError(f"Failed to create material: {path}")
        created = True

    if created:
        base_color_prop = material_property("BASE_COLOR")
        roughness_prop = material_property("ROUGHNESS")
        metallic_prop = material_property("METALLIC")

        base_color = unreal.MaterialEditingLibrary.create_material_expression(
            material,
            unreal.MaterialExpressionConstant3Vector,
            -420,
            -60,
        )
        set_prop(base_color, "constant", unreal.LinearColor(color[0], color[1], color[2], 1.0))
        if base_color_prop is not None:
            unreal.MaterialEditingLibrary.connect_material_property(base_color, "", base_color_prop)

        rough = unreal.MaterialEditingLibrary.create_material_expression(
            material,
            unreal.MaterialExpressionConstant,
            -420,
            110,
        )
        set_prop(rough, "r", float(roughness))
        if roughness_prop is not None:
            unreal.MaterialEditingLibrary.connect_material_property(rough, "", roughness_prop)

        metal = unreal.MaterialEditingLibrary.create_material_expression(
            material,
            unreal.MaterialExpressionConstant,
            -420,
            270,
        )
        set_prop(metal, "r", float(metallic))
        if metallic_prop is not None:
            unreal.MaterialEditingLibrary.connect_material_property(metal, "", metallic_prop)

        unreal.MaterialEditingLibrary.recompile_material(material)

    unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    return material, path, created


def ensure_materials():
    created_or_loaded = {}
    for asset_name, spec in LOOKDEV_MATERIALS.items():
        material, path, created = create_or_update_material(
            asset_name=asset_name,
            color=spec["color"],
            roughness=spec["roughness"],
            metallic=spec["metallic"],
        )
        created_or_loaded[asset_name] = {
            "path": path,
            "created": created,
            "color": spec["color"],
            "roughness": spec["roughness"],
            "metallic": spec["metallic"],
            "material": material,
        }

    black = unreal.EditorAssetLibrary.load_asset(BLACK_MATERIAL_PATH)
    if black is None:
        black, path, created = create_or_update_material(
            asset_name="M_NonEmissive_Black_OffScreen",
            color=(0.0, 0.0, 0.0),
            roughness=0.85,
            metallic=0.0,
        )
        created_or_loaded["M_NonEmissive_Black_OffScreen"] = {
            "path": path,
            "created": created,
            "color": (0.0, 0.0, 0.0),
            "roughness": 0.85,
            "metallic": 0.0,
            "material": black,
        }
    else:
        created_or_loaded["M_NonEmissive_Black_OffScreen"] = {
            "path": BLACK_MATERIAL_PATH,
            "created": False,
            "material": black,
        }
    return created_or_loaded


def material_for_actor(label):
    lower = label.lower()
    for token, material_name in ASSIGNMENT_RULES:
        if token in lower:
            return material_name
    return None


def assign_materials(materials):
    changes = []
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if actor_class_name(actor) != "StaticMeshActor":
            continue
        label = actor.get_actor_label()
        material_name = material_for_actor(label)
        if material_name is None:
            continue
        mesh = mesh_component(actor)
        if mesh is None:
            continue
        material = materials[material_name]["material"]
        count = component_material_count(mesh)
        entry = {
            "actor_label": label,
            "material": materials[material_name]["path"],
            "slot_count": count,
            "assigned_slots": [],
        }
        if "monitorfactory" in label.lower():
            set_prop(mesh, "emissive_light_source", False)
            entry["emissive_light_source"] = get_prop(mesh, "emissive_light_source")
        for index in range(count):
            try:
                mesh.set_material(index, material)
                entry["assigned_slots"].append(index)
            except Exception as exc:
                unreal.log_warning(f"Could not set material on {label} slot {index}: {exc}")
        changes.append(entry)
    return changes


def ensure_player_start():
    player_start = actor_by_label(SPAWN_LABEL)
    if player_start is None:
        player_starts = [
            actor
            for actor in unreal.EditorLevelLibrary.get_all_level_actors()
            if actor_class_name(actor) == "PlayerStart"
        ]
        player_start = player_starts[0] if player_starts else None
    if player_start is None:
        player_start = unreal.EditorLevelLibrary.spawn_actor_from_class(
            actor_class=unreal.PlayerStart,
            location=SPAWN_LOCATION,
            rotation=make_rotator(0.0, yaw_toward(SPAWN_LOCATION, SPAWN_TARGET), 0.0),
        )
    old_location = player_start.get_actor_location()
    old_rotation = player_start.get_actor_rotation()
    player_start.set_actor_label(SPAWN_LABEL)
    player_start.set_actor_location(SPAWN_LOCATION, False, False)
    player_start.set_actor_rotation(
        make_rotator(0.0, yaw_toward(SPAWN_LOCATION, SPAWN_TARGET), 0.0),
        False,
    )
    return {
        "label": player_start.get_actor_label(),
        "old_location": vector_dict(old_location),
        "new_location": vector_dict(player_start.get_actor_location()),
        "old_rotation": rotator_dict(old_rotation),
        "new_rotation": rotator_dict(player_start.get_actor_rotation()),
    }


def configure_post_process():
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.PostProcessVolume,
        location=unreal.Vector(0.0, 0.0, 120.0),
        rotation=make_rotator(),
    )
    actor.set_actor_label(f"{GENERATED_PREFIX}PostProcess")
    set_prop(actor, "b_unbound", True)
    set_prop(actor, "unbound", True)
    set_prop(actor, "priority", 20.0)

    settings = actor.get_editor_property("settings")
    manual = enum_value("AutoExposureMethod", ("AEM_MANUAL", "MANUAL", "Manual"))
    if manual is not None:
        set_prop(settings, "override_auto_exposure_method", True)
        set_prop(settings, "auto_exposure_method", manual)
    for name, value in (
        ("override_auto_exposure_bias", True),
        ("auto_exposure_bias", 1.15),
        ("override_auto_exposure_min_brightness", True),
        ("auto_exposure_min_brightness", 2.0),
        ("override_auto_exposure_max_brightness", True),
        ("auto_exposure_max_brightness", 2.0),
        ("override_auto_exposure_min_ev100", True),
        ("auto_exposure_min_ev100", 0.0),
        ("override_auto_exposure_max_ev100", True),
        ("auto_exposure_max_ev100", 0.0),
        ("override_white_temp", True),
        ("white_temp", 5200.0),
        ("override_white_tint", True),
        ("white_tint", 0.0),
        ("override_color_saturation", True),
        ("color_saturation", unreal.Vector4(0.86, 0.86, 0.86, 1.0)),
        ("override_color_contrast", True),
        ("color_contrast", unreal.Vector4(1.02, 1.02, 1.02, 1.0)),
        ("override_color_gain", True),
        ("color_gain", unreal.Vector4(1.0, 1.0, 1.0, 1.0)),
        ("override_film_slope", True),
        ("film_slope", 0.96),
        ("override_film_toe", True),
        ("film_toe", 0.34),
        ("override_film_shoulder", True),
        ("film_shoulder", 0.26),
        ("override_bloom_intensity", True),
        ("bloom_intensity", 0.08),
        ("override_vignette_intensity", True),
        ("vignette_intensity", 0.08),
    ):
        set_prop(settings, name, value)
    return actor


def light_detail(actor):
    component = light_component(actor)
    entry = {
        "label": actor.get_actor_label(),
        "class": actor_class_name(actor),
        "location": vector_dict(actor.get_actor_location()),
        "rotation": rotator_dict(actor.get_actor_rotation()),
        "component_class": component.get_class().get_name() if component is not None else None,
    }
    if component is not None:
        for name in (
            "intensity",
            "intensity_units",
            "attenuation_radius",
            "source_radius",
            "soft_source_radius",
            "source_length",
            "source_width",
            "source_height",
            "temperature",
            "light_color",
            "use_temperature",
            "use_inverse_squared_falloff",
            "indirect_lighting_intensity",
            "visible",
            "affects_world",
            "cast_shadows",
            "cast_dynamic_shadows",
            "cast_raytraced_shadow",
            "mobility",
        ):
            entry[name] = get_prop(component, name)
    return entry


def post_process_detail(actor):
    settings = actor.get_editor_property("settings")
    detail = {
        "label": actor.get_actor_label(),
        "class": actor_class_name(actor),
        "unbound": get_prop(actor, "b_unbound") or get_prop(actor, "unbound"),
        "priority": get_prop(actor, "priority"),
    }
    for name in (
        "auto_exposure_method",
        "auto_exposure_bias",
        "auto_exposure_min_brightness",
        "auto_exposure_max_brightness",
        "auto_exposure_min_ev100",
        "auto_exposure_max_ev100",
        "white_temp",
        "white_tint",
        "color_saturation",
        "color_contrast",
        "film_slope",
        "film_toe",
        "film_shoulder",
        "bloom_intensity",
        "vignette_intensity",
    ):
        detail[name] = get_prop(settings, name)
    return detail


def active_light_count():
    count = 0
    entries = []
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        component = light_component(actor)
        if component is None:
            continue
        intensity = get_prop(component, "intensity")
        visible = get_prop(component, "visible")
        affects_world = get_prop(component, "affects_world")
        is_active = bool(visible is not False and affects_world is not False and (intensity is None or float(intensity) > 0.0))
        if is_active:
            count += 1
        entries.append(
            {
                "label": actor.get_actor_label(),
                "component_class": component.get_class().get_name(),
                "intensity": intensity,
                "visible": visible,
                "affects_world": affects_world,
                "active": is_active,
            }
        )
    return count, entries


map_state = ensure_target_map()
report = {
    "map_path": args.target_map_path,
    "map_state": map_state,
    "destroyed_prior_generated_actors": destroy_prior_generated_actors(),
    "disabled_existing_light_actors": [],
    "spawned_lights": [],
    "post_process": None,
    "changed_material_slots": [],
    "lamp_mesh_shadow": None,
    "player_start": None,
    "active_light_count": None,
    "all_light_actors": [],
    "saved": False,
}

report["disabled_existing_light_actors"] = disable_existing_lights()
report["lamp_mesh_shadow"] = soften_lamp_mesh_self_shadow()
spawned = [spawn_table_lamp_light(), spawn_lampshade_glow(), spawn_sky_light(), spawn_window_fill()]
post_process = configure_post_process()
materials = ensure_materials()
report["changed_material_slots"] = assign_materials(materials)
report["player_start"] = ensure_player_start()
report["spawned_lights"] = [light_detail(actor) for actor in spawned]
report["post_process"] = post_process_detail(post_process)

active_count, all_lights = active_light_count()
report["active_light_count"] = active_count
report["all_light_actors"] = all_lights
report["reference_note"] = (
    "apartment_0000 was used as a tone and contrast reference only. This pass "
    "authors warm practical lamp lighting with translucent shade behavior, subdued cool fill, fixed lookdev "
    "post process, neutral plaster/floor/fabric/wood materials, and a black "
    "non-emissive monitor on the duplicated map."
)

saved_packages = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
saved_map = unreal.EditorAssetLibrary.save_asset(args.target_map_path, only_if_is_dirty=False)
report["saved"] = bool(saved_packages or saved_map)
report["save_dirty_packages_result"] = bool(saved_packages)
report["save_target_map_result"] = bool(saved_map)

os.makedirs(os.path.dirname(args.report), exist_ok=True)
with open(args.report, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, sort_keys=True)

unreal.log(f"Wrote realistic lookdev report: {args.report}")
unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
