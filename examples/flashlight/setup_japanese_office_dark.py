#
# Copyright (c) 2025 The SPEAR Development Team. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
# Copyright (c) 2022 Intel. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
#

import argparse
import posixpath

import spear
import unreal


parser = argparse.ArgumentParser()
parser.add_argument("--source-map-path", default="/Game/JapaneseOffice/Maps/Demonstration")
parser.add_argument("--target-map-path", default="/Game/JapaneseOffice/Maps/Demonstration_Dark")
parser.add_argument("--replace-existing-map", action="store_true")
args = parser.parse_args()


LIGHT_FIXTURE_TOKENS = [
    "downlight",
    "guidelight",
    "evhall_lamp",
    "pendantlight",
    "wall_light",
]


def duplicate_map(source_map_path, target_map_path, replace_existing_map):
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path=target_map_path):
        if replace_existing_map:
            spear.log("Deleting existing dark map: ", target_map_path)
            success = unreal.EditorAssetLibrary.delete_asset(asset_path_to_delete=target_map_path)
            assert success
        else:
            raise AssertionError(f"Map already exists: {target_map_path}. Pass --replace-existing-map to overwrite it.")

    target_map_dir = posixpath.dirname(target_map_path)
    unreal.EditorAssetLibrary.make_directory(directory_path=target_map_dir)

    spear.log("Duplicating map: ", source_map_path, " -> ", target_map_path)
    duplicated = unreal.EditorAssetLibrary.duplicate_asset(
        source_asset_path=source_map_path,
        destination_asset_path=target_map_path)
    assert duplicated, f"Could not duplicate {source_map_path} to {target_map_path}"


def get_actor_label(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        return actor.get_name()


def name_matches_light_fixture(name):
    name_lower = name.lower()
    return any(token in name_lower for token in LIGHT_FIXTURE_TOKENS)


def component_matches_light_fixture(component):
    names = [component.get_name()]

    try:
        static_mesh = component.get_editor_property("static_mesh")
        if static_mesh is not None:
            names.append(static_mesh.get_path_name())
    except Exception:
        pass

    try:
        material_count = component.get_num_materials()
        for material_index in range(material_count):
            material = component.get_material(material_index)
            if material is not None:
                names.append(material.get_path_name())
    except Exception:
        pass

    return any(name_matches_light_fixture(name=name) for name in names)


def darken_current_level():
    world = unreal.EditorLevelLibrary.get_editor_world()
    world_settings = world.get_world_settings()
    world_settings.set_editor_property(name="force_no_precomputed_lighting", value=True)

    disabled_light_components = 0
    hidden_fixture_actors = 0
    hidden_fixture_components = 0

    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        light_components = actor.get_components_by_class(unreal.LightComponentBase)
        for light_component in light_components:
            light_component.set_editor_property(name="visible", value=False)
            light_component.set_editor_property(name="hidden_in_game", value=True)
            light_component.set_editor_property(name="intensity", value=0.0)
            disabled_light_components += 1

        actor_name = f"{get_actor_label(actor=actor)} {actor.get_name()} {actor.get_class().get_name()}"
        if name_matches_light_fixture(name=actor_name):
            actor.set_actor_hidden_in_game(True)
            actor.set_is_temporarily_hidden_in_editor(True)
            actor.set_actor_enable_collision(False)
            hidden_fixture_actors += 1
            continue

        primitive_components = actor.get_components_by_class(unreal.PrimitiveComponent)
        for primitive_component in primitive_components:
            if component_matches_light_fixture(component=primitive_component):
                primitive_component.set_editor_property(name="visible", value=False)
                primitive_component.set_editor_property(name="hidden_in_game", value=True)
                primitive_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
                hidden_fixture_components += 1

    spear.log("Disabled light components: ", disabled_light_components)
    spear.log("Hidden light fixture actors: ", hidden_fixture_actors)
    spear.log("Hidden light fixture components: ", hidden_fixture_components)


if __name__ == "__main__":
    duplicate_map(
        source_map_path=args.source_map_path,
        target_map_path=args.target_map_path,
        replace_existing_map=args.replace_existing_map)

    level_editor_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    loaded = level_editor_subsystem.load_level(asset_path=args.target_map_path)
    assert loaded, f"Could not load level: {args.target_map_path}"

    darken_current_level()

    spear.log("Saving current level: ", args.target_map_path)
    level_editor_subsystem.save_current_level()
    unreal.EditorAssetLibrary.save_directory(
        directory_path=posixpath.dirname(args.target_map_path),
        only_if_is_dirty=False,
        recursive=True)

    spear.log("Created dark JapaneseOffice map: ", args.target_map_path)
    spear.log("Done.")
