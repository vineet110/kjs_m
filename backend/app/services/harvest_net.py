"""Lead Harvester: safe outbound fetching (security fix after PR #53 review).

The harvester fetches addresses that admins type in, and can attach an API key read from a server setting.
Without limits that allowed two attacks:
1. Secret leak: name ANY server setting (e.g. DATABASE_URL) as the "API key" and point the source at your
   own website: the server sends you the value.
2. SSRF (server-side request forgery): point a source at an internal address (localhost, 10.x, the cloud
   metadata address 169.254.169.254...) and the server fetches it from inside our network.

The rules, checked when a source is saved AND again at every fetch:
1. API key settings must be named HARVEST_<something> (e.g. HARVEST_INDIAMART_KEY). Nothing else is read.
2. Addresses must be https. A specific public http host can be allowed with the HARVEST_ALLOW_HTTP_HOSTS
   setting (comma-separated host names; empty by default).
3. The host must not be localhost or an internal name, and every address must be public.
4. At fetch time the host name is looked up, the private addresses are dropped (refused if none is left),
   and the connection goes to an address we checked. The https certificate is still checked against the
   real host name. Connecting to the checked address also stops "DNS rebinding" (a host answering with a
   public address for our check and a private one for the real connection).
5. Redirects are followed by hand, at most MAX_REDIRECTS, each one checked again; https -> http is refused;
   the API key is only sent to the source's own host, over https.
"""
from __future__ import annotations

import asyncio
import ipaddress
import os
import re
import urllib.parse

import httpx

from app.core.errors import AppError

ENV_PREFIX = "HARVEST_"
ENV_NAME_RE = re.compile(r"^HARVEST_[A-Z0-9_]{1,60}$")
MAX_REDIRECTS = 5
HTTP_TIMEOUT_SECONDS = 30.0
_INTERNAL_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home", ".corp")


def check_env_name(name: str) -> str:
    """'' (no key) or a HARVEST_ name. Raises ValueError with what to do instead."""
    name = (name or "").strip()
    if not name:
        return ""
    if not ENV_NAME_RE.match(name):
        hint = re.sub(r"[^A-Z0-9_]", "_", name.upper()).removeprefix(ENV_PREFIX)[:60] or "KEY"
        raise ValueError(f"API key settings must be named HARVEST_..., e.g. rename {name} to HARVEST_{hint}.")
    return name


def allowed_http_hosts() -> set[str]:
    """Public hosts an admin explicitly allowed over plain http (HARVEST_ALLOW_HTTP_HOSTS)."""
    return {h.strip().lower() for h in os.getenv("HARVEST_ALLOW_HTTP_HOSTS", "").split(",") if h.strip()}


def is_public_ip(ip: str) -> bool:
    """Only addresses on the public internet. Private, loopback, link-local (incl. 169.254.169.254),
    multicast and reserved ones are not; an IPv6 address wrapping an IPv4 one is judged by that one."""
    try:
        addr = ipaddress.ip_address(ip.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


def check_url(url: str) -> str:
    """The address an admin typed: https (or an allowed http host), a real public host. Raises ValueError."""
    url = (url or "").strip()
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        raise ValueError("That is not a valid web address.") from None
    host = (parts.hostname or "").lower().rstrip(".")
    if parts.scheme not in ("https", "http") or not host:
        raise ValueError("The address must start with https:// and name a website.")
    if parts.scheme == "http" and host not in allowed_http_hosts():
        raise ValueError("Use an https:// address (plain http is only allowed for hosts in HARVEST_ALLOW_HTTP_HOSTS).")
    if parts.username or parts.password:
        raise ValueError("Don't put a user name or password in the address.")
    if host == "localhost" or host.endswith(_INTERNAL_SUFFIXES) or "." not in host.strip("[]"):
        raise ValueError("The address must be a public website, not an internal one.")
    try:
        ipaddress.ip_address(host.strip("[]"))
        is_ip = True
    except ValueError:
        is_ip = False
    if is_ip and not is_public_ip(host.strip("[]")):
        raise ValueError("The address must be a public website, not an internal one.")
    return url


async def resolve(host: str, port: int) -> list[str]:
    """The addresses a host name points to. A separate function so tests can replace it (no internet)."""
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=0)
    return list(dict.fromkeys(info[4][0] for info in infos))


def _blocked(message: str) -> AppError:
    return AppError(400, "blocked_address", message)


async def safe_get(url: str, headers: dict[str, str] | None = None, *, api_key: str = "") -> httpx.Response:
    """GET a harvester address safely (rules 3 to 5 above). `api_key`: sent as a Bearer token, only to the
    source's own host and only over https. Returns the final response (raise_for_status is up to the caller)."""
    first_host = (urllib.parse.urlsplit(url).hostname or "").lower()
    headers = dict(headers or {})
    current, previous_scheme = url, None
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                check_url(current)
            except ValueError as e:
                raise _blocked(str(e)) from None
            parts = urllib.parse.urlsplit(current)
            if previous_scheme == "https" and parts.scheme == "http":
                raise _blocked("A redirect tried to go from https to plain http.")
            host = parts.hostname.lower()
            port = parts.port or (443 if parts.scheme == "https" else 80)
            try:
                found = await resolve(host, port)
            except OSError:
                raise AppError(400, "host_not_found", f"Could not find the website {host}.") from None
            public = [ip for ip in found if is_public_ip(ip)]
            if not public:
                raise _blocked(f"{host} points to an internal address.")
            ip = public[0]
            # Connect to the address we checked; the Host header and the https check use the real name.
            netloc = f"[{ip}]" if ":" in ip else ip
            if parts.port:
                netloc += f":{parts.port}"
            pinned = urllib.parse.urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))
            send = {k: v for k, v in headers.items() if k.lower() != "authorization"}
            send["Host"] = parts.netloc.split("@")[-1]
            if api_key and parts.scheme == "https" and host == first_host:
                send["Authorization"] = f"Bearer {api_key}"
            resp = await client.get(pinned, headers=send, extensions={"sni_hostname": host})
            location = resp.headers.get("location")
            if resp.status_code in (301, 302, 303, 307, 308) and location:
                previous_scheme = parts.scheme
                current = urllib.parse.urljoin(current, location)
                continue
            return resp
    raise _blocked(f"Too many redirects (more than {MAX_REDIRECTS}).")
