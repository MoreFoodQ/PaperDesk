"""Curated source ZIP, SHA-256 manifest and privacy gate; never publishes."""
import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ('easyread', 'tests', 'scripts', 'licenses', 'electron', '.github', 'img')
FILES = ('README.md', 'README.en.md', 'LICENSE', 'pyproject.toml', 'package.json', 'package-lock.json',
         'requirements-lock.txt', 'requirements-hashed.txt', 'requirements-build-hashed.txt', 'Build-PaperDesk.cmd', 'Open-PaperDesk.cmd', 'Setup-PaperDesk.cmd', 'start.cmd',
         '.gitignore', 'CONNECTIONS.md', 'ARCHITECTURE.md', 'PROVENANCE.md',
         'CONTRIBUTING.md', 'SECURITY.md', 'docs/USAGE.md', 'docs/VALIDATION.md', 'docs/RELEASE.md', 'docs/FORMATS.md', 'docs/FIGURE-TRANSLATION.md', '.gitattributes')
PRIVATE = {'data', '.tools', '.venv', '.git', '.codex', '.aws', '.claude', 'node_modules', '__pycache__', 'security-audit', 'outputs', 'verification', '.impeccable'}
OMIT = {'scripts/configure_fork.py'}
SECRETS = re.compile(rb'(?<![A-Za-z0-9_-])(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,}|'
                     rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|dpapi:v1:[A-Za-z0-9+/=]{32,}|'
                     rb'eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,})')


def candidates(root=ROOT):
    paths = [root/name for name in FILES]
    for directory in DIRECTORIES:
        paths.extend((root/directory).rglob('*'))
    return sorted({p for p in paths if p.is_file() and not (PRIVATE & {x.lower() for x in p.relative_to(root).parts})
                   and p.relative_to(root).as_posix() not in OMIT and p.suffix.lower() not in ('.pyc', '.log', '.pdf', '.epub')
                   and not (p.name.startswith('.env') or p.suffix == '.env')
                   and not (p.relative_to(root).parts[0] == 'licenses' and p.suffix == '.py')})


def check(root=ROOT):
    if (root/'.git').exists():
        tracked = subprocess.run(['git', 'ls-files', '-z'], cwd=root, check=True, capture_output=True).stdout.decode('utf-8').split('\0')
        bad = [p for p in tracked if p and ({x.lower() for x in Path(p).parts} & PRIVATE or Path(p).name.lower() in ('auth.json', 'config.json', '.server.json') or Path(p).name.startswith('.env') or Path(p).suffix.lower() in ('.env', '.pdf', '.epub'))]
        if bad: raise ValueError('Private files tracked by Git: '+', '.join(bad))
        history = subprocess.run(['git', 'log', '--all', '--format=', '--name-only', '--', 'data', '.tools', '.venv', '.codex', '.aws', '.claude', '*.env', '.env*', 'config.json', 'auth.json'], cwd=root, check=True, capture_output=True).stdout
        if history.strip(): raise ValueError('Private paths exist in Git history; review before publishing')
    paths = candidates(root)
    for name in ('LICENSE', 'Setup-PaperDesk.cmd', 'requirements-hashed.txt', 'scripts/codex/package-lock.json'):
        if not (root/name).is_file(): raise ValueError('Required release file missing: '+name)
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Release path escapes project: '+str(path.relative_to(root)))
        if SECRETS.search(path.read_bytes()):
            # Report locations only. Never echo matched credentials.
            raise ValueError('Possible credential in release file: '+str(path.relative_to(root)))
    lock = json.loads((root/'scripts/codex/package-lock.json').read_text(encoding='utf-8'))
    for name, item in lock['packages'].items():
        if name and (not str(item.get('resolved', '')).startswith('https://registry.npmjs.org/') or not item.get('integrity')):
            raise ValueError('Codex runtime package lacks official registry / integrity: '+name)
    return paths


def build(root=ROOT):
    paths = check(root)
    version = json.loads((root/'package.json').read_text(encoding='utf-8')).get('version', '')
    if not isinstance(version, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?', version):
        raise ValueError('Invalid release version in package.json')
    manifest = {'version': version, 'edition': 'windows-source', 'files': {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    out = root/'outputs'; out.mkdir(exist_ok=True)
    archive = out/f'paperdesk-{version}-source.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in paths:
            info = zipfile.ZipInfo('paperdesk/'+path.relative_to(root).as_posix(), (2026, 10, 11, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, path.read_bytes())
        z.writestr('paperdesk/RELEASE-MANIFEST.json', json.dumps(manifest, indent=2)+'\n')
    (out/'RELEASE-MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    (out/'SHA256SUMS.txt').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n', encoding='ascii')
    return archive, len(paths)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--check-only', action='store_true'); args = parser.parse_args()
    if args.check_only: print('PASS: release privacy and dependency integrity gate;', len(check()), 'files')
    else:
        archive, count = build(); print('Created', archive, 'with', count, 'reviewable source files')
