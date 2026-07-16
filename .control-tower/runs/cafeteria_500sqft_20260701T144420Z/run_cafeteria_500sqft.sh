#!/usr/bin/env bash
set -Eeuo pipefail

RUN_DIR="/home/yashturkar/Workspace/spear/.control-tower/runs/cafeteria_500sqft_20260701T144420Z"
SOURCE_ROOT="/home/yashturkar/Workspace/infinigen/outputs/cafeteria_500sqft"
INFINIGEN_REPO="/home/yashturkar/Workspace/infinigen"
SPEAR_REPO="/home/yashturkar/Workspace/spear"
UE_DIR="/home/yashturkar/Linux_Unreal_Engine_5.5.4"
WORLD_NAME="cafeteria_500sqft"
MAP_PATH="/Game/SPEAR/Scenes/cafeteria_500sqft/Maps/cafeteria_500sqft"
MESH_DIR="/Game/SPEAR/Scenes/cafeteria_500sqft/Meshes"
CREATE_SCRIPT="${SOURCE_ROOT}/scripts/create_cafeteria_500sqft.py"
COARSE_DIR="${SOURCE_ROOT}/coarse"
EXPORT_DIR="${SOURCE_ROOT}/spear_export_r256"
FBX_FILE="${EXPORT_DIR}/export_scene.blend/export_scene.fbx"

mkdir -p "${RUN_DIR}/logs" "${SOURCE_ROOT}/logs"

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
    echo "SOURCE_ROOT:${SOURCE_ROOT}"
    echo "COARSE_BLEND:${COARSE_DIR}/scene.blend"
    echo "EXPORT_DIR:${EXPORT_DIR}"
    echo "FBX_FILE:${FBX_FILE}"
    echo "MAP_PATH:${MAP_PATH}"
    echo "MESH_DIR:${MESH_DIR}"
    echo "FLASHLIGHT_COMMAND:cd ${SPEAR_REPO} && conda activate spear-env && python examples/flashlight/run.py --map-path ${MAP_PATH} --movement-speed 600 --disable-scene-lights"
  } > "${RUN_DIR}/status.txt"
  cp "${RUN_DIR}/status.txt" "${SOURCE_ROOT}/status_cafeteria_500sqft_20260701T144420Z.txt"
}

on_exit() {
  local exit_code=$?
  if [[ ${exit_code} -eq 0 ]]; then
    write_status "success" "create, export, import, and cook completed"
  else
    write_status "failed" "runner exited with ${exit_code}; inspect logs"
  fi
  exit "${exit_code}"
}
trap on_exit EXIT

source "/home/yashturkar/miniconda3/etc/profile.d/conda.sh"

{
  echo "schema_version: 1.0.0"
  echo "world_name: ${WORLD_NAME}"
  echo "started_utc: $(timestamp)"
  echo "run_dir: ${RUN_DIR}"
  echo "source_root: ${SOURCE_ROOT}"
  echo "target_map_path: ${MAP_PATH}"
  echo "target_mesh_dir: ${MESH_DIR}"
  echo "infinigen_repo: ${INFINIGEN_REPO}"
  echo "spear_repo: ${SPEAR_REPO}"
  echo "unreal_engine_dir: ${UE_DIR}"
  echo "material_policy: import_materials_and_textures_enabled"
} > "${RUN_DIR}/manifest.yaml"

write_status "running" "starting generated Blender cafeteria scene"

echo "START_UTC:$(timestamp)"
echo "RUN_DIR:${RUN_DIR}"
echo "TMUX_SESSION:spear_cafeteria_500sqft_20260701T144420Z"
echo "TMUX_WINDOW:build"

echo "START create_scene"
conda activate infinigen
cd "${INFINIGEN_REPO}"
python "${CREATE_SCRIPT}" 2>&1 | tee "${RUN_DIR}/logs/create_scene.log" "${SOURCE_ROOT}/logs/create_scene_20260701T144420Z.log"
echo "CREATE_SCENE_EXIT:0"

echo "START export_r256"
rm -rf "${EXPORT_DIR}"
python -m infinigen.tools.export \
  --input_folder "${COARSE_DIR}" \
  --output_folder "${EXPORT_DIR}" \
  -f fbx \
  -r 256 \
  2>&1 | tee "${RUN_DIR}/logs/export_r256.log" "${SOURCE_ROOT}/logs/export_r256_20260701T144420Z.log"
echo "EXPORT_R256_EXIT:0"
ls -lh "${FBX_FILE}"
find "${EXPORT_DIR}/export_scene.blend" -type f \( -name '*DIFFUSE.png' -o -name '*NORMAL.png' -o -name '*ROUGHNESS.png' -o -name '*METAL.png' -o -name '*TRANSMISSION.png' \) | wc -l | awk '{print "EXPORTED_TEXTURE_FILE_COUNT:" $1}'

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
  --no-auto-generate-collision \
  2>&1 | tee "${RUN_DIR}/logs/import_unreal.log" "${SOURCE_ROOT}/logs/import_unreal_20260701T144420Z.log"
echo "UNREAL_IMPORT_EXIT:0"

echo "START cook_package"
python tools/run_uat.py \
  --unreal-engine-dir "${UE_DIR}" \
  --cook-maps "${MAP_PATH}" \
  -cook -stage -package -archive -pak -skipbuild \
  2>&1 | tee "${RUN_DIR}/logs/cook_package.log" "${SOURCE_ROOT}/logs/cook_20260701T144420Z.log"
echo "COOK_EXIT:0"

du -sh "${SPEAR_REPO}/cpp/unreal_projects/SpearSim/Content/SPEAR/Scenes/cafeteria_500sqft" || true
du -sh "${SPEAR_REPO}/cpp/unreal_projects/SpearSim/Standalone-Development" || true
du -sh "${SPEAR_REPO}/cpp/unreal_projects/SpearSim/Saved/StagedBuilds/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak" || true
echo "DONE_UTC:$(timestamp)"
