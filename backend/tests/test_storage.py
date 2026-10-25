"""R2 request signing must match AWS's published Signature V4 example exactly."""
from datetime import datetime, timezone

import pytest

from app.core.storage import LocalStorage, StorageError, sigv4_presign


def test_presign_matches_aws_example():
    url = sigv4_presign(method="GET", host="examplebucket.s3.amazonaws.com", path="/test.txt",
                        access_key="AKIAIOSFODNN7EXAMPLE", secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                        region="us-east-1", expires=86400, now=datetime(2013, 5, 24, tzinfo=timezone.utc))
    assert url.endswith("X-Amz-Signature=aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404")


def test_local_storage_cannot_escape_its_folder(tmp_path):
    store = LocalStorage(str(tmp_path))
    store.put("board/a.txt", b"hi", "text/plain")
    assert store.get("board/a.txt") == b"hi"
    with pytest.raises(StorageError):
        store.get("../../etc/passwd")
