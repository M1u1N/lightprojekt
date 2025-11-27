import time
import threading

SWITCH_OP = "172.16.26.138"
SWITCH_UNTEN = "172.16.26.139"
NUM_LEDS_START_1_ROW = 1
NUM_LEDS_START_2_ROW = 25
NUM_LEDS_END_1_ROW = 24
NUM_LEDS_END_2_ROW = 48

def totheright(NUM_LEDS_START, NUM_LEDS_END, sw, switch_name):
    print(f"==> Starte totheright auf Switch '{switch_name}' mit IP {sw}")
    time.sleep(1)
    
    for i in range(NUM_LEDS_START, NUM_LEDS_END + 1):
        print(f"[{switch_name}] LED {i}: Haupt-LED (hellrot) an Port {sw}")
        
        if i - 1 >= NUM_LEDS_START:
            print(f"[{switch_name}] LED {i-1}: 1 LED davor dunkler an Port {sw}")
        if i - 2 >= NUM_LEDS_START:
            print(f"[{switch_name}] LED {i-2}: 2 LEDs davor noch dunkler an Port {sw}")
        if i - 3 >= NUM_LEDS_START:
            print(f"[{switch_name}] LED {i-3}: 3 LEDs davor aus an Port {sw}")
        if i + 1 <= NUM_LEDS_END:
            print(f"[{switch_name}] LED {i+1}: LED nach Haupt-LED aus an Port {sw}")
        if i + 2 <= NUM_LEDS_END:
            print(f"[{switch_name}] LED {i+2}: LED nach Haupt-LED aus an Port {sw}")
        
        time.sleep(0.05)
    print(f"==> Fertig mit totheright auf Switch '{switch_name}'\n")

def totheleft(NUM_LEDS_START, NUM_LEDS_END, sw, switch_name):
    print(f"==> Starte totheleft auf Switch '{switch_name}' mit IP {sw}")
    time.sleep(1)
    
    for i in range(NUM_LEDS_END, NUM_LEDS_START -1, -1):
        print(f"[{switch_name}] LED {i}: Haupt-LED (hellrot) an Port {sw}")
        if i + 1 <= NUM_LEDS_END:
            print(f"[{switch_name}] LED {i+1}: 1 LED danach dunkler an Port {sw}")
        if i + 2 <= NUM_LEDS_END:
            print(f"[{switch_name}] LED {i+2}: 2 LEDs danach noch dunkler an Port {sw}")
        if i + 3 <= NUM_LEDS_END:
            print(f"[{switch_name}] LED {i+3}: 3 LEDs danach aus an Port {sw}")
        if i - 1 >= NUM_LEDS_START:
            print(f"[{switch_name}] LED {i-1}: LED vor Haupt-LED aus an Port {sw}")
        if i - 2 >= NUM_LEDS_START:
            print(f"[{switch_name}] LED {i-2}: LED vor Haupt-LED aus an Port {sw}")
        
        time.sleep(0.05)
    print(f"==> Fertig mit totheleft auf Switch '{switch_name}'\n")

def run_sw_op():
    while True:
        totheright(NUM_LEDS_START_2_ROW, NUM_LEDS_END_2_ROW, SWITCH_OP, "SWITCH_OP")
        totheleft(NUM_LEDS_START_2_ROW, NUM_LEDS_END_2_ROW, SWITCH_OP, "SWITCH_OP")

def run_sw_unten():
    while True:
        totheright(NUM_LEDS_START_1_ROW, NUM_LEDS_END_1_ROW, SWITCH_UNTEN, "SWITCH_UNTEN")
        totheleft(NUM_LEDS_START_1_ROW, NUM_LEDS_END_1_ROW, SWITCH_UNTEN, "SWITCH_UNTEN")

def realrun():
    thread_op = threading.Thread(target=run_sw_op)
    thread_unten = threading.Thread(target=run_sw_unten)
    thread_op.start()
    thread_unten.start()

if __name__ == "__main__":
    realrun()
