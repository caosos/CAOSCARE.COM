"""Voice bridge priority classes and admission (capacity) control."""
import asyncio

from routes.voice_bridge_admission import Admission, classify


def test_priority_classes():
    cases = {1: ["I fell and I can't get up.", "I can't breathe", "Help me!", "I have chest pain", "It's an emergency"],
             2: ["I need a nurse", "Can you help me with the TV?", "I need to use the bathroom"],
             3: ["My sink is leaking", "I need a ride to the doctor", "Can housekeeping bring towels"],
             4: ["Turn on the light", "Set the thermostat to 72"],
             5: ["What's for dinner?", "What activities are on?"],
             6: ["Tell me a story", "How are you"]}
    for prio, texts in cases.items():
        for t in texts:
            assert classify(t) == prio, (t, classify(t), prio)


def test_reserved_slots_keep_room_for_staff_help():
    async def run():
        a = Admission(max_active=4, reserved=1)
        got = [await a.acquire(6, 0.05) for _ in range(3)]
        assert all(ok for ok, _ in got)
        ok, _ = await a.acquire(6, 0.05)          # conversation cannot take the reserved slot
        assert not ok
        ok, _ = await a.acquire(2, 0.05)          # staff help can
        assert ok
        ok, _ = await a.acquire(2, 0.05)          # all four slots now busy
        assert not ok
        snap = a.snapshot()
        assert snap["active"] == 4 and all(isinstance(k, str) for k in snap["by_class"])
        assert snap["by_class"]["conversation"]["deferred"] == 1
    asyncio.run(run())


def test_higher_priority_waiter_is_served_first():
    async def run():
        a = Admission(max_active=1, reserved=0)
        assert (await a.acquire(5, 0.05))[0]
        order = []

        async def wait(prio):
            ok, _ = await a.acquire(prio, 2)
            order.append(prio)
            await asyncio.sleep(0.01)
            a.release()
        low = asyncio.create_task(wait(6))
        await asyncio.sleep(0.01)
        high = asyncio.create_task(wait(2))
        await asyncio.sleep(0.01)
        a.release()
        await asyncio.gather(low, high)
        assert order == [2, 6] and a.active == 0
    asyncio.run(run())


def test_deferral_is_bounded_by_wait_limit():
    async def run():
        a = Admission(max_active=1, reserved=0)
        await a.acquire(5, 0.05)
        ok, waited = await a.acquire(6, 0.2)
        assert not ok and 0.15 < waited < 1.0 and a.snapshot()["queued"] == 0
    asyncio.run(run())
