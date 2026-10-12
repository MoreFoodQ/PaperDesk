"""Stage the pinned official native CLI; never copy an account directory."""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare(root=ROOT):
    if os.name != 'nt':
        raise ValueError('Desktop distribution currently requires Windows x64.')
    lock = json.loads((root / 'scripts/codex/package-lock.json').read_text(encoding='utf-8'))
    expected = lock['packages']['node_modules/@openai/codex']['version']
    package = root / '.tools/codex/node_modules/@openai/codex-win32-x64'
    info = json.loads((package / 'package.json').read_text(encoding='utf-8'))
    if info.get('version') != expected + '-win32-x64':
        raise ValueError('Native Codex package does not match the project lock.')
    src = package / 'vendor/x86_64-pc-windows-msvc'
    layout = json.loads((src / 'codex-package.json').read_text(encoding='utf-8'))
    if layout.get('version') != expected or layout.get('entrypoint') != 'bin/codex.exe':
        raise ValueError('Unexpected Codex runtime layout.')
    dst = root / 'build/codex'
    if not src.resolve().is_relative_to(root.resolve()) or not dst.resolve().is_relative_to(root.resolve()):
        raise ValueError('Runtime paths leave the project.')
    # A new staging directory avoids retaining unexpected files from a previous build.
    stage = Path(tempfile.mkdtemp(prefix='codex-stage-', dir=root / 'build'))
    manifest = {}
    try:
        for file in src.rglob('*'):
            if file.is_symlink() or not file.resolve().is_relative_to(src.resolve()):
                raise ValueError('Linked files are not allowed in the runtime.')
            if not file.is_file():
                continue
            rel = file.relative_to(src)
            # PaperDesk disables realtime conversation. Do not distribute unused
            # native audio libraries or their separate redistribution requirements.
            if rel.parts[:2] == ('codex-resources', 'voice'):
                continue
            if file.suffix.lower() not in {'.exe', '.dll', '.json', '.md', '.txt'}:
                raise ValueError('Unexpected native runtime file type.')
            target = stage / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
            manifest[rel.as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(prefix='codex-version-') as home:
            env = {k: v for k, v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','USERPROFILE','APPDATA','LOCALAPPDATA'}}
            env['CODEX_HOME'] = home
            result = subprocess.run([str(stage / 'bin/codex.exe'), '--version'], env=env,
                                    capture_output=True, text=True, timeout=30, creationflags=0x08000000)
            if result.returncode or result.stdout.strip() != 'codex-cli ' + expected:
                raise ValueError('Native Codex version check failed.')
        (stage / 'PAPERDESK-RUNTIME.json').write_text(json.dumps({'version': expected, 'omitted_features': ['voice'], 'files': manifest}, indent=2), encoding='utf-8')
        if dst.exists():
            if dst.is_symlink() or not dst.resolve().is_relative_to(root / 'build'):
                raise ValueError('Unsafe existing runtime directory.')
            # Only this dedicated generated staging directory is replaced.
            shutil.rmtree(dst)
        stage.rename(dst)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    print('Staged official Codex', expected, 'with', len(manifest), 'files; no credentials.')
    return dst


if __name__ == '__main__':
    (ROOT / 'build').mkdir(exist_ok=True)
    prepare()
