"""Off-site backup (app/backup_r2.py): nothing is ever lost from the backup bucket by the nightly copy,
removed uploads stay KEEP days, database backups are kept KEEP days, one file can be put back."""
from datetime import date

import pytest

from app import backup_r2 as b
from app.core.storage import StorageError


class Bucket:
    """An R2 bucket in memory (same methods as R2Storage)."""

    def __init__(self, objs=None):
        self.objs = dict(objs or {})

    def put(self, key, data, content_type):
        self.objs[key] = data

    def get(self, key):
        if key not in self.objs:
            raise StorageError("missing")
        return self.objs[key]

    def delete(self, key):
        self.objs.pop(key, None)

    def list(self, prefix=""):
        return [{"key": k, "size": len(v), "etag": ""} for k, v in sorted(self.objs.items()) if k.startswith(prefix)]


def test_new_uploads_are_copied_and_removed_ones_kept_for_a_while():
    app = Bucket({"board/A/1-po.pdf": b"%PDF", "product/x/2-a.png": b"png"})
    bkp = Bucket()
    assert b.sync_files(app, bkp, date(2026, 11, 9), 30)["copied"] == 2
    assert b.sync_files(app, bkp, date(2026, 11, 9), 30)["copied"] == 0  # nothing new: nothing copied

    del app.objs["board/A/1-po.pdf"]  # an approved delete (or a mistake)
    r = b.sync_files(app, bkp, date(2026, 11, 10), 30)
    assert r["moved_to_deleted"] == 1
    assert bkp.get("deleted/2026-11-10/board/A/1-po.pdf") == b"%PDF" and "files/board/A/1-po.pdf" not in bkp.objs

    b.sync_files(app, bkp, date(2026, 12, 9), 30)  # 29 days later: still kept
    assert "deleted/2026-11-10/board/A/1-po.pdf" in bkp.objs
    assert b.sync_files(app, bkp, date(2026, 12, 11), 30)["dropped_old"] == 1  # 31 days: gone for good
    assert bkp.objs.keys() == {"files/product/x/2-a.png"}


def test_a_lost_upload_can_be_put_back():
    app, bkp = Bucket({"board/A/1-po.pdf": b"%PDF"}), Bucket()
    b.sync_files(app, bkp, date(2026, 11, 9), 30)
    app.objs.clear()
    b.sync_files(app, bkp, date(2026, 11, 10), 30)
    assert b.restore_file(app, bkp, "board/A/1-po.pdf") == "deleted/2026-11-10/board/A/1-po.pdf"
    assert app.get("board/A/1-po.pdf") == b"%PDF"
    with pytest.raises(StorageError):
        b.restore_file(app, bkp, "board/A/never.pdf")


def test_database_backups_are_kept_30_days_and_an_empty_one_is_refused():
    bkp = Bucket()
    assert b.put_db(bkp, "db-20261009.dump.enc", b"x", date(2026, 10, 9), 30)["stored"] == "db/2026-10-09/db-20261009.dump.enc"
    r = b.put_db(bkp, "/tmp/db-20261110.dump.enc", b"y", date(2026, 11, 10), 30)
    assert r["stored"] == "db/2026-11-10/db-20261110.dump.enc" and r["dropped_old"] == 1
    with pytest.raises(StorageError):
        b.put_db(bkp, "empty.enc", b"", date(2026, 11, 10), 30)


def test_a_rewritten_upload_keeps_the_copy_we_had():
    """Upload keys are never reused: a changed size means a rewrite, so the old copy is kept in deleted/."""
    app, bkp = Bucket({"board/A/1-po.pdf": b"%PDF good"}), Bucket()
    b.sync_files(app, bkp, date(2026, 11, 9), 30)
    app.objs["board/A/1-po.pdf"] = b"junk"
    assert b.sync_files(app, bkp, date(2026, 11, 10), 30)["replaced"] == 1
    assert bkp.get("deleted/2026-11-10/board/A/1-po.pdf") == b"%PDF good"
