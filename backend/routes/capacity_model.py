"""Capacity model: each metric's current value against its tested safe value.

Safe values come from the measured EliteDesk baseline (voice-bridge load test,
docs/reports/2026-10-04-voice-bridge-load-test.md) where one exists, and are
marked `configured` where no test set them (disk, memory, database latency).
They live in `capacity_config` and can be changed (with a receipt).

utilization = value / safe. The bottleneck is the metric with the highest
utilization; headroom is what is left of its safe value. Emergency reserve
is the staff-help model slots no lower-priority turn may use; emergency
words never need a slot at all (voice_bridge.py).
"""
from datetime import datetime, timedelta, timezone

BASELINE_SOURCE = "voice-bridge load test 2026-10-04 (ac5dac6), EliteDesk Ryzen 5 PRO 2400GE"

# key: (component, unit, safe default, source, traffic class, recommendation, extractor path)
METRICS = {
    "voice_turns_per_min": ("voice bridge", "turns/min", 1250, "measured", "resident_voice",
                            "add_voice_worker"),
    "voice_slots_used_pct": ("voice bridge admission", "% of unreserved slots", 100, "measured",
                             "resident_voice", "add_voice_worker"),
    "voice_first_answer_p95_s": ("voice bridge", "seconds", 6.0, "measured", "resident_voice",
                                 "add_voice_worker"),
    "voice_provider_errors_per_min": ("language-model provider", "errors/min", 5, "configured",
                                      "resident_voice", "repair_provider"),
    "voice_rate_limited_per_min": ("language-model provider", "429s/min", 3, "configured",
                                   "resident_voice", "increase_provider_quota"),
    "worker_cpu_pct": ("backend worker (one event loop)", "% of one core", 100, "measured", "staff_dashboard",
                       "add_voice_worker"),
    "host_cpu_pct": ("EliteDesk CPU", "% of all cores", 85, "configured", "background_jobs", "add_cpu"),
    "memory_used_pct": ("EliteDesk memory", "% used", 85, "configured", "background_jobs", "add_ram"),
    "swap_out_per_s": ("EliteDesk memory", "pages/s swapped out", 50, "configured", "background_jobs", "add_ram"),
    "disk_used_pct": ("EliteDesk disk", "% used", 85, "configured", "receipt_audit_writes", "add_storage"),
    "db_ping_ms": ("MongoDB", "ms", 50, "configured", "receipt_audit_writes", "investigate_database"),
    "receipt_write_p95_ms": ("receipts", "ms", 100, "configured", "receipt_audit_writes", "investigate_database"),
    "device_events_per_min": ("devices", "events/min", 600, "configured", "resident_device",
                              "correct_device_flood"),
    "api_error_rate_pct": ("CAOSCare API", "% of requests", 2, "configured", "staff_workflow",
                           "investigate_database"),
}
RECOMMENDATIONS = {
    "add_cpu": "Add CPU capacity", "add_ram": "Add RAM", "add_storage": "Add storage",
    "add_voice_worker": "Add another voice-processing worker",
    "increase_provider_quota": "Increase provider concurrency or quota",
    "reduce_background": "Reduce or reschedule background work",
    "pause_simulator": "Pause or slow simulator traffic",
    "investigate_database": "Investigate database latency", "repair_provider": "Repair a failing provider",
    "correct_device_flood": "Correct an abnormal device-event flood",
}
HARDWARE = {"add_cpu", "add_ram", "add_storage"}
DEFAULT_CONFIG = {
    "levels": {"WATCH": 0.6, "ACTION_NEEDED": 0.8, "CRITICAL": 0.95},
    "sustain_samples": {"WATCH": 4, "ACTION_NEEDED": 4, "CRITICAL": 2},
    "clear_margin": 0.1, "clear_samples": 8, "cooldown_s": 900, "hardware_after_s": 900,
    "safe": {k: v[2] for k, v in METRICS.items()},
}
LEVELS = ("NORMAL", "WATCH", "ACTION_NEEDED", "CRITICAL")


def values(sample: dict) -> dict:
    """Metric values from one capacity sample (missing metrics are None)."""
    h, v, a = sample.get("host") or {}, sample.get("voice") or {}, sample.get("api") or {}
    per_min = 60 / max(sample.get("interval_s") or 15, 1)
    adm = v.get("admission") or {}
    unreserved = max((adm.get("slots") or 0) - (adm.get("reserved") or 0), 0) * max(adm.get("workers") or 1, 1)
    reqs = sum(x.get("requests", 0) for x in a.values())
    errs = sum(x.get("errors", 0) for x in a.values())
    return {
        "voice_turns_per_min": round((v.get("turns") or 0) * per_min, 1),
        "voice_slots_used_pct": round((adm.get("active") or 0) / unreserved * 100, 1) if unreserved else None,
        "voice_first_answer_p95_s": v.get("latency_p95_s"),
        "voice_provider_errors_per_min": round(((v.get("llm_failures") or 0) + (v.get("timeouts") or 0)) * per_min, 1),
        "voice_rate_limited_per_min": round((v.get("rate_limited") or 0) * per_min, 1),
        "worker_cpu_pct": sample.get("caoscare_worker_cpu_max_pct"),
        "host_cpu_pct": h.get("cpu_pct"),
        "memory_used_pct": (h.get("memory") or {}).get("used_pct"),
        "swap_out_per_s": h.get("swap_out_per_s"),
        "disk_used_pct": h.get("disk_used_pct"),
        "db_ping_ms": (sample.get("db") or {}).get("ping_ms"),
        "receipt_write_p95_ms": (sample.get("receipts") or {}).get("write_p95_ms"),
        "device_events_per_min": (sample.get("devices") or {}).get("events_per_min"),
        "api_error_rate_pct": round(errs / reqs * 100, 2) if reqs >= 20 else None,
    }


def utilization(sample: dict, config: dict) -> dict:
    safe = config.get("safe", {})
    out = {}
    for k, v in values(sample).items():
        s = safe.get(k)
        out[k] = round(v / s, 3) if v is not None and s else None
    return out


def level_for(u, config) -> str:
    lv = "NORMAL"
    for name, threshold in config["levels"].items():
        if u is not None and u >= threshold:
            lv = name
    return lv


def attribution(sample: dict, key: str) -> dict:
    """Which traffic class is producing the load, and whether it is real.
    Host-level metrics compare CAOSCare's own CPU with the whole host: if
    CAOSCare is a small share, the load is another process on the machine."""
    api = sample.get("api") or {}
    voice = sample.get("voice") or {}
    sim_api = sum(api.get(c, {}).get("requests", 0) for c in ("simulator_resident", "simulator_staff"))
    all_api = sum(x.get("requests", 0) for x in api.values()) or 0
    sim_voice, real_voice = voice.get("simulated") or 0, voice.get("real") or 0
    if key.startswith("voice"):
        sim_share = sim_voice / (sim_voice + real_voice) if sim_voice + real_voice else 0.0
        cls = "simulator_resident" if sim_share > 0.5 else "resident_voice"
    else:
        sim_share = sim_api / all_api if all_api else 0.0
        busiest = max(api.items(), key=lambda kv: kv[1].get("latency_sum_ms", 0), default=(METRICS[key][4], {}))[0]
        cls = busiest if all_api else METRICS[key][4]
    if key == "host_cpu_pct":
        host = (sample.get("host") or {}).get("cpu_pct") or 0
        own = sample.get("caoscare_cpu_share_pct")
        if own is not None and host and own < host * 0.5:
            return {"traffic_class": "non_caoscare_host_process", "simulated": False, "simulated_share": 0.0,
                    "detail": f"CAOSCare uses {own}% of the host; {round(host - own, 1)}% is other processes"}
    if key in ("memory_used_pct", "swap_out_per_s", "disk_used_pct"):
        # Host-wide resources: no per-request attribution is possible.
        return {"traffic_class": "host_all_processes", "simulated": False, "simulated_share": round(sim_share, 3)}
    return {"traffic_class": cls, "simulated": sim_share > 0.5, "simulated_share": round(sim_share, 3)}


def recommendation(key: str, level: str, attr: dict, sustained_s: float, config: dict) -> dict:
    """What to do about a metric at a level. Simulator load -> slow the
    simulator; another process -> reschedule it; hardware only after the
    level has held for `hardware_after_s`."""
    rec = METRICS[key][5]
    if attr.get("simulated"):
        rec = "pause_simulator"
    elif attr.get("traffic_class") == "non_caoscare_host_process":
        rec = "reduce_background"
    if level not in ("ACTION_NEEDED", "CRITICAL"):
        return {"type": None, "text": "Watch - no action yet", "reason": "below ACTION NEEDED"}
    if rec in HARDWARE and sustained_s < config["hardware_after_s"]:
        return {"type": None, "text": "Watch - not sustained long enough for a hardware recommendation",
                "reason": f"held {round(sustained_s)} s of {config['hardware_after_s']} s"}
    return {"type": rec, "text": RECOMMENDATIONS[rec], "reason": f"{key} at {level}"}


def headroom(sample: dict, config: dict) -> dict:
    u = utilization(sample, config)
    known = {k: v for k, v in u.items() if v is not None}
    bottleneck = max(known, key=known.get) if known else None
    vals = values(sample)
    adm = (sample.get("voice") or {}).get("admission") or {}
    reserved = (adm.get("reserved") or 0) * max(adm.get("workers") or 1, 1)
    return {
        "bottleneck": bottleneck, "bottleneck_component": METRICS[bottleneck][0] if bottleneck else None,
        "bottleneck_utilization": known.get(bottleneck), "headroom_pct": round((1 - known[bottleneck]) * 100, 1)
        if bottleneck else None,
        "per_metric": {k: {"value": vals[k], "safe": config["safe"].get(k), "utilization": u[k],
                           "remaining": round(config["safe"][k] - vals[k], 2) if vals[k] is not None else None,
                           "unit": METRICS[k][1], "component": METRICS[k][0], "source": METRICS[k][3]}
                       for k in METRICS},
        "emergency_reserve": {"reserved_staff_help_slots": reserved,
                              "reserved_in_use": adm.get("reserved_in_use"),
                              "emergency_path": "emergency words bypass model slots entirely"},
    }


def projection(daily_peaks: list, threshold: float = 0.8) -> dict:
    """daily_peaks: [(date, utilization)] oldest first. Least-squares trend;
    the date the bottleneck would reach `threshold`, if rising."""
    pts = [(i, u) for i, (_, u) in enumerate(daily_peaks) if u is not None]
    if len(pts) < 3:
        return {"status": "insufficient_history", "days_of_data": len(pts)}
    n = len(pts)
    mx, my = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    slope = sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx if sxx else 0.0
    last_i, last_u = pts[-1]
    current = my + slope * (last_i - mx)
    if slope <= 0.001:
        return {"status": "flat_or_falling", "slope_per_day": round(slope, 4), "current_trend": round(current, 3)}
    days = (threshold - current) / slope
    last_date = daily_peaks[-1][0]
    when = (datetime.fromisoformat(last_date) + timedelta(days=max(days, 0))).date().isoformat() \
        if isinstance(last_date, str) else None
    return {"status": "rising", "slope_per_day": round(slope, 4), "current_trend": round(current, 3),
            "days_to_threshold": round(max(days, 0), 1), "projected_date": when, "threshold": threshold}


def now_iso():
    return datetime.now(timezone.utc).isoformat()
