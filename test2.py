from etherlightwin import Etherlight
import traceback

SWITCH_IP = "172.16.26.138"
USER = "nwlab"

def test_connection():
    try:
        with Etherlight(SWITCH_IP, USER) as eth:
            print("Verbindung hergestellt!")
            # Einfach alle LEDs ausschalten (1-48)
            leds = list(range(1, 49))
            off_list = [(led, (0, 0, 0), 100) for led in leds]
            eth.batch_set_leds(off_list)
            print("LEDs ausgeschaltet.")
    except Exception as e:
        print(f"Fehler bei Verbindung oder LEDs setzen: {e}")
        traceback.print_exc()

test_connection()
