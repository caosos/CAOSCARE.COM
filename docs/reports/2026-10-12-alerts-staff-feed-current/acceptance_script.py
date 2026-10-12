import json, os, sys, time, requests
from pymongo import MongoClient
from playwright.sync_api import sync_playwright
sys.path.insert(0, "/home/caoscare-1/CAOSCARE-INTEGRATION/backend"); os.chdir("/home/caoscare-1/CAOSCARE-INTEGRATION/backend")
from dotenv import load_dotenv; load_dotenv(".env")
from routes.auth import _issue_jwt
SCR = "/tmp/claude-1000/-home-caoscare-1/65cd8277-4ae2-4662-b884-d9db0ebd139d/scratchpad"
BASE = "http://localhost:3000"; API = "http://127.0.0.1:8092/api"
db = MongoClient("mongodb://localhost:27017")["caoscare"]
RID, ROOM = "res_a26499ca719a", "3W03"; KIOSK = db.kiosks.find_one({"room": ROOM})["kiosk_id"]
assert db.alerts.count_documents({"resident_id": RID, "status": {"$ne": "resolved"}}) == 0
OW = _issue_jwt(db.users.find_one({"role": "owner"})["user_id"])
login = lambda e: requests.post(f"{API}/auth/login", json={"email": e, "password": "demo-pass-1234"}, timeout=5).json()["token"]
NU, FD = login("nancy.reyes@demo.caoscare"), login("dana.frost@demo.caoscare")
nurse_id = db.users.find_one({"email": "nancy.reyes@demo.caoscare"})["user_id"]
H = lambda t: {"Authorization": f"Bearer {t}"}
results, failed = [], []
def case(n, ok, note=""): results.append((n, bool(ok), str(note))); print(("PASS " if ok else "FAIL ") + n + (f"  [{note}]" if note else ""))
def ctx(b, token, w, h):
    c = b.new_context(viewport={"width": w, "height": h}); c.add_init_script(f"window.localStorage.setItem('caos_token', {json.dumps(token)});")
    pg = c.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("response", lambda r: failed.append((r.url, r.status)) if "/api/" in r.url and r.status >= 400 else None)
    return c, pg, errs
cur = requests.get(f"{API}/alerts/feed", headers=H(NU), timeout=5).json(); old = requests.get(f"{API}/alerts/feed", headers=H(NU), params={"scope": "older"}, timeout=5).json()
stats = requests.get(f"{API}/alerts/stats", headers=H(NU), timeout=5).json()
open_total = db.alerts.count_documents({"status": {"$in": ["active", "acknowledged", "escalated"]}})
case("API: current + older_open = all open alerts; older list newest-first, capped at 200", len(cur) + stats["older_open"] == open_total and len(old) == min(200, stats["older_open"]), f"current={len(cur)} older={len(old)} older_open={stats['older_open']} open={open_total}")
case("anonymous feed / older feed refused (401)", requests.get(f"{API}/alerts/feed", timeout=5).status_code == 401 and requests.get(f"{API}/alerts/feed", params={"scope": "older"}, timeout=5).status_code == 401)
AID = None
try:
    r = requests.post(f"{API}/alerts", json={"kiosk_id": KIOSK, "resident_id": RID, "severity": "assist", "message": "SYNTHETIC staff-feed acceptance", "triggered_by": "kiosk_button"}, timeout=10)
    AID = r.json()["alert_id"]
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        c, pg, errs = ctx(b, NU, 390, 844); pg.goto(f"{BASE}/staff"); pg.wait_for_selector(f"[data-testid=ack-btn-{AID}]", timeout=60000); time.sleep(1)
        cards = pg.evaluate("document.querySelectorAll('[data-testid^=alert-card-]').length"); hgt = pg.evaluate("document.documentElement.scrollHeight"); sw = pg.evaluate("document.documentElement.scrollWidth")
        first = pg.evaluate("document.querySelector('[data-testid=alerts-list]').firstElementChild.getAttribute('data-testid')")
        banner = pg.inner_text("[data-testid=alerts-older-banner]")
        case("nurse 390: only current alerts listed, new alert first", cards == len(cur) + 1 and first == f"alert-card-{AID}", f"cards={cards} first={first}")
        case("nurse 390: page height reasonable, no overflow", hgt < 8000 and sw <= 390, f"height={hgt} (was ~87,112) scrollWidth={sw}")
        case("nurse 390: banner counts older alerts and says nothing was closed", str(stats["older_open"]) in banner and "Nothing was closed" in banner, banner.replace("\n", " "))
        pg.screenshot(path=f"{SCR}/sf_shots/01_nurse_390_current.png", full_page=True)
        pg.click(f"[data-testid=ack-btn-{AID}]"); time.sleep(2)
        a = db.alerts.find_one({"alert_id": AID}); ack = db.receipts.find_one({"related_object_id": AID, "action_type": "alert_acknowledged"})
        case("nurse 390: new alert acknowledged with receipt", a["status"] == "acknowledged" and ack and ack["actor_id"] == nurse_id, ack and ack["receipt_id"])
        pg.click("[data-testid=alerts-older-toggle]"); time.sleep(4)
        older_cards = pg.evaluate("document.querySelectorAll('[data-testid^=alert-older-]').length")
        b2 = pg.inner_text("[data-testid=alerts-older-banner]")
        case("Show older: older alerts appear marked 'older'; banner states shown of total", older_cards == len(old) and f"Showing {len(old)} of {stats['older_open']}" in b2, f"older cards={older_cards} | {b2[:90]}")
        pg.click("[data-testid=alerts-older-toggle]"); time.sleep(4)
        case("Hide older returns to the current list", pg.evaluate("document.querySelectorAll('[data-testid^=alert-older-]').length") == 0)
        case("nurse: no page errors", not errs, errs[:2]); c.close()
        c, pg, errs = ctx(b, OW, 1280, 900); pg.goto(f"{BASE}/alerts"); pg.wait_for_selector("[data-testid=alerts-counts]", timeout=60000); time.sleep(1)
        counts = pg.inner_text("[data-testid=alerts-counts]")
        case("owner /alerts board unchanged (current/older counts still shown)", "current open" in counts and "older needing review" in counts, counts)
        pg.screenshot(path=f"{SCR}/sf_shots/02_owner_board_1280.png"); c.close()
        c, pg, errs = ctx(b, OW, 1280, 900); pg.goto(f"{BASE}/staff"); pg.wait_for_selector("[data-testid=alerts-older-banner]", timeout=60000); time.sleep(1)
        pg.screenshot(path=f"{SCR}/sf_shots/03_owner_staff_1280.png"); case("owner /staff desktop: banner + current list", pg.is_visible(f"[data-testid=alert-card-{AID}]"), ""); c.close(); b.close()
finally:
    if AID:
        n_r = db.receipts.delete_many({"related_object_id": AID}).deleted_count
        n_n = db.notifications.delete_many({"$or": [{"alert_id": AID}, {"related_object_id": AID}]}).deleted_count
        n_d = db.staff_dispatches.delete_many({"alert_id": AID}).deleted_count
        n_a = db.alerts.delete_many({"alert_id": AID}).deleted_count
        print(f"cleanup: alert {n_a}, receipts {n_r}, notifications {n_n}, dispatches {n_d}; open for resident {db.alerts.count_documents({'resident_id': RID, 'status': {'$ne': 'resolved'}})}; open total {db.alerts.count_documents({'status': {'$in': ['active','acknowledged','escalated']}})}")
print(f"\n{sum(1 for r in results if r[1])}/{len(results)} passed; failed API calls: {len(failed)}"); [print("  API", f) for f in failed]
sys.exit(0 if all(r[1] for r in results) else 1)
