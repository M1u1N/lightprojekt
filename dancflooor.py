"""
Disco Dance Floor - 3 Threads (FIXED VERSION)

FIXES:
1. Korrektes Mapping für alle 4 Reihen (row3/row4 auf separaten Switch)
2. Korrekter flush() Aufruf statt flush_led_cache()
3. Bessere Thread-Synchronisation
4. Reduziert auf 3 Dancer-Threads für weniger Chaos
"""

import time
import random
import threading
import sys
import numpy as np
from collections import deque
try:
    from etherlightwin import Etherlight
except Exception:
    Etherlight = None

# --- Mapping (wie in deinem Originalskript) ---
FIRST_ROW = [2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48]
SECOND_ROW = [1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33,35,37,39,41,43,45,47]

SW_UNTEN_IP = "172.16.146.212"
SW_OBEN_IP = "172.16.26.138"

NUM_COLUMNS = 24
LEDS_PER_COLUMN = 4

# --- Color LUT ---
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
    idx = random.randrange(0, COLOR_LUT_SIZE)
    r, g, b = _color_lut[idx]
    bright = random.uniform(0.5, 1.0)
    return (int(r * bright), int(g * bright), int(b * bright))

# --- OptimizedSwitchController ---
class OptimizedSwitchController:
    def __init__(self, ip, name, monitor_only=False):
        self.ip = ip
        self.name = name
        self.monitor_only = monitor_only
        self.ether = None
        if not monitor_only:
            if Etherlight is None:
                raise RuntimeError("Etherlight library nicht gefunden")
            self.ether = Etherlight(ip)
            time.sleep(0.2)
            print(f"✓ {name} verbunden")
        self._led_buffer = [(0,0,0)] * 48
        self._lock = threading.Lock()

    def set_buffer(self, buffer_list):
        with self._lock:
            self._led_buffer = list(buffer_list)

    def get_buffer_copy(self):
        with self._lock:
            return list(self._led_buffer)

    def flush(self):
        with self._lock:
            buff = list(self._led_buffer)
        if self.monitor_only:
            lit = sum(1 for c in buff if c != (0,0,0))
            print(f"[{self.name}] Flush -> {lit} LEDs ON", end='\r')
            return
        try:
            # Baue led_colors Liste für batch_set_leds
            led_colors = []
            for i, color in enumerate(buff):
                if color != (0,0,0):  # Nur leuchtende LEDs senden
                    led_colors.append((i + 1, color, 100))
            
            if led_colors:
                self.ether.batch_set_leds(led_colors)
        except Exception as e:
            print(f"✗ Fehler beim Flush {self.name}: {e}")

    def cleanup(self):
        try:
            if not self.monitor_only:
                self.ether.set_all_leds((0,0,0), 0)
        except Exception:
            pass
        print(f"✓ {self.name} beendet")

# --- Disco Dance Floor Controller (FIXED) ---
class DiscoDanceFloor:
    def __init__(self, sw_unten_ip=SW_UNTEN_IP, sw_oben_ip=SW_OBEN_IP,
                 num_dancers=3, monitor_only=False, flush_hz=20):
        self.monitor_only = monitor_only
        self.num_dancers = num_dancers
        self.flush_interval = 1.0 / max(1, flush_hz)

        init_color_lut()

        # 🔧 FIX: Korrektes Mapping für alle 4 Reihen!
        # Row 1+2 sind auf SW_UNTEN, Row 3+4 sind auf SW_OBEN
        self._column_to_leds = []
        for col in range(NUM_COLUMNS):
            self._column_to_leds.append({
                'unten': {
                    'row1': FIRST_ROW[col] - 1,   # SW_UNTEN, gerade LED-Nummern
                    'row2': SECOND_ROW[col] - 1   # SW_UNTEN, ungerade LED-Nummern
                },
                'oben': {
                    'row3': FIRST_ROW[col] - 1,   # SW_OBEN, gerade LED-Nummern
                    'row4': SECOND_ROW[col] - 1   # SW_OBEN, ungerade LED-Nummern
                }
            })

        # LED-Puffer
        self.leds_unten = [(0,0,0)] * 48
        self.leds_oben = [(0,0,0)] * 48

        # Locks
        self._buffer_lock = threading.Lock()

        # Switch-Controller
        self.sw_unten = OptimizedSwitchController(sw_unten_ip, "SW_UNTEN", monitor_only=monitor_only)
        self.sw_oben = OptimizedSwitchController(sw_oben_ip, "SW_OBEN", monitor_only=monitor_only)

        self._threads = []
        self._running = threading.Event()
        self._running.set()

    def start(self):
        # Start Flusher
        flusher = threading.Thread(target=self._flusher_thread, name="Flusher", daemon=True)
        flusher.start()
        self._threads.append(flusher)

        # Start dancer threads
        for i in range(self.num_dancers):
            t = threading.Thread(target=self._dancer_thread, name=f"Dancer-{i+1}", args=(i,), daemon=True)
            t.start()
            self._threads.append(t)

        print(f"▶ Disco gestartet mit {self.num_dancers} Tänzern. Ctrl+C zum Beenden.")

        try:
            while self._running.is_set():
                time.sleep(0.2)
        except KeyboardInterrupt:
            print('\n⏹ Stop angefordert...')
            self.stop()

    def stop(self):
        self._running.clear()
        time.sleep(self.flush_interval * 1.5)
        with self._buffer_lock:
            self.leds_unten = [(0,0,0)] * 48
            self.leds_oben = [(0,0,0)] * 48
        self._send_buffers()
        if self.sw_unten:
            self.sw_unten.cleanup()
        if self.sw_oben:
            self.sw_oben.cleanup()
        print("✓ Disco gestoppt")

    def _dancer_thread(self, dancer_idx):
        """🔧 FIX: Jeder Tänzer wählt wirklich ZUFÄLLIG (Spalte, Reihe) und Farbe."""
        rng = random.Random()
        while self._running.is_set():
            col = rng.randrange(0, NUM_COLUMNS)  # 0..23
            row = rng.randrange(0, LEDS_PER_COLUMN)  # 0..3 (zufällig!)

            color = random_color_from_lut()

            mapping = self._column_to_leds[col]
            
            # 🔧 FIX: Korrektes Setzen basierend auf Reihe
            with self._buffer_lock:
                if row == 0:  # Reihe 1 -> SW_UNTEN
                    self.leds_unten[mapping['unten']['row1']] = color
                elif row == 1:  # Reihe 2 -> SW_UNTEN
                    self.leds_unten[mapping['unten']['row2']] = color
                elif row == 2:  # Reihe 3 -> SW_OBEN
                    self.leds_oben[mapping['oben']['row3']] = color
                elif row == 3:  # Reihe 4 -> SW_OBEN
                    self.leds_oben[mapping['oben']['row4']] = color

            # Zufällige Pause
            time.sleep(rng.uniform(0.05, 0.6))

    def _flusher_thread(self):
        """Sammelt Änderungen und sendet periodisch an die Switches."""
        while self._running.is_set():
            start = time.time()
            self._send_buffers()
            elapsed = time.time() - start
            to_sleep = max(0.0, self.flush_interval - elapsed)
            time.sleep(to_sleep)

    def _send_buffers(self):
        with self._buffer_lock:
            bu_unten = list(self.leds_unten)
            bu_oben = list(self.leds_oben)
        
        # 🔧 FIX: Korrekter flush() Aufruf
        try:
            self.sw_unten.set_buffer(bu_unten)
            self.sw_oben.set_buffer(bu_oben)
            self.sw_unten.flush()  # ✓ Richtig!
            self.sw_oben.flush()   # ✓ Richtig!
        except Exception as e:
            print(f"✗ Fehler beim Senden: {e}")


if __name__ == '__main__':
    try:
        dd = DiscoDanceFloor(monitor_only=False)
        dd.start()
    except KeyboardInterrupt:
        print('⏹ Beendet', flush=True)
    except Exception as e:
        print(f"✗ Fehler beim Starten: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)