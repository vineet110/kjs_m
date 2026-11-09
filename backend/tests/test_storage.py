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


def test_signed_list_request_matches_aws_example():
    """AWS's published "GET Bucket (List Objects)" example: GET /?max-keys=2&prefix=J."""
    from app.core.storage import _sign_headers
    h = _sign_headers(method="GET", host="examplebucket.s3.amazonaws.com", path="/", body=b"",
                      access_key="AKIAIOSFODNN7EXAMPLE", secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                      region="us-east-1", now=datetime(2013, 5, 24, tzinfo=timezone.utc),
                      query={"max-keys": "2", "prefix": "J"})
    assert h["authorization"].endswith("Signature=34b48302e7b5fa45bde8084f4b7868a86f0a534bc59db6670ed5711ef69dc6f7")


def test_list_answer_is_read_page_by_page():
    from app.core.storage import parse_list
    xml = (b'<?xml version="1.0" encoding="UTF-8"?><ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
           b'<IsTruncated>true</IsTruncated><NextContinuationToken>abc</NextContinuationToken>'
           b'<Contents><Key>board/A/1-x.pdf</Key><Size>12</Size><ETag>"e1"</ETag></Contents>'
           b'<Contents><Key>board/A/2-y.csv</Key><Size>3</Size><ETag>"e2"</ETag></Contents></ListBucketResult>')
    items, token = parse_list(xml)
    assert items == [{"key": "board/A/1-x.pdf", "size": 12, "etag": "e1"}, {"key": "board/A/2-y.csv", "size": 3, "etag": "e2"}]
    assert token == "abc"
    assert parse_list(xml.replace(b"<IsTruncated>true", b"<IsTruncated>false"))[1] is None


def test_an_empty_key_never_addresses_the_whole_bucket(monkeypatch):
    from app.core import storage as st
    monkeypatch.setattr(st.settings, "R2_ACCOUNT_ID", "acc")
    s = st.R2Storage(bucket="b", access_key="k", secret_key="s")
    for call in (lambda: s.get(""), lambda: s.delete(""), lambda: s.put("", b"x", "text/plain")):
        with pytest.raises(StorageError):
            call()
