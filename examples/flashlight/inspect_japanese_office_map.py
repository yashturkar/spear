#
# Copyright (c) 2025 The SPEAR Development Team. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
# Copyright (c) 2022 Intel. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
#

import argparse
import json
import os

import unreal


parser = argparse.ArgumentParser()
parser.add_argument("--map-path", default="/Game/JapaneseOffice/Maps/Demonstration_Dark")
parser.add_argument("--output-file", default=os.path.realpath(os.path.join(os.path.dirname(__file__), "japanese_office_actors.json")))
args = parser.parse_args()


def vector_to_dict(vector):
    return {"x": vector.x, "y": vector.y, "z": vector.z}


if __name__ == "__main__":
    level_editor_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    loaded = level_editor_subsystem.load_level(asset_path=args.map_path)
    assert loaded, f"Could not load level: {args.map_path}"

    actor_descs = []
    for actor in unreal.EditorLevelLibrary.get_all_level_actors():
        origin, extent = actor.get_actor_bounds(only_colliding_components=False)
        location = actor.get_actor_location()
        actor_descs.append({
            "label": actor.get_actor_label(),
            "name": actor.get_name(),
            "class": actor.get_class().get_name(),
            "location": vector_to_dict(location),
            "bounds_origin": vector_to_dict(origin),
            "bounds_extent": vector_to_dict(extent),
        })

    actor_descs = sorted(actor_descs, key=lambda desc: (desc["class"], desc["label"]))
    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(actor_descs, f, indent=2, sort_keys=True)

    unreal.log(f"Wrote actor dump: {args.output_file}")
