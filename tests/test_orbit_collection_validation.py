import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest

import numpy as np


ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT_DIR, "python"))

MODULE_FILE = os.path.join(ROOT_DIR, "examples", "flashlight", "run_orbit_collection.py")
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


class OrbitCollectionValidationTests(unittest.TestCase):
    def test_parse_args_defaults_orbit_controls_to_shoulders(self):
        args = orbit_collection.parse_args([])

        self.assertEqual(args.select_key, "Gamepad_RightShoulder")
        self.assertEqual(args.orbit_key, "Gamepad_LeftShoulder")
        self.assertEqual(args.toggle_key, "Gamepad_FaceButton_Right")
        self.assertEqual(args.aim_left_key, "Gamepad_DPad_Left")
        self.assertEqual(args.aim_right_key, "Gamepad_DPad_Right")
        self.assertEqual(args.aim_up_key, "Gamepad_DPad_Up")
        self.assertEqual(args.aim_down_key, "Gamepad_DPad_Down")
        self.assertEqual(args.indirect_lighting_intensity, 0.0)
        self.assertEqual(args.scene_light_intensity_scale, 1.0)
        self.assertTrue(args.disable_auto_exposure)
        self.assertEqual(args.depth_visualization_lower_percentile, 1.0)
        self.assertEqual(args.depth_visualization_upper_percentile, 99.0)
        self.assertIsNone(args.depth_visualization_min_meters)
        self.assertIsNone(args.depth_visualization_max_meters)

    def test_run_parse_args_defaults_scene_light_intensity_scale(self):
        args = flashlight_run.parse_args([])

        self.assertEqual(args.scene_light_intensity_scale, 1.0)
        self.assertTrue(args.disable_auto_exposure)

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
            ["--indirect-lighting-intensity", "-1"],
            ["--indirect-lighting-intensity", "nan"],
            ["--scene-light-intensity-scale", "-1"],
            ["--scene-light-intensity-scale", "nan"],
            ["--scene-light-intensity-scale", "inf"],
            ["--disable-auto-exposure", "--enable-auto-exposure"],
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
            ["--scene-light-intensity-scale", "-1"],
            ["--scene-light-intensity-scale", "nan"],
            ["--scene-light-intensity-scale", "inf"],
            ["--disable-auto-exposure", "--enable-auto-exposure"],
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
