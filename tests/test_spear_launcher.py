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
ACTIVE_PACKAGE_VERSION = "full_ledger_plus_infinigen_189cc130_table_lamp_repositioned_screen_off_linux_2026-07-13"
ACTIVE_PACKAGE_RUN_ID = "infinigen_189cc130_table_lamp_only_20260714T002136Z"
ACTIVE_PACKAGE_SHA256 = "4b9dc32d6c02ddad8093695f629f0428b0a1595822efbd8ecaac895ad94d53fa"


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
                "finished_at": "2026-07-14T00:59:41Z",
                "uat_exit_status": 0,
                "verify_exit_status": 0,
                "ledger_target_count": 22,
                "coverage_summary": (
                    "The 2026-07-13 full-ledger package covers 22 runnable environments, "
                    "including the user-edited infinigen_189cc130 map with the table "
                    "lamp repositioned away from the monitor and screen/monitor "
                    "emissive lighting disabled."
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
                "size_bytes": 5259388196,
                "mtime": "2026-07-13T20:59:27.061929048-04:00",
                "verification_artifact": (
                    ".control-tower/runs/infinigen_189cc130_table_lamp_only_20260714T002136Z/"
                    "verification_summary.txt"
                ),
                "coverage_artifact": (
                    ".control-tower/runs/infinigen_189cc130_table_lamp_only_20260714T002136Z/"
                    "cook_maps.txt"
                ),
                "validation_caveat": (
                    "Cook/package coverage only; runtime visual validation statuses on "
                    "individual environments remain authoritative."
                ),
            },
        )
        aliases = [env["alias"] for env in ledger["environments"]]
        self.assertEqual(len(aliases), len(set(aliases)))
        packaged_envs = [
            env
            for env in ledger["environments"]
            if env["package_version"] == ledger["active_package"]["package_version"]
        ]
        self.assertEqual(len(packaged_envs), ledger["active_package"]["ledger_target_count"])
        for alias in [
            "japanese_office",
            "japanese_office_dark",
            "cafeteria_500sqft_v2",
            "college_classroom",
            "infinigen_1dcacf23",
            "infinigen_189cc130",
            "grand_auditorium_classroom_source",
        ]:
            self.assertIn(alias, aliases)
        for env in ledger["environments"]:
            self.assertTrue(required_fields.issubset(env))
            if env["unreal_map_path"] is None:
                self.assertIsNone(env["local_umap_path"])
                self.assertIsNone(env["package_version"])
            else:
                self.assertIsNotNone(env["local_umap_path"])
                self.assertIsNotNone(env["package_version"])
                if env["package_version"] == ACTIVE_PACKAGE_VERSION:
                    self.assertEqual(env["last_cooked_date"], "2026-07-13")
                    self.assertIn(
                        ledger["active_package"]["verification_artifact"],
                        env["cook_artifacts"],
                    )

    def test_env_list_json(self):
        result = run_launcher("env", "list", "--json", "--all")

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        aliases = {env["alias"] for env in data["environments"]}
        self.assertIn("japanese_office_dark", aliases)
        self.assertIn("infinigen_1dcacf23", aliases)
        self.assertIn("infinigen_189cc130", aliases)
        self.assertIn("grand_auditorium_classroom_source", aliases)

    def test_env_show_japanese_office_dark_json(self):
        result = run_launcher("env", "show", "japanese_office_dark", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["alias"], "japanese_office_dark")
        self.assertEqual(data["unreal_map_path"], "/Game/JapaneseOffice/Maps/Demonstration_Dark")
        self.assertEqual(data["package_version"], ACTIVE_PACKAGE_VERSION)

    def test_live_japanese_office_dark_realistic_2x_dry_run(self):
        result = run_launcher("live", "japanese_office_dark", "--setting", "realistic-2x", "--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("examples/flashlight/run.py", result.stdout)
        self.assertIn("--map japanese_office_dark", result.stdout)
        self.assertIn("--flashlight-profile realistic_live_flashlight_2x", result.stdout)
        self.assertIn("--scene-light-intensity-scale 0.0005", result.stdout)
        self.assertIn("--startup-warmup-seconds 3", result.stdout)

    def test_live_college_classroom_falls_back_to_map_path(self):
        result = run_launcher("live", "college_classroom", "--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("examples/flashlight/run.py", result.stdout)
        self.assertIn(
            "--map-path /Game/SPEAR/Scenes/college_classroom/Maps/college_classroom",
            result.stdout,
        )
        self.assertNotIn("--map college_classroom", result.stdout)

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
