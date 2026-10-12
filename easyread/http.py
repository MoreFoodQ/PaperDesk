"""HTTPS with system trust and bundled roots, including in frozen builds."""
from __future__ import annotations

import os
import ssl
import urllib.request
import http.client
import socket
from functools import lru_cache

import certifi
import truststore
from .security import origin, public_addresses, validate_api


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = origin(newurl)
        if req.has_header('Authorization') and target != origin(req.full_url):
            raise ValueError('Refusing to forward credentials across origins')
        if origin(req.full_url)[0] == 'https' and target[0] != 'https':
            raise ValueError('Refusing HTTPS downgrade')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _public_connect(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, **kwargs):
    # Resolve once, validate every answer, then connect to that IP. No second
    # hostname lookup between the SSRF check and socket connection.
    addresses = public_addresses(*address)
    last = None
    for family, kind, proto, _, target in addresses:
        sock = socket.socket(family, kind, proto)
        try:
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(target)
            return sock
        except OSError as exc:
            sock.close()
            last = exc
    raise last or OSError('No public address')


class PublicHTTP(urllib.request.HTTPHandler):
    def http_open(self, req):
        origin(req.full_url)
        def factory(*args, **kwargs):
            conn = http.client.HTTPConnection(*args, **kwargs)
            conn._create_connection = _public_connect
            return conn
        return self.do_open(factory, req)


class PublicHTTPS(urllib.request.HTTPSHandler):
    def https_open(self, req):
        origin(req.full_url)
        def factory(*args, **kwargs):
            conn = http.client.HTTPSConnection(*args, **kwargs)
            conn._create_connection = _public_connect
            return conn
        return self.do_open(factory, req, context=self._context)


@lru_cache(maxsize=4)
def _context(cafile: str | None, capath: str | None):
    context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    # Native trust handles macOS Keychain / Windows roots; certifi also makes
    # Linux and PyInstaller builds independent of build-machine CA paths.
    context.load_verify_locations(cafile=certifi.where())
    if cafile or capath:
        context.load_verify_locations(cafile=cafile or None, capath=capath or None)
    return context


def urlopen(url, *args, **kwargs):
    # urllib can redirect an HTTP request to HTTPS, so use this context for
    # both schemes. It keeps hostname and certificate verification enabled.
    public_only = kwargs.pop('public_only', False)
    context = kwargs.pop('context', _context(os.environ.get("SSL_CERT_FILE"), os.environ.get("SSL_CERT_DIR")))
    req = url if isinstance(url, urllib.request.Request) else urllib.request.Request(url)
    origin(req.full_url)
    validate_api(req.full_url, req.get_header('Authorization') or '')
    handlers = [SafeRedirect(), urllib.request.HTTPSHandler(context=context)]
    if public_only:
        # Downloads do not inherit a local proxy that could bypass IP checks.
        handlers = [urllib.request.ProxyHandler({}), SafeRedirect(), PublicHTTP(), PublicHTTPS(context=context)]
    return urllib.request.build_opener(*handlers).open(req, *args, **kwargs)
