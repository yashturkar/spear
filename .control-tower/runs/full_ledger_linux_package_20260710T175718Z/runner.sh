#!/usr/bin/env bash
set -uo pipefail

RUN_DIR="/home/yashturkar/Workspace/spear/.control-tower/runs/full_ledger_linux_package_20260710T175718Z"
REPO="/home/yashturkar/Workspace/spear"
CONDA_SH="/home/yashturkar/miniconda3/etc/profile.d/conda.sh"
SESSION="full_ledger_pkg_175718"
WINDOW="cook"
COOK_LOG="$RUN_DIR/cook_package.log"
STATUS_FILE="$RUN_DIR/status.txt"
EXIT_FILE="$RUN_DIR/exit_status.txt"
FAILURE_EXCERPT="$RUN_DIR/failure_excerpt.log"

MAPS=(
  "/Game/JapaneseOffice/Maps/Demonstration"
  "/Game/JapaneseOffice/Maps/Demonstration_Dark"
  "/Game/SPEAR/Scenes/apartment_0000/Maps/apartment_0000"
  "/Game/SPEAR/Scenes/debug_0000/Maps/debug_0000"
  "/Game/SPEAR/Scenes/debug_0001/Maps/debug_0001"
  "/Game/Fab/Abandoned_Room_Interior/Maps/AbandonedRoom"
  "/Game/SPEAR/Scenes/infinigen_indoors_0000/Maps/infinigen_indoors_0000"
  "/Game/SPEAR/Scenes/one_bed_apartment/Maps/one_bed_apartment"
  "/Game/SPEAR/Scenes/college_classroom/Maps/college_classroom"
  "/Game/SPEAR/Scenes/cafeteria_500sqft/Maps/cafeteria_500sqft"
  "/Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2"
  "/Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2_flashlight_validation_dark"
  "/Game/StarterContent/Maps/Advanced_Lighting"
  "/Game/StarterContent/Maps/Minimal_Default"
  "/Game/StarterContent/Maps/StarterMap"
  "/Game/ThirdPerson/Maps/ThirdPersonMap"
  "/Game/VehicleTemplate/Maps/VehicleExampleMap"
  "/Game/VehicleTemplate/Maps/VehicleOffroadExampleMap"
)

cd "$REPO" || exit 2

{
  echo "run_id=full_ledger_linux_package_20260710T175718Z"
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "status=running"
  echo "tmux_session=$SESSION"
  echo "tmux_window=$WINDOW"
  echo "attach_command=tmux attach -t $SESSION"
  echo "cook_log=$COOK_LOG"
  echo "verification_script=$RUN_DIR/verify_paks.py"
  echo "verification_summary=$RUN_DIR/verification_summary.txt"
  echo "coverage_table=$RUN_DIR/coverage_table.md"
  echo "archive_pak=$REPO/cpp/unreal_projects/SpearSim/Standalone-Development/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak"
  echo "staged_pak=$REPO/cpp/unreal_projects/SpearSim/Saved/StagedBuilds/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak"
} | tee "$STATUS_FILE"

{
  echo "run_id=full_ledger_linux_package_20260710T175718Z"
  echo "objective=clean Linux UAT cook/stage/package/archive/pak for every non-null docs/environment_ledger.json unreal_map_path"
  echo "map_count=${#MAPS[@]}"
  printf 'maps='
  printf '%s+' "${MAPS[@]}"
  echo
  echo "command=source $CONDA_SH && conda activate spear-env && python tools/run_uat.py --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 --clean-archive-dir --skip-cook-default-maps --cook-maps ${MAPS[*]} -clean -cook -stage -package -archive -pak -skipbuild"
  echo
} | tee "$COOK_LOG"

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

echo "uat_exit_status=$uat_rc" | tee "$EXIT_FILE" | tee -a "$COOK_LOG" >/dev/null
echo "uat_finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$EXIT_FILE" | tee -a "$COOK_LOG" >/dev/null

verify_rc=99
if [[ "$uat_rc" -eq 0 ]]; then
  python "$RUN_DIR/verify_paks.py" > "$RUN_DIR/verify_paks.log" 2>&1
  verify_rc=$?
else
  {
    echo "first relevant error lines from $COOK_LOG"
    grep -nEi '(^|[^A-Za-z])(error|fatal|failed|ensure condition failed|unknown cook failure|cook failed|automationtool exiting with exitcode)' "$COOK_LOG" | head -80 || true
    echo
    echo "last 120 log lines"
    tail -120 "$COOK_LOG" || true
  } > "$FAILURE_EXCERPT"
fi

echo "verify_exit_status=$verify_rc" | tee -a "$EXIT_FILE" | tee -a "$COOK_LOG" >/dev/null
echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$EXIT_FILE" | tee -a "$COOK_LOG" >/dev/null

final_status="success"
exit_code=0
if [[ "$uat_rc" -ne 0 ]]; then
  final_status="failed"
  exit_code="$uat_rc"
elif [[ "$verify_rc" -ne 0 ]]; then
  final_status="failed"
  exit_code="$verify_rc"
fi

{
  echo "run_id=full_ledger_linux_package_20260710T175718Z"
  echo "status=$final_status"
  echo "tmux_session=$SESSION"
  echo "tmux_window=$WINDOW"
  echo "attach_command=tmux attach -t $SESSION"
  echo "uat_exit_status=$uat_rc"
  echo "verify_exit_status=$verify_rc"
  echo "exit_status=$exit_code"
  echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "cook_log=$COOK_LOG"
  echo "failure_excerpt=$FAILURE_EXCERPT"
  echo "verify_log=$RUN_DIR/verify_paks.log"
  echo "verification_summary=$RUN_DIR/verification_summary.txt"
  echo "verification_summary_json=$RUN_DIR/verification_summary.json"
  echo "coverage_table=$RUN_DIR/coverage_table.md"
  echo "archive_pak_list=$RUN_DIR/archive_pak_list.log"
  echo "staged_pak_list=$RUN_DIR/staged_pak_list.log"
} | tee "$STATUS_FILE"

exit "$exit_code"
