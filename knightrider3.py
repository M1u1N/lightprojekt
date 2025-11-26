from etherlightwin import Etherlight
import time
import traceback

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
    if n <= 1:
        return 0
    period = 2 * n - 2
    cyc = step % period
    if cyc < n:
        return cyc
    else:
        return period - cyc

def build_frame_for_row(row, step):
    n = len(row)
    pos = compute_pingpong_pos(step, n)

    if n <= 1:
        direction = 1
    else:
        prev_pos = compute_pingpong_pos(step - 1, n)
        if pos > prev_pos:
            direction = 1
        elif pos < prev_pos:
            direction = -1
        else:
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
        try_set(pos - 1, 'trail1')
        try_set(pos - 2, 'trail2')
        try_set(pos - 3, 'trail3')
    else:
        try_set(pos + 1, 'trail1')
        try_set(pos + 2, 'trail2')
        try_set(pos + 3, 'trail3')

    # Rückgabe als mapping led -> Farbname (nicht RGB, damit Priorität leichter zu handhaben ist)
    return {led: color_name for led, color_name in frame.items()}

def animate_rows(etherlight, rows, step_delay=0.06, max_retries=3):
    """
    Animation mit Pause und einfacher Fehlerbehandlung / Wiederholungslogik.
    """
    # alle verwendeten LEDs sammeln (einmalig)
    all_leds = set()
    for r in rows:
        all_leds.update(r)
    all_leds = sorted(all_leds)

    step = 0
    retries = 0
    try:
        while True:
            # Baseline: alle LEDs auf 'off' setzen
            merged_updates = {led: ('off', COLOR_MAP['off']) for led in all_leds}

            # Für jede Reihe ein Frame bauen und nach Priorität mergen
            for row in rows:
                frame = build_frame_for_row(row, step)
                for led, color_name in frame.items():
                    curr_name, _curr_rgb = merged_updates.get(led, ('off', COLOR_MAP['off']))
                    if COLOR_PRIORITY[color_name] > COLOR_PRIORITY[curr_name]:
                        merged_updates[led] = (color_name, COLOR_MAP[color_name])

            # Batch-Aufruf in try/except, damit wir Fehler sehen und ggf. neu versuchen können
            try:
                if merged_updates:
                    led_colors = [(led, rgb, 100) for led, (_name, rgb) in merged_updates.items()]
                    etherlight.batch_set_leds(led_colors)
                retries = 0  # Erfolg → Rücksetzen der Retry-Zahl
            except Exception as e:
                # Logging der Exception + Backoff
                print(f"[ERROR] batch_set_leds fehlgeschlagen: {e}")
                traceback.print_exc()
                retries += 1
                if retries > max_retries:
                    print("[ERROR] Maximale Wiederholungen erreicht — breche Animation ab.")
                    break
                backoff = min(1.0, 0.1 * retries)
                print(f"[INFO] Warte {backoff}s, bevor ich neu versuche...")
                time.sleep(backoff)
                # retry: gleiche step-Nummer wieder versuchen (oder optional step += 1)
                continue

            step += 1
            # wichtig: sleep, sonst busy-loop
            time.sleep(step_delay)

    except KeyboardInterrupt:
        print("\nAnimation per KeyboardInterrupt gestoppt.")
    finally:
        # Ausschalten aller LEDs der benutzten Reihen — per Batch
        if all_leds:
            try:
                off_list = [(led, COLOR_MAP['off'], 100) for led in all_leds]
                etherlight.batch_set_leds(off_list)
            except Exception:
                # Wenn Ausschalten fehlschlägt, wenigstens Traceback anzeigen
                print("[WARN] Ausschalten der LEDs fehlgeschlagen:")
                traceback.print_exc()

def run_sw(sw_ip, rows_to_run, user="root"):
    try:
        with Etherlight(sw_ip, user) as etherlight:
            # Initial ausschalten (ein Batch-Aufruf)
            leds_to_init = set()
            for r in rows_to_run:
                leds_to_init.update(r)
            if leds_to_init:
                init_list = [(led, COLOR_MAP['off'], 100) for led in leds_to_init]
                etherlight.batch_set_leds(init_list)

            animate_rows(etherlight, rows_to_run, step_delay=0.06)

    except Exception as e:
        print(f"[FATAL] Verbindung / Betrieb fehlgeschlagen: {e}")
        traceback.print_exc()

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

# hier user="root" gesetzt (wenn du lieber 'nwlab' willst: user="nwlab")
run_sw(SWITCH_IP, rows, user="nwlab")
