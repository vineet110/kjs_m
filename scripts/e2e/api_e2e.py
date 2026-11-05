"""End-to-end run against the real servers (Next.js :3002 -> FastAPI :8001 -> kjs_e2e DB).
Every API call goes through the Next.js proxy, like the browser does."""
import io
import re
import sys
import time

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
for path, needles in pages.items():
    r = anon.get(path)
    missing = [n for n in needles if n not in r.text]
    check(f"page {path}", r.status_code == 200 and not missing, f"{r.status_code} missing {missing}")
r = anon.get("/sitemap.xml")
check("sitemap lists new pages", r.status_code == 200 and "/private-label" in r.text and prod["slug"] in r.text, r.text[:200])
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
check("configurator lead", anon.post("/api/v1/public/leads", json=lead | {"source": "configurator", "message": "Pack: Stick pack"}, headers=H).status_code == 201)
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
check("Esha sees unassigned leads with SLA", len(leads) == 3 and all(x["sla_label"] for x in leads), leads[:1])
lid = leads[0]["id"]
check("log a call", e1.post(f"/api/v1/employee/leads/{lid}/notes", json={"kind": "call", "text": "Wants samples"}, headers=H).status_code == 204)
check("call marks contacted", next(x for x in j(e1.get("/api/v1/employee/leads")) if x["id"] == lid)["status"] == "contacted")
check("hand over to Farhan", e1.post(f"/api/v1/employee/leads/{lid}/handover", json={"user_id": farhan}, headers=H).status_code == 204)
bell = j(e2.get("/api/v1/employee/notifications"))
check("Farhan gets a notification", bell["unread"] >= 1 and any("assigned to you" in n["title"] for n in bell["items"]), bell)
r = e2.patch(f"/api/v1/employee/leads/{lid}", json={"status": "closed", "outcome": "sample_sent"}, headers=H)
check("Farhan closes with outcome", r.status_code == 204, j(r))
all_leads = j(admin.get("/api/v1/admin/leads"))
check("admin sees all leads + sources", {x["source"] for x in all_leads} == {"enquiry_form", "price_sheet", "configurator"}, [x["source"] for x in all_leads])
check("employee can't open admin leads", e1.get("/api/v1/admin/leads").status_code == 403)

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

# ---------- Admin views ----------
for path in ("/api/v1/admin/analytics", "/api/v1/admin/alerts", "/api/v1/admin/config", "/api/v1/admin/audit",
             "/api/v1/content/koko-chats", "/api/v1/content/partners", "/api/v1/content/texts", "/api/v1/assign/overview",
             "/api/v1/admin/stats", "/api/v1/admin/sla"):
    r = admin.get(path)
    check(f"admin GET {path}", r.status_code == 200, j(r))
check("Koko transcript saved", j(admin.get("/api/v1/content/koko-chats"))["total"] == 1)
check("analytics counts leads", sum(w["count"] for w in j(admin.get("/api/v1/admin/analytics"))["leads_per_week"]) == 3)

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

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
for name, _, info in failed:
    print(" FAIL:", name, "->", str(info)[:400])
sys.exit(1 if failed else 0)
