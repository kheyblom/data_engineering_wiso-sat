#!/bin/bash
# Finalize one product's verified stores: the fixed finalize sequence, from one
# command, so a delivery can be repeated exactly and its record kept.
#
#   CONFIG=config/<product>/config_zarr.yaml TAG=<tag> ./finalize_wisosat_zarr.sh
#
# The order is load-bearing (CLAUDE.md): --status, --attrs, --tag, then --gc.
# Each step is finalize_wisosat_zarr.py, which logs to logs/finalize_<log_file>
# and refuses --attrs for a store without a passing verifier run.
#
# Three levels, so nothing changes by accident:
#   (default)          every step is a dry run: it reports what it would do;
#   APPLY=1            --attrs and --tag are applied, --gc is still a dry run;
#   APPLY=1 GC_APPLY=1 --gc --apply as well. Irreversible: it deletes every
#                      object no branch or tag references, including commits a
#                      rewind left behind (tools/rewind_stores.py), so run it
#                      only once the dry run has been read.
#
# Light (metadata and small attribute commits), so it runs on a login node
# rather than as a batch job. Tags are immutable: a second APPLY run with the
# same TAG fails at --tag, after --attrs has found nothing left to write.
#
# Tag convention, after data_engineering_gleam: <version>-verified-YYYYMMDD,
# the date the verification passed (e.g. v8.1-verified-20261018).

set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")"

if [[ -z ${CONFIG:-} || ! -f ${CONFIG} ]]; then
    echo "error: CONFIG must name an existing config, e.g." >&2
    echo "       CONFIG=config/tropomi/config_zarr.yaml TAG=v8.1-verified-YYYYMMDD $0" >&2
    exit 1
fi
if [[ -z ${TAG:-} ]]; then
    echo "error: TAG is not set (convention: <version>-verified-YYYYMMDD)" >&2
    exit 1
fi
if [[ -n ${GC_APPLY:-} && -z ${APPLY:-} ]]; then
    echo "error: GC_APPLY needs APPLY: --gc --apply comes after --attrs and --tag are applied" >&2
    exit 1
fi

apply=()
[[ -n ${APPLY:-} ]] && apply=(--apply)

run() {
    echo "== finalize_wisosat_zarr.py --config ${CONFIG} $*"
    uv run python finalize_wisosat_zarr.py --config "${CONFIG}" "$@"
}

echo "started  $(date)"
echo "config   ${CONFIG}"
echo "tag      ${TAG}"
echo "mode     $([[ -n ${GC_APPLY:-} ]] && echo 'apply, gc applied' || ([[ -n ${APPLY:-} ]] && echo 'apply, gc dry run' || echo 'dry run'))"

run --status
run --attrs "${apply[@]}"
run --tag "${TAG}" "${apply[@]}"
run --gc
if [[ -n ${GC_APPLY:-} ]]; then
    run --gc --apply
fi
# the record of where the stores ended up
run --status

echo "finished $(date)"
