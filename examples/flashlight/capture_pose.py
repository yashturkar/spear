#
# Copyright (c) 2025 The SPEAR Development Team. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
# Copyright (c) 2022 Intel. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
#

import argparse
import json
import os
import time

import spear


parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True)
parser.add_argument("--output-file", default=os.path.realpath(os.path.join(os.path.dirname(__file__), "camera_poses.jsonl")))
args = parser.parse_args()


def to_plain_dict(value):
    return json.loads(json.dumps(value))


if __name__ == "__main__":
    config = spear.get_config(user_config_files=[os.path.realpath(os.path.join(os.path.dirname(__file__), "user_config.yaml"))])
    config.defrost()
    config.SPEAR.LAUNCH_MODE = "none"
    config.freeze()

    spear.configure_system(config=config)
    instance = spear.Instance(config=config)
    game = instance.get_game()

    with instance.begin_frame():
        viewport_desc = game.rendering_service.get_current_viewport_desc(only_get_pose=True)

    with instance.end_frame():
        pass

    pose_desc = {
        "name": args.name,
        "time": time.time(),
        "camera_location": to_plain_dict(viewport_desc["camera_location"]),
        "camera_rotation": to_plain_dict(viewport_desc["camera_rotation"]),
    }

    os.makedirs(os.path.dirname(args.output_file), exist_ok=True)
    with open(args.output_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(pose_desc, sort_keys=True) + "\n")

    spear.log("Captured pose: ", pose_desc)
    spear.log("Output file: ", args.output_file)
    instance.close()
