#
# Copyright (c) 2025 The SPEAR Development Team. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
# Copyright (c) 2022 Intel. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
#

import argparse
import math
import os

import cv2
import numpy as np


PREFERRED_ORDER = [
    "rgb",
    "depth_meters",
    "world_normal",
    "world_position",
    "diffuse_color",
    "roughness",
    "metallic",
    "specular_for_lighting",
    "material_ao",
    "unlit",
    "object_ids",
    "segmentation_ids",
]


parser = argparse.ArgumentParser()
parser.add_argument("--frames-dir", default=os.path.realpath(os.path.join(os.path.dirname(__file__), "flythrough_output", "frames")))
parser.add_argument("--output-file", default=os.path.realpath(os.path.join(os.path.dirname(__file__), "flythrough_output", "flashlight_flythrough_all_modalities.mp4")))
parser.add_argument("--fps", type=int, default=24)
parser.add_argument("--columns", type=int, default=0)
parser.add_argument("--tile-width", type=int, default=360)
parser.add_argument("--tile-height", type=int, default=240)
parser.add_argument("--include-preview", action="store_true")
args = parser.parse_args()


def get_modality_dirs(frames_dir):
    modality_names = []
    for name in os.listdir(frames_dir):
        path = os.path.join(frames_dir, name)
        if not os.path.isdir(path):
            continue
        if name == "preview" and not args.include_preview:
            continue
        if os.path.exists(os.path.join(path, "frame_0000.png")):
            modality_names.append(name)

    preferred = [name for name in PREFERRED_ORDER if name in modality_names]
    extra = sorted(name for name in modality_names if name not in preferred)
    return [(name, os.path.join(frames_dir, name)) for name in preferred + extra]


def get_common_frame_names(modality_dirs):
    frame_name_sets = []
    for _, modality_dir in modality_dirs:
        frame_names = {
            name for name in os.listdir(modality_dir)
            if name.startswith("frame_") and name.endswith(".png")
        }
        frame_name_sets.append(frame_names)

    common_frame_names = set.intersection(*frame_name_sets)
    return sorted(common_frame_names)


def add_label(image, label):
    result = image.copy()
    label_width = min(result.shape[1], max(160, 12*len(label)))
    cv2.rectangle(result, (0, 0), (label_width, 30), (0, 0, 0), thickness=-1)
    cv2.putText(result, label, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return result


def read_tile(image_file, label):
    image = cv2.imread(image_file, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Could not read image: {image_file}")
    image = cv2.resize(image, (args.tile_width, args.tile_height), interpolation=cv2.INTER_AREA)
    return add_label(image=image, label=label)


def build_grid(tiles, columns):
    rows = int(math.ceil(len(tiles) / columns))
    blank = np.zeros_like(tiles[0])
    padded_tiles = tiles + [blank for _ in range(rows*columns - len(tiles))]
    row_images = []
    for row_index in range(rows):
        row_tiles = padded_tiles[row_index*columns:(row_index + 1)*columns]
        row_images.append(np.concatenate(row_tiles, axis=1))
    return np.concatenate(row_images, axis=0)


def main():
    modality_dirs = get_modality_dirs(frames_dir=args.frames_dir)
    if not modality_dirs:
        raise RuntimeError(f"No modality frame folders found in: {args.frames_dir}")

    frame_names = get_common_frame_names(modality_dirs=modality_dirs)
    if not frame_names:
        raise RuntimeError("No common frame_*.png files found across modality folders.")

    columns = args.columns
    if columns <= 0:
        columns = int(math.ceil(math.sqrt(len(modality_dirs))))

    first_tiles = [
        read_tile(image_file=os.path.join(modality_dir, frame_names[0]), label=name)
        for name, modality_dir in modality_dirs
    ]
    first_grid = build_grid(tiles=first_tiles, columns=columns)
    height, width = first_grid.shape[:2]

    os.makedirs(os.path.dirname(args.output_file), exist_ok=True)
    video_writer = cv2.VideoWriter(args.output_file, cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (width, height))
    if not video_writer.isOpened():
        raise RuntimeError(f"Could not open video writer: {args.output_file}")

    print("Modalities:")
    for name, _ in modality_dirs:
        print(f"  {name}")
    print(f"Writing {len(frame_names)} frames to: {args.output_file}")

    for frame_index, frame_name in enumerate(frame_names):
        tiles = [
            read_tile(image_file=os.path.join(modality_dir, frame_name), label=name)
            for name, modality_dir in modality_dirs
        ]
        video_writer.write(build_grid(tiles=tiles, columns=columns))
        if frame_index % args.fps == 0:
            print(f"  frame {frame_index + 1}/{len(frame_names)}")

    video_writer.release()
    print("Done.")


if __name__ == "__main__":
    main()
