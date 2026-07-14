import argparse
import json

import unreal


parser = argparse.ArgumentParser()
parser.add_argument("--map-path", required=True)
parser.add_argument("--report", required=True)
args = parser.parse_args()


SCREEN_TOKENS = ("monitor", "tv", "television", "screen", "display")
TABLE_LAMP_LIGHT_LABEL = "Infinigen189cc130_TableLamp_650lm_PointLight"
BLACK_MATERIAL_PATH = "/Game/SPEAR/Scenes/infinigen_189cc130/Materials/M_NonEmissive_Black_OffScreen"


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
    except Exception:
        return False


def get_prop(obj, name):
    try:
        return json_value(obj.get_editor_property(name))
    except Exception:
        return None


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


def material_property(name):
    enum_cls = getattr(unreal, "MaterialProperty", None)
    if enum_cls is None:
        return None
    for member in (name, f"MP_{name}", f"MATERIAL_PROPERTY_MP_{name}"):
        if hasattr(enum_cls, member):
            return getattr(enum_cls, member)
    return None


def create_black_material():
    existing = unreal.EditorAssetLibrary.load_asset(BLACK_MATERIAL_PATH)
    if existing is not None:
        return existing

    package_path, asset_name = BLACK_MATERIAL_PATH.rsplit("/", 1)
    if not unreal.EditorAssetLibrary.does_directory_exist(package_path):
        unreal.EditorAssetLibrary.make_directory(package_path)

    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name=asset_name,
        package_path=package_path,
        asset_class=unreal.Material,
        factory=unreal.MaterialFactoryNew(),
    )
    if material is None:
        raise RuntimeError(f"Failed to create material: {BLACK_MATERIAL_PATH}")

    base_color_prop = material_property("BASE_COLOR")
    roughness_prop = material_property("ROUGHNESS")
    metallic_prop = material_property("METALLIC")

    black = unreal.MaterialEditingLibrary.create_material_expression(
        material,
        unreal.MaterialExpressionConstant3Vector,
        -400,
        0,
    )
    set_prop(black, "constant", unreal.LinearColor(0.0, 0.0, 0.0, 1.0))
    if base_color_prop is not None:
        unreal.MaterialEditingLibrary.connect_material_property(black, "", base_color_prop)

    roughness = unreal.MaterialEditingLibrary.create_material_expression(
        material,
        unreal.MaterialExpressionConstant,
        -400,
        160,
    )
    set_prop(roughness, "r", 0.85)
    if roughness_prop is not None:
        unreal.MaterialEditingLibrary.connect_material_property(roughness, "", roughness_prop)

    metallic = unreal.MaterialEditingLibrary.create_material_expression(
        material,
        unreal.MaterialExpressionConstant,
        -400,
        320,
    )
    set_prop(metallic, "r", 0.0)
    if metallic_prop is not None:
        unreal.MaterialEditingLibrary.connect_material_property(metallic, "", metallic_prop)

    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_asset(BLACK_MATERIAL_PATH, only_if_is_dirty=False)
    return material


def disable_light(component):
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


def is_screen_actor(actor):
    label = actor.get_actor_label().lower()
    class_name = actor.get_class().get_name().lower()
    return any(token in label or token in class_name for token in SCREEN_TOKENS)


if not unreal.EditorLoadingAndSavingUtils.load_map(args.map_path):
    raise RuntimeError(f"Failed to load map: {args.map_path}")

black_material = create_black_material()
report = {
    "map_path": args.map_path,
    "black_material": BLACK_MATERIAL_PATH,
    "screen_actors": [],
    "light_actors": [],
}

for actor in unreal.EditorLevelLibrary.get_all_level_actors():
    label = actor.get_actor_label()
    light = light_component(actor)
    if light is not None:
        if label != TABLE_LAMP_LIGHT_LABEL:
            disable_light(light)
        report["light_actors"].append(
            {
                "label": label,
                "component_class": light.get_class().get_name(),
                "intensity": get_prop(light, "intensity"),
                "visible": get_prop(light, "visible"),
                "affects_world": get_prop(light, "affects_world"),
                "cast_shadows": get_prop(light, "cast_shadows"),
            }
        )

    if not is_screen_actor(actor):
        continue

    mesh = mesh_component(actor)
    entry = {
        "label": label,
        "class": actor.get_class().get_name(),
        "has_light_component": light is not None,
        "mesh_component_class": mesh.get_class().get_name() if mesh is not None else None,
        "material_slots": 0,
        "set_emissive_light_source_false": False,
        "assigned_black_material_slots": [],
        "emissive_light_source": None,
    }
    if mesh is not None:
        entry["set_emissive_light_source_false"] = set_prop(mesh, "emissive_light_source", False)
        count = component_material_count(mesh)
        entry["material_slots"] = count
        for index in range(count):
            try:
                mesh.set_material(index, black_material)
                entry["assigned_black_material_slots"].append(index)
            except Exception as exc:
                unreal.log_warning(f"Could not assign black material to {label} slot {index}: {exc}")
        entry["emissive_light_source"] = get_prop(mesh, "emissive_light_source")

    report["screen_actors"].append(entry)

saved = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
report["saved"] = bool(saved)

with open(args.report, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

unreal.log(f"Wrote screen light-source disable report: {args.report}")
unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
