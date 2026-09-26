# Room Builder — voice-first room configuration (PROPOSAL, not built)

Status: **proposal for Michael's review** (2026-09-25). Nothing implemented.
No earlier "room configurator concept" exists in this repository; this
document starts it. Positioning: help someone see and configure a better
living experience in *their* room — not sell electronics, not CAD.

## 1. Voice-first input — how it should work

- **Same edit pipeline for voice and clicks.** Speech (or typed text) is
  turned into a short list of explicit *room edits* — `add_item`,
  `place_on_wall`, `set_size`, `move`, `attach_feature`, `remove`,
  `set_room_type`. The canvas applies exactly the same edits a click does.
  The model never writes the room directly.
- **Language → edits** via structured tool calls (the same tool-calling
  pattern Aria's Realtime tools already use), with a dedicated *room setup*
  tool set — separate from Resident Aria's care tools.
- **"Over here" needs a pointer.** Deictic speech is paired with the screen:
  "the window is here" + a tap on a wall. Without a tap, relative phrases
  work ("across from the bed", "left of the TV"). If it can't resolve,
  it **asks** ("Which wall — the one with the door?"), never guesses.
- **Everything visible and undoable.** Each edit appears immediately;
  uncertain items are drawn dashed with "check this". Spoken sizes are
  stored as approximate ("about six feet").
- Truth rule carries over: the builder only offers features CAOSCare can
  actually support, and says which are proven vs planned.

## 2. Room model — what is stored

```
RoomPlan
  plan_id, facility_id, room            (room = same string as Kiosk.room)
  template_id | null                    (community floor-plan template or blank)
  unit_type                             (studio, one-bedroom, alcove, ...)
  shape: simple polygon, 4+ walls, approximate dimensions + unit + approx flag
  areas[]:   bedroom | bathroom | living | kitchenette  (region on canvas)
  items[]:   id, type (window, door, bed, chair, tv, lamp, thermostat, ...),
             position (wall + offset, or point in room), size (approx),
             label, source (visual | voice | template),
             utterance (the words that created it, if voice),
             confidence (confirmed | needs_check)
  features[]: item_id -> CAOSCare component
             kind + capabilities from the EXISTING device vocabulary
             (DeviceKind: blinds, light, tv, thermostat, ac, outlet...;
              DeviceCapability: position, power, brightness, input...)
             support: proven | planned | not_available
             device_id -> SmartDevice once actually installed
  history[]: every edit with source (click/voice), time, actor
```

One source of truth: the plan is **intended** configuration; the installed
truth stays `SmartDevice` (linked by `device_id`), so the plan never becomes
a second device registry. The package summary is *derived* from `features`.

## 3. UI — visual and conversational together

```
+------------------------------+---------------------------+
|  top-down room canvas        |  conversation panel       |
|  walls, areas, items         |  mic + text box           |
|  tap = select / point        |  "You said... I placed..."|
|  palette of items            |  clarifying questions     |
+------------------------------+---------------------------+
|  CAOSCare features on selected item  |  package summary  |
+----------------------------------------------------------+
```

Both sides edit the same plan through the same edit list; the panel narrates
what changed so voice users can confirm without reading the canvas. Large
targets and readable text (older users, families on phones).

## 4. Smallest useful first version (Phase 1)

- Blank rectangular room + 1-2 real community templates (if floor plans are
  provided).
- Palette of ~8 items: window, door, bathroom area, bed, chair, TV, lamp,
  thermostat. Drag, snap windows/doors to walls.
- Attach features from the real supported list, each marked honestly:
  lights (proven in Room 214 via Home Assistant/Matter), TV (partial), climate
  (Midea AC blocked on device), blinds (not yet proven).
- Package/configuration summary; save/load one plan per room.
- Edits already go through the edit list, so Phase 2 plugs in without a rewrite.

## 5. Deferred

- Phase 2: guided conversational setup (voice/text → edits, pointing,
  clarifying questions).
- Phase 3: generated room renderings / "life here" previews — enhancement
  only; the product never depends on it.
- Real measurements / install survey, pricing and ordering, multi-room
  apartments beyond templates, photo-to-room, community marketing views.

## Open questions for Michael

1. Who uses it first: prospective resident/family, staff/installer, or the
   resident? (Changes where it lives: public site vs Admin.)
2. Community floor plans available for templates?
3. Pricing in the summary, or capabilities only for now?
4. Room plans describe a person's home — confirm storage/retention
   expectations before any public, logged-out version.
