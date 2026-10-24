"""File storage behind one small interface (backlog D16).

    store = storage()
    store.put(key, data, content_type)
    store.get(key) -> bytes
    store.delete(key)
    store.url(key) -> a short-lived download link (R2) or None (local: the API streams it)

Drivers: "local" (a folder on disk, for dev) and "r2" (Cloudflare R2, S3-compatible).
Pick with STORAGE_DRIVER in .env. The database only keeps the key, never the bytes.

R2 speaks the S3 API. Instead of the large boto3 package we sign requests ourselves with
AWS Signature V4 (standard library hmac/hashlib; see sigv4_presign / _sign_headers).
"""
import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

from app.core.config import settings


class StorageError(Exception):
    pass


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:  # never escape the storage folder
            raise StorageError("bad key")
        return p

    def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as e:
            raise StorageError("missing") from e

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def url(self, key: str, filename: str = "") -> str | None:
        return None


# ---------- AWS Signature V4 (used for R2) ----------
def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def _signing_key(secret: str, day: str, region: str) -> bytes:
    k = _hmac(("AWS4" + secret).encode(), day)
    k = _hmac(k, region)
    k = _hmac(k, "s3")
    return _hmac(k, "aws4_request")


def _canonical_query(params: dict[str, str]) -> str:
    return "&".join(f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in sorted(params.items()))


def sigv4_presign(*, method: str, host: str, path: str, access_key: str, secret_key: str, region: str,
                  expires: int, now: datetime, extra_query: dict[str, str] | None = None) -> str:
    """A URL that works for `expires` seconds without any headers (used for downloads)."""
    stamp, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    scope = f"{day}/{region}/s3/aws4_request"
    params = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": f"{access_key}/{scope}",
        "X-Amz-Date": stamp,
        "X-Amz-Expires": str(expires),
        "X-Amz-SignedHeaders": "host",
        **(extra_query or {}),
    }
    canonical = "\n".join([method, quote(path, safe="/-_.~"), _canonical_query(params),
                           f"host:{host}\n", "host", "UNSIGNED-PAYLOAD"])
    to_sign = "\n".join(["AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    sig = hmac.new(_signing_key(secret_key, day, region), to_sign.encode(), hashlib.sha256).hexdigest()
    return f"https://{host}{quote(path, safe='/-_.~')}?{_canonical_query(params)}&X-Amz-Signature={sig}"


def _sign_headers(*, method: str, host: str, path: str, body: bytes, access_key: str, secret_key: str,
                  region: str, now: datetime, content_type: str = "") -> dict[str, str]:
    """Headers for a normal signed request (upload / delete)."""
    stamp, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(body).hexdigest()
    headers = {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": stamp}
    if content_type:
        headers["content-type"] = content_type
    names = sorted(headers)
    canonical = "\n".join([method, quote(path, safe="/-_.~"), "",
                           "".join(f"{n}:{headers[n]}\n" for n in names), ";".join(names), payload_hash])
    scope = f"{day}/{region}/s3/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    sig = hmac.new(_signing_key(secret_key, day, region), to_sign.encode(), hashlib.sha256).hexdigest()
    headers["authorization"] = (f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
                                f"SignedHeaders={';'.join(names)}, Signature={sig}")
    del headers["host"]  # httpx sets it
    return headers


class R2Storage:
    """Cloudflare R2. Needs R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET."""

    region = "auto"

    def __init__(self):
        if not all([settings.R2_ACCOUNT_ID, settings.R2_ACCESS_KEY_ID, settings.R2_SECRET_ACCESS_KEY, settings.R2_BUCKET]):
            raise StorageError("R2 settings missing in .env")
        self.host = f"{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    def _path(self, key: str) -> str:
        return f"/{settings.R2_BUCKET}/{key}"

    def _request(self, method: str, key: str, body: bytes = b"", content_type: str = "") -> httpx.Response:
        headers = _sign_headers(method=method, host=self.host, path=self._path(key), body=body,
                                access_key=settings.R2_ACCESS_KEY_ID, secret_key=settings.R2_SECRET_ACCESS_KEY,
                                region=self.region, now=datetime.now(timezone.utc), content_type=content_type)
        url = f"https://{self.host}{quote(self._path(key), safe='/-_.~')}"
        r = httpx.request(method, url, content=body, headers=headers, timeout=60)
        if r.status_code >= 300 and not (method == "DELETE" and r.status_code == 404):
            raise StorageError(f"R2 {method} failed: {r.status_code}")
        return r

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._request("PUT", key, data, content_type)

    def get(self, key: str) -> bytes:
        return self._request("GET", key).content

    def delete(self, key: str) -> None:
        self._request("DELETE", key)

    def url(self, key: str, filename: str = "") -> str | None:
        extra = {"response-content-disposition": f'attachment; filename="{filename}"'} if filename else None
        return sigv4_presign(method="GET", host=self.host, path=self._path(key),
                             access_key=settings.R2_ACCESS_KEY_ID, secret_key=settings.R2_SECRET_ACCESS_KEY,
                             region=self.region, expires=300, now=datetime.now(timezone.utc), extra_query=extra)


_store: LocalStorage | R2Storage | None = None


def storage() -> LocalStorage | R2Storage:
    global _store
    if _store is None:
        _store = R2Storage() if settings.STORAGE_DRIVER == "r2" else LocalStorage(settings.FILE_STORAGE_PATH)
    return _store
