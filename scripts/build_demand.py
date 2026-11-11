"""Step 4b: builds hourly traffic demand for each study period, matched to the count stations.

    .venv/bin/python scripts/build_demand.py            # all periods
    .venv/bin/python scripts/build_demand.py evening_peak

For every period the simulation runs 30 min of warm-up plus the study hour. Target counts at each station
= AADT per direction x share of that hour (config/hourly_profile.csv). SUMO's routeSampler then picks routes
from a pool of candidate routes so that the counts at the stations are matched.

Outputs: demand/vtypes.add.xml, demand/<period>/counts.xml, demand/<period>/<group>.rou.xml
"""
import csv
import os
import subprocess
import sys
from pathlib import Path

import sumo

ROOT = Path(__file__).resolve().parent.parent
NET = ROOT / 'network' / 'phuket.net.xml'
OUT = Path(os.environ.get('DEMAND_DIR', ROOT / 'demand'))
BIN = Path(sys.executable).parent
TOOLS = Path(sumo.SUMO_HOME) / 'tools'

PERIODS = {  # name -> study hour (local time)
    'night': 3,
    'morning_peak': 8,
    'late_morning': 10,
    'midday': 12,
    'evening_peak': 17,
    'evening': 20,
}
GROUPS = {  # vehicle group -> SUMO vClass
    'car': 'passenger',
    'bus': 'bus',
    'truck': 'truck',
    'motorcycle': 'motorcycle',
}
WARMUP = 1800  # seconds simulated before the study hour
CANDIDATES = 40000  # candidate routes per vehicle class
# routeSampler counts a vehicle at every station on its route within its departure interval, although a long
# trip reaches its later stations after the interval ends. Capping the route length keeps that error small.
MAX_ROUTE_KM = float(os.environ.get('MAX_ROUTE_KM', 10))


def run(*cmd):
    print('$', ' '.join(str(c) for c in cmd)[:200])
    subprocess.run([str(c) for c in cmd], check=True)


def hourly_shares():
    rows = [r for r in csv.DictReader(l for l in open(ROOT / 'config' / 'hourly_profile.csv') if not l.startswith('#'))]
    shares = [float(r['share']) for r in rows]
    total = sum(shares)
    return [s / total for s in shares]  # normalise so the 24 hours sum to exactly 1


def write_vtypes():
    # SUMO default parameters for each class; motorcycles get the sublane-free default model, so they
    # queue like small cars and do not filter between lanes (a stated limitation).
    path = OUT / 'vtypes.add.xml'
    path.write_text("""<additional>
    <vType id="car" vClass="passenger" color="0.9,0.9,0.9"/>
    <vType id="bus" vClass="bus" color="0.2,0.5,0.9"/>
    <vType id="truck" vClass="truck" color="0.6,0.4,0.2"/>
    <vType id="motorcycle" vClass="motorcycle" color="1,0.6,0"/>
</additional>
""")
    return path


def candidate_routes(vclass):
    """A pool of plausible routes for one vehicle class, cached in data/processed."""
    routes = ROOT / 'data' / 'processed' / f'candidates_{vclass}.rou.xml'
    if routes.exists():
        return routes
    trips = routes.with_suffix('.trips.xml')
    run(BIN / 'python', TOOLS / 'randomTrips.py', '-n', NET, '-o', trips, '-r', routes,
        '--vehicle-class', vclass, '--vclass', vclass,
        '-b', 0, '-e', CANDIDATES, '-p', 1,
        '--lanes', '--length',              # start/end more often on long, multi-lane roads
        '--fringe-factor', 3,               # some trips enter/leave over the Sarasin bridge
        '--min-distance', 500, '--remove-loops', '--validate', '--seed', 42)
    return routes


def station_routes(vclass, stations, per_edge=60):
    """Routes through every count-station edge, from origins to destinations 1-4 km away on either side.
    Without them, the length cap leaves some stations on minor roads with no candidate route at all."""
    routes = ROOT / 'data' / 'processed' / f'candidates_{vclass}.stations.rou.xml'
    if routes.exists():
        return routes
    import random
    import sumolib
    net = sumolib.net.readNet(str(NET))
    usable = [e for e in net.getEdges() if e.allows(vclass)]
    rng = random.Random(42)
    trips = ['<routes>', f'    <vType id="{vclass}" vClass="{vclass}"/>']
    n = 0
    for edge_id in sorted({e for s in stations for e in s['edges'].split()}):
        x, y = net.getEdge(edge_id).getShape()[len(net.getEdge(edge_id).getShape()) // 2]
        ring = [e for e in usable if 1000 <= ((e.getFromNode().getCoord()[0] - x) ** 2 +
                                              (e.getFromNode().getCoord()[1] - y) ** 2) ** 0.5 <= 4000]
        for _ in range(per_edge if ring else 0):
            trips.append(f'    <trip id="{n}" type="{vclass}" depart="0" from="{rng.choice(ring).getID()}" '
                         f'to="{rng.choice(ring).getID()}" via="{edge_id}"/>')
            n += 1
    trips.append('</routes>')
    trip_file = routes.with_suffix('.trips.xml')
    trip_file.write_text('\n'.join(trips) + '\n')
    run(BIN / 'duarouter', '-n', NET, '--route-files', trip_file, '-o', routes,
        '--ignore-errors', '--no-warnings', '--remove-loops', '--seed', 42)
    return routes


def short_routes(*pools):
    """Merges candidate pools, keeping the routes no longer than MAX_ROUTE_KM. Cached next to the first pool."""
    out = pools[0].with_name(pools[0].name.replace('.rou.xml', f'.max{MAX_ROUTE_KM:g}km.rou.xml'))
    if out.exists():
        return out
    import xml.etree.ElementTree as ET
    import sumolib
    length = {e.getID(): e.getLength() for e in sumolib.net.readNet(str(NET)).getEdges()}
    root = ET.Element('routes')
    for pool in pools:
        for vehicle in ET.parse(pool).getroot().iter('vehicle'):
            if sum(length[e] for e in vehicle.find('route').get('edges').split()) <= MAX_ROUTE_KM * 1000:
                vehicle.set('id', f'{len(root)}')
                root.append(vehicle)
    ET.ElementTree(root).write(out, encoding='utf-8', xml_declaration=True)
    print(f'{out.name}: {len(root)} routes')
    return out


def write_counts(period, hour, shares, stations):
    """edgeData file with target counts for the warm-up half hour and the study hour, per vehicle group."""
    begin = hour * 3600 - WARMUP
    # Half-hour intervals: routeSampler aggregates all intervals to one length, so mixed 30/60-minute
    # intervals would give each half of the study hour the full hourly count.
    intervals = [(begin, hour * 3600, shares[(hour - 1) % 24] / 2),
                 (hour * 3600, hour * 3600 + 1800, shares[hour] / 2),
                 (hour * 3600 + 1800, hour * 3600 + 3600, shares[hour] / 2)]
    lines = ['<data>']
    for b, e, share in intervals:
        lines.append(f'    <interval id="{period}_{b}" begin="{b}" end="{e}">')
        per_edge = {}
        for s in stations:
            edges = s['edges'].split()
            for edge in edges:
                counts = {g: round(int(s[g]) / len(edges) * share) for g in GROUPS}
                old = per_edge.get(edge)
                if old is None or sum(counts.values()) > sum(old.values()):
                    per_edge[edge] = counts  # two stations on one edge: keep the larger count
        for edge, counts in sorted(per_edge.items()):
            attrs = ' '.join(f'{g}="{n}"' for g, n in counts.items())
            lines.append(f'        <edge id="{edge}" {attrs}/>')
        lines.append('    </interval>')
    lines.append('</data>')
    path = OUT / period / 'counts.xml'
    path.write_text('\n'.join(lines) + '\n')
    return path, begin, hour * 3600 + 3600


def main(periods):
    OUT.mkdir(exist_ok=True)
    write_vtypes()
    shares = hourly_shares()
    stations = list(csv.DictReader(open(ROOT / 'data' / 'processed' / 'count_stations.csv', encoding='utf-8')))
    pools = {g: short_routes(candidate_routes(v), station_routes(v, stations)) for g, v in GROUPS.items()}
    for period in periods:
        hour = PERIODS[period]
        (OUT / period).mkdir(exist_ok=True)
        counts, begin, end = write_counts(period, hour, shares, stations)
        for group in GROUPS:
            run(BIN / 'python', TOOLS / 'routeSampler.py', '-r', pools[group], '-d', counts,
                '--edgedata-attribute', group, '-o', OUT / period / f'{group}.rou.xml',
                '--prefix', f'{group}_', '-a', f'type="{group}"',
                '-b', begin, '-e', end, '--seed', 42,
                '--mismatch-output', OUT / period / f'{group}.mismatch.xml')


if __name__ == '__main__':
    main(sys.argv[1:] or list(PERIODS))
