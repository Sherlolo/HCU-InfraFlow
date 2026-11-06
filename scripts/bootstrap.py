"""Create a project-local Python environment without requiring distro ensurepip."""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--wheelhouse');parser.add_argument('--test',action='store_true')
    args=parser.parse_args()
    if sys.version_info<(3,10):raise SystemExit('Python >=3.10 required; select the verified container interpreter')
    root=Path(__file__).resolve().parents[1];env=root/'.venv'
    subprocess.run([sys.executable,'-m','venv','--without-pip',str(env)],check=True)
    python=env/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    flags=['--no-index','--find-links',str(Path(args.wheelhouse).resolve())] if args.wheelhouse else []
    subprocess.run([sys.executable,'-m','pip','--python',str(python),'install',*flags,'pip','setuptools>=69.5','wheel'],check=True)
    subprocess.run([str(python),'-m','pip','install','--no-build-isolation',*flags,'-e',str(root)+('[test]' if args.test else '')],check=True)
    print(json.dumps({'status':'complete','python':str(python),'project':str(root)}))


if __name__=='__main__':main()
