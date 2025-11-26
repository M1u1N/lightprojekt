"""
Etherlight Knight-Rider (Grid-basiert)

Layout:
 - Jeder Switch ist ein 2D-Grid: ROWS x COLS
 - Default für deine Vorgabe: COLS=24, ROWS=2 (also 24x2 pro Switch)
 - Es gibt zwei Switches: oben (SW_OBEN) und unten (SW_UNTEN), übereinander angeordnet.

Anforderung umgesetzt:
 - Der rote Knight-Rider-Streifen läuft horizontal über die Spalten (0..COLS-1).
 - Auf SW_OBEN befindet sich der Streifen in Zeile 2 (index 1, also 0-basierte Zeile 1).
 - Auf SW_UNTEN befindet sich der Streifen in Zeile 1 (index 0).
 - Beide Streifen sind synchron: die gleiche Spalte wird gleichzeitig auf beiden Switches aktiviert.
 - Simulation (kein Etherlight) zeigt kompaktes Terminal-Feedback.
 - Wenn Etherlight installiert ist, werden die LED-Indizes wie folgt gemappt:
     led_index = row * cols + col + 1
   (Das kannst du anpassen, falls deine Hardware ein anderes Mapping verwendet.)

Verwendung:
 - Du wirst beim Start nach Länge (COLS) und Breite (ROWS) gefragt. Drücke Enter für Standard 24x2.
 - Befehle:
     python script.py test    -> Simulation: läuft für eine voreingestellte Anzahl Loops
     python script.py knight  -> Wenn Etherlight verfügbar: echtes Lauflicht. Sonst Simulation
     python script.py         -> startet standardmäßig `test`

"""

import time
import sys
from queue import Queue
import threading

# ------------------ Konfiguration / Defaults ------------------
DEFAULT_COLS = 24  # Länge (LEDs pro Zeile)
DEFAULT_ROWS = 2   # Breite (Zeilen pro Switch)

# Knight-Rider Einstellungen
KR_SPEED_DEFAULT = 0.07   # Sekunden zwischen Schritten
KR_LOOPS_DEFAULT = 5      # Default Schleifen im Test-Modus (hin+zurück = 1)

# Farbe (HSV-Helfer unten)
HUE_KR = 0.0  # Rot

# Versuche Etherlight zu importieren
try:
    from etherlight import Etherlight
    HAS_ETHERLIGHT = True
except Exception:
    HAS_ETHERLIGHT = False


# ------------------ Farb-Helfer ------------------
def hsv_to_rgb255(h, s, v):
    if s == 0.0:
        r = g = b = int(v * 255)
        return (r, g, b)
    i = int(h * 6.0)
    f = (h * 6.0) - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    i = i % 6
    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    elif i == 5:
        r, g, b = v, p, q
    return (int(r * 255), int(g * 255), int(b * 255))


# ------------------ SwitchController ------------------
class SwitchController:
    """Controller für einen Switch als ROWS x COLS Grid.
    update_grid(grid) erwartet eine Liste von ROWS Reihen, jede Reihe eine Liste von COLS RGB-Tuples.
    Die interne Mapping-Strategie ist: led_index = row * cols + col + 1
    """

    def __init__(self, ip, name, rows, cols):
        self.ip = ip
        self.name = name
        self.rows = rows
        self.cols = cols
        self.update_queue = Queue(maxsize=10)
        self.running = True
        self.ether = None

        print(f"🔌 Initialisiere {name} ({ip}) - {rows}x{cols}...", flush=True)
        if HAS_ETHERLIGHT:
            try:
                self.ether = Etherlight(ip)
                time.sleep(0.1)
                print(f"✓ {name} verbunden", flush=True)
            except Exception as e:
                print(f"✗ Verbindung zu {name} fehlgeschlagen: {e}", flush=True)
                self.ether = None
        else:
            print(f"⚠ Etherlight nicht vorhanden — Simulation für {name}", flush=True)

        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()

    def _update_loop(self):
        while self.running:
            try:
                if not self.update_queue.empty():
                    grid = self.update_queue.get(timeout=0.1)
                    # grid: rows x cols of (r,g,b) tuples
                    if self.ether is not None:
                        # Schreiben auf die Hardware (angenommenes Mapping)
                        try:
                            for r in range(self.rows):
                                for c in range(self.cols):
                                    led_index = r * self.cols + c + 1
                                    color = grid[r][c]
                                    try:
                                        self.ether.set_led_color(led_index, color)
                                    except Exception:
                                        pass
                            try:
                                self.ether.flush()
                            except Exception:
                                pass
                        except Exception as e:
                            print(f"✗ {self.name} Hardware-Update Fehler: {e}", flush=True)
                    else:
                        # Simulation: kompakte Terminalausgabe
                        out = []
                        for r in range(self.rows):
                            lit_cols = [str(c) for c in range(self.cols) if grid[r][c] != (0, 0, 0)]
                            out.append(f"R{r+1}:[{','.join(lit_cols) if lit_cols else '-'}]")
                        print(f"Sim {self.name}: " + " | ".join(out), flush=True)
                else:
                    time.sleep(0.005)
            except Exception as e:
                if self.running:
                    print(f"✗ {self.name} Update-Loop Fehler: {e}", flush=True)

    def update_grid(self, grid):
        # grid validation
        if not isinstance(grid, list) or len(grid) != self.rows:
            print(f"⚠ Ungültiges Grid für {self.name}", flush=True)
            return
        try:
            if self.update_queue.full():
                try:
                    self.update_queue.get_nowait()
                except Exception:
                    pass
            self.update_queue.put_nowait(grid)
        except Exception:
            pass

    def cleanup(self):
        self.running = False
        if self.update_thread.is_alive():
            self.update_thread.join(timeout=1.0)
        print(f"✓ {self.name} beendet", flush=True)


# ------------------ DualSwitchKnightRider ------------------
class DualSwitchKnightRider:
    def __init__(self, cols, rows, simulate=False):
        # rows and cols per switch
        self.cols = cols
        self.rows = rows
        self.simulate = simulate or not HAS_ETHERLIGHT

        # Switch IPs (kann bei Bedarf angepasst werden)
        self.sw_oben_ip = "172.16.26.138"
        self.sw_unten_ip = "172.16.26.139"

        # Row indices for the knight-rider strip on each switch (0-based):
        # SW_OBEN -> Zeile 2 (index 1), SW_UNTEN -> Zeile 1 (index 0)
        if self.rows < 2:
            raise ValueError("Benötigt mindestens 2 Reihen pro Switch für die gewünschte Anordnung")
        self.row_oben = 1
        self.row_unten = 0

        # Controller-Objekte
        if not self.simulate:
            print("Initialisiere reale Switches...", flush=True)
            self.sw_oben = SwitchController(self.sw_oben_ip, "SW_OBEN", rows=self.rows, cols=self.cols)
            self.sw_unten = SwitchController(self.sw_unten_ip, "SW_UNTEN", rows=self.rows, cols=self.cols)
        else:
            print("  Simulation-Modus (keine Etherlight-Hardware)", flush=True)
            self.sw_oben = SwitchController(self.sw_oben_ip, "SW_OBEN_SIM", rows=self.rows, cols=self.cols)
            self.sw_unten = SwitchController(self.sw_unten_ip, "SW_UNTEN_SIM", rows=self.rows, cols=self.cols)

        self.running = True

    def _empty_grid(self):
        return [[(0, 0, 0) for _ in range(self.cols)] for _ in range(self.rows)]

    def _set_column(self, col, intensity=1.0):
        # Erzeuge leeres Grid für oben und unten
        grid_oben = self._empty_grid()
        grid_unten = self._empty_grid()

        # Farbe und Helligkeit
        v = max(0.0, min(1.0, intensity))
        bright = 0.2 + 0.8 * v
        rgb = hsv_to_rgb255(HUE_KR, 1.0, bright)

        # Setze die entsprechende Zelle (row, col)
        # Prüfe Grenzen
        if 0 <= col < self.cols:
            grid_oben[self.row_oben][col] = rgb
            grid_unten[self.row_unten][col] = rgb

            # Zusätzliche Testausgabe: wenn Spalte 0 aktiv -> "PORT 1 wird angesteuert"
            if col == 0:
                print("PORT 1 wird angesteuert", flush=True)

        # Sende beide Grids gleichzeitig
        self.sw_oben.update_grid(grid_oben)
        self.sw_unten.update_grid(grid_unten)

    def kinghtrider(self, speed=KR_SPEED_DEFAULT, loops=None):
        total = self.cols
        iteration = 0

        try:
            while self.running:
                # Vorwärts
                for c in range(total):
                    self._set_column(c)
                    time.sleep(speed)
                # Rückwärts (ohne Doppel am Ende)
                for c in range(total - 2, -1, -1):
                    self._set_column(c)
                    time.sleep(speed)

                iteration += 1
                if loops is not None and iteration >= loops:
                    break
        except KeyboardInterrupt:
            print(" Knight-Rider unterbrochen", flush=True)
        finally:
            self.cleanup()

    def cleanup(self):
        self.running = False
        if self.sw_oben:
            self.sw_oben.cleanup()
        if self.sw_unten:
            self.sw_unten.cleanup()
        print("✓ Knight-Rider beendet", flush=True)


# ------------------ Hilfsfunktionen zum Start ------------------



def run_test(cols, rows, loops=KR_LOOPS_DEFAULT, speed=KR_SPEED_DEFAULT):
    print("Starte Test-Simulation: Knight-Rider (Simulation)")
    kr = DualSwitchKnightRider(cols=cols, rows=rows, simulate=True)
    try:
        kr.kinghtrider(speed=speed, loops=loops)
    finally:
        kr.cleanup()


def run_hardware(cols, rows, speed=KR_SPEED_DEFAULT):
    if not HAS_ETHERLIGHT:
        print("✗ Etherlight nicht installiert/erreichbar — starte Simulation statt Hardware", flush=True)
        run_test(cols, rows, loops=KR_LOOPS_DEFAULT, speed=speed)
        return
    print("Starte Knight-Rider auf realer Hardware...")
    kr = DualSwitchKnightRider(cols=cols, rows=rows, simulate=False)
    try:
        kr.kinghtrider(speed=speed, loops=None)
    finally:
        kr.cleanup()



def knightriderdouple(cmd=False):
    try:
        cols = DEFAULT_COLS
        rows = DEFAULT_ROWS

        if cmd == True:
                run_test(cols, rows)
        elif cmd == False:
                run_hardware(cols, rows)
        

    except KeyboardInterrupt:
        print("Programm beendet", flush=True)
    except Exception as e:
        print(f"Unerwarteter Fehler: {e}", flush=True)
    finally:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except:
            pass