"""Dev browser acceptance for careops-dining-dietary-allergen-truth-001.
Synthetic date 2031-03-05 (no real screen shows it); demo kitchen/nurse logins; cleans up."""
import json, sys, time, requests
from pymongo import MongoClient
from playwright.sync_api import sync_playwright
OUT = sys.argv[1]
BASE = "http://localhost:3000"; API = "http://127.0.0.1:8092/api"; DAY = "2031-03-05"
db = MongoClient("mongodb://localhost:27017")["caoscare"]
assert db.menu_items.count_documents({"date": DAY}) == 0
login = lambda e: requests.post(f"{API}/auth/login", json={"email": e, "password": "demo-pass-1234"}, timeout=5).json()["token"]
KI, NU = login("iris.kwan@demo.caoscare"), login("nancy.reyes@demo.caoscare")
H = lambda t: {"Authorization": f"Bearer {t}"}
pub = lambda: requests.get(f"{API}/menu/public/today", params={"date": DAY}, timeout=5).json()
results, failed = [], []
def case(n, ok, note=""): results.append((n, bool(ok))); print(("PASS " if ok else "FAIL ") + n + (f"  [{note}]" if note else ""))
def ctx(b, w, h):
    c = b.new_context(viewport={"width": w, "height": h}); c.add_init_script(f"window.localStorage.setItem('caos_token', {json.dumps(KI)});")
    pg = c.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("response", lambda r: failed.append((r.url, r.status)) if "/api/" in r.url and r.status >= 400 else None)
    return c, pg, errs
def open_menu(pg):
    pg.goto(f"{BASE}/workspace"); pg.wait_for_selector("[data-testid=services-tab-content]", timeout=60000)
    pg.click("[data-testid=services-tab-content]"); pg.wait_for_selector("[data-testid=menu-date-picker]", timeout=20000)
    pg.fill("[data-testid=menu-date-picker]", DAY); time.sleep(1)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
        c, pg, errs = ctx(b, 1280, 900); open_menu(pg)
        pg.click("[data-testid=add-menu-btn]"); pg.wait_for_selector("[data-testid=menu-labels-note]")
        case("dialog shows label inputs and the no-inference note", "does not mean the dish is free of it" in pg.inner_text("[data-testid=menu-labels-note]"))
        pg.fill("[data-testid=menu-date]", DAY)
        pg.fill("[data-testid=menu-item-name]", "SYNTHETIC Mac and cheese")
        pg.fill("[data-testid=menu-dietary-labels]", " Vegetarian ,vegetarian, ")
        pg.fill("[data-testid=menu-allergens]", "Milk,  Wheat")
        pg.screenshot(path=f"{OUT}/01_dialog_1280.png")
        pg.click("[data-testid=menu-save-publish]"); time.sleep(2)
        it = db.menu_items.find_one({"date": DAY})
        case("saved normalized and de-duplicated on the one MenuItem", it and it["dietary_labels"] == ["Vegetarian"] and it["allergens"] == ["Milk", "Wheat"] and it["status"] == "approved", it and (it["dietary_labels"], it["allergens"]))
        v1 = it["menu_id"]
        pg.wait_for_selector(f"[data-testid=menu-labels-{v1}]", timeout=10000)
        case("staff list shows the labels", pg.inner_text(f"[data-testid=menu-labels-{v1}]") == "Vegetarian; contains: Milk, Wheat")
        pg.screenshot(path=f"{OUT}/02_list_1280.png", full_page=True)
        pub1 = pub()
        case("residents/Aria endpoint repeats labels verbatim, adds nothing", pub1 == [{"meal_period": "lunch", "item_name": "SYNTHETIC Mac and cheese", "description": "", "availability": "", "dietary_labels": ["Vegetarian"], "allergens": ["Milk", "Wheat"]}], pub1)
        # correction of the labels from the UI
        pg.click(f"[data-testid=edit-menu-{v1}]"); pg.wait_for_selector("[data-testid=menu-allergens]")
        case("correction dialog is prefilled with current labels", pg.input_value("[data-testid=menu-allergens]") == "Milk, Wheat")
        pg.fill("[data-testid=menu-allergens]", "Milk, Wheat, Egg"); pg.click("[data-testid=menu-save-publish]"); time.sleep(2)
        new = db.menu_items.find_one({"date": DAY, "replaces": v1}); old = db.menu_items.find_one({"menu_id": v1})
        case("label correction is a new version; superseded keeps what it said", new and new["allergens"] == ["Milk", "Wheat", "Egg"] and old["status"] == "superseded" and old["allergens"] == ["Milk", "Wheat"] and pub()[0]["allergens"] == ["Milk", "Wheat", "Egg"])
        # refusal shown in the UI
        pg.click(f"[data-testid=edit-menu-{new['menu_id']}]"); pg.wait_for_selector("[data-testid=menu-allergens]")
        pg.fill("[data-testid=menu-allergens]", "<b>milk</b>"); pg.click("[data-testid=menu-save-draft]"); time.sleep(1.5)
        body = pg.inner_text("body")
        case("bad label refused with a readable message, nothing saved", "Labels may contain only" in body and db.menu_items.count_documents({"date": DAY}) == 2, "toast" )
        pg.keyboard.press("Escape")
        case("kitchen 1280: no page errors", not errs, errs[:2]); c.close()
        c, pg, errs = ctx(b, 390, 844); open_menu(pg); pg.wait_for_selector(f"[data-testid=menu-labels-{new['menu_id']}]", timeout=15000)
        sw = pg.evaluate("document.documentElement.scrollWidth")
        case("kitchen 390 px: labels readable, no overflow, no errors", sw <= 390 and not errs, f"sw={sw}")
        pg.screenshot(path=f"{OUT}/03_list_390.png", full_page=True); c.close(); b.close()
    acts = [r["action_type"] for r in db.receipts.find({"related_object_id": {"$in": [v1, new["menu_id"]]}}).sort("created_at", 1)]
    rc = db.receipts.find_one({"related_object_id": new["menu_id"], "action_type": "menu_content_corrected"})
    case("receipts carry the label change", rc and rc["before_state"]["allergens"] == ["Milk", "Wheat"] and rc["after_state"]["allergens"] == ["Milk", "Wheat", "Egg"], acts)
    codes = {"nurse": requests.patch(f"{API}/menu/{new['menu_id']}", headers=H(NU), json={"allergens": ["Peanut"]}, timeout=5).status_code,
             "anon": requests.patch(f"{API}/menu/{new['menu_id']}", json={"allergens": ["Peanut"]}, timeout=5).status_code,
             "13 labels": requests.post(f"{API}/menu", headers=H(KI), json={"date": DAY, "meal_period": "dinner", "item_name": "x", "allergens": [f"a{i}" for i in range(13)]}, timeout=5).status_code}
    case("refusals: nurse 403, anonymous 401, over-limit 422; labels unchanged", codes == {"nurse": 403, "anon": 401, "13 labels": 422} and pub()[0]["allergens"] == ["Milk", "Wheat", "Egg"], codes)
finally:
    ids = [i["menu_id"] for i in db.menu_items.find({"date": DAY}, {"menu_id": 1})]
    print("cleanup: items", db.menu_items.delete_many({"date": DAY}).deleted_count, "receipts", db.receipts.delete_many({"related_object_id": {"$in": ids}}).deleted_count)
expected_fail = [f for f in failed if f[1] == 422]
print(f"\n{sum(1 for r in results if r[1])}/{len(results)} passed; failed API calls from the page: {len(failed)} ({len(expected_fail)} expected 422)")
for f in failed: print("  API", f)
sys.exit(0 if all(r[1] for r in results) else 1)
