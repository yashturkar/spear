#!/usr/bin/env bash
set -uo pipefail

RUN_DIR="/home/yashturkar/Workspace/spear/.control-tower/runs/restore_cafeteria_package_20260709T191205Z"
REPO="/home/yashturkar/Workspace/spear"
UNREAL_PAK="/home/yashturkar/Linux_Unreal_Engine_5.5.4/Engine/Binaries/Linux/UnrealPak"
ARCHIVE_PAK="$REPO/cpp/unreal_projects/SpearSim/Standalone-Development/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak"
STAGED_PAK="$REPO/cpp/unreal_projects/SpearSim/Saved/StagedBuilds/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak"
TARGET_RE='cafeteria_500sqft_v2/Maps/(cafeteria_500sqft_v2|cafeteria_500sqft_v2_flashlight_validation_dark)\.(umap|uexp|ubulk)'

cd "$REPO" || exit 2
{
  echo "run_id=restore_cafeteria_package_20260709T191205Z"
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "unreal_pak=$UNREAL_PAK"
  echo "archive_pak=$ARCHIVE_PAK"
  echo "staged_pak=$STAGED_PAK"
  echo

  for spec in "archive:$ARCHIVE_PAK" "staged:$STAGED_PAK"; do
    label="${spec%%:*}"
    pak="${spec#*:}"
    list_log="$RUN_DIR/${label}_pak_list.log"
    hits_log="$RUN_DIR/${label}_cafeteria_map_hits.log"
    echo "== $label =="
    if [[ ! -f "$pak" ]]; then
      echo "pak_missing=$pak"
      continue
    fi
    stat -c 'pak_stat path=%n size=%s mtime=%y' "$pak"
    "$UNREAL_PAK" "$pak" -List > "$list_log" 2>&1
    list_rc=$?
    echo "unrealpak_list_exit=$list_rc"
    echo "pak_list_log=$list_log"
    if [[ $list_rc -ne 0 ]]; then
      tail -n 80 "$list_log"
      continue
    fi
    grep -E "$TARGET_RE" "$list_log" > "$hits_log" || true
    echo "cafeteria_map_hits_log=$hits_log"
    hit_count="$(wc -l < "$hits_log" | tr -d ' ')"
    echo "cafeteria_map_hit_count=$hit_count"
    cat "$hits_log"
    echo
  done

  echo "local_source_maps:"
  ls -l "$REPO/cpp/unreal_projects/SpearSim/Content/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/"*.umap
  echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} 2>&1 | tee "$RUN_DIR/verify_active_package.log"

archive_hits="$RUN_DIR/archive_cafeteria_map_hits.log"
if [[ -f "$archive_hits" ]] && grep -q 'cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2\.umap' "$archive_hits" && grep -q 'cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2_flashlight_validation_dark\.umap' "$archive_hits"; then
  echo 0 > "$RUN_DIR/verify_exit_status.txt"
  exit 0
fi

echo 3 > "$RUN_DIR/verify_exit_status.txt"
exit 3
