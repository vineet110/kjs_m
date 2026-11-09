"""Off-site backup in the R2 backup bucket (kjs-bkp-prod), run by deploy/backup.sh every night.

Why: uploaded files live only in R2 (STORAGE_DRIVER=r2), and the nightly database backup sits on the
same disk as the database. Without this, a wrong delete, a leaked key or a dead disk loses them for good.

The backup bucket has its own R2 key (R2_BACKUP_*), which the app never gets: backup.sh hands it only to
this command. So a leaked app key can't wipe the backups.

    python -m app.backup_r2 sync-files           copy new uploads into files/; uploads that are gone from
                                                 the app bucket move to deleted/<day>/ and stay KEEP days
    python -m app.backup_r2 put <name> < file    store a database backup (already encrypted by backup.sh)
                                                 as db/<day>/<name>; older than KEEP days are dropped
    python -m app.backup_r2 list [prefix]        what is in the backup bucket
    python -m app.backup_r2 get <key> > file     download one object (e.g. a database backup)
    python -m app.backup_r2 restore-file <key>   put one upload back into the app bucket (from files/, or
                                                 the newest copy in deleted/)

KEEP = OFFSITE_KEEP_DAYS (default 30). Restore steps: deploy/README.md, "Off-site copy".
"""
import mimetypes
import os
import sys
from datetime import date, datetime, timedelta, timezone

from app.core.config import settings
from app.core.storage import R2Storage, StorageError

FILES, DELETED, DB = "files/", "deleted/", "db/"


def backup_bucket() -> R2Storage:
    if not (settings.R2_BACKUP_BUCKET and settings.R2_BACKUP_ACCESS_KEY_ID and settings.R2_BACKUP_SECRET_ACCESS_KEY):
        raise StorageError("R2_BACKUP_BUCKET / R2_BACKUP_ACCESS_KEY_ID / R2_BACKUP_SECRET_ACCESS_KEY missing")
    return R2Storage(bucket=settings.R2_BACKUP_BUCKET, access_key=settings.R2_BACKUP_ACCESS_KEY_ID,
                     secret_key=settings.R2_BACKUP_SECRET_ACCESS_KEY)


def _type(key: str) -> str:
    return mimetypes.guess_type(key)[0] or "application/octet-stream"


def prune(dst, prefix: str, today: date, keep_days: int) -> int:
    """Delete objects under prefix/<YYYY-MM-DD>/ older than keep_days. Returns how many."""
    oldest = today - timedelta(days=keep_days)
    dropped = 0
    for o in dst.list(prefix):
        try:
            day = date.fromisoformat(o["key"][len(prefix):len(prefix) + 10])
        except ValueError:
            continue  # not one of ours: leave it alone
        if day < oldest:
            dst.delete(o["key"])
            dropped += 1
    return dropped


def sync_files(src, dst, today: date, keep_days: int) -> dict:
    """Make files/ in the backup bucket match the app bucket, without ever losing a copy: an upload
    that is gone from the app bucket (approved delete, or a mistake) moves to deleted/<today>/."""
    have = {o["key"][len(FILES):]: o for o in dst.list(FILES)}
    live = {o["key"]: o for o in src.list("")}
    copied = moved = 0
    replaced = 0
    for key, o in live.items():
        if key not in have:
            dst.put(FILES + key, src.get(key), _type(key))
            copied += 1
        elif have[key]["size"] != o["size"]:
            # Upload keys are never reused, so a changed size means the file was rewritten (a mistake, or
            # a leaked key). Keep the copy we had in deleted/ before taking the new one.
            dst.put(f"{DELETED}{today.isoformat()}/{key}", dst.get(FILES + key), _type(key))
            dst.put(FILES + key, src.get(key), _type(key))
            replaced += 1
    for key in sorted(have.keys() - live.keys()):
        dst.put(f"{DELETED}{today.isoformat()}/{key}", dst.get(FILES + key), _type(key))
        dst.delete(FILES + key)
        moved += 1
    return {"files": len(live), "copied": copied, "replaced": replaced, "moved_to_deleted": moved,
            "dropped_old": prune(dst, DELETED, today, keep_days)}


def put_db(dst, name: str, data: bytes, today: date, keep_days: int) -> dict:
    if not data:
        raise StorageError("empty database backup: refused")
    key = f"{DB}{today.isoformat()}/{os.path.basename(name)}"
    dst.put(key, data, "application/octet-stream")
    return {"stored": key, "bytes": len(data), "dropped_old": prune(dst, DB, today, keep_days)}


def restore_file(src, dst, key: str) -> str:
    """Put one upload back into the app bucket. Takes files/<key>, else the newest deleted/*/<key>."""
    found = [o["key"] for o in dst.list(FILES + key) if o["key"] == FILES + key]
    if not found:
        found = sorted((o["key"] for o in dst.list(DELETED) if o["key"].split("/", 2)[-1] == key), reverse=True)
    if not found:
        raise StorageError(f"no backup copy of {key}")
    src.put(key, dst.get(found[0]), _type(key))
    return found[0]


def main(argv: list[str]) -> int:
    keep = int(os.environ.get("OFFSITE_KEEP_DAYS", "30"))
    today = datetime.now(timezone.utc).date()
    cmd, args = (argv[0] if argv else ""), argv[1:]
    dst = backup_bucket()
    if cmd == "sync-files":
        print(sync_files(R2Storage(), dst, today, keep))
    elif cmd == "put" and len(args) == 1:
        print(put_db(dst, args[0], sys.stdin.buffer.read(), today, keep))
    elif cmd == "list":
        for o in dst.list(args[0] if args else ""):
            print(f"{o['size']:>12}  {o['key']}")
    elif cmd == "get" and len(args) == 1:
        sys.stdout.buffer.write(dst.get(args[0]))
    elif cmd == "restore-file" and len(args) == 1:
        print(f"restored {args[0]} from {restore_file(R2Storage(), dst, args[0])}")
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except StorageError as e:  # a clear one-line reason for the cron mail, no traceback with keys in it
        print(f"backup_r2 failed: {e}", file=sys.stderr)
        sys.exit(1)
