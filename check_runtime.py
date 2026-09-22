"""Verify the installed distribution versions against the production lock."""
from importlib import metadata
from pathlib import Path
import json
import platform
import sys


def check():
    mismatches=[]
    if sys.version_info[:2]!=(3,12) or platform.architecture()[0]!='64bit':
        mismatches.append('Required Python 3.12 64-bit')
    versions={}
    for line in (Path(__file__).parent/'requirements-lock.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'):continue
        name,expected=line.split('==')
        try:actual=metadata.version(name)
        except metadata.PackageNotFoundError:actual=None
        versions[name]=actual
        if actual!=expected:mismatches.append(f'{name}: expected {expected}, installed {actual}')
    print(json.dumps({'python':sys.version,'executable':sys.executable,'versions':versions,'mismatches':mismatches},indent=2))
    return bool(mismatches)


if __name__=='__main__':raise SystemExit(check())
