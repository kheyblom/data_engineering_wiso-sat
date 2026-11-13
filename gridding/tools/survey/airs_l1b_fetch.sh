#!/bin/bash
# Fetch the eight AIRS L1B granules (AIRIBRAD.005) of the footprint validation.
#
# Evidence for AIRS gridding decision D1, 1.6 (airs-gridding-decisions.md): a
# one-off check of the airs_fov polygons against L1B geometry. Production reads
# no L1B. The granules hold many targets on an RS day, an FS day and a late FS
# day (the orbit after Aqua stopped its manoeuvres); found in CMR 2026-11-13:
#   2010-06-15 (RS): 126 ascending tropics, 235 descending tropics, 182 descending 43-63N
#   2022-06-01 (FS): 115 ascending tropics, 180 southern mid-latitudes, 053 to 81N
#   2026-05-15 (FS): 193 southern mid-latitudes, 232 descending from 79N
# 54-61 MB each, 458 MB in all, one at a time at nice 19 (login node).
#
# Needs an Earthdata Login in ~/.netrc with GES DISC approved (as
# access_tropess); curl reads it, this script never does. The session cookie
# goes to a file on scratch, removed on exit.
#
# Usage: ./airs_l1b_fetch.sh            (show the user first: user's rule)
set -euo pipefail

OUT=/glade/derecho/scratch/$USER/data/wisosat_validation/airs_l1b
BASE=https://data.gesdisc.earthdata.nasa.gov/data/Aqua_AIRS_Level1/AIRIBRAD.005
FILES=(
  2010/166/AIRS.2010.06.15.126.L1B.AIRS_Rad.v5.0.0.0.G10167122205.hdf
  2010/166/AIRS.2010.06.15.235.L1B.AIRS_Rad.v5.0.0.0.G10167131436.hdf
  2010/166/AIRS.2010.06.15.182.L1B.AIRS_Rad.v5.0.0.0.G10167130714.hdf
  2022/152/AIRS.2022.06.01.115.L1B.AIRS_Rad.v5.0.25.0.G22153120633.hdf
  2022/152/AIRS.2022.06.01.180.L1B.AIRS_Rad.v5.0.25.0.G22153143908.hdf
  2022/152/AIRS.2022.06.01.053.L1B.AIRS_Rad.v5.0.25.0.G22152123022.hdf
  2026/135/AIRS.2026.05.15.193.L1B.AIRS_Rad.v5.0.53.1.G26136121445.hdf
  2026/135/AIRS.2026.05.15.232.L1B.AIRS_Rad.v5.0.53.1.G26136123626.hdf
)

mkdir -p "$OUT"
COOKIES=$(mktemp -p "$OUT" .cookies.XXXXXX)
trap 'rm -f "$COOKIES"' EXIT

for path in "${FILES[@]}"; do
  name=${path##*/}
  if [[ -s $OUT/$name ]]; then
    echo "have $name"
    continue
  fi
  echo "fetching $name"
  nice -n 19 curl --netrc --location --fail --silent --show-error \
    --cookie "$COOKIES" --cookie-jar "$COOKIES" \
    --output "$OUT/$name.part" "$BASE/$path"
  mv "$OUT/$name.part" "$OUT/$name"
done
ls -l "$OUT"
