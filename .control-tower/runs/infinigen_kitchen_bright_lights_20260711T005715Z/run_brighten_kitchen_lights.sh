#!/usr/bin/env bash
set -uo pipefail

RUN_DIR="/home/yashturkar/Workspace/spear/.control-tower/runs/infinigen_kitchen_bright_lights_20260711T005715Z"
LOG_PATH="${RUN_DIR}/logs/editor.log"
STATUS_PATH="${RUN_DIR}/exit_status.txt"

mkdir -p "${RUN_DIR}/logs"
cd /home/yashturkar/Workspace/spear || exit 1

{
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "command=cd /home/yashturkar/Workspace/spear && source /home/yashturkar/miniconda3/etc/profile.d/conda.sh && conda activate spear-env && python tools/run_editor_script.py --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 --launch-mode full --render-offscreen --script ${RUN_DIR}/scripts/brighten_kitchen_lights.py --map-path /Game/SPEAR/Scenes/infinigen_indoors_kitchen/Maps/infinigen_indoors_kitchen --mesh-dir /Game/SPEAR/Scenes/infinigen_indoors_kitchen/Meshes --validation-report ${RUN_DIR}/validation_report.json"
  source /home/yashturkar/miniconda3/etc/profile.d/conda.sh
  conda activate spear-env
  python tools/run_editor_script.py \
    --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 \
    --launch-mode full \
    --render-offscreen \
    --script "${RUN_DIR}/scripts/brighten_kitchen_lights.py" \
    --map-path /Game/SPEAR/Scenes/infinigen_indoors_kitchen/Maps/infinigen_indoors_kitchen \
    --mesh-dir /Game/SPEAR/Scenes/infinigen_indoors_kitchen/Meshes \
    --validation-report "${RUN_DIR}/validation_report.json"
  status=$?
  echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "exit_status=${status}"
  echo "${status}" > "${STATUS_PATH}"
  exit "${status}"
} 2>&1 | tee "${LOG_PATH}"

exit "${PIPESTATUS[0]}"
