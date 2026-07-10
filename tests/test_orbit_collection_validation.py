import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np


ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT_DIR, "python"))

MODULE_FILE = os.path.join(ROOT_DIR, "examples", "flashlight", "run_orbit_collection.py")
WORKFLOW_FILE = os.path.join(ROOT_DIR, "examples", "flashlight", "run_orbit_workflow.sh")
SPEC = importlib.util.spec_from_file_location("run_orbit_collection", MODULE_FILE)
orbit_collection = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = orbit_collection
SPEC.loader.exec_module(orbit_collection)

RUN_MODULE_FILE = os.path.join(ROOT_DIR, "examples", "flashlight", "run.py")
RUN_SPEC = importlib.util.spec_from_file_location("flashlight_run", RUN_MODULE_FILE)
flashlight_run = importlib.util.module_from_spec(RUN_SPEC)
sys.modules[RUN_SPEC.name] = flashlight_run
RUN_SPEC.loader.exec_module(flashlight_run)


def make_orbit_spec():
    return {
        "schema_version": "1.0.0",
        "map": "japanese_office_dark",
        "map_path": None,
        "start_camera_pose": {
            "camera_location": {"X": 0.0, "Y": 0.0, "Z": 100.0},
            "camera_rotation": {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0},
        },
        "target_point": {"X": 100.0, "Y": 0.0, "Z": 100.0},
        "target_was_fallback": False,
        "orbit_radius": 100.0,
        "orbit_duration_seconds": 1.0,
        "fps": 24.0,
        "image_size": {"width": 320, "height": 240},
        "fov_degrees": 80.0,
        "light_baseline_settings": {
            "name": "baseline",
            "enabled": True,
            "intensity": 30000.0,
            "yaw_offset_degrees": 0.0,
            "pitch_offset_degrees": 0.0,
        },
    }


def make_light_settings(name="baseline_on", intensity=30000.0):
    return [{
        "name": name,
        "enabled": True,
        "intensity": intensity,
        "yaw_offset_degrees": 0.0,
        "pitch_offset_degrees": 0.0,
    }]


class FakeCaptureComponent:
    def __init__(self):
        self.bCameraCutThisFrame = False
        self.bAlwaysPersistRenderingState = True
        self.PostProcessSettings = {
            "override_dynamic_global_illumination_method": True,
            "override_reflection_method": True,
        }
        self.ShowFlagSettings = []
        self.ShowFlags = FakeShowFlags()
        self.capture_count = 0
        self.camera_cut_values_at_capture = []
        self.initialize_count = 0
        self.initialize_sp_funcs_count = 0

    def CaptureScene(self):
        self.capture_count += 1
        self.camera_cut_values_at_capture.append(self.bCameraCutThisFrame)

    def read_pixels(self):
        return {
            "arrays": {
                "data": np.array([[self.capture_count]], dtype=np.float32),
            },
        }

    def Initialize(self):
        self.initialize_count += 1
        self.bAlwaysPersistRenderingState = True
        self.PostProcessSettings["override_dynamic_global_illumination_method"] = True
        self.PostProcessSettings["override_reflection_method"] = True

    def initialize_sp_funcs(self):
        self.initialize_sp_funcs_count += 1


class FakeShowFlags:
    def __init__(self):
        self.values = {}

    def __getattr__(self, name):
        if not name.startswith("Set"):
            raise AttributeError(name)

        def setter(value):
            self.values[name[3:]] = value

        return setter


class FakeLightComponent:
    def __init__(self, supports_indirect=True):
        self.visible = True
        self.intensity = 100.0
        self.indirect_lighting_intensity = 1.0
        self.source_radius = None
        self.soft_source_radius = None
        self.cast_shadows = None
        self.cast_dynamic_shadows = None
        self.contact_shadows = None
        self.contact_shadow_length = None
        self.use_inverse_squared_falloff = None
        self.cast_raytraced_shadow = None
        self.supports_indirect = supports_indirect

    def SetVisibility(self, bNewVisibility, bPropagateToChildren):
        self.visible = bNewVisibility

    def SetIntensity(self, NewIntensity):
        self.intensity = NewIntensity

    def SetIndirectLightingIntensity(self, NewIntensity):
        if not self.supports_indirect:
            raise AttributeError("No indirect lighting intensity")
        self.indirect_lighting_intensity = NewIntensity

    def SetSourceRadius(self, bNewValue):
        self.source_radius = bNewValue

    def SetSoftSourceRadius(self, bNewValue):
        self.soft_source_radius = bNewValue

    def SetCastShadows(self, bNewValue):
        self.cast_shadows = bNewValue

    def SetCastDynamicShadows(self, bNewValue):
        self.cast_dynamic_shadows = bNewValue

    def SetUseContactShadow(self, bNewValue):
        self.contact_shadows = bNewValue

    def SetContactShadowLength(self, bNewValue):
        self.contact_shadow_length = bNewValue

    def SetUseInverseSquaredFalloff(self, bNewValue):
        self.use_inverse_squared_falloff = bNewValue

    def SetCastRaytracedShadow(self, bNewValue):
        self.cast_raytraced_shadow = bNewValue


class FakeReflectedSourceRadiusLightComponent:
    def __init__(self):
        self.source_radius = None
        self.soft_source_radius = None
        self.source_radius_args = []
        self.soft_source_radius_args = []

    def SetSourceRadius(self, **kwargs):
        self.source_radius_args.append(kwargs)
        if set(kwargs.keys()) != {"bNewValue"}:
            raise RuntimeError("SetSourceRadius called with non-reflected argument names")
        self.source_radius = kwargs["bNewValue"]

    def SetSoftSourceRadius(self, **kwargs):
        self.soft_source_radius_args.append(kwargs)
        if set(kwargs.keys()) != {"bNewValue"}:
            raise RuntimeError("SetSoftSourceRadius called with non-reflected argument names")
        self.soft_source_radius = kwargs["bNewValue"]


class FakeEditorPropertyLightComponent:
    __slots__ = ("properties",)

    def __init__(self):
        self.properties = {}

    def set_editor_property(self, name, value):
        if name not in {"SourceRadius", "SoftSourceRadius", "UseInverseSquaredFalloff", "CastRaytracedShadow"}:
            raise AttributeError(name)
        self.properties[name] = value

    def get_editor_property(self, name):
        if name not in self.properties:
            raise AttributeError(name)
        return self.properties[name]


class FakeEnumRayTracedMethodLightComponent:
    def __init__(self):
        self.CastRaytracedShadows = None
        self.values = []

    def SetCastRaytracedShadows(self, bNewValue):
        self.values.append(bNewValue)
        self.CastRaytracedShadows = 1 if bNewValue is True else bNewValue


class FakeEnumRayTracedPropertyLightComponent:
    def __init__(self):
        self.properties = {}
        self.values = []

    def set_editor_property(self, name, value):
        if name != "CastRaytracedShadows":
            raise AttributeError(name)
        self.values.append(value)
        self.properties[name] = 1 if value is True else value

    def get_editor_property(self, name):
        if name not in self.properties:
            raise AttributeError(name)
        return self.properties[name]


class FakeStringRejectingRayTracedMethodLightComponent:
    def __init__(self):
        self.cast_raytraced_shadow = None
        self.values = []

    def SetCastRaytracedShadow(self, bNewValue):
        self.values.append(bNewValue)
        if isinstance(bNewValue, str):
            raise AssertionError("string ray-traced shadow values should not be attempted")
        self.cast_raytraced_shadow = bNewValue


class FakeMissingShapeLightComponent:
    __slots__ = ()


class FakeDynamicMissingShapeLightComponent:
    pass


class FakeEnvironmentComponent:
    def __init__(self):
        self.visible = True
        self.Intensity = 3.0

    def SetVisibility(self, bNewVisibility, bPropagateToChildren):
        self.visible = bNewVisibility


class FakeEditorPropertyCaptureComponent(FakeCaptureComponent):
    def __init__(self, persist_property_name):
        super().__init__()
        self.persist_property_name = persist_property_name
        del self.bAlwaysPersistRenderingState
        self.properties = {
            persist_property_name: True,
            "post_process_settings": self.PostProcessSettings,
        }

    def set_editor_property(self, name, value):
        if name not in self.properties:
            raise AttributeError(name)
        self.properties[name] = value

    def get_editor_property(self, name):
        if name not in self.properties:
            raise AttributeError(name)
        return self.properties[name]


class FakeUnrealService:
    def __init__(self, components_by_actor, components_by_name=None, cvar_values=None):
        self.components_by_actor = components_by_actor
        self.components_by_name = components_by_name or {}
        self.cvar_values = cvar_values or {}
        self.component_name_requests = []

    def find_actors(self):
        return list(self.components_by_actor.keys())

    def get_components_by_class(self, actor, uclass, include_from_child_actors):
        self.request = {
            "uclass": uclass,
            "include_from_child_actors": include_from_child_actors,
        }
        actor_components = self.components_by_actor[actor]
        if isinstance(actor_components, dict):
            return actor_components.get(uclass, [])
        return actor_components

    def load_class(self, uclass, name):
        self.loaded_class = {
            "uclass": uclass,
            "name": name,
        }
        return name

    def spawn_actor(self, uclass):
        self.spawned_actor = {
            "uclass": uclass,
        }
        return "camera_sensor"

    def set_stable_name_for_actor(self, actor, stable_name):
        self.stable_name = {
            "actor": actor,
            "stable_name": stable_name,
        }

    def get_component_by_name(self, actor, component_name, uclass):
        self.component_name_requests.append(component_name)
        self.last_component_by_name_request = {
            "actor": actor,
            "component_name": component_name,
            "uclass": uclass,
        }
        return self.components_by_name[component_name]

    def find_console_variable_by_name(self, console_variable_name):
        if console_variable_name not in self.cvar_values:
            return None
        return console_variable_name

    def get_console_variable_value_as_int(self, cvar):
        return int(self.cvar_values[cvar])


class FakeZeroConsoleVariableHandleUnrealService(FakeUnrealService):
    def __init__(self):
        super().__init__(components_by_actor={})
        self.value_getter_calls = []

    def find_console_variable_by_name(self, console_variable_name):
        return 0

    def get_console_variable_value_as_int(self, cvar):
        self.value_getter_calls.append(cvar)
        raise AssertionError("console variable value getter should not be called for null handles")


class FakeRenderingService:
    def __init__(self):
        self.align_requests = []

    def align_camera_with_viewport(self, **kwargs):
        self.align_requests.append(kwargs)


class FakeFrameContext:
    def __init__(self, owner, name):
        self.owner = owner
        self.name = name

    def __enter__(self):
        self.owner.events.append(f"begin:{self.name}")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.owner.events.append(f"end:{self.name}")
        return False


class FakeInstance:
    def __init__(self):
        self.events = []

    def begin_frame(self):
        return FakeFrameContext(owner=self, name="begin_frame")

    def end_frame(self, single_step=False):
        self.events.append(f"single_step:{single_step}")
        return FakeFrameContext(owner=self, name="end_frame")


class FakeFlashlight:
    def __init__(self):
        self.poses = []

    def K2_SetActorLocationAndRotation(self, **kwargs):
        self.poses.append(kwargs)


class FakeGame:
    def __init__(self, components_by_actor=None, components_by_name=None, cvar_values=None):
        self.unreal_service = FakeUnrealService(
            components_by_actor=components_by_actor or {},
            components_by_name=components_by_name,
            cvar_values=cvar_values)
        self.rendering_service = FakeRenderingService()


class FakeConsolePlayerController:
    def __init__(self):
        self.commands = []

    def ConsoleCommand(self, Command, bWriteToLog):
        self.commands.append((Command, bWriteToLog))


class FakeNoDirectConsolePlayerController:
    pass


class FakeKismetSystemLibrary:
    def __init__(self):
        self.commands = []

    def ExecuteConsoleCommand(self, Command, SpecificPlayer=None):
        self.commands.append((Command, SpecificPlayer))


class FakeGameplayStatics:
    def __init__(self, player_controller):
        self.player_controller = player_controller

    def GetPlayerController(self, PlayerIndex):
        return self.player_controller


class FakeConsoleGame(FakeGame):
    def __init__(self, cvar_values=None):
        super().__init__(cvar_values=cvar_values)
        self.player_controller = FakeConsolePlayerController()

    def get_unreal_object(self, uclass):
        self.uclass = uclass
        return FakeGameplayStatics(player_controller=self.player_controller)


class FakeKismetConsoleGame(FakeGame):
    def __init__(self):
        super().__init__()
        self.player_controller = FakeNoDirectConsolePlayerController()
        self.kismet_system_library = FakeKismetSystemLibrary()

    def get_unreal_object(self, uclass):
        if uclass == "UGameplayStatics":
            return FakeGameplayStatics(player_controller=self.player_controller)
        if uclass == "UKismetSystemLibrary":
            return self.kismet_system_library
        raise AttributeError(uclass)


class FakeZeroConsoleVariableHandleGame(FakeConsoleGame):
    def __init__(self):
        super().__init__()
        self.unreal_service = FakeZeroConsoleVariableHandleUnrealService()


class FakeShowFlagSettingsSetPropertyComponent:
    def __init__(self):
        self.calls = []
        self.ShowFlags = FakeShowFlags()

    def set_property_value(self, property_name, value, notify_editor=False):
        self.calls.append((property_name, value, notify_editor))
        if property_name != "ShowFlagSettings":
            raise AttributeError(property_name)
        if not value or "show_flag_name" not in value[0] or "enabled" not in value[0]:
            raise ValueError("snake-case show flag settings required")


class OrbitCollectionValidationTests(unittest.TestCase):
    def run_workflow_with_fake_python(self, workflow_args, env_overrides=None):
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_python = os.path.join(temp_dir, "fake_python.py")
            log_file = os.path.join(temp_dir, "workflow_calls.jsonl")
            with open(fake_python, "w", encoding="utf-8") as f:
                f.write("""#!/usr/bin/env python3
import json
import os
import sys

argv = sys.argv[1:]

def arg_value(flag):
    try:
        return argv[argv.index(flag) + 1]
    except ValueError:
        return None

settings_file = arg_value("--light-settings-file")
settings = None
if settings_file is not None:
    with open(settings_file, "r", encoding="utf-8") as f:
        settings = json.load(f)

record = {
    "argv": argv,
    "map": arg_value("--map"),
    "map_path": arg_value("--map-path"),
    "scene_light_intensity_scale": arg_value("--scene-light-intensity-scale"),
    "light_settings_file": settings_file,
    "output_dir": arg_value("--output-dir"),
    "flashlight_profile": arg_value("--flashlight-profile"),
    "flashlight_profile_file": arg_value("--flashlight-profile-file"),
    "render_lighting_mode": arg_value("--render-lighting-mode"),
    "intensity": arg_value("--intensity"),
    "attenuation_radius": arg_value("--attenuation-radius"),
    "inner_cone_angle": arg_value("--inner-cone-angle"),
    "outer_cone_angle": arg_value("--outer-cone-angle"),
    "source_radius": arg_value("--source-radius"),
    "soft_source_radius": arg_value("--soft-source-radius"),
    "settings": settings,
}
with open(os.environ["WORKFLOW_FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps(record, sort_keys=True) + "\\n")
""")
            os.chmod(fake_python, 0o755)
            env = os.environ.copy()
            env.update({
                "PYTHON": fake_python,
                "TMPDIR": temp_dir,
                "WORKFLOW_FAKE_LOG": log_file,
            })
            if env_overrides:
                env.update(env_overrides)

            result = subprocess.run(
                [WORKFLOW_FILE] + workflow_args,
                cwd=ROOT_DIR,
                env=env,
                check=True,
                capture_output=True,
                text=True)

            records = []
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    records = [json.loads(line) for line in f]
            return result, records

    def test_parse_args_defaults_orbit_controls_to_shoulders(self):
        args = orbit_collection.parse_args([])

        self.assertEqual(args.select_key, "Gamepad_RightShoulder")
        self.assertEqual(args.orbit_key, "Gamepad_LeftShoulder")
        self.assertEqual(args.toggle_key, "Gamepad_FaceButton_Right")
        self.assertEqual(args.aim_left_key, "Gamepad_DPad_Left")
        self.assertEqual(args.aim_right_key, "Gamepad_DPad_Right")
        self.assertEqual(args.aim_up_key, "Gamepad_DPad_Up")
        self.assertEqual(args.aim_down_key, "Gamepad_DPad_Down")
        self.assertEqual(args.flashlight_profile, "real_handheld_16in_16in")
        self.assertEqual(args.intensity, 1500.0)
        self.assertEqual(args.indirect_lighting_intensity, 0.25)
        self.assertEqual(args.inner_cone_angle, 17.0)
        self.assertAlmostEqual(args.outer_cone_angle, 26.5650511771)
        self.assertEqual(args.source_radius, 2.0)
        self.assertEqual(args.soft_source_radius, 12.0)
        self.assertTrue(args.cast_shadows)
        self.assertTrue(args.cast_dynamic_shadows)
        self.assertTrue(args.contact_shadows)
        self.assertFalse(args.use_inverse_squared_falloff)
        self.assertEqual(args.contact_shadow_length, 0.25)
        self.assertEqual(args.scene_light_intensity_scale, 1.0)
        self.assertTrue(args.disable_auto_exposure)
        self.assertTrue(args.disable_render_history)
        self.assertEqual(args.render_lighting_mode, "natural")
        self.assertEqual(args.depth_visualization_lower_percentile, 1.0)
        self.assertEqual(args.depth_visualization_upper_percentile, 99.0)
        self.assertIsNone(args.depth_visualization_min_meters)
        self.assertIsNone(args.depth_visualization_max_meters)

    def test_run_parse_args_defaults_scene_light_intensity_scale(self):
        args = flashlight_run.parse_args([])

        self.assertEqual(args.scene_light_intensity_scale, 1.0)
        self.assertEqual(args.live_lighting_mode, "default")
        self.assertEqual(args.startup_warmup_seconds, 0.0)
        self.assertEqual(args.flashlight_profile, "real_handheld_16in_16in")
        self.assertEqual(args.intensity, 1500.0)
        self.assertEqual(args.indirect_lighting_intensity, 0.25)
        self.assertEqual(args.inner_cone_angle, 17.0)
        self.assertAlmostEqual(args.outer_cone_angle, 26.5650511771)
        self.assertEqual(args.source_radius, 2.0)
        self.assertEqual(args.soft_source_radius, 12.0)
        self.assertTrue(args.cast_shadows)
        self.assertTrue(args.cast_dynamic_shadows)
        self.assertTrue(args.contact_shadows)
        self.assertFalse(args.use_inverse_squared_falloff)
        self.assertEqual(args.contact_shadow_length, 0.25)
        self.assertTrue(args.disable_auto_exposure)

    def test_run_realistic_live_mode_defaults_startup_warmup(self):
        args = flashlight_run.parse_args(["--live-lighting-mode", "realistic"])

        self.assertEqual(args.live_lighting_mode, "realistic")
        self.assertEqual(args.startup_warmup_seconds, flashlight_run.DEFAULT_REALISTIC_LIVE_WARMUP_SECONDS)
        self.assertFalse(args.disable_hardware_ray_tracing)
        self.assertTrue(flashlight_run.should_request_hardware_ray_tracing(args))

    def test_run_realistic_live_mode_can_disable_hardware_ray_tracing(self):
        args = flashlight_run.parse_args([
            "--live-lighting-mode", "realistic",
            "--disable-hardware-ray-tracing",
        ])

        self.assertTrue(args.disable_hardware_ray_tracing)
        self.assertFalse(flashlight_run.should_request_hardware_ray_tracing(args))

    def test_run_default_live_mode_does_not_request_hardware_ray_tracing(self):
        args = flashlight_run.parse_args([])

        self.assertFalse(flashlight_run.should_request_hardware_ray_tracing(args))

    def test_run_startup_warmup_override_is_respected(self):
        args = flashlight_run.parse_args([
            "--live-lighting-mode", "realistic",
            "--startup-warmup-seconds", "1.25",
        ])

        self.assertEqual(args.startup_warmup_seconds, 1.25)

    def test_flashlight_profile_cli_values_override_profile_defaults(self):
        for module in (orbit_collection, flashlight_run):
            with self.subTest(module=module.__name__):
                args = module.parse_args([
                    "--flashlight-profile", "soft_flood_validation",
                    "--intensity", "800",
                    "--outer-cone-angle", "42",
                    "--enable-flashlight-inverse-square",
                    "--disable-flashlight-contact-shadows",
                ])

                self.assertEqual(args.flashlight_profile, "soft_flood_validation")
                self.assertEqual(args.intensity, 800.0)
                self.assertEqual(args.outer_cone_angle, 42.0)
                self.assertEqual(args.inner_cone_angle, 2.0)
                self.assertTrue(args.use_inverse_squared_falloff)
                self.assertFalse(args.contact_shadows)

    def test_realistic_live_flashlight_profile_enables_inverse_square(self):
        args = flashlight_run.parse_args(["--flashlight-profile", "realistic_live_flashlight"])

        self.assertEqual(args.flashlight_profile, "realistic_live_flashlight")
        self.assertEqual(args.intensity, 800.0)
        self.assertEqual(args.indirect_lighting_intensity, 0.35)
        self.assertTrue(args.use_inverse_squared_falloff)
        self.assertTrue(args.cast_shadows)
        self.assertTrue(args.cast_dynamic_shadows)
        self.assertTrue(args.contact_shadows)

    def test_flashlight_profile_rejects_unknown_profile(self):
        for module in (orbit_collection, flashlight_run):
            with self.subTest(module=module.__name__):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        module.parse_args(["--flashlight-profile", "missing"])

    def test_spot_light_shape_controls_use_available_methods(self):
        component = FakeLightComponent()
        args = orbit_collection.parse_args(["--source-radius", "14", "--soft-source-radius", "90"])

        state = orbit_collection.apply_spot_light_shape_controls(
            spot_light_component=component,
            args=args)

        self.assertEqual(state, {
            "source_radius_set": True,
            "soft_source_radius_set": True,
        })
        self.assertEqual(component.source_radius, 14.0)
        self.assertEqual(component.soft_source_radius, 90.0)

    def test_spot_light_shadow_controls_use_available_methods(self):
        component = FakeLightComponent()
        args = orbit_collection.parse_args([
            "--disable-flashlight-shadows",
            "--enable-flashlight-dynamic-shadows",
            "--enable-flashlight-contact-shadows",
            "--contact-shadow-length", "0.4",
        ])

        state = orbit_collection.flashlight_profiles.apply_spot_light_shadow_controls(
            spot_light_component=component,
            args=args)

        self.assertEqual(state, {
            "cast_shadows_set": True,
            "cast_dynamic_shadows_set": True,
            "contact_shadows_set": True,
            "contact_shadow_length_set": True,
        })
        self.assertFalse(component.cast_shadows)
        self.assertTrue(component.cast_dynamic_shadows)
        self.assertTrue(component.contact_shadows)
        self.assertEqual(component.contact_shadow_length, 0.4)

    def test_spot_light_shadow_controls_skip_contact_call_when_disabled(self):
        component = FakeLightComponent()
        args = orbit_collection.parse_args(["--disable-flashlight-contact-shadows"])

        state = orbit_collection.flashlight_profiles.apply_spot_light_shadow_controls(
            spot_light_component=component,
            args=args)

        self.assertTrue(state["contact_shadows_set"])
        self.assertFalse(state["contact_shadow_length_set"])
        self.assertFalse(component.contact_shadows)
        self.assertIsNone(component.contact_shadow_length)

    def test_spot_light_inverse_square_controls_use_available_method(self):
        component = FakeLightComponent()
        args = flashlight_run.parse_args(["--enable-flashlight-inverse-square"])

        state = flashlight_run.flashlight_profiles.apply_spot_light_inverse_square_controls(
            spot_light_component=component,
            args=args)

        self.assertEqual(state, {
            "requested": True,
            "method_set": True,
            "property_set": False,
            "applied": True,
        })
        self.assertTrue(component.use_inverse_squared_falloff)

    def test_spot_light_inverse_square_controls_fall_back_to_editor_property(self):
        component = FakeEditorPropertyLightComponent()
        args = flashlight_run.parse_args(["--enable-flashlight-inverse-square"])

        state = flashlight_run.flashlight_profiles.apply_spot_light_inverse_square_controls(
            spot_light_component=component,
            args=args)

        self.assertEqual(state, {
            "requested": True,
            "method_set": False,
            "property_set": True,
            "applied": True,
        })
        self.assertTrue(component.properties["UseInverseSquaredFalloff"])

    def test_spot_light_ray_traced_shadow_intent_uses_available_method(self):
        component = FakeLightComponent()

        state = flashlight_run.flashlight_profiles.apply_spot_light_ray_traced_shadow_intent(
            spot_light_component=component,
            requested=True)

        self.assertTrue(state["requested"])
        self.assertTrue(state["method_set"])
        self.assertTrue(state["applied"])
        self.assertEqual(state["candidate_strategy"], "bool_only")
        self.assertTrue(component.cast_raytraced_shadow)

    def test_spot_light_ray_traced_shadow_intent_falls_back_to_editor_property(self):
        component = FakeEditorPropertyLightComponent()

        state = flashlight_run.flashlight_profiles.apply_spot_light_ray_traced_shadow_intent(
            spot_light_component=component,
            requested=True)

        self.assertTrue(state["requested"])
        self.assertFalse(state["method_set"])
        self.assertTrue(state["property_set"])
        self.assertTrue(state["applied"])
        self.assertEqual(state["candidate_strategy"], "bool_only")
        self.assertTrue(component.properties["CastRaytracedShadow"])

    def test_spot_light_ray_traced_shadow_intent_uses_bool_only_method_candidate(self):
        component = FakeStringRejectingRayTracedMethodLightComponent()

        state = flashlight_run.flashlight_profiles.apply_spot_light_ray_traced_shadow_intent(
            spot_light_component=component,
            requested=True)

        self.assertTrue(state["method_set"])
        self.assertTrue(state["applied"])
        self.assertEqual(state["candidate_strategy"], "bool_only")
        self.assertEqual(component.values, [True])
        self.assertTrue(component.cast_raytraced_shadow)

    def test_spot_light_ray_traced_shadow_intent_uses_bool_only_property_candidate(self):
        component = FakeEnumRayTracedPropertyLightComponent()

        state = flashlight_run.flashlight_profiles.apply_spot_light_ray_traced_shadow_intent(
            spot_light_component=component,
            requested=True)

        self.assertFalse(state["method_set"])
        self.assertTrue(state["property_set"])
        self.assertTrue(state["applied"])
        self.assertEqual(state["candidate_strategy"], "bool_only")
        self.assertEqual(component.values, [True])
        self.assertEqual(state["readback_value"], 1)

    def test_spot_light_shape_controls_use_reflected_bnewvalue_argument(self):
        for module in (orbit_collection, flashlight_run):
            with self.subTest(module=module.__name__):
                component = FakeReflectedSourceRadiusLightComponent()
                args = module.parse_args(["--source-radius", "14", "--soft-source-radius", "90"])

                state = module.apply_spot_light_shape_controls(
                    spot_light_component=component,
                    args=args)

                self.assertEqual(state, {
                    "source_radius_set": True,
                    "soft_source_radius_set": True,
                })
                self.assertEqual(component.source_radius_args, [{"bNewValue": 14.0}])
                self.assertEqual(component.soft_source_radius_args, [{"bNewValue": 90.0}])
                self.assertEqual(component.source_radius, 14.0)
                self.assertEqual(component.soft_source_radius, 90.0)

    def test_spot_light_shape_controls_fall_back_to_editor_properties(self):
        component = FakeEditorPropertyLightComponent()
        args = orbit_collection.parse_args(["--source-radius", "6", "--soft-source-radius", "32"])

        state = orbit_collection.apply_spot_light_shape_controls(
            spot_light_component=component,
            args=args)

        self.assertEqual(state, {
            "source_radius_set": True,
            "soft_source_radius_set": True,
        })
        self.assertEqual(component.properties["SourceRadius"], 6.0)
        self.assertEqual(component.properties["SoftSourceRadius"], 32.0)

    def test_spot_light_shape_controls_tolerate_missing_unreal_members(self):
        component = FakeMissingShapeLightComponent()
        args = orbit_collection.parse_args([])

        state = orbit_collection.apply_spot_light_shape_controls(
            spot_light_component=component,
            args=args)

        self.assertEqual(state, {
            "source_radius_set": False,
            "soft_source_radius_set": False,
        })

    def test_spot_light_shape_controls_do_not_report_dynamic_python_attrs_as_unreal_properties(self):
        for module in (orbit_collection, flashlight_run):
            with self.subTest(module=module.__name__):
                component = FakeDynamicMissingShapeLightComponent()
                args = module.parse_args([])

                state = module.apply_spot_light_shape_controls(
                    spot_light_component=component,
                    args=args)

                self.assertEqual(state, {
                    "source_radius_set": False,
                    "soft_source_radius_set": False,
                })
                self.assertFalse(hasattr(component, "SourceRadius"))
                self.assertFalse(hasattr(component, "SoftSourceRadius"))

    def test_scene_light_intensity_scale_allows_zero(self):
        orbit_args = orbit_collection.parse_args(["--scene-light-intensity-scale", "0"])
        run_args = flashlight_run.parse_args(["--scene-light-intensity-scale", "0"])

        self.assertEqual(orbit_args.scene_light_intensity_scale, 0.0)
        self.assertEqual(run_args.scene_light_intensity_scale, 0.0)

    def test_auto_exposure_can_be_explicitly_enabled_or_disabled(self):
        orbit_enabled_args = orbit_collection.parse_args(["--enable-auto-exposure"])
        run_enabled_args = flashlight_run.parse_args(["--enable-auto-exposure"])
        orbit_disabled_args = orbit_collection.parse_args(["--disable-auto-exposure"])
        run_disabled_args = flashlight_run.parse_args(["--disable-auto-exposure"])

        self.assertFalse(orbit_enabled_args.disable_auto_exposure)
        self.assertFalse(run_enabled_args.disable_auto_exposure)
        self.assertTrue(orbit_disabled_args.disable_auto_exposure)
        self.assertTrue(run_disabled_args.disable_auto_exposure)

    def test_render_history_can_be_explicitly_enabled_or_disabled(self):
        enabled_args = orbit_collection.parse_args(["--enable-render-history"])
        disabled_args = orbit_collection.parse_args(["--disable-render-history"])

        self.assertFalse(enabled_args.disable_render_history)
        self.assertTrue(disabled_args.disable_render_history)

    def test_live_startup_warmup_advances_frames_before_control(self):
        instance = FakeInstance()
        current_time = [10.0]
        sleep_durations = []

        def fake_monotonic():
            return current_time[0]

        def fake_sleep(duration):
            sleep_durations.append(duration)
            current_time[0] += duration

        state = flashlight_run.run_live_startup_warmup(
            instance=instance,
            duration_seconds=0.05,
            frame_period_seconds=0.02,
            sleep_fn=fake_sleep,
            monotonic_fn=fake_monotonic)

        self.assertEqual(state["duration_seconds"], 0.05)
        self.assertEqual(state["frames"], 3)
        self.assertEqual(
            instance.events,
            [
                "begin:begin_frame", "end:begin_frame", "single_step:False", "begin:end_frame", "end:end_frame",
                "begin:begin_frame", "end:begin_frame", "single_step:False", "begin:end_frame", "end:end_frame",
                "begin:begin_frame", "end:begin_frame", "single_step:False", "begin:end_frame", "end:end_frame",
            ])
        self.assertEqual(len(sleep_durations), 3)
        self.assertAlmostEqual(sleep_durations[0], 0.02)
        self.assertAlmostEqual(sleep_durations[1], 0.02)
        self.assertAlmostEqual(sleep_durations[2], 0.01)

    def test_live_startup_warmup_zero_duration_does_not_step_frames(self):
        instance = FakeInstance()

        state = flashlight_run.run_live_startup_warmup(
            instance=instance,
            duration_seconds=0.0)

        self.assertEqual(state["frames"], 0)
        self.assertEqual(instance.events, [])

    def test_live_runtime_render_config_applies_local_exposure_and_lumen_commands(self):
        game = FakeConsoleGame(cvar_values={
            cvar_name: value
            for cvar_name, value in flashlight_run.HARDWARE_RAY_TRACING_CVARS
        })
        player_controller = game.player_controller
        args = flashlight_run.parse_args(["--live-lighting-mode", "realistic", "--enable-auto-exposure"])

        state = flashlight_run.apply_live_runtime_render_config(
            game=game,
            player_controller=player_controller,
            args=args)

        commands = [command for command, _ in player_controller.commands]
        self.assertFalse(state["disable_auto_exposure"])
        self.assertTrue(state["suppress_local_exposure"])
        self.assertTrue(state["realistic_live_mode"])
        self.assertIn("r.DefaultFeature.LocalExposure.HighlightContrastScale 0", commands)
        self.assertIn("r.DefaultFeature.LocalExposure.ShadowContrastScale 0", commands)
        self.assertIn("ShowFlag.LocalExposure 0", commands)
        self.assertIn("r.DynamicGlobalIlluminationMethod 1", commands)
        self.assertIn("r.ReflectionMethod 1", commands)
        self.assertIn("ShowFlag.Materials 1", commands)
        self.assertIn("r.RayTracing.Enable 1", commands)
        self.assertIn("r.Lumen.HardwareRayTracing 1", commands)
        self.assertTrue(state["hardware_ray_tracing"]["requested"])
        self.assertEqual(
            state["hardware_ray_tracing"]["readback"]["confirmed"],
            True)

    def test_live_runtime_render_config_respects_hardware_ray_tracing_disable_flag(self):
        game = FakeConsoleGame()
        player_controller = game.player_controller
        args = flashlight_run.parse_args([
            "--live-lighting-mode", "realistic",
            "--disable-hardware-ray-tracing",
        ])

        state = flashlight_run.apply_live_runtime_render_config(
            game=game,
            player_controller=player_controller,
            args=args)

        commands = [command for command, _ in player_controller.commands]
        self.assertFalse(state["hardware_ray_tracing"]["requested"])
        self.assertTrue(state["hardware_ray_tracing"]["disabled_by_cli"])
        self.assertNotIn("r.RayTracing.Enable 1", commands)
        self.assertNotIn("r.Lumen.HardwareRayTracing 1", commands)
        self.assertIsNone(state["hardware_ray_tracing"]["readback"])

    def test_live_runtime_render_config_treats_zero_cvar_handle_as_missing(self):
        game = FakeZeroConsoleVariableHandleGame()
        player_controller = game.player_controller
        args = flashlight_run.parse_args(["--live-lighting-mode", "realistic"])

        state = flashlight_run.apply_live_runtime_render_config(
            game=game,
            player_controller=player_controller,
            args=args)

        readback = state["hardware_ray_tracing"]["readback"]
        self.assertIsNone(readback["confirmed"])
        self.assertFalse(readback["has_readback"])
        self.assertEqual(game.unreal_service.value_getter_calls, [])
        for cvar_state in readback["cvars"]:
            self.assertFalse(cvar_state["readback"]["available"])
            self.assertFalse(cvar_state["readback"]["readback_ok"])
            self.assertEqual(cvar_state["readback"]["error"], "console variable not found")
            self.assertFalse(cvar_state["matches_request"])

    def test_live_ray_traced_shadow_intent_skips_when_rt_readback_unsupported(self):
        game = FakeZeroConsoleVariableHandleGame()
        player_controller = game.player_controller
        args = flashlight_run.parse_args(["--live-lighting-mode", "realistic"])
        runtime_state = flashlight_run.apply_live_runtime_render_config(
            game=game,
            player_controller=player_controller,
            args=args)

        def unexpected_intent_fn(**kwargs):
            raise AssertionError("ray-traced shadow intent should not be called")

        state = flashlight_run.apply_live_spot_light_ray_traced_shadow_intent(
            spot_light_component=FakeLightComponent(),
            args=args,
            runtime_render_config_state=runtime_state,
            intent_fn=unexpected_intent_fn)

        self.assertTrue(state["requested_by_config"])
        self.assertFalse(state["runtime_confirmed"])
        self.assertFalse(state["applied"])
        self.assertIsNone(state["intent"])
        self.assertEqual(state["skipped_reason"], "hardware ray tracing runtime readback not confirmed")

    def test_live_ray_traced_shadow_intent_skips_when_rt_readback_false(self):
        game = FakeConsoleGame(cvar_values={
            cvar_name: 0
            for cvar_name, _ in flashlight_run.HARDWARE_RAY_TRACING_CVARS
        })
        player_controller = game.player_controller
        args = flashlight_run.parse_args(["--live-lighting-mode", "realistic"])
        runtime_state = flashlight_run.apply_live_runtime_render_config(
            game=game,
            player_controller=player_controller,
            args=args)

        def unexpected_intent_fn(**kwargs):
            raise AssertionError("ray-traced shadow intent should not be called")

        state = flashlight_run.apply_live_spot_light_ray_traced_shadow_intent(
            spot_light_component=FakeLightComponent(),
            args=args,
            runtime_render_config_state=runtime_state,
            intent_fn=unexpected_intent_fn)

        self.assertFalse(runtime_state["hardware_ray_tracing"]["readback"]["confirmed"])
        self.assertFalse(state["runtime_confirmed"])
        self.assertFalse(state["applied"])
        self.assertIsNone(state["intent"])
        self.assertEqual(state["skipped_reason"], "hardware ray tracing runtime readback not confirmed")

    def test_live_ray_traced_shadow_intent_runs_when_rt_readback_confirmed(self):
        game = FakeConsoleGame(cvar_values={
            cvar_name: value
            for cvar_name, value in flashlight_run.HARDWARE_RAY_TRACING_CVARS
        })
        player_controller = game.player_controller
        args = flashlight_run.parse_args(["--live-lighting-mode", "realistic"])
        runtime_state = flashlight_run.apply_live_runtime_render_config(
            game=game,
            player_controller=player_controller,
            args=args)

        calls = []

        def intent_fn(spot_light_component, requested):
            calls.append((spot_light_component, requested))
            return {"applied": True}

        component = FakeLightComponent()
        state = flashlight_run.apply_live_spot_light_ray_traced_shadow_intent(
            spot_light_component=component,
            args=args,
            runtime_render_config_state=runtime_state,
            intent_fn=intent_fn)

        self.assertTrue(state["runtime_confirmed"])
        self.assertTrue(state["applied"])
        self.assertEqual(calls, [(component, True)])

    def test_workflow_render_history_override_does_not_inject_conflicting_disable(self):
        result, records = self.run_workflow_with_fake_python(
            ["render", "--", "--enable-render-history"])

        self.assertIn("--enable-render-history", result.stdout)
        self.assertNotIn("--disable-render-history", result.stdout)
        self.assertEqual(len(records), 2)
        for record in records:
            self.assertEqual(
                record["map_path"],
                "/Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2_flashlight_validation_dark")
            self.assertIn("--enable-render-history", record["argv"])
            self.assertNotIn("--disable-render-history", record["argv"])
            self.assertEqual(record["flashlight_profile"], "real_handheld_16in_16in")
            self.assertEqual(record["render_lighting_mode"], "natural")
            self.assertIsNone(record["intensity"])
            self.assertIsNone(record["attenuation_radius"])
            self.assertIsNone(record["inner_cone_angle"])
            self.assertIsNone(record["outer_cone_angle"])
            self.assertIsNone(record["source_radius"])
            self.assertIsNone(record["soft_source_radius"])
        self.assertIn("--flashlight-profile real_handheld_16in_16in", result.stdout)
        self.assertIn("--render-lighting-mode natural", result.stdout)
        self.assertNotIn("--intensity 1200", result.stdout)

    def test_workflow_default_color_preset_runs_scene_on_and_scene_off_color_passes(self):
        _, records = self.run_workflow_with_fake_python(["render"])

        self.assertEqual(len(records), 2)
        self.assertEqual([record["scene_light_intensity_scale"] for record in records], ["0.2", "0.0"])
        self.assertEqual([record["flashlight_profile"] for record in records], ["real_handheld_16in_16in", "real_handheld_16in_16in"])
        self.assertEqual([record["render_lighting_mode"] for record in records], ["natural", "natural"])
        self.assertIn("spear_color_flashlight_scene_on_settings.", records[0]["light_settings_file"])
        self.assertIn("spear_color_flashlight_scene_off_settings.", records[1]["light_settings_file"])
        self.assertNotEqual(records[0]["light_settings_file"], "examples/flashlight/orbit_light_settings.json")
        self.assertNotEqual(records[1]["light_settings_file"], "examples/flashlight/orbit_light_settings.json")
        self.assertEqual(
            [setting["name"] for setting in records[0]["settings"]],
            ["scene_on_flashlight_off", "scene_on_flashlight_on"])
        self.assertEqual(
            [setting["name"] for setting in records[1]["settings"]],
            ["scene_off_flashlight_off", "scene_off_flashlight_on"])
        self.assertEqual(
            [setting["scene_lights_enabled"] for setting in records[0]["settings"]],
            [True, True])
        self.assertEqual(
            [setting["scene_lights_enabled"] for setting in records[1]["settings"]],
            [True, True])
        self.assertNotIn("intensity", records[0]["settings"][1])
        self.assertNotIn("intensity", records[1]["settings"][1])

    def test_workflow_color_preset_applies_requested_scale_and_flashlight_intensity(self):
        output_dir = os.path.join(ROOT_DIR, "examples", "flashlight", "orbit_collection_output")
        _, records = self.run_workflow_with_fake_python([
            "render",
            "--scene-light-intensity-scale", "0.35",
            "--intensity", "800",
            "--output-dir", output_dir,
        ])

        self.assertEqual([record["scene_light_intensity_scale"] for record in records], ["0.35", "0.0"])
        self.assertEqual([record["output_dir"] for record in records], [output_dir, output_dir])
        self.assertEqual([record["intensity"] for record in records], ["800", "800"])
        self.assertNotIn("intensity", records[0]["settings"][1])
        self.assertNotIn("intensity", records[1]["settings"][1])

    def test_workflow_validation_preset_uses_checked_in_diagnostic_settings(self):
        _, records = self.run_workflow_with_fake_python(["render", "--render-preset", "validation"])

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["scene_light_intensity_scale"], "0.2")
        self.assertEqual(records[0]["flashlight_profile"], "soft_flood_validation")
        self.assertEqual(records[0]["render_lighting_mode"], "validation")
        self.assertEqual(records[0]["light_settings_file"], "examples/flashlight/orbit_light_settings.json")
        self.assertEqual(
            [setting["scene_lights_enabled"] for setting in records[0]["settings"]],
            [True, False, False, True])

    def test_capture_scene_marks_camera_cut_when_render_history_disabled(self):
        components = [FakeCaptureComponent(), FakeCaptureComponent()]

        orbit_collection.capture_scene(camera_components=components, disable_render_history=True)

        self.assertEqual([component.capture_count for component in components], [1, 1])
        self.assertEqual([component.camera_cut_values_at_capture for component in components], [[True], [True]])

    def test_capture_scene_preserves_camera_cut_when_render_history_enabled(self):
        component = FakeCaptureComponent()

        orbit_collection.capture_scene(camera_components=[component], disable_render_history=False)

        self.assertEqual(component.capture_count, 1)
        self.assertEqual(component.camera_cut_values_at_capture, [False])

    def test_discard_warmup_captures_captures_and_reads_without_returning_frames(self):
        components = [FakeCaptureComponent(), FakeCaptureComponent()]
        component_descs = [
            {"name": "rgb", "component": components[0]},
            {"name": "depth_meters", "component": components[1]},
        ]
        game = FakeGame()
        instance = FakeInstance()
        flashlight = FakeFlashlight()
        spot_light_component = FakeLightComponent()
        viewport_desc = orbit_collection.make_viewport_desc(
            location={"X": 0.0, "Y": 0.0, "Z": 100.0},
            rotation={"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0},
            width=320,
            height=240,
            fov_degrees=80.0)

        orbit_collection.discard_warmup_captures(
            instance=instance,
            game=game,
            camera_sensor="camera_sensor",
            camera_components=components,
            component_descs=component_descs,
            viewport_desc=viewport_desc,
            width=320,
            height=240,
            flashlight=flashlight,
            spot_light_component=spot_light_component,
            command=orbit_collection.LightCommand(
                enabled=True,
                intensity=1500.0,
                yaw_offset_degrees=0.0,
                pitch_offset_degrees=0.0),
            disable_render_history=True,
            num_captures=2)

        self.assertEqual([component.capture_count for component in components], [2, 2])
        self.assertEqual(len(game.rendering_service.align_requests), 2)
        self.assertEqual(len(flashlight.poses), 2)
        self.assertEqual(spot_light_component.intensity, 1500.0)
        self.assertEqual([component.camera_cut_values_at_capture for component in components], [[True, True], [True, True]])

    def test_discard_warmup_captures_supports_no_flashlight_control(self):
        component = FakeCaptureComponent()
        component_descs = [{"name": "rgb", "component": component}]
        game = FakeGame()
        instance = FakeInstance()
        viewport_desc = orbit_collection.make_viewport_desc(
            location={"X": 0.0, "Y": 0.0, "Z": 100.0},
            rotation={"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0},
            width=320,
            height=240,
            fov_degrees=80.0)

        orbit_collection.discard_warmup_captures(
            instance=instance,
            game=game,
            camera_sensor="camera_sensor",
            camera_components=[component],
            component_descs=component_descs,
            viewport_desc=viewport_desc,
            width=320,
            height=240,
            flashlight=None,
            spot_light_component=None,
            command=None,
            disable_render_history=True,
            num_captures=2)

        self.assertEqual(component.capture_count, 2)
        self.assertEqual(len(game.rendering_service.align_requests), 2)
        self.assertEqual(component.camera_cut_values_at_capture, [True, True])

    def test_deterministic_capture_component_disables_temporal_overrides(self):
        component = FakeCaptureComponent()

        state = orbit_collection.configure_deterministic_capture_component(component)

        self.assertFalse(component.bAlwaysPersistRenderingState)
        self.assertFalse(component.PostProcessSettings["override_dynamic_global_illumination_method"])
        self.assertFalse(component.PostProcessSettings["override_reflection_method"])
        self.assertEqual(
            {
                key: state[key]
                for key in (
                    "always_persist_rendering_state_disabled",
                    "dynamic_global_illumination_override_disabled",
                    "reflection_override_disabled",
                )
            },
            {
                "always_persist_rendering_state_disabled": True,
                "dynamic_global_illumination_override_disabled": True,
                "reflection_override_disabled": True,
            })
        self.assertIn("bAlwaysPersistRenderingState", [
            attempt["property"]
            for attempt in state["always_persist_rendering_state_attempts"]
        ])

    def test_deterministic_capture_component_uses_unreal_python_property_readback(self):
        component = FakeEditorPropertyCaptureComponent("always_persist_rendering_state")

        state = orbit_collection.configure_deterministic_capture_component(component)

        self.assertTrue(state["always_persist_rendering_state_disabled"])
        self.assertFalse(component.properties["always_persist_rendering_state"])

    def test_deterministic_capture_component_does_not_report_unverified_persist_disable(self):
        component = FakeEditorPropertyCaptureComponent("unrelated_property")

        state = orbit_collection.configure_deterministic_capture_component(component)

        self.assertFalse(state["always_persist_rendering_state_disabled"])

    def test_setup_camera_sensor_applies_deterministic_capture_config_after_initialize(self):
        components_by_name = {
            component_desc["long_name"]: FakeCaptureComponent()
            for component_desc in orbit_collection.CAPTURE_COMPONENT_DESCS
        }
        game = FakeGame(components_by_name=components_by_name)

        _, component_descs, camera_components = orbit_collection.setup_camera_sensor(
            game=game,
            width=320,
            height=240,
            initial_viewport_desc=make_orbit_spec()["start_camera_pose"],
            disable_render_history=True)

        self.assertEqual(len(component_descs), 2)
        self.assertEqual(game.rendering_service.align_requests[0]["widths"], [320, 320])
        self.assertEqual(game.rendering_service.align_requests[0]["heights"], [240, 240])
        for component_desc, component in zip(component_descs, camera_components):
            self.assertEqual(component.initialize_count, 1)
            self.assertEqual(component.initialize_sp_funcs_count, 1)
            self.assertFalse(component.bAlwaysPersistRenderingState)
            self.assertFalse(component.PostProcessSettings["override_dynamic_global_illumination_method"])
            self.assertFalse(component.PostProcessSettings["override_reflection_method"])
            self.assertEqual(
                {
                    key: component_desc["deterministic_capture_state"][key]
                    for key in (
                        "always_persist_rendering_state_disabled",
                        "dynamic_global_illumination_override_disabled",
                        "reflection_override_disabled",
                    )
                },
                {
                    "always_persist_rendering_state_disabled": True,
                    "dynamic_global_illumination_override_disabled": True,
                    "reflection_override_disabled": True,
                })

    def test_setup_camera_sensor_preserves_render_history_when_enabled(self):
        components_by_name = {
            component_desc["long_name"]: FakeCaptureComponent()
            for component_desc in orbit_collection.CAPTURE_COMPONENT_DESCS
        }
        game = FakeGame(components_by_name=components_by_name)

        _, component_descs, camera_components = orbit_collection.setup_camera_sensor(
            game=game,
            width=320,
            height=240,
            initial_viewport_desc=make_orbit_spec()["start_camera_pose"],
            disable_render_history=False)

        for component_desc, component in zip(component_descs, camera_components):
            self.assertNotIn("deterministic_capture_state", component_desc)
            self.assertEqual(component.initialize_count, 1)
            self.assertEqual(component.initialize_sp_funcs_count, 1)
            self.assertTrue(component.bAlwaysPersistRenderingState)
            self.assertTrue(component.PostProcessSettings["override_dynamic_global_illumination_method"])
            self.assertTrue(component.PostProcessSettings["override_reflection_method"])

    def test_capture_component_descs_use_lighting_only_rgb_for_scene_off(self):
        default_descs = orbit_collection.get_capture_component_descs(
            scene_off_lighting_isolation=False)
        scene_off_descs = orbit_collection.get_capture_component_descs(
            scene_off_lighting_isolation=True)

        self.assertEqual(
            orbit_collection.get_rgb_capture_component_desc(default_descs)["long_name"],
            orbit_collection.FINAL_TONE_CURVE_RGB_COMPONENT_LONG_NAME)
        self.assertEqual(
            orbit_collection.get_rgb_capture_component_desc(default_descs)["capture_profile"],
            orbit_collection.RGB_CAPTURE_PROFILE_FINAL_TONE_CURVE)
        self.assertEqual(
            orbit_collection.get_rgb_capture_component_desc(scene_off_descs)["long_name"],
            orbit_collection.SCENE_OFF_LIGHTING_ONLY_RGB_COMPONENT_LONG_NAME)
        self.assertEqual(
            orbit_collection.get_rgb_capture_component_desc(scene_off_descs)["capture_profile"],
            orbit_collection.RGB_CAPTURE_PROFILE_LIGHTING_ONLY)
        self.assertTrue(
            orbit_collection.get_rgb_capture_component_desc(scene_off_descs)[
                "scene_off_lighting_only_rgb_requested"])

    def test_setup_camera_sensor_uses_lighting_only_rgb_component_for_scene_off(self):
        components_by_name = {
            component_desc["long_name"]: FakeCaptureComponent()
            for component_desc in orbit_collection.SCENE_OFF_CAPTURE_COMPONENT_DESCS
        }
        game = FakeGame(components_by_name=components_by_name)

        _, component_descs, _ = orbit_collection.setup_camera_sensor(
            game=game,
            width=320,
            height=240,
            initial_viewport_desc=make_orbit_spec()["start_camera_pose"],
            disable_render_history=True,
            scene_off_lighting_isolation=True)

        self.assertEqual(
            component_descs[0]["long_name"],
            orbit_collection.SCENE_OFF_LIGHTING_ONLY_RGB_COMPONENT_LONG_NAME)
        self.assertEqual(
            game.unreal_service.component_name_requests[0],
            orbit_collection.SCENE_OFF_LIGHTING_ONLY_RGB_COMPONENT_LONG_NAME)

    def test_visualize_rgb_preserves_final_tone_curve_bgr_uint8_frames(self):
        data = np.array([[[10, 20, 30, 255]]], dtype=np.uint8)

        image = orbit_collection.visualize_rgb(
            data=data,
            capture_profile=orbit_collection.RGB_CAPTURE_PROFILE_FINAL_TONE_CURVE)

        self.assertEqual(image.dtype, np.uint8)
        np.testing.assert_array_equal(
            image,
            np.array([[[10, 20, 30]]], dtype=np.uint8))

    def test_visualize_rgb_converts_lighting_only_float_rgb_to_bgr_uint8(self):
        data = np.array([[
            [0.0, 0.5, 1.0, 1.0],
            [np.nan, np.inf, -1.0, 0.0],
        ]], dtype=np.float32)

        image = orbit_collection.visualize_rgb(
            data=data,
            capture_profile=orbit_collection.RGB_CAPTURE_PROFILE_LIGHTING_ONLY)

        self.assertEqual(image.dtype, np.uint8)
        np.testing.assert_array_equal(
            image,
            np.array([[
                [255, 127, 0],
                [0, 255, 0],
            ]], dtype=np.uint8))

    def test_setup_camera_sensor_can_apply_scene_off_capture_show_flags(self):
        components_by_name = {
            component_desc["long_name"]: FakeCaptureComponent()
            for component_desc in orbit_collection.SCENE_OFF_CAPTURE_COMPONENT_DESCS
        }
        game = FakeGame(components_by_name=components_by_name)

        _, component_descs, camera_components = orbit_collection.setup_camera_sensor(
            game=game,
            width=320,
            height=240,
            initial_viewport_desc=make_orbit_spec()["start_camera_pose"],
            disable_render_history=True,
            scene_off_lighting_isolation=True)

        for component_desc, component in zip(component_descs, camera_components):
            state = component_desc["scene_off_lighting_isolation_state"]
            self.assertTrue(state["configured"])
            self.assertTrue(state["show_flag_settings_set"])
            self.assertEqual(
                [entry["ShowFlagName"] for entry in component.ShowFlagSettings],
                list(orbit_collection.SCENE_OFF_LIGHTING_ISOLATION_SHOW_FLAGS)
                + list(orbit_collection.SCENE_OFF_LIGHTING_ISOLATION_ENABLED_SHOW_FLAGS))
            self.assertEqual(
                set(component.ShowFlags.values.keys()),
                set(orbit_collection.SCENE_OFF_LIGHTING_ISOLATION_SHOW_FLAGS)
                | set(orbit_collection.SCENE_OFF_LIGHTING_ISOLATION_ENABLED_SHOW_FLAGS))
            for show_flag_name in orbit_collection.SCENE_OFF_LIGHTING_ISOLATION_SHOW_FLAGS:
                self.assertFalse(component.ShowFlags.values[show_flag_name])
            for show_flag_name in orbit_collection.SCENE_OFF_LIGHTING_ISOLATION_ENABLED_SHOW_FLAGS:
                self.assertTrue(component.ShowFlags.values[show_flag_name])

    def test_disable_scene_lights_hides_and_zeroes_existing_light_components(self):
        first_component = FakeLightComponent()
        second_component = FakeLightComponent(supports_indirect=False)
        game = FakeGame(components_by_actor={
            "first_actor": [first_component],
            "second_actor": [second_component],
        })

        state = orbit_collection.disable_scene_lights(game=game)

        self.assertEqual(state["components"], 2)
        self.assertEqual(state["visibility_disabled"], 2)
        self.assertEqual(state["direct_intensity_zeroed"], 2)
        self.assertEqual(state["indirect_lighting_intensity_zeroed"], 1)
        self.assertFalse(first_component.visible)
        self.assertEqual(first_component.intensity, 0.0)
        self.assertEqual(first_component.indirect_lighting_intensity, 0.0)
        self.assertFalse(second_component.visible)
        self.assertEqual(second_component.intensity, 0.0)

    def test_disable_scene_lighting_records_environment_contributors(self):
        light_component = FakeLightComponent()
        sky_component = FakeEnvironmentComponent()
        game = FakeGame(components_by_actor={
            "actor": {
                "ULightComponentBase": [light_component],
                "USkyLightComponent": [sky_component],
            },
        })

        state = orbit_collection.disable_scene_lighting(game=game)

        self.assertEqual(state["components"], 1)
        self.assertEqual(state["environment_contributors"]["components"], 1)
        self.assertEqual(state["environment_contributors"]["component_classes"]["USkyLightComponent"], 1)
        self.assertFalse(light_component.visible)
        self.assertFalse(sky_component.visible)
        self.assertEqual(sky_component.Intensity, 0.0)

    def test_scene_off_lighting_isolation_sends_show_flag_console_commands(self):
        game = FakeConsoleGame()

        state = orbit_collection.apply_scene_off_lighting_isolation_console_commands(game=game)

        self.assertEqual(
            state["applied"],
            len(orbit_collection.SCENE_OFF_LIGHTING_ISOLATION_SHOW_FLAGS)
            + len(orbit_collection.SCENE_OFF_LIGHTING_ISOLATION_ENABLED_SHOW_FLAGS))
        self.assertEqual(
            [command for command, _ in game.player_controller.commands],
            [
                f"ShowFlag.{show_flag_name} 0"
                for show_flag_name in orbit_collection.SCENE_OFF_LIGHTING_ISOLATION_SHOW_FLAGS
            ] + [
                f"ShowFlag.{show_flag_name} 1"
                for show_flag_name in orbit_collection.SCENE_OFF_LIGHTING_ISOLATION_ENABLED_SHOW_FLAGS
            ])

    def test_scene_off_lighting_isolation_uses_kismet_console_command_fallback(self):
        game = FakeKismetConsoleGame()

        state = orbit_collection.apply_scene_off_lighting_isolation_console_commands(game=game)

        expected_count = (
            len(orbit_collection.SCENE_OFF_LIGHTING_ISOLATION_SHOW_FLAGS)
            + len(orbit_collection.SCENE_OFF_LIGHTING_ISOLATION_ENABLED_SHOW_FLAGS))
        self.assertEqual(state["applied"], expected_count)
        self.assertEqual(len(game.kismet_system_library.commands), expected_count)
        self.assertIs(game.kismet_system_library.commands[0][1], game.player_controller)

    def test_scene_off_capture_show_flags_try_snake_case_set_property_fallback(self):
        component = FakeShowFlagSettingsSetPropertyComponent()

        state = orbit_collection.configure_scene_off_capture_show_flags(component=component)

        self.assertTrue(state["configured"])
        self.assertTrue(state["show_flag_settings_set"])
        self.assertEqual(state["show_flag_settings_property"], "ShowFlagSettings")
        self.assertEqual(state["show_flag_settings_key_style"], "snake")
        self.assertTrue(any(
            entry["show_flag_name"] == "LightingOnlyOverride" and entry["enabled"] is True
            for _, settings, _ in component.calls
            for entry in settings
            if "show_flag_name" in entry))

    def test_write_setting_metadata_records_scene_light_and_render_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            setting_dir = os.path.join(temp_dir, "scene_off_flashlight_on")
            os.makedirs(setting_dir)
            metadata_file = orbit_collection.write_setting_metadata(
                setting_dir=setting_dir,
                setting={
                    "name": "scene_off_flashlight_on",
                    "scene_lights_enabled": False,
                    "enabled": True,
                    "intensity": 1500.0,
                    "yaw_offset_degrees": 0.0,
                    "pitch_offset_degrees": 0.0,
                },
                scene_lights_enabled=False,
                scene_light_state={
                    "components": 2,
                    "visibility_disabled": 2,
                    "direct_intensity_zeroed": 2,
                    "indirect_lighting_intensity_zeroed": 1,
                },
                disable_auto_exposure=True,
                disable_render_history=True,
                component_descs=[{
                    "name": "rgb",
                    "deterministic_capture_state": {
                        "always_persist_rendering_state_disabled": True,
                    },
                }])

            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = orbit_collection.json.load(f)

        self.assertFalse(metadata["scene_lights_enabled"])
        self.assertTrue(metadata["disable_auto_exposure"])
        self.assertTrue(metadata["disable_render_history"])
        self.assertTrue(metadata["render_history_disable_verified"])
        self.assertEqual(metadata["scene_light_state"]["direct_intensity_zeroed"], 2)
        self.assertTrue(metadata["deterministic_capture"]["render_history_disable_verified"])
        self.assertEqual(metadata["deterministic_capture_components"][0]["name"], "rgb")

    def test_write_setting_metadata_does_not_verify_render_history_without_readback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            setting_dir = os.path.join(temp_dir, "scene_off_flashlight_off")
            os.makedirs(setting_dir)
            metadata_file = orbit_collection.write_setting_metadata(
                setting_dir=setting_dir,
                setting={
                    "name": "scene_off_flashlight_off",
                    "scene_lights_enabled": False,
                    "spawn_flashlight": False,
                    "enabled": False,
                    "intensity": 0.0,
                    "yaw_offset_degrees": 0.0,
                    "pitch_offset_degrees": 0.0,
                },
                scene_lights_enabled=False,
                scene_light_state={},
                disable_auto_exposure=True,
                disable_render_history=True,
                component_descs=[{
                    "name": "rgb",
                    "deterministic_capture_state": {
                        "always_persist_rendering_state_disabled": False,
                        "always_persist_rendering_state_attempts": [{
                            "property": "bAlwaysPersistRenderingState",
                            "set": False,
                            "readback": None,
                            "verified": False,
                        }],
                    },
                }],
                render_diagnostics={
                    "no_flashlight_ever_control": True,
                })

            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = orbit_collection.json.load(f)

        self.assertFalse(metadata["render_history_disable_verified"])
        self.assertFalse(metadata["deterministic_capture"]["render_history_disable_verified"])
        self.assertEqual(metadata["deterministic_capture"]["unverified_render_history_components"], ["rgb"])
        self.assertTrue(metadata["render_diagnostics"]["no_flashlight_ever_control"])

    def test_write_setting_metadata_records_scene_off_lighting_isolation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            setting_dir = os.path.join(temp_dir, "scene_off_flashlight_off")
            os.makedirs(setting_dir)
            metadata_file = orbit_collection.write_setting_metadata(
                setting_dir=setting_dir,
                setting={
                    "name": "scene_off_flashlight_off",
                    "scene_lights_enabled": False,
                    "spawn_flashlight": False,
                    "enabled": False,
                    "intensity": 0.0,
                    "yaw_offset_degrees": 0.0,
                    "pitch_offset_degrees": 0.0,
                },
                scene_lights_enabled=False,
                scene_light_state={},
                disable_auto_exposure=True,
                disable_render_history=True,
                component_descs=[{
                    "name": "rgb",
                    "scene_off_lighting_isolation_state": {
                        "configured": True,
                        "show_flag_settings_set": True,
                    },
                    "deterministic_capture_state": {
                        "always_persist_rendering_state_disabled": True,
                    },
                }],
                scene_off_lighting_isolation_requested=True,
                render_diagnostics={
                    "no_flashlight_ever_control": True,
                })

            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = orbit_collection.json.load(f)

        self.assertTrue(metadata["scene_off_lighting_isolation"]["requested"])
        self.assertTrue(metadata["scene_off_lighting_isolation"]["engine_ini_applied"])
        self.assertTrue(metadata["scene_off_lighting_isolation"]["capture_show_flags_configured"])
        self.assertIn("SkyLighting", metadata["scene_off_lighting_isolation"]["disabled_show_flags"])
        self.assertIn("Materials", metadata["scene_off_lighting_isolation"]["disabled_show_flags"])
        self.assertIn("LightingOnlyOverride", metadata["scene_off_lighting_isolation"]["enabled_show_flags"])

    def test_write_setting_metadata_records_scene_off_rgb_capture_component(self):
        component_descs = orbit_collection.get_capture_component_descs(
            scene_off_lighting_isolation=True)
        for component_desc in component_descs:
            component_desc["deterministic_capture_state"] = {
                "always_persist_rendering_state_disabled": True,
            }
            component_desc["scene_off_lighting_isolation_state"] = {
                "configured": True,
                "show_flag_settings_set": True,
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            setting_dir = os.path.join(temp_dir, "scene_off_flashlight_off")
            os.makedirs(setting_dir)
            metadata_file = orbit_collection.write_setting_metadata(
                setting_dir=setting_dir,
                setting={
                    "name": "scene_off_flashlight_off",
                    "scene_lights_enabled": False,
                    "spawn_flashlight": False,
                    "enabled": False,
                    "intensity": 0.0,
                    "yaw_offset_degrees": 0.0,
                    "pitch_offset_degrees": 0.0,
                },
                scene_lights_enabled=False,
                scene_light_state={},
                disable_auto_exposure=True,
                disable_render_history=True,
                component_descs=component_descs,
                scene_off_lighting_isolation_requested=True)

            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = orbit_collection.json.load(f)

        rgb_capture_component = metadata["rgb_capture_component"]
        self.assertEqual(
            rgb_capture_component["long_name"],
            orbit_collection.SCENE_OFF_LIGHTING_ONLY_RGB_COMPONENT_LONG_NAME)
        self.assertEqual(
            rgb_capture_component["capture_profile"],
            orbit_collection.RGB_CAPTURE_PROFILE_LIGHTING_ONLY)
        self.assertTrue(rgb_capture_component["scene_off_lighting_only_rgb_requested"])
        self.assertIn(rgb_capture_component, metadata["capture_components"])

    def test_residual_scene_off_illumination_diagnostics_flags_bright_no_flashlight_control(self):
        diagnostics = orbit_collection.get_residual_scene_off_illumination_diagnostics(
            render_diagnostics={
                "no_flashlight_ever_control": True,
            },
            rgb_luma_diagnostics={
                "mean_luma_median": 136.0,
            })

        self.assertTrue(diagnostics["checked"])
        self.assertTrue(diagnostics["likely_residual_environment_static_or_material_lighting"])

    def test_build_config_keeps_sp_core_ini_keys_compatible(self):
        args = orbit_collection.parse_args([
            "--mode", "render",
            "--map", "japanese_office_dark",
            "--width", "64",
            "--height", "48",
        ])

        with tempfile.TemporaryDirectory() as temp_dir:
            user_config_file = os.path.join(temp_dir, "user_config.yaml")
            with open(user_config_file, "w", encoding="utf-8") as f:
                f.write(
                    "SP_CORE:\n"
                    "  OVERRIDE_CONFIG_ENGINE_INI: True\n"
                    "  CONFIG_ENGINE_INI_STRING: |\n"
                    "    [/Script/Engine.RendererSettings]\n"
                    "    r.CustomDepth=3\n")

            config = orbit_collection.build_config(
                args=args,
                benchmarking=True,
                max_num_frames=3,
                user_config_files=[user_config_file])

        for key in (
            "OVERRIDE_CONFIG_EDITOR_INI",
            "CONFIG_EDITOR_INI_STRING",
            "OVERRIDE_CONFIG_ENGINE_INI",
            "CONFIG_ENGINE_INI_STRING",
            "OVERRIDE_CONFIG_GAME_INI",
            "CONFIG_GAME_INI_STRING",
            "OVERRIDE_CONFIG_GAME_USER_SETTINGS_INI",
            "CONFIG_GAME_USER_SETTINGS_INI_STRING",
            "OVERRIDE_CONFIG_INPUT_INI",
            "CONFIG_INPUT_INI_STRING",
        ):
            self.assertIn(key, config.SP_CORE)

        self.assertTrue(config.SP_CORE.OVERRIDE_CONFIG_ENGINE_INI)
        self.assertIn("r.CustomDepth=3", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.DefaultFeature.AutoExposure=False", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.EyeAdaptationQuality=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.DefaultFeature.LocalExposure.HighlightContrastScale=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.DefaultFeature.LocalExposure.ShadowContrastScale=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.DynamicGlobalIlluminationMethod=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.ReflectionMethod=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.Lumen.DiffuseIndirect.Allow=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.Lumen.Reflections.Allow=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.TemporalAA.Quality=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)

        for key in (
            "EDITOR_INI_CONFIG_VALUES",
            "ENGINE_INI_CONFIG_VALUES",
            "GAME_INI_CONFIG_VALUES",
            "GAME_USER_SETTINGS_INI_CONFIG_VALUES",
            "INPUT_INI_CONFIG_VALUES",
        ):
            self.assertIn(key, config.SP_CORE)
            self.assertEqual(list(config.SP_CORE[key].keys()), [])

        config_dump = config.dump()
        self.assertIn("CONFIG_ENGINE_INI_STRING", config_dump)
        self.assertIn("ENGINE_INI_CONFIG_VALUES: {}", config_dump)

    def test_orbit_build_config_validation_lighting_mode_disables_gi_for_deterministic_render(self):
        args = orbit_collection.parse_args([
            "--mode", "render",
            "--render-lighting-mode", "validation",
        ])

        with tempfile.TemporaryDirectory() as temp_dir:
            user_config_file = os.path.join(temp_dir, "user_config.yaml")
            with open(user_config_file, "w", encoding="utf-8") as f:
                f.write(
                    "SP_CORE:\n"
                    "  OVERRIDE_CONFIG_ENGINE_INI: True\n"
                    "  CONFIG_ENGINE_INI_STRING: |\n"
                    "    [/Script/Engine.RendererSettings]\n"
                    "    r.CustomDepth=3\n")

            config = orbit_collection.build_config(
                args=args,
                benchmarking=True,
                max_num_frames=3,
                user_config_files=[user_config_file])

        self.assertIn("r.DynamicGlobalIlluminationMethod=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.ReflectionMethod=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.Lumen.DiffuseIndirect.Allow=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.Lumen.Reflections.Allow=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.TemporalAA.Quality=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)

    def test_run_build_config_can_preserve_auto_exposure_when_enabled(self):
        args = flashlight_run.parse_args(["--enable-auto-exposure"])

        with tempfile.TemporaryDirectory() as temp_dir:
            user_config_file = os.path.join(temp_dir, "user_config.yaml")
            with open(user_config_file, "w", encoding="utf-8") as f:
                f.write(
                    "SP_CORE:\n"
                    "  OVERRIDE_CONFIG_ENGINE_INI: True\n"
                    "  CONFIG_ENGINE_INI_STRING: |\n"
                    "    [/Script/Engine.RendererSettings]\n"
                    "    r.CustomDepth=3\n")

            config = flashlight_run.build_config(
                args=args,
                user_config_files=[user_config_file])

        self.assertTrue(config.SP_CORE.OVERRIDE_CONFIG_ENGINE_INI)
        self.assertIn("r.CustomDepth=3", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.DefaultFeature.AutoExposure=False", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.EyeAdaptationQuality=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.DefaultFeature.LocalExposure.HighlightContrastScale=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.DefaultFeature.LocalExposure.ShadowContrastScale=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.RayTracing.Enable=1", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.Lumen.HardwareRayTracing=1", config.SP_CORE.CONFIG_ENGINE_INI_STRING)

    def test_run_build_config_realistic_live_suppresses_local_exposure_with_auto_exposure_enabled(self):
        args = flashlight_run.parse_args(["--live-lighting-mode", "realistic", "--enable-auto-exposure"])

        with tempfile.TemporaryDirectory() as temp_dir:
            user_config_file = os.path.join(temp_dir, "user_config.yaml")
            with open(user_config_file, "w", encoding="utf-8") as f:
                f.write(
                    "SP_CORE:\n"
                    "  OVERRIDE_CONFIG_ENGINE_INI: True\n"
                    "  CONFIG_ENGINE_INI_STRING: |\n"
                    "    [/Script/Engine.RendererSettings]\n"
                    "    r.CustomDepth=3\n")

            config = flashlight_run.build_config(
                args=args,
                user_config_files=[user_config_file])

        self.assertIn("r.CustomDepth=3", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.DefaultFeature.AutoExposure=False", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.EyeAdaptationQuality=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.DefaultFeature.LocalExposure.HighlightContrastScale=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.DefaultFeature.LocalExposure.ShadowContrastScale=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.DynamicGlobalIlluminationMethod=1", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.ReflectionMethod=1", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.Lumen.DiffuseIndirect.Allow=1", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.Lumen.Reflections.Allow=1", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.RayTracing.Enable=1", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.Lumen.HardwareRayTracing=1", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.Lumen.Reflections.HardwareRayTracing=1", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.Lumen.ScreenProbeGather.HardwareRayTracing=1", config.SP_CORE.CONFIG_ENGINE_INI_STRING)

    def test_run_build_config_realistic_live_hardware_ray_tracing_can_be_disabled(self):
        args = flashlight_run.parse_args([
            "--live-lighting-mode", "realistic",
            "--disable-hardware-ray-tracing",
        ])

        with tempfile.TemporaryDirectory() as temp_dir:
            user_config_file = os.path.join(temp_dir, "user_config.yaml")
            with open(user_config_file, "w", encoding="utf-8") as f:
                f.write(
                    "SP_CORE:\n"
                    "  OVERRIDE_CONFIG_ENGINE_INI: True\n"
                    "  CONFIG_ENGINE_INI_STRING: |\n"
                    "    [/Script/Engine.RendererSettings]\n"
                    "    r.CustomDepth=3\n")

            config = flashlight_run.build_config(
                args=args,
                user_config_files=[user_config_file])

        self.assertIn("r.DynamicGlobalIlluminationMethod=1", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.ReflectionMethod=1", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.RayTracing.Enable=1", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.Lumen.HardwareRayTracing=1", config.SP_CORE.CONFIG_ENGINE_INI_STRING)

    def test_orbit_build_config_preserves_temporal_rendering_when_enabled(self):
        args = orbit_collection.parse_args(["--mode", "render", "--enable-render-history"])

        with tempfile.TemporaryDirectory() as temp_dir:
            user_config_file = os.path.join(temp_dir, "user_config.yaml")
            with open(user_config_file, "w", encoding="utf-8") as f:
                f.write(
                    "SP_CORE:\n"
                    "  OVERRIDE_CONFIG_ENGINE_INI: True\n"
                    "  CONFIG_ENGINE_INI_STRING: |\n"
                    "    [/Script/Engine.RendererSettings]\n"
                    "    r.CustomDepth=3\n")

            config = orbit_collection.build_config(
                args=args,
                benchmarking=True,
                max_num_frames=3,
                user_config_files=[user_config_file])

        self.assertIn("r.CustomDepth=3", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.DefaultFeature.AutoExposure=False", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.DynamicGlobalIlluminationMethod=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.ReflectionMethod=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertNotIn("r.TemporalAA.Quality=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)

    def test_orbit_build_config_isolates_scene_off_residual_lighting(self):
        args = orbit_collection.parse_args(["--mode", "render", "--disable-scene-lights"])

        with tempfile.TemporaryDirectory() as temp_dir:
            user_config_file = os.path.join(temp_dir, "user_config.yaml")
            with open(user_config_file, "w", encoding="utf-8") as f:
                f.write(
                    "SP_CORE:\n"
                    "  OVERRIDE_CONFIG_ENGINE_INI: True\n"
                    "  CONFIG_ENGINE_INI_STRING: |\n"
                    "    [/Script/Engine.RendererSettings]\n"
                    "    r.CustomDepth=3\n")

            config = orbit_collection.build_config(
                args=args,
                benchmarking=True,
                max_num_frames=3,
                user_config_files=[user_config_file])

        self.assertIn("r.CustomDepth=3", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("[SystemSettings]", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("ShowFlag.SkyLighting=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("ShowFlag.GlobalIllumination=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("ShowFlag.IndirectLightingCache=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("ShowFlag.VolumetricLightmap=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("ShowFlag.Materials=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("ShowFlag.LightingOnlyOverride=1", config.SP_CORE.CONFIG_ENGINE_INI_STRING)

    def test_run_build_config_disables_auto_exposure_by_default(self):
        args = flashlight_run.parse_args([])

        with tempfile.TemporaryDirectory() as temp_dir:
            user_config_file = os.path.join(temp_dir, "user_config.yaml")
            with open(user_config_file, "w", encoding="utf-8") as f:
                f.write(
                    "SP_CORE:\n"
                    "  OVERRIDE_CONFIG_ENGINE_INI: True\n"
                    "  CONFIG_ENGINE_INI_STRING: |\n"
                    "    [/Script/Engine.RendererSettings]\n"
                    "    r.CustomDepth=3\n")

            config = flashlight_run.build_config(
                args=args,
                user_config_files=[user_config_file])

        self.assertTrue(config.SP_CORE.OVERRIDE_CONFIG_ENGINE_INI)
        self.assertIn("r.CustomDepth=3", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.DefaultFeature.AutoExposure=False", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.EyeAdaptationQuality=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.DefaultFeature.LocalExposure.HighlightContrastScale=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)
        self.assertIn("r.DefaultFeature.LocalExposure.ShadowContrastScale=0", config.SP_CORE.CONFIG_ENGINE_INI_STRING)

    def test_light_setting_names_reject_path_escape_segments(self):
        for name in (".", "..", ".hidden", "nested/path"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    orbit_collection.validate_light_settings(make_light_settings(name=name))

    def test_prepare_setting_output_dir_rejects_before_deleting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = os.path.join(temp_dir, "output")
            os.makedirs(output_dir)
            sentinel = os.path.join(temp_dir, "sentinel.txt")
            with open(sentinel, "w", encoding="utf-8") as f:
                f.write("keep")

            for name in (".", "..", ".hidden", "nested/path"):
                with self.subTest(name=name):
                    with self.assertRaises(ValueError):
                        orbit_collection.prepare_setting_output_dir(
                            output_dir=output_dir,
                            setting_name=name,
                            keep_existing_output=False)
                    self.assertTrue(os.path.exists(sentinel))
                    self.assertTrue(os.path.exists(output_dir))

    def test_prepare_setting_output_dir_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = os.path.join(temp_dir, "output")
            outside_dir = os.path.join(temp_dir, "outside")
            os.makedirs(output_dir)
            os.makedirs(outside_dir)
            sentinel = os.path.join(outside_dir, "sentinel.txt")
            with open(sentinel, "w", encoding="utf-8") as f:
                f.write("keep")
            os.symlink(outside_dir, os.path.join(output_dir, "escape"))

            with self.assertRaises(ValueError):
                orbit_collection.prepare_setting_output_dir(
                    output_dir=output_dir,
                    setting_name="escape",
                    keep_existing_output=False)
            self.assertTrue(os.path.exists(sentinel))

    def test_prepare_setting_output_dir_creates_depth_npy_and_viridis_dirs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            setting_dir, frame_dirs = orbit_collection.prepare_setting_output_dir(
                output_dir=temp_dir,
                setting_name="baseline_on",
                keep_existing_output=False)

            self.assertEqual(
                frame_dirs["depth_meters_npy"],
                os.path.join(setting_dir, "frames", "depth_meters_npy"))
            self.assertEqual(
                frame_dirs["depth_meters_viridis"],
                os.path.join(setting_dir, "frames", "depth_meters_viridis"))
            self.assertTrue(os.path.isdir(frame_dirs["depth_meters_npy"]))
            self.assertTrue(os.path.isdir(frame_dirs["depth_meters_viridis"]))

    def test_get_setting_video_files_includes_rgb_and_one_depth_video(self):
        setting_dir = os.path.realpath("/tmp/orbit-output/baseline_on")

        video_files = orbit_collection.get_setting_video_files(setting_dir=setting_dir)

        self.assertEqual(set(video_files.keys()), {"rgb", "depth_meters_viridis"})
        self.assertEqual(
            video_files["rgb"],
            os.path.join(setting_dir, "rgb.mp4"))
        self.assertEqual(
            video_files["depth_meters_viridis"],
            os.path.join(setting_dir, "depth_meters_viridis.mp4"))

    def test_depth_range_and_normalization_are_stable_across_sequence(self):
        first_depth = np.array([[1.0, 2.0, np.inf]], dtype=np.float32)
        second_depth = np.array([[[3.0], [5.0], [np.nan]]], dtype=np.float32)

        min_depth, max_depth = orbit_collection.update_depth_range(first_depth)
        min_depth, max_depth = orbit_collection.update_depth_range(
            second_depth,
            min_depth=min_depth,
            max_depth=max_depth)
        first_visualization = orbit_collection.normalize_depth_for_visualization(
            depth=first_depth,
            min_depth=min_depth,
            max_depth=max_depth)
        second_visualization = orbit_collection.normalize_depth_for_visualization(
            depth=second_depth,
            min_depth=min_depth,
            max_depth=max_depth)

        self.assertEqual(min_depth, 1.0)
        self.assertEqual(max_depth, 5.0)
        self.assertEqual(first_visualization.tolist(), [[0, 63, 0]])
        self.assertEqual(second_visualization.tolist(), [[127, 255, 0]])

    def test_degenerate_depth_range_maps_finite_pixels_to_midpoint(self):
        depth = np.array([[4.0, np.inf]], dtype=np.float32)

        visualization = orbit_collection.normalize_depth_for_visualization(
            depth=depth,
            min_depth=4.0,
            max_depth=4.0)

        self.assertEqual(visualization.tolist(), [[128, 0]])

    def test_depth_visualization_percentile_bounds_clip_far_outlier(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            depth_frame_file = os.path.join(temp_dir, "frame_0000.npy")
            np.save(depth_frame_file, np.array([[1.0, 2.0, 3.0, 4.0, 100000.0]], dtype=np.float32))

            min_depth, max_depth = orbit_collection.get_depth_visualization_bounds(
                depth_frame_files=[depth_frame_file],
                lower_percentile=0.0,
                upper_percentile=75.0,
                finite_min_depth=1.0,
                finite_max_depth=100000.0)
            visualization = orbit_collection.normalize_depth_for_visualization(
                depth=np.load(depth_frame_file),
                min_depth=min_depth,
                max_depth=max_depth)

        self.assertEqual(min_depth, 1.0)
        self.assertEqual(max_depth, 4.0)
        self.assertEqual(visualization.tolist(), [[0, 85, 170, 255, 255]])

    def test_depth_visualization_explicit_bounds_override_percentiles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            depth_frame_file = os.path.join(temp_dir, "frame_0000.npy")
            np.save(depth_frame_file, np.array([[1.0, 2.0, 3.0, 4.0, 100000.0]], dtype=np.float32))

            min_depth, max_depth = orbit_collection.get_depth_visualization_bounds(
                depth_frame_files=[depth_frame_file],
                lower_percentile=25.0,
                upper_percentile=75.0,
                explicit_min_depth=0.0,
                explicit_max_depth=10.0,
                finite_min_depth=1.0,
                finite_max_depth=100000.0)

        self.assertEqual(min_depth, 0.0)
        self.assertEqual(max_depth, 10.0)

    def test_depth_visualization_args_reject_invalid_bounds(self):
        invalid_argvs = [
            ["--intensity", "-1"],
            ["--intensity", "nan"],
            ["--attenuation-radius", "0"],
            ["--attenuation-radius", "inf"],
            ["--indirect-lighting-intensity", "-1"],
            ["--indirect-lighting-intensity", "nan"],
            ["--inner-cone-angle", "-1"],
            ["--inner-cone-angle", "nan"],
            ["--outer-cone-angle", "5", "--inner-cone-angle", "10"],
            ["--outer-cone-angle", "inf"],
            ["--source-radius", "-1"],
            ["--source-radius", "nan"],
            ["--soft-source-radius", "-1"],
            ["--soft-source-radius", "inf"],
            ["--scene-light-intensity-scale", "-1"],
            ["--scene-light-intensity-scale", "nan"],
            ["--scene-light-intensity-scale", "inf"],
            ["--disable-auto-exposure", "--enable-auto-exposure"],
            ["--enable-flashlight-inverse-square", "--disable-flashlight-inverse-square"],
            ["--disable-render-history", "--enable-render-history"],
            ["--depth-visualization-lower-percentile", "-1"],
            ["--depth-visualization-upper-percentile", "101"],
            ["--depth-visualization-lower-percentile", "90", "--depth-visualization-upper-percentile", "90"],
            ["--depth-visualization-min-meters", "10", "--depth-visualization-max-meters", "10"],
            ["--depth-visualization-max-samples", "0"],
        ]

        for argv in invalid_argvs:
            with self.subTest(argv=argv):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        orbit_collection.parse_args(argv)

    def test_run_scene_light_intensity_scale_rejects_invalid_values(self):
        invalid_argvs = [
            ["--intensity", "-1"],
            ["--intensity", "nan"],
            ["--attenuation-radius", "0"],
            ["--attenuation-radius", "inf"],
            ["--inner-cone-angle", "-1"],
            ["--inner-cone-angle", "nan"],
            ["--outer-cone-angle", "5", "--inner-cone-angle", "10"],
            ["--outer-cone-angle", "inf"],
            ["--source-radius", "-1"],
            ["--source-radius", "nan"],
            ["--soft-source-radius", "-1"],
            ["--soft-source-radius", "inf"],
            ["--scene-light-intensity-scale", "-1"],
            ["--scene-light-intensity-scale", "nan"],
            ["--scene-light-intensity-scale", "inf"],
            ["--startup-warmup-seconds", "-1"],
            ["--startup-warmup-seconds", "nan"],
            ["--disable-auto-exposure", "--enable-auto-exposure"],
            ["--enable-flashlight-inverse-square", "--disable-flashlight-inverse-square"],
        ]

        for argv in invalid_argvs:
            with self.subTest(argv=argv):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        flashlight_run.parse_args(argv)

    def test_light_settings_reject_non_finite_numbers(self):
        for key in ("intensity", "yaw_offset_degrees", "pitch_offset_degrees"):
            settings = make_light_settings()
            settings[0][key] = float("nan")
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    orbit_collection.validate_light_settings(settings)

    def test_light_settings_reject_non_boolean_scene_lights_enabled(self):
        settings = make_light_settings()
        settings[0]["scene_lights_enabled"] = "false"

        with self.assertRaises(ValueError):
            orbit_collection.validate_light_settings(settings)

    def test_light_settings_reject_invalid_spawn_flashlight_controls(self):
        settings = make_light_settings()
        settings[0]["spawn_flashlight"] = "false"
        with self.assertRaises(ValueError):
            orbit_collection.validate_light_settings(settings)

        settings = make_light_settings()
        settings[0]["spawn_flashlight"] = False
        with self.assertRaises(ValueError):
            orbit_collection.validate_light_settings(settings)

    def test_initial_render_light_setup_uses_first_setting_not_orbit_baseline(self):
        settings = [
            {
                "name": "scene_off_flashlight_off",
                "scene_lights_enabled": False,
                "spawn_flashlight": False,
                "enabled": False,
                "intensity": 0.0,
                "yaw_offset_degrees": 0.0,
                "pitch_offset_degrees": 0.0,
            },
            {
                "name": "scene_off_flashlight_on",
                "scene_lights_enabled": False,
                "enabled": True,
                "intensity": 1500.0,
                "yaw_offset_degrees": 1.0,
                "pitch_offset_degrees": -2.0,
            },
        ]

        args = orbit_collection.parse_args([])
        setup = orbit_collection.get_initial_render_light_setup(args=args, light_settings=settings)

        self.assertEqual(setup["setting_name"], "scene_off_flashlight_off")
        self.assertFalse(setup["spawn_flashlight"])
        self.assertIsNone(setup["command"])

    def test_initial_render_light_setup_spawns_with_first_setting_command_when_needed(self):
        settings = [
            {
                "name": "scene_on_flashlight_off",
                "scene_lights_enabled": True,
                "enabled": False,
                "intensity": 0.0,
                "yaw_offset_degrees": 0.0,
                "pitch_offset_degrees": 0.0,
            },
        ]

        args = orbit_collection.parse_args([])
        setup = orbit_collection.get_initial_render_light_setup(args=args, light_settings=settings)

        self.assertTrue(setup["spawn_flashlight"])
        self.assertFalse(setup["command"].enabled)
        self.assertEqual(setup["command"].intensity, 0.0)

    def test_initial_render_light_setup_uses_profile_intensity_when_setting_omits_intensity(self):
        settings = [
            {
                "name": "scene_on_flashlight_on",
                "scene_lights_enabled": True,
                "enabled": True,
                "yaw_offset_degrees": 0.0,
                "pitch_offset_degrees": 0.0,
            },
        ]
        args = orbit_collection.parse_args([])

        setup = orbit_collection.get_initial_render_light_setup(args=args, light_settings=settings)

        self.assertTrue(setup["spawn_flashlight"])
        self.assertTrue(setup["command"].enabled)
        self.assertEqual(setup["command"].intensity, args.intensity)

    def test_scene_light_render_groups_default_to_scene_on_then_scene_off(self):
        settings = [
            {
                "name": "scene_on_flashlight_off",
                "scene_lights_enabled": True,
                "enabled": False,
                "intensity": 0.0,
                "yaw_offset_degrees": 0.0,
                "pitch_offset_degrees": 0.0,
            },
            {
                "name": "scene_off_flashlight_on",
                "scene_lights_enabled": False,
                "enabled": True,
                "intensity": 1500.0,
                "yaw_offset_degrees": 0.0,
                "pitch_offset_degrees": 0.0,
            },
            {
                "name": "scene_on_flashlight_on",
                "enabled": True,
                "intensity": 1500.0,
                "yaw_offset_degrees": 0.0,
                "pitch_offset_degrees": 0.0,
            },
        ]

        groups = orbit_collection.get_scene_light_render_groups(settings)

        self.assertEqual(
            [(enabled, [setting["name"] for setting in group]) for enabled, group in groups],
            [
                (True, ["scene_on_flashlight_off", "scene_on_flashlight_on"]),
                (False, ["scene_off_flashlight_on"]),
            ])

    def test_scene_off_group_args_disable_scene_lights_independent_of_scene_on_scale(self):
        args = orbit_collection.parse_args(["--mode", "render", "--scene-light-intensity-scale", "0.2"])

        group_args = orbit_collection.get_scene_light_group_args(args=args, scene_lights_enabled=False)

        self.assertTrue(group_args.disable_scene_lights)
        self.assertEqual(group_args.scene_light_intensity_scale, 1.0)
        self.assertFalse(args.disable_scene_lights)
        self.assertEqual(args.scene_light_intensity_scale, 0.2)

    def test_checked_in_orbit_light_settings_are_valid(self):
        settings_file = os.path.join(ROOT_DIR, "examples", "flashlight", "orbit_light_settings.json")
        with open(settings_file, "r", encoding="utf-8") as f:
            settings = orbit_collection.json.load(f)

        orbit_collection.validate_light_settings(settings)
        self.assertEqual(
            [setting["name"] for setting in settings],
            [
                "scene_on_flashlight_off",
                "scene_off_flashlight_off",
                "scene_off_flashlight_on",
                "scene_on_flashlight_on",
            ])
        self.assertEqual(
            [setting["scene_lights_enabled"] for setting in settings],
            [True, False, False, True])
        self.assertFalse(settings[1]["spawn_flashlight"])
        self.assertEqual(settings[2]["intensity"], 1200.0)
        self.assertEqual(settings[3]["intensity"], 1200.0)

    def test_orbit_spec_rejects_non_finite_nested_numbers(self):
        invalid_specs = []
        spec = make_orbit_spec()
        spec["orbit_radius"] = float("inf")
        invalid_specs.append(spec)
        spec = make_orbit_spec()
        spec["start_camera_pose"]["camera_location"]["X"] = float("nan")
        invalid_specs.append(spec)
        spec = make_orbit_spec()
        spec["light_baseline_settings"]["yaw_offset_degrees"] = float("-inf")
        invalid_specs.append(spec)

        for spec in invalid_specs:
            with self.subTest(spec=spec):
                with self.assertRaises(ValueError):
                    orbit_collection.validate_orbit_spec(spec)


if __name__ == "__main__":
    unittest.main()
