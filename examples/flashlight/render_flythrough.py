#
# Copyright (c) 2025 The SPEAR Development Team. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
# Copyright (c) 2022 Intel. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
#

import argparse
import math
import os
import shutil

import cv2
import numpy as np
import spear


MAPS = {
    "japanese_office_dark": "/Game/JapaneseOffice/Maps/Demonstration_Dark",
}

WAYPOINTS = [
    {"X": 0.0, "Y": -900.0, "Z": 165.0},
    {"X": 0.0, "Y": -350.0, "Z": 165.0},
    {"X": 0.0, "Y": 80.0, "Z": 165.0},
    {"X": 450.0, "Y": 420.0, "Z": 165.0},
    {"X": 1000.0, "Y": 900.0, "Z": 165.0},
    {"X": 520.0, "Y": 1320.0, "Z": 165.0},
    {"X": -420.0, "Y": 1320.0, "Z": 165.0},
]


parser = argparse.ArgumentParser()
parser.add_argument("--map", choices=sorted(MAPS.keys()), default="japanese_office_dark")
parser.add_argument("--duration-seconds", type=float, default=10.0)
parser.add_argument("--fps", type=int, default=24)
parser.add_argument("--width", type=int, default=1280)
parser.add_argument("--height", type=int, default=720)
parser.add_argument("--fov-degrees", type=float, default=80.0)
parser.add_argument("--intensity", type=float, default=30000.0)
parser.add_argument("--attenuation-radius", type=float, default=1200.0)
parser.add_argument("--inner-cone-angle", type=float, default=12.0)
parser.add_argument("--outer-cone-angle", type=float, default=30.0)
parser.add_argument("--output-dir", default=os.path.realpath(os.path.join(os.path.dirname(__file__), "flythrough_output")))
parser.add_argument("--keep-existing-output", action="store_true")
args = parser.parse_args()


def lerp(a, b, t):
    return a + (b - a)*t


def vector_to_numpy(vector):
    return np.array([vector["X"], vector["Y"], vector["Z"]], dtype=np.float64)


def numpy_to_vector(vector):
    return {"X": float(vector[0]), "Y": float(vector[1]), "Z": float(vector[2])}


def rotation_from_direction(direction):
    direction = direction / max(np.linalg.norm(direction), 1.0e-6)
    yaw = math.degrees(math.atan2(direction[1], direction[0]))
    pitch = math.degrees(math.atan2(direction[2], math.sqrt(direction[0]*direction[0] + direction[1]*direction[1])))
    return {"Roll": 0.0, "Pitch": pitch, "Yaw": yaw}


def build_pose_at_alpha(alpha):
    segment_count = len(WAYPOINTS) - 1
    scaled = min(max(alpha, 0.0), 1.0)*segment_count
    segment_index = min(int(scaled), segment_count - 1)
    local_alpha = scaled - segment_index

    p0 = vector_to_numpy(WAYPOINTS[segment_index])
    p1 = vector_to_numpy(WAYPOINTS[segment_index + 1])
    position = p0*(1.0 - local_alpha) + p1*local_alpha

    lookahead_alpha = min(alpha + 0.035, 1.0)
    lookahead_scaled = lookahead_alpha*segment_count
    lookahead_segment_index = min(int(lookahead_scaled), segment_count - 1)
    lookahead_local_alpha = lookahead_scaled - lookahead_segment_index
    q0 = vector_to_numpy(WAYPOINTS[lookahead_segment_index])
    q1 = vector_to_numpy(WAYPOINTS[lookahead_segment_index + 1])
    lookahead_position = q0*(1.0 - lookahead_local_alpha) + q1*lookahead_local_alpha

    direction = lookahead_position - position
    if np.linalg.norm(direction) < 1.0e-6:
        direction = p1 - p0

    return numpy_to_vector(position), rotation_from_direction(direction)


def make_viewport_desc(location, rotation):
    return {
        "viewport_size_x": args.width,
        "viewport_size_y": args.height,
        "camera_location": location,
        "camera_rotation": rotation,
        "is_perspective": True,
        "fov_degrees": args.fov_degrees,
        "aspect_ratio": args.width / args.height,
        "ortho_width": None,
        "post_process_volumes": [],
    }


def prepare_output_dir(output_dir):
    frames_dir = os.path.join(output_dir, "frames")
    if os.path.exists(output_dir) and not args.keep_existing_output:
        shutil.rmtree(output_dir)
    os.makedirs(frames_dir, exist_ok=True)
    return frames_dir


def write_video(frames_dir, video_file, frame_count):
    first_frame = cv2.imread(os.path.join(frames_dir, "frame_0000.png"), cv2.IMREAD_COLOR)
    if first_frame is None:
        spear.log("No frames found; skipping video encode.")
        return False

    height, width = first_frame.shape[:2]
    video_writer = cv2.VideoWriter(video_file, cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (width, height))
    if not video_writer.isOpened():
        spear.log("OpenCV could not open an MP4 writer; PNG frames are still available.")
        return False

    for frame_index in range(frame_count):
        frame_file = os.path.join(frames_dir, f"frame_{frame_index:04d}.png")
        frame = cv2.imread(frame_file, cv2.IMREAD_COLOR)
        if frame is None:
            video_writer.release()
            raise RuntimeError(f"Missing rendered frame: {frame_file}")
        video_writer.write(frame)

    video_writer.release()
    return True


if __name__ == "__main__":
    frames_dir = prepare_output_dir(output_dir=args.output_dir)
    video_file = os.path.join(args.output_dir, "flashlight_flythrough.mp4")

    config = spear.get_config(user_config_files=[os.path.realpath(os.path.join(os.path.dirname(__file__), "user_config.yaml"))])
    config.defrost()
    config.SPEAR.INSTANCE.COMMAND_LINE_ARGS.resx = args.width
    config.SPEAR.INSTANCE.COMMAND_LINE_ARGS.resy = args.height
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.OVERRIDE_BENCHMARKING = True
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.BENCHMARKING = True
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.BENCHMARKING_MAX_NUM_FRAMES = int(args.duration_seconds*args.fps) + 8
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.OVERRIDE_GAME_DEFAULT_MAP = True
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.GAME_DEFAULT_MAP = MAPS[args.map]
    config.freeze()

    spear.configure_system(config=config)
    instance = spear.Instance(config=config)
    game = instance.get_game()

    frame_count = int(args.duration_seconds*args.fps)
    camera_sensor = None
    camera_component = None
    flashlight = None

    try:
        with instance.begin_frame():
            bp_camera_sensor_uclass = game.unreal_service.load_class(
                uclass="AActor",
                name="/SpContent/Blueprints/BP_CameraSensor.BP_CameraSensor_C")
            camera_sensor = game.unreal_service.spawn_actor(uclass=bp_camera_sensor_uclass)
            camera_component = game.unreal_service.get_component_by_name(
                actor=camera_sensor,
                component_name="DefaultSceneRoot.final_tone_curve_hdr_",
                uclass="USpSceneCaptureComponent2D")

            location, rotation = build_pose_at_alpha(alpha=0.0)
            game.rendering_service.align_camera_with_viewport(
                camera_sensor=camera_sensor,
                camera_components=camera_component,
                viewport_desc=make_viewport_desc(location=location, rotation=rotation),
                widths=args.width,
                heights=args.height)

            camera_component.BufferingMode = "SingleBuffered"
            camera_component.Initialize()
            camera_component.initialize_sp_funcs()

            flashlight = game.unreal_service.spawn_actor(uclass="ASpotLight", location=location, rotation=rotation)
            game.unreal_service.set_stable_name_for_actor(actor=flashlight, stable_name="Debug/ProgrammaticCameraFlashlight")
            flashlight.K2_GetRootComponent().SetMobility(NewMobility="Movable")
            spot_light_component = game.unreal_service.get_component_by_class(actor=flashlight, uclass="USpotLightComponent")
            spot_light_component.SetIntensity(NewIntensity=args.intensity)
            spot_light_component.SetAttenuationRadius(NewRadius=args.attenuation_radius)
            spot_light_component.SetInnerConeAngle(NewInnerConeAngle=args.inner_cone_angle)
            spot_light_component.SetOuterConeAngle(NewOuterConeAngle=args.outer_cone_angle)

        with instance.end_frame(single_step=True):
            pass

        instance.step(num_frames=2)

        for frame_index in range(frame_count):
            alpha = frame_index / max(frame_count - 1, 1)
            location, rotation = build_pose_at_alpha(alpha=alpha)

            with instance.begin_frame():
                camera_sensor.K2_SetActorLocationAndRotation(
                    NewLocation=location,
                    NewRotation=rotation,
                    bSweep=False,
                    bTeleport=True)
                flashlight.K2_SetActorLocationAndRotation(
                    NewLocation=location,
                    NewRotation=rotation,
                    bSweep=False,
                    bTeleport=True)
            with instance.end_frame(single_step=True):
                data_bundle = camera_component.read_pixels()

            frame = data_bundle["arrays"]["data"]
            if frame.shape[2] == 4:
                frame = frame[:, :, :3]
            frame_file = os.path.join(frames_dir, f"frame_{frame_index:04d}.png")
            cv2.imwrite(frame_file, frame)

            if frame_index % args.fps == 0:
                spear.log(f"Rendered frame {frame_index + 1}/{frame_count}: {frame_file}")

        wrote_video = write_video(frames_dir=frames_dir, video_file=video_file, frame_count=frame_count)
        if wrote_video:
            spear.log("Wrote video: ", video_file)
        spear.log("Wrote frames: ", frames_dir)

    finally:
        if instance.is_running():
            with instance.begin_frame():
                pass
            with instance.end_frame(single_step=True):
                if camera_component is not None:
                    camera_component.terminate_sp_funcs()
                    camera_component.Terminate()
                if camera_sensor is not None:
                    game.unreal_service.destroy_actor(actor=camera_sensor)
                if flashlight is not None:
                    game.unreal_service.destroy_actor(actor=flashlight)
            instance.step()

        instance.close()

    spear.log("Done.")
