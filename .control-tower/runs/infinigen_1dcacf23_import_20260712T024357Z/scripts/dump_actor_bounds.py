import argparse
import json
import math
import os

import unreal


parser = argparse.ArgumentParser()
parser.add_argument("--map-path", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()


def actor_class_name(actor):
    return actor.get_class().get_name()


def vector_to_dict(vector):
    return {"x": round(vector.x, 3), "y": round(vector.y, 3), "z": round(vector.z, 3)}


def asset_path_for_static_mesh_actor(actor):
    component = actor.static_mesh_component
    if component is None:
        return None
    mesh = component.static_mesh
    if mesh is None:
        return None
    return mesh.get_path_name()


def actor_record(actor):
    origin, extent = actor.get_actor_bounds(only_colliding_components=False)
    max_extent = max(extent.x, extent.y, extent.z)
    radius = math.sqrt(extent.x * extent.x + extent.y * extent.y + extent.z * extent.z)
    return {
        "label": actor.get_actor_label(),
        "class": actor_class_name(actor),
        "location": vector_to_dict(actor.get_actor_location()),
        "origin": vector_to_dict(origin),
        "extent": vector_to_dict(extent),
        "max_extent": round(max_extent, 3),
        "radius": round(radius, 3),
        "static_mesh": asset_path_for_static_mesh_actor(actor) if actor_class_name(actor) == "StaticMeshActor" else None,
    }


if __name__ == "__main__":
    level_editor_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    loaded = level_editor_subsystem.load_level(asset_path=args.map_path)
    assert loaded, f"Could not load level: {args.map_path}"

    records = [
        actor_record(actor)
        for actor in unreal.EditorLevelLibrary.get_all_level_actors()
    ]
    static_mesh_records = [record for record in records if record["class"] == "StaticMeshActor"]
    report = {
        "map_path": args.map_path,
        "actor_count": len(records),
        "static_mesh_actor_count": len(static_mesh_records),
        "largest_static_mesh_actors": sorted(
            static_mesh_records,
            key=lambda record: record["radius"],
            reverse=True,
        )[:40],
        "all_static_mesh_actors": sorted(static_mesh_records, key=lambda record: record["label"]),
        "all_actors": sorted(records, key=lambda record: record["label"]),
    }
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    unreal.log(f"Wrote actor bounds report: {args.output}")
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
