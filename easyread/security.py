"""Trust boundaries for downloaded URLs and generated paper assets."""
from pathlib import Path
from urllib.parse import urlsplit
import ipaddress
import re
import socket

ASSET = re.compile(r"(?:pages|figures)/[A-Za-z0-9_.-]+\.(?:webp|png|jpe?g)$", re.I)


def asset_path(root: Path, rel) -> Path | None:
    if not isinstance(rel, str) or not ASSET.fullmatch(rel):
        return None
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        return None
    # Inspect bytes, rather than trusting the extension supplied by a model.
    with path.open('rb') as f:
        head = f.read(12)
    if not (head.startswith(b'\x89PNG\r\n\x1a\n') or head.startswith(b'\xff\xd8\xff')
            or (head.startswith(b'RIFF') and head[8:12] == b'WEBP')):
        return None
    return path


def origin(url: str) -> tuple:
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Only HTTP(S) URLs without embedded credentials are allowed')
    return p.scheme, p.hostname.lower(), p.port or (443 if p.scheme == 'https' else 80)


def public_ip(value: str) -> bool:
    address = ipaddress.ip_address(value)
    if not address.is_global or address.is_multicast or address.is_loopback or address.is_link_local or address.is_unspecified:
        return False
    if address.version == 4:
        # Python versions differ on the IETF protocol-assignment block.
        if address in ipaddress.ip_network('192.0.0.0/24') and str(address) not in ('192.0.0.9', '192.0.0.10'):
            return False
        return not address.is_reserved
    if address.ipv4_mapped: return public_ip(str(address.ipv4_mapped))
    if address.sixtofour: return public_ip(str(address.sixtofour))
    if address.teredo: return all(public_ip(str(a)) for a in address.teredo)
    if address in ipaddress.ip_network('64:ff9b:1::/48'): return False
    if address in ipaddress.ip_network('64:ff9b::/96'):
        return public_ip(str(ipaddress.IPv4Address(int(address) & 0xffffffff)))
    return not address.is_reserved


def public_addresses(host: str, port: int):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not public_ip(a[4][0]) for a in addresses):
        raise ValueError('Paper downloads cannot access local or private networks')
    return addresses


def validate_api(url: str, key: str = ''):
    scheme, host, _ = origin(url)
    if key and scheme != 'https':
        try:
            local = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = host == 'localhost'
        if not local:
            raise ValueError('API keys require HTTPS outside this computer')
