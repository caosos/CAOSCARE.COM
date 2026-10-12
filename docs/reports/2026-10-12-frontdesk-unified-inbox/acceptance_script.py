import json, os, sys, time, requests
from pymongo import MongoClient
from playwright.sync_api import sync_playwright
sys.path.insert(0, "/home/caoscare-1/CAOSCARE-INTEGRATION/backend"); os.chdir("/home/caoscare-1/CAOSCARE-INTEGRATION/backend")
from dotenv import load_dotenv; load_dotenv(".env")
from routes.auth import _issue_jwt
SCR = "/tmp/claude-1000/-home-caoscare-1/65cd8277-4ae2-4662-b884-d9db0ebd139d/scratchpad"
BASE = "http://localhost:3000"; API = "http://127.0.0.1:8092/api"
db = MongoClient("mongodb://localhost:27017")["caoscare"]
RID = "res_a26499ca719a"
OW = _issue_jwt(db.users.find_one({"role": "owner"})["user_id"])
login = lambda e: requests.post(f"{API}/auth/login", json={"email": e, "password": "demo-pass-1234"}, timeout=5).json()["token"]
FD, NU = login("dana.frost@demo.caoscare"), login("nancy.reyes@demo.caoscare")
fd_id = db.users.find_one({"email": "dana.frost@demo.caoscare"})["user_id"]
H = lambda t: {"Authorization": f"Bearer {t}"}
results, failed, tids = [], [], []
def case(n, ok, note=""): results.append((n, bool(ok), str(note))); print(("PASS " if ok else "FAIL ") + n + (f"  [{note}]" if note else ""))
def ctx(b, token, w, h):
    c = b.new_context(viewport={"width": w, "height": h}); c.add_init_script(f"window.localStorage.setItem('caos_token', {json.dumps(token)});")
    pg = c.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("response", lambda r: failed.append((r.url, r.status)) if "/api/" in r.url and r.status >= 400 else None)
    return c, pg, errs
try:
    cb = requests.post(f"{API}/tasks/resident-request", headers=H(FD), json={"category": "front_desk", "resident_id": RID, "source": "front_desk",
          "summary": "SYNTHETIC callback about the September bill", "resident_words": "Please call me back about my bill"}, timeout=10).json()["task_id"]
    nur = requests.post(f"{API}/tasks/resident-request", json={"category": "nursing", "resident_id": RID, "room": "3W03", "source": "aria_voice",
          "summary": "SYNTHETIC need help to the bathroom"}, timeout=10).json()["task_id"]
    tids = [cb, nur]
    t = db.staff_tasks.find_one({"task_id": cb}); case("callback request created by front desk in Administration", t["visibility_role"] == "administration", f"{cb} simulated={t.get('simulated')}")
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        c, pg, errs = ctx(b, FD, 1280, 900); pg.goto(f"{BASE}/front-desk"); pg.wait_for_selector("[data-testid=fd-tab-attention]", timeout=60000)
        pg.click("[data-testid=fd-tab-attention]"); pg.wait_for_selector(f"[data-testid=rx-row-{cb}]", timeout=20000); time.sleep(1)
        rows = pg.evaluate("[...document.querySelectorAll('[data-testid^=rx-row-]')].map(e=>e.dataset.testid.slice(7))")
        depts = set(pg.evaluate("[...document.querySelectorAll('[data-testid^=rx-row-] .uppercase')].map(e=>e.textContent.trim().toLowerCase())"))
        api_items = requests.get(f"{API}/ops/routing-exceptions", headers=H(FD), timeout=5).json()
        case("desk 1280: Needs attention lists the callback, not the nursing request; rows = API", cb in rows and nur not in rows and len(rows) == len(api_items["items"]), f"rows={len(rows)} api={len(api_items['items'])}")
        case("desk sees only Administration-scoped rows", {i["department"] for i in api_items["items"]} <= {"administration", "all_staff"}, {i["department"] for i in api_items["items"]})
        txt = pg.inner_text(f"[data-testid=rx-row-{cb}]"); case("row shows what, resident, unassigned, delivery truth", "call me back" in txt.lower() and "Betty" in txt and "no owner" in txt and "Not delivered" in txt, txt.replace("\n", " | ")[:160])
        pg.screenshot(path=f"{SCR}/fd_shots/01_desk_attention_1280.png", full_page=True)
        rn = pg.locator(f"[data-testid=rx-renotify-{cb}]")
        if rn.count():
            rn.click(); time.sleep(2)
            r = db.receipts.find_one({"related_object_id": cb, "action_type": "department_renotified"})
            case("Re-send from the desk writes a receipt (acts_for:administration), no delivery claimed", r and r["actor_id"] == fd_id and r["authority"] == "acts_for:administration" and db.notifications.count_documents({"related_object_id": cb, "status": {"$in": ["sent", "delivered"]}}) == 0, r and r["receipt_id"])
        else:
            case("Re-send shown for an undelivered, non-simulated row", False, "button absent")
        pg.click(f"[data-testid=rx-open-{cb}]"); pg.wait_for_selector("[data-testid=request-detail-dialog]", timeout=10000); time.sleep(1)
        case("Open shows the real request record", "callback" in pg.inner_text("[data-testid=request-detail-dialog]").lower())
        pg.screenshot(path=f"{SCR}/fd_shots/02_desk_open_record.png"); pg.keyboard.press("Escape")
        case("desk 1280: no page errors", not errs, errs[:2]); c.close()
        c, pg, errs = ctx(b, FD, 390, 844); pg.goto(f"{BASE}/front-desk"); pg.wait_for_selector("[data-testid=fd-tab-attention]", timeout=60000)
        pg.click("[data-testid=fd-tab-attention]"); pg.wait_for_selector(f"[data-testid=rx-row-{cb}]", timeout=20000); time.sleep(1)
        sw = pg.evaluate("document.documentElement.scrollWidth"); case("desk 390 px: no horizontal overflow", sw <= 390, f"sw={sw}")
        pg.screenshot(path=f"{SCR}/fd_shots/03_desk_attention_390.png", full_page=True); case("desk 390: no page errors", not errs, errs[:2]); c.close(); b.close()
    codes = {"desk renotify nursing": requests.post(f"{API}/ops/routing-exceptions/{nur}/renotify", headers=H(FD), timeout=5).status_code,
             "anon list": requests.get(f"{API}/ops/routing-exceptions", timeout=5).status_code,
             "desk notification log": requests.get(f"{API}/notifications", headers=H(FD), timeout=5).status_code}
    case("refusals: desk re-send of nursing 403/404, anonymous 401, desk notification log 403 (unchanged)", codes["desk renotify nursing"] in (403, 404) and codes["anon list"] == 401 and codes["desk notification log"] == 403 and db.receipts.count_documents({"related_object_id": nur, "action_type": "department_renotified"}) == 0, codes)
    allx = {i["task_id"] for i in requests.get(f"{API}/ops/routing-exceptions", headers=H(OW), timeout=5).json()["items"]}
    case("owner (API) sees both requests", {cb, nur} <= allx)
finally:
    n = {k: getattr(db, k).delete_many({"task_id" if k == "staff_tasks" else "related_object_id": {"$in": tids}}).deleted_count for k in ("staff_tasks", "receipts", "notifications")}
    print("cleanup:", n, "open for resident:", db.staff_tasks.count_documents({"resident_id": RID, "status": {"$in": ["pending", "in_progress"]}}))
print(f"\n{sum(1 for r in results if r[1])}/{len(results)} passed; failed API calls: {len(failed)}"); [print("  API", f) for f in failed]
sys.exit(0 if all(r[1] for r in results) else 1)
