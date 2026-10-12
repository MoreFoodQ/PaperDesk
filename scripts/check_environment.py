"""Validate the bounded Windows source-release environment."""
import argparse
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--cli', action='store_true')
args = parser.parse_args()
if os.name != 'nt' or sys.maxsize <= 2**32 or platform.machine().lower() not in ('amd64', 'x86_64'):
    raise SystemExit('This release requires 64-bit Windows and x64 Python.')
if not (3, 10) <= sys.version_info[:2] <= (3, 13):
    raise SystemExit('Use Python 3.12 (recommended); supported versions are 3.10 through 3.13.')
if args.cli:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from easyread.engines import codex_path
    exe = codex_path({})
    if not exe or not Path(exe).is_relative_to(root/'.tools'):
        raise SystemExit('Project-local native Codex is missing; rerun Setup-PaperDesk.cmd.')
    env = dict(os.environ, CODEX_HOME=str(root/'data'/'cli-install-check'))
    result = subprocess.run([exe, '--version'], capture_output=True, text=True, env=env, timeout=20,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode or not re.match(r'^codex-cli 0\.162\.1(?:\s|$)', result.stdout.strip()):
        raise SystemExit('Installed Codex does not match frozen version 0.162.1.')
print('PASS: Windows source-release environment' + (' and pinned native Codex CLI' if args.cli else ''))
