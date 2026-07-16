#!/usr/bin/env bash
set -Eeuo pipefail

RUN_ID="restaurant_kitchen_1000sqft_20260710T212622Z"
RUN_DIR="/home/yashturkar/Workspace/spear/.control-tower/runs/${RUN_ID}"
SOURCE_ROOT="/home/yashturkar/Workspace/infinigen/outputs/restaurant_kitchen_1000sqft"
INFINIGEN_REPO="/home/yashturkar/Workspace/infinigen"
SPEAR_REPO="/home/yashturkar/Workspace/spear"
UE_DIR="/home/yashturkar/Linux_Unreal_Engine_5.5.4"
CONDA_SH="/home/yashturkar/miniconda3/etc/profile.d/conda.sh"
WORLD_NAME="restaurant_kitchen_1000sqft"
MAP_PATH="/Game/SPEAR/Scenes/restaurant_kitchen_1000sqft/Maps/restaurant_kitchen_1000sqft"
MESH_DIR="/Game/SPEAR/Scenes/restaurant_kitchen_1000sqft/Meshes"
COARSE_DIR="${SOURCE_ROOT}/coarse"
EXPORT_DIR="${SOURCE_ROOT}/spear_export_r256"
FBX_FILE="${EXPORT_DIR}/export_scene.blend/export_scene.fbx"
CREATE_SCRIPT="${RUN_DIR}/scripts/create_restaurant_kitchen_1000sqft.py"
LIGHT_SCRIPT="${RUN_DIR}/scripts/add_unreal_lights_and_validate.py"
VERIFY_SCRIPT="${RUN_DIR}/scripts/verify_target_paks.py"
VALIDATION_REPORT="${RUN_DIR}/validation_report.json"
STATUS_FILE="${RUN_DIR}/status.txt"
EXIT_FILE="${RUN_DIR}/exit_status.txt"
SESSION="spear_restaurant_kitchen_1000sqft_212622"
WINDOW="build"

mkdir -p "${RUN_DIR}/logs" "${SOURCE_ROOT}/logs"

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

write_status() {
  local status="$1"
  local note="$2"
  {
    echo "run_id=${RUN_ID}"
    echo "status=${status}"
    echo "note=${note}"
    echo "updated_utc=$(timestamp)"
    echo "tmux_session=${SESSION}"
    echo "tmux_window=${WINDOW}"
    echo "attach_command=tmux attach -t ${SESSION}"
    echo "run_dir=${RUN_DIR}"
    echo "source_root=${SOURCE_ROOT}"
    echo "coarse_blend=${COARSE_DIR}/scene.blend"
    echo "fbx_file=${FBX_FILE}"
    echo "map_path=${MAP_PATH}"
    echo "mesh_dir=${MESH_DIR}"
    echo "validation_report=${VALIDATION_REPORT}"
    echo "cook_log=${RUN_DIR}/logs/cook_package.log"
    echo "pak_verification=${RUN_DIR}/pak_verification_summary.txt"
    echo "post_cook_live_command=cd ${SPEAR_REPO} && source ${CONDA_SH} && conda activate spear-env && python examples/flashlight/run.py --map-path ${MAP_PATH} --live-lighting-mode realistic --flashlight-profile realistic_live_flashlight_2x --scene-light-intensity-scale 0.0005 --movement-speed 600 --disable-auto-exposure --startup-warmup-seconds 3"
  } > "${STATUS_FILE}"
}

on_exit() {
  local exit_code=$?
  echo "exit_status=${exit_code}" > "${EXIT_FILE}"
  echo "finished_utc=$(timestamp)" >> "${EXIT_FILE}"
  if [[ ${exit_code} -eq 0 ]]; then
    write_status "success" "generated, exported, imported, lit, cooked, and pak-verified"
  else
    write_status "failed" "runner exited with ${exit_code}; inspect logs"
    {
      echo "first relevant error lines"
      grep -RInEi '(^|[^A-Za-z])(error|fatal|failed|assert|traceback|automationtool exiting with exitcode)' "${RUN_DIR}/logs" | head -100 || true
      echo
      echo "recent cook log"
      tail -120 "${RUN_DIR}/logs/cook_package.log" 2>/dev/null || true
      echo
      echo "recent import log"
      tail -120 "${RUN_DIR}/logs/import_unreal.log" 2>/dev/null || true
    } > "${RUN_DIR}/failure_excerpt.log"
  fi
  exit "${exit_code}"
}
trap on_exit EXIT

{
  echo "{"
  echo "  \"schema_version\": \"1.0.0\","
  echo "  \"run_id\": \"${RUN_ID}\","
  echo "  \"started_utc\": \"$(timestamp)\","
  echo "  \"tmux_session\": \"${SESSION}\","
  echo "  \"tmux_window\": \"${WINDOW}\","
  echo "  \"attach_command\": \"tmux attach -t ${SESSION}\","
  echo "  \"world_name\": \"${WORLD_NAME}\","
  echo "  \"source_root\": \"${SOURCE_ROOT}\","
  echo "  \"coarse_blend\": \"${COARSE_DIR}/scene.blend\","
  echo "  \"fbx_file\": \"${FBX_FILE}\","
  echo "  \"target_map_path\": \"${MAP_PATH}\","
  echo "  \"target_mesh_dir\": \"${MESH_DIR}\","
  echo "  \"unreal_engine_dir\": \"${UE_DIR}\","
  echo "  \"material_policy\": \"import_materials_and_textures_enabled\","
  echo "  \"collision_policy\": \"auto_generate_collision_enabled\","
  echo "  \"export_resolution\": 256,"
  echo "  \"floor_area_sqft_approx\": 992,"
  echo "  \"lighting_policy\": \"dim movable Unreal RectLight fixtures plus reduced setup lights\""
  echo "}"
} > "${RUN_DIR}/manifest.json"

write_status "running" "starting generation"

echo "START_UTC:$(timestamp)"
echo "RUN_DIR:${RUN_DIR}"
echo "TMUX_SESSION:${SESSION}"
echo "TMUX_WINDOW:${WINDOW}"
echo "ATTACH_COMMAND:tmux attach -t ${SESSION}"

source "${CONDA_SH}"

echo "START create_scene"
conda activate infinigen
cd "${INFINIGEN_REPO}"
python "${CREATE_SCRIPT}" --output-folder "${COARSE_DIR}" 2>&1 | tee "${RUN_DIR}/logs/create_scene.log" "${SOURCE_ROOT}/logs/create_scene_${RUN_ID}.log"
echo "CREATE_SCENE_EXIT:0"
ls -lh "${COARSE_DIR}/scene.blend" | tee "${RUN_DIR}/logs/source_files.log"

echo "START export_r256"
rm -rf "${EXPORT_DIR}"
python -m infinigen.tools.export \
  --input_folder "${COARSE_DIR}" \
  --output_folder "${EXPORT_DIR}" \
  -f fbx \
  -r 256 \
  2>&1 | tee "${RUN_DIR}/logs/export_r256.log" "${SOURCE_ROOT}/logs/export_r256_${RUN_ID}.log"
echo "EXPORT_R256_EXIT:0"
ls -lh "${FBX_FILE}" | tee -a "${RUN_DIR}/logs/source_files.log"
find "${EXPORT_DIR}/export_scene.blend" -type f | sort > "${RUN_DIR}/exported_files.txt"

echo "START unreal_import"
conda activate spear-env
cd "${SPEAR_REPO}"
python tools/run_editor_script.py \
  --unreal-engine-dir "${UE_DIR}" \
  --launch-mode full \
  --render-offscreen \
  --script "${SPEAR_REPO}/examples/flashlight/setup_infinigen_indoors.py" \
  --fbx-file "${FBX_FILE}" \
  --mesh-dir "${MESH_DIR}" \
  --map-path "${MAP_PATH}" \
  --replace-existing-assets \
  --replace-existing-map \
  --player-start-x 0 \
  --player-start-y 260 \
  --player-start-z 120 \
  --player-start-yaw -90 \
  2>&1 | tee "${RUN_DIR}/logs/import_unreal.log" "${SOURCE_ROOT}/logs/import_unreal_${RUN_ID}.log"
echo "UNREAL_IMPORT_EXIT:0"

echo "START add_unreal_lights_validate"
python tools/run_editor_script.py \
  --unreal-engine-dir "${UE_DIR}" \
  --launch-mode full \
  --render-offscreen \
  --script "${LIGHT_SCRIPT}" \
  --map-path "${MAP_PATH}" \
  --mesh-dir "${MESH_DIR}" \
  --validation-report "${VALIDATION_REPORT}" \
  2>&1 | tee "${RUN_DIR}/logs/add_unreal_lights_validate.log" "${SOURCE_ROOT}/logs/add_unreal_lights_validate_${RUN_ID}.log"
echo "ADD_UNREAL_LIGHTS_VALIDATE_EXIT:0"
python -m json.tool "${VALIDATION_REPORT}" | tee "${RUN_DIR}/logs/validation_report_pre_cook.log"

echo "START cook_package"
mapfile -t LEDGER_MAPS < <(python - <<'PY'
import json
from pathlib import Path
ledger = json.loads(Path("docs/environment_ledger.json").read_text())
for env in ledger["environments"]:
    map_path = env.get("unreal_map_path")
    if map_path:
        print(map_path)
PY
)
COOK_MAPS=("${LEDGER_MAPS[@]}" "${MAP_PATH}")
printf '%s\n' "${COOK_MAPS[@]}" > "${RUN_DIR}/cook_maps.txt"
python tools/run_uat.py \
  --unreal-engine-dir "${UE_DIR}" \
  --clean-archive-dir \
  --skip-cook-default-maps \
  --cook-maps "${COOK_MAPS[@]}" \
  -clean -cook -stage -package -archive -pak -skipbuild \
  2>&1 | tee "${RUN_DIR}/logs/cook_package.log" "${SOURCE_ROOT}/logs/cook_package_${RUN_ID}.log"
echo "COOK_EXIT:0"

echo "START verify_paks"
python "${VERIFY_SCRIPT}" 2>&1 | tee "${RUN_DIR}/logs/verify_target_paks.log"
echo "VERIFY_PAKS_EXIT:0"

du -sh "${SPEAR_REPO}/cpp/unreal_projects/SpearSim/Content/SPEAR/Scenes/restaurant_kitchen_1000sqft" | tee "${RUN_DIR}/logs/artifact_sizes.log" || true
du -sh "${SPEAR_REPO}/cpp/unreal_projects/SpearSim/Standalone-Development/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak" | tee -a "${RUN_DIR}/logs/artifact_sizes.log" || true
du -sh "${SPEAR_REPO}/cpp/unreal_projects/SpearSim/Saved/StagedBuilds/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak" | tee -a "${RUN_DIR}/logs/artifact_sizes.log" || true
echo "DONE_UTC:$(timestamp)"
