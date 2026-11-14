"""Passwords, session tokens and IP hashing. Standard library only (no extra packages)."""
import hashlib
import ipaddress
import hmac
import secrets

from app.core.config import settings

# scrypt is a slow, memory-hard password hash (like Argon2). These are the
# commonly recommended interactive-login parameters (~16 MB of memory per hash).
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


# LEGACY: passwords live in Firebase now (app/core/firebase.py). These two only remain for accounts made
# before Firebase (users.password_hash) and for tests/conftest.py. Never use them to log anyone in.
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p)
        )
    except ValueError:
        return False
    # compare_digest takes the same time whether the first or last byte differs (no timing leak)
    return hmac.compare_digest(digest.hex(), digest_hex)


def new_session_token() -> str:
    """The random value that goes into the browser cookie."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """We store only a hash of the session token, so a DB leak doesn't leak live sessions."""
    return hashlib.sha256(token.encode()).hexdigest()


def rate_key(ip: str | None) -> str | None:
    """The key the rate limits count by (CR6). One home or phone connection gets a whole IPv6 /64 block
    (billions of addresses), so the block counts as one visitor. IPv4, and IPv4 written as IPv6
    (::ffff:1.2.3.4), stay per address. Never fails: anything that isn't an address is used as it is.
    Only for limits: leads and audit rows keep the hash of the real address."""
    if not ip:
        return None
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if isinstance(addr, ipaddress.IPv6Address):
        if addr.ipv4_mapped:
            return str(addr.ipv4_mapped)
        return str(ipaddress.ip_network(f"{addr}/64", strict=False))
    return str(addr)


def hash_ip(ip: str | None) -> str | None:
    """DPDP: we keep a keyed hash of the IP (for rate limits / abuse), never the raw IP."""
    if not ip:
        return None
    return hmac.new(settings.SECRET_KEY.encode(), ip.encode(), hashlib.sha256).hexdigest()
