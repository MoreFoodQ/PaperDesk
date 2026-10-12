"""Protect optional API credentials with the Windows user account (DPAPI).

Codex authentication remains in the official CLI; PaperDesk never copies it.
"""
from __future__ import annotations

import base64
import copy
import ctypes
import os
from ctypes import wintypes

PREFIX = "dpapi:v1:"


def seal(value: str) -> str:
    return PREFIX + base64.b64encode(_crypt(value.encode('utf-8'))).decode('ascii') if os.name == 'nt' else value


def unseal(value: str) -> str:
    return _crypt(base64.b64decode(value[len(PREFIX):]), True).decode('utf-8') if value.startswith(PREFIX) else value


def _crypt(data: bytes, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise ValueError("API credential storage requires Windows; use Codex CLI on other platforms.")

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    result = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    operation = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    operation.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    operation.restype = wintypes.BOOL
    if not operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        kernel.LocalFree(ctypes.cast(result.data, ctypes.c_void_p))


def transform(cfg: dict, decrypt: bool = False) -> dict:
    out = copy.deepcopy(cfg)
    api = out.get("openai") or {}

    def convert(value):
        if not value:
            return value
        if decrypt:
            return _crypt(base64.b64decode(value[len(PREFIX):]), True).decode("utf-8") if value.startswith(PREFIX) else value
        return value if value.startswith(PREFIX) else PREFIX + base64.b64encode(_crypt(value.encode("utf-8"))).decode("ascii")

    if api.get("api_key"):
        api["api_key"] = convert(api["api_key"])
    if api.get("keys"):
        api["keys"] = {key: convert(value) for key, value in api["keys"].items()}
    return out
