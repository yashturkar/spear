import json
import os
import sys


output_dir = sys.argv[1]
summary_file = sys.argv[2]

settings = {}
for setting_name in [
    "scene_on_flashlight_off",
    "scene_off_flashlight_off",
    "scene_off_flashlight_on",
    "scene_on_flashlight_on",
]:
    metadata_file = os.path.join(output_dir, setting_name, "metadata.json")
    with open(metadata_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    render = metadata.get("render_diagnostics", {})
    residual = metadata.get("residual_scene_off_illumination", {})
    luma = metadata.get("rgb_luma_diagnostics", {})
    scene_off = metadata.get("scene_off_lighting_isolation", {})
    settings[setting_name] = {
        "metadata_file": metadata_file,
        "mean_luma_median": luma.get("mean_luma_median"),
        "mean_luma_min": luma.get("mean_luma_min"),
        "mean_luma_max": luma.get("mean_luma_max"),
        "p99_luma_median": luma.get("p99_luma_median"),
        "residual_likely": residual.get("likely_residual_environment_static_or_material_lighting"),
        "residual_threshold_mean_luma": residual.get("threshold_mean_luma"),
        "no_flashlight_ever_control": render.get("no_flashlight_ever_control"),
        "spawn_flashlight": metadata.get("setting", {}).get("spawn_flashlight"),
        "flashlight_ever_spawned_after_setting_setup": render.get("flashlight_ever_spawned_after_setting_setup"),
        "flashlight_ever_enabled_after_setting_setup": render.get("flashlight_ever_enabled_after_setting_setup"),
        "scene_off_lighting_isolation_requested": scene_off.get("requested"),
        "capture_show_flags_configured": scene_off.get("capture_show_flags_configured"),
        "engine_ini_applied": scene_off.get("engine_ini_applied"),
    }

off = settings["scene_off_flashlight_off"]
acceptance_passed = (
    off["mean_luma_median"] is not None
    and off["mean_luma_median"] < 20.0
    and off["no_flashlight_ever_control"] is True
    and off["flashlight_ever_spawned_after_setting_setup"] is False
    and off["flashlight_ever_enabled_after_setting_setup"] is False
    and off["residual_likely"] is False
)

summary = {
    "schema_version": "1.0.0",
    "output_dir": output_dir,
    "acceptance": {
        "passed": acceptance_passed,
        "threshold_scene_off_flashlight_off_median_mean_luma": 20.0,
        "scene_off_flashlight_off_median_mean_luma": off["mean_luma_median"],
    },
    "settings": settings,
}

os.makedirs(os.path.dirname(summary_file), exist_ok=True)
with open(summary_file, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, sort_keys=True)
print(json.dumps(summary, indent=2, sort_keys=True))
