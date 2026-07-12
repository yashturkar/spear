#
# Copyright (c) 2025 The SPEAR Development Team. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
# Copyright (c) 2022 Intel. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
#

import argparse
import json
import math
import os
import select
import sys
import time

import spear
import yacs.config

FLASHLIGHT_DIR = os.path.dirname(__file__)
if FLASHLIGHT_DIR not in sys.path:
    sys.path.insert(0, FLASHLIGHT_DIR)

import flashlight_profiles


INPUT_POLL_PERIOD_SECONDS = 1.0 / 60.0
LEGACY_SP_CORE_INI_CONFIG_VALUE_KEYS = (
    "EDITOR_INI_CONFIG_VALUES",
    "ENGINE_INI_CONFIG_VALUES",
    "GAME_INI_CONFIG_VALUES",
    "GAME_USER_SETTINGS_INI_CONFIG_VALUES",
    "INPUT_INI_CONFIG_VALUES",
)
AUTO_EXPOSURE_DISABLED_ENGINE_INI = """[/Script/Engine.RendererSettings]
r.DefaultFeature.AutoExposure=False
r.EyeAdaptationQuality=0
r.DefaultFeature.LocalExposure.HighlightContrastScale=0
r.DefaultFeature.LocalExposure.ShadowContrastScale=0
"""
LOCAL_EXPOSURE_DISABLED_ENGINE_INI = """[/Script/Engine.RendererSettings]
r.DefaultFeature.LocalExposure.HighlightContrastScale=0
r.DefaultFeature.LocalExposure.ShadowContrastScale=0
"""
REALISTIC_LIVE_RENDERER_ENGINE_INI = """[/Script/Engine.RendererSettings]
r.DynamicGlobalIlluminationMethod=1
r.ReflectionMethod=1
r.Lumen.DiffuseIndirect.Allow=1
r.Lumen.Reflections.Allow=1
"""
HARDWARE_RAY_TRACING_CVARS = (
    ("r.RayTracing.Enable", 1),
    ("r.Lumen.HardwareRayTracing", 1),
    ("r.Lumen.Reflections.HardwareRayTracing", 1),
    ("r.Lumen.ScreenProbeGather.HardwareRayTracing", 1),
    ("r.Lumen.ScreenProbeGather.ShortRangeAO.HardwareRayTracing", 1),
)
DEFAULT_INNER_CONE_ANGLE = 2.0
DEFAULT_OUTER_CONE_ANGLE = 60.0
DEFAULT_SOURCE_RADIUS = 12.0
DEFAULT_SOFT_SOURCE_RADIUS = 80.0
DEFAULT_REALISTIC_LIVE_WARMUP_SECONDS = 3.0
DEFAULT_INTENSITY_TRIGGER_DEADZONE = 0.05
DEFAULT_INTENSITY_MAX_SCALE = 10.0
DEFAULT_INTENSITY_MAX_RATE_SECONDS = 5.0
DEFAULT_INTENSITY_MIN_RATE = 1000.0

MAPS = {
    "apartment_0000": "/Game/SPEAR/Scenes/apartment_0000/Maps/apartment_0000",
    "debug_0000": "/Game/SPEAR/Scenes/debug_0000/Maps/debug_0000",
    "debug_0001": "/Game/SPEAR/Scenes/debug_0001/Maps/debug_0001",
    "advanced_lighting": "/Game/StarterContent/Maps/Advanced_Lighting",
    "cafeteria_500sqft_v2": "/Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2",
    "japanese_office": "/Game/JapaneseOffice/Maps/Demonstration",
    "japanese_office_dark": "/Game/JapaneseOffice/Maps/Demonstration_Dark",
    "minimal_default": "/Game/StarterContent/Maps/Minimal_Default",
    "starter_map": "/Game/StarterContent/Maps/StarterMap",
    "third_person": "/Game/ThirdPerson/Maps/ThirdPersonMap",
    "vehicle": "/Game/VehicleTemplate/Maps/VehicleExampleMap",
    "vehicle_offroad": "/Game/VehicleTemplate/Maps/VehicleOffroadExampleMap",
}

parser = argparse.ArgumentParser()
parser.add_argument("--map", choices=sorted(MAPS.keys()), default=None)
parser.add_argument("--map-path", default=None)
parser.add_argument("--intensity", type=float, default=None)
parser.add_argument("--attenuation-radius", type=float, default=None)
parser.add_argument("--indirect-lighting-intensity", type=float, default=None)
parser.add_argument("--inner-cone-angle", type=float, default=None)
parser.add_argument("--outer-cone-angle", type=float, default=None)
parser.add_argument("--source-radius", type=float, default=None)
parser.add_argument("--soft-source-radius", type=float, default=None)
flashlight_profiles.add_flashlight_profile_args(parser)
parser.add_argument("--movement-speed", type=float, default=1200.0)
parser.add_argument("--disable-scene-lights", action="store_true")
parser.add_argument("--scene-light-intensity-scale", type=float, default=1.0)
parser.add_argument("--live-lighting-mode", choices=["default", "realistic"], default="default")
parser.add_argument("--disable-hardware-ray-tracing", action="store_true")
parser.add_argument("--startup-warmup-seconds", type=float, default=None)
auto_exposure_group = parser.add_mutually_exclusive_group()
auto_exposure_group.add_argument("--disable-auto-exposure", dest="disable_auto_exposure", action="store_true", default=True)
auto_exposure_group.add_argument("--enable-auto-exposure", dest="disable_auto_exposure", action="store_false")
parser.add_argument("--capture-poses", action="store_true")
parser.add_argument("--capture-key", default="Gamepad_FaceButton_Top")
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
parser.add_argument("--intensity-down-key", default="Gamepad_LeftTriggerAxis")
parser.add_argument("--intensity-up-key", default="Gamepad_RightTriggerAxis")
parser.add_argument("--intensity-adjust-rate", type=float, default=None)
parser.add_argument("--intensity-min", type=float, default=0.0)
parser.add_argument("--intensity-max", type=float, default=None)
parser.add_argument("--intensity-trigger-deadzone", type=float, default=DEFAULT_INTENSITY_TRIGGER_DEADZONE)
parser.add_argument("--intensity-log-period-seconds", type=float, default=0.25)
parser.add_argument("--pose-output-file", default=os.path.realpath(os.path.join(os.path.dirname(__file__), "camera_poses.jsonl")))
parser.add_argument("--idle-period-seconds", type=float, default=0.5)


def parse_args(argv=None):
    raw_argv = sys.argv[1:] if argv is None else list(argv)
    args = parser.parse_args(argv)
    try:
        flashlight_profiles.apply_profile_to_args(args=args, argv=raw_argv)
    except ValueError as exc:
        parser.error(str(exc))

    if args.aim_yaw_min_degrees > args.aim_yaw_max_degrees:
        parser.error("--aim-yaw-min-degrees must be less than or equal to --aim-yaw-max-degrees")
    if args.aim_pitch_min_degrees > args.aim_pitch_max_degrees:
        parser.error("--aim-pitch-min-degrees must be less than or equal to --aim-pitch-max-degrees")
    if args.aim_rate_degrees_per_second < 0.0:
        parser.error("--aim-rate-degrees-per-second must be non-negative")
    if not math.isfinite(args.intensity) or args.intensity < 0.0:
        parser.error("--intensity must be a finite non-negative value")
    if args.intensity_adjust_rate is None:
        args.intensity_adjust_rate = max(args.intensity, DEFAULT_INTENSITY_MIN_RATE)
    if not math.isfinite(args.intensity_adjust_rate) or args.intensity_adjust_rate < 0.0:
        parser.error("--intensity-adjust-rate must be a finite non-negative value")
    if not math.isfinite(args.intensity_min) or args.intensity_min < 0.0:
        parser.error("--intensity-min must be a finite non-negative value")
    if args.intensity_max is None:
        args.intensity_max = max(
            args.intensity * DEFAULT_INTENSITY_MAX_SCALE,
            args.intensity + args.intensity_adjust_rate * DEFAULT_INTENSITY_MAX_RATE_SECONDS,
            args.intensity_min)
    if not math.isfinite(args.intensity_max) or args.intensity_max < 0.0:
        parser.error("--intensity-max must be a finite non-negative value")
    if args.intensity_min > args.intensity_max:
        parser.error("--intensity-min must be less than or equal to --intensity-max")
    if args.intensity < args.intensity_min or args.intensity > args.intensity_max:
        parser.error("--intensity must be between --intensity-min and --intensity-max")
    if not math.isfinite(args.intensity_trigger_deadzone) or not 0.0 <= args.intensity_trigger_deadzone < 1.0:
        parser.error("--intensity-trigger-deadzone must be finite and in [0, 1)")
    if not math.isfinite(args.intensity_log_period_seconds) or args.intensity_log_period_seconds < 0.0:
        parser.error("--intensity-log-period-seconds must be a finite non-negative value")
    if not math.isfinite(args.attenuation_radius) or args.attenuation_radius <= 0.0:
        parser.error("--attenuation-radius must be a finite positive value")
    if not math.isfinite(args.indirect_lighting_intensity) or args.indirect_lighting_intensity < 0.0:
        parser.error("--indirect-lighting-intensity must be a finite non-negative value")
    if not math.isfinite(args.inner_cone_angle) or args.inner_cone_angle < 0.0:
        parser.error("--inner-cone-angle must be a finite non-negative value")
    if not math.isfinite(args.outer_cone_angle) or args.outer_cone_angle < args.inner_cone_angle:
        parser.error("--outer-cone-angle must be finite and greater than or equal to --inner-cone-angle")
    if not math.isfinite(args.source_radius) or args.source_radius < 0.0:
        parser.error("--source-radius must be a finite non-negative value")
    if not math.isfinite(args.soft_source_radius) or args.soft_source_radius < 0.0:
        parser.error("--soft-source-radius must be a finite non-negative value")
    if not math.isfinite(args.contact_shadow_length) or args.contact_shadow_length < 0.0:
        parser.error("--contact-shadow-length must be a finite non-negative value")
    if not math.isfinite(args.scene_light_intensity_scale) or args.scene_light_intensity_scale < 0.0:
        parser.error("--scene-light-intensity-scale must be a finite non-negative value")
    if args.startup_warmup_seconds is None:
        args.startup_warmup_seconds = DEFAULT_REALISTIC_LIVE_WARMUP_SECONDS if args.live_lighting_mode == "realistic" else 0.0
    if not math.isfinite(args.startup_warmup_seconds) or args.startup_warmup_seconds < 0.0:
        parser.error("--startup-warmup-seconds must be a finite non-negative value")

    return args


def get_viewport_pose(game):
    return game.rendering_service.get_current_viewport_desc(only_get_pose=True)


def set_light_pose(light, viewport_desc):
    return light.K2_SetActorLocationAndRotation(
        NewLocation=viewport_desc["camera_location"],
        NewRotation=viewport_desc["camera_rotation"],
        bSweep=False,
        bTeleport=True)


def get_aimed_light_rotation(camera_rotation, yaw_offset_degrees, pitch_offset_degrees):
    light_rotation = to_plain_dict(camera_rotation)
    rotator_key_by_lower_name = {key.lower(): key for key in light_rotation.keys()}
    yaw_key = rotator_key_by_lower_name["yaw"]
    pitch_key = rotator_key_by_lower_name["pitch"]
    light_rotation[yaw_key] += yaw_offset_degrees
    light_rotation[pitch_key] += pitch_offset_degrees
    return light_rotation


def set_light_aim(light, viewport_desc, yaw_offset_degrees, pitch_offset_degrees):
    return light.K2_SetActorRotation(
        NewRotation=get_aimed_light_rotation(
            camera_rotation=viewport_desc["camera_rotation"],
            yaw_offset_degrees=yaw_offset_degrees,
            pitch_offset_degrees=pitch_offset_degrees))


def to_plain_dict(value):
    return json.loads(json.dumps(value))


def save_viewport_pose(name, viewport_desc, output_file):
    pose_desc = {
        "name": name,
        "time": time.time(),
        "camera_location": to_plain_dict(viewport_desc["camera_location"]),
        "camera_rotation": to_plain_dict(viewport_desc["camera_rotation"]),
    }

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(pose_desc, sort_keys=True) + "\n")

    return pose_desc


def get_input_key_arg(key_name):
    return {"KeyName": key_name}


def is_input_key_down(player_controller, key_name):
    return player_controller.IsInputKeyDown(Key=get_input_key_arg(key_name=key_name))


def get_input_axis_value(player_controller, key_name):
    get_input_analog_key_state = getattr(player_controller, "GetInputAnalogKeyState", None)
    if get_input_analog_key_state is None:
        return 0.0

    key_arg = get_input_key_arg(key_name=key_name)
    for call_args, call_kwargs in (
            ((), {"Key": key_arg}),
            ((key_arg,), {})):
        try:
            value = get_input_analog_key_state(*call_args, **call_kwargs)
        except TypeError:
            continue
        except Exception:
            return 0.0
        if hasattr(value, "get"):
            value = value.get()
        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(value):
            return 0.0
        return value
    return 0.0


def clamp(value, min_value, max_value):
    return min(max(value, min_value), max_value)


def normalize_trigger_axis(value, deadzone):
    value = clamp(value=value, min_value=0.0, max_value=1.0)
    if value <= deadzone:
        return 0.0
    return (value - deadzone) / (1.0 - deadzone)


def compute_live_flashlight_intensity(
        current_intensity,
        decrease_axis,
        increase_axis,
        delta_seconds,
        intensity_adjust_rate,
        intensity_min,
        intensity_max,
        trigger_deadzone):
    decrease = normalize_trigger_axis(value=decrease_axis, deadzone=trigger_deadzone)
    increase = normalize_trigger_axis(value=increase_axis, deadzone=trigger_deadzone)
    delta = (increase - decrease) * intensity_adjust_rate * max(delta_seconds, 0.0)
    intensity = clamp(
        value=current_intensity + delta,
        min_value=intensity_min,
        max_value=intensity_max)
    return {
        "previous_intensity": current_intensity,
        "intensity": intensity,
        "decrease": decrease,
        "increase": increase,
        "delta": intensity - current_intensity,
        "changed": not math.isclose(intensity, current_intensity, rel_tol=0.0, abs_tol=1.0e-9),
        "at_min": intensity <= intensity_min,
        "at_max": intensity >= intensity_max,
    }


def update_live_flashlight_intensity_from_triggers(
        player_controller,
        spot_light_component,
        current_intensity,
        delta_seconds,
        args):
    decrease_axis = get_input_axis_value(
        player_controller=player_controller,
        key_name=args.intensity_down_key)
    increase_axis = get_input_axis_value(
        player_controller=player_controller,
        key_name=args.intensity_up_key)
    state = compute_live_flashlight_intensity(
        current_intensity=current_intensity,
        decrease_axis=decrease_axis,
        increase_axis=increase_axis,
        delta_seconds=delta_seconds,
        intensity_adjust_rate=args.intensity_adjust_rate,
        intensity_min=args.intensity_min,
        intensity_max=args.intensity_max,
        trigger_deadzone=args.intensity_trigger_deadzone)
    state["decrease_axis"] = decrease_axis
    state["increase_axis"] = increase_axis
    if state["changed"]:
        spot_light_component.SetIntensity(NewIntensity=state["intensity"])
    return state


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


def try_call_method(obj, method_name, **kwargs):
    method = getattr(obj, method_name, None)
    if method is None:
        call = getattr(obj, "call", None)
        if call is None:
            return False
        try:
            call(method_name, args=kwargs)
        except Exception:
            return False
        return True
    try:
        method(**kwargs)
    except TypeError:
        try:
            method(*kwargs.values())
        except Exception:
            return False
    except Exception:
        return False
    return True


def try_set_float_property(obj, property_names, value):
    for property_name in property_names:
        set_editor_property = getattr(obj, "set_editor_property", None)
        if set_editor_property is not None:
            try:
                set_editor_property(property_name, value)
                get_editor_property = getattr(obj, "get_editor_property", None)
                if get_editor_property is None or get_editor_property(property_name) == value:
                    return True
            except Exception:
                pass

        if hasattr(obj, property_name):
            try:
                setattr(obj, property_name, value)
                if getattr(obj, property_name) == value:
                    return True
            except Exception:
                pass

    return False


def try_call_source_radius_method(spot_light_component, method_name, value):
    return try_call_method(spot_light_component, method_name, bNewValue=value)


def apply_spot_light_shape_controls(spot_light_component, args):
    state = {
        "source_radius_set": False,
        "soft_source_radius_set": False,
    }
    state["source_radius_set"] = (
        try_call_source_radius_method(spot_light_component, "SetSourceRadius", args.source_radius)
        or try_set_float_property(
            obj=spot_light_component,
            property_names=("SourceRadius", "source_radius"),
            value=args.source_radius))
    state["soft_source_radius_set"] = (
        try_call_source_radius_method(spot_light_component, "SetSoftSourceRadius", args.soft_source_radius)
        or try_set_float_property(
            obj=spot_light_component,
            property_names=("SoftSourceRadius", "soft_source_radius"),
            value=args.soft_source_radius))
    return state


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


def try_scale_light_component_intensity(light_component, intensity_scale):
    try:
        intensity = light_component.Intensity
        if hasattr(intensity, "get"):
            intensity = intensity.get()
        intensity = float(intensity)
    except Exception:
        return False

    if not math.isfinite(intensity):
        return False

    try:
        light_component.SetIntensity(NewIntensity=intensity * intensity_scale)
    except Exception:
        return False

    return True


def scale_scene_light_intensities(game, intensity_scale):
    scaled_components = 0
    skipped_components = 0
    actors = game.unreal_service.find_actors()

    for actor in actors:
        light_components = game.unreal_service.get_components_by_class(
            actor=actor,
            uclass="ULightComponentBase",
            include_from_child_actors=True)

        for light_component in light_components:
            if try_scale_light_component_intensity(
                    light_component=light_component,
                    intensity_scale=intensity_scale):
                scaled_components += 1
            else:
                skipped_components += 1

    return scaled_components, skipped_components


def ensure_legacy_sp_core_ini_config_values(config):
    was_new_allowed = config.SP_CORE.is_new_allowed()
    config.SP_CORE.set_new_allowed(True)
    for key in LEGACY_SP_CORE_INI_CONFIG_VALUE_KEYS:
        if key not in config.SP_CORE:
            config.SP_CORE[key] = yacs.config.CfgNode(new_allowed=True)
    config.SP_CORE.set_new_allowed(was_new_allowed)


def append_engine_ini_config(config, engine_ini_config):
    config.SP_CORE.OVERRIDE_CONFIG_ENGINE_INI = True
    existing_engine_ini_config = config.SP_CORE.CONFIG_ENGINE_INI_STRING or ""
    if existing_engine_ini_config and not existing_engine_ini_config.endswith("\n"):
        existing_engine_ini_config += "\n"
    config.SP_CORE.CONFIG_ENGINE_INI_STRING = existing_engine_ini_config + engine_ini_config


def is_realistic_live_mode(args):
    return args.live_lighting_mode == "realistic"


def should_request_hardware_ray_tracing(args):
    return bool(is_realistic_live_mode(args=args) and not args.disable_hardware_ray_tracing)


def should_suppress_local_exposure(args):
    return bool(args.disable_auto_exposure or is_realistic_live_mode(args=args))


def apply_auto_exposure_config(config, args):
    if args.disable_auto_exposure:
        append_engine_ini_config(
            config=config,
            engine_ini_config=AUTO_EXPOSURE_DISABLED_ENGINE_INI)
    elif should_suppress_local_exposure(args=args):
        append_engine_ini_config(
            config=config,
            engine_ini_config=LOCAL_EXPOSURE_DISABLED_ENGINE_INI)


def apply_realistic_live_renderer_config(config, args):
    if is_realistic_live_mode(args=args):
        append_engine_ini_config(
            config=config,
            engine_ini_config=REALISTIC_LIVE_RENDERER_ENGINE_INI)
    if should_request_hardware_ray_tracing(args=args):
        append_engine_ini_config(
            config=config,
            engine_ini_config=get_hardware_ray_tracing_engine_ini())


def get_hardware_ray_tracing_engine_ini():
    lines = ["[/Script/Engine.RendererSettings]"]
    lines.extend(
        f"{cvar_name}={value}"
        for cvar_name, value in HARDWARE_RAY_TRACING_CVARS)
    return "\n".join(lines) + "\n"


def get_hardware_ray_tracing_requested_state(args):
    requested = should_request_hardware_ray_tracing(args=args)
    return {
        "requested": requested,
        "disabled_by_cli": bool(args.disable_hardware_ray_tracing),
        "requires_realistic_live_mode": True,
        "cvars": [
            {
                "name": cvar_name,
                "value": value,
                "requested": requested,
            }
            for cvar_name, value in HARDWARE_RAY_TRACING_CVARS
        ],
    }


def build_config(args, user_config_files=None):
    if user_config_files is None:
        user_config_files = [os.path.realpath(os.path.join(os.path.dirname(__file__), "user_config.yaml"))]
    config = spear.get_config(user_config_files=user_config_files)
    config.defrost()
    ensure_legacy_sp_core_ini_config_values(config=config)
    apply_auto_exposure_config(config=config, args=args)
    apply_realistic_live_renderer_config(config=config, args=args)
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.OVERRIDE_BENCHMARKING = True
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.BENCHMARKING = False
    if args.map is not None or args.map_path is not None:
        config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.OVERRIDE_GAME_DEFAULT_MAP = True
        config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.GAME_DEFAULT_MAP = args.map_path if args.map_path is not None else MAPS[args.map]
    config.freeze()
    return config


def try_execute_console_command(game, player_controller, command):
    if try_call_method(
            player_controller,
            "ConsoleCommand",
            Command=command,
            bWriteToLog=True):
        return True
    if try_call_method(
            player_controller,
            "ConsoleCommand",
            Cmd=command,
            bWriteToLog=True):
        return True

    try:
        kismet_system_library = game.get_unreal_object(uclass="UKismetSystemLibrary")
    except Exception:
        return False

    for player_arg_name in ("SpecificPlayer", "Player"):
        if try_call_method(
                kismet_system_library,
                "ExecuteConsoleCommand",
                Command=command,
                **{player_arg_name: player_controller}):
            return True
    if try_call_method(
            kismet_system_library,
            "ExecuteConsoleCommand",
            Command=command):
        return True
    return False


def try_read_console_variable_int(game, cvar_name):
    state = {
        "name": cvar_name,
        "available": False,
        "readback_ok": False,
        "value": None,
        "error": None,
    }
    unreal_service = getattr(game, "unreal_service", None)
    find_console_variable_by_name = getattr(unreal_service, "find_console_variable_by_name", None)
    if find_console_variable_by_name is None:
        state["error"] = "unreal_service.find_console_variable_by_name unavailable"
        return state

    try:
        cvar = find_console_variable_by_name(console_variable_name=cvar_name)
    except Exception as exc:
        state["error"] = f"find failed: {exc}"
        return state

    if not cvar:
        state["error"] = "console variable not found"
        return state

    state["available"] = True
    for getter_name in (
            "get_console_variable_value_as_int",
            "get_console_variable_value_as_bool",
            "get_console_variable_value_as_float",
            "get_console_variable_value_as_string"):
        getter = getattr(unreal_service, getter_name, None)
        if getter is None:
            continue
        try:
            value = getter(cvar=cvar)
        except Exception:
            continue
        try:
            state["value"] = int(value)
        except (TypeError, ValueError):
            state["value"] = value
        state["readback_ok"] = True
        state["getter"] = getter_name
        return state

    state["error"] = "no console variable value getter succeeded"
    return state


def make_hardware_ray_tracing_console_commands():
    return [
        f"{cvar_name} {value}"
        for cvar_name, value in HARDWARE_RAY_TRACING_CVARS
    ]


def read_hardware_ray_tracing_runtime_state(game):
    cvar_states = []
    confirmed = True
    has_readback = False
    for cvar_name, requested_value in HARDWARE_RAY_TRACING_CVARS:
        readback = try_read_console_variable_int(game=game, cvar_name=cvar_name)
        matches_request = readback["readback_ok"] and readback["value"] == requested_value
        if readback["readback_ok"]:
            has_readback = True
        else:
            confirmed = False
        if readback["readback_ok"] and not matches_request:
            confirmed = False
        cvar_states.append({
            "name": cvar_name,
            "requested_value": requested_value,
            "readback": readback,
            "matches_request": matches_request,
        })

    return {
        "confirmed": confirmed if has_readback else None,
        "has_readback": has_readback,
        "cvars": cvar_states,
    }


def is_hardware_ray_tracing_runtime_confirmed(runtime_render_config_state):
    hardware_ray_tracing_state = runtime_render_config_state.get("hardware_ray_tracing", {})
    readback = hardware_ray_tracing_state.get("readback")
    return bool(
        hardware_ray_tracing_state.get("requested") is True
        and isinstance(readback, dict)
        and readback.get("confirmed") is True)


def apply_live_spot_light_ray_traced_shadow_intent(
        spot_light_component,
        args,
        runtime_render_config_state,
        intent_fn=None):
    if intent_fn is None:
        intent_fn = flashlight_profiles.apply_spot_light_ray_traced_shadow_intent

    requested_by_config = should_request_hardware_ray_tracing(args=args)
    runtime_confirmed = is_hardware_ray_tracing_runtime_confirmed(
        runtime_render_config_state=runtime_render_config_state)
    state = {
        "requested_by_config": requested_by_config,
        "cast_shadows": bool(args.cast_shadows),
        "runtime_confirmed": runtime_confirmed,
        "skipped_reason": None,
        "intent": None,
        "applied": False,
    }
    if not requested_by_config:
        state["skipped_reason"] = "hardware ray tracing not requested"
        return state
    if not args.cast_shadows:
        state["skipped_reason"] = "flashlight shadows disabled"
        return state
    if not runtime_confirmed:
        state["skipped_reason"] = "hardware ray tracing runtime readback not confirmed"
        return state

    intent_state = intent_fn(
        spot_light_component=spot_light_component,
        requested=True)
    state["intent"] = intent_state
    state["applied"] = bool(intent_state.get("applied"))
    if not state["applied"]:
        state["skipped_reason"] = "ray-traced shadow API unavailable"
    return state


def apply_live_runtime_render_config(game, player_controller, args):
    state = {
        "disable_auto_exposure": bool(args.disable_auto_exposure),
        "suppress_local_exposure": should_suppress_local_exposure(args=args),
        "realistic_live_mode": is_realistic_live_mode(args=args),
        "hardware_ray_tracing": {
            "requested": should_request_hardware_ray_tracing(args=args),
            "disabled_by_cli": bool(args.disable_hardware_ray_tracing),
            "commands": [],
            "readback": None,
        },
        "commands": [],
        "applied": 0,
    }
    commands = []
    if args.disable_auto_exposure:
        commands.extend((
            "r.DefaultFeature.AutoExposure 0",
            "r.EyeAdaptationQuality 0",
        ))
    if should_suppress_local_exposure(args=args):
        commands.extend((
            "r.DefaultFeature.LocalExposure.HighlightContrastScale 0",
            "r.DefaultFeature.LocalExposure.ShadowContrastScale 0",
            "ShowFlag.LocalExposure 0",
        ))
    if is_realistic_live_mode(args=args):
        commands.extend((
            "r.DynamicGlobalIlluminationMethod 1",
            "r.ReflectionMethod 1",
            "r.Lumen.DiffuseIndirect.Allow 1",
            "r.Lumen.Reflections.Allow 1",
            "ShowFlag.GlobalIllumination 1",
            "ShowFlag.LumenGlobalIllumination 1",
            "ShowFlag.LumenReflections 1",
            "ShowFlag.Materials 1",
            "ShowFlag.ReflectionEnvironment 1",
            "ShowFlag.ScreenSpaceReflections 1",
            "ShowFlag.Specular 1",
        ))
        if should_request_hardware_ray_tracing(args=args):
            commands.extend(make_hardware_ray_tracing_console_commands())

    for command in commands:
        applied = try_execute_console_command(
            game=game,
            player_controller=player_controller,
            command=command)
        state["commands"].append({
            "command": command,
            "applied": applied,
        })
        if applied:
            state["applied"] += 1

    hardware_commands = set(make_hardware_ray_tracing_console_commands())
    state["hardware_ray_tracing"]["commands"] = [
        command_state
        for command_state in state["commands"]
        if command_state["command"] in hardware_commands
    ]
    if should_request_hardware_ray_tracing(args=args):
        state["hardware_ray_tracing"]["readback"] = read_hardware_ray_tracing_runtime_state(game=game)
    return state


def is_instance_running(instance):
    is_running = getattr(instance, "is_running", None)
    if is_running is None:
        return True
    try:
        return bool(is_running())
    except Exception:
        return True


def run_live_startup_warmup(
        instance,
        duration_seconds,
        frame_period_seconds=INPUT_POLL_PERIOD_SECONDS,
        sleep_fn=time.sleep,
        monotonic_fn=time.monotonic):
    state = {
        "duration_seconds": float(duration_seconds),
        "frames": 0,
    }
    if duration_seconds <= 0.0:
        return state

    end_time = monotonic_fn() + duration_seconds
    while is_instance_running(instance=instance) and monotonic_fn() < end_time:
        with instance.begin_frame():
            pass
        with instance.end_frame():
            pass
        state["frames"] += 1
        remaining_seconds = end_time - monotonic_fn()
        if remaining_seconds > 0.0:
            sleep_fn(min(frame_period_seconds, remaining_seconds))
    return state


if __name__ == "__main__":
    args = parse_args()

    config = build_config(args=args)
    spear.configure_system(config=config)
    instance = spear.Instance(config=config)
    game = instance.get_game()

    light = None

    try:
        with instance.begin_frame():
            pawn = set_camera_movement_speed(game=game, movement_speed=args.movement_speed)
            player_controller = get_player_controller(game=game)
            runtime_render_config_state = apply_live_runtime_render_config(
                game=game,
                player_controller=player_controller,
                args=args)
            scene_light_state = {
                "disabled_components": 0,
                "scaled_components": 0,
                "skipped_components": 0,
                "scale": args.scene_light_intensity_scale,
            }
            if args.disable_scene_lights:
                disabled_components = disable_scene_lights(game=game)
                scene_light_state["disabled_components"] = disabled_components
                spear.log("Disabled scene light components: ", disabled_components)
            elif args.scene_light_intensity_scale != 1.0:
                scaled_components, skipped_components = scale_scene_light_intensities(
                    game=game,
                    intensity_scale=args.scene_light_intensity_scale)
                scene_light_state["scaled_components"] = scaled_components
                scene_light_state["skipped_components"] = skipped_components
                spear.log(
                    "Scaled scene light components: ",
                    scaled_components,
                    " by ",
                    args.scene_light_intensity_scale)
                if skipped_components > 0:
                    spear.log("Skipped scene light components without scalable intensity: ", skipped_components)

            viewport_desc = get_viewport_pose(game=game)

            light = game.unreal_service.spawn_actor(
                uclass="ASpotLight",
                location=viewport_desc["camera_location"])
            game.unreal_service.set_stable_name_for_actor(actor=light, stable_name="Debug/CameraFlashlight")

            root_component = light.K2_GetRootComponent()
            root_component.SetMobility(NewMobility="Movable")

            spot_light_component = game.unreal_service.get_component_by_class(actor=light, uclass="USpotLightComponent")
            spot_light_component.SetIntensity(NewIntensity=args.intensity)
            spot_light_component.SetAttenuationRadius(NewRadius=args.attenuation_radius)
            spot_light_component.SetIndirectLightingIntensity(NewIntensity=args.indirect_lighting_intensity)
            spot_light_component.SetInnerConeAngle(NewInnerConeAngle=args.inner_cone_angle)
            spot_light_component.SetOuterConeAngle(NewOuterConeAngle=args.outer_cone_angle)
            light_shape_state = apply_spot_light_shape_controls(
                spot_light_component=spot_light_component,
                args=args)
            light_inverse_square_state = flashlight_profiles.apply_spot_light_inverse_square_controls(
                spot_light_component=spot_light_component,
                args=args)
            light_shadow_state = flashlight_profiles.apply_spot_light_shadow_controls(
                spot_light_component=spot_light_component,
                args=args)
            light_ray_traced_shadow_state = apply_live_spot_light_ray_traced_shadow_intent(
                spot_light_component=spot_light_component,
                args=args,
                runtime_render_config_state=runtime_render_config_state)

        with instance.end_frame():
            pass

        with instance.begin_frame():
            viewport_desc = get_viewport_pose(game=game)
            set_light_pose(light=light, viewport_desc=viewport_desc)
            attach_light_to_pawn(light=light, pawn=pawn)
        with instance.end_frame():
            pass

        startup_warmup_state = run_live_startup_warmup(
            instance=instance,
            duration_seconds=args.startup_warmup_seconds)

        spear.log("Spawned camera flashlight. Press Ctrl+C to stop.")
        spear.log("Live lighting mode: ", args.live_lighting_mode)
        spear.log("Hardware ray tracing requested config: ", get_hardware_ray_tracing_requested_state(args=args))
        spear.log("Hardware ray tracing runtime command/readback state: ", runtime_render_config_state["hardware_ray_tracing"])
        spear.log("Hardware ray tracing readback caveat: readback must confirm requested CVars; unsupported Vulkan SM5/RHI paths may reject or ignore the request.")
        spear.log("Exposure/local exposure runtime config: ", runtime_render_config_state)
        spear.log("Scene light state: ", scene_light_state)
        spear.log("Realistic live renderer retains Lumen GI/reflections/material response: ", is_realistic_live_mode(args=args))
        spear.log("Flashlight cone angles: ", args.inner_cone_angle, " inner, ", args.outer_cone_angle, " outer")
        spear.log("Flashlight source radii: ", args.source_radius, " source, ", args.soft_source_radius, " soft source")
        spear.log("Flashlight source radius controls applied: ", light_shape_state)
        spear.log("Flashlight profile: ", args.flashlight_profile_desc)
        spear.log("Flashlight inverse-square controls applied: ", light_inverse_square_state)
        spear.log("Flashlight shadow controls applied: ", light_shadow_state)
        spear.log("Flashlight ray-traced shadow intent applied: ", light_ray_traced_shadow_state)
        spear.log("Camera movement speed: ", args.movement_speed)
        spear.log("Flashlight indirect lighting intensity: ", args.indirect_lighting_intensity)
        spear.log("Startup warmup before live control: ", startup_warmup_state)
        spear.log("Live flashlight control begins.")
        spear.log("Flashlight toggle key: ", args.toggle_key)
        spear.log("Flashlight aim D-pad keys: ", args.aim_left_key, args.aim_right_key, args.aim_up_key, args.aim_down_key)
        spear.log(
            "Flashlight intensity triggers: ",
            args.intensity_down_key,
            " decreases, ",
            args.intensity_up_key,
            " increases")
        spear.log(
            "Flashlight intensity control: current ",
            args.intensity,
            ", rate ",
            args.intensity_adjust_rate,
            ", min ",
            args.intensity_min,
            ", max ",
            args.intensity_max,
            ", trigger deadzone ",
            args.intensity_trigger_deadzone)
        spear.log(
            "Flashlight aim yaw range: ",
            args.aim_yaw_min_degrees,
            " to ",
            args.aim_yaw_max_degrees,
            " degrees")
        spear.log(
            "Flashlight aim pitch range: ",
            args.aim_pitch_min_degrees,
            " to ",
            args.aim_pitch_max_degrees,
            " degrees")
        spear.log("Flashlight aim rate: ", args.aim_rate_degrees_per_second, " degrees per second")
        if args.capture_poses:
            spear.log("Pose capture enabled. Press Enter in this terminal or press the capture key on the controller to save the current camera pose.")
            spear.log("Capture key: ", args.capture_key)
            spear.log("Pose output file: ", args.pose_output_file)

        pose_index = 0
        flashlight_visible = True
        flashlight_intensity = args.intensity
        last_intensity_log_time = None
        aim_yaw_offset_degrees = 0.0
        aim_pitch_offset_degrees = 0.0
        previous_poll_time = time.monotonic()
        previous_key_down_by_name = {}
        while instance.is_running():
            time.sleep(min(args.idle_period_seconds, INPUT_POLL_PERIOD_SECONDS))
            poll_time = time.monotonic()
            poll_delta_seconds = poll_time - previous_poll_time
            previous_poll_time = poll_time
            should_capture_pose = False
            should_toggle_flashlight = False
            aim_yaw_direction = 0.0
            aim_pitch_direction = 0.0
            intensity_state = None
            if args.capture_poses:
                if sys.stdin in select.select([sys.stdin], [], [], 0.0)[0]:
                    sys.stdin.readline()
                    should_capture_pose = True

            with instance.begin_frame():
                player_controller = get_player_controller(game=game)
                should_toggle_flashlight = was_input_key_pressed_since_last_poll(
                    player_controller=player_controller,
                    key_name=args.toggle_key,
                    previous_key_down_by_name=previous_key_down_by_name)
                if args.capture_poses and not should_capture_pose:
                    should_capture_pose = was_input_key_pressed_since_last_poll(
                        player_controller=player_controller,
                        key_name=args.capture_key,
                        previous_key_down_by_name=previous_key_down_by_name)
                if is_input_key_down(player_controller=player_controller, key_name=args.aim_left_key):
                    aim_yaw_direction -= 1.0
                if is_input_key_down(player_controller=player_controller, key_name=args.aim_right_key):
                    aim_yaw_direction += 1.0
                if is_input_key_down(player_controller=player_controller, key_name=args.aim_up_key):
                    aim_pitch_direction += 1.0
                if is_input_key_down(player_controller=player_controller, key_name=args.aim_down_key):
                    aim_pitch_direction -= 1.0
                intensity_state = update_live_flashlight_intensity_from_triggers(
                    player_controller=player_controller,
                    spot_light_component=spot_light_component,
                    current_intensity=flashlight_intensity,
                    delta_seconds=poll_delta_seconds,
                    args=args)
            with instance.end_frame():
                pass

            if intensity_state is not None and intensity_state["changed"]:
                flashlight_intensity = intensity_state["intensity"]
                should_log_intensity = (
                    last_intensity_log_time is None
                    or poll_time - last_intensity_log_time >= args.intensity_log_period_seconds
                    or intensity_state["at_min"]
                    or intensity_state["at_max"])
                if should_log_intensity:
                    last_intensity_log_time = poll_time
                    spear.log(
                        "Flashlight intensity: ",
                        flashlight_intensity,
                        " (left trigger ",
                        intensity_state["decrease_axis"],
                        ", right trigger ",
                        intensity_state["increase_axis"],
                        ")")

            if aim_yaw_direction != 0.0 or aim_pitch_direction != 0.0:
                aim_yaw_offset_degrees = clamp(
                    value=aim_yaw_offset_degrees + aim_yaw_direction * args.aim_rate_degrees_per_second * poll_delta_seconds,
                    min_value=args.aim_yaw_min_degrees,
                    max_value=args.aim_yaw_max_degrees)
                aim_pitch_offset_degrees = clamp(
                    value=aim_pitch_offset_degrees + aim_pitch_direction * args.aim_rate_degrees_per_second * poll_delta_seconds,
                    min_value=args.aim_pitch_min_degrees,
                    max_value=args.aim_pitch_max_degrees)
                with instance.begin_frame():
                    viewport_desc = get_viewport_pose(game=game)
                    set_light_aim(
                        light=light,
                        viewport_desc=viewport_desc,
                        yaw_offset_degrees=aim_yaw_offset_degrees,
                        pitch_offset_degrees=aim_pitch_offset_degrees)
                with instance.end_frame():
                    pass

            if should_toggle_flashlight:
                flashlight_visible = not flashlight_visible
                with instance.begin_frame():
                    spot_light_component.SetVisibility(bNewVisibility=flashlight_visible, bPropagateToChildren=True)
                with instance.end_frame():
                    pass
                spear.log("Flashlight visible: ", flashlight_visible)

            if should_capture_pose:
                pose_name = "waypoint_" + str(pose_index).zfill(3)
                pose_index += 1
                with instance.begin_frame():
                    viewport_desc = get_viewport_pose(game=game)
                    pose_desc = save_viewport_pose(
                        name=pose_name,
                        viewport_desc=viewport_desc,
                        output_file=args.pose_output_file)
                with instance.end_frame():
                    pass
                spear.log("Captured pose: ", pose_desc)

    except KeyboardInterrupt:
        spear.log("Stopping camera flashlight.")

    finally:
        if light is not None and instance.is_running():
            with instance.begin_frame():
                pass
            with instance.end_frame():
                game.unreal_service.destroy_actor(actor=light)

        instance.close()
        spear.log("Done.")
