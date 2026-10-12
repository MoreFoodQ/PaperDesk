"""Check the packaged file allowlist and original native runtime hashes."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess


def check(root):
    resources=root/'resources'
    required=[root/'PaperDesk.exe',resources/'app.asar',resources/'backend/easyread-backend.exe',resources/'backend/_internal/python312.dll',resources/'codex/bin/codex.exe',root/'LICENSE.electron.txt',root/'LICENSES.chromium.html',resources/'licenses/Codex-Apache-2.0.txt']
    assert all(p.is_file() for p in required),'Required bundled runtime/license is missing'
    forbidden_dirs={'data','.codex','.aws','.claude','.git','.venv','outputs','verification','security-audit'}
    forbidden_names={'auth.json','config.json','prefs.json','.server.json','credentials.json','.npmrc','.env'}
    for p in root.rglob('*'):
        rel=p.relative_to(root)
        bad={x.lower() for x in rel.parts}&forbidden_dirs
        pdfium_notice=rel.as_posix().startswith('resources/backend/_internal/pypdfium2-5.14.0.dist-info/licenses/data')
        assert not bad or (bad=={'data'} and pdfium_notice),'Private directory in package'
        if p.is_file():
            assert p.name.lower() not in forbidden_names and p.suffix.lower() not in {'.pdf','.epub','.log','.p12','.pfx'},'Private/document file in package'
    runtime=json.loads((resources/'codex/PAPERDESK-RUNTIME.json').read_text(encoding='utf-8'))
    assert runtime['version']=='0.162.1'
    for name,digest in runtime['files'].items():
        file=resources/'codex'/name
        assert file.resolve().is_relative_to((resources/'codex').resolve())
        assert hashlib.sha256(file.read_bytes()).hexdigest()==digest,'Native CLI hash mismatch'
    project=Path(__file__).resolve().parents[1]
    code="const a=require('@electron/asar');const f=a.listPackage(process.argv[1]);const clean=p=>p.split(String.fromCharCode(92)).join('/').slice(1);if(f.some(p=>{const n=clean(p);return n!=='package.json'&&n!=='electron'&&!n.startsWith('electron/')}))process.exit(1);console.log(f.length)"
    result=subprocess.run(['node','-e',code,str(resources/'app.asar')],cwd=project,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,'Unexpected files in desktop ASAR'
    print('PASS: packaged file privacy, original native CLI hashes and runtime license notices')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',nargs='?',default='dist/electron/win-unpacked');args=parser.parse_args();check(Path(args.directory).resolve())
