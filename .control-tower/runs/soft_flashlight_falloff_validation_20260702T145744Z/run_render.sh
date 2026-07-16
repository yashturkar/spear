#!/usr/bin/env bash
set -euo pipefail

repo_root="/home/yashturkar/Workspace/spear"
run_dir="${repo_root}/.control-tower/runs/soft_flashlight_falloff_validation_20260702T145744Z"
log_file="${run_dir}/render.log"
status_file="${run_dir}/status.txt"
output_dir="examples/flashlight/orbit_collection_output_soft_falloff_validation"

cd "${repo_root}"

{
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "repo_root=${repo_root}"
  echo "run_dir=${run_dir}"
  echo "output_dir=${output_dir}"
  echo "command=examples/flashlight/run_orbit_workflow.sh render --python /home/yashturkar/miniconda3/envs/spear-env/bin/python --orbit-spec-file examples/flashlight/orbit_spec.json --light-settings-file ${run_dir}/light_settings_soft_falloff_validation.json --output-dir ${output_dir} --scene-light-intensity-scale 0.2 --intensity 1200 --attenuation-radius 650 --inner-cone-angle 2 --outer-cone-angle 60 --source-radius 12 --soft-source-radius 80 --indirect-lighting-intensity 0"
} > "${status_file}"

set +e
examples/flashlight/run_orbit_workflow.sh render \
  --python /home/yashturkar/miniconda3/envs/spear-env/bin/python \
  --orbit-spec-file examples/flashlight/orbit_spec.json \
  --light-settings-file "${run_dir}/light_settings_soft_falloff_validation.json" \
  --output-dir "${output_dir}" \
  --scene-light-intensity-scale 0.2 \
  --intensity 1200 \
  --attenuation-radius 650 \
  --inner-cone-angle 2 \
  --outer-cone-angle 60 \
  --source-radius 12 \
  --soft-source-radius 80 \
  --indirect-lighting-intensity 0 \
  2>&1 | tee "${log_file}"
exit_status=${PIPESTATUS[0]}
set -e

{
  echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "exit_status=${exit_status}"
} >> "${status_file}"

exit "${exit_status}"
