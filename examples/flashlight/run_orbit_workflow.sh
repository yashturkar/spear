#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  examples/flashlight/run_orbit_workflow.sh teleop [options] [-- extra run_orbit_collection.py args]
  examples/flashlight/run_orbit_workflow.sh render [options] [-- extra run_orbit_collection.py args]

Defaults can be overridden with flags or environment variables:
  --python PATH                         PYTHON
  --map NAME                            SPEAR_ORBIT_MAP
  --map-path PATH                       SPEAR_ORBIT_MAP_PATH
  --render-preset NAME                  SPEAR_ORBIT_RENDER_PRESET
  --orbit-spec-file PATH                SPEAR_ORBIT_SPEC_FILE
  --light-settings-file PATH            SPEAR_ORBIT_LIGHT_SETTINGS_FILE
  --output-dir PATH                     SPEAR_ORBIT_OUTPUT_DIR
  --scene-light-intensity-scale VALUE   SPEAR_SCENE_LIGHT_INTENSITY_SCALE
  --movement-speed VALUE                SPEAR_ORBIT_MOVEMENT_SPEED
  --intensity VALUE                     SPEAR_FLASHLIGHT_INTENSITY
  --attenuation-radius VALUE            SPEAR_FLASHLIGHT_ATTENUATION_RADIUS
  --inner-cone-angle VALUE              SPEAR_FLASHLIGHT_INNER_CONE_ANGLE
  --outer-cone-angle VALUE              SPEAR_FLASHLIGHT_OUTER_CONE_ANGLE
  --source-radius VALUE                 SPEAR_FLASHLIGHT_SOURCE_RADIUS
  --soft-source-radius VALUE            SPEAR_FLASHLIGHT_SOFT_SOURCE_RADIUS
  --indirect-lighting-intensity VALUE   SPEAR_FLASHLIGHT_INDIRECT_LIGHTING_INTENSITY

Render presets:
  color-flashlight-only                 Default. Uses the dark cafeteria map,
                                        preserves material color, and renders
                                        scene on/off x flashlight off/on.
  validation                            Uses the checked-in light settings file
                                        for scene-on/scene-off diagnostics.
EOF
}

require_value() {
  if [[ $# -lt 2 || -z "$2" ]]; then
    printf 'Missing value for %s\n' "$1" >&2
    exit 2
  fi
}

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 2
fi

subcommand="$1"
shift

case "${subcommand}" in
  teleop|render)
    ;;
  -h|--help|help)
    usage
    exit 0
    ;;
  *)
    printf 'Unknown subcommand: %s\n\n' "${subcommand}" >&2
    usage >&2
    exit 2
    ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

default_map_path="/Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2"
default_color_flashlight_map_path="/Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2_flashlight_validation_dark"

python_bin="${PYTHON:-python}"
map_name="${SPEAR_ORBIT_MAP:-}"
map_path="${SPEAR_ORBIT_MAP_PATH:-${default_map_path}}"
map_was_overridden=0
if [[ -n "${SPEAR_ORBIT_MAP:-}" || -n "${SPEAR_ORBIT_MAP_PATH:-}" ]]; then
  map_was_overridden=1
fi
render_preset="${SPEAR_ORBIT_RENDER_PRESET:-color-flashlight-only}"
orbit_spec_file="${SPEAR_ORBIT_SPEC_FILE:-examples/flashlight/orbit_spec.json}"
light_settings_file="${SPEAR_ORBIT_LIGHT_SETTINGS_FILE:-examples/flashlight/orbit_light_settings.json}"
light_settings_file_was_overridden=0
if [[ -n "${SPEAR_ORBIT_LIGHT_SETTINGS_FILE:-}" ]]; then
  light_settings_file_was_overridden=1
fi
output_dir="${SPEAR_ORBIT_OUTPUT_DIR:-examples/flashlight/orbit_collection_output}"
scene_light_intensity_scale="${SPEAR_SCENE_LIGHT_INTENSITY_SCALE:-0.2}"
scene_light_intensity_scale_was_overridden=0
if [[ -n "${SPEAR_SCENE_LIGHT_INTENSITY_SCALE:-}" ]]; then
  scene_light_intensity_scale_was_overridden=1
fi
movement_speed="${SPEAR_ORBIT_MOVEMENT_SPEED:-600}"
flashlight_intensity="${SPEAR_FLASHLIGHT_INTENSITY:-1200}"
flashlight_attenuation_radius="${SPEAR_FLASHLIGHT_ATTENUATION_RADIUS:-650}"
flashlight_inner_cone_angle="${SPEAR_FLASHLIGHT_INNER_CONE_ANGLE:-2}"
flashlight_outer_cone_angle="${SPEAR_FLASHLIGHT_OUTER_CONE_ANGLE:-60}"
flashlight_source_radius="${SPEAR_FLASHLIGHT_SOURCE_RADIUS:-12}"
flashlight_soft_source_radius="${SPEAR_FLASHLIGHT_SOFT_SOURCE_RADIUS:-80}"
flashlight_indirect_lighting_intensity="${SPEAR_FLASHLIGHT_INDIRECT_LIGHTING_INTENSITY:-0}"
extra_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      require_value "$1" "${2-}"
      python_bin="$2"
      shift 2
      ;;
    --map)
      require_value "$1" "${2-}"
      map_name="$2"
      map_path=""
      map_was_overridden=1
      shift 2
      ;;
    --map-path)
      require_value "$1" "${2-}"
      map_path="$2"
      map_name=""
      map_was_overridden=1
      shift 2
      ;;
    --render-preset)
      require_value "$1" "${2-}"
      render_preset="$2"
      shift 2
      ;;
    --orbit-spec-file)
      require_value "$1" "${2-}"
      orbit_spec_file="$2"
      shift 2
      ;;
    --light-settings-file)
      require_value "$1" "${2-}"
      light_settings_file="$2"
      light_settings_file_was_overridden=1
      shift 2
      ;;
    --output-dir)
      require_value "$1" "${2-}"
      output_dir="$2"
      shift 2
      ;;
    --scene-light-intensity-scale)
      require_value "$1" "${2-}"
      scene_light_intensity_scale="$2"
      scene_light_intensity_scale_was_overridden=1
      shift 2
      ;;
    --movement-speed)
      require_value "$1" "${2-}"
      movement_speed="$2"
      shift 2
      ;;
    --intensity)
      require_value "$1" "${2-}"
      flashlight_intensity="$2"
      shift 2
      ;;
    --attenuation-radius)
      require_value "$1" "${2-}"
      flashlight_attenuation_radius="$2"
      shift 2
      ;;
    --inner-cone-angle)
      require_value "$1" "${2-}"
      flashlight_inner_cone_angle="$2"
      shift 2
      ;;
    --outer-cone-angle)
      require_value "$1" "${2-}"
      flashlight_outer_cone_angle="$2"
      shift 2
      ;;
    --source-radius)
      require_value "$1" "${2-}"
      flashlight_source_radius="$2"
      shift 2
      ;;
    --soft-source-radius)
      require_value "$1" "${2-}"
      flashlight_soft_source_radius="$2"
      shift 2
      ;;
    --indirect-lighting-intensity)
      require_value "$1" "${2-}"
      flashlight_indirect_lighting_intensity="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      extra_args+=("$@")
      break
      ;;
    *)
      extra_args+=("$1")
      shift
      ;;
  esac
done

generated_light_settings_files=()

cleanup() {
  local generated_file
  for generated_file in "${generated_light_settings_files[@]}"; do
    if [[ -f "${generated_file}" ]]; then
      rm -f "${generated_file}"
    fi
  done
}
trap cleanup EXIT

write_color_flashlight_light_settings() {
  local output_file="$1"
  local flashlight_off_name="$2"
  local flashlight_on_name="$3"
  cat > "${output_file}" <<EOF
[
  {
    "name": "${flashlight_off_name}",
    "scene_lights_enabled": true,
    "enabled": false,
    "intensity": 0.0,
    "yaw_offset_degrees": 0.0,
    "pitch_offset_degrees": 0.0
  },
  {
    "name": "${flashlight_on_name}",
    "scene_lights_enabled": true,
    "enabled": true,
    "intensity": ${flashlight_intensity},
    "yaw_offset_degrees": 0.0,
    "pitch_offset_degrees": 0.0
  }
]
EOF
}

make_map_args() {
  map_args=()
  if [[ -n "${map_name}" ]]; then
    map_args=(--map "${map_name}")
  elif [[ -n "${map_path}" ]]; then
    map_args=(--map-path "${map_path}")
  fi
}

make_base_cmd() {
  local command_mode="$1"
  make_map_args
  cmd=(
    "${python_bin}" examples/flashlight/run_orbit_collection.py
    --mode "${command_mode}"
    "${map_args[@]}"
    --movement-speed "${movement_speed}"
    --disable-auto-exposure
    --scene-light-intensity-scale "${scene_light_intensity_scale}"
    --intensity "${flashlight_intensity}"
    --attenuation-radius "${flashlight_attenuation_radius}"
    --inner-cone-angle "${flashlight_inner_cone_angle}"
    --outer-cone-angle "${flashlight_outer_cone_angle}"
    --source-radius "${flashlight_source_radius}"
    --soft-source-radius "${flashlight_soft_source_radius}"
    --indirect-lighting-intensity "${flashlight_indirect_lighting_intensity}"
    --orbit-spec-file "${orbit_spec_file}"
  )
}

run_cmd() {
  printf 'Running:'
  printf ' %q' "${cmd[@]}" "${extra_args[@]}"
  printf '\n'
  "${cmd[@]}" "${extra_args[@]}"
}

if [[ "${subcommand}" == "render" ]]; then
  case "${render_preset}" in
    color-flashlight-only)
      if [[ "${map_was_overridden}" -eq 0 ]]; then
        map_name=""
        map_path="${default_color_flashlight_map_path}"
      fi

      scene_on_light_settings_file="$(mktemp "${TMPDIR:-/tmp}/spear_color_flashlight_scene_on_settings.XXXXXX.json")"
      scene_off_light_settings_file="$(mktemp "${TMPDIR:-/tmp}/spear_color_flashlight_scene_off_settings.XXXXXX.json")"
      generated_light_settings_files+=("${scene_on_light_settings_file}" "${scene_off_light_settings_file}")
      write_color_flashlight_light_settings \
        "${scene_on_light_settings_file}" \
        "scene_on_flashlight_off" \
        "scene_on_flashlight_on"
      write_color_flashlight_light_settings \
        "${scene_off_light_settings_file}" \
        "scene_off_flashlight_off" \
        "scene_off_flashlight_on"

      make_base_cmd "render"
      cmd+=(
        --light-settings-file "${scene_on_light_settings_file}"
        --output-dir "${output_dir}"
      )
      run_cmd

      scene_light_intensity_scale="0.0"
      make_base_cmd "render"
      cmd+=(
        --light-settings-file "${scene_off_light_settings_file}"
        --output-dir "${output_dir}"
      )
      run_cmd
      exit 0
      ;;
    validation)
      ;;
    *)
      printf 'Unknown render preset: %s\n\n' "${render_preset}" >&2
      usage >&2
      exit 2
      ;;
  esac
fi

make_base_cmd "${subcommand}"

if [[ "${subcommand}" == "render" ]]; then
  cmd+=(
    --light-settings-file "${light_settings_file}"
    --output-dir "${output_dir}"
  )
fi

run_cmd
