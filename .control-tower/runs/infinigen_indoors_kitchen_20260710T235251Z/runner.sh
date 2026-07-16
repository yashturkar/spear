#!/usr/bin/env bash
set -Eeuo pipefail

RUN_ID="infinigen_indoors_kitchen_20260710T235251Z"
RUN_DIR="/home/yashturkar/Workspace/spear/.control-tower/runs/${RUN_ID}"
SOURCE_ROOT="/home/yashturkar/Workspace/infinigen/outputs/infinigen_indoors_kitchen"
INFINIGEN_REPO="/home/yashturkar/Workspace/infinigen"
SPEAR_REPO="/home/yashturkar/Workspace/spear"
UE_DIR="/home/yashturkar/Linux_Unreal_Engine_5.5.4"
CONDA_SH="/home/yashturkar/miniconda3/etc/profile.d/conda.sh"
BLENDER_BIN="/home/yashturkar/Downloads/blender-5.1.2-linux-x64/blender"
WORLD_NAME="infinigen_indoors_kitchen"
MAP_PATH="/Game/SPEAR/Scenes/infinigen_indoors_kitchen/Maps/infinigen_indoors_kitchen"
MESH_DIR="/Game/SPEAR/Scenes/infinigen_indoors_kitchen/Meshes"
COARSE_DIR="${SOURCE_ROOT}/coarse"
EXPORT_RESOLUTION="1024"
EXPORT_DIR="${SOURCE_ROOT}/spear_export_r${EXPORT_RESOLUTION}"
FBX_FILE="${EXPORT_DIR}/export_scene.blend/export_scene.fbx"
STATS_SCRIPT="${RUN_DIR}/scripts/blender_source_stats.py"
LIGHT_SCRIPT="${RUN_DIR}/scripts/add_unreal_lights_and_validate.py"
VERIFY_SCRIPT="${RUN_DIR}/scripts/verify_target_paks.py"
VALIDATION_REPORT="${RUN_DIR}/validation_report.json"
SOURCE_STATS="${RUN_DIR}/source_stats.json"
STATUS_FILE="${RUN_DIR}/status.txt"
EXIT_FILE="${RUN_DIR}/exit_status.txt"
SESSION="spear_infinigen_kitchen_235251"
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
    echo "source_stats=${SOURCE_STATS}"
    echo "fbx_file=${FBX_FILE}"
    echo "map_path=${MAP_PATH}"
    echo "mesh_dir=${MESH_DIR}"
    echo "validation_report=${VALIDATION_REPORT}"
    echo "cook_log=${RUN_DIR}/logs/cook_package.log"
    echo "pak_verification=${RUN_DIR}/pak_verification_summary.txt"
    echo "live_dry_run_log=${RUN_DIR}/logs/spear_run_live_dry_run.log"
    echo "direct_live_command=cd ${SPEAR_REPO} && source ${CONDA_SH} && conda activate spear-env && python examples/flashlight/run.py --map-path ${MAP_PATH} --live-lighting-mode realistic --flashlight-profile realistic_live_flashlight_2x --scene-light-intensity-scale 0.0005 --movement-speed 600 --disable-auto-exposure --startup-warmup-seconds 3"
  } > "${STATUS_FILE}"
}

on_exit() {
  local exit_code=$?
  echo "exit_status=${exit_code}" > "${EXIT_FILE}"
  echo "finished_utc=$(timestamp)" >> "${EXIT_FILE}"
  if [[ ${exit_code} -eq 0 ]]; then
    write_status "success" "real Infinigen-Indoors kitchen generated, quality-checked, exported, imported, lit, cooked, pak-verified"
  else
    write_status "failed" "runner exited with ${exit_code}; inspect logs"
    {
      echo "first relevant error lines"
      grep -RInEi '(^|[^A-Za-z])(error|fatal|failed|assert|traceback|automationtool exiting with exitcode|quality gate)' "${RUN_DIR}/logs" "${RUN_DIR}" 2>/dev/null | head -140 || true
      echo
      echo "recent status"
      cat "${STATUS_FILE}" 2>/dev/null || true
      echo
      echo "recent generation log"
      tail -120 "${RUN_DIR}/logs/generate_selected.log" 2>/dev/null || true
      echo
      echo "recent export log"
      tail -120 "${RUN_DIR}/logs/export_r${EXPORT_RESOLUTION}.log" 2>/dev/null || true
      echo
      echo "recent import log"
      tail -120 "${RUN_DIR}/logs/import_unreal.log" 2>/dev/null || true
      echo
      echo "recent cook log"
      tail -120 "${RUN_DIR}/logs/cook_package.log" 2>/dev/null || true
    } > "${RUN_DIR}/failure_excerpt.log"
  fi
  exit "${exit_code}"
}
trap on_exit EXIT

cat > "${RUN_DIR}/manifest.json" <<JSON
{
  "schema_version": "1.0.0",
  "run_id": "${RUN_ID}",
  "started_utc": "$(timestamp)",
  "tmux_session": "${SESSION}",
  "tmux_window": "${WINDOW}",
  "attach_command": "tmux attach -t ${SESSION}",
  "world_name": "${WORLD_NAME}",
  "source_root": "${SOURCE_ROOT}",
  "coarse_blend": "${COARSE_DIR}/scene.blend",
  "source_stats": "${SOURCE_STATS}",
  "fbx_file": "${FBX_FILE}",
  "target_map_path": "${MAP_PATH}",
  "target_mesh_dir": "${MESH_DIR}",
  "unreal_engine_dir": "${UE_DIR}",
  "material_policy": "import_materials_and_textures_enabled",
  "collision_policy": "auto_generate_collision_enabled",
  "export_resolution": ${EXPORT_RESOLUTION},
  "generation_policy": "official infinigen_examples.generate_indoors Kitchen single-room; real_geometry.gin proved incompatible because the local Infinigen build lacks terrain/lib/cpu/sdf_from_mesh/sdf_from_mesh.so, so selected run uses the documented restrict_solving Kitchen counter/sink path without real_geometry and exports r1024",
  "lighting_policy": "dim movable Unreal RectLight fixtures added only after import"
}
JSON

write_status "running" "starting real Infinigen-Indoors kitchen pipeline"

echo "START_UTC:$(timestamp)"
echo "RUN_DIR:${RUN_DIR}"
echo "TMUX_SESSION:${SESSION}"
echo "TMUX_WINDOW:${WINDOW}"
echo "ATTACH_COMMAND:tmux attach -t ${SESSION}"

source "${CONDA_SH}"

run_generation() {
  local label="$1"
  local timeout_seconds="$2"
  shift 2
  rm -rf "${COARSE_DIR}"
  mkdir -p "${COARSE_DIR}"
  printf '%q ' "$@" > "${RUN_DIR}/generate_${label}_command.txt"
  printf '\n' >> "${RUN_DIR}/generate_${label}_command.txt"
  echo "START generate_${label} timeout=${timeout_seconds}"
  set +e
  timeout "${timeout_seconds}" "$@" 2>&1 | tee "${RUN_DIR}/logs/generate_${label}.log" "${SOURCE_ROOT}/logs/generate_${label}_${RUN_ID}.log"
  local rc=${PIPESTATUS[0]}
  set -e
  echo "GENERATE_${label}_EXIT:${rc}"
  return "${rc}"
}

echo "START official_infinigen_generation"
conda activate infinigen
cd "${INFINIGEN_REPO}"

QUALITY_FALLBACK_CMD=(
  python -m infinigen_examples.generate_indoors
  --seed 17
  --task coarse
  --output_folder "${COARSE_DIR}"
  -g fast_solve.gin singleroom.gin
  -p
  compose_indoors.terrain_enabled=False
  compose_indoors.solve_medium_enabled=False
  'restrict_solving.restrict_parent_rooms=["Kitchen"]'
  'restrict_solving.restrict_child_primary=["KitchenCounter"]'
  'restrict_solving.restrict_child_secondary=["Sink"]'
  'restrict_solving.consgraph_filters=["counter","sink"]'
  restrict_solving.solve_max_rooms=1
  compose_indoors.invisible_room_ceilings_enabled=True
  compose_indoors.solve_steps_large=30
  compose_indoors.solve_steps_medium=0
  compose_indoors.solve_steps_small=12
)

FAST_FALLBACK_CMD=(
  python -m infinigen_examples.generate_indoors
  --seed 18
  --task coarse
  --output_folder "${COARSE_DIR}"
  -g fast_solve.gin singleroom.gin
  -p
  compose_indoors.terrain_enabled=False
  'restrict_solving.restrict_parent_rooms=["Kitchen"]'
  'restrict_solving.restrict_child_primary=["KitchenCounter"]'
  'restrict_solving.consgraph_filters=["counter"]'
  restrict_solving.solve_max_rooms=1
  compose_indoors.invisible_room_ceilings_enabled=True
  compose_indoors.solve_medium_enabled=False
  compose_indoors.solve_small_enabled=False
  compose_indoors.solve_steps_large=20
  compose_indoors.solve_steps_medium=0
  compose_indoors.solve_steps_small=0
)

{
  echo "Previous no-fast_solve and broad fast_solve attempts showed slow solving around KitchenIsland proposals; real_geometry.gin attempts then failed because the local Infinigen build lacks terrain/lib/cpu/sdf_from_mesh/sdf_from_mesh.so."
  echo "Selected fallback remains official Infinigen-Indoors Kitchen generation and uses the local HelloRoom restrict_solving counter/sink pattern without real_geometry, with r1024 export."
} | tee "${RUN_DIR}/logs/generation_fallback_note.log"

if run_generation "restricted_counter_sink_real_geometry" 420 "${QUALITY_FALLBACK_CMD[@]}"; then
  cp "${RUN_DIR}/logs/generate_restricted_counter_sink_real_geometry.log" "${RUN_DIR}/logs/generate_selected.log"
  echo "selected_generation=restricted_counter_sink_real_geometry" > "${RUN_DIR}/selected_generation.txt"
else
  echo "quality fallback failed or timed out; trying tighter official fast_solve real_geometry fallback" | tee -a "${RUN_DIR}/logs/generation_fallback_note.log"
  if run_generation "restricted_counter_real_geometry_large_only" 360 "${FAST_FALLBACK_CMD[@]}"; then
    cp "${RUN_DIR}/logs/generate_restricted_counter_real_geometry_large_only.log" "${RUN_DIR}/logs/generate_selected.log"
    echo "selected_generation=restricted_counter_real_geometry_large_only" > "${RUN_DIR}/selected_generation.txt"
  else
    echo "Both official Infinigen-Indoors kitchen generation attempts failed." >&2
    exit 20
  fi
fi

test -s "${COARSE_DIR}/scene.blend"
ls -lh "${COARSE_DIR}/scene.blend" | tee "${RUN_DIR}/logs/source_files.log"

echo "START source_stats"
"${BLENDER_BIN}" --background "${COARSE_DIR}/scene.blend" --python "${STATS_SCRIPT}" -- "${SOURCE_STATS}" 2>&1 | tee "${RUN_DIR}/logs/source_stats.log"
python - <<'PY'
import json
from pathlib import Path
run = Path("/home/yashturkar/Workspace/spear/.control-tower/runs/infinigen_indoors_kitchen_20260710T235251Z")
stats = json.loads((run / "source_stats.json").read_text())
thresholds = {
    "mesh_object_count": 20,
    "vertices": 20000,
    "polygons": 20000,
    "material_count": 20,
    "file_size_bytes": 5_000_000,
}
failures = {key: (stats.get(key), minimum) for key, minimum in thresholds.items() if stats.get(key, 0) < minimum}
(run / "source_quality_gate.json").write_text(json.dumps({"thresholds": thresholds, "failures": failures, "passed": not failures}, indent=2, sort_keys=True) + "\n")
if failures:
    print("QUALITY_GATE_FAILED", json.dumps(failures, sort_keys=True))
    raise SystemExit(76)
print("QUALITY_GATE_PASSED", json.dumps({key: stats[key] for key in thresholds}, sort_keys=True))
PY

echo "START export_r${EXPORT_RESOLUTION}"
rm -rf "${EXPORT_DIR}"
python -m infinigen.tools.export \
  --input_folder "${COARSE_DIR}" \
  --output_folder "${EXPORT_DIR}" \
  -f fbx \
  -r "${EXPORT_RESOLUTION}" \
  2>&1 | tee "${RUN_DIR}/logs/export_r${EXPORT_RESOLUTION}.log" "${SOURCE_ROOT}/logs/export_r${EXPORT_RESOLUTION}_${RUN_ID}.log"
echo "EXPORT_R${EXPORT_RESOLUTION}_EXIT:0"
test -s "${FBX_FILE}"
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
  --player-start-y 220 \
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

echo "START live_dry_run"
set +e
tools/spear-run live "${WORLD_NAME}" --setting realistic-2x --dry-run > "${RUN_DIR}/logs/spear_run_live_dry_run.log" 2>&1
LIVE_RC=$?
set -e
echo "live_dry_run_exit=${LIVE_RC}" > "${RUN_DIR}/live_dry_run_status.txt"
if [[ "${LIVE_RC}" -ne 0 ]]; then
  {
    echo "tools/spear-run live ${WORLD_NAME} --setting realistic-2x --dry-run could not resolve the alias because docs/environment_ledger.json has no ${WORLD_NAME} entry."
    echo "Scribe follow-up required for durable ledger entry."
    echo "Direct equivalent command:"
    echo "cd ${SPEAR_REPO} && source ${CONDA_SH} && conda activate spear-env && python examples/flashlight/run.py --map-path ${MAP_PATH} --live-lighting-mode realistic --flashlight-profile realistic_live_flashlight_2x --scene-light-intensity-scale 0.0005 --movement-speed 600 --disable-auto-exposure --startup-warmup-seconds 3"
  } > "${RUN_DIR}/live_command_followup.txt"
fi

du -sh "${SOURCE_ROOT}" | tee "${RUN_DIR}/logs/artifact_sizes.log" || true
du -sh "${SPEAR_REPO}/cpp/unreal_projects/SpearSim/Content/SPEAR/Scenes/infinigen_indoors_kitchen" | tee -a "${RUN_DIR}/logs/artifact_sizes.log" || true
du -sh "${SPEAR_REPO}/cpp/unreal_projects/SpearSim/Standalone-Development/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak" | tee -a "${RUN_DIR}/logs/artifact_sizes.log" || true
du -sh "${SPEAR_REPO}/cpp/unreal_projects/SpearSim/Saved/StagedBuilds/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak" | tee -a "${RUN_DIR}/logs/artifact_sizes.log" || true
echo "DONE_UTC:$(timestamp)"
