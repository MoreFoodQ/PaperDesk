"""Synthetic end-to-end check; never opens the user's library or credentials."""
import http.cookiejar
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.smoke_backend import probe_pdf

results = {}
with tempfile.TemporaryDirectory(prefix='paperdesk-fixed-') as folder:
    home = Path(folder)
    session = 'SYNTHETIC-SESSION-NOT-A-USER-CREDENTIAL'
    env = dict(os.environ, EASYREAD_HOME=str(home), PAPERDESK_SESSION=session, PYTHONUTF8='1')
    env.pop('EASYREAD_LIBRARY', None)
    (home/'config.json').write_text(json.dumps({'engine': 'none', 'auto_translate': False}), encoding='utf-8')
    pdf = home/'probe.pdf'; pdf.write_bytes(probe_pdf())
    subprocess.run([sys.executable, '-m', 'easyread', 'import', str(pdf), '--no-translate'], cwd=ROOT, env=env, check=True, capture_output=True, timeout=60)
    process = subprocess.Popen([sys.executable, '-m', 'easyread', 'serve', '--port', '0'], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if (home/'.server.json').exists(): break
            if process.poll() is not None: raise RuntimeError('Isolated service exited')
            time.sleep(.1)
        info = json.loads((home/'.server.json').read_text(encoding='utf-8'))
        url = info['url']
        try:
            urllib.request.urlopen(url+'/api/library', timeout=5)
            raise AssertionError('Missing session was accepted')
        except urllib.error.HTTPError as exc:
            results['unauthenticated_read_denied'] = exc.code == 401
        jar = http.cookiejar.CookieJar()
        browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        with browser.open(url+'/auth?session='+session, timeout=5) as response:
            results['launcher_redirect_opens_workspace'] = response.status == 200 and response.geturl() == url+'/'
        cookies = list(jar)
        results['session_cookie_httponly_strict'] = bool(cookies and cookies[0].has_nonstandard_attr('HttpOnly') and cookies[0].get_nonstandard_attr('SameSite') == 'Strict')
        with browser.open(url+'/api/library', timeout=5) as response:
            library = json.load(response)
        pid = library['items'][0]['id']
        with browser.open(url+'/api/p/'+pid+'/state', timeout=5) as response:
            state = json.load(response)
        results['authenticated_library_and_reader_work'] = state['id'] == pid
        with browser.open(url+'/p/'+pid+'/pages/page-001.webp', timeout=5) as response:
            image = response.read()
        results['pdf_render_image_works'] = image[:4] == b'RIFF' and image[8:12] == b'WEBP'
        # Exercise actual offline generation with a real rendered synthetic page.
        with browser.open(url+'/api/p/'+pid+'/export', timeout=10) as response:
            exported = response.read().decode('utf-8')
        results['offline_export_contains_valid_image'] = 'data:image/webp;base64,' in exported
        results['disk_session_protected'] = session not in (home/'.server.json').read_text(encoding='utf-8') if os.name == 'nt' else (home/'.server.json').stat().st_mode & 0o777 == 0o600
    finally:
        try:
            req = urllib.request.Request(url+'/api/shutdown', data=b'{}', headers={'X-Token': session})
            urllib.request.urlopen(req, timeout=5).close()
            process.wait(timeout=10)
        except Exception:
            process.terminate(); process.wait(timeout=10)
assert all(results.values()), results
(ROOT/'outputs').mkdir(exist_ok=True)
(ROOT/'outputs/source-smoke.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps(results))
