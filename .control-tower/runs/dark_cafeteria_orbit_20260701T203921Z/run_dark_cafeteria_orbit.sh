#!/usr/bin/env bash
set -Eeuo pipefail

RUN_DIR="/home/yashturkar/Workspace/spear/.control-tower/runs/dark_cafeteria_orbit_20260701T203921Z"
SPEAR_REPO="/home/yashturkar/Workspace/spear"
UE_DIR="/home/yashturkar/Linux_Unreal_Engine_5.5.4"
PYTHON_BIN="/home/yashturkar/miniconda3/envs/spear-env/bin/python"
SOURCE_MAP="/Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2"
TARGET_MAP="/Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2_flashlight_validation_dark"
OUTPUT_DIR="examples/flashlight/orbit_collection_output_validation_dark_map"
TMUX_SESSION="spear_dark_cafeteria_orbit_20260701T203921Z"
TMUX_WINDOW="run"

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

write_status() {
  local status="$1"
  local note="$2"
  {
    echo "STATUS:${status}"
    echo "NOTE:${note}"
    echo "UPDATED_UTC:$(timestamp)"
    echo "RUN_DIR:${RUN_DIR}"
    echo "TMUX_SESSION:${TMUX_SESSION}"
    echo "TMUX_WINDOW:${TMUX_WINDOW}"
    echo "ATTACH_COMMAND:tmux attach -t ${TMUX_SESSION}"
    echo "SOURCE_MAP:${SOURCE_MAP}"
    echo "TARGET_MAP:${TARGET_MAP}"
    echo "OUTPUT_DIR:${SPEAR_REPO}/${OUTPUT_DIR}"
    echo "DARK_MAP_REPORT:${RUN_DIR}/dark_map_report.json"
    echo "LUMA_SUMMARY:${RUN_DIR}/luma_summary.json"
  } > "${RUN_DIR}/status.txt"
}

on_exit() {
  local exit_code=$?
  if [[ ${exit_code} -eq 0 ]]; then
    write_status "success" "dark map creation, cook/package, orbit render, and luma summary completed"
  else
    write_status "failed" "runner exited with ${exit_code}; inspect ${RUN_DIR}/logs/tmux_run.log"
  fi
  exit "${exit_code}"
}
trap on_exit EXIT

mkdir -p "${RUN_DIR}/logs"

{
  echo "schema_version: 1.0.0"
  echo "run_dir: ${RUN_DIR}"
  echo "started_utc: $(timestamp)"
  echo "spear_repo: ${SPEAR_REPO}"
  echo "unreal_engine_dir: ${UE_DIR}"
  echo "source_map_path: ${SOURCE_MAP}"
  echo "target_map_path: ${TARGET_MAP}"
  echo "validation_output_dir: ${SPEAR_REPO}/${OUTPUT_DIR}"
  echo "tmux_session: ${TMUX_SESSION}"
  echo "tmux_window: ${TMUX_WINDOW}"
  echo "attach_command: tmux attach -t ${TMUX_SESSION}"
} > "${RUN_DIR}/manifest.yaml"

write_status "running" "starting dark map editor job"

source "/home/yashturkar/miniconda3/etc/profile.d/conda.sh"
conda activate spear-env
cd "${SPEAR_REPO}"

echo "START_UTC:$(timestamp)"
echo "RUN_DIR:${RUN_DIR}"
echo "TMUX_SESSION:${TMUX_SESSION}"
echo "TMUX_WINDOW:${TMUX_WINDOW}"
echo "ATTACH_COMMAND:tmux attach -t ${TMUX_SESSION}"

echo "START create_dark_map"
echo "COMMAND:${PYTHON_BIN} tools/run_editor_script.py --unreal-engine-dir ${UE_DIR} --launch-mode full --render-offscreen --script ${RUN_DIR}/scripts/create_dark_cafeteria_map.py --source-map-path ${SOURCE_MAP} --target-map-path ${TARGET_MAP} --replace-existing-map --validation-report ${RUN_DIR}/dark_map_report.json"
"${PYTHON_BIN}" tools/run_editor_script.py \
  --unreal-engine-dir "${UE_DIR}" \
  --launch-mode full \
  --render-offscreen \
  --script "${RUN_DIR}/scripts/create_dark_cafeteria_map.py" \
  --source-map-path "${SOURCE_MAP}" \
  --target-map-path "${TARGET_MAP}" \
  --replace-existing-map \
  --validation-report "${RUN_DIR}/dark_map_report.json" \
  2>&1 | tee "${RUN_DIR}/logs/create_dark_map.log"
echo "CREATE_DARK_MAP_EXIT:0"
python -m json.tool "${RUN_DIR}/dark_map_report.json" | tee "${RUN_DIR}/logs/dark_map_report_pre_cook.log"

write_status "running" "dark map saved; starting cook/package"
echo "START cook_package"
echo "COMMAND:${PYTHON_BIN} tools/run_uat.py --unreal-engine-dir ${UE_DIR} --cook-maps ${TARGET_MAP} -cook -stage -package -archive -pak -skipbuild"
"${PYTHON_BIN}" tools/run_uat.py \
  --unreal-engine-dir "${UE_DIR}" \
  --cook-maps "${TARGET_MAP}" \
  -cook -stage -package -archive -pak -skipbuild \
  2>&1 | tee "${RUN_DIR}/logs/cook_package.log"
echo "COOK_PACKAGE_EXIT:0"

write_status "running" "cook/package completed; starting orbit render validation"
echo "START orbit_render_validation"
echo "COMMAND:examples/flashlight/run_orbit_workflow.sh render --python ${PYTHON_BIN} --map-path ${TARGET_MAP} --output-dir ${OUTPUT_DIR}"
examples/flashlight/run_orbit_workflow.sh render \
  --python "${PYTHON_BIN}" \
  --map-path "${TARGET_MAP}" \
  --output-dir "${OUTPUT_DIR}" \
  2>&1 | tee "${RUN_DIR}/logs/orbit_render_validation.log"
echo "ORBIT_RENDER_VALIDATION_EXIT:0"

write_status "running" "orbit render completed; summarizing metadata"
echo "START summarize_validation"
echo "COMMAND:${PYTHON_BIN} ${RUN_DIR}/scripts/summarize_dark_map_validation.py ${SPEAR_REPO}/${OUTPUT_DIR} ${RUN_DIR}/luma_summary.json"
"${PYTHON_BIN}" "${RUN_DIR}/scripts/summarize_dark_map_validation.py" \
  "${SPEAR_REPO}/${OUTPUT_DIR}" \
  "${RUN_DIR}/luma_summary.json" \
  2>&1 | tee "${RUN_DIR}/logs/luma_summary.log"
echo "SUMMARIZE_VALIDATION_EXIT:0"

echo "DONE_UTC:$(timestamp)"
