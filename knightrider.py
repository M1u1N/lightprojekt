import threading
import time
from etherlight import Etherlight
from random import randint

SWITCH_OP="172.16.26.138"
SWITCH_UNTEN="172.16.26.139"
NUM_LEDS_START_1_ROW=1
NUM_LEDS_START_2_ROW=25
NUM_LEDS_END_1_ROW=24
NUM_LEDS_END_2_ROW = 48
COLUMNS=4

def totheright(NUM_LEDS_START, NUM_LEDS_END,sw,user="neubauer"):
    etherlight = Etherlight(sw, user)
    time.sleep(2)
    
    for i in range(NUM_LEDS_START, NUM_LEDS_END + 1):
        # Haupt-LED hellrot
        etherlight.set_led_color(i, (255, 0, 0))
        
        # 1 LED davor dunkler
        if i - 1 >= NUM_LEDS_START:
            etherlight.set_led_color(i - 1, (150, 0, 0))
        
        # 2 LEDs davor noch dunkler
        if i - 2 >= NUM_LEDS_START:
            etherlight.set_led_color(i - 2, (50, 0, 0))
        
        # 3 LEDs davor aus
        if i - 3 >= NUM_LEDS_START:
            etherlight.set_led_color(i - 3, (0, 0, 0))
        
        # LEDs nach der Haupt-LED aus
        if i + 1 <= NUM_LEDS_END:
            etherlight.set_led_color(i + 1, (0, 0, 0))
        if i + 2 <= NUM_LEDS_END:
            etherlight.set_led_color(i + 2, (0, 0, 0))
        
        time.sleep(0.1)
        
def totheleft(NUM_LEDS_START, NUM_LEDS_END,sw,user="neubauer"):
    etherlight = Etherlight(sw, user)
    time.sleep(2)
    
    for i in range(NUM_LEDS_END, NUM_LEDS_START - 1, -1):
        etherlight.set_led_color(i, (255, 0, 0))
        
        # 1 LED danach dunkler
        if i + 1 <= NUM_LEDS_END:
            etherlight.set_led_color(i + 1, (150, 0, 0))
        
        # 2 LEDs danach noch dunkler
        if i + 2 <= NUM_LEDS_END:
            etherlight.set_led_color(i + 2, (50, 0, 0))
        
        # 3 LEDs danach aus
        if i + 3 <= NUM_LEDS_END:
            etherlight.set_led_color(i + 3, (0, 0, 0))
        
        # LEDs vor der Haupt-LED aus
        if i - 1 >= NUM_LEDS_START:
            etherlight.set_led_color(i - 1, (0, 0, 0))
        if i - 2 >= NUM_LEDS_START:
            etherlight.set_led_color(i - 2, (0, 0, 0))
        
        time.sleep(0.1)

def run_sw_op(sw,user="neubauer"):
    while True:
        totheright(NUM_LEDS_START_2_ROW, NUM_LEDS_END_2_ROW,SWITCH_OP,sw,user)
        totheleft(NUM_LEDS_START_2_ROW, NUM_LEDS_END_2_ROW,SWITCH_OP,sw,user)
def run_sw_unten(sw,user="neubauer"):
    while True:
        totheright(NUM_LEDS_START_1_ROW, NUM_LEDS_END_1_ROW,SWITCH_UNTEN,sw,user)
        totheleft(NUM_LEDS_START_1_ROW, NUM_LEDS_END_1_ROW,SWITCH_UNTEN,sw,user)
        
def realrun(user="neubauer"):
    thread_op = threading.Thread(target=run_sw_op, args=(SWITCH_OP,user))
    thread_unten = threading.Thread(target=run_sw_unten, args=(SWITCH_UNTEN,user))
    thread_op.start()
    thread_unten.start()


def knightriderdouple(monitor_only=False, user="neubauer"):
    realrun(user)
    
if __name__ == "__main__":
    knightriderdouple("neubauer")