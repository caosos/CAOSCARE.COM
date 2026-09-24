"""Generated spoken forms of numbers, dates and times (deterministic)."""

ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
        "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
        "seventeen", "eighteen", "nineteen"]
TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth",
            "ninth", "tenth", "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth",
            "sixteenth", "seventeenth", "eighteenth", "nineteenth", "twentieth", "thirtieth"]
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]


def number_words(n):
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10 - 2] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    return ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + number_words(n % 100))


def numbers_dates_times():
    out = [number_words(n) for n in range(0, 101)]
    out += ORDINALS + ["twenty " + o for o in ORDINALS[:9]] + ["thirty first"]
    out += DAYS + MONTHS + ["today", "tomorrow", "yesterday", "tonight", "this morning",
                            "this afternoon", "this evening", "next week", "last week"]
    for h in range(1, 13):
        hw = ONES[h]
        out += [f"{hw} o'clock", f"{hw} fifteen", f"{hw} thirty", f"{hw} forty five",
                f"{hw} a m", f"{hw} p m", f"half past {hw}", f"quarter to {hw}"]
    return sorted(set(out))
