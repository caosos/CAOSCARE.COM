"""What a scheduled simulated ticket says to the worker: the work and why.

Owner (#168): "Scheduled simulated night room check." told a worker nothing.
Each routine gets a plain label and the reason the work is needed; the ticket
title and description read "<Label>: <why>". Resident calls and staff reports
keep their own wording (community_player_requests). Ticket text only - not
part of the plan, so it never changes a run's plan digest. Simulation
wording; no clinical assessment or medication administration is implied.
"""

ROUTINE_TEXT = {
    "overnight_room_check": ("Overnight room check",
                             "check the resident is safe and comfortable and the call light is in reach"),
    "morning_room_check": ("Morning room check",
                           "greet the resident, check they are safe and ask what they need this morning"),
    "night_room_check": ("Night room check",
                         "check the resident is settled for the night and the call light is in reach"),
    "toileting_transfer_support": ("Morning toileting / transfer help",
                                   "scheduled help to the bathroom or out of bed per the care plan"),
    "afternoon_toileting_transfer_support": ("Afternoon toileting / transfer help",
                                             "scheduled help to the bathroom or chair per the care plan"),
    "evening_toileting_transfer_support": ("Evening toileting / transfer help",
                                           "scheduled help to the bathroom or into bed per the care plan"),
    "morning_medication_reminder": ("Morning medication reminder",
                                    "remind the resident it is time for morning medications (reminder only)"),
    "evening_medication_reminder": ("Evening medication reminder",
                                    "remind the resident it is time for evening medications (reminder only)"),
    "shower_assistance": ("Shower assistance",
                          "offer the scheduled shower; the resident may decline or reschedule"),
    "breakfast": ("Breakfast service", "serve the resident's breakfast (service only; intake is not recorded)"),
    "lunch": ("Lunch service", "serve the resident's lunch (service only; intake is not recorded)"),
    "dinner": ("Dinner service", "serve the resident's dinner (service only; intake is not recorded)"),
    "breakfast_room_service": ("Breakfast to the apartment",
                               "carry the resident's breakfast to the apartment (service only; intake is not recorded)"),
    "lunch_room_service": ("Lunch to the apartment",
                           "carry the resident's lunch to the apartment (service only; intake is not recorded)"),
    "dinner_room_service": ("Dinner to the apartment",
                            "carry the resident's dinner to the apartment (service only; intake is not recorded)"),
    "housekeeping_room_service": ("Room cleaning and linens", "scheduled clean of the apartment and linen change"),
    "activity_escort": ("Escort to the activity",
                        "the resident needs help getting to today's group activity"),
    "one_to_one_activity_visit": ("One-to-one activity visit",
                                  "the resident prefers a one-to-one activity in the apartment"),
    "preventive_maintenance_check": ("Preventive maintenance check",
                                     "scheduled inspection of the apartment's fixtures and safety devices"),
    "appointment_coordination": ("Appointment coordination",
                                 "confirm the resident's appointment details with staff (no provider contact claimed)"),
    "transport_coordination": ("Ride coordination",
                               "arrange the ride for the appointment (no vehicle or driver is booked)"),
    "family_call_coordination": ("Family call request",
                                 "the resident asked to reach family; coordinate the call (no call is placed)"),
    "front_desk_message_follow_up": ("Message for the front desk",
                                     "route the resident's message to the right staff for follow-up"),
}


def routine_summary(action_type: str):
    """'<Label>: <why>.' for a known routine, else None."""
    text = ROUTINE_TEXT.get(action_type)
    if not text:
        return None
    label, why = text
    return f"{label}: {why}."
