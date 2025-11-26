import time
from etherlightwin import Etherlight

SWITCH = "172.16.146.212"  # Nur noch ein Switch
FIRST_ROW = [1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33,35,37,39,41,43,45,47]
ROW = FIRST_ROW  # die Reihe, auf der der Effekt laufen soll

# Vorberechnete Farbwerte
COLORS = {
    'main': (190, 0, 0),
    'trail1': (255, 0, 0),
    'trail2': (220, 0, 0),
    'trail3': (100, 0, 0),
    'off': (0, 0, 0)
}

def animate_right(row, etherlight, delay=0.03):
    n = len(row)
    for idx in range(n):
        updates = [(row[idx], COLORS['main'])]
        if idx - 1 >= 0:
            updates.append((row[idx-1], COLORS['trail1']))
        if idx - 2 >= 0:
            updates.append((row[idx-2], COLORS['trail2']))
        if idx - 3 >= 0:
            updates.append((row[idx-3], COLORS['trail3']))
        if idx - 4 >= 0:
            updates.append((row[idx-4], COLORS['off']))
        for led, color in updates:
            etherlight.set_led_color(led, color)
        time.sleep(delay)

def animate_left(row, etherlight, delay=0.03):
    n = len(row)
    for idx in range(n-1, -1, -1):
        updates = [(row[idx], COLORS['main'])]
        if idx + 1 < n:
            updates.append((row[idx+1], COLORS['trail1']))
        if idx + 2 < n:
            updates.append((row[idx+2], COLORS['trail2']))
        if idx + 3 < n:
            updates.append((row[idx+3], COLORS['trail3']))
        if idx + 4 < n:
            updates.append((row[idx+4], COLORS['off']))
        for led, color in updates:
            etherlight.set_led_color(led, color)
        time.sleep(delay)

def run_sw(sw_ip, row, user="neubauer"):
    etherlight = Etherlight(sw_ip, user)
    # Einmaliges Ausschalten der LEDs in der Reihe
    for led in row:
        etherlight.set_led_color(led, COLORS['off'])

    try:
        while True:
            animate_right(row, etherlight, delay=0.03)
            animate_left(row, etherlight, delay=0.03)
    except Exception as e:
        print(f"Fehler in run_sw({sw_ip}): {e}")

def realrun(user="neubauer"):
    try:
        # Direkt im Hauptthread ausführen (ein Switch, eine Reihe)
        run_sw(SWITCH, ROW, user)
    except KeyboardInterrupt:
        print("\nKnight Rider gestoppt")

if __name__ == "__main__":
    realrun(user="nwlab")
