#!/usr/bin/env bash
set -o pipefail

RUN_ROOT="/home/yashturkar/Workspace/infinigen/outputs/one_bed_apartment_import_light_20260626T180612Z"
LOG_DIR="${RUN_ROOT}/logs"
SUMMARY_LOG="${LOG_DIR}/summary.log"
IMPORT_LOG="${LOG_DIR}/import_light_r256.log"
COOK_LOG="${LOG_DIR}/cook_package_archive.log"

PYTHON="/home/yashturkar/miniconda3/envs/spear-env/bin/python"
SPEAR_ROOT="/home/yashturkar/Workspace/spear"
UNREAL_ENGINE_DIR="/home/yashturkar/Linux_Unreal_Engine_5.5.4"
IMPORT_SCRIPT="${SPEAR_ROOT}/examples/flashlight/setup_infinigen_indoors.py"
FBX_FILE="/home/yashturkar/Workspace/infinigen/outputs/one_bed_apartment_import_retry2_20260626T164341Z/export_r256/export_scene.blend/export_scene.fbx"
MESH_DIR="/Game/SPEAR/Scenes/one_bed_apartment/Meshes"
MAP_PATH="/Game/SPEAR/Scenes/one_bed_apartment/Maps/one_bed_apartment"

mkdir -p "${LOG_DIR}"

log_summary() {
    echo "[$(date --iso-8601=seconds)] $*" | tee -a "${SUMMARY_LOG}"
}

log_recent_memory_lines() {
    if command -v rg >/dev/null 2>&1; then
        rg -n "Killed|exit status 137|Out of memory|OOM|Required Memory Estimate|RequiredMemory|MemoryLimit|Maximum resident set size" "${IMPORT_LOG}" | tail -n 40 | tee -a "${SUMMARY_LOG}" || true
    else
        grep -Ein "Killed|exit status 137|Out of memory|OOM|Required Memory Estimate|RequiredMemory|MemoryLimit|Maximum resident set size" "${IMPORT_LOG}" | tail -n 40 | tee -a "${SUMMARY_LOG}" || true
    fi
}

cd "${SPEAR_ROOT}" || exit 1

log_summary "Light import workflow started in tmux session spear_one_bed_apartment_import_light"
log_summary "Run root: ${RUN_ROOT}"
log_summary "Input FBX: ${FBX_FILE}"
log_summary "Target mesh dir: ${MESH_DIR}"
log_summary "Target map: ${MAP_PATH}"

IMPORT_CMD=(
    "${PYTHON}" "${SPEAR_ROOT}/tools/run_editor_script.py"
    --unreal-engine-dir "${UNREAL_ENGINE_DIR}"
    --launch-mode full
    --render-offscreen
    --script "${IMPORT_SCRIPT}"
    --fbx-file "${FBX_FILE}"
    --mesh-dir "${MESH_DIR}"
    --map-path "${MAP_PATH}"
    --replace-existing-assets
    --replace-existing-map
    --no-auto-generate-collision
    --no-import-materials
    --no-import-textures
)

log_summary "START import_light_r256"
log_summary "COMMAND import_light_r256: ${IMPORT_CMD[*]}"
/usr/bin/time -v "${IMPORT_CMD[@]}" 2>&1 | tee "${IMPORT_LOG}"
import_status=${PIPESTATUS[0]}
log_summary "END import_light_r256 exit_code=${import_status} log=${IMPORT_LOG}"

if [[ "${import_status}" -ne 0 ]]; then
    log_summary "Import failed; keeping tmux shell open for inspection."
    log_summary "Relevant memory lines from import log:"
    log_recent_memory_lines
    exec "${SHELL:-/bin/bash}" -l
fi

COOK_CMD=(
    "${PYTHON}" "${SPEAR_ROOT}/tools/run_uat.py"
    --unreal-engine-dir "${UNREAL_ENGINE_DIR}"
    --cook-maps "${MAP_PATH}"
    -cook
    -stage
    -package
    -archive
    -pak
    -skipbuild
)

log_summary "START cook_package_archive"
log_summary "COMMAND cook_package_archive: ${COOK_CMD[*]}"
/usr/bin/time -v "${COOK_CMD[@]}" 2>&1 | tee "${COOK_LOG}"
cook_status=${PIPESTATUS[0]}
log_summary "END cook_package_archive exit_code=${cook_status} log=${COOK_LOG}"
log_summary "Runner exiting with status ${cook_status}"

exec "${SHELL:-/bin/bash}" -l
