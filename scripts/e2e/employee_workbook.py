"""Employee module end-to-end test cases + stress test: builds docs/testing/employee-e2e.xlsx.

Build (cases only):            python scripts/e2e/employee_workbook.py
Fill in a run:                 python scripts/e2e/employee_workbook.py --results e2e-output/results.json
                                   --stress e2e-output/stress/stress.json
Same layout as the admin workbook (scripts/e2e/admin_workbook.py), plus a "Stress test" sheet.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from openpyxl.styles import Alignment, PatternFill

sys.path.insert(0, str(Path(__file__).parent))
import admin_workbook as wbk  # noqa: E402

ROOT = wbk.ROOT
OUT = ROOT / "docs" / "testing" / "employee-e2e.xlsx"
V, C, S, P = "View", "Change", "Security", "Load"

CASES = [
    # ---- Login and access ----
    ("EMP-001", "Login & access", "Employee logs in", "Log in as tester V on /employee/login.",
     "Today (/employee/dashboard) opens; sidebar says 'Employee portal'.", V),
    ("EMP-002", "Login & access", "Logged-out visitor can't open staff pages", "Without logging in, open /employee/dashboard.",
     "Sent to /employee/login with ?next=/employee/dashboard.", S),
    ("EMP-003", "Login & access", "Sidebar matches the permissions", "Open every sidebar group.",
     "Exactly the pages V's permissions and the switched-on areas allow.", S),
    ("EMP-004", "Login & access", "Admin API refused", "As V (no staff.approve), call GET /api/v1/admin/users.", "403 refused.", S),
    ("EMP-005", "Login & access", "Admin page shows no staff data", "As V, open /admin/users.",
     "No staff list is shown (the server refuses the data).", S),
    ("EMP-006", "Login & access", "Logout ends the session", "Fresh login as V, Log out, confirm.",
     "'You've logged out safely'; /api/v1/auth/me answers 401.", S),
    # ---- Today ----
    ("EMP-010", "Today", "Today loads", "Open /employee/dashboard.", "Greeting, today's card and 'My leads' show.", V),
    ("EMP-011", "Today", "Task counts match the server", "Compare the page with GET /api/v1/tasks/stats.", "Same numbers.", V),
    # ---- Attendance ----
    ("EMP-020", "My attendance", "Attendance page loads", "Open /employee/attendance.", "Punch button with live clock and the views show.", V),
    ("EMP-021", "My attendance", "Check in", "Click Check-in.", "Button turns to Check-out; today's record has a check-in time.", C),
    ("EMP-022", "My attendance", "Check out with a note", "Type 'E2E check-out', click Check-out.",
     "Button turns to 'Check-in again'; today's record has a check-out time.", C),
    ("EMP-023", "My attendance", "Switch views", "Open List, Tabular, Calendar and Overtime views.", "Each view shows without errors.", V),
    ("EMP-024", "My attendance", "Apply for leave", "Leave Applications: Casual, two days next month, reason 'E2E test leave'.",
     "Listed under My Leave Applications as pending. (Kept.)", C),
    ("EMP-025", "My attendance", "Leave ending before it starts is refused", "Apply with end date before start date.",
     "Refused with a message; nothing new listed.", C),
    ("EMP-026", "My attendance", "Missed-punch request", "Regularization: yesterday 09:30 to 18:30, reason 'E2E missed punch'.",
     "Listed as pending. (Kept.)", C),
    ("EMP-027", "My attendance", "Reports and shifts", "Open Reports and Shift Schedule.", "Month numbers and company shifts show.", V),
    ("EMP-028", "My attendance", "Requests reach the admin", "As admin, read GET /api/v1/admin/approvals.",
     "V's E2E leave and missed-punch requests are waiting there.", S),
    # ---- Leads ----
    ("EMP-040", "Leads", "Leads list loads", "Open /employee/contacts.", "Table with 'Showing â€¦ Contacts' (or an empty message).", V),
    ("EMP-041", "Leads", "Search leads", "Search for a name from the list, then for nonsense.", "Matching rows; then 'Nothing matches your search'.", V),
    ("EMP-042", "Internal leads", "Add an internal lead", "+ Add lead: 'E2E Lead <time>', E2E Co, phone, India, coffee, 1 tonne a month.",
     "Saved; listed in Internal leads. (Kept; SLA timers apply.)", C),
    ("EMP-043", "Internal leads", "Lead without phone refused", "Save a lead with a name but no phone.", "Refused; nothing saved.", C),
    ("EMP-044", "Leads", "New lead shows in Leads", "Search Leads for the E2E lead.", "It is listed.", V),
    ("EMP-045", "Leads", "Open the lead", "Open the E2E lead.", "Lead Pipeline and Quick actions show.", V),
    ("EMP-046", "Leads", "Add a note", "Add note 'E2E note: called, wants samples'.", "The note shows on the lead.", C),
    ("EMP-047", "Leads", "Add a task from the lead", "Quick actions: add task 'E2E follow-up'.", "The task shows in Tasks & Track.", C),
    ("EMP-048", "Koko chat leads", "Koko leads page loads", "Open /employee/koko-leads.", "List or empty message.", V),
    # ---- Tasks ----
    ("EMP-050", "Tasks & Track", "Tasks page loads", "Open /employee/tasks.", "Add-task form, filters and list show.", V),
    ("EMP-051", "Tasks & Track", "Add a task for me", "Add 'E2E Task <time>' for Me.", "Listed as To do.", C),
    ("EMP-052", "Tasks & Track", "Start the task", "Details, Start.", "Status Doing.", C),
    ("EMP-053", "Tasks & Track", "Save an outcome", "Outcome 'E2E outcome', Save.", "Outcome stored.", C),
    ("EMP-054", "Tasks & Track", "Finish the task", "Tick Done; filter 'Done'.", "Status Done; listed under Done.", C),
    ("EMP-055", "Tasks & Track", "Give a task to a colleague", "Add 'E2E delegated task' for a test employee.",
     "Saved with that person as owner.", C),
    ("EMP-056", "Tasks & Track", "Task without a title refused", "Click Add task with an empty title.", "Not saved.", C),
    # ---- Batches, boards ----
    ("EMP-060", "My batches", "Batches page loads", "Open /employee/batches.", "Today's batch or an empty message.", V),
    ("EMP-065", "My order boards", "Boards page loads", "Open /employee/order-boards.", "V's boards or an empty message.", V),
    # ---- Chat ----
    ("EMP-070", "Chat", "Chat page loads", "Open /employee/chat.", "Chat list shows.", V),
    ("EMP-071", "Chat", "Start a group chat", "+ Group chat 'E2E Group' with 2 test employees.", "The group opens. (Kept.)", C),
    ("EMP-072", "Chat", "Send a message", "Send 'E2E hello <time>'.", "The message shows.", C),
    ("EMP-073", "Chat", "Edit own message", "Edit it to 'â€¦ (edited by test)'.", "New text shows, marked edited.", C),
    ("EMP-074", "Chat", "Delete own message", "Send another, delete it.", "Shows as 'message deleted'.", C),
    ("EMP-075", "Chat", "Live connection", "Open chat and watch the live connection.",
     "Connects. (Known bug: 404 on Vercel, expected to fail until fixed.)", V),
    # ---- Profile ----
    ("EMP-080", "Profile", "Profile loads", "Open /employee/me.", "Name, phone and notification settings show.", V),
    ("EMP-081", "Profile", "Save a setting", "Toggle 'WhatsApp messages', Save.", "'Saved.'; stays after reload. (Kept.)", C),
    ("EMP-082", "Profile", "Wrong current password refused", "Change password with a wrong current password.", "Refused; password unchanged.", S),
    ("EMP-083", "Profile", "New passwords must match", "Two different new passwords.", "Refused; nothing sent.", S),
    ("EMP-084", "Profile", "Short new password refused", "New password of 5 characters.", "Not sent (10+ characters).", S),
    # ---- Whole module ----
    ("EMP-090", "All employee pages", "No errors on any page", "Open every sidebar page.",
     "No error screen, crash, console error, 403 or 5xx (chat live connection excluded: EMP-075).", V),
    ("EMP-091", "All employee pages", "Phone layout", "At 390 px, open the menu and Today.", "Menu opens; no sideways scroll.", V),
    # ---- Stress (filled from the stress run, not Playwright) ----
    ("STR-001", "Stress test", "10 users at once", "75 test employees created; 10 log in and browse for 2 min.", "p95 under 2 s, errors under 1%.", P),
    ("STR-002", "Stress test", "25 users at once", "25 users browse for 2 min.", "p95 under 2 s, errors under 1%.", P),
    ("STR-003", "Stress test", "50 users at once", "50 users browse for 2 min.", "p95 under 2 s, errors under 1%.", P),
    ("STR-004", "Stress test", "Logins under load", "All logins during the run.", "No failed login; p95 under 3 s.", P),
]


def stress_results(path: Path) -> dict[str, dict]:
    r = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for i, s in enumerate(r["stages"], start=1):
        ok = s["pass"]
        out[f"STR-00{i}"] = {"status": "Pass" if ok else "Fail", "evidence": "Stress test sheet",
                             "actual": f"{s['users']} users, {s['requests']} calls ({s['rps']}/s): p50 {s['p50']} ms, p95 {s['p95']} ms, "
                                       f"max {s['max']} ms, errors {s['errors']} ({s['error_rate']:.1%})."}
    for i in range(len(r["stages"]) + 1, 4):
        out[f"STR-00{i}"] = {"status": "Blocked", "evidence": "", "actual": r.get("stop_reason") or "Step not reached."}
    logins = [s["logins"] for s in r["stages"] if s["logins"]["requests"]]
    n = sum(x["requests"] for x in logins); err = sum(x["errors"] for x in logins); p95 = max((x["p95"] for x in logins), default=0)
    out["STR-004"] = {"status": "Pass" if err == 0 and p95 < 3000 else "Fail", "evidence": "Stress test sheet",
                      "actual": f"{n} logins, {err} failed, slowest step p95 {p95} ms."}
    return out


def stress_sheet(path: Path | None):
    def add(wb):
        ws = wb.create_sheet("Stress test")
        ws.column_dimensions["A"].width = 34
        for col in "BCDEFGHI":
            ws.column_dimensions[col].width = 13
        ws["A1"] = "Stress test: test employees browsing the live site"
        ws["A1"].font = wbk.TITLE
        if not path:
            ws["A3"] = "Not run yet."
            return
        r = json.loads(path.read_text(encoding="utf-8"))
        rows = [("Site", r["site"]), ("Started (UTC)", r["started"]), ("Finished (UTC)", r["finished"]),
                ("Pass rule", r["pass_rule"]), ("Stopped early", f"Yes: {r['stop_reason']}" if r["stopped_early"] else "No"),
                ("What each user does", "Logs in once, then opens a random employee page every 2-4 s (all of the page's API calls together). Read-only.")]
        for i, (k, v) in enumerate(rows, start=3):
            ws.cell(row=i, column=1, value=k).font = wbk.BOLD
            ws.cell(row=i, column=2, value=v).font = wbk.BASE

        def table(top, title, headers, data):
            ws.cell(row=top, column=1, value=title).font = wbk.BOLD
            for c, h in enumerate(headers, start=1):
                cell = ws.cell(row=top + 1, column=c, value=h)
                cell.font, cell.fill = wbk.HEAD_FONT, wbk.HEAD_FILL
            for i, row in enumerate(data, start=top + 2):
                for c, v in enumerate(row, start=1):
                    cell = ws.cell(row=i, column=c, value=v)
                    cell.font, cell.alignment = wbk.BASE, Alignment(vertical="top")
                    if c == len(headers) and v in ("Pass", "Fail"):
                        cell.fill = PatternFill("solid", fgColor=wbk.STATUS_COLOURS[v])
            return top + len(data) + 3

        top = table(10, "By step", ["Step", "Users", "Seconds", "API calls", "Calls / s", "p50 ms", "p95 ms", "Max ms", "Errors", "Error %", "Result"],
                    [(s["stage"], s["users"], s["seconds"], s["requests"], s["rps"], s["p50"], s["p95"], s["max"], s["errors"],
                      round(s["error_rate"] * 100, 2), "Pass" if s["pass"] else "Fail") for s in r["stages"]])
        top = table(top, "Logins", ["Step", "Logins", "p50 ms", "p95 ms", "Max ms", "Failed"],
                    [(s["stage"], s["logins"]["requests"], s["logins"]["p50"], s["logins"]["p95"], s["logins"]["max"], s["logins"]["errors"]) for s in r["stages"]])
        top = table(top, "Pages (all API calls of the page together)", ["Page", "Opened", "p50 ms", "p95 ms", "Max ms", "With errors"],
                    [(p["name"], p["requests"], p["p50"], p["p95"], p["max"], p["errors"]) for p in r["pages"]])
        top = table(top, "API calls, slowest first", ["Call", "Count", "p50 ms", "p95 ms", "Max ms", "Errors"],
                    [(e["name"], e["requests"], e["p50"], e["p95"], e["max"], e["errors"]) for e in r["endpoints"]])
        table(top, "Errors", ["Call and answer", "Count"], [(e["what"], e["count"]) for e in r["error_kinds"]] or [("None", 0)])
    return add


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, help="Playwright JSON report")
    ap.add_argument("--stress", type=Path, help="stress.json from scripts/e2e/stress.mjs")
    a = ap.parse_args()
    res = wbk.load_results(a.results, prefix="EMP-") if a.results else None
    if a.stress:
        res = {**(res or {}), **stress_results(a.stress)}
    path = wbk.build(res, datetime.now().strftime("%d %b %Y %H:%M"), cases_list=CASES, out=OUT,
                     title="Employee module: end-to-end and stress test summary",
                     account="Tester V (employee) for the module; 75 E2E test employees for the stress test",
                     scope="Create and keep E2E data (decided by Vineet 12 Nov); check-in/out included; nothing deleted on purpose.",
                     extra=stress_sheet(a.stress))
    print(f"{path.relative_to(ROOT)}: {len(CASES)} cases" + (f", {len(res)} with results" if res else ""))
