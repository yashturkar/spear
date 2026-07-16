import argparse
import json
import os
import posixpath

import unreal


parser = argparse.ArgumentParser()
parser.add_argument("--map-path", required=True)
parser.add_argument("--report", required=True)
args = parser.parse_args()

REMOVE_PREFIXES = (
    "Infinigen_living-room_0_0_",
    "Infinigen_bedroom_0_0_",
    "Infinigen_kitchen_0_0_",
    "Infinigen_bathroom_0_0_",
)


def actor_class_name(actor):
    return actor.get_class().get_name()


def vector_to_dict(vector):
    return {"x": round(vector.x, 3), "y": round(vector.y, 3), "z": round(vector.z, 3)}


def actor_bounds(actor):
    origin, extent = actor.get_actor_bounds(only_colliding_components=False)
    return {
        "origin": vector_to_dict(origin),
        "extent": vector_to_dict(extent),
    }


def should_remove(actor):
    if actor_class_name(actor) != "StaticMeshActor":
        return False
    label = actor.get_actor_label()
    return any(label.startswith(prefix) for prefix in REMOVE_PREFIXES)


if __name__ == "__main__":
    level_editor_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    loaded = level_editor_subsystem.load_level(asset_path=args.map_path)
    assert loaded, f"Could not load level: {args.map_path}"

    removed = []
    kept_static_mesh_count = 0
    for actor in list(unreal.EditorLevelLibrary.get_all_level_actors()):
        if should_remove(actor):
            removed.append({
                "label": actor.get_actor_label(),
                "class": actor_class_name(actor),
                "bounds": actor_bounds(actor),
            })
            unreal.EditorLevelLibrary.destroy_actor(actor)
        elif actor_class_name(actor) == "StaticMeshActor":
            kept_static_mesh_count += 1

    saved_level = level_editor_subsystem.save_current_level()
    assert saved_level, f"Could not save level: {args.map_path}"
    unreal.EditorAssetLibrary.save_directory(
        directory_path=posixpath.dirname(args.map_path),
        only_if_is_dirty=False,
        recursive=True,
    )

    report = {
        "map_path": args.map_path,
        "removed_count": len(removed),
        "removed": sorted(removed, key=lambda item: item["label"]),
        "kept_static_mesh_count_after_removal": kept_static_mesh_count,
        "saved": bool(saved_level),
        "remove_prefixes": REMOVE_PREFIXES,
    }
    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    unreal.log(f"Wrote stray-room cleanup report: {args.report}")
    unreal.log(json.dumps(report, indent=2, sort_keys=True))
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
