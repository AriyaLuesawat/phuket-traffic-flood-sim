"""Step 3: builds the SUMO road network of Phuket province from the OSM extract.

    .venv/bin/python scripts/build_network.py

Inputs : data/raw/osm/thailand-latest.osm.pbf (Geofabrik)
Outputs: data/processed/phuket-boundary.geojson, data/processed/phuket-roads.osm,
         network/phuket.net.xml, docs/network-report.md, docs/img/step3-network.png
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import sumo
import sumolib

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data' / 'raw' / 'osm' / 'thailand-latest.osm.pbf'
PROC = ROOT / 'data' / 'processed'
NET = ROOT / 'network' / 'phuket.net.xml'
BIN = Path(sys.executable).parent
TYPEMAP = Path(sumo.SUMO_HOME) / 'data' / 'typemap' / 'osmNetconvert.typ.xml'

# Roads open to cars. Service roads, tracks and paths are left out: they are mostly driveways and
# car parks, carry no through traffic, and would make the network several times larger.
ROAD_TYPES = [
    'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'unclassified', 'residential', 'living_street',
    'motorway_link', 'trunk_link', 'primary_link', 'secondary_link', 'tertiary_link',
]


def run(*cmd):
    print('$', ' '.join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


def province_boundary():
    """Exports the admin_level=4 polygon of จังหวัดภูเก็ต as GeoJSON for osmium extract."""
    out = PROC / 'phuket-boundary.geojson'
    tmp = PROC / 'admin.pbf'
    run('osmium', 'tags-filter', RAW, 'r/boundary=administrative', '-o', tmp, '--overwrite')
    lines = subprocess.run(['osmium', 'export', str(tmp), '--geometry-types=polygon', '-f', 'geojsonseq'],
                           capture_output=True, text=True, check=True).stdout.splitlines()
    tmp.unlink()
    for line in filter(None, (l.lstrip('\x1e').strip() for l in lines)):
        feature = json.loads(line)
        p = feature['properties']
        if p.get('admin_level') == '4' and p.get('name:en') == 'Phuket Province':
            out.write_text(json.dumps({'type': 'FeatureCollection', 'features': [feature]}))
            return out
    raise SystemExit('Phuket Province boundary not found in OSM extract')


def allow_cars_where_tagged(osm_file):
    """Rewrites access=no + motorcar/motor_vehicle=yes (car-only underpasses on ทล.402, where motorcycles
    are banned) as motorcycle=no. netconvert reads access=no but not the more specific motorcar=yes, so it
    would otherwise close these ways to cars and cut the highway in two."""
    import xml.etree.ElementTree as ET
    tree = ET.parse(osm_file)
    fixed = 0
    for way in tree.getroot().iter('way'):
        tags = {t.get('k'): t for t in way.iter('tag')}
        if tags.get('access') is not None and tags['access'].get('v') == 'no' and any(
                k in tags and tags[k].get('v') == 'yes' for k in ('motorcar', 'motor_vehicle')):
            way.remove(tags['access'])
            if 'motorcycle' not in tags:
                ET.SubElement(way, 'tag', k='motorcycle', v='no')
            fixed += 1
    tree.write(osm_file, encoding='utf-8', xml_declaration=True)
    print(f'car-only ways reopened to cars: {fixed}')


def main():
    PROC.mkdir(parents=True, exist_ok=True)
    NET.parent.mkdir(parents=True, exist_ok=True)
    boundary = province_boundary()

    clipped = PROC / 'phuket-province.osm.pbf'
    roads = PROC / 'phuket-roads.osm'
    run('osmium', 'extract', '-p', boundary, '--strategy=smart', RAW, '-o', clipped, '--overwrite')
    # Keep the road ways plus every node they reference (signals, crossings) and turn restrictions.
    run('osmium', 'tags-filter', clipped, *[f'w/highway={t}' for t in ROAD_TYPES], 'r/type=restriction',
        '-o', roads, '--overwrite')

    allow_cars_where_tagged(roads)

    run(BIN / 'netconvert',
        '--osm-files', roads,
        '--type-files', TYPEMAP,
        '-o', NET,
        '--keep-edges.by-vclass', 'passenger',
        '--remove-edges.isolated',
        '--geometry.remove', '--roundabouts.guess', '--ramps.guess',
        '--junctions.join', '--junctions.corner-detail', '5',
        '--tls.guess-signals', '--tls.discard-simple', '--tls.join', '--tls.default-type', 'actuated',
        '--output.street-names', '--output.original-names',
        '--lefthand',  # Thailand drives on the left
        '--proj.utm',
        '--no-warnings',
        '--log', PROC / 'netconvert.log')


if __name__ == '__main__':
    os.chdir(ROOT)
    main()
