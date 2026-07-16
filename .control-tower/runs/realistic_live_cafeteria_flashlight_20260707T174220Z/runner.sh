#!/usr/bin/env bash
set -u

RUN_DIR="/home/yashturkar/Workspace/spear/.control-tower/runs/realistic_live_cafeteria_flashlight_20260707T174220Z"
LOG="$RUN_DIR/runtime.log"
EXIT_FILE="$RUN_DIR/exit_status.txt"
STATUS_FILE="$RUN_DIR/status.txt"

{
  echo "started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "working_dir=/home/yashturkar/Workspace/spear"
  echo "tmux_session=realistic_live_flashlight_174220"
  echo "tmux_window=runtime"
  echo "attach_command=tmux attach -t realistic_live_flashlight_174220"
  echo "command=cd /home/yashturkar/Workspace/spear && conda activate spear-env && python examples/flashlight/run.py --map cafeteria_500sqft_v2 --live-lighting-mode realistic --flashlight-profile realistic_live_flashlight --scene-light-intensity-scale 0.0005 --movement-speed 600 --disable-auto-exposure --startup-warmup-seconds 3"
} > "$STATUS_FILE"

exec > >(tee -a "$LOG") 2>&1

echo "[runner] started_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[runner] run_dir=$RUN_DIR"
echo "[runner] command: cd /home/yashturkar/Workspace/spear && conda activate spear-env && python examples/flashlight/run.py --map cafeteria_500sqft_v2 --live-lighting-mode realistic --flashlight-profile realistic_live_flashlight --scene-light-intensity-scale 0.0005 --movement-speed 600 --disable-auto-exposure --startup-warmup-seconds 3"

source /home/yashturkar/miniconda3/etc/profile.d/conda.sh
conda activate spear-env
cd /home/yashturkar/Workspace/spear

python examples/flashlight/run.py \
  --map cafeteria_500sqft_v2 \
  --live-lighting-mode realistic \
  --flashlight-profile realistic_live_flashlight \
  --scene-light-intensity-scale 0.0005 \
  --movement-speed 600 \
  --disable-auto-exposure \
  --startup-warmup-seconds 3
exit_code=$?

echo "[runner] finished_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[runner] exit_code=$exit_code"
{
  echo "finished_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "exit_code=$exit_code"
} >> "$STATUS_FILE"
echo "$exit_code" > "$EXIT_FILE"
exit "$exit_code"
