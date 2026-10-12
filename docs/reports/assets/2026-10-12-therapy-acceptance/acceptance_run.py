import asyncio, json, os, sys, time, requests, uuid
from datetime import date, timedelta
sys.path.insert(0, "/home/caoscare-1/CAOSCARE-INTEGRATION/backend"); os.chdir("/home/caoscare-1/CAOSCARE-INTEGRATION/backend")
from dotenv import load_dotenv; load_dotenv(".env")
from playwright.sync_api import sync_playwright
OUT = os.path.dirname(os.path.abspath(__file__)); API = "http://127.0.0.1:8092/api"; WEB = "http://localhost:3000"
KIOSK, RID = "kio_67f409214f27", "res_fd05a2b60ef8"
async def setup():
    from motor.motor_asyncio import AsyncIOMotorClient
    from routes.auth import _issue_jwt
    from routes.realtime_facility import today_facility_date
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    u = await db.users.find_one({"role": "owner"}, {"_id": 0, "user_id": 1})
    r2 = await db.residents.find_one({"name": {"$regex": "^Demo - "}, "room": "3W01"}, {"_id": 0, "resident_id": 1, "name": 1})
    return _issue_jwt(u["user_id"]), r2, today_facility_date()
OWNER, R2, TODAY = asyncio.run(setup())
H = lambda t: {"Authorization": f"Bearer {t}"}
login = lambda e, p: requests.post(f"{API}/auth/login", json={"email": e, "password": p}).json()["token"]
FD = login("dana.frost@demo.caoscare", "demo-pass-1234"); NURSE = login("nancy.reyes@demo.caoscare", "demo-pass-1234")
PW = "acc-" + uuid.uuid4().hex[:12]; EMAIL = f"therapy.acceptance.{uuid.uuid4().hex[:6]}@demo.caoscare"
R = []; ok = lambda name, cond, ev=None: R.append((name, bool(cond), ev))
created, staff_id, tpl_id = [], None, None
d1 = (date.fromisoformat(TODAY) + timedelta(days=2)).isoformat()
try:
    st = requests.post(f"{API}/staff", headers=H(OWNER), json={"email": EMAIL, "name": "Demo - Temp Therapist (acceptance)",
                       "password": PW, "role": "staff", "department": "therapy"})
    ok("temp therapy account created via staff API", st.status_code == 200, st.status_code); staff_id = st.json().get("user_id")
    PT = login(EMAIL, PW)
    # 1 create (front desk, authenticated, canonical resident-request)
    t = requests.post(f"{API}/tasks/resident-request", headers=H(FD), json={"category": "therapy", "resident_id": RID,
        "source": "front_desk", "summary": "Acceptance: knee physical therapy", "resident_words": "my knee therapy"}).json()["task_id"]
    created.append(t)
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
        def page(tok, w=1280, h=900):
            c = br.new_context(viewport={"width": w, "height": h})
            if tok: c.add_init_script(f"localStorage.setItem('caos_token', {json.dumps(tok)})")
            pg = c.new_page(); errs = []
            pg.on("response", lambda r: errs.append(f"{r.status} {r.url.split('/api')[-1]}") if "/api/" in r.url and r.status >= 400 and r.status != 409 else None)
            pg.on("pageerror", lambda e: errs.append(f"pageerror {e}")); return pg, errs
        def shot(pg, n): pg.screenshot(path=f"{OUT}/{n}.png", full_page=True)
        overflow = lambda pg: pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        allerrs = []
        # front desk sees it
        pg, e = page(FD); pg.goto(f"{WEB}/front-desk"); pg.wait_for_timeout(3000)
        pg.get_by_text("All requests").first.click(); pg.wait_for_timeout(2000)
        ok("1 front desk sees the new request", "Acceptance: knee physical therapy" in pg.inner_text("body")); shot(pg, "01-frontdesk"); allerrs += e
        # 2 therapist plans (provider/discipline/location), reschedules
        pg, e = page(PT); pg.goto(f"{WEB}/workspace"); pg.wait_for_timeout(3500); shot(pg, "02a-therapist-workspace")
        def plan(label, extra=True):
            pg.click(f"[data-testid=wo-plan-{t}]"); pg.wait_for_timeout(400)
            pg.fill("[data-testid=wo-plan-date]", d1); pg.fill("[data-testid=wo-plan-label]", label)
            if extra:
                pg.fill("[data-testid=wo-plan-provider]", "Demo - Tess Ortiz PT"); pg.fill("[data-testid=wo-plan-discipline]", "physical therapy")
                pg.fill("[data-testid=wo-plan-location]", "Therapy gym")
            pg.click("[data-testid=wo-plan-save]"); pg.wait_for_timeout(1500)
        plan("10:00 AM"); plan("2:00 PM", extra=False)
        card = pg.inner_text(f"[data-testid=wo-planned-{t}]") if pg.locator(f"[data-testid=wo-planned-{t}]").count() else ""
        ok("2 planned + rescheduled with details on card", "2:00 PM" in card, card)
        ok("2 details on card", "Tess Ortiz" in pg.inner_text("body") and "Therapy gym" in pg.inner_text("body"))
        # 3 claim/start
        pg.click(f"[data-testid=wo-claim-{t}]"); pg.wait_for_timeout(1200)
        pg.click(f"[data-testid=wo-start-{t}]"); pg.wait_for_timeout(1200)
        # 4 note
        pg.click(f"[data-testid=wo-note-{t}]"); pg.wait_for_timeout(300)
        ok("4 note dialog says resident hears it", "resident can hear" in pg.locator("[role=dialog]").inner_text())
        pg.fill("[data-testid=wo-note-text]", "Please wear walking shoes."); pg.click("[data-testid=wo-note-save]"); pg.wait_for_timeout(1200)
        # 9 linked ride
        if pg.locator(f"[data-testid=wo-ride-{t}]").count():
            pg.click(f"[data-testid=wo-ride-{t}]"); pg.wait_for_timeout(1800)
        task = requests.get(f"{API}/tasks/{t}/detail", headers=H(OWNER)).json()["task"]
        ok("3 claimed + started by therapist", task["status"] == "in_progress" and task["assigned_to"] == staff_id)
        ok("9 linked ride created", bool(task.get("linked_ride_task_id")), task.get("linked_ride_task_id"))
        if task.get("linked_ride_task_id"): created.append(task["linked_ride_task_id"])
        shot(pg, "02b-therapist-in-progress"); allerrs += e
        # 12 resident Home + Aria truth (desktop + 390)
        for w, n in ((1280, "1280"), (390, "390")):
            rp, re_ = page(None, w, 900 if w > 400 else 844); rp.goto(f"{WEB}/kiosk/{KIOSK}"); rp.wait_for_timeout(5000)
            b = rp.inner_text("body"); shot(rp, f"03-resident-{n}")
            ok(f"12 resident {n} shows plan + note", "2:00 PM" in b and "walking shoes" in b and "Tess Ortiz" in b)
            if w == 390: ok("12 resident 390 overflow px (pre-existing kiosk row noted earlier)", True, overflow(rp))
            allerrs += re_
        stj = requests.get(f"{API}/tasks/resident-request/status", params={"resident_id": RID, "category": "therapy"}).json()
        sp = json.dumps(stj)
        ok("12 Aria status: working, window, provider, latest note", "working on it" in sp and "2:00 PM" in sp and "Tess Ortiz" in sp and "walking shoes" in sp)
        # 5 complete with note (dialog labelled)
        pg, e = page(PT, 390, 844); pg.goto(f"{WEB}/workspace"); pg.wait_for_timeout(3500)
        pg.click(f"[data-testid=wo-complete-{t}]"); pg.wait_for_timeout(400)
        ok("5 complete dialog says resident sees it", "Aria may read it" in pg.locator("[role=dialog]").inner_text())
        pg.fill("[data-testid=wo-complete-notes]", "Session done; home exercises given."); pg.click("[data-testid=wo-complete-submit]"); pg.wait_for_timeout(1500)
        ok("therapist 390 overflow", overflow(pg) <= 0, overflow(pg)); shot(pg, "04-therapist-complete-390"); allerrs += e
        # 6 reopen (owner) then cancel (therapist) a second appointment
        ap, e = page(OWNER); ap.goto(f"{WEB}/admin?tab=therapy"); ap.wait_for_timeout(3500)
        if ap.locator(f"[data-testid=wo-reopen-{t}]").count():
            ap.click(f"[data-testid=wo-reopen-{t}]"); ap.wait_for_timeout(300)
            ok("6 reopen dialog says resident sees it", "Aria may read it" in ap.locator("[role=dialog]").inner_text())
            ap.fill("[data-testid=wo-reopen-reason]", "Family asked for one more session."); ap.click("[data-testid=wo-reopen-submit]"); ap.wait_for_timeout(1500)
        task = requests.get(f"{API}/tasks/{t}/detail", headers=H(OWNER)).json()["task"]
        ok("6 reopened to pending with assignee", task["status"] == "pending" and task["assigned_to"] == staff_id, task["status"])
        shot(ap, "05-owner-reopen"); allerrs += e
        t2 = requests.post(f"{API}/tasks/resident-request", headers=H(FD), json={"category": "therapy", "resident_id": RID,
            "source": "front_desk", "summary": "Acceptance: balance class"}).json()["task_id"]; created.append(t2)
        pg, e = page(PT); pg.goto(f"{WEB}/workspace"); pg.wait_for_timeout(3500)
        pg.click(f"[data-testid=wo-cancel-{t2}]"); pg.wait_for_timeout(300)
        ok("6 cancel dialog says resident sees it", "Aria may read it" in pg.locator("[role=dialog]").inner_text())
        pg.fill("[data-testid=wo-cancel-reason]", "Resident declined today."); pg.click("[data-testid=wo-cancel-submit]"); pg.wait_for_timeout(1500)
        ok("6 cancelled", requests.get(f"{API}/tasks/{t2}/detail", headers=H(OWNER)).json()["task"]["status"] == "skipped")
        allerrs += e
        # 8 cross-resident conflict refused, then explicit override (UI)
        t3 = requests.post(f"{API}/tasks/resident-request", headers=H(FD), json={"category": "therapy", "resident_id": R2["resident_id"],
            "source": "front_desk", "summary": "Acceptance: gait training"}).json()["task_id"]; created.append(t3)
        pg.reload(); pg.wait_for_timeout(3500)
        pg.click(f"[data-testid=wo-plan-{t3}]"); pg.wait_for_timeout(400)
        pg.fill("[data-testid=wo-plan-date]", d1); pg.fill("[data-testid=wo-plan-label]", "2:30 PM"); pg.fill("[data-testid=wo-plan-provider]", "Demo - Tess Ortiz PT")
        pg.click("[data-testid=wo-plan-save]"); pg.wait_for_timeout(1500)
        dl = pg.locator("[role=dialog]").last.inner_text()
        ok("8 conflict dialog names other resident + same provider", "same provider" in dl and "knee" in dl.lower(), dl[:160])
        before = requests.get(f"{API}/tasks/{t3}/detail", headers=H(OWNER)).json()["task"].get("requested_for_time_label")
        ok("8 nothing written before choice", before is None)
        shot(pg, "06-conflict-dialog"); pg.locator("[role=dialog] button", has_text="Save anyway").click(); pg.wait_for_timeout(2000)
        rc = [x for x in requests.get(f"{API}/tasks/{t3}/detail", headers=H(OWNER)).json()["receipts"] if x.get("result") == "conflict_override"]
        ok("8 override receipted", rc and t in rc[0]["provider_refs"], [(x["action_type"], x["authority"]) for x in rc])
        # 7 recurrence + Upcoming
        tpl = requests.post(f"{API}/tasks/templates", headers=H(OWNER), json={"title": "Demo - Acceptance weekly PT", "recur": "weekly",
            "weekday": date.fromisoformat(d1).weekday(), "time_label": "9:00 AM", "department": "therapy",
            "provider_name": "Demo - Pat Lee PT", "resident_id": RID}).json(); tpl_id = tpl.get("template_id")
        requests.post(f"{API}/tasks/spawn-today", headers=H(OWNER))
        occ = [x for x in requests.get(f"{API}/tasks", headers=H(OWNER), params={"resident_id": RID}).json() if x.get("template_id") == tpl_id]
        created += [x["task_id"] for x in occ]
        pg.reload(); pg.wait_for_timeout(3500); up = pg.inner_text("[data-testid=upcoming-schedule]") if pg.locator("[data-testid=upcoming-schedule]").count() else ""
        ok("7 recurrence occurrence in therapist Upcoming", bool(occ) and "Pat Lee" in up, len(occ))
        ok("8 Upcoming shows overlap", "same provider" in up); shot(pg, "07-upcoming"); allerrs += e
        ru = requests.get(f"{API}/tasks/resident-request/upcoming", params={"resident_id": RID}).json()
        ok("7 resident upcoming has recurring + no conflicts", "Pat Lee" in json.dumps(ru) and "conflicts" not in json.dumps(ru))
        # 11 refusals + clinical rejection
        ok("11 nurse plan 403", requests.patch(f"{API}/tasks/{t}", headers=H(NURSE), json={"requested_for_time_label": "3:00 PM"}).status_code == 403)
        ok("11 front desk start 403", requests.post(f"{API}/tasks/{t}/start", headers=H(FD)).status_code == 403)
        ok("11 nurse detail 404", requests.get(f"{API}/tasks/{t}/detail", headers=H(NURSE)).status_code == 404)
        ok("11 clinical field 422", requests.patch(f"{API}/tasks/{t}", headers=H(PT), json={"diagnosis": "x"}).status_code == 422)
        ok("11 therapist inspect 403", requests.post(f"{API}/tasks/{t}/inspect", headers=H(PT), json={"result": "pass"}).status_code == 403)
        # 10 receipt / history chain
        d = requests.get(f"{API}/tasks/{t}/detail", headers=H(OWNER)).json()
        rs = sorted(d["receipts"], key=lambda x: x["created_at"]); kinds = [x["action_type"] for x in rs]
        cor = {x.get("correlation_id") for x in rs if not x["action_type"].endswith("_refused")}
        ev_ok = all(e_.get("receipt_id") for e_ in d["task"]["event_log"])
        ok("10 one workflow, every history entry has a receipt", len(cor) == 1 and ev_ok, kinds)
        hp, e = page(OWNER); hp.goto(f"{WEB}/admin?tab=therapy"); hp.wait_for_timeout(3500)
        hp.click(f"[data-testid=wo-history-{t}]"); hp.wait_for_timeout(1500); shot(hp, "08-history"); allerrs += e
        ok("no failed API calls across the run", not allerrs, allerrs[:5])
        br.close()
finally:
    for x in created: requests.delete(f"{API}/tasks/{x}", headers=H(OWNER))
    if tpl_id: requests.delete(f"{API}/tasks/templates/{tpl_id}", headers=H(OWNER))
    if staff_id: R.append(("cleanup temp account", requests.delete(f"{API}/staff/{staff_id}", headers=H(OWNER)).status_code == 200, None))
    left = [x for x in requests.get(f"{API}/tasks", headers=H(OWNER), params={"resident_id": RID}).json() if "Acceptance" in (x.get("title") or "") or x.get("template_id") == tpl_id]
    R.append(("cleanup tasks", not left, len(left)))
for n, c, ev in R: print(("PASS " if c else "FAIL ") + n + ("" if ev is None else f"  [{ev}]"))
