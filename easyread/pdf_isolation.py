"""PDF crash/time/memory containment. This is not an OS file-access sandbox."""
import ctypes
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from .store import dir_lock

_slots = threading.BoundedSemaphore(2)


def _job(process):
    from ctypes import wintypes as w
    class Basic(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64), ('flags', w.DWORD),
                    ('minimum', ctypes.c_size_t), ('maximum', ctypes.c_size_t), ('active', w.DWORD),
                    ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ('read_count','write_count','other_count','read_bytes','write_bytes','other_bytes')]
    class Extended(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                    ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]; kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    if not handle: raise ctypes.WinError(ctypes.get_last_error())
    limits = Extended()
    limits.basic.flags = 0x2000 | 0x200 | 0x4  # kill on close, job memory, job CPU time
    limits.basic.job_time = 60*10_000_000
    limits.job_memory = 1536*1024*1024
    try:
        if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.AssignProcessToJobObject(handle, w.HANDLE(int(process._handle))):
            raise ctypes.WinError(ctypes.get_last_error())
    except BaseException:
        kernel.CloseHandle(handle); raise
    return lambda: kernel.CloseHandle(handle)


def run(operation, root, *args):
    directory = root.parent if operation == 'title' else root
    with _slots, dir_lock(directory, '.pdf-worker.lock', timeout=130, stale_after=150):
        dependencies = str(Path(sys.prefix)/('Lib/site-packages' if os.name == 'nt' else f'lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages'))
        executable = getattr(sys, '_base_executable', sys.executable)
        argv = [executable, '-I', str(Path(__file__).with_name('pdf_worker.py')), dependencies, operation, json.dumps([str(root), *args])]
        if getattr(sys, 'frozen', False):
            argv = [sys.executable, '--pdf-worker', '', operation, json.dumps([str(root), *args])]
        env = {k: v for k, v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','LANG','LC_ALL'}}
        env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
        proc = subprocess.Popen(argv, cwd=str(directory), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=0x08000000 if os.name == 'nt' else 0)
        close = lambda: None
        try:
            if os.name == 'nt': close = _job(proc)
            stdout, stderr = proc.communicate(timeout=120)
            if proc.returncode:
                raise ValueError('PDF processing failed or exceeded the safety limit')
            if len(stdout) > 5_000_000: raise ValueError('PDF result too large')
            return json.loads(stdout)
        except subprocess.TimeoutExpired:
            raise ValueError('PDF processing exceeded 120 seconds') from None
        finally:
            close()
            if proc.poll() is None: proc.kill()
            proc.wait(timeout=10)
