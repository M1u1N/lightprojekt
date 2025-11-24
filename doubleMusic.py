"""
Etherlight Dual-Switch Audio Visualizer - OPTIMIZED VERSION

Soundbar-Aufbau (KORRIGIERT):
    - 24 Säulen (horizontal) × 4 LEDs hoch (vertikal) = 96 LEDs gesamt
    - Switch Unten: Port 1,3,5,7... = Reihe 1 | Port 2,4,6,8... = Reihe 2
    - Switch Oben:  Port 1,3,5,7... = Reihe 3 | Port 2,4,6,8... = Reihe 4

Performance-Optimierungen:
    ✓ Vorberechnete LED-Mappings
    ✓ Minimale Array-Operationen
    ✓ Direkte RGB-Berechnung ohne HSV
    ✓ Batch-Updates ohne Queue
    ✓ Numpy Vectorization
    ✓ Cache-freundliche Datenstrukturen

Installation:
    pip install numpy pyaudiowpatch etherlight scipy
"""

import time
import random
import sys
import numpy as np
import threading
from collections import deque
from etherlightwin import Etherlight

# Scipy für bessere Filterung
try:
    from scipy import signal
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# ----------- KORREKTE LED-MAPPINGS -----------
FIRST_ROW = [1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33,35,37,39,41,43,45,47]
SECOND_ROW = [2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48]

# ----------- USER CONFIG -----------
SW_UNTEN_IP = "172.16.146.212"
SW_OBEN_IP = "172.16.26.138"

NUM_COLUMNS = 24
LEDS_PER_COLUMN = 4

# Audio Config - Optimiert für Speed
SAMPLE_RATE = 44100
BLOCKSIZE = 512  # Kleiner = weniger Latenz aber mehr CPU

# Frequenzbänder - 24 Bänder optimiert für Musik
FREQ_BANDS = [
    (0, 60) ,(60, 100), (80, 140), (140, 180), (170, 230),
    (230, 280), (280, 350), (350, 440), (440, 550), (550, 700),
    (700, 880), (880, 1100), (1100, 1400), (1400, 1760), (1760, 2200),
    (2200, 2800), (2800, 3500), (3500, 4400), (4400, 5500), (5500, 7000),
    (7000, 8800), (8800, 11000), (11000, 14000), (14000, 18000)
]


# Verarbeitung
DECAY_FAST = 0.80       # Noch langsamer = LEDs bleiben noch länger an
DECAY_SLOW = 0.94       # Noch langsamer = smooth
MIN_DB = -95.0          # Noch niedriger = noch empfindlicher
MAX_DB = -3.0           # Noch höher = mehr Dynamik
BASS_BOOST = 1.8        # Extra Verstärkung für Bass
MID_BOOST = 2.0         # Extra Verstärkung für Mitten (500-2000Hz)
HIGH_BOOST = 2.2        # Extra Verstärkung für Höhen (>5kHz)

# Beat-Detection
BEAT_HISTORY_SIZE = 43
BEAT_THRESHOLD = 1.5
BEAT_MIN_INTERVAL = 0.1
BASS_BOOST_ON_BEAT = 2.5
BASS_FREQ_MAX = 200

DISPLAY_ORDER = list(range(NUM_COLUMNS))
random.shuffle(DISPLAY_ORDER)


# PyAudio
try:
    import pyaudiowpatch as pyaudio
    HAS_PYAUDIO = True
except ImportError:
    print("✗ PyAudioWPatch nicht gefunden!")
    HAS_PYAUDIO = False
    sys.exit(1)


# ----------- OPTIMIERTE COLOR FUNCTIONS -----------
# Vorberechnete Lookup-Tables für schnellere Farbberechnung
COLOR_LUT_SIZE = 256
_color_lut = None

def init_color_lut():
    """Erstellt Lookup-Table für RGB-Farben basierend auf Frequenz"""
    global _color_lut
    _color_lut = np.zeros((COLOR_LUT_SIZE, 3), dtype=np.uint8)
    
    for i in range(COLOR_LUT_SIZE):
        # 0 = Bass (Rot), 128 = Mids (Gelb), 255 = Highs (Blau)
        t = i / COLOR_LUT_SIZE
        
        if t < 0.33:  # Bass -> Mids
            s = t / 0.33
            r = int(255 * (1 - s) + 255 * s)
            g = int(0 * (1 - s) + 255 * s)
            b = 0
        elif t < 0.66:  # Mids -> Highs
            s = (t - 0.33) / 0.33
            r = int(255 * (1 - s) + 100 * s)
            g = int(255 * (1 - s) + 150 * s)
            b = int(0 * (1 - s) + 255 * s)
        else:  # Highs
            s = (t - 0.66) / 0.34
            r = int(100 * (1 - s) + 50 * s)
            g = int(150 * (1 - s) + 100 * s)
            b = int(255 * (1 - s) + 255 * s)
        
        _color_lut[i] = [r, g, b]

def get_color_fast(freq_max, level, beat_boost=1.0):
    """Ultra-schnelle Farbberechnung mit LUT"""
    # Frequenz zu LUT-Index
    if freq_max <= 200:
        idx = 0
    elif freq_max >= 18000:
        idx = COLOR_LUT_SIZE - 1
    else:
        # Log-Scale für bessere Verteilung
        idx = int((np.log10(freq_max) - np.log10(200)) / 
                  (np.log10(18000) - np.log10(200)) * COLOR_LUT_SIZE)
        idx = max(0, min(COLOR_LUT_SIZE - 1, idx))
    
    # Basis-Farbe aus LUT
    r, g, b = _color_lut[idx]
    
    # Helligkeit basierend auf Level
    brightness = 0.3 + 0.7 * level * beat_boost
    brightness = min(1.0, brightness)
    
    return (int(r * brightness), int(g * brightness), int(b * brightness))


def mag_to_db(mag):
    """Schnelle dB-Konvertierung"""
    return 20.0 * np.log10(np.maximum(mag, 1e-12))

def db_scale_vec(db_array):
    """Vektorisierte dB-Skalierung"""
    return np.clip((db_array - MIN_DB) / (MAX_DB - MIN_DB), 0.0, 1.0)


class BeatDetector:
    """Optimierter Beat-Detector"""
    
    def __init__(self, history_size=BEAT_HISTORY_SIZE):
        self.bass_history = deque(maxlen=history_size)
        self.last_beat_time = 0
        self.beat_strength = 0.0
        self._history_array = np.zeros(history_size)
        self._idx = 0
    
    def detect_beat(self, bass_energy):
        """Schnelle Beat-Detection mit Ring-Buffer"""
        # Ring-Buffer für schnelleren Zugriff
        self._history_array[self._idx] = bass_energy
        self._idx = (self._idx + 1) % len(self._history_array)
        
        if np.count_nonzero(self._history_array) < 10:
            return False, 0.0
        
        # Numpy-optimierte Statistiken
        avg = np.mean(self._history_array)
        std = np.std(self._history_array)
        threshold = avg + (std * BEAT_THRESHOLD)
        
        current_time = time.time()
        is_beat = False
        
        if bass_energy > threshold:
            if current_time - self.last_beat_time > BEAT_MIN_INTERVAL:
                is_beat = True
                self.last_beat_time = current_time
                self.beat_strength = min((bass_energy - avg) / max(threshold - avg, 0.001), 2.0)
        
        self.beat_strength *= 0.8
        return is_beat, self.beat_strength


class FastBandAnalyzer:
    """Ultra-schneller Frequenzband-Analyzer"""
    
    def __init__(self, band_idx, freq_min, freq_max, sample_rate=SAMPLE_RATE):
        self.band_idx = band_idx
        self.freq_min = freq_min
        self.freq_max = freq_max
        self.prev_level = 0.0
        
        # Decay basierend auf Frequenz
        if freq_max < 200:
            self.decay = DECAY_SLOW
        elif freq_min > 5000:
            self.decay = DECAY_FAST
        else:
            t = (freq_min - 200) / (5000 - 200)
            self.decay = DECAY_SLOW + (DECAY_FAST - DECAY_SLOW) * t
        
        # Vorberechne FFT-Indices für dieses Band
        self.fft_size = BLOCKSIZE // 2 + 1
        freqs = np.fft.rfftfreq(BLOCKSIZE, 1.0 / sample_rate)
        self.idx_mask = (freqs >= freq_min) & (freqs <= freq_max)
        self.has_data = np.any(self.idx_mask)
    
    def analyze_fast(self, fft_data):
        """Optimierte Analyse ohne Array-Operationen wo möglich"""
        if not self.has_data:
            self.prev_level *= self.decay
            return self.prev_level
        
        # Numpy-Vektor-Operationen
        band_amplitude = np.mean(fft_data[self.idx_mask])
        band_amplitude = band_amplitude / (BLOCKSIZE * 2)
        
        # Extra Boost basierend auf Frequenzbereich
        if self.freq_min > 5000:
            # Hohe Frequenzen (>5kHz)
            band_amplitude *= HIGH_BOOST
        elif 500 <= self.freq_min <= 2000:
            # Mitten (500-2000Hz) - oft schwach
            band_amplitude *= MID_BOOST
        elif self.freq_max < 200:
            # Bass (<200Hz)
            band_amplitude *= BASS_BOOST
        
        # Schnelle dB-Konvertierung
        band_db = 20.0 * np.log10(max(band_amplitude, 1e-12))
        level = max(0.0, min(1.0, (band_db - MIN_DB) / (MAX_DB - MIN_DB)))
        
        # Smooth decay
        self.prev_level = max(level, self.prev_level * self.decay)
        return self.prev_level


class OptimizedSwitchController:
    """Maximale Performance Switch-Controller ohne Threading-Overhead"""
    
    def __init__(self, ip, name):
        self.ip = ip
        self.name = name
        self.ether = Etherlight(ip)
        time.sleep(0.3)
        print(f"✓ {name} verbunden", flush=True)
        
        # Vorallokierte Arrays
        self._led_buffer = [(0, 0, 0)] * 48
    
    def update_direct(self, led_colors):
        """Direktes Update ohne Queue - maximale Geschwindigkeit"""
        try:
            for led_idx, color in enumerate(led_colors):
                self.ether.set_led_color(led_idx + 1, color)
            self.ether.flush()
        except:
            pass
    
    def cleanup(self):
        """Cleanup"""
        try:
            for i in range(1, 49):
                self.ether.set_led_color(i, (0, 0, 0))
            self.ether.flush()
        except:
            pass
        print(f"✓ {self.name} beendet", flush=True)


class OptimizedDualSwitchVisualizer:
    """Maximale Performance Visualizer"""
    
    def __init__(self, monitor_only=False):
        self.monitor_only = monitor_only
        self.running = True
        
        # Initialisiere Color LUT
        init_color_lut()
        
        # Band-Analyzer mit vorberechneten Indices
        self.band_analyzers = [
            FastBandAnalyzer(i, fmin, fmax) 
            for i, (fmin, fmax) in enumerate(FREQ_BANDS)
        ]
        
        # Beat-Detector
        self.beat_detector = BeatDetector()
        
        # Vorallokierte Arrays für maximale Performance
        self._levels = np.zeros(NUM_COLUMNS, dtype=np.float32)
        self._leds_unten = [(0, 0, 0)] * 48
        self._leds_oben = [(0, 0, 0)] * 48
        
        # Vorberechnete LED-Mappings für O(1) Zugriff
        self._column_to_leds = []
        for col in range(NUM_COLUMNS):
            self._column_to_leds.append({
                'row1': FIRST_ROW[col] - 1,   # Unten Reihe 1
                'row2': SECOND_ROW[col] - 1,  # Unten Reihe 2
                'row3': FIRST_ROW[col] - 1,   # Oben Reihe 3
                'row4': SECOND_ROW[col] - 1   # Oben Reihe 4
            })
        
        # FFT Window vorberechnen
        self._window = np.hanning(BLOCKSIZE)
        
        # Stats
        self.frame_count = 0
        self.last_stats_time = time.time()
        self.current_fps = 0
        self.fps_samples = deque(maxlen=30)
        
        # Audio
        self.p = None
        self.stream = None
        
        # Switches
        if not monitor_only:
            print("\n🎛️  Initialisiere Switches...")
            self.sw_unten = OptimizedSwitchController(SW_UNTEN_IP, "SW_UNTEN")
            self.sw_oben = OptimizedSwitchController(SW_OBEN_IP, "SW_OBEN")
            print("✓ Beide Switches bereit!\n")
        else:
            self.sw_unten = None
            self.sw_oben = None
    
    def process_audio_fast(self, audio_data):
        """Ultra-optimierte Audio-Verarbeitung"""
        # Stelle sicher dass audio_data die richtige Länge hat
        if len(audio_data) != BLOCKSIZE:
            if len(audio_data) < BLOCKSIZE:
                # Padding mit Nullen
                audio_data = np.pad(audio_data, (0, BLOCKSIZE - len(audio_data)), mode='constant')
            else:
                # Trimmen auf BLOCKSIZE
                audio_data = audio_data[:BLOCKSIZE]
        
        # Windowing
        audio_data = audio_data * self._window
        
        # FFT
        fft = np.abs(np.fft.rfft(audio_data))
        
        # Bass-Energie für Beat
        bass_energy = np.mean(fft[:int(BASS_FREQ_MAX * BLOCKSIZE / SAMPLE_RATE)])
        is_beat, beat_strength = self.beat_detector.detect_beat(bass_energy)
        
        # Analysiere alle Bänder parallel
        for i, analyzer in enumerate(self.band_analyzers):
            level = analyzer.analyze_fast(fft)
            
            # Bass-Boost bei Beat
            if analyzer.freq_max <= BASS_FREQ_MAX and is_beat:
                level = min(level * (1.0 + beat_strength), 1.0)
            
            self._levels[i] = level
        
        # Stats
        self.frame_count += 1
        current_time = time.time()
        elapsed = current_time - self.last_stats_time
        
        if elapsed >= 1.0:
            instant_fps = self.frame_count / elapsed
            self.fps_samples.append(instant_fps)
            self.current_fps = int(np.mean(self.fps_samples))
            self.frame_count = 0
            self.last_stats_time = current_time
        
        if self.monitor_only:
            self._print_monitor()
        else:
            self._update_leds_fast(is_beat, beat_strength)
    
    def _print_monitor(self):
        """Monitoring-Ausgabe mit Säulen-Beschriftung"""
        bars = ''.join([
            '█' if l > 0.6 else '▓' if l > 0.4 else 
            '▒' if l > 0.25 else '░' if l > 0.1 else 
            '·' if l > 0.05 else ' '
            for l in self._levels
        ])
        
        max_level = np.max(self._levels)
        avg_level = np.mean(self._levels)
        
        # Erstelle Säulen-Nummern (1-24) - statisch oben
        column_numbers = ''.join([str(i % 10) for i in range(1, 25)])
        
        # Finde dunkelste Säulen (die nicht leuchten)
        dark_columns = [i+1 for i, l in enumerate(self._levels) if l < 0.05]
        dark_info = f" Dunkel:[{','.join(map(str, dark_columns))}]" if dark_columns else ""
        
        # Nutze ANSI-Codes um Cursor zu bewegen (keine neue Zeile)
        print(f"\r    {column_numbers}", end='')
        print(f"\r🔊 [{bars}] Max:{max_level:.2f} Avg:{avg_level:.2f} | FPS:{self.current_fps}{dark_info}".ljust(100), 
              end='\r', flush=True)
    
    def _update_leds_fast(self, is_beat, beat_strength):
        """Optimiertes LED-Update mit korrektem Mapping"""
        beat_boost = 1.0 + (beat_strength if is_beat else 0.0)
        
        # Reset Arrays
        for i in range(48):
            self._leds_unten[i] = (0, 0, 0)
            self._leds_oben[i] = (0, 0, 0)
        
        # Setze LEDs pro Säule
        for col in range(NUM_COLUMNS):
            level = self._levels[DISPLAY_ORDER[col]]
            num_leds_lit = int(round(level * LEDS_PER_COLUMN))
            
            if num_leds_lit == 0:
                continue
            
            # Farbe basierend auf Frequenz
            analyzer = self.band_analyzers[col]
            boost = beat_boost if analyzer.freq_max <= BASS_FREQ_MAX else 1.0
            color = get_color_fast(analyzer.freq_max, level, boost)
            
            # Mapping über vorberechnete Indices
            mapping = self._column_to_leds[col]
            
            if num_leds_lit >= 1:
                self._leds_unten[mapping['row1']] = color
            if num_leds_lit >= 2:
                self._leds_unten[mapping['row2']] = color
            if num_leds_lit >= 3:
                self._leds_oben[mapping['row3']] = color
            if num_leds_lit >= 4:
                self._leds_oben[mapping['row4']] = color
        
        # Direkte Updates ohne Queue
        self.sw_unten.update_direct(self._leds_unten)
        self.sw_oben.update_direct(self._leds_oben)
    
    def cleanup(self):
        """Cleanup"""
        print("\n🛑 Beende...", flush=True)
        self.running = False
        
        try:
            if self.stream:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
        except:
            pass
        
        try:
            if self.p:
                self.p.terminate()
        except:
            pass
        
        if self.sw_unten:
            self.sw_unten.cleanup()
        if self.sw_oben:
            self.sw_oben.cleanup()
        
        print("✓ Beendet", flush=True)
    
    def run(self):
        """Hauptschleife"""
        try:
            self.p = pyaudio.PyAudio()
            
            # Finde Loopback
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            
            if not default_speakers.get("isLoopbackDevice", False):
                for loopback in self.p.get_loopback_device_info_generator():
                    if default_speakers["name"] in loopback["name"]:
                        default_speakers = loopback
                        break
            
            device_index = default_speakers["index"]
            device_info = self.p.get_device_info_by_index(device_index)
            
            print(f"🎵 Audio: {device_info['name']}", flush=True)
            print(f"📊 24 Frequenzbänder | Buffer: {BLOCKSIZE}", flush=True)
            
            if self.monitor_only:
                print("\n" + "="*70)
                print("MONITORING MODE - Säulen-Übersicht:")
                print("="*70)
                # Zeige Frequenzbänder für jede Säule
                for i in range(0, 24, 6):  # 4 Zeilen mit je 6 Säulen
                    line = ""
                    for j in range(6):
                        col = i + j
                        if col < 24:
                            fmin, fmax = FREQ_BANDS[col]
                            # Formatierung: Säule [Freq-Range]
                            if fmax >= 1000:
                                line += f"{col+1:2d}[{fmin/1000:.1f}-{fmax/1000:.1f}k] "
                            else:
                                line += f"{col+1:2d}[{fmin:3.0f}-{fmax:3.0f}Hz] "
                    print(line)
                print("="*70)
                print("Die Zahlenreihe zeigt Säulen-Nummern:")
                print("    123456789012345678901234")
                print()
            
            print("⌨️  Ctrl+C zum Beenden\n", flush=True)
            
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
                    
                    # Multi-Channel zu Mono
                    if audio_data.ndim > 1 or len(audio_data) > BLOCKSIZE:
                        num_channels = device_info['maxInputChannels']
                        if len(audio_data) >= BLOCKSIZE * num_channels:
                            audio_data = audio_data[:BLOCKSIZE * num_channels].reshape(-1, num_channels).mean(axis=1)
                        elif audio_data.ndim > 1:
                            audio_data = audio_data.mean(axis=1)
                    
                    self.process_audio_fast(audio_data)
                except Exception as e:
                    if self.running:
                        print(f"\n✗ Audio-Fehler: {e}", flush=True)
                    break
                    
        except KeyboardInterrupt:
            print("\n⏸️  Unterbrochen", flush=True)
        except Exception as e:
            print(f"\n✗ Fehler: {e}", flush=True)
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()


def test_mapping():
    """Test des korrigierten LED-Mappings"""
    print("\n🧪 LED-MAPPING TEST\n")
    
    sw_unten = OptimizedSwitchController(SW_UNTEN_IP, "SW_UNTEN")
    sw_oben = OptimizedSwitchController(SW_OBEN_IP, "SW_OBEN")
    
    print("\nTest: Säulenweise von links nach rechts")
    for col in range(24):
        leds_unten = [(0, 0, 0)] * 48
        leds_oben = [(0, 0, 0)] * 48
        
        # Reihe 1 (unten, ungerade Ports)
        leds_unten[FIRST_ROW[col] - 1] = (255, 0, 0)
        # Reihe 2 (unten, gerade Ports)
        leds_unten[SECOND_ROW[col] - 1] = (255, 128, 0)
        # Reihe 3 (oben, ungerade Ports)
        leds_oben[FIRST_ROW[col] - 1] = (255, 255, 0)
        # Reihe 4 (oben, gerade Ports)
        leds_oben[SECOND_ROW[col] - 1] = (0, 255, 0)
        
        sw_unten.update_direct(leds_unten)
        sw_oben.update_direct(leds_oben)
        
        print(f"\rSäule {col + 1}/24", end='', flush=True)
        time.sleep(0.15)
    
    print("\n✓ Test OK\n")
    
    sw_unten.cleanup()
    sw_oben.cleanup()


# ----------- MODE SELECTION -----------
# 0 = Normal (LED-Visualisierung)
# 1 = Test (LED-Mapping Test)
# 2 = Monitoring (Audio-Monitoring ohne LEDs)
MODE = 2

if __name__ == '__main__':
    try:
        if MODE == 1:
            test_mapping()
        elif MODE == 2:
            viz = OptimizedDualSwitchVisualizer(monitor_only=True)
            viz.run()
        else:
            viz = OptimizedDualSwitchVisualizer(monitor_only=False)
            viz.run()
    except KeyboardInterrupt:
        print("\n⏹ Beendet", flush=True)
    except Exception as e:
        print(f"\n✗ Fehler: {e}", flush=True)
        import traceback
        traceback.print_exc()