#
# Copyright (c) 2025 The SPEAR Development Team. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
# Copyright (c) 2022 Intel. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
#

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
import os
import re
import shutil
import sys
import time

import numpy as np
import spear


INPUT_POLL_PERIOD_SECONDS = 1.0 / 60.0

MAPS = {
    "apartment_0000": "/Game/SPEAR/Scenes/apartment_0000/Maps/apartment_0000",
    "debug_0000": "/Game/SPEAR/Scenes/debug_0000/Maps/debug_0000",
    "debug_0001": "/Game/SPEAR/Scenes/debug_0001/Maps/debug_0001",
    "advanced_lighting": "/Game/StarterContent/Maps/Advanced_Lighting",
    "japanese_office": "/Game/JapaneseOffice/Maps/Demonstration",
    "japanese_office_dark": "/Game/JapaneseOffice/Maps/Demonstration_Dark",
    "minimal_default": "/Game/StarterContent/Maps/Minimal_Default",
    "starter_map": "/Game/StarterContent/Maps/StarterMap",
    "third_person": "/Game/ThirdPerson/Maps/ThirdPersonMap",
    "vehicle": "/Game/VehicleTemplate/Maps/VehicleExampleMap",
    "vehicle_offroad": "/Game/VehicleTemplate/Maps/VehicleOffroadExampleMap",
}

CAPTURE_COMPONENT_DESCS = [
    {
        "name": "rgb",
        "long_name": "DefaultSceneRoot.final_tone_curve_hdr_",
    },
    {
        "name": "depth_meters",
        "long_name": "DefaultSceneRoot.sp_depth_meters_",
    },
]

DEFAULT_ORBIT_SPEC_FILE = os.path.realpath(os.path.join(os.path.dirname(__file__), "orbit_spec.json"))
DEFAULT_LIGHT_SETTINGS_FILE = os.path.realpath(os.path.join(os.path.dirname(__file__), "light_settings.example.json"))
DEFAULT_OUTPUT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), "orbit_collection_output"))
LIGHT_SETTING_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


@dataclass
class LightCommand:
    enabled: bool
    intensity: float
    yaw_offset_degrees: float
    pitch_offset_degrees: float


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["teleop", "render"], default="teleop")
    parser.add_argument("--map", choices=sorted(MAPS.keys()), default=None)
    parser.add_argument("--map-path", default=None)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=float, default=24.0)
    parser.add_argument("--fov-degrees", type=float, default=80.0)
    parser.add_argument("--intensity", type=float, default=30000.0)
    parser.add_argument("--attenuation-radius", type=float, default=1200.0)
    parser.add_argument("--inner-cone-angle", type=float, default=12.0)
    parser.add_argument("--outer-cone-angle", type=float, default=30.0)
    parser.add_argument("--initial-light-disabled", action="store_true")
    parser.add_argument("--light-yaw-offset-degrees", type=float, default=0.0)
    parser.add_argument("--light-pitch-offset-degrees", type=float, default=0.0)
    parser.add_argument("--movement-speed", type=float, default=1200.0)
    parser.add_argument("--disable-scene-lights", action="store_true")
    parser.add_argument("--orbit-duration-seconds", type=float, default=10.0)
    parser.add_argument("--fallback-target-distance", type=float, default=500.0)
    parser.add_argument("--target-ray-distance", type=float, default=100000.0)
    parser.add_argument("--orbit-spec-file", default=DEFAULT_ORBIT_SPEC_FILE)
    parser.add_argument("--light-settings-file", default=DEFAULT_LIGHT_SETTINGS_FILE)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--keep-existing-output", action="store_true")
    parser.add_argument("--select-key", default="Gamepad_RightShoulder")
    parser.add_argument("--orbit-key", default="Gamepad_LeftShoulder")
    parser.add_argument("--toggle-key", default="Gamepad_FaceButton_Right")
    parser.add_argument("--aim-yaw-min-degrees", type=float, default=-30.0)
    parser.add_argument("--aim-yaw-max-degrees", type=float, default=30.0)
    parser.add_argument("--aim-pitch-min-degrees", type=float, default=-30.0)
    parser.add_argument("--aim-pitch-max-degrees", type=float, default=30.0)
    parser.add_argument("--aim-rate-degrees-per-second", type=float, default=90.0)
    parser.add_argument("--aim-left-key", default="Gamepad_DPad_Left")
    parser.add_argument("--aim-right-key", default="Gamepad_DPad_Right")
    parser.add_argument("--aim-up-key", default="Gamepad_DPad_Up")
    parser.add_argument("--aim-down-key", default="Gamepad_DPad_Down")
    parser.add_argument("--idle-period-seconds", type=float, default=0.5)
    parser.add_argument("--settle-frames", type=int, default=2)
    args = parser.parse_args(argv)

    if args.map is not None and args.map_path is not None:
        parser.error("--map and --map-path are mutually exclusive")
    if args.width <= 0:
        parser.error("--width must be positive")
    if args.height <= 0:
        parser.error("--height must be positive")
    if args.fps <= 0.0:
        parser.error("--fps must be positive")
    if args.fov_degrees <= 0.0:
        parser.error("--fov-degrees must be positive")
    if args.intensity < 0.0:
        parser.error("--intensity must be non-negative")
    if args.attenuation_radius <= 0.0:
        parser.error("--attenuation-radius must be positive")
    if args.inner_cone_angle < 0.0:
        parser.error("--inner-cone-angle must be non-negative")
    if args.outer_cone_angle < args.inner_cone_angle:
        parser.error("--outer-cone-angle must be greater than or equal to --inner-cone-angle")
    if args.movement_speed <= 0.0:
        parser.error("--movement-speed must be positive")
    if args.orbit_duration_seconds <= 0.0:
        parser.error("--orbit-duration-seconds must be positive")
    if args.fallback_target_distance <= 0.0:
        parser.error("--fallback-target-distance must be positive")
    if args.target_ray_distance <= 0.0:
        parser.error("--target-ray-distance must be positive")
    if args.aim_yaw_min_degrees > args.aim_yaw_max_degrees:
        parser.error("--aim-yaw-min-degrees must be less than or equal to --aim-yaw-max-degrees")
    if args.aim_pitch_min_degrees > args.aim_pitch_max_degrees:
        parser.error("--aim-pitch-min-degrees must be less than or equal to --aim-pitch-max-degrees")
    if args.aim_rate_degrees_per_second < 0.0:
        parser.error("--aim-rate-degrees-per-second must be non-negative")
    if args.settle_frames < 0:
        parser.error("--settle-frames must be non-negative")

    return args


def import_cv2():
    try:
        import cv2
    except ImportError:
        raise SystemExit(
            "OpenCV is required to write orbit collection frames and videos.\n"
            "Install SPEAR's Python examples dependencies with: python -m pip install -e 'python[examples]'"
        ) from None
    return cv2


def to_plain_dict(value):
    return json.loads(json.dumps(value))


def get_case_insensitive_value(desc, key_name):
    key_by_lower = {key.lower(): key for key in desc.keys()}
    return desc[key_by_lower[key_name.lower()]]


def vector_to_numpy(vector):
    return np.array([
        float(get_case_insensitive_value(desc=vector, key_name="X")),
        float(get_case_insensitive_value(desc=vector, key_name="Y")),
        float(get_case_insensitive_value(desc=vector, key_name="Z")),
    ], dtype=np.float64)


def numpy_to_vector(vector):
    return {"X": float(vector[0]), "Y": float(vector[1]), "Z": float(vector[2])}


def rotation_to_pitch_yaw_roll(rotation):
    return (
        float(get_case_insensitive_value(desc=rotation, key_name="Pitch")),
        float(get_case_insensitive_value(desc=rotation, key_name="Yaw")),
        float(get_case_insensitive_value(desc=rotation, key_name="Roll")),
    )


def rotation_from_direction(direction):
    direction = np.asarray(direction, dtype=np.float64)
    direction = direction / max(float(np.linalg.norm(direction)), 1.0e-6)
    yaw = math.degrees(math.atan2(direction[1], direction[0]))
    pitch = math.degrees(math.atan2(direction[2], math.sqrt(direction[0]*direction[0] + direction[1]*direction[1])))
    return {"Roll": 0.0, "Pitch": pitch, "Yaw": yaw}


def forward_vector_from_rotation(rotation):
    pitch, yaw, _ = rotation_to_pitch_yaw_roll(rotation=rotation)
    pitch_radians = math.radians(pitch)
    yaw_radians = math.radians(yaw)
    return np.array([
        math.cos(pitch_radians) * math.cos(yaw_radians),
        math.cos(pitch_radians) * math.sin(yaw_radians),
        math.sin(pitch_radians),
    ], dtype=np.float64)


def build_light_rotation(camera_rotation, command):
    light_rotation = to_plain_dict(camera_rotation)
    key_by_lower = {key.lower(): key for key in light_rotation.keys()}
    light_rotation[key_by_lower["yaw"]] += command.yaw_offset_degrees
    light_rotation[key_by_lower["pitch"]] += command.pitch_offset_degrees
    return light_rotation


def clamp(value, min_value, max_value):
    return min(max(value, min_value), max_value)


def get_input_key_arg(key_name):
    return {"KeyName": key_name}


def is_input_key_down(player_controller, key_name):
    return player_controller.IsInputKeyDown(Key=get_input_key_arg(key_name=key_name))


def was_input_key_pressed_since_last_poll(player_controller, key_name, previous_key_down_by_name):
    is_key_down = is_input_key_down(player_controller=player_controller, key_name=key_name)
    was_key_down = previous_key_down_by_name.get(key_name, False)
    previous_key_down_by_name[key_name] = is_key_down
    return is_key_down and not was_key_down


def get_player_controller(game):
    gameplay_statics = game.get_unreal_object(uclass="UGameplayStatics")
    return gameplay_statics.GetPlayerController(PlayerIndex=0)


def set_camera_movement_speed(game, movement_speed):
    player_controller = get_player_controller(game=game)
    pawn = player_controller.K2_GetPawn()
    movement_component = game.unreal_service.get_component_by_class(actor=pawn, uclass="USpectatorPawnMovement")
    movement_component.MaxSpeed = movement_speed
    movement_component.Acceleration = movement_speed
    movement_component.Deceleration = movement_speed
    return pawn


def attach_light_to_pawn(light, pawn):
    attached = light.K2_AttachToActor(
        ParentActor=pawn,
        SocketName="",
        LocationRule="KeepWorld",
        RotationRule="KeepWorld",
        ScaleRule="KeepWorld",
        bWeldSimulatedBodies=False)
    assert attached


def disable_scene_lights(game):
    disabled_components = 0
    actors = game.unreal_service.find_actors()

    for actor in actors:
        light_components = game.unreal_service.get_components_by_class(
            actor=actor,
            uclass="ULightComponentBase",
            include_from_child_actors=True)

        for light_component in light_components:
            light_component.SetVisibility(bNewVisibility=False, bPropagateToChildren=True)
            disabled_components += 1

    return disabled_components


def set_light_enabled(spot_light_component, command):
    spot_light_component.SetIntensity(NewIntensity=command.intensity if command.enabled else 0.0)
    spot_light_component.SetVisibility(bNewVisibility=command.enabled, bPropagateToChildren=True)


def set_light_pose(light, viewport_desc, command):
    light.K2_SetActorLocationAndRotation(
        NewLocation=viewport_desc["camera_location"],
        NewRotation=build_light_rotation(camera_rotation=viewport_desc["camera_rotation"], command=command),
        bSweep=False,
        bTeleport=True)


def get_baseline_light_command(args):
    return LightCommand(
        enabled=not args.initial_light_disabled,
        intensity=args.intensity,
        yaw_offset_degrees=args.light_yaw_offset_degrees,
        pitch_offset_degrees=args.light_pitch_offset_degrees)


def get_map_path(args, orbit_spec=None):
    if args.map_path is not None:
        return args.map_path
    if args.map is not None:
        return MAPS[args.map]
    if orbit_spec is not None:
        spec_map_path = orbit_spec.get("map_path")
        if spec_map_path:
            return spec_map_path
        spec_map = orbit_spec.get("map")
        if spec_map:
            return MAPS[spec_map]
    return None


def build_config(args, orbit_spec=None, benchmarking=False, max_num_frames=None, width=None, height=None):
    config = spear.get_config(user_config_files=[os.path.realpath(os.path.join(os.path.dirname(__file__), "user_config.yaml"))])
    config.defrost()
    config.SPEAR.INSTANCE.COMMAND_LINE_ARGS.resx = width if width is not None else args.width
    config.SPEAR.INSTANCE.COMMAND_LINE_ARGS.resy = height if height is not None else args.height
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.OVERRIDE_BENCHMARKING = True
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.BENCHMARKING = benchmarking
    if max_num_frames is not None:
        config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.BENCHMARKING_MAX_NUM_FRAMES = max_num_frames
    map_path = get_map_path(args=args, orbit_spec=orbit_spec)
    if map_path is not None:
        config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.OVERRIDE_GAME_DEFAULT_MAP = True
        config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.GAME_DEFAULT_MAP = map_path
    config.freeze()
    return config


def get_current_viewport_desc(game, only_get_pose=False):
    return game.rendering_service.get_current_viewport_desc(only_get_pose=only_get_pose)


def find_vector_in_hit_result(hit_result):
    if not isinstance(hit_result, dict):
        return None
    normalized_hit_result = {
        re.sub(r"[^a-z0-9]", "", key.lower()): value
        for key, value in hit_result.items()
    }
    for key in ("ImpactPoint", "Location", "TraceEnd"):
        hit_value = normalized_hit_result.get(re.sub(r"[^a-z0-9]", "", key.lower()))
        if isinstance(hit_value, dict):
            return hit_value
    return None


def get_visibility_trace_channel(game):
    try:
        engine_types = game.get_unreal_object(uclass="UEngineTypes")
        return engine_types.ConvertToTraceType(CollisionChannel="ECC_Visibility")
    except Exception:
        return "TraceTypeQuery1"


def try_line_trace_target(game, viewport_desc, ray_distance):
    start = vector_to_numpy(viewport_desc["camera_location"])
    end = start + forward_vector_from_rotation(viewport_desc["camera_rotation"]) * ray_distance
    kismet_system_library = game.get_unreal_object(uclass="UKismetSystemLibrary")
    trace_args = {
        "Start": numpy_to_vector(start),
        "End": numpy_to_vector(end),
        "TraceChannel": get_visibility_trace_channel(game=game),
        "bTraceComplex": True,
        "ActorsToIgnore": [],
        "DrawDebugType": "None",
        "bIgnoreSelf": True,
        "TraceColor": {"R": 1.0, "G": 0.0, "B": 0.0, "A": 1.0},
        "TraceHitColor": {"R": 0.0, "G": 1.0, "B": 0.0, "A": 1.0},
        "DrawTime": 0.0,
    }

    try:
        result = kismet_system_library.call("LineTraceSingle", args=trace_args, as_dict=True)
    except Exception as exc:
        spear.log("Visibility ray trace failed; using fallback target. Error: ", str(exc))
        return None

    did_hit = bool(result.get("ReturnValue", False)) if isinstance(result, dict) else False
    hit_result = None
    if did_hit:
        for key, value in result.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
            if normalized_key in {"outhit", "hit", "hitresult"}:
                hit_result = value
                break
    hit_point = find_vector_in_hit_result(hit_result) if did_hit else None
    if hit_point is None:
        return None
    return to_plain_dict(hit_point)


def select_or_fallback_target(game, viewport_desc, fallback_target_distance, ray_distance):
    target = try_line_trace_target(game=game, viewport_desc=viewport_desc, ray_distance=ray_distance)
    if target is not None:
        return target, False

    camera_location = vector_to_numpy(viewport_desc["camera_location"])
    target_location = camera_location + forward_vector_from_rotation(viewport_desc["camera_rotation"]) * fallback_target_distance
    target = numpy_to_vector(target_location)
    spear.log(
        "No visibility hit point was available; using fallback target ",
        fallback_target_distance,
        " cm forward from the camera: ",
        target)
    return target, True


def build_orbit_parameters(start_camera_location, target_point, orbit_radius=None):
    start = vector_to_numpy(start_camera_location)
    target = vector_to_numpy(target_point)
    offset = start - target
    requested_radius = float(np.linalg.norm(offset)) if orbit_radius is None else float(orbit_radius)
    vertical_offset = float(offset[2])
    horizontal_offset = offset[:2]
    horizontal_norm = float(np.linalg.norm(horizontal_offset))

    if horizontal_norm <= 1.0e-6:
        start_angle = 0.0
        horizontal_radius = math.sqrt(max(requested_radius*requested_radius - vertical_offset*vertical_offset, 1.0))
    else:
        start_angle = math.atan2(horizontal_offset[1], horizontal_offset[0])
        horizontal_radius = horizontal_norm

    return {
        "target": target,
        "radius": requested_radius,
        "vertical_offset": vertical_offset,
        "horizontal_radius": horizontal_radius,
        "start_angle": start_angle,
    }


def build_orbit_pose(start_camera_location, target_point, orbit_radius, alpha):
    params = build_orbit_parameters(
        start_camera_location=start_camera_location,
        target_point=target_point,
        orbit_radius=orbit_radius)
    angle = params["start_angle"] + 2.0 * math.pi * float(alpha)
    position = params["target"] + np.array([
        params["horizontal_radius"] * math.cos(angle),
        params["horizontal_radius"] * math.sin(angle),
        params["vertical_offset"],
    ], dtype=np.float64)
    rotation = rotation_from_direction(params["target"] - position)
    return numpy_to_vector(position), rotation


def build_orbit_poses(start_camera_location, target_point, orbit_radius, frame_count):
    return [
        build_orbit_pose(
            start_camera_location=start_camera_location,
            target_point=target_point,
            orbit_radius=orbit_radius,
            alpha=frame_index / max(frame_count - 1, 1))
        for frame_index in range(frame_count)
    ]


def make_viewport_desc(location, rotation, width, height, fov_degrees):
    return {
        "viewport_size_x": int(width),
        "viewport_size_y": int(height),
        "camera_location": location,
        "camera_rotation": rotation,
        "is_perspective": True,
        "fov_degrees": float(fov_degrees),
        "aspect_ratio": float(width) / float(height),
        "ortho_width": None,
        "post_process_volumes": [],
    }


def make_orbit_spec(args, map_path, start_viewport_desc, target_point, target_was_fallback, command):
    start_camera_location = to_plain_dict(start_viewport_desc["camera_location"])
    target_point = to_plain_dict(target_point)
    radius = float(np.linalg.norm(vector_to_numpy(start_camera_location) - vector_to_numpy(target_point)))
    fov_degrees = float(start_viewport_desc.get("fov_degrees", args.fov_degrees))
    return {
        "schema_version": "1.0.0",
        "map": args.map,
        "map_path": map_path,
        "start_camera_pose": {
            "camera_location": start_camera_location,
            "camera_rotation": to_plain_dict(start_viewport_desc["camera_rotation"]),
        },
        "target_point": target_point,
        "target_was_fallback": bool(target_was_fallback),
        "orbit_radius": radius,
        "orbit_duration_seconds": float(args.orbit_duration_seconds),
        "fps": float(args.fps),
        "width": int(args.width),
        "height": int(args.height),
        "image_size": {"width": int(args.width), "height": int(args.height)},
        "fov_degrees": fov_degrees,
        "light_baseline_settings": {
            "name": "baseline",
            "enabled": bool(command.enabled),
            "intensity": float(command.intensity),
            "yaw_offset_degrees": float(command.yaw_offset_degrees),
            "pitch_offset_degrees": float(command.pitch_offset_degrees),
        },
    }


def write_orbit_spec(orbit_spec_file, orbit_spec):
    os.makedirs(os.path.dirname(os.path.realpath(orbit_spec_file)), exist_ok=True)
    with open(orbit_spec_file, "w", encoding="utf-8") as f:
        json.dump(orbit_spec, f, indent=2, sort_keys=True)
        f.write("\n")


def read_json_file(json_file):
    with open(json_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_required_key(desc, key_name, context):
    if not isinstance(desc, dict):
        raise ValueError(f"{context} must be an object.")
    key_by_lower = {key.lower(): key for key in desc.keys()}
    key = key_by_lower.get(key_name.lower())
    if key is None:
        raise ValueError(f"{context} is missing required key: {key_name}")
    return desc[key]


def parse_finite_float(value, context):
    if isinstance(value, bool):
        raise ValueError(f"{context} must be numeric, not boolean.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} must be numeric.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{context} must be finite.")
    return result


def parse_positive_int(value, context):
    numeric_value = parse_finite_float(value=value, context=context)
    result = int(numeric_value)
    if float(result) != numeric_value:
        raise ValueError(f"{context} must be an integer.")
    if result <= 0:
        raise ValueError(f"{context} must be positive.")
    return result


def validate_optional_string(desc, key_name, context):
    if key_name in desc and desc[key_name] is not None and not isinstance(desc[key_name], str):
        raise ValueError(f"{context} {key_name} must be a string or null.")


def validate_vector_desc(desc, context):
    for key_name in ("X", "Y", "Z"):
        parse_finite_float(
            value=get_required_key(desc=desc, key_name=key_name, context=context),
            context=f"{context}.{key_name}")


def validate_rotator_desc(desc, context):
    for key_name in ("Pitch", "Yaw", "Roll"):
        parse_finite_float(
            value=get_required_key(desc=desc, key_name=key_name, context=context),
            context=f"{context}.{key_name}")


def validate_light_setting_name(name, context):
    if not isinstance(name, str):
        raise ValueError(f"{context} name must be a string.")
    if name in {".", ".."} or name.startswith(".") or not LIGHT_SETTING_NAME_PATTERN.fullmatch(name):
        raise ValueError(
            f"{context} has invalid name {name!r}; use a non-hidden basename containing only letters, numbers, underscore, dash, and dot.")
    if os.path.basename(name) != name:
        raise ValueError(f"{context} name must not contain path separators.")


def validate_light_setting_desc(setting, context):
    if not isinstance(setting, dict):
        raise ValueError(f"{context} must be an object.")
    for key in ("name", "enabled", "intensity", "yaw_offset_degrees", "pitch_offset_degrees"):
        if key not in setting:
            raise ValueError(f"{context} is missing required key: {key}")
    validate_light_setting_name(name=setting["name"], context=context)
    if not isinstance(setting["enabled"], bool):
        raise ValueError(f"Light setting {setting['name']} enabled must be a JSON boolean.")
    intensity = parse_finite_float(value=setting["intensity"], context=f"Light setting {setting['name']} intensity")
    if intensity < 0.0:
        raise ValueError(f"Light setting {setting['name']} intensity must be non-negative.")
    parse_finite_float(value=setting["yaw_offset_degrees"], context=f"Light setting {setting['name']} yaw_offset_degrees")
    parse_finite_float(value=setting["pitch_offset_degrees"], context=f"Light setting {setting['name']} pitch_offset_degrees")


def validate_orbit_spec(orbit_spec):
    if not isinstance(orbit_spec, dict):
        raise ValueError("Orbit spec JSON must be an object.")
    required_keys = [
        "start_camera_pose",
        "target_point",
        "orbit_radius",
        "orbit_duration_seconds",
        "fps",
        "image_size",
        "light_baseline_settings",
    ]
    for key in required_keys:
        if key not in orbit_spec:
            raise ValueError(f"Orbit spec is missing required key: {key}")

    if "schema_version" in orbit_spec and not isinstance(orbit_spec["schema_version"], str):
        raise ValueError("Orbit spec schema_version must be a string.")
    validate_optional_string(desc=orbit_spec, key_name="map", context="Orbit spec")
    validate_optional_string(desc=orbit_spec, key_name="map_path", context="Orbit spec")
    if "target_was_fallback" in orbit_spec and not isinstance(orbit_spec["target_was_fallback"], bool):
        raise ValueError("Orbit spec target_was_fallback must be a JSON boolean.")

    start_pose = orbit_spec["start_camera_pose"]
    if not isinstance(start_pose, dict):
        raise ValueError("Orbit spec start_camera_pose must be an object.")
    validate_vector_desc(
        desc=get_required_key(desc=start_pose, key_name="camera_location", context="Orbit spec start_camera_pose"),
        context="Orbit spec start_camera_pose.camera_location")
    validate_rotator_desc(
        desc=get_required_key(desc=start_pose, key_name="camera_rotation", context="Orbit spec start_camera_pose"),
        context="Orbit spec start_camera_pose.camera_rotation")
    validate_vector_desc(desc=orbit_spec["target_point"], context="Orbit spec target_point")

    if parse_finite_float(orbit_spec["orbit_radius"], "Orbit spec orbit_radius") <= 0.0:
        raise ValueError("Orbit spec orbit_radius must be positive.")
    if parse_finite_float(orbit_spec["orbit_duration_seconds"], "Orbit spec orbit_duration_seconds") <= 0.0:
        raise ValueError("Orbit spec orbit_duration_seconds must be positive.")
    if parse_finite_float(orbit_spec["fps"], "Orbit spec fps") <= 0.0:
        raise ValueError("Orbit spec fps must be positive.")
    image_size = orbit_spec["image_size"]
    if not isinstance(image_size, dict):
        raise ValueError("Orbit spec image_size must be an object.")
    parse_positive_int(
        value=get_required_key(desc=image_size, key_name="width", context="Orbit spec image_size"),
        context="Orbit spec image_size.width")
    parse_positive_int(
        value=get_required_key(desc=image_size, key_name="height", context="Orbit spec image_size"),
        context="Orbit spec image_size.height")
    if "width" in orbit_spec:
        parse_positive_int(value=orbit_spec["width"], context="Orbit spec width")
    if "height" in orbit_spec:
        parse_positive_int(value=orbit_spec["height"], context="Orbit spec height")
    if "fov_degrees" in orbit_spec and parse_finite_float(orbit_spec["fov_degrees"], "Orbit spec fov_degrees") <= 0.0:
        raise ValueError("Orbit spec fov_degrees must be positive.")
    validate_light_setting_desc(
        setting=orbit_spec["light_baseline_settings"],
        context="Orbit spec light_baseline_settings")


def validate_light_settings(light_settings):
    if not isinstance(light_settings, list):
        raise ValueError("Light settings JSON must be a list of objects.")
    if not light_settings:
        raise ValueError("Light settings JSON must contain at least one setting.")

    names = set()
    for index, setting in enumerate(light_settings):
        if not isinstance(setting, dict):
            raise ValueError(f"Light setting {index} must be an object.")
        for key in ("name", "enabled", "intensity", "yaw_offset_degrees", "pitch_offset_degrees"):
            if key not in setting:
                raise ValueError(f"Light setting {index} is missing required key: {key}")
        name = setting["name"]
        validate_light_setting_name(name=name, context=f"Light setting {index}")
        if name in names:
            raise ValueError(f"Duplicate light setting name: {name}")
        names.add(name)
        validate_light_setting_desc(setting=setting, context=f"Light setting {index}")


def command_from_setting(setting):
    return LightCommand(
        enabled=bool(setting["enabled"]),
        intensity=parse_finite_float(setting["intensity"], f"Light setting {setting['name']} intensity"),
        yaw_offset_degrees=parse_finite_float(setting["yaw_offset_degrees"], f"Light setting {setting['name']} yaw_offset_degrees"),
        pitch_offset_degrees=parse_finite_float(setting["pitch_offset_degrees"], f"Light setting {setting['name']} pitch_offset_degrees"))


def prepare_setting_output_dir(output_dir, setting_name, keep_existing_output=False):
    validate_light_setting_name(name=setting_name, context="Light setting")
    real_output_dir = os.path.realpath(output_dir)
    setting_dir = os.path.realpath(os.path.join(real_output_dir, setting_name))
    if os.path.commonpath([real_output_dir, setting_dir]) != real_output_dir:
        raise ValueError(f"Light setting output directory escapes output directory: {setting_name!r}")
    if os.path.exists(setting_dir) and not keep_existing_output:
        shutil.rmtree(setting_dir)
    frame_dirs = {
        "rgb": os.path.join(setting_dir, "frames", "rgb"),
        "depth_meters_visualization": os.path.join(setting_dir, "frames", "depth_meters_visualization"),
    }
    for frame_dir in frame_dirs.values():
        os.makedirs(frame_dir, exist_ok=True)
    return setting_dir, frame_dirs


def get_setting_video_files(setting_dir):
    return {
        "rgb": os.path.join(setting_dir, "rgb.mp4"),
        "depth_meters_visualization": os.path.join(setting_dir, "depth_meters_visualization.mp4"),
    }


def visualize_rgb(data):
    image = np.asarray(data)
    if image.ndim == 3 and image.shape[2] >= 3:
        return image[:, :, :3]
    return image


def visualize_depth(data):
    depth = data[:, :, 0] if data.ndim == 3 else data
    depth = np.asarray(depth, dtype=np.float32)
    valid = np.isfinite(depth)
    if np.any(valid):
        min_depth = float(np.min(depth[valid]))
        span = float(np.max(depth[valid]) - min_depth)
        depth_visualization = np.clip((depth - min_depth) / max(span, 1.0e-6), 0.0, 1.0)
    else:
        depth_visualization = np.zeros(depth.shape, dtype=np.float32)
    depth_u8 = (depth_visualization * 255.0).astype(np.uint8)
    return np.repeat(depth_u8[:, :, np.newaxis], 3, axis=2)


def capture_scene(camera_components):
    for component in camera_components:
        component.CaptureScene()


def write_video(frames_dir, video_file, frame_count, fps):
    cv2 = import_cv2()
    first_frame = cv2.imread(os.path.join(frames_dir, "frame_0000.png"), cv2.IMREAD_COLOR)
    if first_frame is None:
        spear.log("No frames found; skipping video encode: ", frames_dir)
        return False

    height, width = first_frame.shape[:2]
    video_writer = cv2.VideoWriter(video_file, cv2.VideoWriter_fourcc(*"mp4v"), float(fps), (width, height))
    if not video_writer.isOpened():
        spear.log("OpenCV could not open an MP4 writer; PNG frames are still available: ", video_file)
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


def was_arg_supplied(arg_name):
    return arg_name in sys.argv


def get_render_value(args, orbit_spec, arg_name, spec_key, cast):
    if was_arg_supplied(arg_name):
        return cast(getattr(args, arg_name[2:].replace("-", "_")))
    return cast(orbit_spec[spec_key])


def get_render_image_size(args, orbit_spec):
    image_size = orbit_spec["image_size"]
    width = args.width if was_arg_supplied("--width") else int(image_size["width"])
    height = args.height if was_arg_supplied("--height") else int(image_size["height"])
    return int(width), int(height)


def setup_camera_sensor(game, width, height, initial_viewport_desc):
    bp_camera_sensor_uclass = game.unreal_service.load_class(
        uclass="AActor",
        name="/SpContent/Blueprints/BP_CameraSensor.BP_CameraSensor_C")
    camera_sensor = game.unreal_service.spawn_actor(uclass=bp_camera_sensor_uclass)
    game.unreal_service.set_stable_name_for_actor(actor=camera_sensor, stable_name="Debug/OrbitCollectionCameraSensor")

    component_descs = [dict(component_desc) for component_desc in CAPTURE_COMPONENT_DESCS]
    camera_components = []
    for component_desc in component_descs:
        component = game.unreal_service.get_component_by_name(
            actor=camera_sensor,
            component_name=component_desc["long_name"],
            uclass="USpSceneCaptureComponent2D")
        component_desc["component"] = component
        camera_components.append(component)

    game.rendering_service.align_camera_with_viewport(
        camera_sensor=camera_sensor,
        camera_components=camera_components,
        viewport_desc=initial_viewport_desc,
        widths=[width for _ in camera_components],
        heights=[height for _ in camera_components])

    for component in camera_components:
        component.BufferingMode = "SingleBuffered"
        component.bCaptureEveryFrame = False
        component.bCaptureOnMovement = False
        component.Initialize()
        component.initialize_sp_funcs()

    return camera_sensor, component_descs, camera_components


def spawn_flashlight(game, location, rotation, args, command, stable_name):
    flashlight = game.unreal_service.spawn_actor(uclass="ASpotLight")
    game.unreal_service.set_stable_name_for_actor(actor=flashlight, stable_name=stable_name)
    flashlight.K2_GetRootComponent().SetMobility(NewMobility="Movable")
    flashlight.K2_SetActorLocationAndRotation(
        NewLocation=location,
        NewRotation=build_light_rotation(camera_rotation=rotation, command=command),
        bSweep=False,
        bTeleport=True)
    spot_light_component = game.unreal_service.get_component_by_class(actor=flashlight, uclass="USpotLightComponent")
    spot_light_component.SetAttenuationRadius(NewRadius=args.attenuation_radius)
    spot_light_component.SetInnerConeAngle(NewInnerConeAngle=args.inner_cone_angle)
    spot_light_component.SetOuterConeAngle(NewOuterConeAngle=args.outer_cone_angle)
    set_light_enabled(spot_light_component=spot_light_component, command=command)
    return flashlight, spot_light_component


def restore_teleop_pose(instance, pawn, player_controller, viewport_desc, light, command):
    with instance.begin_frame():
        pawn.K2_SetActorLocation(NewLocation=viewport_desc["camera_location"])
        player_controller.SetControlRotation(NewRotation=viewport_desc["camera_rotation"])
        set_light_pose(light=light, viewport_desc=viewport_desc, command=command)
    with instance.end_frame():
        pass


def run_visible_teleop_orbit(instance, pawn, player_controller, light, start_viewport_desc, target_point, orbit_radius, duration_seconds, fps, command):
    frame_count = max(int(round(duration_seconds * fps)), 1)
    period = 1.0 / float(fps)
    next_frame_time = time.monotonic()

    for frame_index, (location, rotation) in enumerate(build_orbit_poses(
            start_camera_location=start_viewport_desc["camera_location"],
            target_point=target_point,
            orbit_radius=orbit_radius,
            frame_count=frame_count)):
        now = time.monotonic()
        if now < next_frame_time:
            time.sleep(next_frame_time - now)
        viewport_desc = {
            "camera_location": location,
            "camera_rotation": rotation,
        }
        with instance.begin_frame():
            pawn.K2_SetActorLocation(NewLocation=location)
            player_controller.SetControlRotation(NewRotation=rotation)
            set_light_pose(light=light, viewport_desc=viewport_desc, command=command)
        with instance.end_frame():
            pass
        next_frame_time += period
        if frame_index % max(int(round(fps)), 1) == 0:
            spear.log("Preview orbit frame ", frame_index + 1, "/", frame_count)


def run_teleop(args):
    config = build_config(args=args, benchmarking=False)
    spear.configure_system(config=config)
    instance = spear.Instance(config=config)
    game = instance.get_game()
    light = None

    try:
        with instance.begin_frame():
            pawn = set_camera_movement_speed(game=game, movement_speed=args.movement_speed)
            player_controller = get_player_controller(game=game)
            if args.disable_scene_lights:
                disabled_components = disable_scene_lights(game=game)
                spear.log("Disabled scene light components: ", disabled_components)

            viewport_desc = get_current_viewport_desc(game=game, only_get_pose=True)
            command = get_baseline_light_command(args=args)
            light, spot_light_component = spawn_flashlight(
                game=game,
                location=viewport_desc["camera_location"],
                rotation=viewport_desc["camera_rotation"],
                args=args,
                command=command,
                stable_name="Debug/OrbitCollectionFlashlight")

        with instance.end_frame():
            pass

        with instance.begin_frame():
            viewport_desc = get_current_viewport_desc(game=game, only_get_pose=True)
            set_light_pose(light=light, viewport_desc=viewport_desc, command=command)
            attach_light_to_pawn(light=light, pawn=pawn)
        with instance.end_frame():
            pass

        spear.log("Orbit collection teleop mode is running.")
        spear.log("Select target key: ", args.select_key)
        spear.log("Preview orbit key: ", args.orbit_key)
        spear.log("Flashlight toggle key: ", args.toggle_key)
        spear.log("Orbit spec file: ", args.orbit_spec_file)

        selected_target = None
        selected_spec = None
        aim_yaw_offset_degrees = command.yaw_offset_degrees
        aim_pitch_offset_degrees = command.pitch_offset_degrees
        previous_poll_time = time.monotonic()
        previous_key_down_by_name = {}

        while instance.is_running():
            time.sleep(min(args.idle_period_seconds, INPUT_POLL_PERIOD_SECONDS))
            poll_time = time.monotonic()
            poll_delta_seconds = poll_time - previous_poll_time
            previous_poll_time = poll_time
            aim_yaw_direction = 0.0
            aim_pitch_direction = 0.0

            with instance.begin_frame():
                player_controller = get_player_controller(game=game)
                should_toggle_flashlight = was_input_key_pressed_since_last_poll(
                    player_controller=player_controller,
                    key_name=args.toggle_key,
                    previous_key_down_by_name=previous_key_down_by_name)
                should_select_target = was_input_key_pressed_since_last_poll(
                    player_controller=player_controller,
                    key_name=args.select_key,
                    previous_key_down_by_name=previous_key_down_by_name)
                should_preview_orbit = was_input_key_pressed_since_last_poll(
                    player_controller=player_controller,
                    key_name=args.orbit_key,
                    previous_key_down_by_name=previous_key_down_by_name)
                if is_input_key_down(player_controller=player_controller, key_name=args.aim_left_key):
                    aim_yaw_direction -= 1.0
                if is_input_key_down(player_controller=player_controller, key_name=args.aim_right_key):
                    aim_yaw_direction += 1.0
                if is_input_key_down(player_controller=player_controller, key_name=args.aim_up_key):
                    aim_pitch_direction += 1.0
                if is_input_key_down(player_controller=player_controller, key_name=args.aim_down_key):
                    aim_pitch_direction -= 1.0
                viewport_desc = get_current_viewport_desc(game=game, only_get_pose=True)
            with instance.end_frame():
                pass

            if aim_yaw_direction != 0.0 or aim_pitch_direction != 0.0:
                aim_yaw_offset_degrees = clamp(
                    value=aim_yaw_offset_degrees + aim_yaw_direction * args.aim_rate_degrees_per_second * poll_delta_seconds,
                    min_value=args.aim_yaw_min_degrees,
                    max_value=args.aim_yaw_max_degrees)
                aim_pitch_offset_degrees = clamp(
                    value=aim_pitch_offset_degrees + aim_pitch_direction * args.aim_rate_degrees_per_second * poll_delta_seconds,
                    min_value=args.aim_pitch_min_degrees,
                    max_value=args.aim_pitch_max_degrees)
                command.yaw_offset_degrees = aim_yaw_offset_degrees
                command.pitch_offset_degrees = aim_pitch_offset_degrees

            if should_toggle_flashlight:
                command.enabled = not command.enabled
                with instance.begin_frame():
                    set_light_enabled(spot_light_component=spot_light_component, command=command)
                with instance.end_frame():
                    pass
                spear.log("Flashlight enabled: ", command.enabled)

            with instance.begin_frame():
                viewport_desc = get_current_viewport_desc(game=game, only_get_pose=True)
                set_light_pose(light=light, viewport_desc=viewport_desc, command=command)
            with instance.end_frame():
                pass

            if should_select_target:
                with instance.begin_frame():
                    viewport_desc = get_current_viewport_desc(game=game, only_get_pose=False)
                    selected_target, target_was_fallback = select_or_fallback_target(
                        game=game,
                        viewport_desc=viewport_desc,
                        fallback_target_distance=args.fallback_target_distance,
                        ray_distance=args.target_ray_distance)
                    selected_spec = make_orbit_spec(
                        args=args,
                        map_path=get_map_path(args=args),
                        start_viewport_desc=viewport_desc,
                        target_point=selected_target,
                        target_was_fallback=target_was_fallback,
                        command=command)
                    write_orbit_spec(orbit_spec_file=args.orbit_spec_file, orbit_spec=selected_spec)
                with instance.end_frame():
                    pass
                spear.log("Selected orbit target: ", selected_target)
                spear.log("Wrote orbit spec: ", args.orbit_spec_file)

            if should_preview_orbit:
                if selected_target is None or selected_spec is None:
                    spear.log("No orbit target selected yet. Press the select target key first: ", args.select_key)
                    continue
                with instance.begin_frame():
                    player_controller = get_player_controller(game=game)
                    pawn = player_controller.K2_GetPawn()
                    original_viewport_desc = get_current_viewport_desc(game=game, only_get_pose=True)
                with instance.end_frame():
                    pass
                spear.log("Starting visible orbit preview.")
                run_visible_teleop_orbit(
                    instance=instance,
                    pawn=pawn,
                    player_controller=player_controller,
                    light=light,
                    start_viewport_desc=selected_spec["start_camera_pose"],
                    target_point=selected_target,
                    orbit_radius=selected_spec["orbit_radius"],
                    duration_seconds=args.orbit_duration_seconds,
                    fps=args.fps,
                    command=command)
                restore_teleop_pose(
                    instance=instance,
                    pawn=pawn,
                    player_controller=player_controller,
                    viewport_desc=original_viewport_desc,
                    light=light,
                    command=command)
                spear.log("Completed orbit preview and restored the original teleop pose.")

    except KeyboardInterrupt:
        spear.log("Stopping orbit collection teleop mode.")

    finally:
        if light is not None and instance.is_running():
            with instance.begin_frame():
                pass
            with instance.end_frame():
                game.unreal_service.destroy_actor(actor=light)

        instance.close()
        spear.log("Done.")


def settle_render_state(instance, num_frames):
    for _ in range(num_frames):
        with instance.begin_frame():
            pass
        with instance.end_frame(single_step=True):
            pass


def run_render(args):
    cv2 = import_cv2()
    orbit_spec = read_json_file(args.orbit_spec_file)
    validate_orbit_spec(orbit_spec=orbit_spec)
    light_settings = read_json_file(args.light_settings_file)
    validate_light_settings(light_settings=light_settings)

    width, height = get_render_image_size(args=args, orbit_spec=orbit_spec)
    fps = get_render_value(args=args, orbit_spec=orbit_spec, arg_name="--fps", spec_key="fps", cast=float)
    duration_seconds = get_render_value(
        args=args,
        orbit_spec=orbit_spec,
        arg_name="--orbit-duration-seconds",
        spec_key="orbit_duration_seconds",
        cast=float)
    frame_count = max(int(round(duration_seconds * fps)), 1)
    fov_degrees = float(orbit_spec.get("fov_degrees", args.fov_degrees))
    if was_arg_supplied("--fov-degrees"):
        fov_degrees = args.fov_degrees

    max_num_frames = len(light_settings) * (frame_count + args.settle_frames + 2) + 8
    config = build_config(
        args=args,
        orbit_spec=orbit_spec,
        benchmarking=True,
        max_num_frames=max_num_frames,
        width=width,
        height=height)
    spear.configure_system(config=config)
    instance = spear.Instance(config=config)
    game = instance.get_game()
    camera_sensor = None
    camera_components = []
    flashlight = None

    try:
        start_pose = orbit_spec["start_camera_pose"]
        first_location, first_rotation = build_orbit_pose(
            start_camera_location=start_pose["camera_location"],
            target_point=orbit_spec["target_point"],
            orbit_radius=orbit_spec["orbit_radius"],
            alpha=0.0)
        initial_viewport_desc = make_viewport_desc(
            location=first_location,
            rotation=first_rotation,
            width=width,
            height=height,
            fov_degrees=fov_degrees)
        baseline_command = command_from_setting(orbit_spec["light_baseline_settings"])

        with instance.begin_frame():
            if args.disable_scene_lights:
                disabled_components = disable_scene_lights(game=game)
                spear.log("Disabled scene light components: ", disabled_components)
            camera_sensor, component_descs, camera_components = setup_camera_sensor(
                game=game,
                width=width,
                height=height,
                initial_viewport_desc=initial_viewport_desc)
            flashlight, spot_light_component = spawn_flashlight(
                game=game,
                location=first_location,
                rotation=first_rotation,
                args=args,
                command=baseline_command,
                stable_name="Debug/OrbitCollectionRenderFlashlight")
        with instance.end_frame(single_step=True):
            pass

        settle_render_state(instance=instance, num_frames=args.settle_frames)

        poses = build_orbit_poses(
            start_camera_location=start_pose["camera_location"],
            target_point=orbit_spec["target_point"],
            orbit_radius=orbit_spec["orbit_radius"],
            frame_count=frame_count)

        for setting in light_settings:
            command = command_from_setting(setting=setting)
            setting_dir, frame_dirs = prepare_setting_output_dir(
                output_dir=args.output_dir,
                setting_name=setting["name"],
                keep_existing_output=args.keep_existing_output)
            video_files = get_setting_video_files(setting_dir=setting_dir)
            spear.log("Rendering light setting: ", setting["name"])

            with instance.begin_frame():
                set_light_enabled(spot_light_component=spot_light_component, command=command)
            with instance.end_frame(single_step=True):
                pass
            settle_render_state(instance=instance, num_frames=args.settle_frames)

            for frame_index, (location, rotation) in enumerate(poses):
                viewport_desc = make_viewport_desc(
                    location=location,
                    rotation=rotation,
                    width=width,
                    height=height,
                    fov_degrees=fov_degrees)
                component_data = {}
                with instance.begin_frame():
                    game.rendering_service.align_camera_with_viewport(
                        camera_sensor=camera_sensor,
                        camera_components=camera_components,
                        viewport_desc=viewport_desc,
                        widths=[width for _ in camera_components],
                        heights=[height for _ in camera_components])
                    flashlight.K2_SetActorLocationAndRotation(
                        NewLocation=location,
                        NewRotation=build_light_rotation(camera_rotation=rotation, command=command),
                        bSweep=False,
                        bTeleport=True)
                    set_light_enabled(spot_light_component=spot_light_component, command=command)
                    capture_scene(camera_components=camera_components)
                with instance.end_frame(single_step=True):
                    for component_desc in component_descs:
                        data_bundle = component_desc["component"].read_pixels()
                        component_data[component_desc["name"]] = data_bundle["arrays"]["data"].copy()

                rgb_frame = visualize_rgb(data=component_data["rgb"])
                depth_frame = visualize_depth(data=component_data["depth_meters"])
                cv2.imwrite(os.path.join(frame_dirs["rgb"], f"frame_{frame_index:04d}.png"), rgb_frame)
                cv2.imwrite(os.path.join(frame_dirs["depth_meters_visualization"], f"frame_{frame_index:04d}.png"), depth_frame)

                if frame_index % max(int(round(fps)), 1) == 0:
                    spear.log("Rendered frame ", frame_index + 1, "/", frame_count, " for ", setting["name"])

            if write_video(
                    frames_dir=frame_dirs["rgb"],
                    video_file=video_files["rgb"],
                    frame_count=frame_count,
                    fps=fps):
                spear.log("Wrote RGB video: ", video_files["rgb"])
            if write_video(
                    frames_dir=frame_dirs["depth_meters_visualization"],
                    video_file=video_files["depth_meters_visualization"],
                    frame_count=frame_count,
                    fps=fps):
                spear.log("Wrote depth visualization video: ", video_files["depth_meters_visualization"])
            spear.log("Wrote frames: ", os.path.join(setting_dir, "frames"))

    finally:
        if instance.is_running():
            with instance.begin_frame():
                pass
            with instance.end_frame(single_step=True):
                for component in camera_components:
                    component.terminate_sp_funcs()
                    component.Terminate()
                if camera_sensor is not None:
                    game.unreal_service.destroy_actor(actor=camera_sensor)
                if flashlight is not None:
                    game.unreal_service.destroy_actor(actor=flashlight)
            instance.step()

        instance.close()
        spear.log("Done.")


def main(argv=None):
    args = parse_args(argv=argv)
    if args.mode == "teleop":
        return run_teleop(args=args)
    if args.mode == "render":
        return run_render(args=args)
    raise AssertionError(f"Unhandled mode: {args.mode}")


if __name__ == "__main__":
    sys.exit(main())
