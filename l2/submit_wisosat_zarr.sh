#!/bin/bash -l

#PBS -N wisosat_zarr
#PBS -j oe
#PBS -o logs/

set -euo pipefail

# stock qsub reads only PBS_DEFAULT and PBS_DPREFIX from the environment, and a
# #PBS line is a literal comment that cannot expand $PBS_ACCOUNT, so the account
# is resolved here instead: run outside PBS, this hands itself to qsub with it
if [[ -z ${PBS_ENVIRONMENT:-} ]]; then
    if [[ -z ${PBS_ACCOUNT:-} ]]; then
        echo "error: PBS_ACCOUNT is not set" >&2
        echo "       export it in ~/.bashrc, or submit with qsub -A <PROJECT>" >&2
        exit 1
    fi
    # refuse before anything reaches the scheduler. CONFIG is required (see the
    # note further down); catching it here means a mistyped or missing config
    # costs nothing rather than queuing a job that dies on startup.
    if [[ -z ${CONFIG:-} ]]; then
        echo "error: CONFIG is not set" >&2
        echo "       CONFIG=config/<product>/config_zarr.yaml $0" >&2
        echo "       available:" >&2
        ls config/*/config_zarr*.yaml 2>/dev/null | sed 's/^/         /' >&2
        exit 1
    fi
    if [[ ! -f ${CONFIG} ]]; then
        echo "error: no such config: ${CONFIG}" >&2
        exit 1
    fi

    # a build is stamped with the code revision that wrote it, so it must start
    # from a clean commit (user decision 2026-10-18). The build checks again
    # when the job starts; this refuses before anything is queued
    if [[ -z ${VERIFY:-} ]]; then
        dirty=$(git -C "$(dirname "$(readlink -f "$0")")" status --porcelain 2>&1) || {
            echo "error: git cannot report the working tree's state" >&2
            exit 1
        }
        if [[ -n ${dirty} ]]; then
            echo "error: the working tree is not a clean commit; commit or move these first:" >&2
            echo "${dirty}" | head -10 | sed 's/^/         /' >&2
            exit 1
        fi
    fi

    # the queue shape is not a #PBS directive either, since testing needs to
    # vary it and a directive cannot expand a variable: these defaults are the
    # production run, and a develop queue test overrides them in the
    # environment. They are set only here, so that inside the job NCPUS stays
    # whatever PBS actually granted and the guard below can trust it.
    QUEUE="${QUEUE:-main}"
    NCPUS="${NCPUS:-128}"
    # derecho caps the main queue at 12 hours; a run too big for that resumes
    WALLTIME="${WALLTIME:-12:00:00}"
    # a main queue job gets the whole node's memory and needs no request; a
    # shared develop job gets a flat 10 GB default whatever ncpus it asked for,
    # which may be below what a batch of granules needs and quietly starves the run,
    # so a test has to ask for memory explicitly
    MEM="${MEM:-}"

    select="1:ncpus=${NCPUS}"
    if [[ -n ${MEM} ]]; then
        select="${select}:mem=${MEM}"
    fi

    qsub_args=(
        -A "${PBS_ACCOUNT}"
        -q "${QUEUE}"
        -l "select=${select}"
        -l "walltime=${WALLTIME}"
    )
    # job_priority is a main queue concept; the develop queue rejects it
    if [[ ${QUEUE} == main ]]; then
        qsub_args+=(-l job_priority=regular)
    fi
    # only one writer at a time can hold the icechunk branch, so a run too long
    # for one walltime chains its jobs instead of overlapping them. The default
    # is afterany, not afterok: a job stopped by walltime exits non-zero, and
    # that is precisely the case the next job in the chain exists to resume.
    DEPEND="${DEPEND:-afterany}"
    if [[ -n ${AFTER:-} ]]; then
        qsub_args+=(-W "depend=${DEPEND}:${AFTER}")
    fi
    # VERIFY switches the job from building the stores to auditing them. It is
    # worth a batch job for the same reason the build is: verification reads
    # every observation of every granule again.
    passthrough="CONFIG=${CONFIG}"
    if [[ -n ${VERIFY:-} ]]; then
        passthrough="${passthrough},VERIFY=1"
        # qsub -v splits on commas, and --stores takes a comma separated list;
        # PBS keeps a quoted value whole
        if [[ -n ${VERIFY_ARGS:-} ]]; then
            if [[ ${VERIFY_ARGS} == *"'"* ]]; then
                echo "error: VERIFY_ARGS cannot contain a single quote" >&2
                exit 1
            fi
            passthrough="${passthrough},VERIFY_ARGS='${VERIFY_ARGS}'"
        fi
        qsub_args+=(-N wisosat_verify)
    fi
    qsub_args+=(-v "${passthrough}")
    # an absolute path so the submission does not depend on the caller's cwd
    exec qsub "${qsub_args[@]}" "$(readlink -f "$0")"
fi

# qsub starts the job in $HOME; PBS_O_WORKDIR is where it was submitted from
cd "${PBS_O_WORKDIR:-$(dirname "$(readlink -f "$0")")}"

# the same module set the venv was built against, so the wheels' bundled HDF5
# does not meet a different one through LD_LIBRARY_PATH
module reset > /dev/null 2>&1

export PATH="$HOME/.local/bin:$PATH"
# keep scratch space, not /tmp, behind anything the libraries spill
export TMPDIR="${TMPDIR:-/glade/derecho/scratch/$USER/tmp}"
mkdir -p "$TMPDIR" logs

# dask supplies the parallelism; a threaded BLAS underneath it would oversubscribe
export OMP_NUM_THREADS=1
# MALLOC_TRIM_THRESHOLD_=0 (carried over from GLEAM) is deliberately not set:
# with multi-GB arrays freed and reallocated every batch it cost the TROPOMI
# 2-D build ~8 s of kernel time per orbit, 22% of its CPU (TESTING.md finding
# 12). glibc's default trim keeps the memory for the next batch
unset MALLOC_TRIM_THRESHOLD_

# No default. Each product's config builds every store of that product, and a
# wrong default would silently start building the wrong ones -- hours of
# walltime before anyone notices. CONFIG is required, and is checked here
# rather than left to fail later inside python.
if [[ -z ${CONFIG:-} ]]; then
    echo "error: CONFIG is not set" >&2
    echo "       CONFIG=config/<product>/config_zarr.yaml $0" >&2
    echo "       available:" >&2
    ls config/*/config_zarr*.yaml 2>/dev/null | sed 's/^/         /' >&2
    exit 1
fi
if [[ ! -f ${CONFIG} ]]; then
    echo "error: no such config: ${CONFIG}" >&2
    exit 1
fi

echo "job      ${PBS_JOBID:-interactive} on $(hostname)"
echo "started  $(date)"
echo "config   ${CONFIG}"
echo "queue    ${PBS_QUEUE:-unset}"
# the true cpu count is reported by the guard below, which already starts python

# num_workers lives in the config while the job size lives here, so they can
# drift; an oversubscribed run would multiply the granules held in flight
# straight past the memory the job asked for.
#
# The cpu count comes from the affinity mask rather than $NCPUS or nproc, both of
# which lie here: on a shared develop node PBS reports NCPUS=1 whatever it
# granted, and nproc reports OMP_NUM_THREADS, which this script pins to 1.
# A verify job runs verify_num_workers scan processes when the config sets
# it, unless it skips the values phase.
read -r workers available < <(uv run python -c "
import os
from utils.path_utils import load_config
settings = load_config('${CONFIG}')
workers = settings.get('num_workers') or 0
if '${VERIFY:-}':
    workers = settings.get('verify_num_workers', workers)
    # a run without the values phase scans nothing, so starts no workers
    args = '${VERIFY_ARGS:-}'.split()
    if '--phases' in args and 'values' not in args[args.index('--phases') + 1]:
        workers = 1
print(workers, len(os.sched_getaffinity(0)))
")
echo "workers  ${workers:-unset} processes, cpus available=${available}"
if (( workers > available )); then
    echo "error: ${workers} worker processes from ${CONFIG} exceed the ${available} cpus" >&2
    echo "       this job can use; raise ncpus or lower num_workers / verify_num_workers" >&2
    exit 1
fi

# the build is the default; VERIFY runs the read-only verifier over the same
# config instead. The verifier opens every session read only, so this cannot
# damage anything even if pointed at finished stores.
if [[ -n ${VERIFY:-} ]]; then
    # shellcheck disable=SC2086  # VERIFY_ARGS is deliberately word-split
    uv run python verify_wisosat_zarr.py --config "${CONFIG}" ${VERIFY_ARGS:-}
else
    uv run python wisosat_zarr.py --config "${CONFIG}"
fi

echo "finished $(date)"
