"""
Etherlight Dual-Switch Audio Visualizer mit Beat-Detection

Soundbar-Aufbau:
    - 24 Säulen (horizontal) × 4 LEDs hoch (vertikal) = 96 LEDs gesamt
    - Unten:  Switch 1 (Ports 1-48)  - Reihe 1+2 (24 Säulen × 2 LEDs)
    - Oben:   Switch 2 (Ports 1-48)  - Reihe 3+4 (24 Säulen × 2 LEDs)

Features:
    ✓ Beat-Detection für Bass/Kick-Drums
    ✓ Unabhängige Frequenzbänder pro Säule
    ✓ Separate Amplituden-Berechnung
    ✓ Dynamische Bass-Verstärkung
    ✓ Multi-threaded Updates

Installation:
    pip install numpy pyaudiowpatch etherlight scipy

Verwendung:
    python script.py          # LED-Visualisierung
    python script.py test     # LED-Mapping Test
    python script.py monitor  # Audio-Monitoring
    python script.py debug    # Audio-Geräte anzeigen
"""

import time
import math
import sys
import numpy as np
import threading
from queue import Queue
from collections import deque
from etherlight import Etherlight

# Scipy für bessere Filterung (optional)
try:
    from scipy import signal
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("⚠ Scipy nicht gefunden - Beat-Detection limitiert")
    print("  Installiere mit: pip install scipy")

# ----------- USER CONFIG -----------
# Switch IPs
SW_UNTEN_IP = "172.16.26.138"   # Unterer Switch (Reihe 1+2)
SW_OBEN_IP = "172.16.26.139"    # Oberer Switch (Reihe 3+4)

# Soundbar Konfiguration
NUM_COLUMNS = 24        # 24 Säulen horizontal
LEDS_PER_COLUMN = 4     # 4 LEDs pro Säule (vertikal)
LEDS_PER_SWITCH = 48    # 48 LEDs pro Switch (24 × 2 Reihen)

# Audio Konfiguration
SAMPLE_RATE = 44100
BLOCKSIZE = 2048
FPS = 60

# Frequenzbänder (Hz) - jede Säule hat ihr eigenes Band
# Logarithmisch verteilt für bessere Musikwahrnehmung
FREQ_BANDS = [
    (20, 60),      # Sub-Bass
    (60, 100),     # Bass 1
    (100, 150),    # Bass 2
    (150, 200),    # Bass 3
    (200, 300),    # Low Mids 1
    (300, 400),    # Low Mids 2
    (400, 500),    # Low Mids 3
    (500, 700),    # Mids 1
    (700, 900),    # Mids 2
    (900, 1200),   # Mids 3
    (1200, 1500),  # Mids 4
    (1500, 2000),  # High Mids 1
    (2000, 2500),  # High Mids 2
    (2500, 3000),  # High Mids 3
    (3000, 4000),  # Highs 1
    (4000, 5000),  # Highs 2
    (5000, 6000),  # Highs 3
    (6000, 7000),  # Highs 4
    (7000, 8000),  # Highs 5
    (8000, 10000), # Very Highs 1
    (10000, 12000),# Very Highs 2
    (12000, 14000),# Very Highs 3
    (14000, 16000),# Very Highs 4
    (16000, 20000) # Ultra Highs
]

# Amplituden-Verarbeitung pro Band
DECAY_FAST = 0.7        # Schneller Abfall für responsive Visualisierung
DECAY_SLOW = 0.9        # Langsamer Abfall für smooth Bewegung
MIN_DB = -80.0          # Minimale Lautstärke
MAX_DB = -10.0          # Maximale Lautstärke

# Beat-Detection Parameter
BEAT_HISTORY_SIZE = 43  # ~1 Sekunde bei 44100/1024
BEAT_THRESHOLD = 1.5    # Multiplikator über Durchschnitt
BEAT_MIN_INTERVAL = 0.1 # Min. 100ms zwischen Beats
BASS_BOOST_ON_BEAT = 2.0# Verstärkung bei Beat
BASS_FREQ_MAX = 200     # Frequenzen unter 200Hz sind "Bass"

# Farben
HUE_BASS = 0.0          # Rot für Bass/Beat
HUE_MIDS = 60/360.0     # Gelb für Mitten
HUE_HIGHS = 200/360.0   # Blau für Höhen

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


def db_scale(db, min_db=MIN_DB, max_db=MAX_DB):
    """Skaliert dB-Wert auf 0-1"""
    if db <= min_db:
        return 0.0
    if db >= max_db:
        return 1.0
    return (db - min_db) / (max_db - min_db)


def debug_devices():
    """Zeigt alle verfügbaren Audio-Geräte an"""
    print("\n" + "="*70)
    print("DEBUG: Alle verfügbaren Audio-Geräte")
    print("="*70)
    
    p = pyaudio.PyAudio()
    
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        print(f"\n✓ WASAPI verfügbar")
    except OSError:
        print("\n✗ WASAPI nicht verfügbar!")
        p.terminate()
        return
    
    print(f"\nAnzahl Geräte: {p.get_device_count()}")
    
    loopback_devices = []
    
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        
        if info.get('isLoopbackDevice', False):
            loopback_devices.append((i, info))
            print(f"\n[{i}] 🔁 LOOPBACK")
            print(f"  {info['name']}")
    
    print("\n" + "="*70)
    if loopback_devices:
        print("✓ LOOPBACK-GERÄTE:")
        for idx, info in loopback_devices:
            print(f"  [{idx}] {info['name']}")
    print("="*70 + "\n")
    
    p.terminate()


class BeatDetector:
    """Erkennt Beats in Bass-Frequenzen"""
    
    def __init__(self, history_size=BEAT_HISTORY_SIZE):
        self.bass_history = deque(maxlen=history_size)
        self.last_beat_time = 0
        self.beat_strength = 0.0
    
    def detect_beat(self, bass_energy):
        """
        Erkennt Beat basierend auf Bass-Energie
        Returns: (is_beat, beat_strength)
        """
        self.bass_history.append(bass_energy)
        
        if len(self.bass_history) < 10:
            return False, 0.0
        
        # Berechne Durchschnitt und Varianz
        avg = np.mean(self.bass_history)
        std = np.std(self.bass_history)
        
        # Beat wenn aktuelle Energie deutlich über Durchschnitt
        threshold = avg + (std * BEAT_THRESHOLD)
        
        current_time = time.time()
        is_beat = False
        
        if bass_energy > threshold:
            # Verhindere zu schnelle Beat-Erkennung
            if current_time - self.last_beat_time > BEAT_MIN_INTERVAL:
                is_beat = True
                self.last_beat_time = current_time
                # Stärke basiert auf wie weit über Threshold
                self.beat_strength = min((bass_energy - avg) / (threshold - avg), 2.0)
        
        # Decay beat strength
        self.beat_strength *= 0.8
        
        return is_beat, self.beat_strength


class FrequencyBandAnalyzer:
    """Analysiert einzelne Frequenzbänder unabhängig"""
    
    def __init__(self, freq_min, freq_max, sample_rate=SAMPLE_RATE):
        self.freq_min = freq_min
        self.freq_max = freq_max
        self.sample_rate = sample_rate
        self.prev_level = 0.0
        
        # Bestimme Decay basierend auf Frequenz
        # Bass = langsamer Decay, Höhen = schneller Decay
        if freq_max < 200:
            self.decay = DECAY_SLOW
        elif freq_min > 5000:
            self.decay = DECAY_FAST
        else:
            # Interpoliere zwischen slow und fast
            t = (freq_min - 200) / (5000 - 200)
            self.decay = DECAY_SLOW + (DECAY_FAST - DECAY_SLOW) * t
    
    def analyze(self, fft_data, freqs):
        """
        Analysiert FFT-Daten für dieses Frequenzband
        Returns: normalized level (0-1)
        """
        # Finde Indices für dieses Frequenzband
        idx = np.where((freqs >= self.freq_min) & (freqs <= self.freq_max))[0]
        
        if idx.size == 0:
            # Keine Daten in diesem Band
            self.prev_level *= self.decay
            return self.prev_level
        
        # Berechne durchschnittliche Amplitude in diesem Band
        band_amplitude = np.mean(fft_data[idx])
        
        # Normalisierung: FFT gibt große Werte
        # Teile durch Anzahl Samples für Normalisierung
        band_amplitude = band_amplitude / (len(fft_data) * 2)
        
        # Konvertiere zu dB
        band_db = mag_to_db(band_amplitude)
        
        # Skaliere auf 0-1
        level = db_scale(band_db)
        
        # Smooth mit Decay (aber nimm Maximum von neu und decay)
        # Das gibt responsive peaks aber smooth decay
        self.prev_level = max(level, self.prev_level * self.decay)
        
        return self.prev_level
    
    def get_color_hue(self):
        """Bestimmt Farbe basierend auf Frequenz"""
        if self.freq_max <= 200:
            return HUE_BASS  # Rot für Bass
        elif self.freq_min >= 5000:
            return HUE_HIGHS  # Blau für Höhen
        else:
            # Interpoliere zwischen Bass und Highs über Mitten
            t = (self.freq_min - 200) / (5000 - 200)
            return HUE_BASS + (HUE_HIGHS - HUE_BASS) * t


class SwitchController:
    """Kontrolliert einen einzelnen Switch mit Threading"""
    
    def __init__(self, ip, name, num_leds=LEDS_PER_SWITCH):
        self.ip = ip
        self.name = name
        self.num_leds = num_leds
        
        print(f"🔌 Verbinde mit {name} ({ip})...", flush=True)
        self.ether = Etherlight(ip)
        time.sleep(0.5)
        print(f"✓ {name} verbunden ({num_leds} LEDs)", flush=True)
        
        # Threading
        self.update_queue = Queue(maxsize=10)
        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
    
    def _update_loop(self):
        """Thread-Loop für LED-Updates"""
        while self.running:
            try:
                if not self.update_queue.empty():
                    led_colors = self.update_queue.get(timeout=0.1)
                    
                    # Setze alle LEDs
                    for led_idx, color in enumerate(led_colors):
                        try:
                            self.ether.set_led_color(led_idx + 1, color)
                        except:
                            pass
                    
                    # Flush
                    try:
                        self.ether.flush()
                    except:
                        pass
                else:
                    time.sleep(0.001)
                    
            except Exception as e:
                if self.running:
                    print(f"✗ {self.name} Update-Fehler: {e}", flush=True)
    
    def update_leds(self, led_colors):
        """Aktualisiert LEDs"""
        if len(led_colors) != self.num_leds:
            return
        
        try:
            if self.update_queue.full():
                self.update_queue.get_nowait()
            self.update_queue.put_nowait(led_colors)
        except:
            pass
    
    def cleanup(self):
        """Beendet Thread"""
        self.running = False
        if self.update_thread.is_alive():
            self.update_thread.join(timeout=2.0)
        
        # LEDs aus
        try:
            for i in range(1, self.num_leds + 1):
                self.ether.set_led_color(i, (0, 0, 0))
            self.ether.flush()
        except:
            pass
        
        print(f"✓ {self.name} beendet", flush=True)


class DualSwitchAudioVisualizer:
    """
    Audio Visualizer mit Beat-Detection und unabhängigen Frequenzbändern
    """
    
    def __init__(self, monitor_only=False):
        self.monitor_only = monitor_only
        self.running = True
        
        # Initialisiere Frequenzband-Analyzer für jede Säule
        self.band_analyzers = []
        for freq_min, freq_max in FREQ_BANDS:
            analyzer = FrequencyBandAnalyzer(freq_min, freq_max)
            self.band_analyzers.append(analyzer)
        
        # Beat-Detector
        self.beat_detector = BeatDetector()
        
        # Audio
        self.device_name = "Unbekannt"
        self.p = None
        self.stream = None
        
        # Stats
        self.frame_count = 0
        self.last_stats_time = time.time()
        self.current_fps = 0
        
        # Switch-Controller
        if not monitor_only:
            print("\n🎛️  Initialisiere Dual-Switch Soundbar...")
            print(f"   └─ Unten: {SW_UNTEN_IP} (Reihe 1+2)")
            print(f"   └─ Oben:  {SW_OBEN_IP} (Reihe 3+4)")
            print(f"   └─ 24 unabhängige Frequenzbänder")
            print(f"   └─ Beat-Detection aktiviert\n")
            
            self.sw_unten = SwitchController(SW_UNTEN_IP, "SW_UNTEN")
            self.sw_oben = SwitchController(SW_OBEN_IP, "SW_OBEN")
            
            print("✓ Beide Switches bereit!\n")
        else:
            self.sw_unten = None
            self.sw_oben = None
    
    def process_audio(self, audio_data):
        """Verarbeitet Audio mit Beat-Detection und Band-Analyse"""
        
        # Apply Hanning window
        window = np.hanning(len(audio_data))
        audio_data = audio_data * window
        
        # FFT
        fft = np.abs(np.fft.rfft(audio_data))
        freqs = np.fft.rfftfreq(len(audio_data), 1.0 / SAMPLE_RATE)
        
        # Berechne Bass-Energie für Beat-Detection
        bass_idx = np.where(freqs <= BASS_FREQ_MAX)[0]
        bass_energy = np.mean(fft[bass_idx]) if bass_idx.size > 0 else 0.0
        
        # Beat-Detection
        is_beat, beat_strength = self.beat_detector.detect_beat(bass_energy)
        
        # Analysiere jedes Frequenzband unabhängig
        levels = []
        for analyzer in self.band_analyzers:
            level = analyzer.analyze(fft, freqs)
            
            # Verstärke Bass-Bänder bei Beat
            if analyzer.freq_max <= BASS_FREQ_MAX and is_beat:
                level = min(level * (1.0 + beat_strength), 1.0)
            
            levels.append(level)
        
        levels = np.array(levels)
        
        # Stats
        self.frame_count += 1
        current_time = time.time()
        if current_time - self.last_stats_time >= 1.0:
            self.current_fps = self.frame_count
            self.frame_count = 0
            self.last_stats_time = current_time
        
        if self.monitor_only:
            # ASCII-Visualisierung mit Beat-Anzeige
            max_level = float(np.max(levels))
            avg_level = float(np.mean(levels))
            
            bars = ''.join([
                '█' if l > 0.7 else 
                '▓' if l > 0.4 else 
                '░' if l > 0.1 else ' ' 
                for l in levels
            ])
            
            beat_indicator = "💥 BEAT!" if is_beat else "      "
            print(f"\r🔊 [{bars}] Max:{max_level:.2f} Avg:{avg_level:.2f} {beat_indicator} FPS:{self.current_fps}", 
                  end='', flush=True)
        else:
            # LED-Update
            self.update_switches(levels, is_beat, beat_strength)
    
    def update_switches(self, levels, is_beat, beat_strength):
        """Verteilt Levels auf beide Switches mit Beat-Effekten"""
        if self.sw_unten is None or self.sw_oben is None:
            return
        
        leds_unten = [(0, 0, 0)] * LEDS_PER_SWITCH
        leds_oben = [(0, 0, 0)] * LEDS_PER_SWITCH
        
        for col in range(NUM_COLUMNS):
            level = levels[col]
            analyzer = self.band_analyzers[col]
            
            # Anzahl LEDs basierend auf Level
            num_leds_lit = int(round(level * LEDS_PER_COLUMN))
            
            # Farbe basierend auf Frequenz
            hue = analyzer.get_color_hue()
            
            # Helligkeit: höher bei höherem Level
            value = 0.5 + 0.5 * level
            
            # Bei Beat: erhöhe Sättigung für Bass-Säulen
            if is_beat and analyzer.freq_max <= BASS_FREQ_MAX:
                saturation = 1.0
                value = min(value * (1.0 + beat_strength * 0.5), 1.0)
            else:
                saturation = 0.9
            
            rgb = hsv_to_rgb255(hue, saturation, value)
            
            # Setze LEDs von unten nach oben
            if num_leds_lit >= 1:
                leds_unten[col] = rgb
            
            if num_leds_lit >= 2:
                leds_unten[24 + col] = rgb
            
            if num_leds_lit >= 3:
                leds_oben[col] = rgb
            
            if num_leds_lit >= 4:
                leds_oben[24 + col] = rgb
        
        # Update beide Switches parallel
        self.sw_unten.update_leds(leds_unten)
        self.sw_oben.update_leds(leds_oben)
    
    def cleanup(self):
        """Cleanup"""
        print("\n🛑 Beende Visualizer...", flush=True)
        self.running = False
        
        try:
            if self.stream:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
                self.stream = None
        except:
            pass
        
        try:
            if self.p:
                self.p.terminate()
                self.p = None
        except:
            pass
        
        if self.sw_unten:
            self.sw_unten.cleanup()
        if self.sw_oben:
            self.sw_oben.cleanup()
        
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except:
            pass
        
        print("✓ Beendet", flush=True)
    
    def run(self, device_index=None):
        """Hauptschleife"""
        try:
            self.p = pyaudio.PyAudio()
            
            if device_index is None:
                try:
                    wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
                    default_speakers = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
                    
                    print(f"🔍 Lautsprecher: {default_speakers['name']}", flush=True)
                    
                    if not default_speakers.get("isLoopbackDevice", False):
                        print("🔍 Suche Loopback...", flush=True)
                        for loopback in self.p.get_loopback_device_info_generator():
                            if default_speakers["name"] in loopback["name"]:
                                default_speakers = loopback
                                print(f"✓ Loopback: {loopback['name']}", flush=True)
                                break
                        else:
                            print("✗ Kein Loopback!", flush=True)
                            return
                    
                    device_index = default_speakers["index"]
                    
                except Exception as e:
                    print(f"✗ Fehler: {e}", flush=True)
                    return
            
            device_info = self.p.get_device_info_by_index(device_index)
            self.device_name = device_info['name']
            
            print(f"\n🎵 Audio: {self.device_name}", flush=True)
            print(f"📊 24 Frequenzbänder | Beat-Detection aktiv", flush=True)
            print("⌨️  Drücke Ctrl+C zum Beenden\n", flush=True)
            
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=device_info['maxInputChannels'],
                rate=int(device_info['defaultSampleRate']),
                input=True,
                input_device_index=device_index,
                frames_per_buffer=BLOCKSIZE
            )
            
            self.stream.start_stream()
            
            while self.running and self.stream.is_active():
                try:
                    data = self.stream.read(BLOCKSIZE, exception_on_overflow=False)
                    audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                    
                    if len(audio_data) > BLOCKSIZE:
                        audio_data = audio_data.reshape(-1, device_info['maxInputChannels']).mean(axis=1)
                    
                    self.process_audio(audio_data)
                    
                except Exception as e:
                    if self.running:
                        print(f"\n✗ Fehler: {e}", flush=True)
                    break
                    
        except KeyboardInterrupt:
            print("\n⏸️  Unterbrochen", flush=True)
        except Exception as e:
            print(f"\n✗ Fehler: {e}", flush=True)
        finally:
            self.cleanup()


def test_switches():
    """LED-Test"""
    print("\n" + "="*70)
    print("  🧪 LED-MAPPING TEST")
    print("="*70 + "\n")
    
    try:
        sw_unten = SwitchController(SW_UNTEN_IP, "SW_UNTEN")
        sw_oben = SwitchController(SW_OBEN_IP, "SW_OBEN")
        
        print("\nTest: Säulenweise (24 Säulen)")
        for col in range(24):
            leds_unten = [(0, 0, 0)] * 48
            leds_oben = [(0, 0, 0)] * 48
            
            leds_unten[col] = (255, 0, 0)
            leds_unten[24 + col] = (255, 128, 0)
            leds_oben[col] = (255, 255, 0)
            leds_oben[24 + col] = (0, 255, 0)
            
            sw_unten.update_leds(leds_unten)
            sw_oben.update_leds(leds_oben)
            
            print(f"\r  Säule {col + 1}/24", end='', flush=True)
            time.sleep(0.1)
        
        print("\n✓ Test OK\n")
        
        sw_unten.cleanup()
        sw_oben.cleanup()
        
    except Exception as e:
        print(f"\n✗ Fehler: {e}")


def music_play(monitor_only=False):
    """Startet Visualizer"""
    print("\n" + "="*70)
    print("  🎛️  ADVANCED AUDIO VISUALIZER")
    print("="*70)
    print(f"  Features:")
    print(f"    • 24 unabhängige Frequenzbänder")
    print(f"    • Beat-Detection (Bass/Kick)")
    print(f"    • Frequenz-basierte Farben")
    print(f"    • Multi-threaded Updates")
    print("="*70 + "\n")
    
    viz = DualSwitchAudioVisualizer(monitor_only=monitor_only)
    
    try:
        viz.run()
    finally:
        viz.cleanup()


if __name__ == '__main__':
    try:
        music_play(monitor_only=True)
    except KeyboardInterrupt:
        print("\n⏹ Beendet", flush=True)
    except Exception as e:
        print(f"\n✗ Fehler: {e}", flush=True)
    