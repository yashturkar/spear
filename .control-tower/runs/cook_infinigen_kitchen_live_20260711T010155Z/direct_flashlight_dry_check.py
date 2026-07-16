#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path


REPO = Path("/home/yashturkar/Workspace/spear")
RUN_PY = REPO / "examples/flashlight/run.py"
MAP_PATH = "/Game/SPEAR/Scenes/infinigen_indoors_kitchen/Maps/infinigen_indoors_kitchen"


def main() -> int:
    spec = importlib.util.spec_from_file_location("flashlight_run_dry_check", RUN_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    argv = [
        "--map-path",
        MAP_PATH,
        "--live-lighting-mode",
        "realistic",
        "--flashlight-profile",
        "realistic_live_flashlight_2x",
        "--scene-light-intensity-scale",
        "0.0005",
        "--movement-speed",
        "600",
        "--disable-auto-exposure",
        "--startup-warmup-seconds",
        "3",
    ]
    args = module.parse_args(argv)
    config = module.build_config(args=args)
    resolved_map = config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.GAME_DEFAULT_MAP
    result = {
        "status": "success" if resolved_map == MAP_PATH else "failed",
        "command": "python examples/flashlight/run.py " + " ".join(argv),
        "resolved_map": resolved_map,
        "expected_map": MAP_PATH,
        "override_game_default_map": bool(config.SP_SERVICES.INITIALIZE_ENGINE_SERVICE.OVERRIDE_GAME_DEFAULT_MAP),
        "live_lighting_mode": args.live_lighting_mode,
        "flashlight_profile": args.flashlight_profile,
        "movement_speed": args.movement_speed,
        "scene_light_intensity_scale": args.scene_light_intensity_scale,
        "disable_auto_exposure": args.disable_auto_exposure,
        "startup_warmup_seconds": args.startup_warmup_seconds,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "success" else 10


if __name__ == "__main__":
    raise SystemExit(main())
