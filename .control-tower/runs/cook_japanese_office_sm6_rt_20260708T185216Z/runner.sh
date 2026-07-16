#!/usr/bin/env bash
set -euo pipefail

RUN_DIR="/home/yashturkar/Workspace/spear/.control-tower/runs/cook_japanese_office_sm6_rt_20260708T185216Z"
STATUS_FILE="${RUN_DIR}/status.txt"
EXIT_FILE="${RUN_DIR}/exit_status.txt"
COOK_LOG="${RUN_DIR}/cook_package.log"
PAK_LIST_LOG="${RUN_DIR}/pak_list.log"
VERIFY_LOG="${RUN_DIR}/verification_summary.txt"
ENV_LOG="${RUN_DIR}/runtime_environment_check.log"
PAK="/home/yashturkar/Workspace/spear/cpp/unreal_projects/SpearSim/Standalone-Development/Linux/SpearSim/Content/Paks/SpearSim-Linux.pak"
UNREAL_PAK="/home/yashturkar/Linux_Unreal_Engine_5.5.4/Engine/Binaries/Linux/UnrealPak"
SESSION="cook_jp_office_sm6_185216"
WINDOW="uat"

cd /home/yashturkar/Workspace/spear

{
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "status=running"
  echo "tmux_session=${SESSION}"
  echo "tmux_window=${WINDOW}"
  echo "cook_log=${COOK_LOG}"
  echo "pak_list_log=${PAK_LIST_LOG}"
  echo "verification_log=${VERIFY_LOG}"
} > "${STATUS_FILE}"

{
  echo "DISPLAY=${DISPLAY:-}"
  echo "WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-}"
  if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    echo "runtime_validation=skipped_no_display"
  else
    echo "runtime_validation=not_run_display_available_but_task_requested_package_verification_only"
  fi
} > "${ENV_LOG}"

set +e
(
  set -euo pipefail
  source /home/yashturkar/miniconda3/etc/profile.d/conda.sh
  conda activate spear-env
  python tools/run_uat.py \
    --unreal-engine-dir /home/yashturkar/Linux_Unreal_Engine_5.5.4 \
    --clean-archive-dir \
    --cook-maps \
      /Game/JapaneseOffice/Maps/Demonstration \
      /Game/JapaneseOffice/Maps/Demonstration_Dark \
    -clean -cook -stage -package -archive -pak -skipbuild
) 2>&1 | tee "${COOK_LOG}"
cmd_status=${PIPESTATUS[0]}
set -e

{
  echo "cook_exit_status=${cmd_status}"
  echo "cook_finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "${EXIT_FILE}"

if [[ "${cmd_status}" -eq 0 ]]; then
  "${UNREAL_PAK}" "${PAK}" -List > "${PAK_LIST_LOG}" 2>&1

  demo_count=$(grep -c 'JapaneseOffice/Maps/Demonstration\.umap' "${PAK_LIST_LOG}" || true)
  dark_count=$(grep -c 'JapaneseOffice/Maps/Demonstration_Dark\.umap' "${PAK_LIST_LOG}" || true)
  shader_count=$(grep -c 'GlobalShaderCache-VULKAN_SM6\.bin' "${PAK_LIST_LOG}" || true)
  pak_size=$(stat -c '%s' "${PAK}")

  {
    echo "pak=${PAK}"
    echo "pak_size_bytes=${pak_size}"
    echo "map_demonstration_umap_count=${demo_count}"
    echo "map_demonstration_dark_umap_count=${dark_count}"
    echo "global_shader_cache_vulkan_sm6_count=${shader_count}"
    echo "matching_entries:"
    grep -E 'JapaneseOffice/Maps/Demonstration(_Dark)?\.umap|GlobalShaderCache-VULKAN_SM6\.bin' "${PAK_LIST_LOG}" || true
  } > "${VERIFY_LOG}"

  if [[ "${demo_count}" -gt 0 && "${dark_count}" -gt 0 && "${shader_count}" -gt 0 ]]; then
    verify_status=success
    exit_code=0
  else
    verify_status=failed
    exit_code=2
  fi
else
  verify_status=not_run
  exit_code="${cmd_status}"
fi

{
  echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "status=${verify_status}"
  echo "tmux_session=${SESSION}"
  echo "tmux_window=${WINDOW}"
  echo "cook_log=${COOK_LOG}"
  echo "pak_list_log=${PAK_LIST_LOG}"
  echo "verification_log=${VERIFY_LOG}"
  echo "runtime_environment_log=${ENV_LOG}"
  echo "archive_dir=/home/yashturkar/Workspace/spear/cpp/unreal_projects/SpearSim/Standalone-Development"
  echo "archive_pak=${PAK}"
  echo "exit_status=${exit_code}"
} > "${STATUS_FILE}"

{
  echo "exit_status=${exit_code}"
  echo "finished_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "${EXIT_FILE}"

exit "${exit_code}"
