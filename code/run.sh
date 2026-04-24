#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ROUND="${ROUND:-4}"
WEIGHT="${WEIGHT:-78}"
SAT_THREADS="${SAT_THREADS:-20}"
START_RND="${START_RND:-0}"
SOLVER="${SOLVER:-cryptominisat5}"
MODE="${MODE:-direct-n}"
EXTEND_DIRECTION="${EXTEND_DIRECTION:-forward}"
SEARCH_ROUNDS="${SEARCH_ROUNDS:-}"
TRAIL_PATH="${TRAIL_PATH:-${PROJECT_ROOT}/trails/W250_4R_S12_M31E33_K5_space_167.log}"

CNF_DIR="${CNF_DIR:-${PROJECT_ROOT}/modelcnfs}"
SAT_LOG_DIR="${SAT_LOG_DIR:-${PROJECT_ROOT}/logs/tmp}"
RIGHTPAIR_DIR="${RIGHTPAIR_DIR:-${PROJECT_ROOT}/result/${ROUND}round}"

CMD=(
    python -u "${SCRIPT_DIR}/solve_verify_model.py"
    --mode "${MODE}"
    --extend-direction "${EXTEND_DIRECTION}"
    -r "${ROUND}"
    -w "${WEIGHT}"
    -m "${START_RND}"
    -satTrd "${SAT_THREADS}"
    -f "${CNF_DIR}"
    -sat "${SOLVER}"
    --trail "${TRAIL_PATH}"
    --satlog-dir "${SAT_LOG_DIR}"
    --rightpair-dir "${RIGHTPAIR_DIR}"
    --max-solutions 1
)

if [[ -n "${SEARCH_ROUNDS}" ]]; then
    CMD+=(--search-rounds "${SEARCH_ROUNDS}")
fi

"${CMD[@]}"
