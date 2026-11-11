"""Checks that every tool the workflow needs is installed: python scripts/check_env.py"""
import importlib
import shutil
import subprocess
import sys

ok = True
for name in ['sumolib', 'traci', 'osmnx', 'geopandas', 'rasterio', 'numpy', 'scipy', 'pyproj', 'shapely']:
    try:
        module = importlib.import_module(name)
        print(f'  ok  {name} {getattr(module, "__version__", "")}')
    except ImportError as e:
        ok = False
        print(f'  --  {name}: {e}')
for tool in ['sumo', 'netconvert', 'duarouter']:
    path = shutil.which(tool)
    if path:
        print(f'  ok  {tool}: {subprocess.run([tool, "--version"], capture_output=True, text=True).stdout.splitlines()[0]}')
    else:
        ok = False
        print(f'  --  {tool} not found (activate .venv first)')
print('Python', sys.version.split()[0])
sys.exit(0 if ok else 1)
