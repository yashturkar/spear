#!/usr/bin/env bash
set -uo pipefail

RUN_ID="cook_infinigen_kitchen_live_20260711T010155Z"
RUN_DIR="/home/yashturkar/Workspace/spear/.control-tower/runs/${RUN_ID}"
REPO="/home/yashturkar/Workspace/spear"
CONDA_SH="/home/yashturkar/miniconda3/etc/profile.d/conda.sh"
SESSION="cook_kitchen_live_010155"
WINDOW="cook"
COOK_LOG="${RUN_DIR}/cook_package.log"
STATUS_FILE="${RUN_DIR}/status.txt"
EXIT_FILE="${RUN_DIR}/exit_status.txt"
FAILURE_EXCERPT="${RUN_DIR}/failure_excerpt.log"
MANIFEST="${RUN_DIR}/manifest.json"
TARGET_MAP="/Game/SPEAR/Scenes/infinigen_indoors_kitchen/Maps/infinigen_indoors_kitchen"
ARCHIVE_PAK="${REPO}/cpp/unreal_projects/SpearSim/Standalone-Development/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak"
STAGED_PAK="${REPO}/cpp/unreal_projects/SpearSim/Saved/StagedBuilds/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak"

cd "$REPO" || exit 2

mapfile -t MAPS < <(
  python - <<'PY'
import json
from pathlib import Path
ledger = json.loads(Path("docs/environment_ledger.json").read_text())
seen = set()
for env in ledger["environments"]:
    map_path = env.get("unreal_map_path")
    if map_path and map_path not in seen:
        seen.add(map_path)
        print(map_path)
PY
)

{
  echo "run_id=${RUN_ID}"
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "status=running"
  echo "tmux_session=${SESSION}"
  echo "tmux_window=${WINDOW}"
  echo "attach_command=tmux attach -t ${SESSION}"
  echo "target_map=${TARGET_MAP}"
  echo "cook_log=${COOK_LOG}"
  echo "archive_pak=${ARCHIVE_PAK}"
  echo "staged_pak=${STAGED_PAK}"
  echo "verification_summary=${RUN_DIR}/pak_verification_summary.txt"
  echo "direct_dry_run_log=${RUN_DIR}/direct_flashlight_dry_check.log"
  echo "wrapper_dry_run_log=${RUN_DIR}/spear_run_live_dry_run.log"
} | tee "$STATUS_FILE"

{
  echo "run_id=${RUN_ID}"
  echo "objective=clean Linux UAT cook/stage/package/archive/pak for active standalone live package after Infinigen kitchen bright ceiling light edits"
  echo "map_count=${#MAPS[@]}"
  printf 'maps='
  printf '%s+' "${MAPS[@]}"
  echo
  echo "command=source ${CONDA_SH} && conda activate spear-env && python tools/run_uat.py --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 --clean-archive-dir --skip-cook-default-maps --cook-maps ${MAPS[*]} -clean -cook -stage -package -archive -pak -skipbuild"
  echo
} | tee "$COOK_LOG"

python - <<PY > "$MANIFEST"
import json
from pathlib import Path
run_dir = Path("${RUN_DIR}")
manifest = {
    "run_id": "${RUN_ID}",
    "target_map": "${TARGET_MAP}",
    "tmux_session": "${SESSION}",
    "tmux_window": "${WINDOW}",
    "attach_command": "tmux attach -t ${SESSION}",
    "cook_log": "${COOK_LOG}",
    "archive_pak": "${ARCHIVE_PAK}",
    "staged_pak": "${STAGED_PAK}",
    "map_count": len(${MAPS[@]+["placeholder"]}),
}
manifest["files"] = sorted(str(p.relative_to(run_dir)) for p in run_dir.glob("*"))
print(json.dumps(manifest, indent=2, sort_keys=True))
PY

{
  source "$CONDA_SH"
  conda activate spear-env
  python tools/run_uat.py \
    --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 \
    --clean-archive-dir \
    --skip-cook-default-maps \
    --cook-maps "${MAPS[@]}" \
    -clean -cook -stage -package -archive -pak -skipbuild
} 2>&1 | tee -a "$COOK_LOG"
uat_rc=${PIPESTATUS[0]}

echo "uat_exit_status=${uat_rc}" | tee "$EXIT_FILE" | tee -a "$COOK_LOG" >/dev/null
echo "uat_finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$EXIT_FILE" | tee -a "$COOK_LOG" >/dev/null

verify_rc=99
direct_rc=99
wrapper_rc=99
if [[ "$uat_rc" -eq 0 ]]; then
  python "$RUN_DIR/verify_kitchen_paks.py" > "$RUN_DIR/verify_kitchen_paks.log" 2>&1
  verify_rc=$?

  {
    source "$CONDA_SH"
    conda activate spear-env
    python "$RUN_DIR/direct_flashlight_dry_check.py"
  } > "$RUN_DIR/direct_flashlight_dry_check.log" 2>&1
  direct_rc=$?

  {
    ./tools/spear-run live infinigen_indoors_kitchen --setting realistic-2x --dry-run
  } > "$RUN_DIR/spear_run_live_dry_run.log" 2>&1
  wrapper_rc=$?
else
  {
    echo "first relevant error lines from ${COOK_LOG}"
    grep -nEi '(^|[^A-Za-z])(error|fatal|failed|ensure condition failed|unknown cook failure|cook failed|automationtool exiting with exitcode)' "$COOK_LOG" | head -80 || true
    echo
    echo "last 120 log lines"
    tail -120 "$COOK_LOG" || true
  } > "$FAILURE_EXCERPT"
fi

echo "verify_exit_status=${verify_rc}" | tee -a "$EXIT_FILE" | tee -a "$COOK_LOG" >/dev/null
echo "direct_dry_run_exit_status=${direct_rc}" | tee -a "$EXIT_FILE" | tee -a "$COOK_LOG" >/dev/null
echo "wrapper_dry_run_exit_status=${wrapper_rc}" | tee -a "$EXIT_FILE" | tee -a "$COOK_LOG" >/dev/null
echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$EXIT_FILE" | tee -a "$COOK_LOG" >/dev/null

final_status="success"
exit_code=0
if [[ "$uat_rc" -ne 0 ]]; then
  final_status="failed"
  exit_code="$uat_rc"
elif [[ "$verify_rc" -ne 0 ]]; then
  final_status="failed"
  exit_code="$verify_rc"
elif [[ "$direct_rc" -ne 0 ]]; then
  final_status="failed"
  exit_code="$direct_rc"
elif [[ "$wrapper_rc" -ne 0 ]]; then
  final_status="failed"
  exit_code="$wrapper_rc"
fi

{
  echo "run_id=${RUN_ID}"
  echo "status=${final_status}"
  echo "tmux_session=${SESSION}"
  echo "tmux_window=${WINDOW}"
  echo "attach_command=tmux attach -t ${SESSION}"
  echo "uat_exit_status=${uat_rc}"
  echo "verify_exit_status=${verify_rc}"
  echo "direct_dry_run_exit_status=${direct_rc}"
  echo "wrapper_dry_run_exit_status=${wrapper_rc}"
  echo "exit_status=${exit_code}"
  echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "cook_log=${COOK_LOG}"
  echo "failure_excerpt=${FAILURE_EXCERPT}"
  echo "verify_log=${RUN_DIR}/verify_kitchen_paks.log"
  echo "verification_summary=${RUN_DIR}/pak_verification_summary.txt"
  echo "verification_summary_json=${RUN_DIR}/pak_verification_summary.json"
  echo "archive_pak_list=${RUN_DIR}/archive_pak_list.log"
  echo "staged_pak_list=${RUN_DIR}/staged_pak_list.log"
  echo "direct_dry_run_log=${RUN_DIR}/direct_flashlight_dry_check.log"
  echo "wrapper_dry_run_log=${RUN_DIR}/spear_run_live_dry_run.log"
} | tee "$STATUS_FILE"

exit "$exit_code"
