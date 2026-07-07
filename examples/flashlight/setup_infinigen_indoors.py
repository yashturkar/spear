#
# Copyright (c) 2025 The SPEAR Development Team. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
# Copyright (c) 2022 Intel. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
#

import argparse
import os
import posixpath

import spear
import unreal


WORLD_NAME = "infinigen_indoors_0000"
CONTENT_ROOT = f"/Game/SPEAR/Scenes/{WORLD_NAME}"
DEFAULT_FBX_FILE = "/home/yashturkar/Workspace/infinigen/outputs/spear_export/export_scene.blend/export_scene.fbx"
DEFAULT_MESH_DIR = f"{CONTENT_ROOT}/Meshes"
DEFAULT_MAP_PATH = f"{CONTENT_ROOT}/Maps/{WORLD_NAME}"


parser = argparse.ArgumentParser()
parser.add_argument("--fbx-file", default=DEFAULT_FBX_FILE)
parser.add_argument("--mesh-dir", default=DEFAULT_MESH_DIR)
parser.add_argument("--map-path", default=DEFAULT_MAP_PATH)
parser.add_argument("--replace-existing-assets", action="store_true")
parser.add_argument("--replace-existing-map", action="store_true")
parser.add_argument("--no-auto-generate-collision", action="store_true")
parser.add_argument("--no-import-materials", action="store_true")
parser.add_argument("--no-import-textures", action="store_true")
parser.add_argument("--player-start-x", "--player-start-position-x", type=float, default=-250.0)
parser.add_argument("--player-start-y", "--player-start-position-y", type=float, default=0.0)
parser.add_argument("--player-start-z", "--player-start-position-z", type=float, default=120.0)
parser.add_argument("--player-start-yaw", type=float, default=0.0)
parser.add_argument("--actor-scale", type=float, default=1.0)
args = parser.parse_args()


def get_static_meshes(mesh_dir):
    static_meshes = []
    if not unreal.EditorAssetLibrary.does_directory_exist(directory_path=mesh_dir):
        return static_meshes

    for asset_path in unreal.EditorAssetLibrary.list_assets(directory_path=mesh_dir, recursive=True, include_folder=False):
        asset = unreal.load_asset(name=asset_path)
        if isinstance(asset, unreal.StaticMesh):
            static_meshes.append(asset)

    static_meshes = sorted(static_meshes, key=lambda asset: asset.get_path_name())
    return static_meshes


def fail_if_unrequested_replacement(mesh_dir, map_path, replace_existing_assets, replace_existing_map):
    if unreal.EditorAssetLibrary.does_directory_exist(directory_path=mesh_dir) and not replace_existing_assets:
        raise AssertionError(f"Asset directory already exists: {mesh_dir}. Pass --replace-existing-assets to overwrite it.")

    if unreal.EditorAssetLibrary.does_asset_exist(asset_path=map_path) and not replace_existing_map:
        raise AssertionError(f"Map already exists: {map_path}. Pass --replace-existing-map to overwrite it.")


def replace_existing_targets(mesh_dir, map_path, replace_existing_assets, replace_existing_map):
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path=map_path) and replace_existing_map:
        spear.log("Deleting existing map: ", map_path)
        success = unreal.EditorAssetLibrary.delete_asset(asset_path_to_delete=map_path)
        assert success, f"Could not delete existing map: {map_path}"

    if unreal.EditorAssetLibrary.does_directory_exist(directory_path=mesh_dir) and replace_existing_assets:
        spear.log("Deleting existing asset directory: ", mesh_dir)
        success = unreal.EditorAssetLibrary.delete_directory(directory_path=mesh_dir)
        assert success, f"Could not delete existing asset directory: {mesh_dir}"


def try_set_editor_property(obj, name, value):
    try:
        obj.set_editor_property(name=name, value=value)
        return True
    except Exception as e:
        spear.log("Could not set editor property: ", obj.get_class().get_name(), ".", name, " (", str(e), ")")
        return False


def make_fbx_import_options(import_materials, import_textures, auto_generate_collision):
    options = unreal.FbxImportUI()
    try_set_editor_property(obj=options, name="import_mesh", value=True)
    try_set_editor_property(obj=options, name="import_as_skeletal", value=False)
    try_set_editor_property(obj=options, name="import_materials", value=import_materials)
    try_set_editor_property(obj=options, name="import_textures", value=import_textures)

    try:
        static_mesh_import_data = options.get_editor_property(name="static_mesh_import_data")
        try_set_editor_property(obj=static_mesh_import_data, name="combine_meshes", value=False)
        try_set_editor_property(obj=static_mesh_import_data, name="auto_generate_collision", value=auto_generate_collision)
    except Exception as e:
        spear.log("Could not configure static mesh FBX import data: ", str(e))

    return options


def import_infinigen_meshes(fbx_file, mesh_dir, import_materials, import_textures, auto_generate_collision):
    spear.log("Importing Infinigen FBX: ", fbx_file)
    spear.log("Destination mesh directory: ", mesh_dir)
    spear.log("Import materials: ", import_materials)
    spear.log("Import textures: ", import_textures)
    spear.log("Auto-generate collision: ", auto_generate_collision)
    success = unreal.EditorAssetLibrary.make_directory(directory_path=mesh_dir)
    assert success, f"Could not create mesh directory: {mesh_dir}"

    import_task = unreal.AssetImportTask()
    import_task.set_editor_property(name="async_", value=False)
    import_task.set_editor_property(name="automated", value=True)
    import_task.set_editor_property(name="destination_path", value=mesh_dir)
    import_task.set_editor_property(name="filename", value=fbx_file)
    import_task.set_editor_property(name="replace_existing", value=False)
    import_task.set_editor_property(name="replace_existing_settings", value=False)
    import_task.set_editor_property(name="save", value=True)
    import_task.set_editor_property(name="options", value=make_fbx_import_options(
        import_materials=import_materials,
        import_textures=import_textures,
        auto_generate_collision=auto_generate_collision))

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    asset_tools.import_asset_tasks(import_tasks=[import_task])

    static_meshes = get_static_meshes(mesh_dir=mesh_dir)
    assert len(static_meshes) > 0, f"No static meshes were found after importing {fbx_file} to {mesh_dir}"

    unreal.EditorAssetLibrary.save_directory(directory_path=mesh_dir, only_if_is_dirty=False, recursive=True)
    return static_meshes


def new_level(map_path):
    map_dir = posixpath.dirname(map_path)
    success = unreal.EditorAssetLibrary.make_directory(directory_path=map_dir)
    assert success, f"Could not create map directory: {map_dir}"

    level_editor_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    created = level_editor_subsystem.new_level(asset_path=map_path)
    assert created, f"Could not create level: {map_path}"
    return level_editor_subsystem


def get_static_mesh_component(actor):
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    assert component is not None
    return component


def vector_to_string(vector):
    return f"({vector.x:.2f}, {vector.y:.2f}, {vector.z:.2f})"


def include_actor_bounds(bounds, actor):
    origin, extent = actor.get_actor_bounds(only_colliding_components=False)
    min_x = origin.x - extent.x
    min_y = origin.y - extent.y
    min_z = origin.z - extent.z
    max_x = origin.x + extent.x
    max_y = origin.y + extent.y
    max_z = origin.z + extent.z

    if bounds["min"] is None:
        bounds["min"] = unreal.Vector(x=min_x, y=min_y, z=min_z)
        bounds["max"] = unreal.Vector(x=max_x, y=max_y, z=max_z)
    else:
        bounds["min"].x = min(bounds["min"].x, min_x)
        bounds["min"].y = min(bounds["min"].y, min_y)
        bounds["min"].z = min(bounds["min"].z, min_z)
        bounds["max"].x = max(bounds["max"].x, max_x)
        bounds["max"].y = max(bounds["max"].y, max_y)
        bounds["max"].z = max(bounds["max"].z, max_z)


def spawn_static_mesh_actor(static_mesh, actor_scale):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        actor_class=unreal.StaticMeshActor,
        location=unreal.Vector(x=0.0, y=0.0, z=0.0),
        rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=0.0))
    actor.set_actor_label("Infinigen_" + static_mesh.get_name())
    actor.set_actor_scale3d(unreal.Vector(x=actor_scale, y=actor_scale, z=actor_scale))
    get_static_mesh_component(actor=actor).set_static_mesh(static_mesh)
    return actor


def add_basic_lighting_and_player_start(player_start_x, player_start_y, player_start_z, player_start_yaw):
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
        location=unreal.Vector(x=player_start_x, y=player_start_y, z=player_start_z),
        rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=player_start_yaw))
    player_start.set_actor_label("Setup_PlayerStart")


def validate_args(parsed_args):
    fbx_file = os.path.realpath(parsed_args.fbx_file)
    assert os.path.exists(fbx_file), f"FBX file does not exist: {fbx_file}"
    assert fbx_file.lower().endswith(".fbx"), f"Expected an .fbx file, got: {fbx_file}"
    assert parsed_args.actor_scale > 0.0, f"--actor-scale must be greater than zero, got: {parsed_args.actor_scale}"
    return fbx_file


if __name__ == "__main__":
    fbx_file = validate_args(parsed_args=args)
    fail_if_unrequested_replacement(
        mesh_dir=args.mesh_dir,
        map_path=args.map_path,
        replace_existing_assets=args.replace_existing_assets,
        replace_existing_map=args.replace_existing_map)
    replace_existing_targets(
        mesh_dir=args.mesh_dir,
        map_path=args.map_path,
        replace_existing_assets=args.replace_existing_assets,
        replace_existing_map=args.replace_existing_map)

    static_meshes = import_infinigen_meshes(
        fbx_file=fbx_file,
        mesh_dir=args.mesh_dir,
        import_materials=not args.no_import_materials,
        import_textures=not args.no_import_textures,
        auto_generate_collision=not args.no_auto_generate_collision)
    level_editor_subsystem = new_level(map_path=args.map_path)

    spear.log("Spawning Infinigen static meshes...")
    mesh_bounds = {"min": None, "max": None}
    mesh_actors = []
    for static_mesh in static_meshes:
        mesh_actor = spawn_static_mesh_actor(static_mesh=static_mesh, actor_scale=args.actor_scale)
        mesh_actors.append(mesh_actor)
        include_actor_bounds(bounds=mesh_bounds, actor=mesh_actor)

    spear.log("Adding basic light and player start...")
    add_basic_lighting_and_player_start(
        player_start_x=args.player_start_x,
        player_start_y=args.player_start_y,
        player_start_z=args.player_start_z,
        player_start_yaw=args.player_start_yaw)

    spear.log("Saving current level: ", args.map_path)
    level_editor_subsystem.save_current_level()

    spear.log("Saving project assets...")
    unreal.EditorAssetLibrary.save_directory(directory_path=args.mesh_dir, only_if_is_dirty=False, recursive=True)
    unreal.EditorAssetLibrary.save_directory(directory_path=posixpath.dirname(args.map_path), only_if_is_dirty=False, recursive=True)

    spear.log("Imported static mesh assets: ", len(static_meshes))
    spear.log("Spawned static mesh actors: ", len(mesh_actors))
    if mesh_bounds["min"] is not None:
        dimensions = mesh_bounds["max"] - mesh_bounds["min"]
        spear.log("Approximate spawned mesh bounds min: ", vector_to_string(mesh_bounds["min"]))
        spear.log("Approximate spawned mesh bounds max: ", vector_to_string(mesh_bounds["max"]))
        spear.log("Approximate spawned mesh dimensions: ", vector_to_string(dimensions))
    spear.log("Created Infinigen indoor map: ", args.map_path)
    spear.log("Done.")
