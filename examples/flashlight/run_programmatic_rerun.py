#
# Copyright (c) 2025 The SPEAR Development Team. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
# Copyright (c) 2022 Intel. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
#

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
import sys
import time

import numpy as np
import spear


MAPS = {
    "apartment_0000": "/Game/SPEAR/Scenes/apartment_0000/Maps/apartment_0000",
    "debug_0000": "/Game/SPEAR/Scenes/debug_0000/Maps/debug_0000",
    "debug_0001": "/Game/SPEAR/Scenes/debug_0001/Maps/debug_0001",
    "advanced_lighting": "/Game/StarterContent/Maps/Advanced_Lighting",
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

UNREAL_CENTIMETERS_TO_RERUN_METERS = 0.01
UNREAL_TO_RERUN_WORLD_MATRIX = np.array([
    [0.0, 1.0, 0.0],
    [1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0],
], dtype=np.float64)
RERUN_IMAGE_PATHS = {
    "rgb": "rgb",
    "depth_meters": "depth_meters",
    "depth_meters_visualization": "depth_meters_visualization",
    "camera_position_plot": "camera_position_plot",
}


@dataclass
class LightCommand:
    enabled: bool = True
    intensity: float = 30000.0
    yaw_offset_degrees: float = 0.0
    pitch_offset_degrees: float = 0.0


def compute_light_command(elapsed_seconds, frame_index, viewport_desc, previous_command):
    del elapsed_seconds, frame_index, viewport_desc

    # Edit this hook to drive the flashlight from Python. By default it keeps
    # the previous command, which is initialized from the CLI light defaults.
    if previous_command is None:
        return LightCommand()
    return previous_command


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", choices=sorted(MAPS.keys()), default=None)
    parser.add_argument("--map-path", default=None)
    parser.add_argument("--movement-speed", type=float, default=1200.0)
    parser.add_argument("--disable-scene-lights", action="store_true")
    parser.add_argument("--intensity", type=float, default=30000.0)
    parser.add_argument("--attenuation-radius", type=float, default=1200.0)
    parser.add_argument("--inner-cone-angle", type=float, default=12.0)
    parser.add_argument("--outer-cone-angle", type=float, default=30.0)
    parser.add_argument("--initial-light-disabled", action="store_true")
    parser.add_argument("--light-yaw-offset-degrees", type=float, default=0.0)
    parser.add_argument("--light-pitch-offset-degrees", type=float, default=0.0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--capture-fps", type=float, default=12.0)
    parser.add_argument("--rerun-app-id", default="spear_flashlight_rgb_depth")
    parser.add_argument("--no-rerun-spawn", action="store_true")
    args = parser.parse_args()

    if args.map is not None and args.map_path is not None:
        parser.error("--map and --map-path are mutually exclusive")
    if args.width <= 0:
        parser.error("--width must be positive")
    if args.height <= 0:
        parser.error("--height must be positive")
    if args.capture_fps <= 0.0:
        parser.error("--capture-fps must be positive")
    if args.attenuation_radius <= 0.0:
        parser.error("--attenuation-radius must be positive")
    if args.inner_cone_angle < 0.0:
        parser.error("--inner-cone-angle must be non-negative")
    if args.outer_cone_angle < args.inner_cone_angle:
        parser.error("--outer-cone-angle must be greater than or equal to --inner-cone-angle")

    return args


def import_rerun():
    try:
        import rerun as rr
    except ImportError:
        raise SystemExit(
            "The Rerun Python SDK is required for this example.\n"
            "Install it with: python -m pip install rerun-sdk==0.32.2\n"
            "Or install SPEAR's examples extras after this change is available: python -m pip install -e 'python[examples]'"
        ) from None
    return rr


def get_plain_dict(value):
    return json.loads(json.dumps(value))


def get_case_insensitive_value(desc, key_name):
    key_by_lower = {key.lower(): key for key in desc.keys()}
    return desc[key_by_lower[key_name.lower()]]


def get_location_xyz(location):
    return np.array([
        float(get_case_insensitive_value(desc=location, key_name="X")),
        float(get_case_insensitive_value(desc=location, key_name="Y")),
        float(get_case_insensitive_value(desc=location, key_name="Z")),
    ], dtype=np.float64)


def unreal_vector_to_rerun_world(vector):
    return UNREAL_TO_RERUN_WORLD_MATRIX @ np.asarray(vector, dtype=np.float64)


def unreal_location_to_rerun_world(location):
    return unreal_vector_to_rerun_world(vector=get_location_xyz(location=location)) * UNREAL_CENTIMETERS_TO_RERUN_METERS


def unreal_location_to_game_world_meters(location):
    return get_location_xyz(location=location) * UNREAL_CENTIMETERS_TO_RERUN_METERS


def build_light_rotation(camera_rotation, command):
    light_rotation = get_plain_dict(camera_rotation)
    key_by_lower = {key.lower(): key for key in light_rotation.keys()}
    light_rotation[key_by_lower["yaw"]] += command.yaw_offset_degrees
    light_rotation[key_by_lower["pitch"]] += command.pitch_offset_degrees
    return light_rotation


def to_rerun_final_tone_curve_rgb_image(data):
    image = np.asarray(data)
    if image.ndim == 3 and image.shape[2] >= 3:
        image = image[:, :, [2, 1, 0]]

    if np.issubdtype(image.dtype, np.floating):
        return np.clip(image, 0.0, 1.0).astype(np.float32)

    return image.astype(np.uint8, copy=False)


def to_rerun_depth_image(data):
    depth = data[:, :, 0] if data.ndim == 3 else data
    return np.asarray(depth, dtype=np.float32)


def to_rerun_depth_visualization(data):
    depth = to_rerun_depth_image(data=data)
    valid = np.isfinite(depth)
    depth_visualization = np.zeros(depth.shape, dtype=np.float32)
    if np.any(valid):
        min_depth = float(np.min(depth[valid]))
        span = float(np.max(depth[valid]) - min_depth)
        depth_visualization = np.clip((depth - min_depth) / max(span, 1.0e-6), 0.0, 1.0)
    depth_u8 = (depth_visualization*255.0).astype(np.uint8)
    return np.repeat(depth_u8[:, :, np.newaxis], 3, axis=2)


def render_camera_position_plot(camera_positions_meters):
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except ImportError:
        raise SystemExit(
            "matplotlib is required for the camera position plot.\n"
            "Install SPEAR's Python dependencies with: python -m pip install -e 'python[examples]'"
        ) from None

    positions = np.asarray(camera_positions_meters, dtype=np.float64)
    xy = positions[:, :2]
    current = xy[-1]

    figure = Figure(figsize=(5.0, 5.0), dpi=120)
    canvas = FigureCanvasAgg(figure)
    axis = figure.add_subplot(1, 1, 1)

    axis.plot(xy[:, 0], xy[:, 1], color="#1f77b4", linewidth=2.0)
    axis.scatter([current[0]], [current[1]], color="#d62728", s=45, zorder=3)
    axis.set_title("Camera position in game world")
    axis.set_xlabel("Unreal X (m)")
    axis.set_ylabel("Unreal Y (m)")
    axis.grid(True, color="#d0d0d0", linewidth=0.8)
    axis.set_aspect("equal", adjustable="box")

    min_xy = np.min(xy, axis=0)
    max_xy = np.max(xy, axis=0)
    center = (min_xy + max_xy) / 2.0
    span = np.maximum(max_xy - min_xy, 1.0)
    padding = max(float(np.max(span)) * 0.15, 1.0)
    half_extent = max(float(np.max(span)) / 2.0 + padding, 1.0)
    axis.set_xlim(center[0] - half_extent, center[0] + half_extent)
    axis.set_ylim(center[1] - half_extent, center[1] + half_extent)

    figure.tight_layout()
    canvas.draw()
    rgba = np.asarray(canvas.buffer_rgba())
    return np.ascontiguousarray(rgba[:, :, :3])


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


def capture_scene(camera_components):
    for component in camera_components:
        component.CaptureScene()


def build_rerun_blueprint():
    import rerun.blueprint as rrb

    return rrb.Blueprint(
        rrb.Horizontal(
            rrb.Vertical(
                rrb.Spatial2DView(
                    name="RGB",
                    origin=RERUN_IMAGE_PATHS["rgb"],
                    contents=RERUN_IMAGE_PATHS["rgb"]),
                rrb.Spatial2DView(
                    name="Depth visualization",
                    origin=RERUN_IMAGE_PATHS["depth_meters_visualization"],
                    contents=RERUN_IMAGE_PATHS["depth_meters_visualization"]),
                rrb.Spatial2DView(
                    name="Camera position plot",
                    origin=RERUN_IMAGE_PATHS["camera_position_plot"],
                    contents=RERUN_IMAGE_PATHS["camera_position_plot"]),
            ),
            rrb.Vertical(
                rrb.Spatial2DView(
                    name="Depth meters",
                    origin=RERUN_IMAGE_PATHS["depth_meters"],
                    contents=RERUN_IMAGE_PATHS["depth_meters"]),
                rrb.TimeSeriesView(
                    name="Camera position",
                    origin="status/camera",
                    contents=[
                        "status/camera/world_x_meters",
                        "status/camera/world_y_meters",
                        "status/camera/world_z_meters",
                    ]),
                rrb.TimeSeriesView(
                    name="Light command",
                    origin="status/light",
                    contents=[
                        "status/light/intensity",
                        "status/light/enabled",
                        "status/light/yaw_offset_degrees",
                        "status/light/pitch_offset_degrees",
                    ]),
                rrb.TextDocumentView(
                    name="Camera status",
                    origin="status/camera/status",
                    contents="status/camera/status"),
                rrb.TextDocumentView(
                    name="Light status",
                    origin="status/light/status",
                    contents="status/light/status"),
            ),
            column_shares=[2.0, 1.0],
        ),
        rrb.SelectionPanel(state="collapsed"),
        rrb.BlueprintPanel(state="collapsed"),
        rrb.TimePanel(state="expanded", timeline="frame"),
        auto_layout=False,
        auto_views=False,
        collapse_panels=True,
    )


def configure_rerun(rr, args):
    blueprint = build_rerun_blueprint()
    rr.init(args.rerun_app_id, spawn=not args.no_rerun_spawn, default_blueprint=blueprint)
    rr.send_blueprint(blueprint, make_active=True, make_default=True)


def log_rerun_frame(rr, frame_index, elapsed_seconds, viewport_desc, command, component_data, camera_positions_meters):
    rr.set_time("frame", sequence=frame_index)
    rr.set_time("elapsed", duration=elapsed_seconds)

    location = unreal_location_to_rerun_world(location=viewport_desc["camera_location"])
    camera_positions_meters.append(unreal_location_to_game_world_meters(location=viewport_desc["camera_location"]))

    rgb_image = to_rerun_final_tone_curve_rgb_image(data=component_data["rgb"])
    rr.log(RERUN_IMAGE_PATHS["rgb"], rr.Image(rgb_image, color_model="RGB"))
    rr.log(RERUN_IMAGE_PATHS["depth_meters"], rr.DepthImage(to_rerun_depth_image(data=component_data["depth_meters"]), meter=1.0))
    rr.log(RERUN_IMAGE_PATHS["depth_meters_visualization"], rr.Image(to_rerun_depth_visualization(data=component_data["depth_meters"]), color_model="RGB"))
    rr.log(RERUN_IMAGE_PATHS["camera_position_plot"], rr.Image(render_camera_position_plot(camera_positions_meters), color_model="RGB"))

    rr.log("status/camera/world_x_meters", rr.Scalars(float(location[0])))
    rr.log("status/camera/world_y_meters", rr.Scalars(float(location[1])))
    rr.log("status/camera/world_z_meters", rr.Scalars(float(location[2])))
    rr.log(
        "status/camera/status",
        rr.TextDocument(
            f"world_m=({location[0]:.3f},{location[1]:.3f},{location[2]:.3f})\n"
            f"pitch_degrees={get_case_insensitive_value(desc=viewport_desc['camera_rotation'], key_name='Pitch'):.3f}\n"
            f"yaw_degrees={get_case_insensitive_value(desc=viewport_desc['camera_rotation'], key_name='Yaw'):.3f}\n"
            f"roll_degrees={get_case_insensitive_value(desc=viewport_desc['camera_rotation'], key_name='Roll'):.3f}"))
    rr.log("status/light/intensity", rr.Scalars(command.intensity))
    rr.log("status/light/enabled", rr.Scalars(1.0 if command.enabled else 0.0))
    rr.log("status/light/yaw_offset_degrees", rr.Scalars(command.yaw_offset_degrees))
    rr.log("status/light/pitch_offset_degrees", rr.Scalars(command.pitch_offset_degrees))
    rr.log(
        "status/light/status",
        rr.TextDocument(
            f"enabled={command.enabled}\n"
            f"intensity={command.intensity:.3f}\n"
            f"yaw_offset_degrees={command.yaw_offset_degrees:.3f}\n"
            f"pitch_offset_degrees={command.pitch_offset_degrees:.3f}"))


def print_status(frame_index, viewport_desc, command):
    location = viewport_desc["camera_location"]
    rotation = viewport_desc["camera_rotation"]
    loc = unreal_location_to_rerun_world(location=location)
    rot = (
        get_case_insensitive_value(desc=rotation, key_name="Pitch"),
        get_case_insensitive_value(desc=rotation, key_name="Yaw"),
        get_case_insensitive_value(desc=rotation, key_name="Roll"),
    )
    print(
        f"frame={frame_index:06d} "
        f"world_m=({loc[0]:.2f},{loc[1]:.2f},{loc[2]:.2f}) "
        f"rot=({rot[0]:.2f},{rot[1]:.2f},{rot[2]:.2f}) "
        f"light={'on' if command.enabled else 'off'} "
        f"intensity={command.intensity:.1f} "
        f"yaw={command.yaw_offset_degrees:+.2f} "
        f"pitch={command.pitch_offset_degrees:+.2f}",
        flush=True)


def build_config(args):
    config = spear.get_config(user_config_files=[os.path.realpath(os.path.join(os.path.dirname(__file__), "user_config.yaml"))])
    config.defrost()
    config.SPEAR.INSTANCE.COMMAND_LINE_ARGS.resx = args.width
    config.SPEAR.INSTANCE.COMMAND_LINE_ARGS.resy = args.height
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.OVERRIDE_BENCHMARKING = True
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.BENCHMARKING = False
    if args.map is not None or args.map_path is not None:
        config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.OVERRIDE_GAME_DEFAULT_MAP = True
        config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.GAME_DEFAULT_MAP = args.map_path if args.map_path is not None else MAPS[args.map]
    config.freeze()
    return config


def run():
    args = parse_args()
    rr = import_rerun()
    configure_rerun(rr=rr, args=args)

    config = build_config(args=args)
    spear.configure_system(config=config)
    instance = spear.Instance(config=config)
    game = instance.get_game()

    camera_sensor = None
    camera_components = []
    component_descs = [dict(component_desc) for component_desc in CAPTURE_COMPONENT_DESCS]
    light = None
    previous_command = LightCommand(
        enabled=not args.initial_light_disabled,
        intensity=args.intensity,
        yaw_offset_degrees=args.light_yaw_offset_degrees,
        pitch_offset_degrees=args.light_pitch_offset_degrees)
    camera_positions_meters = []

    try:
        with instance.begin_frame():
            set_camera_movement_speed(game=game, movement_speed=args.movement_speed)
            if args.disable_scene_lights:
                disabled_components = disable_scene_lights(game=game)
                spear.log("Disabled scene light components: ", disabled_components)

            bp_camera_sensor_uclass = game.unreal_service.load_class(
                uclass="AActor",
                name="/SpContent/Blueprints/BP_CameraSensor.BP_CameraSensor_C")
            camera_sensor = game.unreal_service.spawn_actor(uclass=bp_camera_sensor_uclass)
            game.unreal_service.set_stable_name_for_actor(actor=camera_sensor, stable_name="Debug/ProgrammaticRerunCameraSensor")

            for component_desc in component_descs:
                component = game.unreal_service.get_component_by_name(
                    actor=camera_sensor,
                    component_name=component_desc["long_name"],
                    uclass="USpSceneCaptureComponent2D")
                component_desc["component"] = component
                camera_components.append(component)

            viewport_desc = game.rendering_service.get_current_viewport_desc()
            game.rendering_service.align_camera_with_viewport(
                camera_sensor=camera_sensor,
                camera_components=camera_components,
                viewport_desc=viewport_desc,
                widths=[args.width for _ in camera_components],
                heights=[args.height for _ in camera_components])

            for component in camera_components:
                component.BufferingMode = "SingleBuffered"
                component.bCaptureEveryFrame = False
                component.bCaptureOnMovement = False
                component.Initialize()
                component.initialize_sp_funcs()

            light = game.unreal_service.spawn_actor(
                uclass="ASpotLight",
                location=viewport_desc["camera_location"],
                rotation=build_light_rotation(camera_rotation=viewport_desc["camera_rotation"], command=previous_command))
            game.unreal_service.set_stable_name_for_actor(actor=light, stable_name="Debug/ProgrammaticRerunFlashlight")
            light.K2_GetRootComponent().SetMobility(NewMobility="Movable")
            spot_light_component = game.unreal_service.get_component_by_class(actor=light, uclass="USpotLightComponent")
            spot_light_component.SetAttenuationRadius(NewRadius=args.attenuation_radius)
            spot_light_component.SetInnerConeAngle(NewInnerConeAngle=args.inner_cone_angle)
            spot_light_component.SetOuterConeAngle(NewOuterConeAngle=args.outer_cone_angle)
            set_light_enabled(spot_light_component=spot_light_component, command=previous_command)

        with instance.end_frame():
            pass

        instance.step(num_frames=2)

        spear.log("Streaming live viewport-aligned flashlight captures to Rerun. Press Ctrl+C to stop.")
        spear.log("Capture size: ", args.width, "x", args.height, " at ", args.capture_fps, " fps")
        spear.log("Camera movement speed: ", args.movement_speed)

        frame_index = 0
        start_time = time.monotonic()
        next_capture_time = start_time
        capture_period = 1.0 / args.capture_fps

        while instance.is_running():
            now = time.monotonic()
            if now < next_capture_time:
                time.sleep(min(next_capture_time - now, capture_period))
                continue

            elapsed_seconds = now - start_time
            component_data = {}
            viewport_desc = None
            command = None

            with instance.begin_frame():
                viewport_desc = game.rendering_service.get_current_viewport_desc()
                command = compute_light_command(
                    elapsed_seconds=elapsed_seconds,
                    frame_index=frame_index,
                    viewport_desc=viewport_desc,
                    previous_command=previous_command)
                if command is None:
                    command = previous_command
                if command is None:
                    command = LightCommand()

                game.rendering_service.align_camera_with_viewport(
                    camera_sensor=camera_sensor,
                    camera_components=camera_components,
                    viewport_desc=viewport_desc,
                    widths=[args.width for _ in camera_components],
                    heights=[args.height for _ in camera_components])
                light.K2_SetActorLocationAndRotation(
                    NewLocation=viewport_desc["camera_location"],
                    NewRotation=build_light_rotation(camera_rotation=viewport_desc["camera_rotation"], command=command),
                    bSweep=False,
                    bTeleport=True)
                set_light_enabled(spot_light_component=spot_light_component, command=command)
                capture_scene(camera_components=camera_components)

            with instance.end_frame():
                for component_desc in component_descs:
                    data_bundle = component_desc["component"].read_pixels()
                    component_data[component_desc["name"]] = data_bundle["arrays"]["data"].copy()

            log_rerun_frame(
                rr=rr,
                frame_index=frame_index,
                elapsed_seconds=elapsed_seconds,
                viewport_desc=viewport_desc,
                command=command,
                component_data=component_data,
                camera_positions_meters=camera_positions_meters)
            print_status(frame_index=frame_index, viewport_desc=viewport_desc, command=command)

            previous_command = command
            frame_index += 1
            next_capture_time += capture_period
            if next_capture_time < time.monotonic() - capture_period:
                next_capture_time = time.monotonic()

    except KeyboardInterrupt:
        spear.log("Stopping programmatic Rerun flashlight stream.")

    finally:
        if instance.is_running():
            with instance.begin_frame():
                pass
            with instance.end_frame():
                for component in camera_components:
                    component.terminate_sp_funcs()
                    component.Terminate()
                if camera_sensor is not None:
                    game.unreal_service.destroy_actor(actor=camera_sensor)
                if light is not None:
                    game.unreal_service.destroy_actor(actor=light)

        instance.close()
        rr.disconnect()
        spear.log("Done.")


if __name__ == "__main__":
    sys.exit(run())
