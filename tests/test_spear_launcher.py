import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest


ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
LAUNCHER = os.path.join(ROOT_DIR, "tools", "spear-run")
LEDGER = os.path.join(ROOT_DIR, "docs", "environment_ledger.json")
ACTIVE_PACKAGE_VERSION = "college_cafeteria_showcase_linux_2026-07-16"
ACTIVE_PACKAGE_RUN_ID = "cook_college_cafeteria_showcase_20260716T154626"
ACTIVE_PACKAGE_SHA256 = "0f4b8caaf31be899b68ea1f91d0b0be83d8139a0d58a30730b294512bac86696"


def load_launcher_module():
    loader = importlib.machinery.SourceFileLoader("spear_run", LAUNCHER)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def run_launcher(*args):
    with tempfile.TemporaryDirectory() as cwd:
        return subprocess.run(
            [sys.executable, LAUNCHER, *args],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )


class SpearLauncherTests(unittest.TestCase):
    def test_environment_ledger_json_is_valid(self):
        with open(LEDGER, "r", encoding="utf-8") as f:
            ledger = json.load(f)

        required_fields = {
            "alias",
            "display_name",
            "unreal_map_path",
            "local_umap_path",
            "category",
            "status",
            "source",
            "created_or_imported_date",
            "last_cooked_date",
            "package_version",
            "cook_artifacts",
            "validation",
            "recommended_settings",
            "notes",
        }
        self.assertEqual(ledger["schema_version"], "1.0.0")
        self.assertEqual(ledger["default_package_version"], ACTIVE_PACKAGE_VERSION)
        self.assertEqual(
            ledger["active_package"],
            {
                "package_version": ACTIVE_PACKAGE_VERSION,
                "run_id": ACTIVE_PACKAGE_RUN_ID,
                "finished_at": "2026-07-16T19:50:04Z",
                "uat_exit_status": 0,
                "verify_exit_status": 0,
                "ledger_target_count": 1,
                "coverage_summary": (
                    "Focused Linux package cooked on 2026-07-16 for the Fab "
                    "CollegeCafeteria L_Showcase map. It also includes run_uat.py "
                    "default/template maps and configured always-cook directories, "
                    "but it is not a full-ledger recook for every environment."
                ),
                "archive_pak": (
                    "cpp/unreal_projects/SpearSim/Standalone-Development/Linux/"
                    "SpearSim/Content/Paks/SpearSim-Linux.pak"
                ),
                "staged_pak": (
                    "cpp/unreal_projects/SpearSim/Saved/StagedBuilds/Linux/"
                    "SpearSim/Content/Paks/SpearSim-Linux.pak"
                ),
                "sha256": ACTIVE_PACKAGE_SHA256,
                "size_bytes": 4780552749,
                "mtime": "2026-07-16T15:50:03.240545603-04:00",
                "verification_artifact": (
                    ".control-tower/runs/cook_college_cafeteria_showcase_20260716T154626/"
                    "verification_summary.txt"
                ),
                "coverage_artifact": (
                    ".control-tower/runs/cook_college_cafeteria_showcase_20260716T154626/"
                    "logs/pak_entries_college_cafeteria_showcase.txt"
                ),
                "validation_caveat": (
                    "Focused cook/package coverage plus bounded live flashlight smoke "
                    "for college_cafeteria only; older ledger environments still point "
                    "at their previous package evidence until a full-ledger recook is run."
                ),
                "source_tree_scene_dirs": [
                    "apartment_0000",
                    "cafeteria_500sqft_v2",
                    "CollegeCafeteria",
                    "infinigen_189cc130",
                    "infinigen_1dcacf23",
                    "infinigen_indoors_0000",
                    "JapaneseOffice",
                ],
                "source_tree_runnable_count": 9,
            },
        )
        aliases = [env["alias"] for env in ledger["environments"]]
        self.assertEqual(len(aliases), len(set(aliases)))
        self.assertEqual(
            set(aliases),
            {
                "japanese_office",
                "college_cafeteria",
                "apartment_0000",
                "infinigen_indoors_0000",
                "cafeteria_500sqft_v2",
                "cafeteria_500sqft_v2_flashlight_validation_dark",
                "infinigen_1dcacf23",
                "infinigen_189cc130",
                "infinigen_189cc130_realistic",
            },
        )
        packaged_envs = [
            env
            for env in ledger["environments"]
            if env["package_version"] == ledger["active_package"]["package_version"]
        ]
        self.assertEqual(len(packaged_envs), ledger["active_package"]["ledger_target_count"])
        for alias in [
            "japanese_office",
            "college_cafeteria",
            "apartment_0000",
            "cafeteria_500sqft_v2",
            "cafeteria_500sqft_v2_flashlight_validation_dark",
            "infinigen_indoors_0000",
            "infinigen_1dcacf23",
            "infinigen_189cc130",
            "infinigen_189cc130_realistic",
        ]:
            self.assertIn(alias, aliases)
        for alias in [
            "japanese_office_dark",
            "abandoned_room",
            "advanced_lighting",
            "debug_0000",
            "debug_0001",
            "minimal_default",
            "one_bed_apartment",
            "college_classroom",
            "cafeteria_500sqft",
            "restaurant_kitchen_1000sqft",
            "infinigen_indoors_kitchen",
            "starter_map",
            "third_person",
            "vehicle",
            "vehicle_offroad",
            "grand_auditorium_classroom_source",
            "indoors_smoke_source",
        ]:
            self.assertNotIn(alias, aliases)
        for env in ledger["environments"]:
            self.assertTrue(required_fields.issubset(env))
            if env["unreal_map_path"] is None:
                self.assertIsNone(env["local_umap_path"])
                self.assertIsNone(env["package_version"])
            else:
                self.assertIsNotNone(env["local_umap_path"])
                self.assertIsNotNone(env["package_version"])
                if env["package_version"] == ACTIVE_PACKAGE_VERSION:
                    self.assertEqual(env["last_cooked_date"], "2026-07-16")
                    self.assertIn(
                        ledger["active_package"]["verification_artifact"],
                        env["cook_artifacts"],
                    )

    def test_env_list_json(self):
        result = run_launcher("env", "list", "--json", "--all")

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        aliases = {env["alias"] for env in data["environments"]}
        self.assertEqual(
            aliases,
            {
                "japanese_office",
                "college_cafeteria",
                "apartment_0000",
                "infinigen_indoors_0000",
                "cafeteria_500sqft_v2",
                "cafeteria_500sqft_v2_flashlight_validation_dark",
                "infinigen_1dcacf23",
                "infinigen_189cc130",
                "infinigen_189cc130_realistic",
            },
        )

    def test_env_show_college_cafeteria_json(self):
        result = run_launcher("env", "show", "college_cafeteria", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["alias"], "college_cafeteria")
        self.assertEqual(data["unreal_map_path"], "/Game/CollegeCafeteria/levels/L_Showcase")
        self.assertEqual(data["package_version"], ACTIVE_PACKAGE_VERSION)

    def test_live_college_cafeteria_default_dry_run(self):
        result = run_launcher("live", "college_cafeteria", "--setting", "default", "--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("examples/flashlight/run.py", result.stdout)
        self.assertIn("--map-path /Game/CollegeCafeteria/levels/L_Showcase", result.stdout)
        self.assertIn("--live-lighting-mode realistic", result.stdout)
        self.assertIn("--flashlight-profile realistic_live_flashlight", result.stdout)
        self.assertIn("--disable-auto-exposure", result.stdout)
        self.assertIn("--movement-speed 600", result.stdout)
        self.assertIn("--scene-light-intensity-scale 1.0", result.stdout)
        self.assertIn("--indirect-lighting-intensity 0.05", result.stdout)
        self.assertIn("--startup-warmup-seconds 3", result.stdout)

    def test_live_infinigen_indoors_0000_falls_back_to_map_path(self):
        result = run_launcher("live", "infinigen_indoors_0000", "--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("examples/flashlight/run.py", result.stdout)
        self.assertIn(
            "--map-path /Game/SPEAR/Scenes/infinigen_indoors_0000/Maps/infinigen_indoors_0000",
            result.stdout,
        )
        self.assertNotIn("--map infinigen_indoors_0000", result.stdout)

    def test_live_infinigen_1dcacf23_realistic_2x_uses_map_path(self):
        result = run_launcher("live", "infinigen_1dcacf23", "--setting", "realistic-2x", "--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("examples/flashlight/run.py", result.stdout)
        self.assertIn(
            "--map-path /Game/SPEAR/Scenes/infinigen_1dcacf23/Maps/infinigen_1dcacf23",
            result.stdout,
        )
        self.assertIn("--flashlight-profile realistic_live_flashlight_2x", result.stdout)
        self.assertIn("--scene-light-intensity-scale 0.0005", result.stdout)

    def test_live_infinigen_189cc130_realistic_2x_uses_map_path(self):
        result = run_launcher("live", "infinigen_189cc130", "--setting", "realistic-2x", "--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("examples/flashlight/run.py", result.stdout)
        self.assertIn(
            "--map-path /Game/SPEAR/Scenes/infinigen_189cc130/Maps/infinigen_189cc130",
            result.stdout,
        )
        self.assertIn("--flashlight-profile realistic_live_flashlight_2x", result.stdout)
        self.assertIn("--scene-light-intensity-scale 1.0", result.stdout)
        self.assertIn("--disable-flashlight", result.stdout)

    def test_live_infinigen_189cc130_enable_flashlight_removes_default_disable(self):
        result = run_launcher(
            "live",
            "infinigen_189cc130",
            "--setting",
            "realistic-2x",
            "--dry-run",
            "--",
            "--enable-flashlight",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--enable-flashlight", result.stdout)
        self.assertNotIn("--disable-flashlight", result.stdout)

    def test_live_infinigen_189cc130_realistic_default_uses_map_path(self):
        result = run_launcher(
            "live",
            "infinigen_189cc130_realistic",
            "--setting",
            "default",
            "--dry-run",
            "--",
            "--enable-auto-exposure",
            "--disable-flashlight",
            "--scene-light-intensity-scale",
            "1.0",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("examples/flashlight/run.py", result.stdout)
        self.assertIn(
            "--map-path /Game/SPEAR/Scenes/infinigen_189cc130/Maps/infinigen_189cc130_realistic",
            result.stdout,
        )
        self.assertIn("--movement-speed 600", result.stdout)
        self.assertIn("--enable-auto-exposure", result.stdout)
        self.assertIn("--disable-flashlight", result.stdout)
        self.assertIn("--scene-light-intensity-scale 1.0", result.stdout)

    def test_orbit_render_dark_cafeteria_uses_map_path(self):
        result = run_launcher(
            "orbit",
            "render",
            "cafeteria_500sqft_v2_flashlight_validation_dark",
            "--dry-run",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("examples/flashlight/run_orbit_workflow.sh render", result.stdout)
        self.assertIn(
            "--map-path /Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2_flashlight_validation_dark",
            result.stdout,
        )
        self.assertIn("--render-preset color-flashlight-only", result.stdout)

    def test_unknown_environment_failure_suggests_env_list(self):
        result = run_launcher("live", "missing_world", "--dry-run")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown environment: missing_world", result.stderr)
        self.assertIn("spear env list", result.stderr)

    def test_launcher_locates_repo_root_from_own_path(self):
        module = load_launcher_module()

        self.assertEqual(str(module.repo_root()), ROOT_DIR)
        self.assertEqual(str(module.ledger_path()), LEDGER)


if __name__ == "__main__":
    unittest.main()
