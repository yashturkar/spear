#!/usr/bin/env bash
set -euo pipefail

repo_root="/home/yashturkar/Workspace/spear"
run_dir="${repo_root}/.control-tower/runs/cook_cafeteria_500sqft_v2_20260702T153100Z"
log_file="${run_dir}/cook.log"
status_file="${run_dir}/status.txt"

cd "${repo_root}"

{
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "repo_root=${repo_root}"
  echo "run_dir=${run_dir}"
  echo "command=/home/yashturkar/miniconda3/envs/spear-env/bin/python tools/run_uat.py --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 --cook-maps /Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2 -cook -stage -package -archive -pak -skipbuild"
} > "${status_file}"

set +e
/home/yashturkar/miniconda3/envs/spear-env/bin/python tools/run_uat.py \
  --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 \
  --cook-maps /Game/SPEAR/Scenes/cafeteria_500sqft_v2/Maps/cafeteria_500sqft_v2 \
  -cook -stage -package -archive -pak -skipbuild \
  2>&1 | tee "${log_file}"
exit_status=${PIPESTATUS[0]}
set -e

{
  echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "exit_status=${exit_status}"
} >> "${status_file}"

exit "${exit_status}"
