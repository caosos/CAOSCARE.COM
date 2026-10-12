import json, os, sys, time, requests
from datetime import datetime, timezone
from pymongo import MongoClient
from playwright.sync_api import sync_playwright
sys.path.insert(0, "/home/caoscare-1/CAOSCARE-INTEGRATION/backend"); os.chdir("/home/caoscare-1/CAOSCARE-INTEGRATION/backend")
from dotenv import load_dotenv; load_dotenv(".env")
from routes.auth import _issue_jwt
SCR = "/tmp/claude-1000/-home-caoscare-1/65cd8277-4ae2-4662-b884-d9db0ebd139d/scratchpad"
BASE = "http://localhost:3000"; API = "http://127.0.0.1:8092/api"
db = MongoClient("mongodb://localhost:27017")["caoscare"]
RID = "res_a26499ca719a"; KIOSK = db.kiosks.find_one({"room": "3W03"})["kiosk_id"]; PHONE = "+15550101234"
assert db.escalation_rules.count_documents({}) == 0 and db.alerts.count_documents({"resident_id": RID, "status": {"$ne": "resolved"}}) == 0
T0 = datetime.now(timezone.utc).isoformat()
OW = _issue_jwt(db.users.find_one({"role": "owner"})["user_id"])
login = lambda e: requests.post(f"{API}/auth/login", json={"email": e, "password": "demo-pass-1234"}, timeout=5).json()["token"]
FD, NU = login("dana.frost@demo.caoscare"), login("nancy.reyes@demo.caoscare")
H = lambda t: {"Authorization": f"Bearer {t}"}
results, failed = [], []; AID = None
def case(n, ok, note=""): results.append((n, bool(ok), str(note))); print(("PASS " if ok else "FAIL ") + n + (f"  [{note}]" if note else ""))
def ctx(b, token, w, h):
    c = b.new_context(viewport={"width": w, "height": h}); c.add_init_script(f"window.localStorage.setItem('caos_token', {json.dumps(token)});")
    pg = c.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("response", lambda r: failed.append((r.url, r.status)) if "/api/" in r.url and r.status >= 400 else None)
    return c, pg, errs
try:
    r = requests.put(f"{API}/escalation/rule", headers=H(OW), json={"level_2_seconds": 20, "level_3_seconds": 600, "notify_supervisor_phone": PHONE, "enabled": True}, timeout=5)
    case("temporary policy with a fictional supervisor phone (no SMS provider on dev)", r.status_code == 200)
    AID = requests.post(f"{API}/alerts", json={"kiosk_id": KIOSK, "resident_id": RID, "severity": "emergency", "message": "SYNTHETIC delivery-exceptions acceptance", "triggered_by": "kiosk_button"}, timeout=10).json()["alert_id"]
    for _ in range(70):
        if db.notifications.count_documents({"alert_id": AID, "channel": "sms"}): break
        time.sleep(1)
    notes = list(db.notifications.find({"alert_id": AID}, {"_id": 0, "notification_id": 1, "channel": 1, "status": 1, "related_object_type": 1, "receipt_id": 1}))
    case("real paths wrote a family email and a supervisor SMS, both 'logged' (not sent)", {n["channel"] for n in notes} >= {"email", "sms"} and all(n["status"] == "logged" for n in notes), notes)
    api = requests.get(f"{API}/ops/delivery-exceptions", headers=H(FD), timeout=5).json()
    mine = [i for i in api["items"] if i["alert_id"] == AID]
    raw = json.dumps(mine)
    case("desk API lists both, redacted (no message text, no full address/number)", len(mine) == len(notes) and "SYNTHETIC" not in raw and "family.3W03@demo.caoscare" not in raw and PHONE not in raw and "Staff have been paged" not in raw, [(i["recipient"], i["label"]) for i in mine])
    fam = next(i for i in mine if i["channel"] == "email"); sms = next(i for i in mine if i["channel"] == "sms")
    case("labels: family relationship; supervisor phone; honest 'not sent'", fam["recipient"] == "Family: Betty's daughter (daughter)" and sms["recipient"] == "Supervisor phone ending 1234" and all(i["state"] == "not_sent" and "no message provider" in i["label"] for i in mine))
    case("SMS row links its delivery receipt (alert_sms_attempt)", db.receipts.find_one({"receipt_id": sms["receipt_id"]}, {"action_type": 1})["action_type"] == "alert_sms_attempt", sms["receipt_id"])
    own = requests.get(f"{API}/ops/delivery-exceptions", headers=H(OW), timeout=5).json()
    case("owner sees the same rows; owner full log still has raw detail", [i["notification_id"] for i in own["items"]] == [i["notification_id"] for i in api["items"]] and any(n.get("to") == PHONE for n in requests.get(f"{API}/notifications", headers=H(OW), params={"limit": 100}, timeout=5).json()))
    case("refusals: nurse 403, anonymous 401, desk full log 403", requests.get(f"{API}/ops/delivery-exceptions", headers=H(NU), timeout=5).status_code == 403 and requests.get(f"{API}/ops/delivery-exceptions", timeout=5).status_code == 401 and requests.get(f"{API}/notifications", headers=H(FD), timeout=5).status_code == 403)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        c, pg, errs = ctx(b, FD, 1280, 900); pg.goto(f"{BASE}/front-desk"); pg.wait_for_selector("[data-testid=fd-tab-attention]", timeout=60000)
        pg.click("[data-testid=fd-tab-attention]"); pg.wait_for_selector(f"[data-testid=dx-row-{fam['notification_id']}]", timeout=20000); time.sleep(1)
        ui = pg.evaluate("[...document.querySelectorAll('[data-testid^=dx-row-]')].length"); txt = pg.inner_text(f"[data-testid=dx-row-{sms['notification_id']}]")
        case("desk 1280: rows = API rows; SMS row readable", ui == len(api["items"]) and "Supervisor phone ending 1234" in txt and "Betty" in txt and "emergency alert" in txt, txt.replace("\n", " | "))
        pg.locator("[data-testid=delivery-exceptions]").scroll_into_view_if_needed(); pg.screenshot(path=f"{SCR}/dx_shots/01_desk_1280.png", full_page=True)
        pg.click(f"[data-testid=dx-open-{sms['notification_id']}]"); pg.wait_for_selector("[data-testid=alert-detail-dialog]", timeout=20000); time.sleep(1)
        case("Open alert opens the real alert", "Betty" in pg.inner_text("[data-testid=alert-detail-dialog]"), pg.url)
        pg.screenshot(path=f"{SCR}/dx_shots/02_open_alert.png"); case("desk 1280: no page errors", not errs, errs[:2]); c.close()
        c, pg, errs = ctx(b, FD, 390, 844); pg.goto(f"{BASE}/front-desk"); pg.wait_for_selector("[data-testid=fd-tab-attention]", timeout=60000)
        pg.click("[data-testid=fd-tab-attention]"); pg.wait_for_selector(f"[data-testid=dx-row-{fam['notification_id']}]", timeout=20000); time.sleep(1)
        sw = pg.evaluate("document.documentElement.scrollWidth"); case("desk 390 px: no horizontal overflow, no page errors", sw <= 390 and not errs, f"sw={sw} {errs[:1]}")
        pg.screenshot(path=f"{SCR}/dx_shots/03_desk_390.png", full_page=True); c.close(); b.close()
finally:
    rr = [x["receipt_id"] for x in db.receipts.find({"related_object_type": "escalation_rule", "created_at": {"$gte": T0}}, {"receipt_id": 1})]
    db.escalation_rules.delete_many({"facility_id": None})
    if AID:
        out = {"alert": db.alerts.delete_many({"alert_id": AID}).deleted_count,
               "receipts": db.receipts.delete_many({"$or": [{"related_object_id": AID}, {"receipt_id": {"$in": rr}}]}).deleted_count,
               "notifications": db.notifications.delete_many({"$or": [{"alert_id": AID}, {"related_object_id": AID}]}).deleted_count,
               "dispatches": db.staff_dispatches.delete_many({"alert_id": AID}).deleted_count}
        print("cleanup:", out, "rules left", db.escalation_rules.count_documents({}), "open for resident", db.alerts.count_documents({"resident_id": RID, "status": {"$ne": "resolved"}}))
print(f"\n{sum(1 for r in results if r[1])}/{len(results)} passed; failed API calls: {len(failed)}"); [print("  API", f) for f in failed]
sys.exit(0 if all(r[1] for r in results) else 1)
