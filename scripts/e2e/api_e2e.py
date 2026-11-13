"""End-to-end run against the real servers (Next.js :3002 -> FastAPI :8001 -> kjs_e2e DB).
Every API call goes through the Next.js proxy, like the browser does."""
import io
import re
import sys
import time
import zipfile

import httpx

sys.stdout.reconfigure(encoding="utf-8")

WEB = "http://127.0.0.1:3002"
H = {"x-requested-with": "kjs"}
results = []


def check(name, ok, info=""):
    results.append((name, bool(ok), info))
    print(("PASS " if ok else "FAIL ") + name + (f"  -> {info}" if info and not ok else ""))


def client():
    return httpx.Client(base_url=WEB, timeout=60, follow_redirects=False)


def j(r):
    try:
        return r.json()
    except Exception:
        return r.text[:300]


def docx_bytes(paragraphs):
    """The smallest real Word file (standard library only): one paragraph per text, plus a 2x2 table."""
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    p = "".join(f"<w:p><w:r><w:t>{t}</w:t></w:r></w:p>" for t in paragraphs)
    cell = lambda t: f"<w:tc><w:p><w:r><w:t>{t}</w:t></w:r></w:p></w:tc>"
    table = f"<w:tbl><w:tr>{cell('Item')}{cell('Qty')}</w:tr><w:tr>{cell('Coffee stick')}{cell('1000')}</w:tr></w:tbl>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/document.xml", f'<?xml version="1.0" encoding="UTF-8"?><w:document {w}><w:body>{p}{table}</w:body></w:document>')
    return buf.getvalue()


def xlsx_bytes(sheets):
    """The smallest real Excel file: {sheet name: rows}, text cells only (standard library only)."""
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    col = lambda i: chr(65 + i)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                             for i in range(1, len(sheets) + 1)) + "</Types>")
        z.writestr("_rels/.rels", f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   f'<Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml", f'<?xml version="1.0" encoding="UTF-8"?><workbook {ns} xmlns:r="{rel}"><sheets>'
                   + "".join(f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(sheets, 1)) + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(f'<Relationship Id="rId{i}" Type="{rel}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1)) + "</Relationships>")
        for i, rows in enumerate(sheets.values(), 1):
            data = "".join(f'<row r="{r}">' + "".join(f'<c r="{col(c)}{r}" t="inlineStr"><is><t>{v}</t></is></c>' for c, v in enumerate(row)) + "</row>"
                           for r, row in enumerate(rows, 1))
            z.writestr(f"xl/worksheets/sheet{i}.xml", f'<?xml version="1.0" encoding="UTF-8"?><worksheet {ns}><sheetData>{data}</sheetData></worksheet>')
    return buf.getvalue()


def pdf_bytes(text):
    """A one-page PDF with one line of text (offsets computed, so viewers open it)."""
    stream = f"BT /F1 24 Tf 72 760 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


admin, e1, e2, anon = client(), client(), client(), client()

# ---------- Admin login + content setup ----------
r = admin.post("/api/v1/auth/login", json={"email": "admin@e2e.test", "password": "e2e-admin-pass-1"}, headers=H)
check("admin login", r.status_code == 200 and "kjs_session" in r.cookies, j(r))
check("cookie is httpOnly", "httponly" in r.headers.get("set-cookie", "").lower())

r = admin.post("/api/v1/admin/products", json={"category_slug": "coffee", "name": "Instant Coffee 3-in-1 Stick",
                                               "pack_formats": "Stick 18 g", "moq": "100,000 sticks", "is_best_seller": True,
                                               "offer_percent": 15,
                                               "description": "Classic 3-in-1."}, headers=H)
check("create product (with a 15 % offer)", r.status_code == 201 and j(r).get("offer_percent") == 15, j(r))
prod = j(r)
r = admin.post("/api/v1/admin/products", json={"category_slug": "tea", "name": "Masala Tea Premix"}, headers=H)
check("create 2nd product", r.status_code == 201, j(r))
png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
r = admin.post("/api/v1/files", data={"owner_type": "product", "owner_id": prod["slug"], "is_public": "true"},
               files={"file": ("stick.png", png, "image/png")}, headers=H)
check("upload public product photo", r.status_code == 201, j(r))
r = admin.post("/api/v1/files", data={"owner_type": "product", "owner_id": prod["slug"], "is_public": "true"},
               files={"file": ("spec-sheet.pdf", b"%PDF-1.4 spec", "application/pdf")}, headers=H)
check("upload public spec PDF", r.status_code == 201, j(r))
r = admin.post("/api/v1/content/offers", json={"text": "Free samples for new distributors"}, headers=H)
check("add offer", r.status_code == 201, j(r))
r = admin.put("/api/v1/content/texts/home.hero_title", json={"value": "E2E headline: stick packs made right"}, headers=H)
check("edit home headline", r.status_code == 204, j(r))
r = admin.post("/api/v1/admin/holidays", json={"day": "2026-11-09", "name": "Diwali"}, headers=H)
check("add holiday", r.status_code == 201, j(r))

# ---------- Public pages (server-rendered) ----------
pages = {"/products": ["Masala Tea Premix"], "/private-label": ["Build your product", "Instant Coffee 3-in-1 Stick"],
         "/partners": ["Apply to become a partner"], "/contact": ["Send an enquiry"],
         f"/products/{prod['slug']}": ["Request price sheet", "Get spec sheet", "Request a sample", "Get a quote", "spec-sheet.pdf"],
         "/categories/coffee": ["Instant Coffee 3-in-1 Stick"],
         "/employee/login": ["Log in"]}
# Lists of products can still be the 60 s cached copy from before the products were added (always so right after
# a fresh `next build`): those pages are checked for the new products after the cache refresh, at the end.
LISTS = {"/products", "/private-label"}
for path, needles in pages.items():
    r = anon.get(path)
    missing = [] if path in LISTS else [n for n in needles if n not in r.text]
    check(f"page {path}", r.status_code == 200 and not missing, f"{r.status_code} missing {missing}")
check("sitemap.xml answers", anon.get("/sitemap.xml").status_code == 200)
check("robots.txt", anon.get("/robots.txt").status_code == 200)
check("unknown page is 404", anon.get("/this-does-not-exist").status_code == 404)
r = anon.get("/employee/dashboard")
check("portal without login redirects to login", r.status_code in (302, 307) and "/employee/login" in r.headers.get("location", ""), r.status_code)
r = anon.get("/api/v1/public/config")
check("public config has feature switches", r.status_code == 200 and "gated_actions" in j(r)["features"], j(r))

# ---------- Visitor actions ----------
lead = {"name": "Omar Al Noor", "company": "Al Noor Trading", "email": "omar@alnoor.ae", "country": "UAE", "consent": True, "phone": "+971 50 123 4567"}
check("enquiry form lead", anon.post("/api/v1/public/leads", json=lead | {"message": "Need 3-in-1 sticks"}, headers=H).status_code == 201)
check("gated price-sheet lead", anon.post("/api/v1/public/leads", json=lead | {"source": "price_sheet", "product_slug": prod["slug"]}, headers=H).status_code == 201)
check("gated quote lead", anon.post("/api/v1/public/leads", json=lead | {"source": "quote", "product_slug": prod["slug"]}, headers=H).status_code == 201)
# A switched-off feature refuses its API too (PR #45); config/features.ini has configurator = false
conf_on = j(anon.get("/api/v1/public/config"))["features"]["configurator"]
r = anon.post("/api/v1/public/leads", json=lead | {"source": "configurator", "message": "Pack: Stick pack"}, headers=H)
check("configurator lead follows its on/off switch", r.status_code == (201 if conf_on else 404), j(r))
r = anon.post("/api/v1/public/leads", json=lead | {"consent": False}, headers=H)
check("lead without consent rejected", r.status_code == 422, j(r))
r = anon.post("/api/v1/public/partners", json={"name": "Ravi", "partner_type": "forwarder", "country": "UAE",
                                               "email": "ravi@ship.ae", "consent": True, "phone": "+971 50 123 4567"}, headers=H)
check("partner application", r.status_code == 201, j(r))
r = anon.post("/api/v1/koko/chat", json={"messages": [{"role": "user", "content": "Do you make private label coffee sticks? We need 50,000 a month."}],
                                         "chat_id": "e2e-chat-1", "page": "/"}, headers=H)
reply = j(r).get("reply", "") if isinstance(j(r), dict) else ""
check("Koko replies (real Groq)", r.status_code == 200 and len(reply) > 20, j(r))
check("Koko does not promise volume", not re.search(r"\byes,? we can\b", reply, re.I), reply[:200])
print("   Koko said:", reply[:220].replace("\n", " "))

# ---------- Staff sign-up and approval ----------
for c, email, name in ((e1, "esha@e2e.test", "Esha"), (e2, "farhan@e2e.test", "Farhan")):
    r = c.post("/api/v1/auth/signup", json={"name": name, "email": email, "password": "staff-pass-123", "phone": "+91 98765 43210"}, headers=H)
    check(f"signup {name}", r.status_code == 201, j(r))
    r = c.post("/api/v1/auth/login", json={"email": email, "password": "staff-pass-123"}, headers=H)
    check(f"{name} blocked until approved", r.status_code == 403 and j(r)["code"] == "pending_approval", j(r))
inbox = j(admin.get("/api/v1/admin/approvals"))
ids = {u["email"]: u["id"] for u in inbox["signups"]}
check("approvals inbox lists sign-ups", set(ids) == {"esha@e2e.test", "farhan@e2e.test"}, inbox)
check("approve Esha", admin.post(f"/api/v1/admin/users/{ids['esha@e2e.test']}/approve", json={"permissions": ["leads.view"]}, headers=H).status_code == 200)
check("approve Farhan", admin.post(f"/api/v1/admin/users/{ids['farhan@e2e.test']}/approve", json={"permissions": ["leads.view", "attendance.manage"]}, headers=H).status_code == 200)
esha, farhan = ids["esha@e2e.test"], ids["farhan@e2e.test"]
for c, email in ((e1, "esha@e2e.test"), (e2, "farhan@e2e.test")):
    r = c.post("/api/v1/auth/login", json={"email": email, "password": "staff-pass-123"}, headers=H)
    check(f"login {email}", r.status_code == 200, j(r))

# ---------- Attendance ----------
r = e1.post("/api/v1/attendance/check-in", headers=H)
check("Esha checks in", r.status_code == 200 and j(r)["check_in"], j(r))
check("double check-in refused", e1.post("/api/v1/attendance/check-in", headers=H).status_code == 409)
check("week view", len(j(e1.get("/api/v1/attendance/week"))["days"]) == 7)
check("holiday list visible to staff", any(h["name"] == "Diwali" for h in j(e1.get("/api/v1/attendance/holidays"))))
r = e2.post("/api/v1/attendance/regularizations", json={"day": "2026-10-22", "check_in": "09:30", "check_out": "18:30", "reason": "Forgot to punch"}, headers=H)
check("Farhan asks to fix a missed punch", r.status_code == 201, j(r))
reg_id = j(r)["id"]
check("Farhan can't approve his own request", e2.post(f"/api/v1/attendance/approvals/{reg_id}", json={"approve": True}, headers=H).status_code == 403)
check("admin approves it", j(admin.post(f"/api/v1/attendance/approvals/{reg_id}", json={"approve": True}, headers=H))["status"] == "approved")
team = j(admin.get("/api/v1/attendance/team"))
check("team view shows Esha in", any(t["name"] == "Esha" and t["check_in"] for t in team), team)

# ---------- Leave and shifts (PR #31) ----------
check("shift list answers", isinstance(j(e1.get("/api/v1/attendance/shifts")), list))
r = admin.post("/api/v1/attendance/shifts", json={"name": "E2E Early", "code": "E2EEARLY", "start_time": "07:00", "end_time": "15:00"}, headers=H)
check("admin creates a shift", r.status_code == 201 and j(r)["start_time"] == "07:00", j(r))
sid = j(r).get("id") if r.status_code == 201 else 0
check("an employee can't create a shift", e1.post("/api/v1/attendance/shifts", json={"name": "Mine", "code": "MINE1", "start_time": "10:00", "end_time": "12:00"}, headers=H).status_code == 403)
check("bad shift time refused", admin.post("/api/v1/attendance/shifts", json={"name": "Bad", "code": "BAD01", "start_time": "25:00", "end_time": "12:00"}, headers=H).status_code == 422)
r = admin.post("/api/v1/attendance/shifts/assign", json={"user_id": esha, "shift_id": sid}, headers=H)
check("admin gives Esha the shift", r.status_code == 200 and j(r)["shift_id"] == sid, j(r))
today = j(e1.get("/api/v1/attendance/today"))
check("Esha's day shows the new shift", today.get("shift_code") == "E2EEARLY" or "07:00" in str(today.get("shift", "")), today)
check("an employee can't assign shifts", e1.post("/api/v1/attendance/shifts/assign", json={"user_id": esha, "shift_id": sid}, headers=H).status_code == 403)
leave = {"leave_type": "casual", "start_date": "2026-11-23", "end_date": "2026-11-24", "reason": "Family function"}
r = e1.post("/api/v1/attendance/leaves", json=leave, headers=H)
check("Esha asks for 2 days' leave", r.status_code == 201 and j(r)["status"] == "pending" and j(r)["working_days"] == 2, j(r))
lv = j(r).get("id") if r.status_code == 201 else 0
check("overlapping leave refused", e1.post("/api/v1/attendance/leaves", json=leave | {"start_date": "2026-11-24", "end_date": "2026-11-25"}, headers=H).status_code == 409)
check("end before start refused", e1.post("/api/v1/attendance/leaves", json=leave | {"start_date": "2026-11-26", "end_date": "2026-11-25"}, headers=H).status_code == 422)
check("Esha sees her request", any(x["id"] == lv for x in j(e1.get("/api/v1/attendance/leaves"))))
check("Esha can't open the approvals list", e1.get("/api/v1/attendance/leaves/approvals").status_code == 403)
check("Farhan (attendance.manage) sees it waiting", any(x["id"] == lv for x in j(e2.get("/api/v1/attendance/leaves/approvals"))))
r = e2.post(f"/api/v1/attendance/leaves/approvals/{lv}", json={"approve": True}, headers=H)
check("Farhan approves Esha's leave", r.status_code == 200 and j(r)["status"] == "approved", j(r))
check("deciding twice refused", e2.post(f"/api/v1/attendance/leaves/approvals/{lv}", json={"approve": False}, headers=H).status_code == 409)
month = j(e1.get("/api/v1/attendance/month?year=2026&month=11"))
day23 = next((d for d in month.get("days", []) if d["day"] == "2026-11-23"), {}) if isinstance(month, dict) else {}
check("the approved leave shows in Esha's month", day23.get("state") == "leave", day23)
r = e2.post("/api/v1/attendance/leaves", json=leave | {"start_date": "2026-11-27", "end_date": "2026-11-27", "is_half_day": True, "half_day_session": "first_half"}, headers=H)
check("Farhan asks for half a day", r.status_code == 201, j(r))
fl = j(r).get("id") if r.status_code == 201 else 0
check("Farhan can't approve his own leave", e2.post(f"/api/v1/attendance/leaves/approvals/{fl}", json={"approve": True}, headers=H).status_code == 403)
r = admin.post(f"/api/v1/attendance/leaves/approvals/{fl}", json={"approve": False, "rejection_reason": "Audit that day"}, headers=H)
check("admin rejects it with a reason", r.status_code == 200 and j(r)["status"] == "rejected" and j(r).get("rejection_reason") == "Audit that day", j(r))

# ---------- Auto-assign ----------
check("set Esha's categories", admin.post(f"/api/v1/assign/staff/{esha}/categories", json={"categories": ["coffee"]}, headers=H).status_code == 204)
csv = "Company,Contact,Email,Country,Category\nDubai Mart,Ali,ali@dm.ae,UAE,coffee\nLagos Foods,Ada,,Nigeria,coffee\n,x,,,coffee\n"
r = admin.post("/api/v1/assign/import", files={"file": ("buyers.csv", csv.encode(), "text/csv")}, headers=H)
check("import buyer list", r.status_code == 201 and j(r)["added"] == 2 and j(r)["skipped_count"] == 1, j(r))
plan = j(admin.get("/api/v1/assign/preview"))
check("preview gives Esha 2", [(p["name"], p["would_get"]) for p in plan] == [("Esha", 2)], plan)
r = admin.post("/api/v1/assign/run", headers=H)
check("run now", j(r)["batches"] == 1, j(r))
batch = j(e1.get("/api/v1/assign/my-batches"))[0]
r = e1.patch(f"/api/v1/assign/records/{batch['records'][0]['id']}", json={"status": "done", "outcome": "Sent catalogue"}, headers=H)
check("Esha works a record", j(r)["left"] == 1, j(r))

# ---------- Leads ----------
leads = j(e1.get("/api/v1/employee/leads"))
WEB_LEADS = 3 + (1 if conf_on else 0)  # enquiry, price sheet, quote (+ configurator when it is on)
check("Esha sees unassigned leads with SLA", len(leads) == WEB_LEADS and all(x["sla_label"] for x in leads), leads[:1])
lid = leads[0]["id"]
check("log a call", e1.post(f"/api/v1/employee/leads/{lid}/notes", json={"kind": "call", "text": "Wants samples"}, headers=H).status_code == 204)
check("call marks contacted", next(x for x in j(e1.get("/api/v1/employee/leads")) if x["id"] == lid)["status"] == "contacted")
check("hand over to Farhan", e1.post(f"/api/v1/employee/leads/{lid}/handover", json={"user_id": farhan}, headers=H).status_code == 204)
bell = j(e2.get("/api/v1/employee/notifications"))
check("Farhan gets a notification", bell["unread"] >= 1 and any("assigned to you" in n["title"] for n in bell["items"]), bell)
r = e2.patch(f"/api/v1/employee/leads/{lid}", json={"status": "closed", "outcome": "sample_sent"}, headers=H)
check("Farhan closes with outcome", r.status_code == 204, j(r))
all_leads = j(admin.get("/api/v1/admin/leads"))
check("admin sees all leads + sources", {x["source"] for x in all_leads} == {"enquiry_form", "price_sheet", "quote"} | ({"configurator"} if conf_on else set()), [x["source"] for x in all_leads])
check("employee can't open admin leads", e1.get("/api/v1/admin/leads").status_code == 403)

# ---------- Lead management and contacts (PR #33) ----------
kiran = {"name": "Kiran Rao", "company": "Rao Foods", "phone": "+91 98480 22222", "email": "kiran@raofoods.in",
         "country": "India", "quantity": "20,000 sticks", "message": "Met at the trade fair"}
r = e1.post("/api/v1/employee/leads", json=kiran, headers=H)
check("Esha adds an internal lead (hers from the start)", r.status_code == 201 and j(r)["source"] == "internal" and j(r)["assigned_to"] == esha, j(r))
ilead = j(r)["id"] if r.status_code == 201 else 0
check("internal lead list (source=internal)", [x["id"] for x in j(e1.get("/api/v1/employee/leads?source=internal"))] == [ilead])
check("Koko lead list answers (source=koko)", e1.get("/api/v1/employee/leads?source=koko").status_code == 200)
r = e1.post("/api/v1/employee/leads", json=kiran | {"phone": ""}, headers=H)
check("internal lead without a phone refused", r.status_code == 422, j(r))
cs = j(e1.get("/api/v1/employee/contacts"))
names = [c["name"] for c in cs] if isinstance(cs, list) else cs
check("contacts: one row per person (Omar's enquiries are one row)", names.count("Omar Al Noor") == 1 and "Kiran Rao" in names, names)
omar = next((c for c in cs if c["name"] == "Omar Al Noor"), {}) if isinstance(cs, list) else {}
check("contacts: Omar's open enquiries counted", omar.get("total", 0) >= 2, omar)
d = j(e1.get(f"/api/v1/employee/contacts/{ilead}"))
check("contact page: the lead and the person's enquiries", isinstance(d, dict) and d["lead"]["name"] == "Kiran Rao" and len(d["enquiries"]) == 1, d)
r = e1.post(f"/api/v1/employee/leads/{ilead}/tasks", json={"title": "Send samples to Kiran", "due_at": "2026-11-20T06:30:00Z"}, headers=H)
check("task on a lead", r.status_code == 201, j(r))
check("the lead's task list shows it", [t["title"] for t in j(e1.get(f"/api/v1/employee/leads/{ilead}/tasks"))] == ["Send samples to Kiran"])
check("the task is in Esha's tasks (source lead)", any(t["title"] == "Send samples to Kiran" and t["source"] == "lead" for t in j(e1.get("/api/v1/tasks"))))
check("note on a lead", e1.post(f"/api/v1/employee/leads/{ilead}/notes", json={"kind": "note", "text": "Prefers WhatsApp"}, headers=H).status_code == 204)
check("the note is listed", any(n["text"] == "Prefers WhatsApp" for n in j(e1.get(f"/api/v1/employee/leads/{ilead}/notes"))))
check("Farhan can't open Esha's lead (404)", e2.get(f"/api/v1/employee/contacts/{ilead}").status_code == 404)
check("Farhan can't add notes to it", e2.post(f"/api/v1/employee/leads/{ilead}/notes", json={"kind": "note", "text": "x y"}, headers=H).status_code in (403, 404))
check("Farhan's contacts don't list Kiran", "Kiran Rao" not in [c["name"] for c in j(e2.get("/api/v1/employee/contacts"))])
check("admin (all leads) sees Kiran in contacts", "Kiran Rao" in [c["name"] for c in j(admin.get("/api/v1/employee/contacts"))])
check("admin assigns Kiran's lead to Farhan", admin.post(f"/api/v1/admin/leads/{ilead}/assign", json={"user_id": farhan}, headers=H).status_code == 204)
check("now Farhan can open it", e2.get(f"/api/v1/employee/contacts/{ilead}").status_code == 200)
check("and Esha no longer can", e1.get(f"/api/v1/employee/contacts/{ilead}").status_code == 404)
check("an employee can't use the admin assign route", e1.post(f"/api/v1/admin/leads/{ilead}/assign", json={"user_id": esha}, headers=H).status_code == 403)

# ---------- Tasks ----------
r = admin.post("/api/v1/tasks", json={"title": "Send spec sheet to Al Noor", "assignee_id": esha, "due_at": "2026-10-27T12:00:00Z"}, headers=H)
check("admin gives Esha a task", r.status_code == 201, j(r))
tid = j(r)["id"]
r = e1.post("/api/v1/tasks", json={"title": "Follow up Dubai Mart"}, headers=H)
check("Esha adds own task", r.status_code == 201)
check("Esha completes task", j(e1.patch(f"/api/v1/tasks/{tid}", json={"status": "done", "outcome": "Sent"}, headers=H))["status"] == "done")
check("task stats", j(e1.get("/api/v1/tasks/stats"))["done"] == 1)

# ---------- Order board ----------
board = {"code": "E2E117-1", "name": "3-in-1 sticks", "client": "Al Noor", "start": "2026-10-26", "deadline": "2026-11-14",
         "steps": [{"name": "Blending", "percent": 40, "member_ids": [esha], "task_templates": ["Weigh raw materials"], "checklist": ["QC ok"]},
                   {"name": "Packing", "percent": 60, "member_ids": [farhan], "task_templates": ["Pack sticks"]}]}
r = admin.post("/api/v1/boards/preview", json={"start": board["start"], "deadline": board["deadline"], "sizes": [40, 60]}, headers=H)
check("board plan preview skips the Diwali holiday", r.status_code == 200 and j(r)["steps"][1]["end"] == "2026-11-14", j(r))
r = admin.post("/api/v1/boards", json=board, headers=H)
check("create order board", r.status_code == 201, j(r))
b = j(e1.get("/api/v1/boards/E2E117-1"))
check("Esha sees board, step 1 running", b["steps"][0]["status"] == "active" and b["my_step_ids"] == [b["steps"][0]["id"]], b)
check("Esha got the step task", any(t["source"] == "board" for t in j(e1.get("/api/v1/tasks"))))
r = e1.post("/api/v1/files", data={"owner_type": "board", "owner_id": "E2E117-1"}, files={"file": ("po.pdf", b"%PDF po", "application/pdf")}, headers=H)
check("Esha uploads a board document", r.status_code == 201, j(r))
fid = j(r)["id"]
check("download works through the proxy", e1.get(f"/api/v1/files/{fid}/download").content == b"%PDF po")
check("Esha asks to delete it", e1.post(f"/api/v1/files/{fid}/delete-request", json={"reason": "Wrong PO"}, headers=H).status_code == 200)
check("approvals inbox shows the delete", any(f["id"] == fid for f in j(admin.get("/api/v1/admin/approvals"))["file_deletes"]))
check("admin approves delete", j(admin.post(f"/api/v1/files/{fid}/delete-decision", json={"approve": True}, headers=H))["delete_status"] == "approved")
r = e1.post(f"/api/v1/boards/E2E117-1/steps/{b['steps'][0]['id']}/done", headers=H)
check("Esha finishes her step, Packing starts", [s["status"] for s in j(r)["steps"]] == ["done", "active"], j(r))
check("Farhan now sees the board", [x["code"] for x in j(e2.get("/api/v1/boards"))] == ["E2E117-1"])

# ---------- Order boards: people, step heads, file previews, History, plan lock (PRs #35-#39) ----------
BRD = "/api/v1/boards/E2E117-1"
me_admin = j(admin.get("/api/v1/auth/me"))["id"]
r = admin.post("/api/v1/admin/users", json={"name": "Gita", "email": "gita@e2e.test", "phone": "+91 98765 11111",
                                             "employee_code": "E2E-3", "branch": "Hyderabad", "role": "employee"}, headers=H)
check("admin creates a third person (Gita)", r.status_code == 201, j(r))
gita = j(r)["user"]["id"] if r.status_code == 201 else 0
g = client()
check("Gita logs in", g.post("/api/v1/auth/login", json={"email": "gita@e2e.test", "password": j(r).get("temp_password", "")}, headers=H).status_code == 200)
check("Gita can't open a board she isn't on", g.get(BRD).status_code in (403, 404))
check("a member (Esha) can't add people", e1.post(f"{BRD}/people", json={"user_id": gita}, headers=H).status_code == 403)
r = admin.post(f"{BRD}/people", json={"user_id": gita}, headers=H)
check("owner adds Gita to the board", r.status_code == 200 and gita in [p["id"] for p in j(r)["people"]], j(r))
check("adding her twice refused", admin.post(f"{BRD}/people", json={"user_id": gita}, headers=H).status_code == 409)
check("Gita now sees the board and is told", g.get(BRD).status_code == 200 and any("E2E117-1" in n["title"] for n in j(g.get("/api/v1/employee/notifications"))["items"]))
b = j(admin.get(BRD))
blending, packing = b["steps"][0]["id"], b["steps"][1]["id"]
r = admin.put(f"{BRD}/steps/{packing}/people", json={"member_ids": [farhan, gita], "head_ids": [gita]}, headers=H)
pk = next((s for s in j(r)["steps"] if s["id"] == packing), {}) if r.status_code == 200 else {}
check("owner puts Gita on Packing as its head", [(m["id"], m["is_head"]) for m in pk.get("members", [])] == [(gita, True), (farhan, False)], j(r))
check("the head must be one of the step's people", admin.put(f"{BRD}/steps/{packing}/people", json={"member_ids": [farhan], "head_ids": [esha]}, headers=H).status_code == 422)
check("a step needs at least one person", admin.put(f"{BRD}/steps/{packing}/people", json={"member_ids": [], "head_ids": []}, headers=H).status_code == 422)
check("a done step's people can't change", admin.put(f"{BRD}/steps/{blending}/people", json={"member_ids": [gita]}, headers=H).status_code == 409)
check("a member can't change a step's people", e2.put(f"{BRD}/steps/{packing}/people", json={"member_ids": [farhan]}, headers=H).status_code == 403)
check("the owner can't be removed", admin.delete(f"{BRD}/people/{me_admin}", headers=H).status_code == 409)
admin.put(f"{BRD}/steps/{packing}/people", json={"member_ids": [gita], "head_ids": [gita]}, headers=H)
check("the last person on a running step can't be removed", admin.delete(f"{BRD}/people/{gita}", headers=H).status_code == 409)
admin.put(f"{BRD}/steps/{packing}/people", json={"member_ids": [farhan, gita], "head_ids": [farhan]}, headers=H)

# Files of each type: the preview route (/view) sends them to be shown in the page, never cached, only to the board's
# people. A real PDF may be framed by our own pages (Chrome's PDF viewer won't open a sandboxed one); every other file,
# and a ".pdf" that isn't really a PDF, is sandboxed (no scripts can run in it).
SAMPLES = {
    "rates-hindi.csv": ("text/csv", "उत्पाद,मात्रा,दर (₹)\nकॉफ़ी स्टिक,1000,₹ 2.50\nचाय प्रीमिक्स,500,\"₹ 1,250\"\n".encode()),
    "plan.xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                  xlsx_bytes({"Order": [["Item", "Qty", "Rate (₹)"], ["Coffee stick", "1000", "2.50"]], "Notes": [["Note"], ["दूसरी शीट"]]})),
    "po-117.docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    docx_bytes(["Purchase order PO-117", "Deliver 1000 coffee sticks. दर ₹ 2.50"])),
    "board-test.pdf": ("application/pdf", pdf_bytes("Board E2E117-1 test PDF")),
    "label.png": ("image/png", png),
    "fake.pdf": ("application/pdf", b"<html><script>alert(1)</script></html>"),
}
fids = {}
for name, (ctype, data) in SAMPLES.items():
    r = e2.post("/api/v1/files", data={"owner_type": "board", "owner_id": "E2E117-1"}, files={"file": (name, data, ctype)}, headers=H)
    fids[name] = j(r).get("id") if r.status_code == 201 else 0
check("a member uploads a CSV, Excel, Word, PDF, PNG and a fake PDF", all(fids.values()), fids)
for name, (ctype, data) in SAMPLES.items():
    r = e1.get(f"/api/v1/files/{fids[name]}/view")
    csp = "frame-ancestors 'self'" if name == "board-test.pdf" else "sandbox"
    ok = (r.status_code == 200 and r.content == data and r.headers.get("content-type", "").startswith(ctype)
          and r.headers.get("content-disposition", "").startswith("inline") and "no-store" in r.headers.get("cache-control", "")
          and r.headers.get("x-content-type-options") == "nosniff" and r.headers.get("content-security-policy") == csp)
    check(f"preview of {name}: same bytes, inline, not cached, CSP {csp}", ok,
          f"{r.status_code} {r.headers.get('content-type')} {r.headers.get('content-disposition')} {r.headers.get('content-security-policy')}")
check("preview without logging in refused", anon.get(f"/api/v1/files/{fids['board-test.pdf']}/view").status_code == 401)

# History tab
h = j(e1.get(f"{BRD}/history"))
texts = " | ".join(i["text"] for i in h.get("items", [])) if isinstance(h, dict) else str(h)
check("History: people, step heads and uploads are listed", all(w in texts for w in ("added Gita to the board", "head now Gita", "uploaded board-test.pdf")), texts[:400])
check("History: newest first", isinstance(h, dict) and [i["id"] for i in h["items"]] == sorted((i["id"] for i in h["items"]), reverse=True))
oldest = h["items"][-1]["id"] if isinstance(h, dict) and h["items"] else 0
older = j(e1.get(f"{BRD}/history?before_id={oldest}"))
check("History: older lines page back (before_id)", isinstance(older, dict) and all(i["id"] < oldest for i in older["items"]), older)
check("History: only the board's people", client().get(f"{BRD}/history").status_code == 401)

# Plan editing and the owner's lock
def plan_body(c, **change):
    x = j(c.get(BRD))
    return {"start": x["start"], "deadline": x["deadline"], "split_mode": x["split_mode"], "version": x["plan_version"],
            "steps": [{"id": s["id"], "name": s["name"], "size": s["percent"]} for s in x["steps"]]} | change
r = e1.put(f"{BRD}/plan", json=plan_body(e1, deadline="2026-11-16"), headers=H)
check("unlocked: a member moves the deadline", r.status_code == 200 and j(r)["deadline"] == "2026-11-16", j(r))
stale = plan_body(e2)
admin.put(f"{BRD}/plan", json=plan_body(admin, deadline="2026-11-17"), headers=H)
check("an old copy of the plan is refused (someone changed it meanwhile)", e2.put(f"{BRD}/plan", json=stale, headers=H).status_code == 409)
check("a member can't lock the plan", e1.post(f"{BRD}/plan-lock", json={"locked": True}, headers=H).status_code == 403)
r = admin.post(f"{BRD}/plan-lock", json={"locked": True}, headers=H)
check("the owner locks the plan", r.status_code == 200 and j(r)["plan_locked"] is True, j(r))
x = j(e1.get(BRD))
check("locked: members see it and can't edit", x["plan_locked"] and not x["can_edit_plan"], x.get("can_edit_plan"))
r = e1.put(f"{BRD}/plan", json=plan_body(e1, deadline="2026-11-18"), headers=H)
check("locked: a member's plan change is refused", r.status_code == 403 and j(r)["code"] == "plan_locked", j(r))
r = admin.put(f"{BRD}/plan", json=plan_body(admin, deadline="2026-11-18"), headers=H)
check("locked: the owner can still change it", r.status_code == 200 and j(r)["deadline"] == "2026-11-18", j(r))
check("the owner unlocks", j(admin.post(f"{BRD}/plan-lock", json={"locked": False}, headers=H))["plan_locked"] is False)
check("unlocked again: a member can change it", e1.put(f"{BRD}/plan", json=plan_body(e1, deadline="2026-11-14"), headers=H).status_code == 200)
h = " | ".join(i["text"] for i in j(admin.get(f"{BRD}/history"))["items"])
check("History shows the lock, unlock and plan changes", "locked" in h and "unlocked" in h and re.search(r"plan|deadline", h, re.I), h[:400])

# Removing someone
r = admin.delete(f"{BRD}/people/{gita}", headers=H)
check("the owner removes Gita", r.status_code == 200 and gita not in [p["id"] for p in j(r)["people"]], j(r))
check("Gita can't open the board any more", g.get(BRD).status_code in (403, 404))
check("Gita can't preview its files any more", g.get(f"/api/v1/files/{fids['board-test.pdf']}/view").status_code in (403, 404))
check("Gita is told she was removed", any("removed" in n["title"] for n in j(g.get("/api/v1/employee/notifications"))["items"]))

# ---------- Admin views ----------
for path in ("/api/v1/admin/analytics", "/api/v1/admin/alerts", "/api/v1/admin/config", "/api/v1/admin/audit",
             "/api/v1/content/koko-chats", "/api/v1/content/partners", "/api/v1/content/texts", "/api/v1/assign/overview",
             "/api/v1/admin/stats", "/api/v1/admin/sla"):
    r = admin.get(path)
    check(f"admin GET {path}", r.status_code == 200, j(r))
check("Koko transcript saved", j(admin.get("/api/v1/content/koko-chats"))["total"] == 1)
check("analytics counts leads (website + 1 internal)", sum(w["count"] for w in j(admin.get("/api/v1/admin/analytics"))["leads_per_week"]) == WEB_LEADS + 1)

# ---------- Profile ----------
check("profile update", j(e1.patch("/api/v1/auth/profile", json={"phone": "+91 90000 00000"}, headers=H))["phone"] == "+91 90000 00000")
check("password change", e1.post("/api/v1/auth/password", json={"current": "staff-pass-123", "new": "staff-pass-456"}, headers=H).status_code == 204)

# ---------- Every portal page renders (logged in as admin) ----------
for path in ("/employee/dashboard", "/employee/attendance", "/employee/tasks", "/employee/batches", "/employee/order-boards",
             "/employee/order-boards/E2E117-1", "/employee/me", "/admin/dashboard", "/admin/leads", "/admin/approvals",
             "/admin/team-attendance", "/admin/order-boards", "/admin/order-boards/E2E117-1", "/admin/auto-assign",
             "/admin/products", "/admin/website", "/admin/koko", "/admin/holidays", "/admin/analytics", "/admin/alerts",
             "/admin/audit", "/admin/settings"):
    r = admin.get(path)
    check(f"portal page {path}", r.status_code == 200 and "<html" in r.text, r.status_code)

# ---------- Logout ----------
check("logout", e1.post("/api/v1/auth/logout", headers=H).status_code == 204)
check("after logout: 401", e1.get("/api/v1/auth/me").status_code == 401)
check("CSRF: POST without header refused", admin.post("/api/v1/tasks", json={"title": "x y"}).status_code == 403)

# ---------- Home page refreshes by itself (60 s cache, backlog A37) ----------
anon.get("/")  # may serve the cached copy and start a refresh in the background
time.sleep(62)
anon.get("/")
time.sleep(3)
r = anon.get("/")
needles = ["E2E headline", "Free samples for new distributors", "Instant Coffee 3-in-1 Stick"]
check("home shows admin changes within a minute", r.status_code == 200 and all(n in r.text for n in needles),
      [n for n in needles if n not in r.text])
for path in [*sorted(LISTS), "/sitemap.xml"]:  # past the 60 s now: this visit starts the refresh (see LISTS above)
    anon.get(path)
time.sleep(3)
for path in sorted(LISTS):
    r = anon.get(path)
    missing = [n for n in pages[path] if n not in r.text]
    check(f"page {path} lists the new products", r.status_code == 200 and not missing, f"{r.status_code} missing {missing}")
r = anon.get("/sitemap.xml")
check("sitemap lists new pages", r.status_code == 200 and "/private-label" in r.text and prod["slug"] in r.text, r.text[:200])

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
for name, _, info in failed:
    print(" FAIL:", name, "->", str(info)[:400])
sys.exit(1 if failed else 0)
