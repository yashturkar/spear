import importlib.util
import os
import sys
import tempfile
import unittest


ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT_DIR, "python"))

MODULE_FILE = os.path.join(ROOT_DIR, "examples", "flashlight", "run_orbit_collection.py")
SPEC = importlib.util.spec_from_file_location("run_orbit_collection", MODULE_FILE)
orbit_collection = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = orbit_collection
SPEC.loader.exec_module(orbit_collection)


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
