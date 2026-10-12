import json, sys, time, requests
from datetime import datetime, timezone
from pymongo import MongoClient
from playwright.sync_api import sync_playwright
SCR = "/tmp/claude-1000/-home-caoscare-1/65cd8277-4ae2-4662-b884-d9db0ebd139d/scratchpad"
BASE = "http://localhost:3000"; API = "http://127.0.0.1:8092/api"
db = MongoClient("mongodb://localhost:27017")["caoscare"]
RID = "res_a26499ca719a"; T0 = datetime.now(timezone.utc).isoformat()
login = lambda e: requests.post(f"{API}/auth/login", json={"email": e, "password": "demo-pass-1234"}, timeout=5).json()["token"]
FD, NU = login("dana.frost@demo.caoscare"), login("nancy.reyes@demo.caoscare")
H = lambda t: {"Authorization": f"Bearer {t}"}
results, failed = [], []; TID = None
def case(n, ok, note=""): results.append((n, bool(ok), str(note))); print(("PASS " if ok else "FAIL ") + n + (f"  [{note}]" if note else ""))
def ctx(b, token, w, h):
    c = b.new_context(viewport={"width": w, "height": h}); c.add_init_script(f"window.localStorage.setItem('caos_token', {json.dumps(token)});")
    pg = c.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "422" not in m.text else None)
    pg.on("response", lambda r: failed.append((r.url, r.status)) if "/api/" in r.url and r.status >= 400 and r.status != 422 else None)
    return c, pg, errs
try:
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        c, pg, errs = ctx(b, FD, 1280, 900); pg.goto(f"{BASE}/front-desk"); pg.wait_for_selector("[data-testid=fd-new-request-btn]", timeout=60000)
        pg.click("[data-testid=fd-new-request-btn]"); pg.wait_for_selector("[data-testid=fd-request-resident]")
        pg.click("[data-testid=fd-request-resident]"); pg.get_by_role("option", name="Demo - Betty Owusu · Room 3W03").click()
        pg.fill("[data-testid=fd-request-summary]", "SYNTHETIC callback about the September bill")
        pg.fill("[data-testid=fd-request-callback-phone]", "12")
        with pg.expect_response(lambda r: "resident-request" in r.url and r.request.method == "POST") as rr: pg.click("[data-testid=fd-request-save]")
        time.sleep(0.5)
        case("invalid callback phone refused (422) with a readable reason; nothing created", rr.value.status == 422 and pg.locator("text=Callback phone needs 7 to 15 digits.").count() > 0 and db.staff_tasks.count_documents({"resident_id": RID, "created_at": {"$gte": T0}}) == 0)
        pg.fill("[data-testid=fd-request-callback-phone]", "(555) 010-4321"); pg.fill("[data-testid=fd-request-callback-window]", "after 2 pm")
        pg.screenshot(path=f"{SCR}/cb_shots/01_new_request_form.png")
        with pg.expect_response(lambda r: "resident-request" in r.url and r.request.method == "POST") as rr: pg.click("[data-testid=fd-request-save]")
        TID = rr.value.json().get("task_id"); t = db.staff_tasks.find_one({"task_id": TID}) or {}
        case("desk creates the callback; phone normalized, best time stored", rr.value.status == 200 and t.get("callback_phone") == "+15550104321" and t.get("callback_window") == "after 2 pm", TID)
        time.sleep(1); pg.click("[data-testid=fd-tab-attention]"); pg.wait_for_selector(f"[data-testid=rx-open-{TID}]", timeout=20000)
        pg.click(f"[data-testid=rx-open-{TID}]"); pg.wait_for_selector("[data-testid=callback-editor]", timeout=10000); time.sleep(0.5)
        case("detail shows the staff-only Call back section with the number", pg.input_value("[data-testid=callback-phone]") == "+15550104321" and "staff only" in pg.inner_text("[data-testid=callback-editor]").lower(), (pg.input_value("[data-testid=callback-phone]"), pg.inner_text("[data-testid=callback-editor]")[:60]))
        pg.fill("[data-testid=callback-window]", "tomorrow morning"); pg.click("[data-testid=callback-save]"); time.sleep(1.5)
        t = db.staff_tasks.find_one({"task_id": TID}); rc = db.receipts.find_one({"related_object_id": TID, "action_type": "task_details_updated"})
        case("edit saved and receipted (acts_for:administration)", t["callback_window"] == "tomorrow morning" and rc and rc["authority"] == "acts_for:administration", rc and rc["receipt_id"])
        pg.screenshot(path=f"{SCR}/cb_shots/02_detail_callback_1280.png"); pg.keyboard.press("Escape")
        case("desk 1280: no page errors", not errs, errs[:2]); c.close()
        c, pg, errs = ctx(b, FD, 390, 844); pg.goto(f"{BASE}/front-desk"); pg.wait_for_selector("[data-testid=fd-tab-attention]", timeout=60000)
        pg.click("[data-testid=fd-tab-attention]"); pg.wait_for_selector(f"[data-testid=rx-open-{TID}]", timeout=20000); pg.click(f"[data-testid=rx-open-{TID}]")
        pg.wait_for_selector("[data-testid=callback-editor]", timeout=10000); time.sleep(0.5)
        sw = pg.evaluate("document.documentElement.scrollWidth"); case("desk 390 px: callback section usable, no overflow, no errors", sw <= 390 and pg.is_visible("[data-testid=callback-save]") and not errs, f"sw={sw}")
        pg.screenshot(path=f"{SCR}/cb_shots/03_detail_callback_390.png"); c.close(); b.close()
    s = requests.get(f"{API}/tasks/resident-request/status", params={"resident_id": RID, "category": "administration"}, timeout=5).json()
    case("resident/Aria status never carries the phone or time", s.get("found") and "0104321" not in json.dumps(s) and "tomorrow morning" not in json.dumps(s) and "callback_phone" not in s, list(s)[:6])
    case("nurse cannot edit (403); no call claimed", requests.patch(f"{API}/tasks/{TID}", headers=H(NU), json={"callback_window": "now"}, timeout=5).status_code == 403 and db.receipts.count_documents({"related_object_id": TID, "action_type": {"$regex": "^call\\."}}) == 0)
finally:
    if TID:
        n = {"tasks": db.staff_tasks.delete_many({"task_id": TID}).deleted_count, "receipts": db.receipts.delete_many({"related_object_id": TID}).deleted_count,
             "notifications": db.notifications.delete_many({"related_object_id": TID}).deleted_count}
        print("cleanup:", n, "open for resident:", db.staff_tasks.count_documents({"resident_id": RID, "status": {"$in": ["pending", "in_progress"]}}))
print(f"\n{sum(1 for r in results if r[1])}/{len(results)} passed; failed API calls (excluding the deliberate 422): {len(failed)}"); [print("  API", f) for f in failed]
sys.exit(0 if all(r[1] for r in results) else 1)
