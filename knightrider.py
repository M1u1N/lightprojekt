import threading
import time
from etherlightwin import Etherlight

SWITCH_OP = "172.16.26.138"
#SWITCH_UNTEN = "172.16.146.212"
SWITCH_UNTEN = "172.16.26.138"
FIRST_ROW = [1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33,35,37,39,41,43,45,47]
SECOND_ROW = [2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48]

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
    # Batch-Updates vorbereiten
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
        
        # Alle Updates auf einmal senden (falls API das unterstützt)
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
    
    # Schnelles initiales Ausschalten - nur einmal
    for led in row:
        etherlight.set_led_color(led, COLORS['off'])

    try:
        while True:
            animate_right(row, etherlight, delay=0.03)
            animate_left(row, etherlight, delay=0.03)
    except Exception as e:
        print(f"Fehler in run_sw({sw_ip}): {e}")

def realrun(user="neubauer"):
    thread_op = threading.Thread(target=run_sw, args=(SWITCH_UNTEN, FIRST_ROW, user), daemon=True)
    thread_unten = threading.Thread(target=run_sw, args=(SWITCH_OP, SECOND_ROW, user), daemon=True)
    
    thread_op.start()
    thread_unten.start()
    
    try:
        # Effizienter als time.sleep(0)
        thread_op.join()
        thread_unten.join()
    except KeyboardInterrupt:
        print("\nKnight Rider gestoppt")

if __name__ == "__main__":
    realrun(user="nwlab")