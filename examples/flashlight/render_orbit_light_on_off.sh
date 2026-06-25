#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../.." && pwd)"
cd "${repo_root}"

light_settings_file="$(mktemp "${TMPDIR:-/tmp}/spear_orbit_light_settings.XXXXXX.json")"
trap 'rm -f "${light_settings_file}"' EXIT

printf '%s\n' \
  '[' \
  '  {' \
  '    "name": "light_on",' \
  '    "enabled": true,' \
  '    "intensity": 30000.0,' \
  '    "yaw_offset_degrees": 0.0,' \
  '    "pitch_offset_degrees": 0.0' \
  '  },' \
  '  {' \
  '    "name": "light_off",' \
  '    "enabled": false,' \
  '    "intensity": 0.0,' \
  '    "yaw_offset_degrees": 0.0,' \
  '    "pitch_offset_degrees": 0.0' \
  '  }' \
  ']' > "${light_settings_file}"

"${PYTHON:-python}" examples/flashlight/run_orbit_collection.py \
  --mode render \
  --orbit-spec-file examples/flashlight/orbit_spec.json \
  --light-settings-file "${light_settings_file}" \
  --output-dir examples/flashlight/orbit_collection_output \
  "$@"
