#
# Copyright (c) 2025 The SPEAR Development Team. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
# Copyright (c) 2022 Intel. Licensed under the MIT License <http://opensource.org/licenses/MIT>.
#

import argparse
import os
import time

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

parser = argparse.ArgumentParser()
parser.add_argument("--map", choices=sorted(MAPS.keys()), default=None)
parser.add_argument("--map-path", default=None)
parser.add_argument("--intensity", type=float, default=30000.0)
parser.add_argument("--attenuation-radius", type=float, default=1200.0)
parser.add_argument("--inner-cone-angle", type=float, default=12.0)
parser.add_argument("--outer-cone-angle", type=float, default=30.0)
parser.add_argument("--movement-speed", type=float, default=60000.0)
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

        while instance.is_running():
            time.sleep(args.idle_period_seconds)

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
