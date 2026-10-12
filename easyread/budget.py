"""Shared local daily call and reported-token guard; never infers provider balance."""
import threading
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from . import config
from .store import read_json, write_json_atomic, dir_lock

_lock = threading.RLock()


def _today(): return datetime.now(timezone(timedelta(hours=8))).date().isoformat()
def _path(day=None): return config.HOME/('usage-budget-'+(day or _today())+'.json')


def _load(day=None):
    day = day or _today()
    data = read_json(_path(day), {}) or {}
    return data if data.get('day') == day else {'day': day, 'calls': 0, 'reported_tokens': 0}


def snapshot():
    with _lock:
        return {**_load(), 'limits': config.load().get('budget', {}), 'timezone': 'Asia/Taipei'}


def validate(options):
    if not isinstance(options, dict): raise ValueError('Invalid budget settings')
    for key, value in options.items():
        if key not in ('daily_calls', 'daily_tokens') or type(value) is not int or not 0 <= value <= 1_000_000_000:
            raise ValueError('Budget must be a nonnegative integer')


@contextmanager
def call(meter):
    from .engines import EngineError
    limits = config.load().get('budget', {})
    config.HOME.mkdir(parents=True, exist_ok=True)
    with _lock, dir_lock(config.HOME, '.budget.lock'):
        data = _load()
        day = data['day']
        if (limits.get('daily_calls') and data['calls'] >= limits['daily_calls']) or (limits.get('daily_tokens') and data['reported_tokens'] >= limits['daily_tokens']):
            raise EngineError('PaperDesk daily usage limit reached; change it in Settings → Usage')
        data['calls'] += 1
        write_json_atomic(_path(day), data)
    try:
        yield
    finally:
        usage = meter.snapshot()
        with _lock, dir_lock(config.HOME, '.budget.lock'):
            data = _load(day)
            data['reported_tokens'] += max(0, int(usage.get('input', 0))+int(usage.get('output', 0)))
            write_json_atomic(_path(day), data)


def forward(local, total):
    if total is None: return
    data = local.snapshot()
    if data.get('calls'):
        total.add(**{k: data[k] for k in ('input','cached','output','cost_usd','limits','context_window') if k in data})
