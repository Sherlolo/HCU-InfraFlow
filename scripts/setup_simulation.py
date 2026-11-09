"""Install a supplied DCUSim wheel directly into the selected container's Python."""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--wheel',required=True);p.add_argument('--wheelhouse')
    a=p.parse_args()
    if sys.version_info[:2]!=(3,10):raise SystemExit('Select a CPython 3.10 environment for the supplied DCUSim wheel')
    if importlib.util.find_spec('numpy'):
        import numpy
        if int(numpy.__version__.split('.')[0])!=1:raise SystemExit('Select a container with NumPy 1.x; shared NumPy is not silently downgraded')
    wheel=Path(a.wheel).resolve(strict=True)
    flags=['--no-index','--find-links',str(Path(a.wheelhouse).resolve())] if a.wheelhouse else []
    subprocess.run([sys.executable,'-m','pip','install',*flags,str(wheel),'numpy>=1.19,<2','openpyxl','et_xmlfile'],check=True)
    subprocess.run([sys.executable,'-c','import dcusim,numpy,openpyxl;print(dcusim.__version__)'],check=True)
    print(json.dumps({'simulation_python':sys.executable,'simulation_wheel':str(wheel),'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
