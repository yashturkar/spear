#
# Copyright (c) 2025 The SPEAR Development Team. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
# Copyright (c) 2022 Intel. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
#

import argparse
import glob
import os
import posixpath

import spear
import unreal


parser = argparse.ArgumentParser()
parser.add_argument("--gltf-file", default=None)
parser.add_argument("--mesh-dir", default="/Game/Fab/Abandoned_Room_Interior")
parser.add_argument("--map-path", default="/Game/Fab/Abandoned_Room_Interior/Maps/AbandonedRoom")
parser.add_argument("--replace-existing-map", action="store_true")
args = parser.parse_args()


def find_abandoned_room_gltf():
    candidates = glob.glob("/var/tmp/FabLibrary/**/abandoned_room_interior*_extracted/scene.gltf", recursive=True)
    candidates += glob.glob("/var/tmp/FabLibrary/**/scene.gltf", recursive=True)
    candidates = [os.path.realpath(candidate) for candidate in candidates if os.path.exists(candidate)]
    candidates = sorted(candidates, key=os.path.getmtime, reverse=True)
    assert len(candidates) > 0, "Could not find Fab glTF under /var/tmp/FabLibrary. Re-download/import the Fab asset first."
    return candidates[0]


def get_static_meshes(mesh_dir):
    static_meshes = []
    for asset_path in unreal.EditorAssetLibrary.list_assets(directory_path=mesh_dir, recursive=False, include_folder=False):
        asset = unreal.load_asset(name=asset_path)
        if isinstance(asset, unreal.StaticMesh):
            static_meshes.append(asset)
    static_meshes = sorted(static_meshes, key=lambda asset: asset.get_path_name())
    return static_meshes


def import_room_meshes(gltf_file, mesh_dir):
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    static_meshes = get_static_meshes(mesh_dir=mesh_dir) if unreal.EditorAssetLibrary.does_directory_exist(directory_path=mesh_dir) else []

    if len(static_meshes) > 0:
        spear.log("Using existing room static meshes in: ", mesh_dir)
        return static_meshes

    spear.log("Importing room glTF: ", gltf_file)
    unreal.EditorAssetLibrary.make_directory(directory_path=mesh_dir)

    import_task = unreal.AssetImportTask()
    import_task.set_editor_property(name="async_", value=False)
    import_task.set_editor_property(name="automated", value=True)
    import_task.set_editor_property(name="destination_path", value=mesh_dir)
    import_task.set_editor_property(name="filename", value=gltf_file)
    import_task.set_editor_property(name="replace_existing", value=True)
    import_task.set_editor_property(name="replace_existing_settings", value=True)
    import_task.set_editor_property(name="save", value=True)
    asset_tools.import_asset_tasks(import_tasks=[import_task])

    static_meshes = get_static_meshes(mesh_dir=mesh_dir)
    assert len(static_meshes) > 0, f"No static meshes were found after importing {gltf_file} to {mesh_dir}"
    return static_meshes


def new_level(map_path, replace_existing_map):
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path=map_path):
        if replace_existing_map:
            spear.log("Deleting existing map: ", map_path)
            success = unreal.EditorAssetLibrary.delete_asset(asset_path_to_delete=map_path)
            assert success
        else:
            raise AssertionError(f"Map already exists: {map_path}. Pass --replace-existing-map to overwrite it.")

    map_dir = posixpath.dirname(map_path)
    unreal.EditorAssetLibrary.make_directory(directory_path=map_dir)

    level_editor_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    created = level_editor_subsystem.new_level(asset_path=map_path)
    assert created, f"Could not create level: {map_path}"
    return level_editor_subsystem


def get_static_mesh_component(actor):
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    assert component is not None
    return component


if __name__ == "__main__":
    gltf_file = os.path.realpath(args.gltf_file) if args.gltf_file is not None else find_abandoned_room_gltf()
    room_meshes = import_room_meshes(gltf_file=gltf_file, mesh_dir=args.mesh_dir)
    level_editor_subsystem = new_level(map_path=args.map_path, replace_existing_map=args.replace_existing_map)

    spear.log("Spawning room meshes...")
    for room_mesh in room_meshes:
        room_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
            actor_class=unreal.StaticMeshActor,
            location=unreal.Vector(x=0.0, y=0.0, z=0.0),
            rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
        room_actor.set_actor_label("Abandoned_Room_Interior_" + room_mesh.get_name())
        room_actor.set_actor_scale3d(unreal.Vector(x=1.0, y=1.0, z=1.0))
        get_static_mesh_component(actor=room_actor).set_static_mesh(room_mesh)

    spear.log("Adding basic light and player start...")
    directional_light = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.DirectionalLight,
        location=unreal.Vector(x=0.0, y=0.0, z=600.0),
        rotation=unreal.Rotator(roll=0.0, pitch=-45.0, yaw=45.0))
    directional_light.set_actor_label("Setup_DirectionalLight")
    directional_light.light_component.set_editor_property(name="intensity", value=3.0)

    sky_light = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.SkyLight,
        location=unreal.Vector(x=0.0, y=0.0, z=300.0))
    sky_light.set_actor_label("Setup_SkyLight")

    player_start = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.PlayerStart,
        location=unreal.Vector(x=-250.0, y=0.0, z=120.0),
        rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    player_start.set_actor_label("Setup_PlayerStart")

    spear.log("Saving current level: ", args.map_path)
    level_editor_subsystem.save_current_level()

    spear.log("Saving project assets...")
    unreal.EditorAssetLibrary.save_directory(directory_path=args.mesh_dir, only_if_is_dirty=False, recursive=True)
    unreal.EditorAssetLibrary.save_directory(directory_path=posixpath.dirname(args.map_path), only_if_is_dirty=False, recursive=True)

    spear.log("Created map: ", args.map_path)
    spear.log("Done.")
