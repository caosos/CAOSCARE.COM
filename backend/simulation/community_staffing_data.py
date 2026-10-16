"""Static staffing data for the living-community simulator: calendar, roles, shifts.

Reference data only (no functions over it beyond the weekday helper); the rota and
status logic live in :mod:`simulation.community_staffing`.  Headcounts and shift
windows are simulation assumptions informed by the owner, not facility HR data.
"""

SIMULATION_LOAD_DISCLAIMER = (
    "Synthetic event-load fixture only; not real-world staffing or clinical coverage advice."
)
MAX_SCHEDULED_DAYS_PER_ROLLING_WEEK = 6
MIN_REST_BETWEEN_DUTIES_MINUTES = 8 * 60

# Simulated calendar: Day 1 (day_index 0) is a Monday. Weekly schedules below
# use 0 = Monday ... 6 = Sunday.
DAY0_WEEKDAY = 0
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MON_FRI = frozenset(range(5))
WED_SUN = frozenset({2, 3, 4, 5, 6})
SAT_SUN = frozenset({5, 6})


def weekday_of(day_index: int) -> int:
    return (DAY0_WEEKDAY + day_index) % 7


DEPARTMENT_LABELS = {
    "nursing": "Nursing / Care",
    "kitchen": "Dining / Kitchen",
    "housekeeping": "Housekeeping",
    "maintenance": "Maintenance",
    "transportation": "Transportation",
    "activities": "Activities",
    "front_desk": "Front Desk",
    "administration": "Administration / Leadership",
}

# (department, role, number of stable synthetic identities)
_HEADCOUNT = (
    ("nursing", "registered_nurse", 4),
    ("nursing", "medication_reminder_support", 3),
    ("nursing", "care_aide", 15),
    ("kitchen", "cook", 3),
    ("kitchen", "dining_server", 6),
    ("kitchen", "meal_delivery_aide", 9),
    ("housekeeping", "housekeeper", 2),
    ("maintenance", "maintenance_technician", 1),
    ("transportation", "driver", 4),
    ("activities", "activities_coordinator", 1),
    ("front_desk", "front_desk_coordinator", 4),
    ("administration", "business_office_manager", 1),
    ("administration", "administrator", 1),
    ("administration", "executive_director", 1),
)



# Owner direction (Michael, 2026-10-13): an 80-apartment, budget-constrained
# assisted-living community.  Overnight 2-3 care staff are physically present;
# med techs work 7-7 (07:00-19:00 and 19:00-07:00, Michael 2026-10-14);
# maintenance works normal hours plus after-hours ON-CALL (never on site 24 h);
# other departments keep realistic operating hours and are CLOSED otherwise.
#
# Row: (department, job role, shift, start, end, count, duty[, schedule]).  End <=
# start means the window crosses midnight.  The optional schedule names the
# weekdays the row runs ("days") and/or one fixed person ("worker", 1-based);
# rows without one run every day and rotate through the role's people.  ``on_site`` workers are physically
# present; ``on_call`` workers are reachable but off site and never clock in.
ON_SITE = "on_site"
ON_CALL = "on_call"
_SHIFT_LOAD = (
    ("nursing", "care_aide", "day", "06:00", "14:00", 4, ON_SITE),
    ("nursing", "registered_nurse", "day", "06:00", "14:00", 1, ON_SITE),
    ("nursing", "care_aide", "evening", "14:00", "22:00", 3, ON_SITE),
    ("nursing", "registered_nurse", "evening", "14:00", "22:00", 1, ON_SITE),
    ("nursing", "care_aide", "night", "22:00", "06:00", 2, ON_SITE),
    ("nursing", "medication_reminder_support", "med_tech_day", "07:00", "19:00", 1, ON_SITE),
    ("nursing", "medication_reminder_support", "med_tech_night", "19:00", "07:00", 1, ON_SITE),
    ("nursing", "registered_nurse", "night_on_call", "22:00", "06:00", 1, ON_CALL),
    # Service model (CO-008, owner 2026-10-15): the cook holds prep, plating and dish work;
    # dining servers serve residents in parallel at each seating.
    ("kitchen", "cook", "early", "05:30", "13:30", 1, ON_SITE),
    ("kitchen", "cook", "late", "12:00", "20:00", 1, ON_SITE),
    ("kitchen", "dining_server", "early", "06:30", "14:30", 2, ON_SITE),
    ("kitchen", "dining_server", "late", "12:00", "20:00", 2, ON_SITE),
    # Room delivery (owner estimate 2026-10-15): about 30 trays per meal need their own staff.
    ("kitchen", "meal_delivery_aide", "meals_am", "07:15", "13:15", 3, ON_SITE),
    ("kitchen", "meal_delivery_aide", "meals_pm", "16:45", "19:45", 3, ON_SITE),
    # Owner corrections (Michael, 2026-10-15): two named housekeepers on fixed weekly schedules.
    ("housekeeping", "housekeeper", "weekday", "08:00", "16:30", 1, ON_SITE, {"days": MON_FRI, "worker": 1}),
    ("housekeeping", "housekeeper", "midweek_weekend", "08:00", "16:30", 1, ON_SITE, {"days": WED_SUN, "worker": 2}),
    # Owner (2026-10-15): ONE maintenance person. On site on business days, and the same
    # person is the after-hours and weekend on-call contact (no other maintenance staff).
    ("maintenance", "maintenance_technician", "day", "07:00", "15:30", 1, ON_SITE, {"days": MON_FRI, "worker": 1}),
    ("maintenance", "maintenance_technician", "after_hours_on_call", "15:30", "07:00", 1, ON_CALL,
     {"days": MON_FRI, "worker": 1}),
    ("maintenance", "maintenance_technician", "weekend_on_call", "07:00", "07:00", 1, ON_CALL,
     {"days": SAT_SUN, "worker": 1}),
    ("transportation", "driver", "early", "07:30", "15:30", 1, ON_SITE),
    ("transportation", "driver", "late", "09:30", "17:30", 1, ON_SITE),
    # One activities coordinator, no assistant (weekdays: an owner-unconfirmed assumption).
    ("activities", "activities_coordinator", "day", "09:00", "17:00", 1, ON_SITE, {"days": MON_FRI, "worker": 1}),
    ("front_desk", "front_desk_coordinator", "day", "07:00", "15:00", 1, ON_SITE),
    ("front_desk", "front_desk_coordinator", "evening", "15:00", "23:00", 1, ON_SITE),
    # Recognizable front-office roles, one person each, business days.
    ("administration", "business_office_manager", "business", "08:00", "17:00", 1, ON_SITE,
     {"days": MON_FRI, "worker": 1}),
    ("administration", "administrator", "business", "08:00", "17:00", 1, ON_SITE, {"days": MON_FRI, "worker": 1}),
    ("administration", "executive_director", "business", "08:00", "17:00", 1, ON_SITE,
     {"days": MON_FRI, "worker": 1}),
)
