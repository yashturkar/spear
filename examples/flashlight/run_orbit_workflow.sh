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
  --orbit-spec-file PATH                SPEAR_ORBIT_SPEC_FILE
  --light-settings-file PATH            SPEAR_ORBIT_LIGHT_SETTINGS_FILE
  --output-dir PATH                     SPEAR_ORBIT_OUTPUT_DIR
  --scene-light-intensity-scale VALUE   SPEAR_SCENE_LIGHT_INTENSITY_SCALE
  --movement-speed VALUE                SPEAR_ORBIT_MOVEMENT_SPEED
  --intensity VALUE                     SPEAR_FLASHLIGHT_INTENSITY
  --attenuation-radius VALUE            SPEAR_FLASHLIGHT_ATTENUATION_RADIUS
  --inner-cone-angle VALUE              SPEAR_FLASHLIGHT_INNER_CONE_ANGLE
  --outer-cone-angle VALUE              SPEAR_FLASHLIGHT_OUTER_CONE_ANGLE
  --indirect-lighting-intensity VALUE   SPEAR_FLASHLIGHT_INDIRECT_LIGHTING_INTENSITY

Render mode uses the default light settings file to produce:
  scene_on_flashlight_off
  scene_off_flashlight_off
  scene_off_flashlight_on
  scene_on_flashlight_on
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

python_bin="${PYTHON:-python}"
map_name="${SPEAR_ORBIT_MAP:-}"
map_path="${SPEAR_ORBIT_MAP_PATH:-/Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2}"
orbit_spec_file="${SPEAR_ORBIT_SPEC_FILE:-examples/flashlight/orbit_spec.json}"
light_settings_file="${SPEAR_ORBIT_LIGHT_SETTINGS_FILE:-examples/flashlight/orbit_light_settings.json}"
output_dir="${SPEAR_ORBIT_OUTPUT_DIR:-examples/flashlight/orbit_collection_output}"
scene_light_intensity_scale="${SPEAR_SCENE_LIGHT_INTENSITY_SCALE:-0.2}"
movement_speed="${SPEAR_ORBIT_MOVEMENT_SPEED:-600}"
flashlight_intensity="${SPEAR_FLASHLIGHT_INTENSITY:-1500}"
flashlight_attenuation_radius="${SPEAR_FLASHLIGHT_ATTENUATION_RADIUS:-450}"
flashlight_inner_cone_angle="${SPEAR_FLASHLIGHT_INNER_CONE_ANGLE:-8}"
flashlight_outer_cone_angle="${SPEAR_FLASHLIGHT_OUTER_CONE_ANGLE:-20}"
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
      shift 2
      ;;
    --map-path)
      require_value "$1" "${2-}"
      map_path="$2"
      map_name=""
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

map_args=()
if [[ -n "${map_name}" ]]; then
  map_args=(--map "${map_name}")
elif [[ -n "${map_path}" ]]; then
  map_args=(--map-path "${map_path}")
fi

cmd=(
  "${python_bin}" examples/flashlight/run_orbit_collection.py
  --mode "${subcommand}"
  "${map_args[@]}"
  --movement-speed "${movement_speed}"
  --disable-auto-exposure
  --scene-light-intensity-scale "${scene_light_intensity_scale}"
  --intensity "${flashlight_intensity}"
  --attenuation-radius "${flashlight_attenuation_radius}"
  --inner-cone-angle "${flashlight_inner_cone_angle}"
  --outer-cone-angle "${flashlight_outer_cone_angle}"
  --indirect-lighting-intensity "${flashlight_indirect_lighting_intensity}"
  --orbit-spec-file "${orbit_spec_file}"
)

if [[ "${subcommand}" == "render" ]]; then
  cmd+=(
    --light-settings-file "${light_settings_file}"
    --output-dir "${output_dir}"
  )
fi

printf 'Running:'
printf ' %q' "${cmd[@]}" "${extra_args[@]}"
printf '\n'
exec "${cmd[@]}" "${extra_args[@]}"
