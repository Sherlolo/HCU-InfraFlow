"""Install a supplied DCUSim wheel in an explicit isolated environment; never install globally."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--wheel',required=True)
    p.add_argument('--environment',required=True)
    p.add_argument('--wheelhouse')
    a=p.parse_args()
    if sys.version_info[:2] != (3,10): raise SystemExit('The supplied DCUSim wheel requires CPython 3.10')
    wheel=Path(a.wheel).resolve(strict=True);env=Path(a.environment).absolute()
    # Only the selected environment receives packages; reuse the system NumPy read-only.
    subprocess.run([sys.executable,'-m','venv','--system-site-packages','--without-pip',str(env)],check=True)
    python=env/'bin/python'
    flags=['--no-index','--find-links',str(Path(a.wheelhouse).resolve())] if a.wheelhouse else []
    subprocess.run([sys.executable,'-m','pip','--python',str(python),'install',*flags,'--no-deps',str(wheel),'openpyxl','et_xmlfile'],check=True)
    subprocess.run([str(python),'-c','import numpy, openpyxl, dcusim; assert int(numpy.__version__.split(".")[0]) < 2; print(dcusim.__version__)'],check=True)
    print(json.dumps({'simulation_python':str(python),'simulation_wheel':str(wheel),'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest()}))


if __name__=='__main__':main()
