"""
Etherlight Dual-Switch Audio Visualizer mit Threading

Installation:
    pip install numpy pyaudiowpatch etherlight

Konfiguration:
    - Zwei Switches übereinander (oben/unten)
    - Jeder Switch hat 4 Interfaces (Soundbar-Segmente)
    - Threading für parallele LED-Updates

Verwendung:
    1. python script.py debug     # Zeigt alle verfügbaren Geräte an
    2. python script.py test      # Testet Audio-Erkennung
    3. python script.py monitor   # Monitor-Modus (nur Erkennung)
    4. python script.py           # LED-Visualisierung
"""

import time
import math
import sys
import numpy as np
import threading
from queue import Queue
from etherlight import Etherlight

# ----------- USER CONFIG -----------
# Switch IPs
SW_OBEN_IP = "172.16.26.138"    # Oberer Switch
SW_UNTEN_IP = "172.16.26.139"   # Unterer Switch

# LED Konfiguration pro Interface
LEDS_PER_INTERFACE = 13  # 52 LEDs / 4 Interfaces = 13 LEDs pro Interface
NUM_INTERFACES = 4       # 4 Interfaces pro Switch
TOTAL_COLUMNS = 8        # 2 Switches × 4 Interfaces = 8 Säulen

# Audio Konfiguration
SAMPLE_RATE = 44100
BLOCKSIZE = 2048
FPS = 60
DECAY = 0.85
MIN_DB = -80.0
MAX_DB = -10.0

# Farben
HUE_GREEN = 120/360.0
HUE_RED = 0.0

# Threading
UPDATE_INTERVAL = 1.0 / FPS

# Versuche PyAudioWPatch zu laden
try:
    import pyaudiowpatch as pyaudio
    HAS_PYAUDIO = True
    print("✓ PyAudioWPatch geladen")
except ImportError:
    print("✗ PyAudioWPatch nicht gefunden!")
    print("  Installiere mit: pip install pyaudiowpatch")
    HAS_PYAUDIO = False
    sys.exit(1)


def hsv_to_rgb255(h, s, v):
    """Konvertiert HSV zu RGB (0-255)"""
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


def mag_to_db(mag):
    """Konvertiert Magnitude zu Dezibel"""
    mag = max(mag, 1e-12)
    return 20.0 * math.log10(mag)


def db_scale(db):
    """Skaliert dB-Wert auf 0-1"""
    if db <= MIN_DB:
        return 0.0
    if db >= MAX_DB:
        return 1.0
    return (db - MIN_DB) / (MAX_DB - MIN_DB)


def debug_devices():
    """Zeigt alle verfügbaren Audio-Geräte an"""
    print("\n" + "="*70)
    print("DEBUG: Alle verfügbaren Audio-Geräte")
    print("="*70)
    
    p = pyaudio.PyAudio()
    
    # WASAPI Info
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        print(f"\n✓ WASAPI verfügbar")
        print(f"  Default Output Device: {wasapi_info['defaultOutputDevice']}")
        print(f"  Default Input Device: {wasapi_info['defaultInputDevice']}")
    except OSError:
        print("\n✗ WASAPI nicht verfügbar!")
        p.terminate()
        return
    
    print(f"\nAnzahl Geräte: {p.get_device_count()}")
    print("\n" + "-"*70)
    
    loopback_devices = []
    
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        
        device_type = "❓ Unbekannt"
        if info.get('isLoopbackDevice', False):
            device_type = "🔁 LOOPBACK"
            loopback_devices.append((i, info))
        elif info['maxOutputChannels'] > 0:
            device_type = "🔊 OUTPUT"
        elif info['maxInputChannels'] > 0:
            device_type = "🎤 INPUT"
        
        print(f"\n[{i}] {device_type}")
        print(f"  Name: {info['name']}")
        print(f"  Input Channels: {info['maxInputChannels']}")
        print(f"  Output Channels: {info['maxOutputChannels']}")
    
    print("\n" + "="*70)
    if loopback_devices:
        print("✓ LOOPBACK-GERÄTE GEFUNDEN:")
        for idx, info in loopback_devices:
            print(f"  [{idx}] {info['name']}")
    
    p.terminate()


class SwitchController:
    """Kontrolliert einen einzelnen Switch mit Threading"""
    
    def __init__(self, ip, name, leds_per_interface=LEDS_PER_INTERFACE, num_interfaces=NUM_INTERFACES):
        self.ip = ip
        self.name = name
        self.leds_per_interface = leds_per_interface
        self.num_interfaces = num_interfaces
        self.total_leds = leds_per_interface * num_interfaces
        
        print(f"🔌 Verbinde mit {name} ({ip})...", flush=True)
        self.ether = Etherlight(ip)
        time.sleep(0.5)
        print(f"✓ {name} verbunden", flush=True)
        
        # Threading
        self.update_queue = Queue(maxsize=10)
        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
    
    def _update_loop(self):
        """Thread-Loop für LED-Updates"""
        while self.running:
            try:
                # Hole neueste LED-Daten aus Queue
                if not self.update_queue.empty():
                    led_colors = self.update_queue.get(timeout=0.1)
                    
                    # Setze alle LEDs
                    for interface_idx in range(self.num_interfaces):
                        start_led = interface_idx * self.leds_per_interface + 1
                        
                        for led_in_interface in range(self.leds_per_interface):
                            led_index = start_led + led_in_interface
                            color = led_colors[interface_idx][led_in_interface]
                            
                            try:
                                self.ether.set_led_color(led_index, color)
                            except:
                                pass
                    
                    # Flush alle Updates gleichzeitig
                    try:
                        self.ether.flush()
                    except:
                        pass
                else:
                    time.sleep(0.001)  # Kurze Pause wenn keine Daten
                    
            except Exception as e:
                if self.running:
                    print(f"✗ {self.name} Update-Fehler: {e}", flush=True)
    
    def update_leds(self, levels):
        """
        Aktualisiert LEDs basierend auf Audio-Levels
        levels: Array mit 4 Werten (0-1) für jedes Interface
        """
        if len(levels) != self.num_interfaces:
            print(f"⚠ Warnung: {len(levels)} Levels für {self.num_interfaces} Interfaces")
            return
        
        led_colors = []
        
        for interface_idx, level in enumerate(levels):
            interface_colors = []
            n_lit = int(round(level * self.leds_per_interface))
            
            for led_idx in range(self.leds_per_interface):
                if led_idx < n_lit:
                    # LED an - Farbe basierend auf Level
                    hue = HUE_GREEN + (HUE_RED - HUE_GREEN) * level
                    value = 0.6 + 0.4 * level
                    rgb = hsv_to_rgb255(hue, 1.0, value)
                else:
                    # LED aus
                    rgb = (0, 0, 0)
                
                interface_colors.append(rgb)
            
            led_colors.append(interface_colors)
        
        # In Queue für Update-Thread
        try:
            if self.update_queue.full():
                self.update_queue.get_nowait()  # Alte Daten verwerfen
            self.update_queue.put_nowait(led_colors)
        except:
            pass
    
    def cleanup(self):
        """Beendet Thread und räumt auf"""
        self.running = False
        if self.update_thread.is_alive():
            self.update_thread.join(timeout=2.0)
        print(f"✓ {self.name} beendet", flush=True)


class DualSwitchAudioVisualizer:
    """Audio Visualizer für zwei Switches mit je 4 Interfaces"""
    
    def __init__(self, monitor_only=False):
        self.monitor_only = monitor_only
        self.running = True
        
        # Audio-Verarbeitung
        self.prev_levels = np.zeros(TOTAL_COLUMNS)
        self.device_name = "Unbekannt"
        self.p = None
        self.stream = None
        
        # Switch-Controller
        if not monitor_only:
            print("\n🎛️  Initialisiere Dual-Switch Setup...")
            print(f"   └─ Oben:  {SW_OBEN_IP} (4 Interfaces)")
            print(f"   └─ Unten: {SW_UNTEN_IP} (4 Interfaces)")
            print(f"   └─ Gesamt: {TOTAL_COLUMNS} Soundbar-Säulen\n")
            
            self.sw_oben = SwitchController(SW_OBEN_IP, "SW_OBEN")
            self.sw_unten = SwitchController(SW_UNTEN_IP, "SW_UNTEN")
            
            print("✓ Beide Switches bereit!\n")
        else:
            self.sw_oben = None
            self.sw_unten = None
    
    def process_audio(self, audio_data):
        """Verarbeitet Audio-Daten und berechnet Levels für alle 8 Säulen"""
        
        # Apply window
        window = np.hanning(len(audio_data))
        audio_data = audio_data * window
        
        # FFT
        fft = np.abs(np.fft.rfft(audio_data))
        freqs = np.fft.rfftfreq(len(audio_data), 1.0 / SAMPLE_RATE)
        
        # Frequency bands für 8 Säulen
        fmin = 20.0
        fmax = 16000.0
        band_edges = np.logspace(math.log10(fmin), math.log10(fmax), num=TOTAL_COLUMNS + 1)
        band_amps = np.zeros(TOTAL_COLUMNS)
        
        for i in range(TOTAL_COLUMNS):
            lo = band_edges[i]
            hi = band_edges[i + 1]
            idx = np.where((freqs >= lo) & (freqs < hi))[0]
            if idx.size > 0:
                band_amps[i] = np.mean(fft[idx])
        
        # Normalisierung
        band_amps = band_amps / (len(audio_data) / 2)
        
        # Convert to dB and scale
        with np.errstate(divide='ignore'):
            band_db = np.array([mag_to_db(a) for a in band_amps])
        band_scaled = np.array([db_scale(d) for d in band_db])
        
        # Smooth mit Decay
        self.prev_levels = np.maximum(self.prev_levels * DECAY, band_scaled)
        
        if self.monitor_only:
            # Monitor-Modus: Zeige Levels
            max_level = float(np.max(self.prev_levels))
            if max_level > 0.05:
                bars = ''.join(['█' if l > 0.1 else '▓' if l > 0.05 else '░' for l in self.prev_levels])
                print(f"\r🔊 [{bars}] {max_level:.2f}", end='', flush=True)
        else:
            # LED-Update via Threading
            self.update_switches()
    
    def update_switches(self):
        """Verteilt Audio-Levels auf beide Switches"""
        if self.sw_oben is None or self.sw_unten is None:
            return
        
        # Split levels: Erste 4 für oberen Switch, letzte 4 für unteren Switch
        levels_oben = self.prev_levels[0:4]
        levels_unten = self.prev_levels[4:8]
        
        # Parallel Updates via Threading
        self.sw_oben.update_leds(levels_oben)
        self.sw_unten.update_leds(levels_unten)
    
    def cleanup(self):
        """Sauberes Beenden aller Ressourcen"""
        print("\n🛑 Beende Visualizer...", flush=True)
        self.running = False
        
        # Stoppe Audio-Stream
        try:
            if self.stream:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
                self.stream = None
        except Exception as e:
            print(f"⚠ Stream-Fehler: {e}", flush=True)
        
        try:
            if self.p:
                self.p.terminate()
                self.p = None
        except Exception as e:
            print(f"⚠ PyAudio-Fehler: {e}", flush=True)
        
        # Stoppe Switch-Controller
        if self.sw_oben:
            self.sw_oben.cleanup()
        if self.sw_unten:
            self.sw_unten.cleanup()
        
        # Flush Output
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except:
            pass
        
        print("✓ Beendet", flush=True)
    
    def run(self, device_index=None):
        """Hauptschleife für Audio-Capture und Visualisierung"""
        try:
            self.p = pyaudio.PyAudio()
            
            # Finde Loopback-Gerät
            if device_index is None:
                try:
                    wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
                    default_speakers = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
                    
                    print(f"🔍 Standard-Lautsprecher: {default_speakers['name']}", flush=True)
                    
                    # Suche Loopback
                    if not default_speakers.get("isLoopbackDevice", False):
                        print("🔍 Suche Loopback...", flush=True)
                        for loopback in self.p.get_loopback_device_info_generator():
                            if default_speakers["name"] in loopback["name"]:
                                default_speakers = loopback
                                print(f"✓ Loopback gefunden: {loopback['name']}", flush=True)
                                break
                        else:
                            print("✗ Kein Loopback gefunden!", flush=True)
                            return
                    
                    device_index = default_speakers["index"]
                    
                except Exception as e:
                    print(f"✗ Fehler: {e}", flush=True)
                    return
            
            device_info = self.p.get_device_info_by_index(device_index)
            self.device_name = device_info['name']
            
            print(f"\n🎵 Audio-Capture: {self.device_name}", flush=True)
            print(f"📊 Visualisierung: {TOTAL_COLUMNS} Säulen @ {FPS} FPS", flush=True)
            print("⌨️  Drücke Ctrl+C zum Beenden\n", flush=True)
            
            # Öffne Audio-Stream
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=device_info['maxInputChannels'],
                rate=int(device_info['defaultSampleRate']),
                input=True,
                input_device_index=device_index,
                frames_per_buffer=BLOCKSIZE
            )
            
            self.stream.start_stream()
            
            # Hauptschleife
            while self.running and self.stream.is_active():
                try:
                    data = self.stream.read(BLOCKSIZE, exception_on_overflow=False)
                    audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                    
                    # Mix zu Mono
                    if len(audio_data) > BLOCKSIZE:
                        audio_data = audio_data.reshape(-1, device_info['maxInputChannels']).mean(axis=1)
                    
                    self.process_audio(audio_data)
                    
                except Exception as e:
                    if self.running:
                        print(f"\n✗ Audio-Fehler: {e}", flush=True)
                    break
                    
        except KeyboardInterrupt:
            print("\n⏸️  Unterbrochen", flush=True)
        except Exception as e:
            print(f"\n✗ Fehler: {e}", flush=True)
        finally:
            self.cleanup()


def music_play(monitor_only=False):
    """Startet den Audio Visualizer"""
    print("\n" + "="*70)
    print("  🎛️  DUAL-SWITCH AUDIO VISUALIZER")
    print("="*70)
    print(f"  Konfiguration:")
    print(f"    • Switch Oben:  {SW_OBEN_IP} (Interfaces 1-4)")
    print(f"    • Switch Unten: {SW_UNTEN_IP} (Interfaces 1-4)")
    print(f"    • Gesamt:       {TOTAL_COLUMNS} Soundbar-Säulen")
    print(f"    • LEDs/Säule:   {LEDS_PER_INTERFACE}")
    print(f"    • FPS:          {FPS}")
    print("="*70 + "\n")
    
    if monitor_only:
        print("👁️  Modus: Audio-Monitoring (ohne LEDs)\n")
    else:
        print("🎨 Modus: LED-Visualisierung\n")
    
    viz = DualSwitchAudioVisualizer(monitor_only=monitor_only)
    
    try:
        viz.run()
    finally:
        viz.cleanup()


if __name__ == '__main__':
    try:
        if len(sys.argv) > 1:
            cmd = sys.argv[1].lower()
            if cmd == 'debug':
                debug_devices()
            elif cmd == 'test':
                print("Test-Modus noch nicht implementiert für Dual-Switch")
            elif cmd == 'monitor':
                music_play(monitor_only=True)
            else:
                print("Verwendung:")
                print("  python script.py debug    - Zeigt alle Audio-Geräte")
                print("  python script.py monitor  - Nur Audio-Monitoring")
                print("  python script.py          - LED-Visualisierung")
        else:
            music_play(monitor_only=False)
    except KeyboardInterrupt:
        print("\n⏹ Programm beendet", flush=True)
    except Exception as e:
        print(f"\n✗ Unerwarteter Fehler: {e}", flush=True)
    finally:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except:
            pass