# Regenerate: python3 frontend/scripts/generate_public_illustrations.py frontend/public/media/illustrations
# Generates the public capability illustrations (#162). One style for all:
# white/gray ground, ink lines, CAOSCare blue accent, green for "done" states.
import sys, html
OUT = sys.argv[1]
INK, BLUE, PALE, LINE, GREEN, MUTE = "#111827", "#2F80ED", "#EFF6FF", "#E5E7EB", "#16A34A", "#6B7280"
FONT = "Inter, 'Helvetica Neue', Arial, sans-serif"

def svg(name, title, body):
    s = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" width="1600" height="900" role="img" aria-labelledby="t">
<title id="t">{html.escape(title)}</title>
<rect width="1600" height="900" fill="#F9FAFB"/>
<g font-family="{FONT}" fill="none" stroke-linecap="round" stroke-linejoin="round">{body}</g>
</svg>
'''
    open(f"{OUT}/{name}.svg", "w").write(s)

def text(x, y, t, size=34, color=INK, weight=500, anchor="start"):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" stroke="none" text-anchor="{anchor}">{html.escape(t)}</text>'

def bubble(x, y, w, lines, fill="#FFFFFF", color=INK, tail="left", size=32):
    h = 40 + 46 * len(lines)
    tx = x + 60 if tail == "left" else x + w - 60
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="28" fill="{fill}" stroke="{LINE}" stroke-width="3"/>'
    s += f'<path d="M{tx-18} {y+h-2} L{tx-30 if tail=="left" else tx+30} {y+h+34} L{tx+18} {y+h-2}" fill="{fill}" stroke="{LINE}" stroke-width="3"/>'
    s += f'<rect x="{tx-20}" y="{y+h-8}" width="40" height="8" fill="{fill}" stroke="none"/>'
    for i, l in enumerate(lines):
        s += text(x + 32, y + 62 + 46 * i, l, size, color)
    return s

def card(x, y, w, h, rows, accent=BLUE):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="22" fill="#FFFFFF" stroke="{LINE}" stroke-width="3"/>'
    s += f'<rect x="{x}" y="{y}" width="10" height="{h}" rx="5" fill="{accent}" stroke="none"/>'
    for i, (t, size, color, weight) in enumerate(rows):
        s += text(x + 40, y + 58 + 50 * i, t, size, color, weight)
    return s

def chair(x, y):  # armchair with seated resident, facing right
    return (f'<rect x="{x}" y="{y}" width="260" height="300" rx="50" fill="#DBEAFE" stroke="{INK}" stroke-width="6"/>'
            f'<rect x="{x-30}" y="{y+150}" width="320" height="170" rx="40" fill="#BFDBFE" stroke="{INK}" stroke-width="6"/>'
            f'<rect x="{x}" y="{y+300}" width="20" height="60" fill="{INK}" stroke="none"/><rect x="{x+240}" y="{y+300}" width="20" height="60" fill="{INK}" stroke="none"/>'
            f'<circle cx="{x+150}" cy="{y+40}" r="52" fill="#FDE7D3" stroke="{INK}" stroke-width="6"/>'
            f'<path d="M{x+70} {y+250} C{x+70} {y+120} {x+230} {y+120} {x+230} {y+250}" fill="#93C5FD" stroke="{INK}" stroke-width="6"/>')

# 1. Talk to Aria - voice first, the room display only supports
b = '<rect x="0" y="720" width="1600" height="180" fill="#F3F4F6" stroke="none"/>'
b += f'<rect x="980" y="120" width="480" height="290" rx="20" fill="{INK}"/><rect x="1004" y="144" width="432" height="242" rx="10" fill="#FFFFFF"/>'
b += text(1220, 220, "Hello, Sam.", 44, INK, 700, "middle") + text(1220, 270, "Nursing request · sent", 26, GREEN, 600, "middle") + text(1220, 314, "Lunch 12:00 · Concert 2 PM", 24, MUTE, 400, "middle")
b += text(1220, 450, "Room display: supporting information", 24, MUTE, 400, "middle")
b += f'<rect x="1080" y="560" width="70" height="110" rx="20" fill="#FFFFFF" stroke="{INK}" stroke-width="5"/><circle cx="1115" cy="640" r="16" fill="{BLUE}" stroke="none"/>' + text(1115, 705, "Speaker + mic", 22, MUTE, 400, "middle")
b += chair(110, 400)
b += bubble(80, 90, 700, ["Hey Aria, could someone help", "me to the bathroom?"], tail="left")
b += bubble(470, 440, 470, ["I've sent that to nursing.", "I'll tell you when", "someone takes it."], fill=PALE, tail="right")
svg("talk-to-aria", "Illustration: a resident in an armchair says \"Hey Aria\" and asks for help; Aria answers by voice and the room display shows the request status", b)

# 2. Pendant / one-press help
b = f'<path d="M330 120 C250 300 250 420 330 520 M330 120 C410 300 410 420 330 520" stroke="{MUTE}" stroke-width="5"/>'
b += f'<circle cx="330" cy="600" r="120" fill="#FFFFFF" stroke="{INK}" stroke-width="8"/><circle cx="330" cy="600" r="70" fill="#DC2626" stroke="{INK}" stroke-width="6"/>' + text(330, 612, "HELP", 34, "#FFFFFF", 800, "middle")
for r in (60, 100, 140):
    b += f'<path d="M{500+r*0.2} {600-r} A{r} {r} 0 0 1 {500+r*0.2} {600+r}" stroke="{BLUE}" stroke-width="7"/>'
b += f'<rect x="700" y="520" width="200" height="160" rx="22" fill="#FFFFFF" stroke="{INK}" stroke-width="6"/>' + text(800, 615, "Receiver", 30, INK, 600, "middle") + text(800, 720, "in the room", 26, MUTE, 400, "middle")
b += f'<path d="M920 600 L1020 600" stroke="{INK}" stroke-width="6"/><path d="M1000 580 L1024 600 L1000 620" stroke="{INK}" stroke-width="6"/>'
b += card(1050, 430, 470, 260, [("Help call · Room 12", 34, INK, 700), ("Pendant press · signal good", 28, MUTE, 400), ("Battery OK · Aria is talking", 28, MUTE, 400), ("Waiting for staff", 28, "#B45309", 600)], "#DC2626")
b += text(330, 820, "One press on a paired pendant", 30, INK, 600, "middle")
svg("pendant-help", "Illustration: a paired help pendant is pressed; a receiver in the room decodes it and a help call appears for staff with signal and battery", b)

# 3. Wearables (planned)
b = f'<rect x="420" y="150" width="240" height="600" rx="110" fill="#DBEAFE" stroke="{INK}" stroke-width="7"/>'
b += f'<rect x="380" y="330" width="320" height="240" rx="60" fill="#FFFFFF" stroke="{INK}" stroke-width="8"/><rect x="420" y="370" width="240" height="160" rx="30" fill="{INK}"/>'
b += text(540, 440, "10:42", 46, "#FFFFFF", 700, "middle") + text(540, 492, "Help · hold 2 s", 24, "#93C5FD", 500, "middle")
b += f'<rect x="700" y="420" width="22" height="60" rx="8" fill="{BLUE}" stroke="none"/>'
b += card(900, 230, 560, 170, [("Approved device list", 34, INK, 700), ("chosen per community", 28, MUTE, 400)], BLUE)
b += card(900, 450, 560, 220, [("Resident consent", 34, INK, 700), ("shares only what they agree to", 28, MUTE, 400), ("e.g. help press, not location", 28, MUTE, 400)], GREEN)
b += text(540, 820, "Wristband concept", 30, INK, 600, "middle")
svg("wearable-wristband", "Concept illustration: an approved wristband with a help button, sharing only the data the resident consents to", b)

# 4. Motorized blinds (planned)
b = f'<rect x="250" y="110" width="620" height="660" rx="16" fill="#E0F2FE" stroke="{INK}" stroke-width="8"/>'
b += f'<rect x="230" y="90" width="660" height="40" rx="10" fill="{INK}"/>'
for i in range(8):
    b += f'<rect x="262" y="{140+i*34}" width="596" height="26" rx="6" fill="#FFFFFF" stroke="{INK}" stroke-width="3"/>'
b += f'<circle cx="420" cy="620" r="70" fill="#FDE68A" stroke="none"/><path d="M250 770 L870 770" stroke="{INK}" stroke-width="8"/>'
b += f'<path d="M880 150 L880 420" stroke="{MUTE}" stroke-width="5"/><rect x="866" y="420" width="28" height="60" rx="10" fill="{MUTE}" stroke="none"/>'
b += bubble(960, 200, 520, ["Aria, open the", "blinds halfway."], tail="left")
b += bubble(960, 470, 520, ["The blinds report", "50% open."], fill=PALE, tail="left")
svg("motorized-blinds", "Concept illustration: a resident asks Aria to open the blinds halfway and Aria confirms only the position the blinds report", b)

# 5. Building-wide location (planned)
b = f'<rect x="120" y="110" width="900" height="680" rx="20" fill="#FFFFFF" stroke="{INK}" stroke-width="6"/>'
rooms = [(140,130,260,200,"Room 10"),(420,130,260,200,"Room 12"),(700,130,300,200,"Library"),(140,560,420,210,"Dining room"),(580,560,420,210,"Activity room")]
for x,y,w,h,l in rooms:
    b += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#F3F4F6" stroke="{LINE}" stroke-width="4"/>' + text(x+w/2, y+h/2+10, l, 28, MUTE, 500, "middle")
b += f'<rect x="140" y="350" width="860" height="190" fill="#FFFFFF" stroke="none"/>' + text(570, 455, "Hallway", 28, "#9CA3AF", 500, "middle")
for r,o in ((80,0.15),(50,0.3)):
    b += f'<circle cx="470" cy="610" r="{r}" fill="{BLUE}" fill-opacity="{o}" stroke="none"/>'
b += f'<circle cx="470" cy="610" r="22" fill="{BLUE}" stroke="#FFFFFF" stroke-width="6"/>'
b += card(1070, 300, 450, 270, [("Help call", 34, INK, 700), ("Last known area:", 28, MUTE, 400), ("Dining room", 30, INK, 600), ("with resident consent", 26, MUTE, 400)], "#DC2626")
svg("building-location", "Concept illustration: a building floor plan showing a help call's last known area, the dining room, shared only with consent", b)

# 6. Family connection (planned) - authorized updates, not calls
b = chair(120, 430)
b += bubble(80, 120, 640, ["Aria, let my daughter know", "I'm going to the concert."], tail="left")
b += f'<rect x="980" y="90" width="400" height="720" rx="56" fill="{INK}"/><rect x="1004" y="150" width="352" height="600" rx="18" fill="#FFFFFF"/>'
b += text(1180, 215, "Anna · Daughter", 28, INK, 700, "middle") + text(1180, 252, "authorized family", 22, GREEN, 600, "middle")
b += f'<rect x="1030" y="290" width="300" height="190" rx="22" fill="{PALE}" stroke="none"/>'
b += text(1050, 340, "Update from Mom", 26, INK, 700) + text(1050, 382, "Going to the 2 PM", 26, INK, 400) + text(1050, 420, "concert today.", 26, INK, 400) + text(1050, 458, "Sent via CAOSCare", 20, MUTE, 400)
b += text(1180, 560, "Only what she", 24, MUTE, 400, "middle") + text(1180, 594, "chooses to share.", 24, MUTE, 400, "middle")
b += f'<path d="M760 330 C840 330 880 380 960 380" stroke="{BLUE}" stroke-width="6" stroke-dasharray="14 12"/><path d="M944 362 L966 381 L944 400" stroke="{BLUE}" stroke-width="6"/>'
svg("family-updates", "Concept illustration: a resident asks Aria to tell her daughter she is going to a concert; an update reaches only authorized family, with only what the resident chooses to share", b)

# 7. Phone and calling (in development)
b = f'<path d="M300 520 L700 520 L760 760 L240 760 Z" fill="#FFFFFF" stroke="{INK}" stroke-width="8"/>'
b += f'<path d="M260 470 C260 360 740 360 740 470 L700 520 L620 520 L600 470 L400 470 L380 520 L300 520 Z" fill="#DBEAFE" stroke="{INK}" stroke-width="8"/>'
b += f'<rect x="420" y="580" width="160" height="110" rx="14" fill="#F3F4F6" stroke="{LINE}" stroke-width="4"/>'
b += bubble(160, 110, 620, ["Aria, call the", "front desk."], tail="left")
b += card(920, 230, 560, 330, [("Call · Front desk", 34, INK, 700), ("Approved contact ✓", 28, GREEN, 600), ("Status told truthfully:", 28, MUTE, 400), ("ringing · connected · no answer", 28, MUTE, 400), ("never \"connected\" by guess", 28, MUTE, 400)], BLUE)
svg("phone-calling", "Concept illustration: a simple handset and a resident asking Aria to call the front desk; the call status is reported only as it really happened", b)

# 8. Beauty shop (planned)
b = f'<rect x="230" y="600" width="380" height="60" rx="20" fill="{INK}"/><rect x="400" y="660" width="40" height="110" fill="{INK}" stroke="none"/><rect x="300" y="770" width="240" height="24" rx="12" fill="{INK}" stroke="none"/>'
b += f'<rect x="250" y="300" width="340" height="320" rx="60" fill="#FCE7F3" stroke="{INK}" stroke-width="7"/><rect x="200" y="470" width="440" height="80" rx="30" fill="#FBCFE8" stroke="{INK}" stroke-width="7"/>'
b += f'<rect x="280" y="110" width="280" height="160" rx="80" fill="#FFFFFF" stroke="{INK}" stroke-width="6"/>' + text(420, 205, "Salon", 36, INK, 700, "middle")
b += card(860, 200, 600, 200, [("Request: haircut Thursday", 32, INK, 700), ("Waiting for the salon", 28, "#B45309", 600)], "#D97706")
b += card(860, 470, 600, 200, [("Booked only when", 32, INK, 700), ("the salon confirms", 28, GREEN, 600)], GREEN)
svg("beauty-salon", "Concept illustration: a salon chair and a haircut request that is booked only after the salon confirms", b)

# 9. Television by infrared (pilot)
b = f'<rect x="760" y="140" width="720" height="430" rx="22" fill="{INK}"/><rect x="784" y="164" width="672" height="382" rx="10" fill="#1E3A8A"/>'
b += text(1120, 370, "Sound muted while Aria talks", 32, "#FFFFFF", 600, "middle")
b += f'<rect x="1080" y="570" width="80" height="60" fill="{INK}" stroke="none"/><rect x="980" y="630" width="280" height="22" rx="10" fill="{INK}" stroke="none"/>'
b += f'<rect x="420" y="560" width="150" height="90" rx="20" fill="#FFFFFF" stroke="{INK}" stroke-width="6"/><circle cx="545" cy="605" r="14" fill="#DC2626" stroke="none"/>' + text(495, 700, "Infrared adapter", 26, MUTE, 400, "middle")
for i,o in enumerate((0.5,0.35,0.2)):
    b += f'<path d="M590 {585-i*30} Q680 {470-i*40} 760 {420-i*30}" stroke="{BLUE}" stroke-opacity="{o+0.3}" stroke-width="6" stroke-dasharray="16 12"/>'
b += bubble(80, 140, 560, ["Aria, turn my", "TV down."], tail="left")
b += text(495, 780, "One-way: the command is sent, not read back", 26, INK, 600, "middle")
svg("tv-infrared", "Illustration: Aria sends an infrared command to the room's TV and mutes it while she talks; infrared cannot read back the TV's state", b)
print("ok")
