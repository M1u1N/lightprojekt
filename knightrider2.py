from etherlightwin import Etherlight

# Nur ein Switch
SWITCH_IP = "172.16.26.138"

# Welche Reihe soll laufen?
# Möglichkeiten: "first", "second", "both"
CHOOSE = "both"   # <- hier ändern!

FIRST_ROW = [
    1,3,5,7,9,11,13,15,
    17,19,21,23,25,27,29,31,
    33,35,37,39,41,43,45,47
]

SECOND_ROW = [
    2,4,6,8,10,12,14,16,
    18,20,22,24,26,28,30,32,
    34,36,38,40,42,44,46,48
]

# Farben (Name -> RGB)
COLOR_MAP = {
    'main':   (190, 0, 0),
    'trail1': (255, 0, 0),
    'trail2': (220, 0, 0),
    'trail3': (100, 0, 0),
    'off':    (0, 0, 0)
}

# Priorität für Überlappungen
COLOR_PRIORITY = {
    'off': 0,
    'trail3': 1,
    'trail2': 2,
    'trail1': 3,
    'main': 4
}

def compute_pingpong_pos(step, n):
    """
    Berechnet die Position (0..n-1) auf einer Strecke der Länge n
    mit Ping-Pong (hin und zurück). Für n==1 immer 0.
    """
    if n <= 1:
        return 0
    period = 2 * n - 2  # z.B. n=5 -> period=8: 0,1,2,3,4,3,2,1
    cyc = step % period
    if cyc < n:
        return cyc
    else:
        return period - cyc

def build_frame_for_row(row, step):
    """
    Erzeugt ein Frame für eine einzelne Reihe mit einem Kopf, der
    ping-pong (hin und zurück) läuft. Trails folgen 'hinter' dem Kopf
    je nach aktuellem Bewegungsrichtung.
    """
    n = len(row)
    pos = compute_pingpong_pos(step, n)

    # Bestimme die Bewegungsrichtung anhand der vorherigen Position
    if n <= 1:
        direction = 1
    else:
        prev_pos = compute_pingpong_pos(step - 1, n)
        if pos > prev_pos:
            direction = 1   # bewegt sich nach rechts (Index steigt)
        elif pos < prev_pos:
            direction = -1  # bewegt sich nach links (Index fällt)
        else:
            # selten (z.B. bei n==2), default nach rechts
            direction = 1

    frame = {}

    def try_set(idx_in_row, color_name):
        if 0 <= idx_in_row < n:
            led = row[idx_in_row]
            existing = frame.get(led)
            if existing is None or COLOR_PRIORITY[color_name] > COLOR_PRIORITY[existing]:
                frame[led] = color_name

    # Hauptlicht (Kopf)
    try_set(pos, 'main')

    # Trails je nach Richtung hinter dem Kopf platzieren
    if direction == 1:
        # Kopf bewegt sich nach rechts -> Trails links vom Kopf
        try_set(pos - 1, 'trail1')
        try_set(pos - 2, 'trail2')
        try_set(pos - 3, 'trail3')
        try_set(pos - 4, 'off')
        # kleinen 'Sicherheits'-Off rechts vom Kopf setzen (optional)
        try_set(pos + 1, 'off')
    else:
        # Kopf bewegt sich nach links -> Trails rechts vom Kopf
        try_set(pos + 1, 'trail1')
        try_set(pos + 2, 'trail2')
        try_set(pos + 3, 'trail3')
        try_set(pos + 4, 'off')
        # kleinen 'Sicherheits'-Off links vom Kopf setzen (optional)
        try_set(pos - 1, 'off')

    return {row_idx: COLOR_MAP[color] for row_idx, color in frame.items()}


def animate_rows(etherlight, rows):
    lengths = [len(r) for r in rows]
    max_len = max(lengths)

    inv_color_map = {v: k for k, v in COLOR_MAP.items()}

    try:
        step = 0
        while True:
            merged_updates = {}  # led -> (color_name, rgb)

            for row in rows:
                frame = build_frame_for_row(row, step)
                for led, rgb in frame.items():
                    incoming_name = inv_color_map[rgb]
                    if led not in merged_updates:
                        merged_updates[led] = (incoming_name, rgb)
                    else:
                        current_name, current_rgb = merged_updates[led]
                        if COLOR_PRIORITY[incoming_name] > COLOR_PRIORITY[current_name]:
                            merged_updates[led] = (incoming_name, rgb)

            for led, (_name, rgb) in merged_updates.items():
                etherlight.set_led_color(led, rgb)

            step += 1

    except KeyboardInterrupt:
        print("\nAnimation gestoppt.")
    finally:
        # Ausschalten aller LEDs der benutzten Reihen
        all_leds = set()
        for r in rows:
            all_leds.update(r)
        for led in all_leds:
            etherlight.set_led_color(led, COLOR_MAP['off'])


def run_sw(sw_ip, rows_to_run, user="neubauer"):
    etherlight = Etherlight(sw_ip, user)

    # Initial ausschalten
    leds_to_init = set()
    for r in rows_to_run:
        leds_to_init.update(r)
    for led in leds_to_init:
        etherlight.set_led_color(led, COLOR_MAP['off'])

    animate_rows(etherlight, rows_to_run)


# -------------------------------
# Auswahllogik über Variable
# -------------------------------
if CHOOSE.lower() == "first":
    rows = [FIRST_ROW]
    print("Starte erste Reihe")
elif CHOOSE.lower() == "second":
    rows = [SECOND_ROW]
    print("Starte zweite Reihe")
elif CHOOSE.lower() == "both":
    rows = [FIRST_ROW, SECOND_ROW]
    print("Starte beide Reihen")
else:
    rows = [FIRST_ROW]
    print("Ungültig – starte erste Reihe")

run_sw(SWITCH_IP, rows, user="nwlab")
