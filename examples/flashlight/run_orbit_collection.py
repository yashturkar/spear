#
# Copyright (c) 2025 The SPEAR Development Team. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
# Copyright (c) 2022 Intel. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
#

from __future__ import annotations

import argparse
import copy
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
import yacs.config


INPUT_POLL_PERIOD_SECONDS = 1.0 / 60.0
DEPTH_VISUALIZATION_EPSILON = 1.0e-6
DEFAULT_DEPTH_VISUALIZATION_LOWER_PERCENTILE = 1.0
DEFAULT_DEPTH_VISUALIZATION_UPPER_PERCENTILE = 99.0
DEFAULT_DEPTH_VISUALIZATION_MAX_SAMPLES = 1000000
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
DEFAULT_INNER_CONE_ANGLE = 2.0
DEFAULT_OUTER_CONE_ANGLE = 60.0
DEFAULT_SOURCE_RADIUS = 12.0
DEFAULT_SOFT_SOURCE_RADIUS = 80.0

DETERMINISTIC_ORBIT_RENDER_ENGINE_INI = """[/Script/Engine.RendererSettings]
r.DefaultFeature.AntiAliasing=0
r.AntiAliasingMethod=0
r.DefaultFeature.MotionBlur=False
r.MotionBlurQuality=0
r.DynamicGlobalIlluminationMethod=0
r.ReflectionMethod=0
r.Lumen.DiffuseIndirect.Allow=0
r.Lumen.Reflections.Allow=0
r.SSR.Quality=0
r.TemporalAA.Quality=0
"""

SCENE_OFF_LIGHTING_ISOLATION_SHOW_FLAGS = (
    "AmbientOcclusion",
    "AmbientCubemap",
    "Atmosphere",
    "Cloud",
    "DistanceFieldAO",
    "Fog",
    "GlobalIllumination",
    "IndirectLightingCache",
    "LightShafts",
    "LocalExposure",
    "LumenGlobalIllumination",
    "LumenReflections",
    "Materials",
    "ReflectionEnvironment",
    "ScreenSpaceAO",
    "ScreenSpaceReflections",
    "Specular",
    "SkyLighting",
    "VolumetricFog",
    "VolumetricLightmap",
)

SCENE_OFF_LIGHTING_ISOLATION_ENABLED_SHOW_FLAGS = (
    "LightingOnlyOverride",
)

SCENE_OFF_LIGHTING_ISOLATION_ENGINE_INI = """[SystemSettings]
ShowFlag.AmbientOcclusion=0
ShowFlag.AmbientCubemap=0
ShowFlag.Atmosphere=0
ShowFlag.Cloud=0
ShowFlag.DistanceFieldAO=0
ShowFlag.Fog=0
ShowFlag.GlobalIllumination=0
ShowFlag.IndirectLightingCache=0
ShowFlag.LightShafts=0
ShowFlag.LightingOnlyOverride=1
ShowFlag.LocalExposure=0
ShowFlag.LumenGlobalIllumination=0
ShowFlag.LumenReflections=0
ShowFlag.Materials=0
ShowFlag.ReflectionEnvironment=0
ShowFlag.ScreenSpaceAO=0
ShowFlag.ScreenSpaceReflections=0
ShowFlag.Specular=0
ShowFlag.SkyLighting=0
ShowFlag.VolumetricFog=0
ShowFlag.VolumetricLightmap=0
"""

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

RGB_CAPTURE_PROFILE_FINAL_TONE_CURVE = "final_tone_curve_hdr"
RGB_CAPTURE_PROFILE_LIGHTING_ONLY = "lighting_only_post_process_input_2"

FINAL_TONE_CURVE_RGB_COMPONENT_LONG_NAME = "DefaultSceneRoot.final_tone_curve_hdr_"
SCENE_OFF_LIGHTING_ONLY_RGB_COMPONENT_LONG_NAME = "DefaultSceneRoot.lighting_only_post_process_input_2_"

CAPTURE_COMPONENT_DESCS = [
    {
        "name": "rgb",
        "long_name": FINAL_TONE_CURVE_RGB_COMPONENT_LONG_NAME,
        "capture_profile": RGB_CAPTURE_PROFILE_FINAL_TONE_CURVE,
        "scene_off_lighting_only_rgb_requested": False,
    },
    {
        "name": "depth_meters",
        "long_name": "DefaultSceneRoot.sp_depth_meters_",
    },
]

SCENE_OFF_CAPTURE_COMPONENT_DESCS = [
    {
        "name": "rgb",
        "long_name": SCENE_OFF_LIGHTING_ONLY_RGB_COMPONENT_LONG_NAME,
        "capture_profile": RGB_CAPTURE_PROFILE_LIGHTING_ONLY,
        "scene_off_lighting_only_rgb_requested": True,
    },
    {
        "name": "depth_meters",
        "long_name": "DefaultSceneRoot.sp_depth_meters_",
    },
]


def get_capture_component_descs(scene_off_lighting_isolation=False):
    component_descs = (
        SCENE_OFF_CAPTURE_COMPONENT_DESCS
        if scene_off_lighting_isolation
        else CAPTURE_COMPONENT_DESCS)
    return [dict(component_desc) for component_desc in component_descs]


def get_rgb_capture_component_desc(component_descs):
    for component_desc in component_descs:
        if component_desc["name"] == "rgb":
            return component_desc
    raise RuntimeError("No rgb capture component descriptor is configured.")

PERSIST_RENDERING_STATE_PROPERTY_NAMES = (
    "always_persist_rendering_state",
    "bAlwaysPersistRenderingState",
    "b_always_persist_rendering_state",
)

POST_PROCESS_SETTINGS_PROPERTY_NAMES = (
    "PostProcessSettings",
    "post_process_settings",
)

ENVIRONMENT_COMPONENT_CLASS_NAMES = (
    "USkyLightComponent",
    "UExponentialHeightFogComponent",
    "UAtmosphericFogComponent",
    "USkyAtmosphereComponent",
    "UVolumetricCloudComponent",
    "UReflectionCaptureComponent",
    "UPostProcessComponent",
)

ENVIRONMENT_ZERO_PROPERTIES_BY_CLASS = {
    "USkyLightComponent": (
        "Intensity",
        "intensity",
        "IndirectLightingIntensity",
        "indirect_lighting_intensity",
    ),
    "UExponentialHeightFogComponent": (
        "FogDensity",
        "fog_density",
        "StartDistance",
        "start_distance",
        "VolumetricFogScatteringDistribution",
        "volumetric_fog_scattering_distribution",
    ),
    "UAtmosphericFogComponent": (
        "SunMultiplier",
        "sun_multiplier",
        "FogMultiplier",
        "fog_multiplier",
        "DensityMultiplier",
        "density_multiplier",
    ),
    "USkyAtmosphereComponent": (
        "AerialPespectiveViewDistanceScale",
        "aerial_pespective_view_distance_scale",
        "HeightFogContribution",
        "height_fog_contribution",
    ),
    "UVolumetricCloudComponent": (
        "LayerBottomAltitude",
        "layer_bottom_altitude",
        "LayerHeight",
        "layer_height",
    ),
    "UPostProcessComponent": (
        "BlendWeight",
        "blend_weight",
    ),
}

ENVIRONMENT_ZERO_METHODS_BY_CLASS = {
    "USkyLightComponent": (
        ("SetIntensity", {"NewIntensity": 0.0}),
        ("SetIndirectLightingIntensity", {"NewIntensity": 0.0}),
        ("SetAffectsWorld", {"bNewValue": False}),
        ("RecaptureSky", {}),
    ),
    "UExponentialHeightFogComponent": (
        ("SetFogDensity", {"Value": 0.0}),
        ("SetStartDistance", {"Value": 100000000.0}),
    ),
}

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
    parser.add_argument("--indirect-lighting-intensity", type=float, default=0.0)
    parser.add_argument("--inner-cone-angle", type=float, default=DEFAULT_INNER_CONE_ANGLE)
    parser.add_argument("--outer-cone-angle", type=float, default=DEFAULT_OUTER_CONE_ANGLE)
    parser.add_argument("--source-radius", type=float, default=DEFAULT_SOURCE_RADIUS)
    parser.add_argument("--soft-source-radius", type=float, default=DEFAULT_SOFT_SOURCE_RADIUS)
    parser.add_argument("--initial-light-disabled", action="store_true")
    parser.add_argument("--light-yaw-offset-degrees", type=float, default=0.0)
    parser.add_argument("--light-pitch-offset-degrees", type=float, default=0.0)
    parser.add_argument("--movement-speed", type=float, default=1200.0)
    parser.add_argument("--disable-scene-lights", action="store_true")
    parser.add_argument("--scene-light-intensity-scale", type=float, default=1.0)
    auto_exposure_group = parser.add_mutually_exclusive_group()
    auto_exposure_group.add_argument("--disable-auto-exposure", dest="disable_auto_exposure", action="store_true", default=True)
    auto_exposure_group.add_argument("--enable-auto-exposure", dest="disable_auto_exposure", action="store_false")
    render_history_group = parser.add_mutually_exclusive_group()
    render_history_group.add_argument("--disable-render-history", dest="disable_render_history", action="store_true", default=True)
    render_history_group.add_argument("--enable-render-history", dest="disable_render_history", action="store_false")
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
    parser.add_argument("--depth-visualization-lower-percentile", type=float, default=DEFAULT_DEPTH_VISUALIZATION_LOWER_PERCENTILE)
    parser.add_argument("--depth-visualization-upper-percentile", type=float, default=DEFAULT_DEPTH_VISUALIZATION_UPPER_PERCENTILE)
    parser.add_argument("--depth-visualization-min-meters", type=float, default=None)
    parser.add_argument("--depth-visualization-max-meters", type=float, default=None)
    parser.add_argument("--depth-visualization-max-samples", type=int, default=DEFAULT_DEPTH_VISUALIZATION_MAX_SAMPLES)
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
    if not math.isfinite(args.intensity) or args.intensity < 0.0:
        parser.error("--intensity must be a finite non-negative value")
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
    if args.movement_speed <= 0.0:
        parser.error("--movement-speed must be positive")
    if not math.isfinite(args.scene_light_intensity_scale) or args.scene_light_intensity_scale < 0.0:
        parser.error("--scene-light-intensity-scale must be a finite non-negative value")
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
    if not math.isfinite(args.depth_visualization_lower_percentile):
        parser.error("--depth-visualization-lower-percentile must be finite")
    if not math.isfinite(args.depth_visualization_upper_percentile):
        parser.error("--depth-visualization-upper-percentile must be finite")
    if args.depth_visualization_lower_percentile < 0.0 or args.depth_visualization_lower_percentile > 100.0:
        parser.error("--depth-visualization-lower-percentile must be between 0 and 100")
    if args.depth_visualization_upper_percentile < 0.0 or args.depth_visualization_upper_percentile > 100.0:
        parser.error("--depth-visualization-upper-percentile must be between 0 and 100")
    if args.depth_visualization_lower_percentile >= args.depth_visualization_upper_percentile:
        parser.error("--depth-visualization-lower-percentile must be less than --depth-visualization-upper-percentile")
    if args.depth_visualization_min_meters is not None and not math.isfinite(args.depth_visualization_min_meters):
        parser.error("--depth-visualization-min-meters must be finite")
    if args.depth_visualization_max_meters is not None and not math.isfinite(args.depth_visualization_max_meters):
        parser.error("--depth-visualization-max-meters must be finite")
    if (args.depth_visualization_min_meters is not None and
            args.depth_visualization_max_meters is not None and
            args.depth_visualization_min_meters >= args.depth_visualization_max_meters):
        parser.error("--depth-visualization-min-meters must be less than --depth-visualization-max-meters")
    if args.depth_visualization_max_samples <= 0:
        parser.error("--depth-visualization-max-samples must be positive")

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


def disable_scene_light_component(light_component):
    state = {
        "visibility_disabled": False,
        "direct_intensity_zeroed": False,
        "indirect_lighting_intensity_zeroed": False,
    }
    state["visibility_disabled"] = try_call_method(
        light_component,
        "SetVisibility",
        bNewVisibility=False,
        bPropagateToChildren=True)
    state["direct_intensity_zeroed"] = try_call_method(
        light_component,
        "SetIntensity",
        NewIntensity=0.0)
    state["indirect_lighting_intensity_zeroed"] = try_call_method(
        light_component,
        "SetIndirectLightingIntensity",
        NewIntensity=0.0)
    return state


def disable_scene_lights(game):
    state = {
        "components": 0,
        "visibility_disabled": 0,
        "direct_intensity_zeroed": 0,
        "indirect_lighting_intensity_zeroed": 0,
    }
    actors = game.unreal_service.find_actors()

    for actor in actors:
        light_components = game.unreal_service.get_components_by_class(
            actor=actor,
            uclass="ULightComponentBase",
            include_from_child_actors=True)

        for light_component in light_components:
            component_state = disable_scene_light_component(light_component=light_component)
            state["components"] += 1
            for key, value in component_state.items():
                if value:
                    state[key] += 1

    return state


def get_components_by_class_safely(game, actor, uclass):
    try:
        return game.unreal_service.get_components_by_class(
            actor=actor,
            uclass=uclass,
            include_from_child_actors=True)
    except Exception:
        return []


def disable_scene_environment_component(component, uclass):
    state = {
        "visibility_disabled": False,
        "properties_zeroed": 0,
        "methods_zeroed": 0,
    }
    state["visibility_disabled"] = try_call_method(
        component,
        "SetVisibility",
        bNewVisibility=False,
        bPropagateToChildren=True)

    for method_name, kwargs in ENVIRONMENT_ZERO_METHODS_BY_CLASS.get(uclass, ()):
        if try_call_method(component, method_name, **kwargs):
            state["methods_zeroed"] += 1

    for property_name in ENVIRONMENT_ZERO_PROPERTIES_BY_CLASS.get(uclass, ()):
        if try_set_property_and_verify(obj=component, property_names=(property_name,), value=0.0):
            state["properties_zeroed"] += 1

    post_process_settings = get_first_property_value(
        obj=component,
        property_names=POST_PROCESS_SETTINGS_PROPERTY_NAMES)
    if post_process_settings is not None:
        post_process_settings_value = unwrap_property_value(value=post_process_settings)
        for property_name in (
                "ambient_cubemap_intensity",
                "AmbientCubemapIntensity",
                "indirect_lighting_color",
                "IndirectLightingColor"):
            if try_set_property_and_verify(obj=post_process_settings_value, property_names=(property_name,), value=0.0):
                state["properties_zeroed"] += 1

    return state


def disable_scene_environment_contributors(game):
    state = {
        "components": 0,
        "visibility_disabled": 0,
        "properties_zeroed": 0,
        "methods_zeroed": 0,
        "component_classes": {},
    }
    actors = game.unreal_service.find_actors()

    for actor in actors:
        for uclass in ENVIRONMENT_COMPONENT_CLASS_NAMES:
            components = get_components_by_class_safely(game=game, actor=actor, uclass=uclass)
            if not components:
                continue
            state["component_classes"][uclass] = state["component_classes"].get(uclass, 0) + len(components)
            for component in components:
                component_state = disable_scene_environment_component(component=component, uclass=uclass)
                state["components"] += 1
                if component_state["visibility_disabled"]:
                    state["visibility_disabled"] += 1
                state["properties_zeroed"] += component_state["properties_zeroed"]
                state["methods_zeroed"] += component_state["methods_zeroed"]

    return state


def disable_scene_lighting(game):
    state = disable_scene_lights(game=game)
    state["environment_contributors"] = disable_scene_environment_contributors(game=game)
    return state


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


def apply_auto_exposure_config(config, args):
    if args.disable_auto_exposure:
        append_engine_ini_config(
            config=config,
            engine_ini_config=AUTO_EXPOSURE_DISABLED_ENGINE_INI)


def apply_deterministic_orbit_render_config(config, args):
    if args.mode == "render" and args.disable_render_history:
        append_engine_ini_config(
            config=config,
            engine_ini_config=DETERMINISTIC_ORBIT_RENDER_ENGINE_INI)


def should_apply_scene_off_lighting_isolation(args):
    return bool(args.mode == "render" and args.disable_scene_lights)


def apply_scene_off_lighting_isolation_config(config, args):
    if should_apply_scene_off_lighting_isolation(args=args):
        append_engine_ini_config(
            config=config,
            engine_ini_config=SCENE_OFF_LIGHTING_ISOLATION_ENGINE_INI)


def apply_scene_off_lighting_isolation_console_commands(game):
    state = {
        "commands": [],
        "applied": 0,
    }
    try:
        player_controller = get_player_controller(game=game)
    except Exception as exc:
        state["error"] = str(exc)
        return state

    show_flag_values = {
        show_flag_name: False
        for show_flag_name in SCENE_OFF_LIGHTING_ISOLATION_SHOW_FLAGS
    }
    show_flag_values.update({
        show_flag_name: True
        for show_flag_name in SCENE_OFF_LIGHTING_ISOLATION_ENABLED_SHOW_FLAGS
    })

    for show_flag_name, enabled in show_flag_values.items():
        command = f"ShowFlag.{show_flag_name} {1 if enabled else 0}"
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

    return state


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


def build_config(
        args,
        orbit_spec=None,
        benchmarking=False,
        max_num_frames=None,
        width=None,
        height=None,
        user_config_files=None):
    if user_config_files is None:
        user_config_files = [os.path.realpath(os.path.join(os.path.dirname(__file__), "user_config.yaml"))]
    config = spear.get_config(user_config_files=user_config_files)
    config.defrost()
    ensure_legacy_sp_core_ini_config_values(config=config)
    apply_auto_exposure_config(config=config, args=args)
    apply_deterministic_orbit_render_config(config=config, args=args)
    apply_scene_off_lighting_isolation_config(config=config, args=args)
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
    if "scene_lights_enabled" in setting and not isinstance(setting["scene_lights_enabled"], bool):
        raise ValueError(f"Light setting {setting['name']} scene_lights_enabled must be a JSON boolean.")
    if "spawn_flashlight" in setting and not isinstance(setting["spawn_flashlight"], bool):
        raise ValueError(f"Light setting {setting['name']} spawn_flashlight must be a JSON boolean.")
    if setting.get("spawn_flashlight") is False and setting["enabled"]:
        raise ValueError(f"Light setting {setting['name']} cannot enable a flashlight when spawn_flashlight is false.")
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


def light_command_to_metadata(command):
    if command is None:
        return None
    return {
        "enabled": bool(command.enabled),
        "intensity": float(command.intensity),
        "yaw_offset_degrees": float(command.yaw_offset_degrees),
        "pitch_offset_degrees": float(command.pitch_offset_degrees),
    }


def get_light_setting_scene_lights_enabled(setting):
    return bool(setting.get("scene_lights_enabled", True))


def should_spawn_flashlight_for_setting(setting):
    return bool(setting.get("spawn_flashlight", True))


def get_initial_render_light_setup(light_settings):
    first_setting = light_settings[0]
    spawn_flashlight = should_spawn_flashlight_for_setting(setting=first_setting)
    return {
        "source": "first_light_setting",
        "setting_name": first_setting["name"],
        "spawn_flashlight": spawn_flashlight,
        "command": command_from_setting(setting=first_setting) if spawn_flashlight else None,
    }


def get_scene_light_render_groups(light_settings):
    scene_on_settings = []
    scene_off_settings = []
    for setting in light_settings:
        if get_light_setting_scene_lights_enabled(setting=setting):
            scene_on_settings.append(setting)
        else:
            scene_off_settings.append(setting)

    groups = []
    if scene_on_settings:
        groups.append((True, scene_on_settings))
    if scene_off_settings:
        groups.append((False, scene_off_settings))
    return groups


def get_scene_light_group_args(args, scene_lights_enabled):
    group_args = copy.copy(args)
    if not scene_lights_enabled:
        group_args.disable_scene_lights = True
        group_args.scene_light_intensity_scale = 1.0
    return group_args


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
        "depth_meters_npy": os.path.join(setting_dir, "frames", "depth_meters_npy"),
        "depth_meters_viridis": os.path.join(setting_dir, "frames", "depth_meters_viridis"),
    }
    for frame_dir in frame_dirs.values():
        os.makedirs(frame_dir, exist_ok=True)
    return setting_dir, frame_dirs


def get_setting_video_files(setting_dir):
    return {
        "rgb": os.path.join(setting_dir, "rgb.mp4"),
        "depth_meters_viridis": os.path.join(setting_dir, "depth_meters_viridis.mp4"),
    }


def get_deterministic_capture_metadata(component_descs, disable_render_history):
    components = [
        {
            "name": component_desc["name"],
            "state": to_plain_dict(component_desc.get("deterministic_capture_state", {})),
        }
        for component_desc in component_descs
    ]
    unverified_components = [
        component["name"]
        for component in components
        if disable_render_history and not component["state"].get("always_persist_rendering_state_disabled", False)
    ]
    return {
        "requested": bool(disable_render_history),
        "render_history_disable_verified": bool(disable_render_history) and not unverified_components,
        "unverified_render_history_components": unverified_components,
        "components": components,
        "note": (
            "Render-history disable was verified by capture-component readback."
            if bool(disable_render_history) and not unverified_components
            else "Render-history disable was requested, but live proxy readback did not verify every capture component."
            if disable_render_history
            else "Render-history disable was not requested."
        ),
    }


def get_capture_component_metadata(component_descs):
    return [
        {
            "name": component_desc["name"],
            "long_name": component_desc.get("long_name"),
            "capture_profile": component_desc.get("capture_profile"),
            "scene_off_lighting_only_rgb_requested": bool(
                component_desc.get("scene_off_lighting_only_rgb_requested", False)),
        }
        for component_desc in component_descs
    ]


def get_scene_off_lighting_isolation_metadata(component_descs, requested):
    components = [
        {
            "name": component_desc["name"],
            "state": to_plain_dict(component_desc.get("scene_off_lighting_isolation_state", {})),
        }
        for component_desc in component_descs
    ]
    return {
        "requested": bool(requested),
        "disabled_show_flags": list(SCENE_OFF_LIGHTING_ISOLATION_SHOW_FLAGS) if requested else [],
        "enabled_show_flags": list(SCENE_OFF_LIGHTING_ISOLATION_ENABLED_SHOW_FLAGS) if requested else [],
        "engine_ini_applied": bool(requested),
        "capture_show_flags_attempted": bool(requested),
        "capture_show_flags_configured": bool(requested) and all(
            component["state"].get("configured", False)
            for component in components),
        "components": components,
        "note": (
            "Scene-off renders request lighting-only direct-light capture by disabling materials, skylight, GI, ambient, reflection, fog, and volumetric show flags."
            if requested
            else "Scene-off lighting isolation was not requested."
        ),
    }


def write_setting_metadata(
        setting_dir,
        setting,
        scene_lights_enabled,
        scene_light_state,
        disable_auto_exposure,
        disable_render_history,
        component_descs,
        scene_off_lighting_isolation_requested=False,
        render_diagnostics=None):
    deterministic_capture = get_deterministic_capture_metadata(
        component_descs=component_descs,
        disable_render_history=disable_render_history)
    scene_off_lighting_isolation = get_scene_off_lighting_isolation_metadata(
        component_descs=component_descs,
        requested=scene_off_lighting_isolation_requested)
    capture_components = get_capture_component_metadata(component_descs=component_descs)
    rgb_capture_components = [
        component_desc
        for component_desc in capture_components
        if component_desc["name"] == "rgb"
    ]
    metadata = {
        "schema_version": "1.0.0",
        "setting": to_plain_dict(setting),
        "scene_lights_enabled": bool(scene_lights_enabled),
        "scene_light_state": to_plain_dict(scene_light_state),
        "disable_auto_exposure": bool(disable_auto_exposure),
        "disable_render_history": bool(disable_render_history),
        "capture_components": capture_components,
        "rgb_capture_component": rgb_capture_components[0] if rgb_capture_components else None,
        "render_history_disable_verified": deterministic_capture["render_history_disable_verified"],
        "deterministic_capture": deterministic_capture,
        "deterministic_capture_components": deterministic_capture["components"],
        "scene_off_lighting_isolation": scene_off_lighting_isolation,
    }
    if render_diagnostics is not None:
        metadata["render_diagnostics"] = to_plain_dict(render_diagnostics)
    metadata_file = os.path.join(setting_dir, "metadata.json")
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, sort_keys=True)
    return metadata_file


def update_setting_metadata(metadata_file, updates):
    metadata = read_json_file(json_file=metadata_file)
    metadata.update(to_plain_dict(updates))
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, sort_keys=True)
    return metadata


def visualize_rgb(data, capture_profile=RGB_CAPTURE_PROFILE_FINAL_TONE_CURVE):
    image = np.asarray(data)
    if capture_profile == RGB_CAPTURE_PROFILE_LIGHTING_ONLY:
        if image.ndim == 3 and image.shape[2] >= 3:
            image = image[:, :, :3]
        if np.issubdtype(image.dtype, np.floating):
            image = np.nan_to_num(image, nan=0.0, posinf=1.0, neginf=0.0)
            image = (np.clip(image, 0.0, 1.0) * 255.0).astype(np.uint8)
        else:
            image = np.clip(image, 0, 255).astype(np.uint8)
        if image.ndim == 3 and image.shape[2] >= 3:
            return image[:, :, [2, 1, 0]]
        return image
    if capture_profile == RGB_CAPTURE_PROFILE_FINAL_TONE_CURVE:
        if image.ndim == 3 and image.shape[2] >= 3:
            return image[:, :, :3]
        return image
    raise ValueError(f"Unsupported RGB capture profile: {capture_profile}")


def compute_rgb_luma_diagnostics(frame_dir, frame_count):
    cv2 = import_cv2()
    mean_luma_values = []
    p99_luma_values = []
    bright_pixel_fractions = {
        "gte_200": [],
        "gte_230": [],
    }
    for frame_index in range(frame_count):
        frame_file = os.path.join(frame_dir, f"frame_{frame_index:04d}.png")
        frame = cv2.imread(frame_file, cv2.IMREAD_COLOR)
        if frame is None:
            raise RuntimeError(f"Missing rendered RGB frame for luma diagnostics: {frame_file}")
        frame = np.asarray(frame, dtype=np.float32)
        luma = (
            0.2126 * frame[:, :, 2]
            + 0.7152 * frame[:, :, 1]
            + 0.0722 * frame[:, :, 0])
        mean_luma_values.append(float(np.mean(luma)))
        p99_luma_values.append(float(np.percentile(luma, 99.0)))
        bright_pixel_fractions["gte_200"].append(float(np.mean(luma >= 200.0)))
        bright_pixel_fractions["gte_230"].append(float(np.mean(luma >= 230.0)))

    mean_luma_values = np.asarray(mean_luma_values, dtype=np.float64)
    p99_luma_values = np.asarray(p99_luma_values, dtype=np.float64)
    return {
        "frame_count": int(frame_count),
        "mean_luma_min": float(np.min(mean_luma_values)),
        "mean_luma_median": float(np.median(mean_luma_values)),
        "mean_luma_max": float(np.max(mean_luma_values)),
        "p99_luma_median": float(np.median(p99_luma_values)),
        "bright_pixel_fraction_median": {
            key: float(np.median(np.asarray(values, dtype=np.float64)))
            for key, values in bright_pixel_fractions.items()
        },
    }


def get_residual_scene_off_illumination_diagnostics(render_diagnostics, rgb_luma_diagnostics):
    no_flashlight_control = bool(render_diagnostics.get("no_flashlight_ever_control", False))
    median_mean_luma = float(rgb_luma_diagnostics["mean_luma_median"])
    return {
        "checked": no_flashlight_control,
        "median_mean_luma": median_mean_luma,
        "likely_residual_environment_static_or_material_lighting": bool(
            no_flashlight_control and median_mean_luma > 20.0),
        "threshold_mean_luma": 20.0,
    }


def depth_to_meters(data):
    depth = np.asarray(data)
    if depth.ndim == 3:
        if depth.shape[2] < 1:
            raise ValueError("Depth image must have at least one channel")
        depth = depth[:, :, 0]
    elif depth.ndim != 2:
        raise ValueError(f"Depth image must be 2D or 3D with channels, got shape {depth.shape}")
    return np.asarray(depth, dtype=np.float32)


def update_depth_range(depth, min_depth=None, max_depth=None):
    depth = depth_to_meters(depth)
    valid = np.isfinite(depth)
    if not np.any(valid):
        return min_depth, max_depth
    frame_min = float(np.min(depth[valid]))
    frame_max = float(np.max(depth[valid]))
    min_depth = frame_min if min_depth is None else min(min_depth, frame_min)
    max_depth = frame_max if max_depth is None else max(max_depth, frame_max)
    return min_depth, max_depth


def normalize_depth_for_visualization(depth, min_depth, max_depth):
    depth = depth_to_meters(depth)
    depth_u8 = np.zeros(depth.shape, dtype=np.uint8)
    valid = np.isfinite(depth)
    if min_depth is None or max_depth is None or not np.any(valid):
        return depth_u8

    span = float(max_depth - min_depth)
    if abs(span) <= DEPTH_VISUALIZATION_EPSILON:
        depth_u8[valid] = 128
    else:
        normalized = np.clip((depth[valid] - min_depth) / span, 0.0, 1.0)
        depth_u8[valid] = (normalized * 255.0).astype(np.uint8)
    return depth_u8


def get_depth_visualization_samples(depth, max_samples):
    depth = depth_to_meters(depth)
    finite_values = depth[np.isfinite(depth)].reshape(-1)
    if finite_values.size <= max_samples:
        return finite_values

    sample_indices = np.linspace(0, finite_values.size - 1, num=max_samples, dtype=np.int64)
    return finite_values[sample_indices]


def get_depth_visualization_bounds(
        depth_frame_files,
        lower_percentile,
        upper_percentile,
        explicit_min_depth=None,
        explicit_max_depth=None,
        finite_min_depth=None,
        finite_max_depth=None,
        max_samples=DEFAULT_DEPTH_VISUALIZATION_MAX_SAMPLES):
    def check_bounds():
        if min_depth is not None and max_depth is not None and min_depth > max_depth:
            raise ValueError(
                "Depth visualization minimum is greater than maximum; adjust explicit bounds or percentile clipping options.")

    min_depth = explicit_min_depth
    max_depth = explicit_max_depth
    need_percentile_min = min_depth is None and lower_percentile > 0.0
    need_percentile_max = max_depth is None and upper_percentile < 100.0

    if min_depth is None and not need_percentile_min:
        min_depth = finite_min_depth
    if max_depth is None and not need_percentile_max:
        max_depth = finite_max_depth
    if not need_percentile_min and not need_percentile_max:
        check_bounds()
        return min_depth, max_depth

    max_samples_per_frame = max(int(math.ceil(max_samples / max(len(depth_frame_files), 1))), 1)
    samples = []
    for depth_frame_file in depth_frame_files:
        frame_samples = get_depth_visualization_samples(
            depth=np.load(depth_frame_file),
            max_samples=max_samples_per_frame)
        if frame_samples.size > 0:
            samples.append(frame_samples)

    if not samples:
        check_bounds()
        return min_depth, max_depth

    all_samples = np.concatenate(samples)
    if need_percentile_min:
        min_depth = float(np.percentile(all_samples, lower_percentile))
    if need_percentile_max:
        max_depth = float(np.percentile(all_samples, upper_percentile))
    check_bounds()
    return min_depth, max_depth


def visualize_depth_viridis(depth, min_depth, max_depth):
    cv2 = import_cv2()
    depth_u8 = normalize_depth_for_visualization(
        depth=depth,
        min_depth=min_depth,
        max_depth=max_depth)
    colorized = cv2.applyColorMap(depth_u8, cv2.COLORMAP_VIRIDIS)
    invalid = ~np.isfinite(depth_to_meters(depth))
    if np.any(invalid):
        colorized[invalid] = 0
    return colorized


def write_depth_viridis_frames(depth_frame_files, frame_dir, min_depth, max_depth):
    cv2 = import_cv2()
    for frame_index, depth_frame_file in enumerate(depth_frame_files):
        depth = np.load(depth_frame_file)
        depth_frame = visualize_depth_viridis(
            depth=depth,
            min_depth=min_depth,
            max_depth=max_depth)
        cv2.imwrite(os.path.join(frame_dir, f"frame_{frame_index:04d}.png"), depth_frame)


def capture_scene(camera_components, disable_render_history=True):
    for component in camera_components:
        if disable_render_history:
            component.bCameraCutThisFrame = True
        component.CaptureScene()


def unwrap_property_value(value):
    if not isinstance(value, dict) and hasattr(value, "get"):
        try:
            return value.get()
        except Exception:
            return value
    return value


def get_mapping_or_attr_value(obj, key):
    if isinstance(obj, dict):
        if key not in obj:
            raise AttributeError(key)
        return obj[key]
    if hasattr(obj, "get_editor_property"):
        return obj.get_editor_property(key)
    return getattr(obj, key)


def try_get_mapping_or_attr_value(obj, key):
    try:
        return unwrap_property_value(get_mapping_or_attr_value(obj=obj, key=key))
    except Exception:
        return None


def get_first_property_value(obj, property_names):
    for property_name in property_names:
        try:
            return get_mapping_or_attr_value(obj=obj, key=property_name)
        except Exception:
            continue
    return None


def set_mapping_or_attr_value(obj, key, value):
    if isinstance(obj, dict):
        if key not in obj:
            raise AttributeError(key)
        obj[key] = value
        return True
    if hasattr(obj, "set_editor_property"):
        try:
            obj.set_editor_property(name=key, value=value)
        except TypeError:
            obj.set_editor_property(key, value)
        return True
    if not hasattr(obj, key):
        raise AttributeError(key)
    setattr(obj, key, value)
    return True


def try_set_mapping_or_attr_value(obj, key, value):
    try:
        set_mapping_or_attr_value(obj=obj, key=key, value=value)
    except Exception:
        return False
    return True


def values_match(actual_value, expected_value):
    if isinstance(expected_value, bool):
        return bool(actual_value) is expected_value
    try:
        return float(actual_value) == float(expected_value)
    except (TypeError, ValueError):
        return actual_value == expected_value


def try_set_property_and_verify(obj, property_names, value):
    for property_name in property_names:
        if not try_set_mapping_or_attr_value(obj=obj, key=property_name, value=value):
            continue
        actual_value = try_get_mapping_or_attr_value(obj=obj, key=property_name)
        if actual_value is not None and values_match(actual_value=actual_value, expected_value=value):
            return True
    return False


def set_boolean_property_with_readback(obj, property_names, value):
    attempts = []
    for property_name in property_names:
        attempt = {
            "property": property_name,
            "set": False,
            "readback": None,
            "verified": False,
        }
        attempt["set"] = try_set_mapping_or_attr_value(obj=obj, key=property_name, value=value)
        readback = try_get_mapping_or_attr_value(obj=obj, key=property_name)
        if readback is not None:
            attempt["readback"] = bool(readback)
            attempt["verified"] = bool(readback) is bool(value)
        attempts.append(attempt)
        if attempt["verified"]:
            return True, attempts
    return False, attempts


def configure_deterministic_capture_component(component):
    state = {
        "always_persist_rendering_state_disabled": False,
        "always_persist_rendering_state_attempts": [],
        "dynamic_global_illumination_override_disabled": False,
        "reflection_override_disabled": False,
    }

    (
        state["always_persist_rendering_state_disabled"],
        state["always_persist_rendering_state_attempts"],
    ) = set_boolean_property_with_readback(
        obj=component,
        property_names=PERSIST_RENDERING_STATE_PROPERTY_NAMES,
        value=False)

    post_process_settings = get_first_property_value(
        obj=component,
        property_names=POST_PROCESS_SETTINGS_PROPERTY_NAMES)
    if post_process_settings is not None:
        post_process_settings_value = unwrap_property_value(value=post_process_settings)
        state["dynamic_global_illumination_override_disabled"] = try_set_property_and_verify(
            obj=post_process_settings_value,
            property_names=("override_dynamic_global_illumination_method", "OverrideDynamicGlobalIlluminationMethod"),
            value=False)
        state["reflection_override_disabled"] = try_set_property_and_verify(
            obj=post_process_settings_value,
            property_names=("override_reflection_method", "OverrideReflectionMethod"),
            value=False)
        if post_process_settings_value is not post_process_settings:
            for property_name in POST_PROCESS_SETTINGS_PROPERTY_NAMES:
                if try_set_mapping_or_attr_value(
                        obj=component,
                        key=property_name,
                        value=post_process_settings_value):
                    break

    return state


def get_scene_off_show_flag_values():
    show_flag_values = {
        show_flag_name: False
        for show_flag_name in SCENE_OFF_LIGHTING_ISOLATION_SHOW_FLAGS
    }
    show_flag_values.update({
        show_flag_name: True
        for show_flag_name in SCENE_OFF_LIGHTING_ISOLATION_ENABLED_SHOW_FLAGS
    })
    return show_flag_values


def make_scene_off_show_flag_settings(name_key="ShowFlagName", enabled_key="Enabled"):
    return [
        {
            name_key: show_flag_name,
            enabled_key: enabled,
        }
        for show_flag_name, enabled in get_scene_off_show_flag_values().items()
    ]


def get_show_flag_setter_method_names(show_flag_name):
    snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", show_flag_name).lower()
    return (
        f"Set{show_flag_name}",
        f"set_{snake_name}",
    )


def try_disable_show_flag_object_methods(show_flags, show_flag_name):
    for method_name in get_show_flag_setter_method_names(show_flag_name=show_flag_name):
        if try_call_method(show_flags, method_name, Value=False):
            return True
        if try_call_method(show_flags, method_name, bEnabled=False):
            return True
        if try_call_method(show_flags, method_name, Enabled=False):
            return True
    return False


def try_set_show_flag_settings_property(component, property_name, show_flag_settings):
    if try_set_mapping_or_attr_value(obj=component, key=property_name, value=show_flag_settings):
        return True
    set_property_value = getattr(component, "set_property_value", None)
    if set_property_value is not None:
        try:
            set_property_value(property_name, show_flag_settings, notify_editor=True)
            return True
        except TypeError:
            try:
                set_property_value(property_name, show_flag_settings)
                return True
            except Exception:
                pass
        except Exception:
            pass
    return False


def configure_scene_off_capture_show_flags(component):
    state = {
        "configured": False,
        "show_flag_settings_set": False,
        "show_flag_settings_property": None,
        "show_flag_settings_key_style": None,
        "show_flag_methods_disabled": [],
        "show_flag_methods_enabled": [],
        "show_flag_methods_unverified": [],
    }

    show_flag_setting_variants = (
        ("pascal", make_scene_off_show_flag_settings("ShowFlagName", "Enabled")),
        ("snake", make_scene_off_show_flag_settings("show_flag_name", "enabled")),
    )
    for property_name in ("ShowFlagSettings", "show_flag_settings"):
        for key_style, show_flag_settings in show_flag_setting_variants:
            if try_set_show_flag_settings_property(
                    component=component,
                    property_name=property_name,
                    show_flag_settings=show_flag_settings):
                state["show_flag_settings_set"] = True
                state["show_flag_settings_property"] = property_name
                state["show_flag_settings_key_style"] = key_style
                break
        if state["show_flag_settings_set"]:
            break

    show_flags = get_first_property_value(obj=component, property_names=("ShowFlags", "show_flags"))
    if show_flags is not None:
        show_flags = unwrap_property_value(value=show_flags)
        for show_flag_name, enabled in get_scene_off_show_flag_values().items():
            if try_set_show_flag_object_methods(
                    show_flags=show_flags,
                    show_flag_name=show_flag_name,
                    enabled=enabled):
                if enabled:
                    state["show_flag_methods_enabled"].append(show_flag_name)
                else:
                    state["show_flag_methods_disabled"].append(show_flag_name)
            else:
                state["show_flag_methods_unverified"].append(show_flag_name)

    state["configured"] = (
        state["show_flag_settings_set"]
        or bool(state["show_flag_methods_disabled"])
        or bool(state["show_flag_methods_enabled"]))
    return state


def try_set_show_flag_object_methods(show_flags, show_flag_name, enabled):
    for method_name in get_show_flag_setter_method_names(show_flag_name=show_flag_name):
        if try_call_method(show_flags, method_name, Value=enabled):
            return True
        if try_call_method(show_flags, method_name, bEnabled=enabled):
            return True
        if try_call_method(show_flags, method_name, Enabled=enabled):
            return True
    return False


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


def setup_camera_sensor(
        game,
        width,
        height,
        initial_viewport_desc,
        disable_render_history=True,
        scene_off_lighting_isolation=False):
    bp_camera_sensor_uclass = game.unreal_service.load_class(
        uclass="AActor",
        name="/SpContent/Blueprints/BP_CameraSensor.BP_CameraSensor_C")
    camera_sensor = game.unreal_service.spawn_actor(uclass=bp_camera_sensor_uclass)
    game.unreal_service.set_stable_name_for_actor(actor=camera_sensor, stable_name="Debug/OrbitCollectionCameraSensor")

    component_descs = get_capture_component_descs(
        scene_off_lighting_isolation=scene_off_lighting_isolation)
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

    for component_desc, component in zip(component_descs, camera_components):
        component.BufferingMode = "SingleBuffered"
        component.bCaptureEveryFrame = False
        component.bCaptureOnMovement = False
        component.Initialize()
        component.initialize_sp_funcs()
        if disable_render_history:
            component_desc["deterministic_capture_state"] = configure_deterministic_capture_component(
                component=component)
        if scene_off_lighting_isolation:
            component_desc["scene_off_lighting_isolation_state"] = configure_scene_off_capture_show_flags(
                component=component)

    return camera_sensor, component_descs, camera_components


def capture_orbit_frame(
        instance,
        game,
        camera_sensor,
        camera_components,
        component_descs,
        viewport_desc,
        width,
        height,
        flashlight,
        spot_light_component,
        command,
        disable_render_history,
        read_pixel_data=True):
    component_data = {}
    with instance.begin_frame():
        game.rendering_service.align_camera_with_viewport(
            camera_sensor=camera_sensor,
            camera_components=camera_components,
            viewport_desc=viewport_desc,
            widths=[width for _ in camera_components],
            heights=[height for _ in camera_components])
        if flashlight is not None and spot_light_component is not None:
            flashlight.K2_SetActorLocationAndRotation(
                NewLocation=viewport_desc["camera_location"],
                NewRotation=build_light_rotation(camera_rotation=viewport_desc["camera_rotation"], command=command),
                bSweep=False,
                bTeleport=True)
            set_light_enabled(spot_light_component=spot_light_component, command=command)
        capture_scene(
            camera_components=camera_components,
            disable_render_history=disable_render_history)
    with instance.end_frame(single_step=True):
        for component_desc in component_descs:
            data_bundle = component_desc["component"].read_pixels()
            if read_pixel_data:
                component_data[component_desc["name"]] = data_bundle["arrays"]["data"].copy()

    return component_data


def discard_warmup_captures(
        instance,
        game,
        camera_sensor,
        camera_components,
        component_descs,
        viewport_desc,
        width,
        height,
        flashlight,
        spot_light_component,
        command,
        disable_render_history,
        num_captures):
    for _ in range(num_captures):
        capture_orbit_frame(
            instance=instance,
            game=game,
            camera_sensor=camera_sensor,
            camera_components=camera_components,
            component_descs=component_descs,
            viewport_desc=viewport_desc,
            width=width,
            height=height,
            flashlight=flashlight,
            spot_light_component=spot_light_component,
            command=command,
            disable_render_history=disable_render_history,
            read_pixel_data=False)


def get_warmup_capture_count(args):
    return max(int(args.settle_frames), 1)


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
    spot_light_component.SetIndirectLightingIntensity(NewIntensity=args.indirect_lighting_intensity)
    spot_light_component.SetInnerConeAngle(NewInnerConeAngle=args.inner_cone_angle)
    spot_light_component.SetOuterConeAngle(NewOuterConeAngle=args.outer_cone_angle)
    light_shape_state = apply_spot_light_shape_controls(
        spot_light_component=spot_light_component,
        args=args)
    try:
        spot_light_component._spear_light_shape_state = light_shape_state
    except Exception:
        pass
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
                disabled_components = disable_scene_lighting(game=game)
                spear.log("Disabled scene light components: ", disabled_components)
            elif args.scene_light_intensity_scale != 1.0:
                scaled_components, skipped_components = scale_scene_light_intensities(
                    game=game,
                    intensity_scale=args.scene_light_intensity_scale)
                spear.log(
                    "Scaled scene light components: ",
                    scaled_components,
                    " by ",
                    args.scene_light_intensity_scale)
                if skipped_components > 0:
                    spear.log("Skipped scene light components without scalable intensity: ", skipped_components)

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
        spear.log("Flashlight cone angles: ", args.inner_cone_angle, " inner, ", args.outer_cone_angle, " outer")
        spear.log("Flashlight source radii: ", args.source_radius, " source, ", args.soft_source_radius, " soft source")
        spear.log("Flashlight indirect lighting intensity: ", args.indirect_lighting_intensity)
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


def run_render_group(args, orbit_spec, light_settings, scene_lights_enabled):
    cv2 = import_cv2()

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

    warmup_capture_count = get_warmup_capture_count(args=args)
    max_num_frames = len(light_settings) * (frame_count + warmup_capture_count + 2) + warmup_capture_count + 8
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
    spot_light_component = None
    scene_light_state = {
        "components": 0,
        "visibility_disabled": 0,
        "direct_intensity_zeroed": 0,
        "indirect_lighting_intensity_zeroed": 0,
        "scaled_components": 0,
        "skipped_components": 0,
        "scale": args.scene_light_intensity_scale,
    }

    try:
        spear.log(
            "Rendering scene lights ",
            "enabled" if scene_lights_enabled else "disabled",
            " for settings: ",
            [setting["name"] for setting in light_settings])
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
        initial_light_setup = get_initial_render_light_setup(light_settings=light_settings)
        flashlight_ever_spawned = False
        flashlight_ever_enabled = False

        with instance.begin_frame():
            if args.disable_scene_lights:
                scene_light_state.update(disable_scene_lighting(game=game))
                scene_light_state["scene_off_lighting_isolation_console_commands"] = (
                    apply_scene_off_lighting_isolation_console_commands(game=game))
                spear.log("Disabled scene light components: ", scene_light_state)
            elif args.scene_light_intensity_scale != 1.0:
                scaled_components, skipped_components = scale_scene_light_intensities(
                    game=game,
                    intensity_scale=args.scene_light_intensity_scale)
                scene_light_state.update({
                    "scaled_components": scaled_components,
                    "skipped_components": skipped_components,
                })
                spear.log(
                    "Scaled scene light components: ",
                    scaled_components,
                    " by ",
                    args.scene_light_intensity_scale)
                if skipped_components > 0:
                    spear.log("Skipped scene light components without scalable intensity: ", skipped_components)
            camera_sensor, component_descs, camera_components = setup_camera_sensor(
                game=game,
                width=width,
                height=height,
                initial_viewport_desc=initial_viewport_desc,
                disable_render_history=args.disable_render_history,
                scene_off_lighting_isolation=should_apply_scene_off_lighting_isolation(args=args))
            if initial_light_setup["spawn_flashlight"]:
                flashlight, spot_light_component = spawn_flashlight(
                    game=game,
                    location=first_location,
                    rotation=first_rotation,
                    args=args,
                    command=initial_light_setup["command"],
                    stable_name="Debug/OrbitCollectionRenderFlashlight")
                flashlight_ever_spawned = True
                flashlight_ever_enabled = bool(initial_light_setup["command"].enabled)
        with instance.end_frame(single_step=True):
            pass

        spear.log("Flashlight cone angles: ", args.inner_cone_angle, " inner, ", args.outer_cone_angle, " outer")
        spear.log("Flashlight source radii: ", args.source_radius, " source, ", args.soft_source_radius, " soft source")
        spear.log("Flashlight indirect lighting intensity: ", args.indirect_lighting_intensity)
        spear.log("Initial render light setup: ", {
            "source": initial_light_setup["source"],
            "setting_name": initial_light_setup["setting_name"],
            "spawn_flashlight": initial_light_setup["spawn_flashlight"],
        })
        spear.log("Discarding warm-up captures after camera sensor setup: ", warmup_capture_count)
        discard_warmup_captures(
            instance=instance,
            game=game,
            camera_sensor=camera_sensor,
            camera_components=camera_components,
            component_descs=component_descs,
            viewport_desc=initial_viewport_desc,
            width=width,
            height=height,
            flashlight=flashlight,
            spot_light_component=spot_light_component,
            command=initial_light_setup["command"],
            disable_render_history=args.disable_render_history,
            num_captures=warmup_capture_count)

        poses = build_orbit_poses(
            start_camera_location=start_pose["camera_location"],
            target_point=orbit_spec["target_point"],
            orbit_radius=orbit_spec["orbit_radius"],
            frame_count=frame_count)

        for setting in light_settings:
            command = command_from_setting(setting=setting)
            setting_spawns_flashlight = should_spawn_flashlight_for_setting(setting=setting)
            flashlight_ever_spawned_before_setting = flashlight_ever_spawned
            flashlight_ever_enabled_before_setting = flashlight_ever_enabled
            if not setting_spawns_flashlight and flashlight_ever_spawned:
                raise RuntimeError(
                    f"Light setting {setting['name']} has spawn_flashlight=false but a render flashlight already exists. "
                    "Move no-flashlight-ever diagnostic settings before any setting that spawns the flashlight.")
            if setting_spawns_flashlight and flashlight is None:
                with instance.begin_frame():
                    flashlight, spot_light_component = spawn_flashlight(
                        game=game,
                        location=first_location,
                        rotation=first_rotation,
                        args=args,
                        command=command,
                        stable_name="Debug/OrbitCollectionRenderFlashlight")
                    flashlight_ever_spawned = True
                with instance.end_frame(single_step=True):
                    pass
            setting_dir, frame_dirs = prepare_setting_output_dir(
                output_dir=args.output_dir,
                setting_name=setting["name"],
                keep_existing_output=args.keep_existing_output)
            video_files = get_setting_video_files(setting_dir=setting_dir)
            spear.log("Rendering light setting: ", setting["name"])

            with instance.begin_frame():
                if setting_spawns_flashlight:
                    set_light_enabled(spot_light_component=spot_light_component, command=command)
            with instance.end_frame(single_step=True):
                pass
            if setting_spawns_flashlight and command.enabled:
                flashlight_ever_enabled = True

            render_diagnostics = {
                "initial_light_setup": {
                    "source": initial_light_setup["source"],
                    "setting_name": initial_light_setup["setting_name"],
                    "spawn_flashlight": initial_light_setup["spawn_flashlight"],
                    "command": light_command_to_metadata(command=initial_light_setup["command"]),
                },
                "flashlight_spawned_for_setting": setting_spawns_flashlight,
                "flashlight_ever_spawned_before_setting": flashlight_ever_spawned_before_setting,
                "flashlight_ever_enabled_before_setting": flashlight_ever_enabled_before_setting,
                "flashlight_ever_spawned_after_setting_setup": flashlight_ever_spawned,
                "flashlight_ever_enabled_after_setting_setup": flashlight_ever_enabled,
                "no_flashlight_ever_control": (
                    not setting_spawns_flashlight
                    and not flashlight_ever_spawned_before_setting
                    and not flashlight_ever_enabled_before_setting),
            }
            metadata_file = write_setting_metadata(
                setting_dir=setting_dir,
                setting=setting,
                scene_lights_enabled=scene_lights_enabled,
                scene_light_state=scene_light_state,
                disable_auto_exposure=args.disable_auto_exposure,
                disable_render_history=args.disable_render_history,
                component_descs=component_descs,
                scene_off_lighting_isolation_requested=should_apply_scene_off_lighting_isolation(args=args),
                render_diagnostics=render_diagnostics)
            spear.log("Wrote render metadata: ", metadata_file)

            spear.log("Discarding warm-up captures after light setting change: ", warmup_capture_count)
            discard_warmup_captures(
                instance=instance,
                game=game,
                camera_sensor=camera_sensor,
                camera_components=camera_components,
                component_descs=component_descs,
                viewport_desc=initial_viewport_desc,
                width=width,
                height=height,
                flashlight=flashlight,
                spot_light_component=spot_light_component,
                command=command if setting_spawns_flashlight else None,
                disable_render_history=args.disable_render_history,
                num_captures=warmup_capture_count)

            depth_frame_files = []
            finite_min_depth = None
            finite_max_depth = None
            for frame_index, (location, rotation) in enumerate(poses):
                viewport_desc = make_viewport_desc(
                    location=location,
                    rotation=rotation,
                    width=width,
                    height=height,
                    fov_degrees=fov_degrees)
                component_data = capture_orbit_frame(
                    instance=instance,
                    game=game,
                    camera_sensor=camera_sensor,
                    camera_components=camera_components,
                    component_descs=component_descs,
                    viewport_desc=viewport_desc,
                    width=width,
                    height=height,
                    flashlight=flashlight,
                    spot_light_component=spot_light_component,
                    command=command if setting_spawns_flashlight else None,
                    disable_render_history=args.disable_render_history,
                    read_pixel_data=True)

                rgb_capture_component_desc = get_rgb_capture_component_desc(component_descs=component_descs)
                rgb_frame = visualize_rgb(
                    data=component_data["rgb"],
                    capture_profile=rgb_capture_component_desc.get(
                        "capture_profile",
                        RGB_CAPTURE_PROFILE_FINAL_TONE_CURVE))
                depth = depth_to_meters(data=component_data["depth_meters"])
                finite_min_depth, finite_max_depth = update_depth_range(
                    depth=depth,
                    min_depth=finite_min_depth,
                    max_depth=finite_max_depth)
                depth_frame_file = os.path.join(frame_dirs["depth_meters_npy"], f"frame_{frame_index:04d}.npy")
                depth_frame_files.append(depth_frame_file)
                cv2.imwrite(os.path.join(frame_dirs["rgb"], f"frame_{frame_index:04d}.png"), rgb_frame)
                np.save(depth_frame_file, depth)

                if frame_index % max(int(round(fps)), 1) == 0:
                    spear.log("Rendered frame ", frame_index + 1, "/", frame_count, " for ", setting["name"])

            rgb_luma_diagnostics = compute_rgb_luma_diagnostics(
                frame_dir=frame_dirs["rgb"],
                frame_count=frame_count)
            residual_scene_off_illumination = get_residual_scene_off_illumination_diagnostics(
                render_diagnostics=render_diagnostics,
                rgb_luma_diagnostics=rgb_luma_diagnostics)
            update_setting_metadata(
                metadata_file=metadata_file,
                updates={
                    "rgb_luma_diagnostics": rgb_luma_diagnostics,
                    "residual_scene_off_illumination": residual_scene_off_illumination,
                })
            spear.log("RGB luma diagnostics for ", setting["name"], ": ", rgb_luma_diagnostics)

            min_depth, max_depth = get_depth_visualization_bounds(
                depth_frame_files=depth_frame_files,
                lower_percentile=args.depth_visualization_lower_percentile,
                upper_percentile=args.depth_visualization_upper_percentile,
                explicit_min_depth=args.depth_visualization_min_meters,
                explicit_max_depth=args.depth_visualization_max_meters,
                finite_min_depth=finite_min_depth,
                finite_max_depth=finite_max_depth,
                max_samples=args.depth_visualization_max_samples)
            spear.log(
                "Depth visualization bounds for ",
                setting["name"],
                ": ",
                min_depth,
                " to ",
                max_depth,
                " meters")
            write_depth_viridis_frames(
                depth_frame_files=depth_frame_files,
                frame_dir=frame_dirs["depth_meters_viridis"],
                min_depth=min_depth,
                max_depth=max_depth)
            spear.log("Wrote stable viridis depth frames: ", frame_dirs["depth_meters_viridis"])

            if write_video(
                    frames_dir=frame_dirs["rgb"],
                    video_file=video_files["rgb"],
                    frame_count=frame_count,
                    fps=fps):
                spear.log("Wrote RGB video: ", video_files["rgb"])
            if write_video(
                    frames_dir=frame_dirs["depth_meters_viridis"],
                    video_file=video_files["depth_meters_viridis"],
                    frame_count=frame_count,
                    fps=fps):
                spear.log("Wrote viridis depth video: ", video_files["depth_meters_viridis"])
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


def run_render(args):
    orbit_spec = read_json_file(args.orbit_spec_file)
    validate_orbit_spec(orbit_spec=orbit_spec)
    light_settings = read_json_file(args.light_settings_file)
    validate_light_settings(light_settings=light_settings)

    for scene_lights_enabled, group_settings in get_scene_light_render_groups(light_settings=light_settings):
        run_render_group(
            args=get_scene_light_group_args(args=args, scene_lights_enabled=scene_lights_enabled),
            orbit_spec=orbit_spec,
            light_settings=group_settings,
            scene_lights_enabled=scene_lights_enabled)


def main(argv=None):
    args = parse_args(argv=argv)
    if args.mode == "teleop":
        return run_teleop(args=args)
    if args.mode == "render":
        return run_render(args=args)
    raise AssertionError(f"Unhandled mode: {args.mode}")


if __name__ == "__main__":
    sys.exit(main())
