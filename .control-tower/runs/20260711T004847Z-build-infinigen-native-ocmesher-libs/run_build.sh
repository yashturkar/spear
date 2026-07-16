#!/usr/bin/env bash
set -u

RUN_DIR="/home/yashturkar/Workspace/spear/.control-tower/runs/20260711T004847Z-build-infinigen-native-ocmesher-libs"
INF_ROOT="/home/yashturkar/Workspace/infinigen"
SDF_SO="$INF_ROOT/infinigen/terrain/lib/cpu/sdf_from_mesh/sdf_from_mesh.so"
CORE_SO="$INF_ROOT/infinigen/OcMesher/ocmesher/lib/core.so"
PRIMARY_LOG="$RUN_DIR/make-terrain.log"
FALLBACK_LOG="$RUN_DIR/fallback-build.log"
VERIFY_LOG="$RUN_DIR/ctypes-verify.log"
STATUS_FILE="$RUN_DIR/status.txt"

log_status() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$STATUS_FILE"
}

verify_libs() {
  (
    set -e
    test -s "$SDF_SO"
    test -s "$CORE_SO"
    conda run -n infinigen python -c "from ctypes import CDLL; CDLL('$SDF_SO'); CDLL('$CORE_SO'); print('native ocmesher libs load')"
  ) 2>&1 | tee "$VERIFY_LOG"
  return "${PIPESTATUS[0]}"
}

mkdir -p "$RUN_DIR"
: > "$STATUS_FILE"
log_status "run started"
log_status "primary command: cd $INF_ROOT && source /home/yashturkar/miniconda3/etc/profile.d/conda.sh && conda activate infinigen && make terrain"

cd "$INF_ROOT" || exit 10
source /home/yashturkar/miniconda3/etc/profile.d/conda.sh
conda activate infinigen

set +e
make terrain 2>&1 | tee "$PRIMARY_LOG"
MAKE_STATUS="${PIPESTATUS[0]}"
set -e
log_status "make terrain exit status: $MAKE_STATUS"

if verify_libs; then
  log_status "ctypes verification succeeded after make terrain"
  log_status "run completed successfully"
  exit 0
fi

VERIFY_STATUS=$?
log_status "ctypes verification after make terrain failed with status: $VERIFY_STATUS"
log_status "fallback command: cd $INF_ROOT/infinigen/terrain && mkdir -p lib/cpu/sdf_from_mesh && g++ -O3 -c -fpic -fopenmp -o lib/cpu/sdf_from_mesh/sdf_from_mesh.o source/cpu/sdf_from_mesh/sdf_from_mesh.cpp && g++ -O3 -shared -fopenmp -o lib/cpu/sdf_from_mesh/sdf_from_mesh.so lib/cpu/sdf_from_mesh/sdf_from_mesh.o && cd $INF_ROOT/infinigen/OcMesher && bash install.sh"

set +e
(
  set -e
  cd "$INF_ROOT/infinigen/terrain"
  mkdir -p lib/cpu/sdf_from_mesh
  g++ -O3 -c -fpic -fopenmp -o lib/cpu/sdf_from_mesh/sdf_from_mesh.o source/cpu/sdf_from_mesh/sdf_from_mesh.cpp
  g++ -O3 -shared -fopenmp -o lib/cpu/sdf_from_mesh/sdf_from_mesh.so lib/cpu/sdf_from_mesh/sdf_from_mesh.o
  cd "$INF_ROOT/infinigen/OcMesher"
  bash install.sh
) 2>&1 | tee "$FALLBACK_LOG"
FALLBACK_STATUS="${PIPESTATUS[0]}"
set -e
log_status "fallback exit status: $FALLBACK_STATUS"

if verify_libs; then
  log_status "ctypes verification succeeded after fallback"
  log_status "run completed successfully"
  exit 0
fi

FINAL_VERIFY_STATUS=$?
log_status "ctypes verification after fallback failed with status: $FINAL_VERIFY_STATUS"
log_status "run failed"
exit "$FINAL_VERIFY_STATUS"
