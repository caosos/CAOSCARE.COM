import asyncio, os, sys, json
os.environ["DB_NAME"] = "caoscare_acc_fa_chain"; os.environ["CAOSCARE_ESCALATION_AUTO"] = "1"
sys.path.insert(0, "/home/caoscare-1/CAOSCARE-INTEGRATION/backend"); os.chdir("/home/caoscare-1/CAOSCARE-INTEGRATION/backend")
from dotenv import load_dotenv; load_dotenv(".env", override=False)
os.environ["DB_NAME"] = "caoscare_acc_fa_chain"
from deps import db
from routes import escalation_schedule as es
async def main():
    assert db.name == "caoscare_acc_fa_chain"
    real = es.run_tick
    async def broken(now=None): raise RuntimeError("synthetic tick failure")
    es.run_tick = broken; await es.tick_once(); await es.tick_once()
    es.run_tick = real; await es.tick_once()
    async def dies(interval): raise MemoryError("synthetic loop crash")
    es.run_escalation_loop = dies; await es.start_schedule()
    for _ in range(10): await asyncio.sleep(0.05)
    await es.tick_once()
    async def sleeper(interval): await asyncio.sleep(3600)
    es.run_escalation_loop = sleeper; await es.start_schedule(); await asyncio.sleep(0.05); await es.stop_schedule()
    for _ in range(10): await asyncio.sleep(0.05)
    rs = await db.receipts.find({"related_object_type": "escalation_schedule"}, {"_id": 0, "receipt_id": 1, "action_type": 1, "parent_receipt_id": 1, "before_state": 1, "after_state": 1, "authority": 1, "actor_id": 1}).sort("created_at", 1).to_list(20)
    for r in rs:
        print(r["receipt_id"], r["action_type"], "parent=", r.get("parent_receipt_id"), r["before_state"]["tick"], "->", r["after_state"]["tick"], r["authority"], r["actor_id"])
    print("notifications:", await db.notifications.count_documents({}))
    await db.client.drop_database("caoscare_acc_fa_chain"); print("scratch DB dropped")
asyncio.run(main())
