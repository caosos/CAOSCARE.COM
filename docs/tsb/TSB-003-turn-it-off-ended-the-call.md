# TSB-003 — "Turn it off" / "stop" were classed as an explicit end of the call

**Status:** FIXED IN CODE (`cfc8020`, integration) — NOT LIVE. The Room 214 page still runs `main.18cb3cf4.js`; applying it needs a page rebuild (parked by owner 2026-10-10). Live acceptance: none.

**Symptom (found offline, never seen live):** the handler replay test (`frontend/src/lib/__tests__/handlerReplay.test.js`, audit gap 6) fed "Turn it off." and the real handler logged `local_end` and sent a goodbye instead of dispatching the light tool.
**Confirmed cause:** `frontend/src/lib/endIntent.js` CORE patterns included `shut/turn (it|this|that) off` and a bare `(please) stop`. With lights and a TV in the room these mean a device or a barge-in, never the call.
**Not established:** whether any real resident was ever hung up by this. Room 214 session logs were not searched for it.
**Fix:** only `turn/shut yourself off` ends the call (`cfc8020`); regression tests in `endIntent.test.js`. Frontend 56 suites / 495 passed at the fix; 58 / 501 at `cc00b46`.
**Rollback:** `git revert cfc8020` (nothing live depends on it).
**Evidence (re-runnable):** `cd frontend && CI=true REACT_APP_BACKEND_URL=http://localhost:8000 yarn test --watchAll=false src/lib/__tests__/handlerReplay.test.js src/lib/__tests__/endIntent.test.js`.
**Linked receipts:** PROJECT_STATE 2026-10-10 "Test-reality audit gaps 1-6 closed" and #117 comments for items da-de69e45b5a, da-4daec2d025.
**Next owner/task:** the page rebuild to ship it is Michael's call when voice work resumes (scope in the #117 comment for da-4daec2d025).
