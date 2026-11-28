"""Retire every employee (never an admin), so the same emails can sign up fresh. One-off, before go-live:
all employees so far are test accounts.

Run on the server (from deploy/):
    docker compose -f docker-compose.prod.yml exec backend python -m app.reset_staff            # check only
    docker compose -f docker-compose.prod.yml exec backend python -m app.reset_staff --apply    # do it
    ... --keep a@kjsindia.com,b@kjsindia.com    protects these employees too

Why "retire" and not delete: about 30 tables point at a person, the activity log too (every login writes a
line, and that log can't be edited). So the row stays, but:
1. its Firebase login is deleted (first: if that fails, the person is left as is and listed; run it again),
2. its email becomes removed-<id>@invalid (the real email is free for a new sign-up),
3. it is disabled, unlinked from Firebase and logged out,
4. its open leads go back to unassigned and its open batch is returned (as when an admin disables someone).
Already retired rows (…@invalid) are skipped, so running it twice is safe.
"""
import argparse
import asyncio

from sqlalchemy import delete, select

from app.core import firebase
from app.core.database import AsyncSessionLocal
from app.core.errors import AppError
from app.models.user import User, UserSession
from app.services import assign_service, audit_service, lead_service

RETIRED_DOMAIN = "@invalid"


def retired_email(user_id: int) -> str:
    return f"removed-{user_id}{RETIRED_DOMAIN}"


async def run(apply: bool, keep: set[str], out=print) -> dict:
    """Returns {"retire": [emails], "kept": [emails], "failed": [emails]} (also printed)."""
    keep = {e.strip().lower() for e in keep if e.strip()}
    async with AsyncSessionLocal() as db:
        users = (await db.scalars(select(User).order_by(User.id))).all()
        admins = [u for u in users if u.role == "admin"]
        by = next((u for u in admins if u.status == "active"), None)  # signs the lead notes ("back to unassigned")
        kept = [u for u in users if u.role != "admin" and u.email in keep]
        targets = [u for u in users if u.role != "admin" and u.email not in keep
                   and not u.email.endswith(RETIRED_DOMAIN)]
        out(f"Admins (never touched): {len(admins)}")
        for u in admins:
            out(f"  {u.email}  ({u.status})")
        out(f"Employees kept (--keep): {len(kept)}")
        for u in kept:
            out(f"  {u.email}  ({u.status})")
        out(f"Employees to retire: {len(targets)}")
        for u in targets:
            out(f"  #{u.id}  {u.email}  ({u.status})")
        result = {"retire": [u.email for u in targets], "kept": [u.email for u in kept], "failed": []}
        if not apply:
            out("Check only: nothing changed. Add --apply to retire them.")
            return result
        if targets and by is None:
            out("No active admin found: stopped, nothing changed.")
            result["failed"] = result["retire"]
            return result

        done = 0
        for u in targets:
            email = u.email
            try:
                # The Firebase login first: if Google fails, this person stays as they were (run it again)
                uids = {uid for uid in (u.firebase_uid, await firebase.uid_by_email(email)) if uid}
                for uid in uids:
                    if await firebase.tokens_valid_after_ms(uid) is not None:  # None = already gone
                        await firebase.delete_user(uid)
            except AppError as e:
                out(f"  FAILED (Firebase): {email}: {e.message}")
                result["failed"].append(email)
                continue
            user = await db.get(User, u.id, with_for_update=True, populate_existing=True)
            await db.execute(delete(UserSession).where(UserSession.user_id == user.id))  # log them out
            returned = await assign_service.return_open_batch(db, user.id)
            leads_back = await lead_service.return_open_leads(db, by, user)
            before = {"email": email, "status": user.status}
            user.email = retired_email(user.id)
            user.status = "disabled"
            user.firebase_uid = None
            user.firebase_valid_after = user.firebase_checked_at = None
            audit_service.record(db, actor=None, action="user.retired", entity_type="user", entity_id=user.id,
                                 before=before, after={"email": user.email, "status": "disabled"}
                                 | ({"buyers_returned": returned} if returned else {})
                                 | ({"leads_unassigned": leads_back} if leads_back else {}))
            await db.commit()  # one person at a time: a stop halfway leaves no one half-done
            done += 1
        out(f"Retired {done} of {len(targets)}. Failed: {len(result['failed'])}.")
        return result


def main() -> None:
    p = argparse.ArgumentParser(description="Retire every employee (not admins) so they can sign up again.")
    p.add_argument("--apply", action="store_true", help="really do it (without it: only lists who)")
    p.add_argument("--keep", default="", help="comma-separated employee emails to leave untouched")
    a = p.parse_args()
    asyncio.run(run(a.apply, set(a.keep.split(","))))


if __name__ == "__main__":
    main()
