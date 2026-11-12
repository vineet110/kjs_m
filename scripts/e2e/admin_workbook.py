"""Admin module end-to-end test cases: builds docs/testing/admin-e2e.xlsx.

Build (cases only, every status "Not run"):
    python scripts/e2e/admin_workbook.py
Fill in a run (Playwright JSON report; test titles start with the case ID, e.g. "ADM-062 ..."):
    python scripts/e2e/admin_workbook.py --results frontend/test-results/admin-results.json

The Summary sheet counts with Excel formulas, so editing a Status by hand updates it.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "testing" / "admin-e2e.xlsx"
SITE = "https://kjs-m.vercel.app"
ACCOUNT = "Admin test account (from frontend/.env.e2e.local)"
STATUSES = ["Not run", "Pass", "Fail", "Blocked", "Skipped"]

V, C, S = "View", "Change", "Security"

# (id, page, test case, steps, expected result, type)
CASES = [
    # ---- Login and access ----
    ("ADM-001", "Login & access", "Admin logs in", "Open /employee/login, enter the admin email and password, click Log in.",
     "Admin overview (/admin/dashboard) opens; sidebar says 'Admin console'.", V),
    ("ADM-002", "Login & access", "Wrong password is refused", "Log in with the admin email and a wrong password.",
     "An error message shows; still on the login page; no session.", S),
    ("ADM-003", "Login & access", "Logged-out visitor can't open admin pages", "Without logging in, open /admin/dashboard.",
     "Sent to /employee/login with ?next=/admin/dashboard.", S),
    ("ADM-004", "Login & access", "Employee without staff.approve is refused by the admin API",
     "Log in as tester V (no staff.approve), call GET /api/v1/admin/users.", "403 refused.", S),
    ("ADM-005", "Login & access", "Admin sidebar shows every admin group",
     "Log in as admin, open the sidebar, open each group.",
     "Groups: My work, Lead Management, Dashboard, Employees, Order Boards & Assigning, Global Site, Reports & settings.", V),
    ("ADM-006", "Login & access", "Logout ends the session", "Log in as admin (fresh session), Log out, confirm.",
     "Login page says 'You've logged out safely'; /api/v1/auth/me answers 401.", S),
    # ---- Admin overview ----
    ("ADM-010", "Admin overview", "Stat tiles show", "Open /admin/dashboard.",
     "Tiles: Active staff, All leads, Leads this week, New leads, Products, Waiting for approval.", V),
    ("ADM-011", "Admin overview", "Tile numbers match the server", "Compare the tiles with GET /api/v1/admin/stats.",
     "Every tile shows the server's number.", V),
    ("ADM-012", "Admin overview", "Waiting sign-ups list or empty message", "Open /admin/dashboard, look at the approvals part.",
     "Pending sign-ups are listed, or an empty message shows.", V),
    # ---- All Enquiries ----
    ("ADM-020", "All Enquiries", "Enquiries list loads", "Open /admin/leads.", "A table of enquiries with owner and SLA shows (or an empty message).", V),
    ("ADM-021", "All Enquiries", "SLA times shown match settings", "Compare the page's SLA note with GET /api/v1/admin/sla.",
     "Respond / resolve minutes match the server.", V),
    ("ADM-022", "All Enquiries", "SLA filter narrows the list", "Choose 'Overdue' in the SLA filter.",
     "The list reloads with only overdue enquiries (never more than all).", V),
    # ---- Approvals ----
    ("ADM-030", "Approvals", "Approvals inbox loads", "Open /admin/approvals.",
     "Sign-ups, attendance fixes and file deletions show (or empty messages). Nothing is approved by the test.", V),
    ("ADM-031", "Approvals", "Sidebar badge matches the inbox", "Compare the 'All approvals' badge with GET /api/v1/admin/approvals.",
     "Badge = sign-ups + attendance fixes + file deletions (no badge when 0).", V),
    # ---- Manage employees ----
    ("ADM-040", "Manage employees", "Staff list loads", "Open /admin/users.", "Rows with name, email, role and status.", V),
    ("ADM-041", "Manage employees", "Search in the staff list", "Type part of an email into the table search.", "Only matching rows stay.", V),
    ("ADM-042", "Manage employees", "New employee form checks required fields", "Open /admin/users/new, submit empty.",
     "The form is not sent; required fields are marked.", V),
    ("ADM-043", "Manage employees", "Create test employee", "Create 'E2E Test User', e2e.user@kjs-e2e.test, phone, code E2E-001, Main Branch, role Employee (reused if it exists).",
     "'E2E Test User can log in now' with a one-time password; shows in the staff list.", C),
    ("ADM-044", "Manage employees", "Duplicate email refused", "Create another employee with e2e.user@kjs-e2e.test.",
     "Refused with a clear message; no second user.", C),
    ("ADM-045", "Manage employees", "Edit the test employee", "Open the E2E user, change Branch, Submit.",
     "'Saved.'; the new branch is stored. (The form has no permission boxes; permissions are set when approving.)", C),
    ("ADM-046", "Manage employees", "Disable the test employee", "On Admin overview, click Disable on the E2E user's row.",
     "Status shows disabled in the list. (Left disabled as clean-up.)", C),
    # ---- Team attendance ----
    ("ADM-050", "Attendance", "Team attendance for today", "Open /admin/team-attendance.", "Staff list for today with check-in status.", V),
    ("ADM-051", "Attendance", "Another day", "Pick yesterday.", "The list reloads for that day.", V),
    ("ADM-052", "Attendance", "Approval lists show", "Look at the attendance-fix and leave approval parts.", "Lists or empty messages; nothing approved.", V),
    ("ADM-053", "Attendance", "Export to Excel", "Click 'Export to Excel', then 'Download .xlsx Report'.", "An .xlsx file downloads.", V),
    # ---- Holidays ----
    ("ADM-060", "Holidays", "Holiday list for this year", "Open /admin/holidays.", "This year's holidays are listed.", V),
    ("ADM-061", "Holidays", "Switch year", "Choose next year.", "That year's list shows.", V),
    ("ADM-062", "Holidays", "Add a test holiday", "Add 'E2E Holiday' on 30 Dec next year (far away: no effect on SLA now).",
     "Saved; shows in that year's list.", C),
    ("ADM-063", "Holidays", "Holiday without a name is refused", "Click Add holiday with an empty name.", "Not saved.", C),
    ("ADM-064", "Holidays", "Delete the test holiday", "Delete 'E2E Holiday'.", "Gone from the list.", C),
    # ---- Order boards ----
    ("ADM-070", "Order boards", "Boards list loads", "Open /admin/order-boards; tick 'Show finished'.", "Running boards show; finished ones appear when ticked.", V),
    ("ADM-071", "Order boards", "Create a test board", "New board 'E2E Board (test)', code E2E-<number>, client E2E Client, 30 days; only the admin on each of the 3 steps.",
     "Saved with a board code; shows in the list.", C),
    ("ADM-072", "Order boards", "Open the board", "Open the E2E board.", "Plan, steps, people and history show.", V),
    ("ADM-073", "Order boards", "Mark a step done", "Mark the first step done.", "Step shows done; history has an entry.", C),
    ("ADM-074", "Order boards", "Finish the test board", "Close the E2E board as 'Cancelled'.",
     "It leaves the running list and shows under 'Show finished'. (Clean-up: boards can't be deleted.)", C),
    # ---- Auto-assign ----
    ("ADM-080", "Auto-assign", "Overview loads", "Open /admin/auto-assign.", "Staff, categories and waiting records show.", V),
    ("ADM-081", "Auto-assign", "Preview without running", "Click Preview.", "A proposed split shows; nothing is assigned (Run is not clicked).", V),
    # ---- Client Schedulers ----
    ("ADM-090", "Client Schedulers", "Page loads", "Open /admin/client-schedulers.", "Sources, recent runs and stats show.", V),
    ("ADM-091", "Client Schedulers", "Add a test source", "Add 'E2E Source', type RSS, https://example.com/e2e-feed.xml, 'active' unticked (never runs).", "Saved; in the list.", C),
    ("ADM-092", "Client Schedulers", "Unsafe address refused", "Add a source with http://localhost.", "Refused with a message.", S),
    ("ADM-093", "Client Schedulers", "Delete the test source", "Delete 'E2E Source'.", "Gone from the list.", C),
    # ---- Products ----
    ("ADM-100", "Products", "Product list loads", "Open /admin/products.", "Products with category and website status.", V),
    ("ADM-101", "Products", "Create a hidden test product", "Add 'E2E Product' (reused if it exists), then click Hide at once (a new product is live straight away).",
     "Saved; in the admin list marked hidden.", C),
    ("ADM-102", "Products", "Edit the test product", "Change its short description, save.", "The new text stays after reload.", C),
    ("ADM-103", "Products", "Hidden product is not public", "Open the public /products page.",
     "'E2E Product' is not listed. (Clean-up: stays hidden; products can't be deleted.)", S),
    # ---- SEO & Partners ----
    ("ADM-110", "SEO & Partners", "Page loads", "Open /admin/website.", "Site texts, offers and partners show.", V),
    ("ADM-111", "SEO & Partners", "Add a test offer", "Product offers tab: add 'E2E Offer', then Switch off at once.", "Saved; in the offers list, switched off.", C),
    ("ADM-112", "SEO & Partners", "Delete the test offer", "Delete 'E2E Offer'.", "Gone from the list (and from the public site).", C),
    ("ADM-113", "SEO & Partners", "Partner list shows", "Look at the partners part.", "Partners with status; nothing changed.", V),
    # ---- Manage KOKO ----
    ("ADM-120", "Manage KOKO", "Page loads", "Open /admin/koko.", "Koko facts text and recent chats show. Facts are not saved.", V),
    # ---- Reports, Alerts, Activity log, Settings ----
    ("ADM-130", "Reports", "Reports load", "Open /admin/analytics.", "Numbers and charts show.", V),
    ("ADM-140", "Alerts", "Alerts load", "Open /admin/alerts.", "Alerts list or an empty message.", V),
    ("ADM-150", "Activity log", "Log loads", "Open /admin/audit.", "Up to 200 latest actions.", V),
    ("ADM-151", "Activity log", "Test actions are logged", "After ADM-062/064, look for the E2E holiday in the log.",
     "The add and delete are listed with the admin's name.", S),
    ("ADM-160", "Settings", "Settings list loads", "Open /admin/settings.", "Settings with their value and where it comes from.", V),
    ("ADM-161", "Settings", "Search settings", "Type 'sla'.", "Only SLA settings stay.", V),
    ("ADM-162", "Settings", "Re-read files", "Click 'Re-read files now'.", "A success message; values unchanged. Nothing is saved.", V),
    # ---- Whole module ----
    ("ADM-170", "All admin pages", "No errors on any admin page", "Open every admin page in the sidebar.",
     "No error screen, no console error, no 403 or 5xx from the API.", V),
    ("ADM-171", "All admin pages", "Phone layout", "At phone width (390 px), open the menu with ☰ and visit Admin overview.",
     "Menu opens over the page; the page is usable.", V),
    ("ADM-172", "All admin pages", "Clean-up check", "After the run, search for 'E2E' in holidays, offers and sources.",
     "None left. Known leftovers: hidden E2E Product, finished E2E Board, disabled E2E user.", C),
]

HEAD_FILL = PatternFill("solid", fgColor="1F2937")
HEAD_FONT = Font(name="Arial", bold=True, color="FFFFFF")
BASE = Font(name="Arial", size=10)
BOLD = Font(name="Arial", size=10, bold=True)
TITLE = Font(name="Arial", size=14, bold=True)
THIN = Border(*(Side(style="thin", color="D1D5DB"),) * 4)
WRAP = Alignment(wrap_text=True, vertical="top")
STATUS_COLOURS = {"Pass": "D1FAE5", "Fail": "FEE2E2", "Blocked": "FEF3C7", "Skipped": "E5E7EB"}


def load_results(path: Path) -> dict[str, dict]:
    """Case ID -> {status, actual, evidence} from a Playwright JSON report."""
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}

    def walk(suite):
        for spec in suite.get("specs", []):
            cid = spec["title"].split(" ")[0]
            if not cid.startswith("ADM-"):
                continue
            for test in spec.get("tests", []):
                res = test["results"][-1] if test.get("results") else {}
                st = res.get("status", "skipped")
                notes = [a.get("description", "") for a in test.get("annotations", []) if a.get("type") in ("skip", "blocked", "note")]
                if st == "passed":
                    status, actual = "Pass", "; ".join(n for n in notes if n) or "As expected."
                elif st == "skipped":
                    blocked = any(a.get("type") == "blocked" for a in test.get("annotations", []))
                    status, actual = ("Blocked" if blocked else "Skipped"), "; ".join(n for n in notes if n) or "Skipped."
                else:
                    errs = [e.get("message", "") for e in res.get("errors", [])]
                    first = next((e for e in errs if e), "Failed")
                    status = "Fail"
                    actual = " ".join(first.replace("\x1b", "").split())[:400]
                shots = [a.get("path", "") for a in res.get("attachments", []) if a.get("name") == "screenshot" and a.get("path")]
                evidence = str(Path(shots[0]).relative_to(ROOT)) if shots and Path(shots[0]).is_relative_to(ROOT) else ""
                out[cid] = {"status": status, "actual": actual, "evidence": evidence}
        for s in suite.get("suites", []):
            walk(s)

    for s in data.get("suites", []):
        walk(s)
    return out


def build(results: dict[str, dict] | None, run_date: str):
    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"
    cases = wb.create_sheet("Test cases")

    # ---------- Test cases ----------
    headers = ["ID", "Page", "Test case", "Steps", "Expected result", "Type", "Status", "Actual result", "Evidence", "Run date"]
    widths = [10, 18, 34, 48, 48, 10, 11, 48, 30, 12]
    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        c = cases.cell(row=1, column=i, value=h)
        c.font, c.fill, c.alignment, c.border = HEAD_FONT, HEAD_FILL, Alignment(vertical="center"), THIN
        cases.column_dimensions[get_column_letter(i)].width = w
    for r, (cid, page, title, steps, expected, kind) in enumerate(CASES, start=2):
        res = (results or {}).get(cid)
        status = res["status"] if res else ("Skipped" if results is not None else "Not run")
        actual = res["actual"] if res else ("No test ran for this case." if results is not None else "")
        row = [cid, page, title, steps, expected, kind, status, actual, res["evidence"] if res else "", run_date if results is not None else ""]
        for col, v in enumerate(row, start=1):
            c = cases.cell(row=r, column=col, value=v)
            c.font, c.alignment, c.border = BASE, WRAP, THIN
    last = len(CASES) + 1
    cases.freeze_panes = "C2"
    cases.auto_filter.ref = f"A1:J{last}"
    dv = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"', allow_blank=False)
    cases.add_data_validation(dv)
    dv.add(f"G2:G{last}")
    for status, colour in STATUS_COLOURS.items():
        cases.conditional_formatting.add(
            f"G2:G{last}", FormulaRule(formula=[f'$G2="{status}"'], fill=PatternFill("solid", fgColor=colour))
        )

    # ---------- Summary ----------
    rng = lambda col: f"'Test cases'!${col}$2:${col}${last}"  # noqa: E731
    summary.column_dimensions["A"].width = 26
    for col in "BCDEFG":
        summary.column_dimensions[col].width = 12
    summary.column_dimensions["H"].width = 60
    summary["A1"] = "Admin module: end-to-end test summary"
    summary["A1"].font = TITLE
    info = [
        ("Site", SITE),
        ("Account", ACCOUNT),
        ("Run date", run_date if results is not None else "Not run yet"),
        ("Scope", "Option (b): view everything; create and delete only E2E test data; shared settings are never saved."),
        ("How to edit", "Change a Status in 'Test cases' (column G, drop-down). This page updates itself."),
    ]
    for i, (k, v) in enumerate(info, start=3):
        summary.cell(row=i, column=1, value=k).font = BOLD
        summary.cell(row=i, column=2, value=v).font = BASE

    # Totals by status
    r0 = 9
    summary.cell(row=r0, column=1, value="Result").font = HEAD_FONT
    summary.cell(row=r0, column=2, value="Cases").font = HEAD_FONT
    for col in (1, 2):
        summary.cell(row=r0, column=col).fill = HEAD_FILL
    for i, st in enumerate(STATUSES, start=1):
        summary.cell(row=r0 + i, column=1, value=st).font = BASE
        summary.cell(row=r0 + i, column=2, value=f'=COUNTIF({rng("G")},A{r0 + i})').font = BASE
    tot = r0 + len(STATUSES) + 1
    summary.cell(row=tot, column=1, value="Total").font = BOLD
    summary.cell(row=tot, column=2, value=f"=SUM(B{r0 + 1}:B{tot - 1})").font = BOLD
    summary.cell(row=tot + 1, column=1, value="Pass rate (of cases run)").font = BOLD
    # run = pass + fail + blocked (rows r0+2 .. r0+4)
    c = summary.cell(row=tot + 1, column=2, value=f"=IF(SUM(B{r0 + 2}:B{r0 + 4})=0,0,B{r0 + 2}/SUM(B{r0 + 2}:B{r0 + 4}))")
    c.font, c.number_format = BOLD, "0.0%"

    # Per page
    p0 = tot + 4
    for col, h in enumerate(["Page", "Cases", "Pass", "Fail", "Blocked", "Skipped", "Not run"], start=1):
        c = summary.cell(row=p0, column=col, value=h)
        c.font, c.fill = HEAD_FONT, HEAD_FILL
    pages = list(dict.fromkeys(p for _, p, *_ in CASES))
    for i, page in enumerate(pages, start=1):
        r = p0 + i
        summary.cell(row=r, column=1, value=page).font = BASE
        summary.cell(row=r, column=2, value=f'=COUNTIF({rng("B")},A{r})').font = BASE
        for col, st in zip("CDEFG", ["Pass", "Fail", "Blocked", "Skipped", "Not run"]):
            summary[f"{col}{r}"] = f'=COUNTIFS({rng("B")},$A{r},{rng("G")},"{st}")'
            summary[f"{col}{r}"].font = BASE
    for status, colour in {"Fail": "FEE2E2", "Blocked": "FEF3C7"}.items():
        col = "D" if status == "Fail" else "E"
        summary.conditional_formatting.add(
            f"{col}{p0 + 1}:{col}{p0 + len(pages)}",
            FormulaRule(formula=[f"{col}{p0 + 1}>0"], fill=PatternFill("solid", fgColor=colour)),
        )

    # Every case in one line, so the summary lists each test (status follows the case sheet)
    l0 = p0 + len(pages) + 3
    summary.cell(row=l0 - 1, column=1, value="Every test case").font = BOLD
    for col, h in enumerate(["ID", "Page", "Status", "", "", "", "", "Test case / actual result"], start=1):
        c = summary.cell(row=l0, column=col, value=h or None)
        c.font, c.fill = HEAD_FONT, HEAD_FILL
    for i in range(len(CASES)):
        r, src = l0 + 1 + i, i + 2
        summary[f"A{r}"] = f"='Test cases'!A{src}"
        summary[f"B{r}"] = f"='Test cases'!B{src}"
        summary[f"C{r}"] = f"='Test cases'!G{src}"
        summary[f"H{r}"] = f"='Test cases'!C{src}&IF('Test cases'!H{src}=\"\",\"\",\": \"&'Test cases'!H{src})"
        for col in "ABCH":
            summary[f"{col}{r}"].font = BASE
            summary[f"{col}{r}"].alignment = WRAP
    end = l0 + len(CASES)
    for status, colour in STATUS_COLOURS.items():
        summary.conditional_formatting.add(f"C{l0 + 1}:C{end}", FormulaRule(formula=[f'$C{l0 + 1}="{status}"'], fill=PatternFill("solid", fgColor=colour)))
    summary.freeze_panes = "A3"

    wb.calculation.fullCalcOnLoad = True  # Excel works the formulas out when the file opens
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    return OUT


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, help="Playwright JSON report to fill in")
    a = ap.parse_args()
    res = load_results(a.results) if a.results else None
    path = build(res, datetime.now().strftime("%d %b %Y %H:%M"))
    print(f"{path.relative_to(ROOT)}: {len(CASES)} cases" + (f", {len(res)} with results" if res is not None else ""))
