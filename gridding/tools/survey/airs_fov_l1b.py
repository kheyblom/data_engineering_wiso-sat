"""AIRS footprint polygons from L2 fields against AIRS L1B geometry (decision D1, 1.6).

The one-off validation of the `airs_fov` prototype (`airs_fov_polygon.py`)
against the eight AIRIBRAD.005 granules fetched by `airs_l1b_fetch.sh`
(2026-11-13; deleted 2026-11-14 once the engine's module had been checked
against them too: fetch them again to rerun this). Production reads no L1B. For every target TROPESS retrieved
in those granules it checks, against L1B:

- **the indices** (1.3): `airs_atrack`/`airs_xtrack` address L1B's arrays
  0-based (L2's centre against `Latitude`/`Longitude` there);
- **the side** (1.3): `airs_view_ang` is |`scanang`|, and `scanang` is
  negative for `airs_xtrack` <= 44;
- **the scan plane** (1.2): the model's bearing from the target to the
  sub-satellite point against `satazi`, for each way of finding it
  (`orbit` in the inertial and the ground frame, and the per-granule `fit`);
- **the height** (1.4): `satheight` against the nominal 705.3 km, and
  against a height taken from the orbit phase (see `airs_fov_polygon.py`);
- **the polygons**: the model's 32-gon against the one drawn the same way
  (1.1 degree cone onto WGS84) from L1B's own satellite position, by area
  ratio and by the share of area they have in common (intersection over
  union), in each target's local plane.

L1B's satellite position (`sat_lat`, `sat_lon`, `satheight`, one per scan
at `nadirTAI`) is taken to each footprint's `Time` by interpolating between
scans.

Reads untrusted downloads: run isolated, from the repo root, in a throwaway
environment (pyhdf reads HDF4; no project lock is changed):
uv run --no-project --python 3.13 --with pyhdf --with netCDF4 --with shapely --with numpy \
    python -I gridding/tools/survey/airs_fov_l1b.py --l1b <dir> <raw TROPESS file> [...]
"""
import argparse
import glob
import os
import re
import sys

import numpy as np
import pyhdf.VS  # noqa: F401  (registers HDF.vstart)
import shapely
from pyhdf.HDF import HDF
from pyhdf.SD import SD, SDC

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import airs_fov_polygon as fov  # noqa: E402


def read_l1b(path):
    """Geolocation of one L1B granule: per-footprint arrays and per-scan satellite state."""
    sd = SD(path, SDC.READ)
    out = {name: sd.select(name).get().astype('float64')
           for name in ('Latitude', 'Longitude', 'Time', 'scanang', 'satzen', 'satazi', 'topog')}
    sd.end()
    hdf = HDF(path)
    vs = hdf.vstart()
    for name in ('sat_lat', 'sat_lon', 'satheight', 'nadirTAI'):
        vd = vs.attach(name)
        out[name] = np.array(vd.read(vd.inquire()[0]), dtype='float64').ravel()
        vd.detach()
    vs.end()
    hdf.close()
    return out


def satellite_at(l1b, atrack, xtrack):
    """L1B's satellite ECEF position at each footprint's time, interpolated between scans."""
    position = fov.ecef(l1b['sat_lat'], l1b['sat_lon'], l1b['satheight'])
    when = l1b['Time'][atrack, xtrack]
    return np.stack([np.interp(when, l1b['nadirTAI'], position[:, i]) for i in range(3)], axis=-1)


def local_polygons(lat, lon, plat, plon):
    """Polygons as shapely geometries in each target's local plane (km east, km north)."""
    radius = np.linalg.norm(fov.ecef(lat, lon), axis=-1)[:, None]
    east = np.radians((plon - lon[:, None] + 180) % 360 - 180) * radius * np.cos(np.radians(lat))[:, None]
    north = np.radians(plat - lat[:, None]) * radius
    return shapely.polygons(np.stack([east, north], axis=-1))


def wrap(angle):
    """Degrees into -180..180."""
    return (angle + 180) % 360 - 180


def spread(name, values, unit, fmt='.3f'):
    v = np.abs(values)
    print(f'    {name}: p50 {np.median(v):{fmt}}, p95 {np.percentile(v, 95):{fmt}}, max {v.max():{fmt}} {unit}')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('files', nargs='+', help='raw TROPESS AIRS files')
    parser.add_argument('--l1b', required=True, help='directory holding the L1B granules')
    args = parser.parse_args()
    for path in args.files:
        day = re.search(r'_HDO_(\d{4})(\d{2})(\d{2})_', path).groups()
        f = fov.read(path)
        variants = {
            'orbit, inertial frame, 705.3 km': fov.model(f, 'inertial', 'orbit', 1.0, 'nominal'),
            'orbit, ground frame, 705.3 km': fov.model(f, 'ground', 'orbit', 1.0, 'nominal'),
            'per-granule fit, 705.3 km': fov.model(f, 'inertial', 'fit', 1.0, 'nominal'),
            'orbit, inertial frame, height from phase (chosen)': fov.model(f, 'inertial', 'orbit', 1.0, 'phase'),
        }
        base = variants['orbit, inertial frame, 705.3 km']
        totals = {label: [] for label in variants}
        print(f'{os.path.basename(path)}: phase fit u0 {base["u0"] % 360:.3f} deg, k/k0 {base["k"] / fov.K0:.5f}')
        for l1b_path in sorted(glob.glob(os.path.join(args.l1b, 'AIRS.{}.{}.{}.*.hdf'.format(*day)))):
            granule = int(os.path.basename(l1b_path).split('.')[4])
            rows = np.flatnonzero(f['granule'] == granule)
            l1b = read_l1b(l1b_path)
            atrack, xtrack = f['atrack'][rows], f['xtrack'][rows]
            lat, lon = f['lat'][rows], f['lon'][rows]
            print(f'  granule {granule:03d}: {rows.size} targets, latitude {lat.min():.1f} to {lat.max():.1f}, '
                  f'satheight {l1b["satheight"].min():.1f} to {l1b["satheight"].max():.1f} km')
            for shift in (0, 1):
                ok = (atrack + shift < 135) & (xtrack + shift < 90)
                d_lat = lat[ok] - l1b['Latitude'][atrack[ok] + shift, xtrack[ok] + shift]
                d_lon = wrap(lon[ok] - l1b['Longitude'][atrack[ok] + shift, xtrack[ok] + shift])
                print(f'    indices {"0-based" if shift == 0 else "1-based (as 0-based + 1)"}: centre differs by up to '
                      f'{np.abs(d_lat).max():.5f} deg lat, {np.abs(d_lon).max():.5f} deg lon')
            scanang = l1b['scanang'][atrack, xtrack]
            print(f'    view angle - |scanang|: max {np.abs(f["view"][rows] - np.abs(scanang)).max():.6f} deg; '
                  f'side rule (xtrack <= 44 negative) holds on {(np.sign(scanang) == np.sign(base["scan"][rows])).sum()} '
                  f'of {rows.size}')
            truth_sat = satellite_at(l1b, atrack, xtrack)
            truth = local_polygons(lat, lon, *fov.polygons(lat, lon, truth_sat))
            off_nadir = l1b['satzen'][atrack, xtrack] > 5
            for label, m in variants.items():
                ok = m['ok'][rows]
                if not ok.any():
                    print(f'    {label}: no target oriented')
                    continue
                print(f'    {label} ({ok.sum()} of {rows.size} targets):')
                use = ok & off_nadir
                if use.any():
                    spread('bearing to nadir - satazi (satzen > 5)',
                           wrap(np.degrees(m['back'][rows][use]) - l1b['satazi'][atrack, xtrack][use]), 'deg')
                spread('satellite position - L1B', np.linalg.norm(m['sat'][rows][ok] - truth_sat[ok], axis=-1), 'km', '.2f')
                ours = local_polygons(lat[ok], lon[ok], m['plat'][rows][ok], m['plon'][rows][ok])
                ratio = shapely.area(ours) / shapely.area(truth[ok])
                iou = shapely.area(shapely.intersection(ours, truth[ok])) / shapely.area(shapely.union(ours, truth[ok]))
                print(f'    area / L1B area: p5 {np.percentile(ratio, 5):.4f}, p50 {np.median(ratio):.4f}, '
                      f'p95 {np.percentile(ratio, 95):.4f}; common area (IoU): min {iou.min():.4f}, '
                      f'p5 {np.percentile(iou, 5):.4f}, p50 {np.median(iou):.4f}')
                totals[label].append((ratio, iou))
        print('  all granules of this file:')
        for label, parts in totals.items():
            ratio, iou = (np.concatenate(x) for x in zip(*parts))
            print(f'    {label}: {ratio.size} targets, area / L1B area {ratio.min():.4f} to {ratio.max():.4f} '
                  f'(p50 {np.median(ratio):.4f}); common area min {iou.min():.4f}, p50 {np.median(iou):.4f}')


if __name__ == '__main__':
    main()
