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
    "apartment_0000": "/Game/SPEAR/Scenes/apartment_0000/Maps/apartment_0000",
    "japanese_office_dark": "/Game/JapaneseOffice/Maps/Demonstration_Dark",
}

# Coarse floor-level goals for maps where we want a hand-authored path. The
# renderer asks Unreal's navmesh to find the collision-aware path between these
# goals, then raises the camera to human height. Other maps sample navmesh goals.
ROUTE_GOALS_BY_MAP = {
    "japanese_office_dark": [
        {"X": 0.0, "Y": -900.0, "Z": 10.0},
        {"X": 0.0, "Y": -350.0, "Z": 10.0},
        {"X": 560.0, "Y": -350.0, "Z": 10.0},
        {"X": 560.0, "Y": 120.0, "Z": 10.0},
        {"X": 650.0, "Y": 800.0, "Z": 10.0},
        {"X": 650.0, "Y": 1320.0, "Z": 10.0},
        {"X": 80.0, "Y": 1500.0, "Z": 10.0},
    ],
}


parser = argparse.ArgumentParser()
parser.add_argument("--map", choices=sorted(MAPS.keys()), default="japanese_office_dark")
parser.add_argument("--duration-seconds", type=float, default=10.0)
parser.add_argument("--fps", type=int, default=24)
parser.add_argument("--width", type=int, default=1280)
parser.add_argument("--height", type=int, default=720)
parser.add_argument("--fov-degrees", type=float, default=80.0)
parser.add_argument("--camera-height", type=float, default=165.0)
parser.add_argument("--route-mode", choices=["navmesh", "straight"], default="navmesh")
parser.add_argument("--num-route-goals", type=int, default=8)
parser.add_argument("--intensity", type=float, default=30000.0)
parser.add_argument("--attenuation-radius", type=float, default=1200.0)
parser.add_argument("--inner-cone-angle", type=float, default=12.0)
parser.add_argument("--outer-cone-angle", type=float, default=30.0)
parser.add_argument("--output-dir", default=os.path.realpath(os.path.join(os.path.dirname(__file__), "flythrough_output")))
parser.add_argument("--keep-existing-output", action="store_true")
parser.add_argument("--render-ground-truth", action="store_true")
parser.add_argument("--save-raw-ground-truth", action="store_true")
parser.add_argument("--render-flashlight-comparison", action="store_true")
parser.add_argument("--flashlight-comparison-settle-frames", type=int, default=2)
args = parser.parse_args()


GROUND_TRUTH_COMPONENT_DESCS = [
    {
        "name": "rgb",
        "long_name": "DefaultSceneRoot.final_tone_curve_hdr_",
    },
    {
        "name": "depth_meters",
        "long_name": "DefaultSceneRoot.sp_depth_meters_",
    },
    {
        "name": "world_normal",
        "long_name": "DefaultSceneRoot.world_normal_",
    },
    {
        "name": "world_position",
        "long_name": "DefaultSceneRoot.sp_world_position_",
    },
    {
        "name": "diffuse_color",
        "long_name": "DefaultSceneRoot.diffuse_color_",
    },
    {
        "name": "roughness",
        "long_name": "DefaultSceneRoot.roughness_",
    },
    {
        "name": "metallic",
        "long_name": "DefaultSceneRoot.metallic_",
    },
    {
        "name": "specular_for_lighting",
        "long_name": "DefaultSceneRoot.specular_for_lighting_",
    },
    {
        "name": "material_ao",
        "long_name": "DefaultSceneRoot.material_ao_",
    },
    {
        "name": "unlit",
        "long_name": "DefaultSceneRoot.sp_unlit_uint8_",
    },
    {
        "name": "object_ids",
        "long_name": "DefaultSceneRoot.sp_object_ids_uint8_",
    },
]


def vector_to_numpy(vector):
    return np.array([vector["X"], vector["Y"], vector["Z"]], dtype=np.float64)


def numpy_to_vector(vector):
    return {"X": float(vector[0]), "Y": float(vector[1]), "Z": float(vector[2])}


def rotation_from_direction(direction):
    direction = direction / max(np.linalg.norm(direction), 1.0e-6)
    yaw = math.degrees(math.atan2(direction[1], direction[0]))
    pitch = math.degrees(math.atan2(direction[2], math.sqrt(direction[0]*direction[0] + direction[1]*direction[1])))
    return {"Roll": 0.0, "Pitch": pitch, "Yaw": yaw}


def set_camera_height(points):
    result = np.array(points, dtype=np.float64)
    result[:, 2] = args.camera_height
    return result


def get_fixed_route_goal_points():
    route_goals = ROUTE_GOALS_BY_MAP.get(args.map)
    if route_goals is None:
        return None
    return np.array([vector_to_numpy(goal) for goal in route_goals], dtype=np.float64)


def get_sampled_route_goal_points(game, navigation_data):
    if args.num_route_goals < 2:
        raise RuntimeError("--num-route-goals must be at least 2.")
    route_goal_points = game.navigation_service.get_random_points(
        navigation_data=navigation_data,
        num_points=args.num_route_goals)
    if route_goal_points.shape[0] < 2:
        raise RuntimeError("Could not sample at least 2 navmesh route goals.")
    return route_goal_points


def get_route_goal_points(game=None, navigation_data=None):
    route_goal_points = get_fixed_route_goal_points()
    if route_goal_points is not None:
        return route_goal_points
    if game is None or navigation_data is None:
        raise RuntimeError(
            f"No fixed route goals are defined for {args.map}. Use --route-mode navmesh "
            "so the script can sample route goals from the map's navmesh.")
    return get_sampled_route_goal_points(game=game, navigation_data=navigation_data)


def get_straight_route_points():
    return set_camera_height(points=get_route_goal_points())


def get_navigation_data(game):
    navigation_data_actors = game.unreal_service.find_actors_by_class(uclass="ARecastNavMesh")
    if not navigation_data_actors:
        navigation_data_actors = game.unreal_service.find_actors_by_class(uclass="ANavigationData")
    if not navigation_data_actors:
        raise RuntimeError(
            "No navmesh actor was found in the loaded map. Rebuild nav data in the editor, "
            "or rerun with --route-mode straight to render the old non-collision-aware path.")

    spear.log("Using navigation data actor.")
    return navigation_data_actors[0]


def get_navmesh_route_points(game):
    navigation_system_v1 = game.get_unreal_object(uclass="UNavigationSystemV1")
    sp_navigation_system_v1 = game.get_unreal_object(uclass="USpNavigationSystemV1")
    navigation_system = navigation_system_v1.GetNavigationSystem()

    supports_rebuilding = navigation_system.bSupportRebuilding.get()
    navigation_system.bSupportRebuilding = True
    sp_navigation_system_v1.Build(NavigationSystem=navigation_system)
    sp_navigation_system_v1.AddNavigationBuildLock(NavigationSystem=navigation_system, Flags="Custom")
    navigation_system.bSupportRebuilding = supports_rebuilding

    navigation_data = get_navigation_data(game=game)
    route_goal_points = get_route_goal_points(game=game, navigation_data=navigation_data)
    route_points = []

    for route_index in range(route_goal_points.shape[0] - 1):
        start_point = route_goal_points[route_index].reshape(1, 3)
        end_point = route_goal_points[route_index + 1].reshape(1, 3)
        paths = game.navigation_service.find_paths(
            navigation_system=navigation_system,
            navigation_data=navigation_data,
            num_paths=1,
            start_points=start_point,
            end_points=end_point)
        assert len(paths) == 1
        path = paths[0]
        if path.shape[0] < 2:
            raise RuntimeError(f"Navmesh could not find a path for route segment {route_index}.")
        if route_points:
            path = path[1:]
        route_points.extend(path)

    route_points = set_camera_height(points=np.array(route_points, dtype=np.float64))
    if route_points.shape[0] < 2:
        raise RuntimeError("Navmesh route has fewer than 2 points.")
    return route_points


def get_route_points(game):
    if args.route_mode == "straight":
        route_points = get_straight_route_points()
    else:
        route_points = get_navmesh_route_points(game=game)

    spear.log("Route mode: ", args.route_mode)
    spear.log("Route points:")
    for point in route_points:
        spear.log_no_prefix("    ", numpy_to_vector(point))

    return route_points


def sample_route_at_alpha(route_points, alpha):
    alpha = min(max(alpha, 0.0), 1.0)
    deltas = route_points[1:] - route_points[:-1]
    lengths = np.linalg.norm(deltas, axis=1)
    total_length = float(np.sum(lengths))
    if total_length <= 1.0e-6:
        return route_points[0], route_points[-1] - route_points[0]

    target_distance = alpha*total_length
    cumulative_distance = 0.0

    for segment_index, segment_length in enumerate(lengths):
        next_cumulative_distance = cumulative_distance + segment_length
        if target_distance <= next_cumulative_distance or segment_index == len(lengths) - 1:
            local_alpha = (target_distance - cumulative_distance) / max(segment_length, 1.0e-6)
            position = route_points[segment_index]*(1.0 - local_alpha) + route_points[segment_index + 1]*local_alpha
            return position, deltas[segment_index]
        cumulative_distance = next_cumulative_distance

    return route_points[-1], route_points[-1] - route_points[-2]


def build_pose_at_alpha(route_points, alpha):
    position, segment_direction = sample_route_at_alpha(route_points=route_points, alpha=alpha)
    lookahead_position, _ = sample_route_at_alpha(route_points=route_points, alpha=min(alpha + 0.025, 1.0))

    direction = lookahead_position - position
    if np.linalg.norm(direction) < 1.0e-6:
        direction = segment_direction

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


def prepare_frame_dirs(frames_dir):
    if not args.render_ground_truth:
        frame_dirs = {"rgb": frames_dir}
        if args.render_flashlight_comparison:
            comparison_dir = os.path.join(frames_dir, "flashlight_comparison")
            frame_dirs["flashlight_comparison_off"] = os.path.join(comparison_dir, "off")
            frame_dirs["flashlight_comparison_on"] = os.path.join(comparison_dir, "on")
            frame_dirs["flashlight_comparison_side_by_side"] = os.path.join(comparison_dir, "side_by_side")
            for frame_dir in frame_dirs.values():
                os.makedirs(frame_dir, exist_ok=True)
        return frame_dirs

    frame_dirs = {
        "preview": os.path.join(frames_dir, "preview"),
        "rgb": os.path.join(frames_dir, "rgb"),
        "depth_meters": os.path.join(frames_dir, "depth_meters"),
        "world_normal": os.path.join(frames_dir, "world_normal"),
        "world_position": os.path.join(frames_dir, "world_position"),
        "diffuse_color": os.path.join(frames_dir, "diffuse_color"),
        "roughness": os.path.join(frames_dir, "roughness"),
        "metallic": os.path.join(frames_dir, "metallic"),
        "specular_for_lighting": os.path.join(frames_dir, "specular_for_lighting"),
        "material_ao": os.path.join(frames_dir, "material_ao"),
        "unlit": os.path.join(frames_dir, "unlit"),
        "object_ids": os.path.join(frames_dir, "object_ids"),
        "segmentation_ids": os.path.join(frames_dir, "segmentation_ids"),
    }
    if args.render_flashlight_comparison:
        comparison_dir = os.path.join(frames_dir, "flashlight_comparison")
        frame_dirs["flashlight_comparison_off"] = os.path.join(comparison_dir, "off")
        frame_dirs["flashlight_comparison_on"] = os.path.join(comparison_dir, "on")
        frame_dirs["flashlight_comparison_side_by_side"] = os.path.join(comparison_dir, "side_by_side")
    if args.save_raw_ground_truth:
        for name in list(frame_dirs.keys()):
            if name not in {"preview", "flashlight_comparison_off", "flashlight_comparison_on", "flashlight_comparison_side_by_side"}:
                frame_dirs[f"{name}_raw"] = os.path.join(args.output_dir, "raw", name)

    for frame_dir in frame_dirs.values():
        os.makedirs(frame_dir, exist_ok=True)
    return frame_dirs


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


def as_uint8_image(image):
    return (np.clip(image, 0.0, 1.0)*255.0).astype(np.uint8)


def visualize_rgb(data):
    if data.shape[2] == 4:
        return data[:, :, :3]
    return data


def visualize_depth(data):
    depth = data[:, :, 0] if data.ndim == 3 else data
    valid = np.isfinite(depth)
    if np.any(valid):
        min_depth = float(np.min(depth[valid]))
        span = min(float(np.max(depth[valid]) - min_depth), 7.5)
        depth_vis = np.clip((depth - min_depth) / max(span, 1.0e-6), 0.0, 1.0)
    else:
        depth_vis = np.zeros_like(depth, dtype=np.float32)
    depth_u8 = as_uint8_image(depth_vis)
    return cv2.cvtColor(depth_u8, cv2.COLOR_GRAY2BGR)


def visualize_world_normal(data):
    return as_uint8_image((data[:, :, :3] + 1.0) / 2.0)


def visualize_world_position(data):
    position = data[:, :, :3]
    valid = np.isfinite(position)
    if not np.any(valid):
        return np.zeros(position.shape, dtype=np.uint8)
    min_position = np.min(position[valid])
    max_position = np.max(position[valid])
    return as_uint8_image((position - min_position) / max(max_position - min_position, 1.0e-6))


def visualize_float_rgb(data):
    rgb = as_uint8_image(data[:, :, :3])
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def visualize_scalar(data):
    scalar = data[:, :, 0] if data.ndim == 3 else data
    scalar_u8 = as_uint8_image(scalar)
    return cv2.cvtColor(scalar_u8, cv2.COLOR_GRAY2BGR)


def visualize_object_ids(data):
    if data.shape[2] == 4:
        return data[:, :, :3]
    return data


def colors_for_ids(id_image):
    max_id = int(np.max(id_image)) if id_image.size else 0
    colors = np.zeros((max_id + 1, 3), dtype=np.uint8)
    for i in range(1, max_id + 1):
        colors[i] = np.array([(37*i) % 255, (17*i + 73) % 255, (97*i + 31) % 255], dtype=np.uint8)
    return colors[id_image]


def add_label(image, label):
    result = image.copy()
    cv2.rectangle(result, (0, 0), (220, 30), (0, 0, 0), thickness=-1)
    cv2.putText(result, label, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return result


def build_preview_tile(images):
    tile_size = (args.width // 3, args.height // 2)
    labeled = []
    for label, image in images:
        resized = cv2.resize(image, tile_size, interpolation=cv2.INTER_AREA)
        labeled.append(add_label(image=resized, label=label))
    top = np.concatenate(labeled[:3], axis=1)
    bottom = np.concatenate(labeled[3:], axis=1)
    return np.concatenate([top, bottom], axis=0)


def build_side_by_side(left_image, right_image):
    left = add_label(image=left_image, label="without flashlight")
    right = add_label(image=right_image, label="with flashlight")
    return np.concatenate([left, right], axis=1)


def save_flashlight_comparison_frame(frame_dirs, frame_index, off_data, on_data):
    off_image = visualize_rgb(data=off_data)
    on_image = visualize_rgb(data=on_data)
    side_by_side = build_side_by_side(left_image=off_image, right_image=on_image)

    off_file = os.path.join(frame_dirs["flashlight_comparison_off"], f"frame_{frame_index:04d}.png")
    on_file = os.path.join(frame_dirs["flashlight_comparison_on"], f"frame_{frame_index:04d}.png")
    side_by_side_file = os.path.join(frame_dirs["flashlight_comparison_side_by_side"], f"frame_{frame_index:04d}.png")
    cv2.imwrite(off_file, off_image)
    cv2.imwrite(on_file, on_image)
    cv2.imwrite(side_by_side_file, side_by_side)
    return side_by_side_file


def set_flashlight_enabled(spot_light_component, enabled):
    spot_light_component.SetIntensity(NewIntensity=args.intensity if enabled else 0.0)
    spot_light_component.SetVisibility(bNewVisibility=enabled, bPropagateToChildren=True)


def capture_scene(camera_components):
    for component in camera_components:
        component.CaptureScene()


def settle_render_state(instance, num_frames):
    for _ in range(num_frames):
        with instance.begin_frame():
            pass
        with instance.end_frame(single_step=True):
            pass


def save_ground_truth_frame(frame_dirs, frame_index, component_data, segmentation_id_image):
    visualizers = {
        "rgb": visualize_rgb,
        "depth_meters": visualize_depth,
        "world_normal": visualize_world_normal,
        "world_position": visualize_world_position,
        "diffuse_color": visualize_float_rgb,
        "roughness": visualize_scalar,
        "metallic": visualize_scalar,
        "specular_for_lighting": visualize_scalar,
        "material_ao": visualize_scalar,
        "unlit": visualize_rgb,
        "object_ids": visualize_object_ids,
    }

    images = {}
    for name, data in component_data.items():
        image = visualizers[name](data)
        images[name] = image
        cv2.imwrite(os.path.join(frame_dirs[name], f"frame_{frame_index:04d}.png"), image)
        if args.save_raw_ground_truth:
            np.save(os.path.join(frame_dirs[f"{name}_raw"], f"frame_{frame_index:04d}.npy"), data)

    segmentation_image = colors_for_ids(id_image=segmentation_id_image)
    images["segmentation_ids"] = segmentation_image
    cv2.imwrite(os.path.join(frame_dirs["segmentation_ids"], f"frame_{frame_index:04d}.png"), segmentation_image)
    if args.save_raw_ground_truth:
        np.save(os.path.join(frame_dirs["segmentation_ids_raw"], f"frame_{frame_index:04d}.npy"), segmentation_id_image)

    preview = build_preview_tile(images=[
        ("rgb", images["rgb"]),
        ("depth", images["depth_meters"]),
        ("normal", images["world_normal"]),
        ("diffuse", images["diffuse_color"]),
        ("unlit", images["unlit"]),
        ("segments", images["segmentation_ids"]),
    ])
    preview_file = os.path.join(frame_dirs["preview"], f"frame_{frame_index:04d}.png")
    cv2.imwrite(preview_file, preview)
    return preview_file


if __name__ == "__main__":
    frames_dir = prepare_output_dir(output_dir=args.output_dir)
    frame_dirs = prepare_frame_dirs(frames_dir=frames_dir)
    video_file = os.path.join(args.output_dir, "flashlight_flythrough.mp4")

    config = spear.get_config(user_config_files=[os.path.realpath(os.path.join(os.path.dirname(__file__), "user_config.yaml"))])
    config.defrost()
    config.SPEAR.INSTANCE.COMMAND_LINE_ARGS.resx = args.width
    config.SPEAR.INSTANCE.COMMAND_LINE_ARGS.resy = args.height
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.OVERRIDE_BENCHMARKING = True
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.BENCHMARKING = True
    render_frames_per_output_frame = 1
    if args.render_flashlight_comparison:
        render_frames_per_output_frame = 2*(args.flashlight_comparison_settle_frames + 3)
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.BENCHMARKING_MAX_NUM_FRAMES = int(args.duration_seconds*args.fps)*render_frames_per_output_frame + 8
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.OVERRIDE_GAME_DEFAULT_MAP = True
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.GAME_DEFAULT_MAP = MAPS[args.map]
    config.freeze()

    spear.configure_system(config=config)
    instance = spear.Instance(config=config)
    game = instance.get_game()

    frame_count = int(args.duration_seconds*args.fps)
    camera_sensor = None
    camera_component = None
    camera_components = []
    component_descs = GROUND_TRUTH_COMPONENT_DESCS if args.render_ground_truth else GROUND_TRUTH_COMPONENT_DESCS[:1]
    flashlight = None

    try:
        with instance.begin_frame():
            if args.render_ground_truth:
                game.segmentation_service.initialize()

            bp_camera_sensor_uclass = game.unreal_service.load_class(
                uclass="AActor",
                name="/SpContent/Blueprints/BP_CameraSensor.BP_CameraSensor_C")
            camera_sensor = game.unreal_service.spawn_actor(uclass=bp_camera_sensor_uclass)

            for component_desc in component_descs:
                component_desc["component"] = game.unreal_service.get_component_by_name(
                    actor=camera_sensor,
                    component_name=component_desc["long_name"],
                    uclass="USpSceneCaptureComponent2D")
                camera_components.append(component_desc["component"])
                if component_desc["name"] == "rgb":
                    camera_component = component_desc["component"]
            assert camera_component is not None

            route_points = get_route_points(game=game)
            location, rotation = build_pose_at_alpha(route_points=route_points, alpha=0.0)
            game.rendering_service.align_camera_with_viewport(
                camera_sensor=camera_sensor,
                camera_components=camera_components,
                viewport_desc=make_viewport_desc(location=location, rotation=rotation),
                widths=[args.width for _ in camera_components],
                heights=[args.height for _ in camera_components])

            for component in camera_components:
                component.BufferingMode = "SingleBuffered"
                component.bCaptureEveryFrame = False
                component.bCaptureOnMovement = False
                component.Initialize()
                component.initialize_sp_funcs()

            flashlight = game.unreal_service.spawn_actor(uclass="ASpotLight", location=location, rotation=rotation)
            game.unreal_service.set_stable_name_for_actor(actor=flashlight, stable_name="Debug/ProgrammaticCameraFlashlight")
            flashlight.K2_GetRootComponent().SetMobility(NewMobility="Movable")
            spot_light_component = game.unreal_service.get_component_by_class(actor=flashlight, uclass="USpotLightComponent")
            spot_light_component.SetIntensity(NewIntensity=args.intensity)
            spot_light_component.SetAttenuationRadius(NewRadius=args.attenuation_radius)
            spot_light_component.SetInnerConeAngle(NewInnerConeAngle=args.inner_cone_angle)
            spot_light_component.SetOuterConeAngle(NewOuterConeAngle=args.outer_cone_angle)
            set_flashlight_enabled(spot_light_component=spot_light_component, enabled=True)

        with instance.end_frame(single_step=True):
            pass

        instance.step(num_frames=2)
        if args.render_ground_truth:
            game.async_loading_service.wait_for_engine_idle()

        for frame_index in range(frame_count):
            alpha = frame_index / max(frame_count - 1, 1)
            location, rotation = build_pose_at_alpha(route_points=route_points, alpha=alpha)
            comparison_frame_file = None
            flashlight_off_data = None

            if args.render_flashlight_comparison:
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
                    set_flashlight_enabled(spot_light_component=spot_light_component, enabled=False)
                with instance.end_frame(single_step=True):
                    pass

                settle_render_state(instance=instance, num_frames=args.flashlight_comparison_settle_frames)

                with instance.begin_frame():
                    pass
                with instance.end_frame(single_step=True):
                    pass

                with instance.begin_frame():
                    capture_scene(camera_components=[camera_component])
                with instance.end_frame(single_step=True):
                    data_bundle = camera_component.read_pixels()
                    flashlight_off_data = data_bundle["arrays"]["data"].copy()

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
                    set_flashlight_enabled(spot_light_component=spot_light_component, enabled=True)
                with instance.end_frame(single_step=True):
                    pass

                settle_render_state(instance=instance, num_frames=args.flashlight_comparison_settle_frames)

                with instance.begin_frame():
                    pass
                with instance.end_frame(single_step=True):
                    pass

                with instance.begin_frame():
                    capture_scene(camera_components=camera_components)
                with instance.end_frame(single_step=True):
                    component_data = {}
                    for component_desc in component_descs:
                        data_bundle = component_desc["component"].read_pixels()
                        component_data[component_desc["name"]] = data_bundle["arrays"]["data"].copy()
                    if args.render_ground_truth:
                        segmentation_id_image, _ = game.segmentation_service.get_segmentation_data(
                            object_ids_bgra_uint8_image=component_data["object_ids"])
            else:
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
                    set_flashlight_enabled(spot_light_component=spot_light_component, enabled=True)
                    capture_scene(camera_components=camera_components)
                with instance.end_frame(single_step=True):
                    component_data = {}
                    for component_desc in component_descs:
                        data_bundle = component_desc["component"].read_pixels()
                        component_data[component_desc["name"]] = data_bundle["arrays"]["data"].copy()
                    if args.render_ground_truth:
                        segmentation_id_image, _ = game.segmentation_service.get_segmentation_data(
                            object_ids_bgra_uint8_image=component_data["object_ids"])

            if args.render_flashlight_comparison:
                comparison_frame_file = save_flashlight_comparison_frame(
                    frame_dirs=frame_dirs,
                    frame_index=frame_index,
                    off_data=flashlight_off_data,
                    on_data=component_data["rgb"])

            if args.render_ground_truth:
                frame_file = save_ground_truth_frame(
                    frame_dirs=frame_dirs,
                    frame_index=frame_index,
                    component_data=component_data,
                    segmentation_id_image=segmentation_id_image)
            else:
                frame = visualize_rgb(data=component_data["rgb"])
                frame_file = os.path.join(frame_dirs["rgb"], f"frame_{frame_index:04d}.png")
                cv2.imwrite(frame_file, frame)
            if comparison_frame_file is not None:
                frame_file = comparison_frame_file

            if frame_index % args.fps == 0:
                spear.log(f"Rendered frame {frame_index + 1}/{frame_count}: {frame_file}")

        video_frames_dir = frame_dirs["preview"] if args.render_ground_truth else frame_dirs["rgb"]
        wrote_video = write_video(frames_dir=video_frames_dir, video_file=video_file, frame_count=frame_count)
        if wrote_video:
            spear.log("Wrote video: ", video_file)
        if args.render_flashlight_comparison:
            comparison_video_file = os.path.join(args.output_dir, "flashlight_comparison.mp4")
            wrote_comparison_video = write_video(
                frames_dir=frame_dirs["flashlight_comparison_side_by_side"],
                video_file=comparison_video_file,
                frame_count=frame_count)
            if wrote_comparison_video:
                spear.log("Wrote flashlight comparison video: ", comparison_video_file)
        spear.log("Wrote frames: ", frames_dir)

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
                if args.render_ground_truth:
                    game.segmentation_service.terminate()
            instance.step()

        instance.close()

    spear.log("Done.")
