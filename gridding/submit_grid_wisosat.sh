#!/bin/bash -l
#PBS -N grid_wisosat
#PBS -j oe
#PBS -o logs/
#
# Submit a gridding job; run from gridding/. Show the user the command first:
# jobs cost core-hours against the allocation.
#
#   CONFIG=config/tropomi/config_grid.yaml ./submit_grid_wisosat.sh                 # build (spatial)
#   CONFIG=... VERIFY=1 LAYOUT=spatial ./submit_grid_wisosat.sh                     # verify a layout
#   CONFIG=... RECHUNK=1 ./submit_grid_wisosat.sh                                    # spatial -> temporal
#
# Optional: QUEUE (main), NCPUS (128), MEM, WALLTIME (12:00:00), AFTER=<jobid>
# to chain with afterany (a walltime kill exits non-zero, and that is the case
# the next job resumes; never two writers on one branch).
set -euo pipefail

if [[ -z ${PBS_ENVIRONMENT:-} ]]; then
    # outside PBS: resolve the account here (#PBS -A cannot expand a variable) and self-submit
    [[ -z ${PBS_ACCOUNT:-} ]] && { echo "error: PBS_ACCOUNT is not set (run through a login shell)" >&2; exit 1; }
    [[ -z ${CONFIG:-} || ! -f ${CONFIG} ]] && { echo "error: CONFIG must name a config file" >&2; exit 1; }
    if [[ -z ${VERIFY:-} && -n $(git status --porcelain -- .) ]] && ! grep -q '^allow_dirty_tree: true' "${CONFIG}"; then
        echo "error: gridding/ has uncommitted changes; commit before submitting a build" >&2; exit 1
    fi
    [[ -n ${VERIFY:-} && -z ${LAYOUT:-} ]] && { echo "error: VERIFY=1 needs LAYOUT=spatial|temporal" >&2; exit 1; }
    QUEUE="${QUEUE:-main}"; NCPUS="${NCPUS:-128}"; WALLTIME="${WALLTIME:-12:00:00}"; MEM="${MEM:-}"
    select="1:ncpus=${NCPUS}"; [[ -n ${MEM} ]] && select="${select}:mem=${MEM}"
    qsub_args=(-A "${PBS_ACCOUNT}" -q "${QUEUE}" -l "select=${select}" -l "walltime=${WALLTIME}")
    [[ ${QUEUE} == main ]] && qsub_args+=(-l job_priority=regular)
    [[ -n ${AFTER:-} ]] && qsub_args+=(-W "depend=afterany:${AFTER}")
    passthrough="CONFIG=${CONFIG}"
    if [[ -n ${VERIFY:-} ]]; then
        passthrough="${passthrough},VERIFY=1,LAYOUT=${LAYOUT}"; qsub_args+=(-N grid_verify)
    elif [[ -n ${RECHUNK:-} ]]; then
        passthrough="${passthrough},RECHUNK=1"; qsub_args+=(-N grid_rechunk)
    fi
    qsub_args+=(-v "${passthrough}")
    exec qsub "${qsub_args[@]}" "$(readlink -f "$0")"
fi

cd "${PBS_O_WORKDIR:-$(dirname "$(readlink -f "$0")")}"
module reset > /dev/null 2>&1
export PATH="$HOME/.local/bin:$PATH"
export TMPDIR="${TMPDIR:-/glade/derecho/scratch/$USER/tmp}"; mkdir -p "$TMPDIR" logs
export OMP_NUM_THREADS=1

# num_workers may not exceed the cpus this job can use (sched_getaffinity, not $NCPUS or nproc)
read -r workers available < <(uv run python -c "
import os
from utils.config import load_config
print(load_config('${CONFIG}').get('num_workers') or 0, len(os.sched_getaffinity(0)))")
(( workers > available )) && { echo "error: num_workers ${workers} exceeds ${available} cpus" >&2; exit 1; }

if [[ -n ${VERIFY:-} ]]; then
    uv run python verify_grid_wisosat.py --config "${CONFIG}" --layout "${LAYOUT}"
elif [[ -n ${RECHUNK:-} ]]; then
    uv run python rechunk_wisosat.py --config "${CONFIG}"
else
    uv run python grid_wisosat.py --config "${CONFIG}"
fi
