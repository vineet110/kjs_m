# Backend: Python, FastAPI, Postgres

## How a request flows through our API
```
HTTP request → router.py (parse + role check) → service.py (business rule, DB writes, audit row)
→ models.py (SQLAlchemy tables) → Postgres → back up as a schemas.py (Pydantic) response
```
Learn each layer in that order.

| Topic | Learn | Where |
|---|---|---|
| Python typing | `str | None`, `list[int]`, dataclasses, `async/await` basics | docs.python.org → typing |
| FastAPI | path/query/body params, dependencies (`Depends`) for DB session + current user + role, status codes, OpenAPI at `/docs` | fastapi.tiangolo.com → Tutorial (User Guide) |
| Pydantic v2 | models, validation, `model_config`, custom validators | docs.pydantic.dev |
| SQLAlchemy 2 | `DeclarativeBase`, `Mapped[...]`, relationships, `select()`, sessions & transactions, async | docs.sqlalchemy.org → Unified Tutorial |
| Alembic | autogenerate a migration, review it, upgrade/downgrade; **never edit an applied migration** | alembic.sqlalchemy.org → Tutorial |
| PostgreSQL | primary/foreign keys, indexes, unique + **partial unique** indexes, views, transactions, `JSONB`, triggers | postgresql.org/docs → Tutorial; then "Indexes", "CREATE TRIGGER" |
| Auth | Argon2 password hashing, server-side sessions, cookies, CSRF token | OWASP cheat sheets: "Session Management", "Password Storage" |
| pytest | fixtures, parametrize, a test DB, testing allowed + forbidden roles, freezegun for time | docs.pytest.org → Getting started |
| Jobs | APScheduler cron triggers; Postgres queue with `SKIP LOCKED` | see `04-concepts.md` |
| Anthropic SDK | messages, streaming, system prompts, token limits, cost | official Anthropic API docs (Python SDK) |

## First exercises (Phase 1)
1. By hand: a `GET /api/health` that returns `{"status":"ok"}`. Then add a DB ping.
2. A `users` table via an Alembic migration. Read the generated SQL before applying it.
3. A `require_role("admin")` dependency + two tests (admin → 200, employee → 403).
4. A trigger that raises on `UPDATE audit_log`. Prove it with a test.
