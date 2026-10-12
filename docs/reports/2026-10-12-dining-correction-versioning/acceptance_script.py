import json, sys, time, requests
from pymongo import MongoClient
from playwright.sync_api import sync_playwright
SCR = "/tmp/claude-1000/-home-caoscare-1/65cd8277-4ae2-4662-b884-d9db0ebd139d/scratchpad"
BASE = "http://localhost:3000"; API = "http://127.0.0.1:8092/api"; DAY = "2031-03-04"
db = MongoClient("mongodb://localhost:27017")["caoscare"]
assert db.menu_items.count_documents({"date": DAY}) == 0
login = lambda e: requests.post(f"{API}/auth/login", json={"email": e, "password": "demo-pass-1234"}, timeout=5).json()["token"]
KI, NU = login("iris.kwan@demo.caoscare"), login("nancy.reyes@demo.caoscare")
H = lambda t: {"Authorization": f"Bearer {t}"}
pub = lambda: [i["item_name"] for i in requests.get(f"{API}/menu/public/today", params={"date": DAY, "meal_period": "dinner"}, timeout=5).json()]
results, failed = [], []
def case(n, ok, note=""): results.append((n, bool(ok), str(note))); print(("PASS " if ok else "FAIL ") + n + (f"  [{note}]" if note else ""))
def ctx(b, token, w, h):
    c = b.new_context(viewport={"width": w, "height": h}); c.add_init_script(f"window.localStorage.setItem('caos_token', {json.dumps(token)});")
    pg = c.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("response", lambda r: failed.append((r.url, r.status)) if "/api/" in r.url and r.status >= 400 else None)
    return c, pg, errs
try:
    v1 = requests.post(f"{API}/menu", headers=H(KI), json={"date": DAY, "meal_period": "dinner", "item_name": "SYNTHETIC Baked cod", "description": "with rice"}, timeout=5).json()["menu_id"]
    requests.post(f"{API}/menu/{v1}/approve", headers=H(KI), timeout=5)
    case("published dinner visible to residents/Aria", pub() == ["SYNTHETIC Baked cod"])
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        c, pg, errs = ctx(b, KI, 1280, 900); pg.goto(f"{BASE}/workspace"); pg.wait_for_selector("[data-testid=services-tab-content]", timeout=60000); pg.click("[data-testid=services-tab-content]"); pg.wait_for_selector("[data-testid=menu-date-picker]", timeout=20000)
        pg.fill("[data-testid=menu-date-picker]", DAY); pg.wait_for_selector(f"[data-testid=menu-row-{v1}]", timeout=15000)
        pg.click(f"[data-testid=edit-menu-{v1}]"); pg.wait_for_selector("[data-testid=menu-save-draft]")
        txt = pg.inner_text("[role=dialog]"); case("correct dialog explains versioning", "new version" in txt and "Replaced" in txt)
        pg.fill("[data-testid=menu-item-name]" if pg.locator("[data-testid=menu-item-name]").count() else "[role=dialog] input[required]:not([type=date])", "SYNTHETIC Grilled salmon")
        pg.screenshot(path=f"{SCR}/mv_shots/01_correct_dialog_1280.png")
        pg.click("[data-testid=menu-save-draft]"); time.sleep(1.5)
        new = db.menu_items.find_one({"date": DAY, "replaces": v1}); old = db.menu_items.find_one({"menu_id": v1})
        case("draft correction is a new item; published one untouched and still live", new and new["status"] == "draft" and new["item_name"] == "SYNTHETIC Grilled salmon" and old["status"] == "approved" and old["item_name"] == "SYNTHETIC Baked cod" and pub() == ["SYNTHETIC Baked cod"], new and new["menu_id"])
        pg.wait_for_selector(f"[data-testid=menu-correction-{new['menu_id']}]", timeout=10000)
        pg.screenshot(path=f"{SCR}/mv_shots/02_list_draft_correction_1280.png", full_page=True)
        pg.click(f"[data-testid=approve-menu-{new['menu_id']}]"); pg.wait_for_selector(f"[data-testid=menu-replaced-{v1}]", timeout=10000); time.sleep(0.5)
        old = db.menu_items.find_one({"menu_id": v1})
        case("publishing the correction supersedes the original (labelled Replaced); residents/Aria see the correction", old["status"] == "superseded" and old["superseded_by"] == new["menu_id"] and pub() == ["SYNTHETIC Grilled salmon"] and "Replaced" in pg.inner_text(f"[data-testid=menu-row-{v1}]"))
        pg.screenshot(path=f"{SCR}/mv_shots/03_list_after_publish_1280.png", full_page=True)
        case("kitchen 1280: no page errors", not errs, errs[:2]); c.close()
        c, pg, errs = ctx(b, KI, 390, 844); pg.goto(f"{BASE}/workspace"); pg.wait_for_selector("[data-testid=services-tab-content]", timeout=60000); pg.click("[data-testid=services-tab-content]"); pg.wait_for_selector("[data-testid=menu-date-picker]", timeout=20000)
        pg.fill("[data-testid=menu-date-picker]", DAY); pg.wait_for_selector(f"[data-testid=menu-replaced-{v1}]", timeout=15000); time.sleep(0.5)
        sw = pg.evaluate("document.documentElement.scrollWidth"); case("kitchen 390 px: versions readable, no overflow, no errors", sw <= 390 and not errs, f"sw={sw}")
        pg.screenshot(path=f"{SCR}/mv_shots/04_list_390.png", full_page=True); c.close(); b.close()
    acts = [r["action_type"] for r in db.receipts.find({"related_object_id": {"$in": [v1, new["menu_id"]]}}).sort("created_at", 1)]
    case("receipts: created, published, corrected, superseded, published", acts == ["menu_content_created", "menu_content_published", "menu_content_corrected", "menu_content_superseded", "menu_content_published"], acts)
    codes = {"republish old": requests.post(f"{API}/menu/{v1}/approve", headers=H(KI), timeout=5).status_code,
             "edit old": requests.patch(f"{API}/menu/{v1}", headers=H(KI), json={"item_name": "x"}, timeout=5).status_code,
             "nurse edit": requests.patch(f"{API}/menu/{new['menu_id']}", headers=H(NU), json={"item_name": "x"}, timeout=5).status_code,
             "anon edit": requests.patch(f"{API}/menu/{new['menu_id']}", json={"item_name": "x"}, timeout=5).status_code}
    case("refusals: superseded 409/409, nurse 403, anonymous 401; menu unchanged", codes == {"republish old": 409, "edit old": 409, "nurse edit": 403, "anon edit": 401} and pub() == ["SYNTHETIC Grilled salmon"], codes)
finally:
    ids = [i["menu_id"] for i in db.menu_items.find({"date": DAY}, {"menu_id": 1})]
    print("cleanup: items", db.menu_items.delete_many({"date": DAY}).deleted_count, "receipts", db.receipts.delete_many({"related_object_id": {"$in": ids}}).deleted_count)
real_fail = [f for f in failed if not any(k in f[0] for k in ("/approve", f"/menu/"))]
print(f"\n{sum(1 for r in results if r[1])}/{len(results)} passed; failed API calls from the page: {len(failed)}"); [print("  API", f) for f in failed]
sys.exit(0 if all(r[1] for r in results) else 1)
