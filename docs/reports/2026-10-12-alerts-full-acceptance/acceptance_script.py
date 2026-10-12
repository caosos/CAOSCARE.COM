import json, os, sys, time, uuid, requests, concurrent.futures as cf
from datetime import datetime, timezone
from pymongo import MongoClient
from playwright.sync_api import sync_playwright
sys.path.insert(0, "/home/caoscare-1/CAOSCARE-INTEGRATION/backend"); os.chdir("/home/caoscare-1/CAOSCARE-INTEGRATION/backend")
from dotenv import load_dotenv; load_dotenv(".env")
from routes.auth import _issue_jwt
SCR = "/tmp/claude-1000/-home-caoscare-1/65cd8277-4ae2-4662-b884-d9db0ebd139d/scratchpad"
BASE = "http://localhost:3000"; API = "http://127.0.0.1:8092/api"
db = MongoClient("mongodb://localhost:27017")["caoscare"]
RID, ROOM = "res_a26499ca719a", "3W03"
KIOSK = db.kiosks.find_one({"room": ROOM})["kiosk_id"]
assert db.escalation_rules.count_documents({}) == 0 and db.alerts.count_documents({"resident_id": RID, "status": {"$in": ["active", "acknowledged", "escalated"]}}) == 0
T0 = datetime.now(timezone.utc).isoformat()
owner = db.users.find_one({"role": "owner"}, {"_id": 0, "user_id": 1}); OW = _issue_jwt(owner["user_id"])
login = lambda e: requests.post(f"{API}/auth/login", json={"email": e, "password": "demo-pass-1234"}, timeout=5).json()["token"]
NU, FD = login("nancy.reyes@demo.caoscare"), login("dana.frost@demo.caoscare")
nurse_id = db.users.find_one({"email": "nancy.reyes@demo.caoscare"})["user_id"]
H = lambda t: {"Authorization": f"Bearer {t}"} if t else {}
results, failed, ev = [], [], {}
def case(n, ok, note=""): results.append((n, bool(ok), str(note))); print(("PASS " if ok else "FAIL ") + n + (f"  [{note}]" if note else ""))
def ctx(b, token, w, h=900):
    c = b.new_context(viewport={"width": w, "height": h}); c.add_init_script(f"window.localStorage.setItem('caos_token', {json.dumps(token)});")
    pg = c.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "422" not in m.text else None)
    pg.on("response", lambda r: failed.append((r.url, r.status)) if "/api/" in r.url and r.status >= 400 and r.request.method != "PUT" else None)
    return c, pg, errs
AID = None
try:
    # 1. creation + coalescing: 4 concurrent room-screen presses -> one event
    with cf.ThreadPoolExecutor(4) as ex:
        rs = list(ex.map(lambda _: requests.post(f"{API}/alerts", json={"kiosk_id": KIOSK, "resident_id": RID, "severity": "assist", "message": "SYNTHETIC acceptance press", "triggered_by": "kiosk_button"}, timeout=10), range(4)))
    ids = {r.json().get("alert_id") for r in rs if r.ok}
    AID = next(iter(ids)) if len(ids) == 1 else None
    a = db.alerts.find_one({"alert_id": AID}) if AID else {}
    cr = list(db.receipts.find({"related_object_id": AID, "action_type": {"$regex": "created|resident_assistance"}}, {"_id": 0, "receipt_id": 1, "action_type": 1, "actor_type": 1, "authority": 1}))
    case("4 concurrent presses -> 1 open event, press_count 4, 1 creation receipt", len(ids) == 1 and a.get("press_count") == 4 and len(cr) == 1, f"{AID} presses={a.get('press_count')} receipts={cr}")
    ev["creation_receipt"] = cr
    # 2. public / room-screen / Aria-safe outputs
    pub = requests.get(f"{API}/alerts/public/{AID}/status", timeout=5).json()
    case("public room-screen status is minimal (alert_id, status, severity)", set(pub) == {"alert_id", "status", "severity"}, pub)
    case("anonymous cannot read the full alert or the feed (401)", requests.get(f"{API}/alerts/{AID}", timeout=5).status_code == 401 and requests.get(f"{API}/alerts/feed", timeout=5).status_code == 401)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        # 3. policy edit (owner desktop) and runtime effect through the existing background tick
        c, pg, errs = ctx(b, OW, 1280); pg.goto(f"{BASE}/admin?tab=escalation"); pg.wait_for_selector("[data-testid=escalation-tab]", timeout=60000)
        pg.fill("[data-testid=esc-l2-seconds]", "20"); pg.fill("[data-testid=esc-l3-seconds]", "15")
        with pg.expect_response(lambda r: "escalation/rule" in r.url and r.request.method == "PUT") as rr: pg.click("[data-testid=esc-save]")
        case("invalid policy refused in the editor (422)", rr.value.status == 422 and db.escalation_rules.count_documents({}) == 0)
        pg.fill("[data-testid=esc-l3-seconds]", "40")
        with pg.expect_response(lambda r: "escalation/rule" in r.url and r.request.method == "PUT") as rr: pg.click("[data-testid=esc-save]")
        rule = db.escalation_rules.find_one({"facility_id": None}) or {}
        prc = db.receipts.find_one({"receipt_id": rule.get("receipt_id")}, {"_id": 0}) or {}
        case("owner policy edit saved with provenance receipt", rr.value.status == 200 and prc.get("authority") == "policy_editor:owner" and prc.get("after_state", {}).get("level_2_seconds") == 20, prc.get("receipt_id"))
        ev["policy_receipt"] = prc.get("receipt_id")
        pg.screenshot(path=f"{SCR}/fa_shots/01_policy_owner_1280.png", full_page=True); c.close()
        lvl = 0
        for _ in range(70):
            lvl = (db.alerts.find_one({"alert_id": AID}) or {}).get("escalation_level") or 0
            if lvl >= 2: break
            time.sleep(1)
        esc = list(db.receipts.find({"related_object_id": AID, "action_type": "alert_escalated"}, {"_id": 0, "receipt_id": 1, "after_state": 1, "authority": 1}))
        case("background tick escalated the event under the edited policy", lvl >= 2 and esc and esc[-1]["after_state"]["thresholds"] == {"level_2_seconds": 20, "level_3_seconds": 40}, f"level={lvl} {[e['receipt_id'] for e in esc]}")
        ev["escalation_receipts"] = [e["receipt_id"] for e in esc]
        case("no external delivery claimed (no phones configured -> no SMS attempt)", db.receipts.count_documents({"related_object_id": AID, "action_type": {"$regex": "sms|call"}}) == 0)
        h = requests.get(f"{API}/health", timeout=5).json()
        case("health: escalation running", h.get("escalation", {}).get("state") == "running", h.get("escalation"))
        # 4. nurse 390 px: sees and acknowledges
        c, pg, errs = ctx(b, NU, 390, 844); pg.goto(f"{BASE}/staff"); pg.wait_for_selector(f"[data-testid=ack-btn-{AID}]", timeout=60000)
        sw = pg.evaluate("document.documentElement.scrollWidth")
        pg.screenshot(path=f"{SCR}/fa_shots/02_nurse_390_open.png", full_page=True)
        pg.click(f"[data-testid=ack-btn-{AID}]"); time.sleep(2)
        a = db.alerts.find_one({"alert_id": AID})
        ack = db.receipts.find_one({"related_object_id": AID, "action_type": "alert_acknowledged"}, {"_id": 0})
        linked = [e for e in a.get("event_log", []) if e.get("to") == "acknowledged"]
        case("nurse at 390 px acknowledges; receipt + linked history; escalation stops", a["status"] == "acknowledged" and ack and ack["actor_id"] == nurse_id and linked and linked[0].get("receipt_id") == ack["receipt_id"], f"{ack and ack['receipt_id']} authority={ack and ack['authority']} scrollWidth={sw}")
        ev["ack_receipt"] = ack and ack["receipt_id"]
        case("nurse 390 px: no horizontal overflow, no page errors", sw <= 390 and not errs, f"sw={sw} {errs[:2]}")
        pg.screenshot(path=f"{SCR}/fa_shots/03_nurse_390_acked.png", full_page=True); c.close()
        lvl_after = db.alerts.find_one({"alert_id": AID}).get("escalation_level"); time.sleep(35)
        case("no further escalation after acknowledgement", db.alerts.find_one({"alert_id": AID}).get("escalation_level") == lvl_after, lvl_after)
        # 5. refusals
        codes = {
            "anon ack": requests.post(f"{API}/alerts/{AID}/acknowledge", timeout=5).status_code,
            "anon close": requests.post(f"{API}/alerts/{AID}/close", json={"outcome": "x"}, timeout=5).status_code,
            "anon policy": requests.put(f"{API}/escalation/rule", json={"level_2_seconds": 5, "level_3_seconds": 9}, timeout=5).status_code,
            "nurse policy": requests.put(f"{API}/escalation/rule", headers=H(NU), json={"level_2_seconds": 5, "level_3_seconds": 9}, timeout=5).status_code,
            "front desk policy": requests.put(f"{API}/escalation/rule", headers=H(FD), json={"level_2_seconds": 5, "level_3_seconds": 9}, timeout=5).status_code,
            "nurse tick": requests.post(f"{API}/escalation/tick", headers=H(NU), timeout=5).status_code,
            "repeat ack": requests.post(f"{API}/alerts/{AID}/acknowledge", headers=H(NU), timeout=5).status_code,
        }
        case("refusals: anon 401; nurse/front desk policy+tick 403; repeat ack refused", codes["anon ack"] == codes["anon close"] == codes["anon policy"] == 401 and codes["nurse policy"] == codes["front desk policy"] == codes["nurse tick"] == 403 and codes["repeat ack"] in (404, 409), codes)
        # 6. owner desktop: sees acknowledged, closes with outcome
        c, pg, errs = ctx(b, OW, 1280); pg.goto(f"{BASE}/alerts"); pg.wait_for_selector(f"[data-testid=alert-row-{AID}]", timeout=60000)
        pg.screenshot(path=f"{SCR}/fa_shots/04_owner_1280_acked.png", full_page=True)
        pg.click(f"[data-testid=alert-row-{AID}]"); pg.wait_for_selector("[data-testid=close-outcome]", timeout=10000)
        pg.fill("[data-testid=close-outcome]", "resolved_no_action"); pg.fill("[data-testid=close-notes]", "SYNTHETIC acceptance: checked on resident")
        pg.screenshot(path=f"{SCR}/fa_shots/05_owner_close_dialog.png")
        pg.click("[data-testid=close-event-btn]"); time.sleep(2)
        a = db.alerts.find_one({"alert_id": AID})
        done = db.receipts.find_one({"related_object_id": AID, "action_type": "alert_completed"}, {"_id": 0})
        case("owner closes: resolved, alert_completed receipt with actor, before/after, parent = origin (creation) receipt", a["status"] == "resolved" and done and done["actor_id"] == owner["user_id"] and done["before_state"]["status"] == "acknowledged" and done.get("parent_receipt_id") == ev["creation_receipt"][0]["receipt_id"], f"{done and done['receipt_id']} parent={done and done.get('parent_receipt_id')}")
        ackr = db.receipts.find_one({"receipt_id": ev["ack_receipt"]}, {"_id": 0}) or {}
        ev["ack_parent"] = ackr.get("parent_receipt_id"); print("INFO acknowledgement receipt parent:", ev["ack_parent"])
        ev["close_receipt"] = done and done["receipt_id"]
        case("repeat close refused (409), nothing changed", requests.post(f"{API}/alerts/{AID}/close", headers=H(OW), json={"outcome": "again"}, timeout=5).status_code == 409 and db.alerts.find_one({"alert_id": AID})["resolved_by"] == a["resolved_by"])
        case("public status now 'resolved', still minimal", requests.get(f"{API}/alerts/public/{AID}/status", timeout=5).json() == {"alert_id": AID, "status": "resolved", "severity": a["severity"]})
        case("owner desktop: no page errors", not errs, errs[:2]); c.close()
        c, pg, errs = ctx(b, OW, 390, 844); pg.goto(f"{BASE}/alerts"); pg.wait_for_selector("[data-testid=alerts-board]", timeout=60000); time.sleep(1)
        sw = pg.evaluate("document.documentElement.scrollWidth"); case("owner /alerts at 390 px: no horizontal overflow", sw <= 390, f"sw={sw}")
        pg.screenshot(path=f"{SCR}/fa_shots/06_owner_390.png", full_page=True); c.close(); b.close()
finally:
    rule = db.escalation_rules.find_one({"facility_id": None}) or {}
    rr = [x["receipt_id"] for x in db.receipts.find({"related_object_type": "escalation_rule", "created_at": {"$gte": T0}}, {"receipt_id": 1})]
    db.escalation_rules.delete_many({"facility_id": None})
    n_r = db.receipts.delete_many({"$or": [{"related_object_id": AID}, {"receipt_id": {"$in": rr}}]}).deleted_count if AID else 0
    n_n = db.notifications.delete_many({"$or": [{"alert_id": AID}, {"related_object_id": AID}]}).deleted_count if AID else 0
    n_d = db.staff_dispatches.delete_many({"alert_id": AID}).deleted_count if AID else 0
    n_a = db.alerts.delete_many({"alert_id": AID}).deleted_count if AID else 0
    print(f"cleanup: alert {n_a}, receipts {n_r}, notifications {n_n}, dispatches {n_d}, rules left {db.escalation_rules.count_documents({})}, open for resident {db.alerts.count_documents({'resident_id': RID, 'status': {'$ne': 'resolved'}})}")
print(f"\n{sum(1 for r in results if r[1])}/{len(results)} passed; failed API calls: {len(failed)}"); [print("  API", f) for f in failed]
json.dump({"results": results, "failed": failed, "evidence": ev, "alert_id": AID}, open(f"{SCR}/fa_acceptance.json", "w"), default=str)
sys.exit(0 if all(r[1] for r in results) else 1)
