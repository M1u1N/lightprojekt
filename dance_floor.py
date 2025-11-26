"""
Simple Disco Dance Floor - Alle LEDs gleichzeitig

Dieser Dance Floor wechselt alle LEDs eines Switches gleichzeitig
zu zufälligen Farben. Perfekt für synchrone Lichtshows!

Features:
 - Beide Switches wechseln abwechselnd oder gleichzeitig die Farbe
 - Nutzt set_all_leds() für maximale Performance
 - Einfacher, synchroner Effekt
"""

import time
import random
import threading
import sys
import numpy as np
try:
    from etherlightwin import Etherlight
except Exception:
    Etherlight = None

SW_UNTEN_IP = "172.16.146.212"
SW_OBEN_IP = "172.16.26.138"

# --- Color LUT für schöne Farbverläufe ---
COLOR_LUT_SIZE = 256
_color_lut = None

def init_color_lut():
    global _color_lut
    _color_lut = np.zeros((COLOR_LUT_SIZE, 3), dtype=np.uint8)
    for i in range(COLOR_LUT_SIZE):
        t = i / COLOR_LUT_SIZE
        if t < 0.33:
            s = t / 0.33
            r = int(255 * (1 - s) + 255 * s)
            g = int(0 * (1 - s) + 255 * s)
            b = 0
        elif t < 0.66:
            s = (t - 0.33) / 0.33
            r = int(255 * (1 - s) + 100 * s)
            g = int(255 * (1 - s) + 150 * s)
            b = int(0 * (1 - s) + 255 * s)
        else:
            s = (t - 0.66) / 0.34
            r = int(100 * (1 - s) + 50 * s)
            g = int(150 * (1 - s) + 100 * s)
            b = int(255 * (1 - s) + 255 * s)
        _color_lut[i] = [r, g, b]

def random_color_from_lut():
    """Holt eine zufällige Farbe aus der LUT"""
    idx = random.randrange(0, COLOR_LUT_SIZE)
    r, g, b = _color_lut[idx]
    bright = random.uniform(0.6, 1.0)
    return (int(r * bright), int(g * bright), int(b * bright))


class SimpleDanceFloor:
    """Dance Floor mit synchronen Farbwechseln für ganze Switches"""
    
    def __init__(self, sw_unten_ip=SW_UNTEN_IP, sw_oben_ip=SW_OBEN_IP, 
                 mode="alternating", change_speed=0.5, monitor_only=False):
        """
        Args:
            mode: "alternating" = Switches wechseln abwechselnd
                  "sync" = beide Switches gleichzeitig
                  "random" = zufälliges Timing
            change_speed: Sekunden zwischen Farbwechseln (float)
            monitor_only: True für Test-Modus ohne Hardware
        """
        self.mode = mode
        self.change_speed = change_speed
        self.monitor_only = monitor_only
        
        init_color_lut()
        
        # Etherlight-Verbindungen
        if not monitor_only:
            if Etherlight is None:
                raise RuntimeError("Etherlight library nicht gefunden")
            print("Verbinde zu Switches...")
            self.sw_unten = Etherlight(sw_unten_ip)
            self.sw_oben = Etherlight(sw_oben_ip)
            time.sleep(0.3)
            print("✓ Beide Switches verbunden")
        else:
            self.sw_unten = None
            self.sw_oben = None
            print("✓ Monitor-Modus aktiv")
        
        self._running = threading.Event()
        self._running.set()
        self._thread = None

    def start(self):
        """Startet den Dance Floor"""
        if self.mode == "alternating":
            self._thread = threading.Thread(target=self._alternating_mode, daemon=True)
        elif self.mode == "sync":
            self._thread = threading.Thread(target=self._sync_mode, daemon=True)
        elif self.mode == "random":
            self._thread = threading.Thread(target=self._random_mode, daemon=True)
        else:
            raise ValueError(f"Unbekannter Modus: {self.mode}")
        
        self._thread.start()
        print(f"▶ Dance Floor gestartet (Modus: {self.mode}). Ctrl+C zum Beenden.")
        
        try:
            while self._running.is_set():
                time.sleep(0.2)
        except KeyboardInterrupt:
            print('\n⏹ Stop angefordert...')
            self.stop()

    def stop(self):
        """Stoppt den Dance Floor und schaltet alle LEDs aus"""
        self._running.clear()
        time.sleep(0.2)
        
        if not self.monitor_only:
            print("Schalte LEDs aus...")
            self.sw_unten.set_all_leds((0, 0, 0), 0)
            self.sw_oben.set_all_leds((0, 0, 0), 0)
            self.sw_unten.close()
            self.sw_oben.close()
        
        print("✓ Dance Floor gestoppt")

    def _set_switch_color(self, switch, color, name="Switch"):
        """Setzt alle LEDs eines Switches auf eine Farbe"""
        if self.monitor_only:
            print(f"[{name}] Farbe: RGB{color}")
        else:
            switch.set_all_leds(color, 100)

    def _alternating_mode(self):
        """Switches wechseln abwechselnd die Farbe"""
        while self._running.is_set():
            # SW_UNTEN wechselt
            color = random_color_from_lut()
            self._set_switch_color(self.sw_unten, color, "SW_UNTEN")
            time.sleep(self.change_speed)
            
            if not self._running.is_set():
                break
            
            # SW_OBEN wechselt
            color = random_color_from_lut()
            self._set_switch_color(self.sw_oben, color, "SW_OBEN")
            time.sleep(self.change_speed)

    def _sync_mode(self):
        """Beide Switches wechseln gleichzeitig"""
        while self._running.is_set():
            color = random_color_from_lut()
            self._set_switch_color(self.sw_unten, color, "BEIDE")
            self._set_switch_color(self.sw_oben, color, "BEIDE")
            time.sleep(self.change_speed)

    def _random_mode(self):
        """Zufälliger Switch wechselt zu zufälligen Zeiten"""
        while self._running.is_set():
            # Zufällig einen Switch auswählen
            switch_choice = random.choice(['unten', 'oben'])
            color = random_color_from_lut()
            
            if switch_choice == 'unten':
                self._set_switch_color(self.sw_unten, color, "SW_UNTEN")
            else:
                self._set_switch_color(self.sw_oben, color, "SW_OBEN")
            
            # Zufällige Wartezeit
            wait_time = random.uniform(self.change_speed * 0.5, self.change_speed * 1.5)
            time.sleep(wait_time)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple Disco Dance Floor')
    parser.add_argument('--mode', choices=['alternating', 'sync', 'random'], 
                        default='alternating',
                        help='Farbwechsel-Modus (default: alternating)')
    parser.add_argument('--speed', type=float, default=0.5,
                        help='Sekunden zwischen Farbwechseln (default: 0.5)')
    parser.add_argument('--monitor', action='store_true',
                        help='Monitor-Modus (kein Hardware-Zugriff)')
    
    args = parser.parse_args()
    
    try:
        df = SimpleDanceFloor(
            mode=args.mode,
            change_speed=args.speed,
            monitor_only=args.monitor
        )
        df.start()
    except KeyboardInterrupt:
        print('⏹ Beendet', flush=True)
    except Exception as e:
        print(f"✗ Fehler beim Starten: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)