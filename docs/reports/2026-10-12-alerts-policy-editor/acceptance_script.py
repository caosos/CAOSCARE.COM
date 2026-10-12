import json, os, sys, time, uuid, requests
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from playwright.sync_api import sync_playwright
sys.path.insert(0, "/home/caoscare-1/CAOSCARE-INTEGRATION/backend")
os.chdir("/home/caoscare-1/CAOSCARE-INTEGRATION/backend")
from dotenv import load_dotenv; load_dotenv(".env")
from routes.auth import _issue_jwt
SCR = "/tmp/claude-1000/-home-caoscare-1/65cd8277-4ae2-4662-b884-d9db0ebd139d/scratchpad"
BASE = "http://localhost:3000"; API = "http://127.0.0.1:8092/api"
db = MongoClient("mongodb://localhost:27017")["caoscare"]
TAG = f"polacc_{uuid.uuid4().hex[:6]}"
assert db.escalation_rules.count_documents({}) == 0, "dev already has a stored rule; refusing to edit it"
owner = db.users.find_one({"role": "owner"}, {"_id": 0, "user_id": 1})
OW = _issue_jwt(owner["user_id"])
NU = requests.post(f"{API}/auth/login", json={"email": "nancy.reyes@demo.caoscare", "password": "demo-pass-1234"}, timeout=5).json()["token"]
FD = requests.post(f"{API}/auth/login", json={"email": "dana.frost@demo.caoscare", "password": "demo-pass-1234"}, timeout=5).json()["token"]
H = lambda t: {"Authorization": f"Bearer {t}"}
results, failed = [], []
def case(n, ok, note=""): results.append((n, bool(ok), note)); print(("PASS " if ok else "FAIL ") + n + (f"  [{note}]" if note else ""))
def ctx(b, token, w=1280, h=900):
    c = b.new_context(viewport={"width": w, "height": h}); c.add_init_script(f"window.localStorage.setItem('caos_token', {json.dumps(token)});")
    pg = c.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("response", lambda r: failed.append((r.url, r.status)) if "/api/" in r.url and r.status >= 400 and "escalation/rule" not in r.url else None)
    return c, pg, errs
def fill(pg, tid, v): pg.fill(f"[data-testid={tid}]", str(v))
AID = f"{TAG}_alert"
try:
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        c, pg, errs = ctx(b, OW); pg.goto(f"{BASE}/admin?tab=escalation"); pg.wait_for_selector("[data-testid=escalation-tab]", timeout=60000)
        case("desktop: editor shows safe defaults 90 / 150", pg.input_value("[data-testid=esc-l2-seconds]") == "90" and pg.input_value("[data-testid=esc-l3-seconds]") == "150")
        pg.screenshot(path=f"{SCR}/pol_shots/01_defaults_desktop.png", full_page=True)
        fill(pg, "esc-l2-seconds", 20); fill(pg, "esc-l3-seconds", 10)
        with pg.expect_response(lambda r: "escalation/rule" in r.url and r.request.method == "PUT") as rr: pg.click("[data-testid=esc-save]")
        pg.wait_for_selector("text=Level 3 must come later than Level 2.", timeout=5000)
        case("invalid edit refused (422) with a readable reason, nothing stored", rr.value.status == 422 and db.escalation_rules.count_documents({}) == 0)
        pg.screenshot(path=f"{SCR}/pol_shots/02_invalid_refused.png", full_page=True)
        fill(pg, "esc-l3-seconds", 40)
        with pg.expect_response(lambda r: "escalation/rule" in r.url and r.request.method == "PUT") as rr: pg.click("[data-testid=esc-save]")
        pg.wait_for_selector("[data-testid=esc-last-change]", timeout=5000)
        rule = db.escalation_rules.find_one({"facility_id": None}, {"_id": 0})
        rc = db.receipts.find_one({"receipt_id": rule["receipt_id"]}, {"_id": 0})
        case("owner edit saved, rule links its receipt", rr.value.status == 200 and rule["level_2_seconds"] == 20 and rc is not None, rule["receipt_id"])
        case("receipt provenance: actor, authority, before (defaults) / after", rc["action_type"] == "escalation_rule_changed" and rc["actor_id"] == owner["user_id"] and rc["actor_type"] == "real-human" and rc["authority"] == "policy_editor:owner" and rc["before_state"]["source"] == "defaults" and rc["before_state"]["level_2_seconds"] == 90 and rc["after_state"]["level_3_seconds"] == 40, json.dumps({k: rc.get(k) for k in ("authority", "before_state", "after_state")})[:200])
        pg.screenshot(path=f"{SCR}/pol_shots/03_saved_desktop.png", full_page=True)
        case("desktop: no page errors", not errs, "; ".join(errs)[:150]); c.close()
        # runtime: a synthetic alert 25 s old; the existing background tick (30 s) applies the edited policy
        db.alerts.insert_one({"alert_id": AID, "room": f"{TAG}-R", "severity": "assist", "status": "active", "escalation_level": 0,
                              "event_log": [], "message": "SYNTHETIC policy acceptance", "simulated": True,
                              "created_at": (datetime.now(timezone.utc) - timedelta(seconds=25)).isoformat()})
        lvl = 0
        for _ in range(45):
            lvl = (db.alerts.find_one({"alert_id": AID}) or {}).get("escalation_level") or 0
            if lvl >= 2: break
            time.sleep(1)
        esc = db.receipts.find_one({"related_object_id": AID, "action_type": "alert_escalated"}, {"_id": 0})
        case("existing background tick escalated the synthetic alert under the edited policy", lvl >= 2 and esc and esc["after_state"]["thresholds"] == {"level_2_seconds": 20, "level_3_seconds": 40}, f"level={lvl} src={(db.alerts.find_one({'alert_id': AID}) or {}).get('escalation_source')}")
        for who, t in (("nurse", NU), ("front desk", FD)):
            case(f"{who}: read/edit/tick refused (403)", all(s == 403 for s in (
                requests.get(f"{API}/escalation/rule", headers=H(t), timeout=5).status_code,
                requests.put(f"{API}/escalation/rule", headers=H(t), json={"level_2_seconds": 5, "level_3_seconds": 6}, timeout=5).status_code,
                requests.post(f"{API}/escalation/tick", headers=H(t), timeout=5).status_code)))
        case("refused edits changed nothing", db.escalation_rules.find_one({"facility_id": None})["level_2_seconds"] == 20)
        c, pg, errs = ctx(b, OW, 390, 844); pg.goto(f"{BASE}/admin?tab=escalation"); pg.wait_for_selector("[data-testid=escalation-tab]", timeout=60000); time.sleep(0.5)
        sw = pg.evaluate("document.documentElement.scrollWidth")
        case("390 px: editor shows the stored 20 / 40 and last change, no overflow", pg.input_value("[data-testid=esc-l2-seconds]") == "20" and pg.is_visible("[data-testid=esc-last-change]") and sw <= 390, f"scrollWidth={sw}")
        pg.screenshot(path=f"{SCR}/pol_shots/04_editor_390.png", full_page=True)
        case("390 px: no page errors", not errs, "; ".join(errs)[:150]); c.close()
        c, pg, errs = ctx(b, NU, 390, 844); pg.goto(f"{BASE}/admin?tab=escalation"); time.sleep(4)
        case("nurse at 390 px: escalation editor not shown", pg.locator("[data-testid=escalation-tab]").count() == 0, pg.url)
        pg.screenshot(path=f"{SCR}/pol_shots/05_nurse_390.png"); c.close(); b.close()
finally:
    rule = db.escalation_rules.find_one({"facility_id": None}, {"_id": 0}) or {}
    rids = [r["receipt_id"] for r in db.receipts.find({"related_object_type": "escalation_rule", "related_object_id": "default", "actor_id": owner["user_id"]}, {"receipt_id": 1})]
    db.escalation_rules.delete_many({"facility_id": None})
    db.alerts.delete_many({"alert_id": AID})
    n = db.receipts.delete_many({"$or": [{"related_object_id": AID}, {"receipt_id": {"$in": rids}}]}).deleted_count
    print("cleanup: rules", db.escalation_rules.count_documents({}), "alert", db.alerts.count_documents({"alert_id": AID}), "receipts removed", n)
print(f"\n{sum(1 for r in results if r[1])}/{len(results)} passed; failed API calls: {len(failed)}"); [print("  API", f) for f in failed]
json.dump({"results": results, "failed": failed}, open(f"{SCR}/pol_acceptance.json", "w"))
sys.exit(0 if all(r[1] for r in results) else 1)
