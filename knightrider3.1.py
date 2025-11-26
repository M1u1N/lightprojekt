from etherlightwin import Etherlight

# Nur ein Switch
SWITCH_IP = "172.16.26.138"

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

# Farben (Name -> RGB) mit Alpha-Werten - 5 LEDs gleichzeitig
COLOR_MAP = {
    'main':   ((190, 0, 0), 255),    # maximale Helligkeit
    'trail1': ((255, 0, 0), 180),    # hell
    'trail2': ((220, 0, 0), 100),    # mittel
    'trail3': ((100, 0, 0), 30),     # sehr gedimmt
    'trail4': ((50, 0, 0), 15),      # neu: noch dunkler
    'off':    ((0, 0, 0), 0)         # aus
}

# Priorität für Überlappungen
COLOR_PRIORITY = {
    'off': 0,
    'trail4': 1,
    'trail3': 2,
    'trail2': 3,
    'trail1': 4,
    'main': 5
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

    # 4 Trails je nach Richtung hinter dem Kopf platzieren
    if direction == 1:
        try_set(pos - 1, 'trail1')
        try_set(pos - 2, 'trail2')
        try_set(pos - 3, 'trail3')
        try_set(pos - 4, 'trail4')
    else:
        try_set(pos + 1, 'trail1')
        try_set(pos + 2, 'trail2')
        try_set(pos + 3, 'trail3')
        try_set(pos + 4, 'trail4')

    return {led: color_name for led, color_name in frame.items()}

def animate_rows(etherlight, rows):
    """
    Animation ohne jegliche Delays - maximale Geschwindigkeit
    """
    # Alle verwendeten LEDs sammeln
    all_leds = set()
    for r in rows:
        all_leds.update(r)
    all_leds = sorted(all_leds)

    step = 0
    error_count = 0
    max_errors = 10
    
    try:
        while True:
            try:
                # Baseline: alle LEDs auf 'off' setzen
                merged_updates = {led: ('off', COLOR_MAP['off'][0], COLOR_MAP['off'][1]) for led in all_leds}

                # Für jede Reihe ein Frame bauen
                for row in rows:
                    frame = build_frame_for_row(row, step)
                    for led, color_name in frame.items():
                        curr_name, curr_rgb, curr_alpha = merged_updates.get(led, ('off', COLOR_MAP['off'][0], COLOR_MAP['off'][1]))
                        if COLOR_PRIORITY[color_name] > COLOR_PRIORITY[curr_name]:
                            rgb, alpha = COLOR_MAP[color_name]
                            merged_updates[led] = (color_name, rgb, alpha)

                # Batch-Aufruf mit Alpha-Werten
                if merged_updates:
                    led_colors = []
                    for led, (_name, rgb, alpha) in merged_updates.items():
                        led_colors.append((led, rgb, alpha))

                    success = etherlight.batch_set_leds(led_colors)
                    if not success:
                        error_count += 1
                        if error_count >= max_errors:
                            print(f"\n⚠ Zu viele Fehler ({error_count}), beende Animation")
                            break
                    else:
                        error_count = 0  # Reset bei Erfolg

                step += 1

            except Exception as e:
                error_count += 1
                print(f"\n⚠ Fehler in Animation: {e}")
                if error_count >= max_errors:
                    print("Zu viele Fehler, beende Animation")
                    break

    except KeyboardInterrupt:
        print("\nAnimation gestoppt (Ctrl+C)")
    finally:
        # Ausschalten aller LEDs
        print("\nSchalte alle LEDs aus...")
        if all_leds:
            off_list = [(led, COLOR_MAP['off'][0], COLOR_MAP['off'][1]) for led in all_leds]
            etherlight.batch_set_leds(off_list)

def run_sw(sw_ip, rows_to_run, user="nwlab"):
    print(f"Verbinde mit {sw_ip}...")
    
    with Etherlight(sw_ip, user) as etherlight:
        # Initial ausschalten
        leds_to_init = set()
        for r in rows_to_run:
            leds_to_init.update(r)
        if leds_to_init:
            print(f"Initialisiere {len(leds_to_init)} LEDs...")
            init_list = [(led, COLOR_MAP['off'][0], COLOR_MAP['off'][1]) for led in leds_to_init]
            etherlight.batch_set_leds(init_list)
        
        print("Starte Animation (Strg+C zum Beenden)...\n")
        animate_rows(etherlight, rows_to_run)

# Beide Reihen laufen immer
rows = [FIRST_ROW, SECOND_ROW]
print(">>> Starte beide Reihen - 5 LEDs gleichzeitig, ohne Delay")

run_sw(SWITCH_IP, rows, user="nwlab")