#
# Copyright (c) 2025 The SPEAR Development Team. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
# Copyright (c) 2022 Intel. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
#

import argparse
import json
import os
import select
import sys
import time

import spear


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

parser = argparse.ArgumentParser()
parser.add_argument("--map", choices=sorted(MAPS.keys()), default=None)
parser.add_argument("--map-path", default=None)
parser.add_argument("--intensity", type=float, default=30000.0)
parser.add_argument("--attenuation-radius", type=float, default=1200.0)
parser.add_argument("--inner-cone-angle", type=float, default=12.0)
parser.add_argument("--outer-cone-angle", type=float, default=30.0)
parser.add_argument("--movement-speed", type=float, default=1200.0)
parser.add_argument("--disable-scene-lights", action="store_true")
parser.add_argument("--capture-poses", action="store_true")
parser.add_argument("--capture-key", default="Gamepad_FaceButton_Top")
parser.add_argument("--pose-output-file", default=os.path.realpath(os.path.join(os.path.dirname(__file__), "camera_poses.jsonl")))
parser.add_argument("--idle-period-seconds", type=float, default=0.5)
args = parser.parse_args()


def get_viewport_pose(game):
    return game.rendering_service.get_current_viewport_desc(only_get_pose=True)


def set_light_pose(light, viewport_desc):
    return light.K2_SetActorLocationAndRotation(
        NewLocation=viewport_desc["camera_location"],
        NewRotation=viewport_desc["camera_rotation"],
        bSweep=False,
        bTeleport=True)


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


def was_input_key_just_pressed(game, player_controller, key_name):
    key = game.get_unreal_object(uclass="FKey")
    key.KeyName = key_name
    return player_controller.WasInputKeyJustPressed(Key=key)


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


if __name__ == "__main__":

    config = spear.get_config(user_config_files=[os.path.realpath(os.path.join(os.path.dirname(__file__), "user_config.yaml"))])
    config.defrost()
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.OVERRIDE_BENCHMARKING = True
    config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.BENCHMARKING = False
    if args.map is not None or args.map_path is not None:
        config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.OVERRIDE_GAME_DEFAULT_MAP = True
        config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.GAME_DEFAULT_MAP = args.map_path if args.map_path is not None else MAPS[args.map]
    config.freeze()

    spear.configure_system(config=config)
    instance = spear.Instance(config=config)
    game = instance.get_game()

    light = None

    try:
        with instance.begin_frame():
            pawn = set_camera_movement_speed(game=game, movement_speed=args.movement_speed)
            if args.disable_scene_lights:
                disabled_components = disable_scene_lights(game=game)
                spear.log("Disabled scene light components: ", disabled_components)

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
            spot_light_component.SetInnerConeAngle(NewInnerConeAngle=args.inner_cone_angle)
            spot_light_component.SetOuterConeAngle(NewOuterConeAngle=args.outer_cone_angle)

        with instance.end_frame():
            pass

        with instance.begin_frame():
            viewport_desc = get_viewport_pose(game=game)
            set_light_pose(light=light, viewport_desc=viewport_desc)
            attach_light_to_pawn(light=light, pawn=pawn)
        with instance.end_frame():
            pass

        spear.log("Spawned camera flashlight. Press Ctrl+C to stop.")
        spear.log("Camera movement speed: ", args.movement_speed)
        if args.capture_poses:
            spear.log("Pose capture enabled. Press Enter in this terminal or press the capture key on the controller to save the current camera pose.")
            spear.log("Capture key: ", args.capture_key)
            spear.log("Pose output file: ", args.pose_output_file)

        pose_index = 0
        while instance.is_running():
            time.sleep(args.idle_period_seconds)
            should_capture_pose = False
            if args.capture_poses:
                if sys.stdin in select.select([sys.stdin], [], [], 0.0)[0]:
                    sys.stdin.readline()
                    should_capture_pose = True
                else:
                    with instance.begin_frame():
                        should_capture_pose = was_input_key_just_pressed(
                            game=game,
                            player_controller=get_player_controller(game=game),
                            key_name=args.capture_key)
                    with instance.end_frame():
                        pass

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
