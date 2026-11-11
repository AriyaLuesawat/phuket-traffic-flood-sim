"""Step 6b: rain-on-grid surface flood model of Phuket island (30 m).

    .venv/bin/python scripts/flood_model.py                       # 26-29 Oct 2569 event, drainage 10 mm/h
    .venv/bin/python scripts/flood_model.py --drainage 0 20       # drainage sensitivity

Method
  Flow:      local inertial approximation of the 2D shallow water equations (Bates, Horritt & Fewtrell 2010,
             J. Hydrol. 387, 33-45), explicit, time step from their CFL condition (alpha = 0.7).
  Losses:    SCS curve number (USDA TR-55, 1986), cumulative rainfall excess per cell, CN from land cover and
             an assumed hydrologic soil group (default C; no soil map was available).
  Roughness: Manning's n = midpoint of the HEC-RAS 2D User's Manual ranges for the NLCD class closest to each
             ESA WorldCover class.
  Drainage:  pipes are not modelled. Built-up cells lose surface water at a uniform rate (ASSUMPTION, tested
             with several values). --drain-roads also drains road cells (roadside drains), used to match the
             reported recession: water back to normal by 10:00 on 29 Oct 2569 (provincial disaster office).
  Sea:       cells outside the land are held at zero depth, so water that reaches them leaves the model.
  Rain:      ERA5 hourly rainfall of one grid cell, applied uniformly to the island.

Outputs: output/flood/<run>/depth_hourly.npz, max_depth.tif, summary.json
"""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
GRIDS = ROOT / 'data' / 'processed' / 'flood'
RAIN = ROOT / 'data' / 'raw' / 'rain' / 'era5_phuket_town_2000_2026.json'
G = 9.81
ALPHA = 0.7      # CFL coefficient, Bates et al. (2010)
H_MIN = 0.001    # m; below this a face carries no flow

# WorldCover class -> (NLCD class used, Manning n midpoint of the HEC-RAS range)
MANNING = {10: ('42 Evergreen Forest', 0.12), 20: ('52 Shrub/Scrub', 0.115), 30: ('71 Grassland', 0.0375),
           40: ('82 Cultivated Crops', 0.035), 50: ('23 Developed, Medium Intensity', 0.12),
           60: ('31 Barren Land', 0.0265), 80: ('11 Open Water', 0.0375), 90: ('95 Emergent Herb. Wetlands', 0.0675),
           95: ('90 Woody Wetlands', 0.0975)}
# WorldCover class -> TR-55 cover type and CN for hydrologic soil groups B, C, D
CURVE = {10: ('Woods, fair (Table 2-2c)', (60, 73, 79)), 20: ('Brush, fair (2-2c)', (56, 70, 77)),
         30: ('Pasture/grassland, fair (2-2c)', (69, 79, 84)), 40: ('Row crops, straight row, good (2-2b)', (78, 85, 89)),
         50: ('Residential 1/8 acre, 65% impervious (2-2a)', (85, 90, 92)),
         60: ('Newly graded areas (2-2a)', (86, 91, 94)), 80: ('Open water: all rain stays', (100, 100, 100)),
         90: ('Wetland: treated as impervious (ASSUMPTION)', (98, 98, 98)),
         95: ('Mangrove: treated as impervious (ASSUMPTION)', (98, 98, 98))}
SOIL = {'B': 0, 'C': 1, 'D': 2}


def load_grids(dem_file='dem.tif'):
    with rasterio.open(GRIDS / dem_file) as f:
        dem, transform, crs = f.read(1).astype('float64'), f.transform, f.crs
    with rasterio.open(GRIDS / 'landcover.tif') as f:
        lc = f.read(1)
    with rasterio.open(GRIDS / 'sea.tif') as f:
        sea = f.read(1).astype(bool)
    # Keep the main island only: crop to the largest land component plus a margin of sea.
    labels, n = ndimage.label(~sea)
    main = labels == (np.bincount(labels.ravel())[1:].argmax() + 1)
    rows, cols = np.where(main)
    r0, r1, c0, c1 = max(rows.min() - 5, 0), rows.max() + 6, max(cols.min() - 5, 0), cols.max() + 6
    window = (slice(r0, r1), slice(c0, c1))
    transform = transform * rasterio.Affine.translation(c0, r0)
    with rasterio.open(GRIDS / 'roads.tif') as f:
        roads = f.read(1).astype(bool)
    return dem[window], lc[window], ~main[window], transform, crs, roads[window]


def event_rain(start, hours):
    data = json.loads(RAIN.read_text())['hourly']
    times = data['time']
    i = times.index(start)
    return np.array([p or 0.0 for p in data['precipitation'][i:i + hours]]), times[i:i + hours]


def scs_excess(p_cum, s):
    """Cumulative runoff depth (mm) for cumulative rainfall p_cum (mm), TR-55 eq. 2-3 with Ia = 0.2 S."""
    ia = 0.2 * s
    return np.where(p_cum > ia, (p_cum - ia) ** 2 / (p_cum + 0.8 * s + 1e-12), 0.0)


def run(name, rain_mm, times, drainage_mm_h, soil, dem_file='dem.tif', drain_roads=False):
    dem, lc, sea, transform, crs, roads = load_grids(dem_file)
    dx = transform.a
    land = ~sea
    n = np.vectorize(lambda c: MANNING.get(int(c), (None, 0.035))[1])(lc)
    cn = np.vectorize(lambda c: CURVE.get(int(c), (None, (98, 98, 98)))[1][SOIL[soil]])(lc).astype(float)
    s = 25400.0 / cn - 254.0  # mm
    drained_cells = ((lc == 50) | (roads & drain_roads)) & land
    drain = np.where(drained_cells, drainage_mm_h / 1000 / 3600, 0.0)  # m/s
    z = np.where(sea, np.minimum(dem, 0.0), dem)

    h = np.zeros_like(z)
    qx = np.zeros((z.shape[0], z.shape[1] - 1))  # flux per unit width (m2/s) between columns j and j+1
    qy = np.zeros((z.shape[0] - 1, z.shape[1]))  # between rows i and i+1
    n2x = (0.5 * (n[:, 1:] + n[:, :-1])) ** 2
    n2y = (0.5 * (n[1:, :] + n[:-1, :])) ** 2
    p_cum = 0.0
    runoff_prev = np.zeros_like(z)
    hourly, max_depth = [], np.zeros_like(z)
    t, total = 0.0, 3600.0 * len(rain_mm)
    volumes = {'rain_m3': 0.0, 'runoff_m3': 0.0, 'drained_m3': 0.0, 'to_sea_m3': 0.0}
    tic = time.time()
    for hour, p in enumerate(rain_mm):
        # rainfall excess for this hour, spread evenly over the hour
        runoff_now = scs_excess(p_cum + p, s)
        excess_rate = np.where(land, (runoff_now - runoff_prev) / 1000 / 3600, 0.0)  # m/s
        volumes['rain_m3'] += p / 1000 * land.sum() * dx * dx
        volumes['runoff_m3'] += float((runoff_now - runoff_prev)[land].sum()) / 1000 * dx * dx
        runoff_prev, p_cum = runoff_now, p_cum + p
        t_end = (hour + 1) * 3600.0
        while t < t_end:
            dt = min(ALPHA * dx / np.sqrt(G * max(h.max(), 0.01)), t_end - t, 10.0)
            eta = z + h
            # x faces
            hf = np.maximum(eta[:, 1:], eta[:, :-1]) - np.maximum(z[:, 1:], z[:, :-1])
            wet = hf > H_MIN
            slope = (eta[:, 1:] - eta[:, :-1]) / dx
            hf_s = np.where(wet, hf, 1.0)
            qx = np.where(wet, (qx - G * hf_s * dt * slope) /
                          (1 + G * dt * n2x * np.abs(qx) / hf_s ** (7 / 3)), 0.0)
            # y faces
            hf = np.maximum(eta[1:, :], eta[:-1, :]) - np.maximum(z[1:, :], z[:-1, :])
            wet = hf > H_MIN
            slope = (eta[1:, :] - eta[:-1, :]) / dx
            hf_s = np.where(wet, hf, 1.0)
            qy = np.where(wet, (qy - G * hf_s * dt * slope) /
                          (1 + G * dt * n2y * np.abs(qy) / hf_s ** (7 / 3)), 0.0)
            # limit outflow so no cell goes below zero depth
            out = (np.pad(np.maximum(qx, 0), ((0, 0), (0, 1))) + np.pad(np.maximum(-qx, 0), ((0, 0), (1, 0))) +
                   np.pad(np.maximum(qy, 0), ((0, 1), (0, 0))) + np.pad(np.maximum(-qy, 0), ((1, 0), (0, 0))))
            avail = h * dx / dt
            scale = np.where(out > avail, avail / np.maximum(out, 1e-12), 1.0)
            qx = np.where(qx > 0, qx * scale[:, :-1], qx * scale[:, 1:])
            qy = np.where(qy > 0, qy * scale[:-1, :], qy * scale[1:, :])
            div = np.zeros_like(h)
            div[:, :-1] -= qx
            div[:, 1:] += qx
            div[:-1, :] -= qy
            div[1:, :] += qy
            h = h + dt * (div / dx + excess_rate)
            drained = np.minimum(h, drain * dt)
            h -= drained
            volumes['drained_m3'] += float(drained.sum()) * dx * dx
            volumes['to_sea_m3'] += float(h[sea].sum()) * dx * dx
            h[sea] = 0.0
            h = np.maximum(h, 0.0)
            max_depth = np.maximum(max_depth, h)
            t += dt
        hourly.append(h.astype('float16'))
        print(f'{name} {times[hour]} rain {p:5.1f} mm  max depth {h[land].max():.2f} m  '
              f'cells > 0.3 m {(h > 0.3).sum():6d}  wall {time.time() - tic:5.0f} s', flush=True)

    out = ROOT / 'output' / 'flood' / name
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / 'depth_hourly.npz', depth=np.stack(hourly), times=np.array(times),
                        transform=np.array(transform)[:6])
    profile = dict(driver='GTiff', height=h.shape[0], width=h.shape[1], count=1, dtype='float32', crs=crs,
                   transform=transform, compress='deflate')
    with rasterio.open(out / 'max_depth.tif', 'w', **profile) as f:
        f.write(max_depth.astype('float32'), 1)
    stored = float(h[land].sum()) * dx * dx
    summary = {'run': name, 'start': times[0], 'hours': len(rain_mm), 'rain_total_mm': float(rain_mm.sum()),
               'drainage_mm_h': drainage_mm_h, 'drain_roads': drain_roads, 'soil_group': soil, 'dem': dem_file, **volumes, 'stored_end_m3': stored,
               'mass_error_pct': 100 * (volumes['runoff_m3'] - volumes['drained_m3'] - volumes['to_sea_m3'] - stored)
               / max(volumes['runoff_m3'], 1),
               'area_max_gt_0.1m_km2': float((max_depth > 0.1)[land].sum()) * dx * dx / 1e6,
               'area_max_gt_0.3m_km2': float((max_depth > 0.3)[land].sum()) * dx * dx / 1e6,
               'wall_s': time.time() - tic}
    (out / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', default='2026-10-26T07:00')
    ap.add_argument('--hours', type=int, default=72)
    ap.add_argument('--drainage', type=float, nargs='+', default=[10.0])
    ap.add_argument('--soil', default='C', choices=list(SOIL))
    ap.add_argument('--dem', default='dem.tif', help='grid in data/processed/flood, e.g. dem_conditioned.tif')
    ap.add_argument('--drain-roads', action='store_true', help='also drain road cells (roadside drains)')
    a = ap.parse_args()
    rain, times = event_rain(a.start, a.hours)
    for d in a.drainage:
        tag = ('' if a.dem == 'dem.tif' else '_' + a.dem.removesuffix('.tif')) + ('_roads' if a.drain_roads else '')
        tag += '' if a.hours == 72 else f'_{a.hours}h'
        run(f'oct2569_drain{d:g}_soil{a.soil}{tag}', rain, times, d, a.soil, a.dem, a.drain_roads)
