"""Step 6a: builds the 30 m grids for the flood model on UTM 47N (EPSG:32647).

    .venv/bin/python scripts/prepare_flood_inputs.py              # grids
    .venv/bin/python scripts/prepare_flood_inputs.py condition    # conditioned DEM + road mask (needs the grids)
    .venv/bin/python scripts/prepare_flood_inputs.py fabdem       # FABDEM on the same grid, raw + conditioned
    .venv/bin/python scripts/prepare_flood_inputs.py burn         # FABDEM with OSM streams burned in + conditioned

Grids (data/processed/flood/*.tif, same shape and transform):
  dem.tif        Copernicus DEM GLO-30 reprojected (bilinear). A DSM: includes buildings and trees.
  landcover.tif  ESA WorldCover 2021 v200 class, resampled to 30 m by majority (mode).
  sea.tif        1 where the cell is outside the land of Phuket province (fixed water level 0 m).

Inputs : data/processed/phuket_cop30.tif, data/processed/phuket-boundary.geojson,
         ESA WorldCover tile N06E096, read remotely (only the needed window) from the AWS open-data bucket.
"""
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import Resampling, reproject, transform_bounds, transform_geom

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / 'data' / 'processed'
OUT = PROC / 'flood'
CRS = 'EPSG:32647'
RES = 30.0
WORLDCOVER = ('/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/'
              'ESA_WorldCover_10m_2021_v200_N06E096_Map.tif')


def grid(boundary):
    """Grid covering the province boundary plus a 300 m margin of sea."""
    left, bottom, right, top = transform_bounds('EPSG:4326', CRS, *boundary_bounds(boundary))
    left, bottom = np.floor(left / RES) * RES - 300, np.floor(bottom / RES) * RES - 300
    right, top = np.ceil(right / RES) * RES + 300, np.ceil(top / RES) * RES + 300
    width, height = int(round((right - left) / RES)), int(round((top - bottom) / RES))
    return rasterio.transform.from_origin(left, top, RES, RES), (height, width)


def boundary_bounds(geom):
    coords = np.array([c for poly in (geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']])
                       for ring in poly for c in ring])
    return coords[:, 0].min(), coords[:, 1].min(), coords[:, 0].max(), coords[:, 1].max()


def warp(src_path, transform, shape, resampling, dtype):
    out = np.zeros(shape, dtype=dtype)
    with rasterio.open(src_path) as src:
        reproject(rasterio.band(src, 1), out, dst_transform=transform, dst_crs=CRS, resampling=resampling,
                  dst_nodata=0)
    return out


def save(name, array, transform, nodata=None):
    profile = dict(driver='GTiff', height=array.shape[0], width=array.shape[1], count=1, dtype=array.dtype,
                   crs=CRS, transform=transform, compress='deflate', nodata=nodata)
    with rasterio.open(OUT / name, 'w', **profile) as dst:
        dst.write(array, 1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    boundary = json.loads((PROC / 'phuket-boundary.geojson').read_text())['features'][0]['geometry']
    transform, shape = grid(boundary)
    dem = warp(PROC / 'phuket_cop30.tif', transform, shape, Resampling.bilinear, 'float32')
    landcover = warp(WORLDCOVER, transform, shape, Resampling.mode, 'uint8')

    inside = ~geometry_mask([transform_geom('EPSG:4326', CRS, boundary)], shape, transform)
    # The province polygon may include sea around the islands, so sea is also any water-class cell at or below
    # 0.5 m that is connected to the grid edge.
    from scipy import ndimage
    wet_low = (landcover == 80) & (dem <= 0.5) | (dem <= 0)
    labels, _ = ndimage.label(wet_low | ~inside)
    edge_labels = np.unique(np.r_[labels[0], labels[-1], labels[:, 0], labels[:, -1]])
    sea = np.isin(labels, edge_labels[edge_labels > 0]) | ~inside

    save('dem.tif', dem, transform, nodata=-9999)
    save('landcover.tif', landcover, transform, nodata=0)
    save('sea.tif', sea.astype('uint8'), transform)
    land = ~sea
    print(f'grid {shape[1]} x {shape[0]} cells at {RES:g} m, land cells {land.sum():,} '
          f'({land.sum() * RES * RES / 1e6:.0f} km2)')
    classes, counts = np.unique(landcover[land], return_counts=True)
    print('land cover on land:', {int(c): f'{100 * n / land.sum():.1f}%' for c, n in zip(classes, counts)})


if __name__ == '__main__' and len(__import__('sys').argv) == 1:
    main()


# ---- Step 6d: DEM conditioning and road mask (added after the first run flooded thousands of DSM pits) ----
FILL_MAX = 1.0  # m; ASSUMPTION: depressions in built-up/open land shallower than this are DSM artefacts


def condition_dem(fill_max=FILL_MAX, name='dem_conditioned.tif', source='dem.tif'):
    """Removes spurious pits from the DSM before the flood run.

    Depression filling by morphological reconstruction gives the same surface as Priority-Flood (Barnes et al.
    2014): every pit is raised to its spill level. Pits are then kept or filled per depression:
      - filled when the depression is mostly tree cover (canopy gaps in the DSM) or open water (ponds start
        full), or when its deepest point is shallower than fill_max;
      - kept otherwise, as real low ground in built-up or open land.
    fill_max = inf fills every depression. source is the grid to condition. Output: name
    """
    from scipy import ndimage
    from skimage.morphology import reconstruction
    with rasterio.open(OUT / source) as f:
        dem, transform = f.read(1).astype('float64'), f.transform
    with rasterio.open(OUT / 'landcover.tif') as f:
        lc = f.read(1)
    with rasterio.open(OUT / 'sea.tif') as f:
        sea = f.read(1).astype(bool)
    z = np.where(sea, np.minimum(dem, 0.0), dem)
    seed = np.where(sea, z, z.max())
    seed[0, :], seed[-1, :], seed[:, 0], seed[:, -1] = z[0, :], z[-1, :], z[:, 0], z[:, -1]
    filled = reconstruction(seed, z, method='erosion')
    depth = filled - z
    labels, n = ndimage.label(depth > 0.01)
    idx = np.arange(1, n + 1)
    max_depth = ndimage.maximum(depth, labels, idx)
    tree_share = ndimage.mean((lc == 10).astype(float), labels, idx)
    water_share = ndimage.mean((lc == 80).astype(float), labels, idx)
    fill = (max_depth < fill_max) | (tree_share > 0.5) | (water_share > 0.5)
    fill_cells = np.zeros(n + 1, bool)
    fill_cells[1:] = fill
    out = np.where(fill_cells[labels], filled, z).astype('float32')
    kept = ~fill_cells[labels] & (labels > 0)
    save(name, out, transform, nodata=-9999)
    print(f'depressions: {n:,}, filled {fill.sum():,}, kept {n - fill.sum():,} '
          f'({kept.sum() * RES * RES / 1e6:.1f} km2 of kept depression area)')


def road_mask():
    """1 on cells crossed by an edge of the SUMO network (lane centre lines sampled every 5 m)."""
    import sumolib
    net = sumolib.net.readNet(str(ROOT / 'network' / 'phuket.net.xml'))
    ox, oy = net.getLocationOffset()
    with rasterio.open(OUT / 'dem.tif') as f:
        transform, shape = f.transform, f.shape
    mask = np.zeros(shape, 'uint8')
    for edge in net.getEdges():
        pts = np.array(edge.getShape()) - (ox, oy)  # net x,y -> UTM 47N
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            k = max(int(np.hypot(x1 - x0, y1 - y0) / 5), 1)
            xs, ys = np.linspace(x0, x1, k + 1), np.linspace(y0, y1, k + 1)
            cols, rows = ~transform * (xs, ys)
            ok = (rows >= 0) & (rows < shape[0]) & (cols >= 0) & (cols < shape[1])
            mask[rows[ok].astype(int), cols[ok].astype(int)] = 1
    save('roads.tif', mask, transform)
    print(f'road cells: {mask.sum():,}')


# ---- Step 6e: FABDEM (Hawker et al. 2022), Copernicus GLO-30 with buildings and forest removed ----
def fabdem_grid():
    """Reprojects FABDEM V1-2 (data/processed/phuket_fabdem.tif, from the `fabdem` package) to the model grid."""
    with rasterio.open(OUT / 'dem.tif') as f:
        transform, shape = f.transform, f.shape
    dem = warp(PROC / 'phuket_fabdem.tif', transform, shape, Resampling.bilinear, 'float32')
    save('dem_fabdem.tif', dem, transform, nodata=-9999)
    with rasterio.open(OUT / 'dem.tif') as f:
        cop = f.read(1)
    with rasterio.open(OUT / 'sea.tif') as f:
        land = ~f.read(1).astype(bool)
    with rasterio.open(OUT / 'landcover.tif') as f:
        lc = f.read(1)
    diff = cop - dem
    for c, label in [(10, 'tree'), (50, 'built-up')]:
        m = land & (lc == c)
        print(f'Copernicus minus FABDEM on {label}: mean {diff[m].mean():.2f} m, median {np.median(diff[m]):.2f} m')
    condition_dem(name='dem_fabdem_conditioned.tif', source='dem_fabdem.tif')


# ---- Step 7 fix: stream burning (Lindsay 2016), after roads in step 7 flooded far more than the news reported ----
BURN_M = 2.0  # m; ASSUMPTION: streams narrower than a 30 m cell are missing from the DEM, lowered by this depth


def burn_streams(source='dem_fabdem.tif', name='dem_fabdem_burned.tif'):
    """Lowers the DEM by BURN_M along OSM waterway lines (data/processed/phuket-waterways.geojsonseq) so that
    water collects in the channels instead of spreading over the flood plain, then conditions it as before."""
    from pyproj import Transformer
    from rasterio.features import rasterize
    from shapely.geometry import shape as geom
    from shapely.ops import transform as reproject
    to_utm = Transformer.from_crs('EPSG:4326', CRS, always_xy=True).transform
    lines = [reproject(to_utm, geom(json.loads(row.strip('\x1e'))['geometry']))
             for row in open(PROC / 'phuket-waterways.geojsonseq')]
    with rasterio.open(OUT / source) as f:
        dem, transform = f.read(1), f.transform
    stream = rasterize(lines, out_shape=dem.shape, transform=transform, all_touched=True).astype(bool)
    save(name, np.where(stream, dem - BURN_M, dem).astype('float32'), transform, nodata=-9999)
    print(f'burned {stream.sum():,} stream cells by {BURN_M:g} m')
    condition_dem(name=name.replace('.tif', '_conditioned.tif'), source=name)


if __name__ == '__main__' and len(__import__('sys').argv) > 1 and __import__('sys').argv[1] == 'burn':
    burn_streams()


if __name__ == '__main__' and len(__import__('sys').argv) > 1 and __import__('sys').argv[1] == 'fabdem':
    fabdem_grid()


if __name__ == '__main__' and len(__import__('sys').argv) > 1 and __import__('sys').argv[1] == 'condition':
    condition_dem()
    condition_dem(np.inf, 'dem_filled_all.tif')  # sensitivity: no depression kept
    road_mask()
