#!/usr/bin/env bash
set -euo pipefail

RUN_DIR="/home/yashturkar/Workspace/spear/.control-tower/runs/cook_cafeteria_v2_maps_20260707T171735Z"
STATUS_FILE="${RUN_DIR}/status.txt"
LOG_FILE="${RUN_DIR}/cook_package.log"
EXIT_FILE="${RUN_DIR}/exit_status.txt"

cd /home/yashturkar/Workspace/spear

{
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "status=running"
  echo "tmux_session=cook_cafeteria_v2_171735"
  echo "tmux_window=uat"
  echo "log=${LOG_FILE}"
} > "${STATUS_FILE}"

set +e
(
  set -euo pipefail
  source /home/yashturkar/miniconda3/etc/profile.d/conda.sh
  conda activate spear-env
  python tools/run_uat.py \
    --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 \
    --cook-maps \
      /Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2 \
      /Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2_flashlight_validation_dark \
    -cook -stage -package -archive -pak -skipbuild
) 2>&1 | tee "${LOG_FILE}"
cmd_status=${PIPESTATUS[0]}
set -e

{
  echo "exit_status=${cmd_status}"
  echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "${EXIT_FILE}"

if [[ "${cmd_status}" -eq 0 ]]; then
  {
    echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "status=success"
    echo "tmux_session=cook_cafeteria_v2_171735"
    echo "tmux_window=uat"
    echo "log=${LOG_FILE}"
    echo "archive_dir=/home/yashturkar/Workspace/spear/cpp/unreal_projects/SpearSim/Standalone-Development"
    echo "staged_pak=/home/yashturkar/Workspace/spear/cpp/unreal_projects/SpearSim/Saved/StagedBuilds/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak"
    echo "archive_pak=/home/yashturkar/Workspace/spear/cpp/unreal_projects/SpearSim/Standalone-Development/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak"
  } > "${STATUS_FILE}"
else
  {
    echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "status=failed"
    echo "tmux_session=cook_cafeteria_v2_171735"
    echo "tmux_window=uat"
    echo "log=${LOG_FILE}"
    echo "exit_status=${cmd_status}"
  } > "${STATUS_FILE}"
fi

exit "${cmd_status}"
