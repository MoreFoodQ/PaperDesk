"""Read official Codex account quotas without starting a model turn."""
import json
import math
import queue
import threading
import time
from pathlib import Path

from . import codex_lean, config, engines

_lock = threading.Lock()
_cached = None


def normalize(result):
    buckets = result.get('rateLimitsByLimitId')
    if not isinstance(buckets, dict) or not buckets:
        legacy = result.get('rateLimits')
        buckets = {legacy.get('limitId') or 'codex': legacy} if isinstance(legacy, dict) else {}
    out = []
    for name, bucket in buckets.items():
        if not isinstance(bucket, dict): continue
        windows = []
        for key in ('primary', 'secondary'):
            value = bucket.get(key)
            if not isinstance(value, dict): continue
            used = value.get('usedPercent')
            if isinstance(used, bool) or not isinstance(used, (int, float)) or not math.isfinite(used): continue
            used = max(0, min(100, used))
            windows.append({'kind': key, 'used_percent': used, 'remaining_percent': 100-used,
                            'window_minutes': value.get('windowDurationMins'), 'resets_at': value.get('resetsAt')})
        if windows:
            out.append({'id': str(name)[:100], 'name': str(bucket.get('limitName') or name)[:100], 'windows': windows})
    return out


def _read(timeout=15):
    cfg = config.load()
    exe = engines.codex_path(cfg.get('codex') or {})
    if not exe: raise ValueError('Codex unavailable')
    proc = engines._popen([exe, 'app-server', '--listen', 'stdio://', *codex_lean.args(), '-c', 'features.hooks=false'], Path.cwd())
    messages = queue.Queue(maxsize=100)
    def read():
        try:
            for line in proc.stdout:
                if len(line) > 1_000_000: break
                try: messages.put_nowait(json.loads(line))
                except (ValueError, queue.Full): continue
        finally:
            try: messages.put_nowait(None)
            except queue.Full: pass
    threading.Thread(target=read, daemon=True).start()
    # Drain diagnostics without storing or exposing potentially sensitive text.
    def drain():
        for _ in proc.stderr: pass
    threading.Thread(target=drain, daemon=True).start()
    deadline = time.monotonic()+timeout
    def send(obj):
        proc.stdin.write(json.dumps(obj)+'\n'); proc.stdin.flush()
    def receive(ident):
        while True:
            left = deadline-time.monotonic()
            if left <= 0: raise TimeoutError()
            obj = messages.get(timeout=left)
            if obj is None: raise ValueError('CLI exited')
            if obj.get('id') == ident:
                if 'error' in obj: raise ValueError('Official quota unavailable')
                return obj.get('result') or {}
            if 'id' in obj and 'method' in obj:
                # Never approve actions or fulfil token-refresh/login requests.
                send({'id': obj['id'], 'error': {'code': -32601, 'message': 'Read-only quota client'}})
    try:
        send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'paperdesk_quota', 'title': 'PaperDesk', 'version': '0.1.0'}}})
        receive(1)
        send({'method': 'initialized', 'params': {}})
        send({'id': 2, 'method': 'account/rateLimits/read'})
        return normalize(receive(2))
    finally:
        if proc.poll() is None: proc.kill()
        proc.wait(timeout=5)
        for stream in (proc.stdin, proc.stdout, proc.stderr): stream.close()


def snapshot(refresh=False):
    global _cached
    with _lock:
        # Repeated refresh clicks cannot spawn an unbounded number of CLIs.
        if _cached and time.time()-_cached['at'] < 60:
            return dict(_cached)
        try:
            buckets = _read()
            status = 'available' if buckets else 'unavailable'
        except Exception:
            buckets, status = [], 'unavailable'
        _cached = {'engine': 'codex', 'source': 'official_cli', 'status': status,
                   'at': int(time.time()), 'buckets': buckets}
        return dict(_cached)
