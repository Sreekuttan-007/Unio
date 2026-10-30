"""Synthetic training data for the triage classifier, plus a hand-written holdout.

The training corpus is generated from phrase templates crossed with campus places, with typos and
mixed-language wording. The holdout is written by hand and is never used for training or tuning,
so its score is an honest, if modest, estimate. Both are fictional (PS constraint C2).
"""

import random

CATEGORIES = ("ELECTRICAL", "NETWORK", "PLUMBING", "HVAC", "CARPENTRY", "EQUIPMENT", "HOUSEKEEPING", "SAFETY", "OTHER")

PHRASES: dict[str, list[str]] = {
    "ELECTRICAL": [
        "power is out", "no electricity", "lights are not working", "the lights keep flickering", "socket is sparking", "switch board tripped",
        "fan stopped working", "ceiling fan is making noise", "MCB keeps tripping", "tube light is fused", "no power in the whole floor",
        "power cut", "the plug point is dead", "bulb has burnt out", "short circuit smell from the switch", "light switch is loose",
        "electrical panel tripped", "current is not coming", "fan not rotating", "lights went off suddenly",
    ],
    "NETWORK": [
        "wifi is not working", "no internet", "wi-fi keeps disconnecting", "network is very slow", "cannot connect to the lan",
        "access point is down", "unable to login to campus wifi", "internet speed is terrible", "ethernet port is dead", "wifi signal is weak",
        "network is down", "no connectivity in the room", "wifi keeps dropping", "cannot browse anything", "lan cable is loose",
        "router seems to be off", "the wifi password does not work", "internet not working since morning", "the network switch is blinking red", "wifi not available",
    ],
    "PLUMBING": [
        "tap is leaking", "water is leaking from the pipe", "the toilet is blocked", "no water in the bathroom", "drain is overflowing",
        "flush is not working", "water tank is overflowing", "pipe has burst", "washbasin is clogged", "low water pressure",
        "leakage near the wash area", "the water cooler is leaking", "bathroom floor is flooded", "tap will not close", "dirty water coming from the tap",
        "sewage smell from the drain", "geyser is leaking", "urinal is blocked", "water dripping from the ceiling", "no water supply",
    ],
    "HVAC": [
        "air conditioner is not cooling", "ac is not working", "the ac is making a loud noise", "room is too hot, ac is off", "ac is leaking water",
        "air conditioning broken", "ac remote not working", "ac is blowing warm air", "cooling is poor", "the ac keeps shutting off",
        "ac filter is dirty", "it is very hot because the ac is dead", "split ac stopped", "the ventilation fan is stuck", "the room is freezing, ac stuck on cold",
        "ac compressor sound is odd", "ac not turning on", "exhaust fan is not working", "ac thermostat is faulty", "no cooling in the lab",
    ],
    "CARPENTRY": [
        "door is broken", "door hinge has come off", "the bench is broken", "window glass is cracked", "desk is wobbling",
        "chair leg is broken", "the door will not lock", "cupboard door is loose", "window will not close", "the door handle fell off",
        "whiteboard is hanging loose", "the shelf collapsed", "lock is jammed", "table top is damaged", "broken window latch",
        "door is stuck and will not open", "the wooden partition is broken", "drawer will not open", "the notice board fell down", "ceiling panel is hanging",
    ],
    "EQUIPMENT": [
        "projector is not working", "the projector keeps flickering", "no display on the projector", "hdmi cable is damaged", "microphone is not working",
        "speaker has no sound", "smart board is not responding", "the screen is stuck", "projector lamp has failed", "podium computer will not start",
        "the clicker is dead", "pa system is humming", "projector image is blurry", "the display is blank", "audio is not coming from the speakers",
        "lab computer is not booting", "the printer is jammed", "the visualiser is not working", "projector remote is missing", "mic is giving feedback noise",
    ],
    "HOUSEKEEPING": [
        "the classroom is dirty", "dustbin is overflowing", "floor is not cleaned", "washroom is not clean", "garbage has not been collected",
        "cobwebs on the ceiling", "the corridor is littered", "the room smells bad", "spill on the floor needs cleaning", "benches are dusty",
        "bin is full", "the staircase is dirty", "no soap in the washroom", "tissue paper is not refilled", "mosquitoes and standing water outside",
        "the lab floor has not been swept", "classroom needs sweeping", "pest problem in the canteen area", "toilet needs cleaning", "the lawn waste has not been cleared",
    ],
    "SAFETY": [
        "there is smoke coming from the panel", "burning smell in the room", "fire alarm is ringing", "sparks from the wire", "gas smell in the lab",
        "exposed live wire", "fire extinguisher is missing", "someone got an electric shock", "the stairs are slippery and unsafe", "emergency exit is blocked",
        "smoke from the ac", "a wire is hanging dangerously", "it smells like something is burning", "the railing is broken, unsafe", "chemical spill in the lab",
        "fire exit door is locked", "there is a short circuit and smoke", "glass on the floor, dangerous", "loose ceiling is about to fall", "the lift is stuck with people inside",
    ],
    "OTHER": [
        "i lost my id card", "where is the exam schedule", "need a bonafide certificate", "the notice board has an old notice", "request for a parking sticker",
        "can i get a locker", "question about hostel timings", "suggestion for the cafeteria menu", "need a key for the seminar hall", "how do i book the auditorium",
        "feedback about the new timetable", "please change my section", "found a wallet", "event poster approval", "need access card replacement",
        "update my contact number", "who do i contact for scholarships", "lost and found", "late fee query", "request to extend library hours",
    ],
}

PLACES = (
    "ARB-204", "ARB 205", "arb-101", "ARB-306", "BHB-201", "bhb 105", "RMB-102", "RLB-102", "RLB-205", "LIB-101", "ADM-101", "CAF-102", "KLH-304", "KLH 206",
    "Aryabhata Block", "Bhaskara Block", "Ramanujan block", "the library", "the cafeteria", "Kalam hostel", "the seminar hall", "second floor", "ground floor",
    "lab", "classroom", "our classroom", "the corridor", "my room", "block A", "the staff room",
)

WRAPPERS = (
    "{p} in {loc}", "{loc}: {p}", "please check, {p} at {loc}", "urgent: {p} {loc}", "{p} {loc} da", "{p}, {loc}", "hi, {p} in {loc}. please fix",
    "{p} near {loc}", "{loc} {p}", "{p}", "{p} please", "problem: {p} ({loc})", "sir {p} in {loc}", "{p} in {loc} since morning", "{p} in {loc} and we have a class",
)


def _typo(text: str, rng: random.Random) -> str:
    if len(text) < 8 or rng.random() > 0.25:
        return text
    chars = list(text)
    index = rng.randrange(1, len(chars) - 2)
    kind = rng.choice(("swap", "drop", "double"))
    if kind == "swap":
        chars[index], chars[index + 1] = chars[index + 1], chars[index]
    elif kind == "drop":
        del chars[index]
    else:
        chars.insert(index, chars[index])
    return "".join(chars)


def generate_corpus(size: int = 3000, seed: int = 20261030) -> list[tuple[str, str]]:
    rng = random.Random(seed)
    rows: list[tuple[str, str]] = []
    per_class = size // len(CATEGORIES)
    for category in CATEGORIES:
        for _ in range(per_class):
            phrase = rng.choice(PHRASES[category])
            text = rng.choice(WRAPPERS).format(p=phrase, loc=rng.choice(PLACES))
            text = text.capitalize() if rng.random() < 0.5 else text
            rows.append((_typo(text, rng), category))
    rng.shuffle(rows)
    return rows


# Written by hand, in the voice of real students and staff. Never used for training or tuning.
HOLDOUT: tuple[tuple[str, str], ...] = (
    ("The whole second floor of Aryabhata block has lost power, we have an exam at 9", "ELECTRICAL"),
    ("lights in BHB-105 keep flickering and one tube is buzzing loudly", "ELECTRICAL"),
    ("Switch board near the back door of RMB-102 is hot to touch and the fan stopped", "ELECTRICAL"),
    ("no current in the staff room since lunch", "ELECTRICAL"),
    ("The plug point next to the projector is dead, cannot charge laptops", "ELECTRICAL"),
    ("MCB tripped again in the lab, third time this week", "ELECTRICAL"),
    ("fan in KLH 206 is not rotating even at full speed", "ELECTRICAL"),
    ("Corridor lights on floor 3 are all off", "ELECTRICAL"),
    ("our classroom has no power sockets working", "ELECTRICAL"),
    ("power went off in the library reading hall", "ELECTRICAL"),
    ("Wifi not working in ARB-204 and the exam portal will not load", "NETWORK"),
    ("internet is extremely slow in the hostel since last night", "NETWORK"),
    ("cant connect to campus wifi, it says authentication failed", "NETWORK"),
    ("LAN port in the lab is not giving any connection", "NETWORK"),
    ("the wifi drops every few minutes in BHB block", "NETWORK"),
    ("no network in RLB-205, switch is blinking orange", "NETWORK"),
    ("Students on floor 3 report there is no wifi at all", "NETWORK"),
    ("The access point in the seminar hall seems to be dead", "NETWORK"),
    ("net not working in library, many people complaining", "NETWORK"),
    ("our department cannot reach the internet at all", "NETWORK"),
    ("Tap in the bathroom of KLH-304 is leaking continuously", "PLUMBING"),
    ("water is overflowing from the tank on the terrace", "PLUMBING"),
    ("toilet on the ground floor is blocked and smells", "PLUMBING"),
    ("there is no water supply in the washroom near the canteen", "PLUMBING"),
    ("A pipe above the corridor is dripping on the floor", "PLUMBING"),
    ("flush is stuck in the boys washroom", "PLUMBING"),
    ("The water cooler near the lab is leaking and the floor is wet", "PLUMBING"),
    ("drain outside the cafeteria is clogged", "PLUMBING"),
    ("hostel bathroom is flooded", "PLUMBING"),
    ("sink in the staff pantry will not drain", "PLUMBING"),
    ("AC in RLB-102 is on but the room is still hot", "HVAC"),
    ("the air conditioner in the seminar hall makes a rattling noise", "HVAC"),
    ("ac is dripping water on the desks", "HVAC"),
    ("Cooling is not working in the server room", "HVAC"),
    ("split ac in the principal's room will not start", "HVAC"),
    ("ac in lab 2 keeps switching itself off", "HVAC"),
    ("the exhaust fan in the chemistry lab is stuck", "HVAC"),
    ("It is boiling in this classroom, ac must be broken", "HVAC"),
    ("AC remote is missing and temperature is stuck at 16", "HVAC"),
    ("room is not cooling even after an hour", "HVAC"),
    ("The door of ARB-301 does not close properly, the hinge has come loose", "CARPENTRY"),
    ("desk in the front row is broken", "CARPENTRY"),
    ("window pane cracked in BHB-203", "CARPENTRY"),
    ("lock on the staff room door is jammed, nobody can get in", "CARPENTRY"),
    ("two benches in our class have broken legs", "CARPENTRY"),
    ("The cupboard door in the lab fell off", "CARPENTRY"),
    ("whiteboard is falling off the wall", "CARPENTRY"),
    ("door handle came off in my hand", "CARPENTRY"),
    ("wooden partition in the library is cracked", "CARPENTRY"),
    ("chair in the seminar hall wobbles badly", "CARPENTRY"),
    ("Projector in ARB-205 flickers after ten minutes", "EQUIPMENT"),
    ("the mic in the seminar hall gives a loud buzzing noise", "EQUIPMENT"),
    ("HDMI cable of the projector is torn", "EQUIPMENT"),
    ("podium PC does not turn on", "EQUIPMENT"),
    ("smart board is not responding to touch", "EQUIPMENT"),
    ("speakers give no sound in the auditorium", "EQUIPMENT"),
    ("projector shows a blue screen and nothing else", "EQUIPMENT"),
    ("The printer in the department office is jammed again", "EQUIPMENT"),
    ("lab computers in row 3 are not booting", "EQUIPMENT"),
    ("clicker battery is dead and we have a presentation", "EQUIPMENT"),
    ("Classroom was not cleaned today, there is litter everywhere", "HOUSEKEEPING"),
    ("dustbins in the corridor are overflowing", "HOUSEKEEPING"),
    ("washroom on floor 2 is very dirty and there is no soap", "HOUSEKEEPING"),
    ("garbage near the back gate has not been picked up for days", "HOUSEKEEPING"),
    ("lab floor needs sweeping, there is dust everywhere", "HOUSEKEEPING"),
    ("the cafeteria tables are sticky and unwashed", "HOUSEKEEPING"),
    ("there are mosquitoes breeding in the water near the hostel", "HOUSEKEEPING"),
    ("staircase has not been mopped and is full of dust", "HOUSEKEEPING"),
    ("bad smell in the room, dustbin has not been emptied", "HOUSEKEEPING"),
    ("The common room is untidy and the bin is full", "HOUSEKEEPING"),
    ("there is smoke coming out of the electrical panel near the stairs", "SAFETY"),
    ("burning smell in the corridor, please check immediately", "SAFETY"),
    ("An exposed wire is hanging from the ceiling in the lab", "SAFETY"),
    ("fire extinguisher on floor 1 is missing from its stand", "SAFETY"),
    ("someone got a small shock from the switch board", "SAFETY"),
    ("the emergency exit is blocked by furniture", "SAFETY"),
    ("sparks flew from the socket when I plugged in my charger", "SAFETY"),
    ("floor near the entrance is wet and very slippery, someone may fall", "SAFETY"),
    ("lift stopped between floors with people inside", "SAFETY"),
    ("gas smell from the chemistry lab store", "SAFETY"),
    ("I lost my ID card somewhere near the library", "OTHER"),
    ("what time does the library close during exams", "OTHER"),
    ("need a bonafide certificate for my bank", "OTHER"),
    ("can the auditorium be booked for a cultural event next month", "OTHER"),
    ("i found a wallet near the cafeteria", "OTHER"),
    ("request to change my elective section", "OTHER"),
    ("How do I get a hostel mess refund", "OTHER"),
    ("Please update my phone number in the records", "OTHER"),
    ("who is the contact for scholarship queries", "OTHER"),
    ("feedback: the new timetable has too many gaps", "OTHER"),
)
