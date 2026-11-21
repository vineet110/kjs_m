# Debugging by hand

How to find where an error comes from without Claude Code. A free GPT with limited tokens is fine as a helper.
Words like traceback, status code and request ID are explained in `kb.md`.


1. Find which side failed

   i.   Browser: press F12.
        a. Console tab: red frontend (JavaScript) errors, with the file and line number.
        b. Network tab: click the failed (red) request, then read its status code and Response body.
   ii.  4xx (400, 401, 403, 404, 422): the request was wrong, a permission was missing or the URL was wrong.
        The response body usually says which.
   iii. 5xx (500 and up): the backend crashed. Go to the backend terminal.


2. Backend error (Python traceback)

   i.   Look in the terminal running uvicorn (`.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000`).
        The full traceback is printed there.
   ii.  Read it from the bottom up. The last line is the error type and message, for example `KeyError: 'user_id'`.
   iii. Move up to the first line that points into `backend/app/...`. That is our code. Lines from
        `site-packages` are library code, so skip them.


3. Frontend error

   i.   Check the terminal running `npm run dev`. Errors from server-side code show up there.
   ii.  Check the error overlay in the browser.
   iii. In the stack trace, look for the first file under `frontend/src/...`.


4. Find it in the code (VS Code)

   i.   `Ctrl+Shift+F`: search for the exact error text, or for the API URL from the Network tab.
   ii.  `Ctrl+click` a function name to jump to where it is defined.
   iii. If it "worked yesterday", run `git diff` and `git log -5` to see what changed.
   iv.  Check the matching `config/*.ini` and `.env`. A wrong setting often looks like a code bug.


5. Narrow it down

   i.   Reproduce it with the smallest possible step. Run one test:
        `.venv/Scripts/python.exe -m pytest -q -k test_name` (from `backend/`).
   ii.  Add a `print()` or `logging` line before the failing line to see the real values.
   iii. Or set a breakpoint with the VS Code debugger (F5) and step through.


6. Errors on the live server (VPS)

   i.   Backend logs: `docker compose -f docker-compose.prod.yml logs -f --tail 100 backend`
   ii.  One request only: `docker compose -f docker-compose.prod.yml logs backend | grep <request_id>`
   iii. Change `backend` to `frontend`, `nginx` or `db` for the other containers.
        `docker compose -f docker-compose.prod.yml ps` shows which ones are down.
   iv.  Read `deploy/README.md` first ("Look at logs" and the common problems at the end).


7. Database errors

   i.   Messages that mention `sqlalchemy`, `psycopg` or `alembic` usually mean a missing migration or a column
        that doesn't match. Run `alembic current` to check.
   ii.  Before running `alembic` by hand, override BOTH database URLs in `.env`. If you don't, it migrates Neon
        instead of the local database.


8. Errors that are not code bugs

   i.   403 or a feature is missing: the module switch may be off in `config/<feature>.ini`, or the user lacks
        the permission.
   ii.  CORS error in the browser console: rare for us, because the frontend calls `/api/...` and Next.js passes
        it to the backend (same address). If you see one, some code is calling the backend's address directly
        instead of `/api/...`.
   iii. Login or Firebase errors: usually an expired token or a wrong key in `.env`.


9. Build, type and test errors

   i.   `npm run build` or `tsc` errors give the file and line directly. Fix the first one, because the rest
        often go away with it.
   ii.  Tests: add `-x -vv` to pytest to stop at the first failure and see full details. Read the `assert`
        line (it shows expected vs actual).


10. Setup problems

   i.   `ModuleNotFoundError`: Python was started without `.venv`, or `pip install` hasn't been run.
   ii.  `Cannot find module`: `npm install` hasn't been run.
   iii. If nothing makes sense: restart the servers, delete `frontend/.next`, then hard-refresh with
        `Ctrl+Shift+R`.


11. No error, but the result is wrong (the hardest kind)

   i.   There is no traceback, so make your own clues. Log the input and output at each step (frontend, then API,
        then database) and find the first step where the value goes wrong.


12. Using a free GPT (limited tokens)

   i.   Send only:
        a. the last 15-20 lines of the traceback
        b. the one function involved, not the whole file
        c. what you did, what you expected and what happened
   ii.  Ask "what does this error mean and where should I look?", not "fix it". You learn more and use fewer
        tokens.
   iii. Never paste secrets: `.env` values, database URLs, tokens or passwords.
   iv.  Before using AI, search Google for the exact error message in quotes. Stack Overflow and GitHub issues
        usually have the answer.


13. Afterwards

   i.   Write the error and its fix in your temp file (`tempV.md` or `tempS.md`). The same errors come back.
