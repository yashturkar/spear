#!/usr/bin/env bash
set -uo pipefail

RUN_DIR="/home/yashturkar/Workspace/spear/.control-tower/runs/restore_cafeteria_package_20260709T191205Z"
REPO="/home/yashturkar/Workspace/spear"
CONDA_SH="/home/yashturkar/miniconda3/etc/profile.d/conda.sh"
UNREAL_PAK="/home/yashturkar/Linux_Unreal_Engine_5.5.4/Engine/Binaries/Linux/UnrealPak"
ARCHIVE_PAK="$REPO/cpp/unreal_projects/SpearSim/Standalone-Development/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak"
STAGED_PAK="$REPO/cpp/unreal_projects/SpearSim/Saved/StagedBuilds/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak"
MAP_A="/Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2"
MAP_B="/Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2_flashlight_validation_dark"
TARGET_RE='cafeteria_500sqft_v2/Maps/(cafeteria_500sqft_v2|cafeteria_500sqft_v2_flashlight_validation_dark)\.(umap|uexp|ubulk)'

cd "$REPO" || exit 2
{
  echo "run_id=restore_cafeteria_package_20260709T191205Z"
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "tmux_session=restore_cafeteria_pkg_191205"
  echo "tmux_window=cook"
  echo "attach_command=tmux attach -t restore_cafeteria_pkg_191205"
  echo "objective=restore active Standalone-Development and Saved/StagedBuilds Linux pak with cafeteria maps"
  echo "command=source $CONDA_SH && conda activate spear-env && python tools/run_uat.py --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 --clean-archive-dir --cook-maps $MAP_A $MAP_B -clean -cook -stage -package -archive -pak -skipbuild"
  echo
} | tee "$RUN_DIR/cook_restore.log"

{
  source "$CONDA_SH"
  conda activate spear-env
  python tools/run_uat.py \
    --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 \
    --clean-archive-dir \
    --cook-maps "$MAP_A" "$MAP_B" \
    -clean -cook -stage -package -archive -pak -skipbuild
} 2>&1 | tee -a "$RUN_DIR/cook_restore.log"
uat_rc=${PIPESTATUS[0]}
echo "$uat_rc" > "$RUN_DIR/cook_exit_status.txt"
echo "uat_exit_status=$uat_rc" | tee -a "$RUN_DIR/cook_restore.log"

verify_rc=0
for spec in "archive:$ARCHIVE_PAK" "staged:$STAGED_PAK"; do
  label="${spec%%:*}"
  pak="${spec#*:}"
  list_log="$RUN_DIR/${label}_postcook_pak_list.log"
  hits_log="$RUN_DIR/${label}_postcook_cafeteria_map_hits.log"
  echo | tee -a "$RUN_DIR/cook_restore.log"
  echo "== postcook $label ==" | tee -a "$RUN_DIR/cook_restore.log"
  if [[ ! -f "$pak" ]]; then
    echo "pak_missing=$pak" | tee -a "$RUN_DIR/cook_restore.log"
    verify_rc=4
    continue
  fi
  stat -c 'pak_stat path=%n size=%s mtime=%y' "$pak" | tee -a "$RUN_DIR/cook_restore.log"
  "$UNREAL_PAK" "$pak" -List > "$list_log" 2>&1
  list_rc=$?
  {
    echo "unrealpak_list_exit=$list_rc"
    echo "pak_list_log=$list_log"
  } | tee -a "$RUN_DIR/cook_restore.log"
  if [[ $list_rc -ne 0 ]]; then
    tail -n 80 "$list_log" | tee -a "$RUN_DIR/cook_restore.log"
    verify_rc=5
    continue
  fi
  grep -E "$TARGET_RE" "$list_log" > "$hits_log" || true
  hit_count="$(wc -l < "$hits_log" | tr -d ' ')"
  {
    echo "cafeteria_map_hits_log=$hits_log"
    echo "cafeteria_map_hit_count=$hit_count"
    cat "$hits_log"
  } | tee -a "$RUN_DIR/cook_restore.log"
  if ! grep -q 'cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2\.umap' "$hits_log"; then
    verify_rc=6
  fi
  if ! grep -q 'cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2_flashlight_validation_dark\.umap' "$hits_log"; then
    verify_rc=6
  fi
done

echo "verify_exit_status=$verify_rc" > "$RUN_DIR/postcook_verify_exit_status.txt"
echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$RUN_DIR/cook_restore.log"

if [[ $uat_rc -ne 0 ]]; then
  exit "$uat_rc"
fi
exit "$verify_rc"
