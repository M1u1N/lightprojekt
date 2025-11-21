"""
Etherlight Audio Visualizer mit verbessertem Debug und automatischer Erkennung

Installation:
    pip install numpy pyaudiowpatch etherlight

Verwendung:
    1. python script.py debug     # Zeigt alle verfügbaren Geräte an
    2. python script.py test      # Testet Audio-Erkennung
    3. python script.py monitor   # Monitor-Modus (nur Erkennung)
    4. python script.py           # LED-Visualisierung
"""

import time
import math
import sys
import os
import numpy as np
from etherlight import Etherlight

# ----------- USER CONFIG -----------
ETH_URL = "172.16.26.138"
NUM_LEDS = 52
COLUMNS = 4
SAMPLE_RATE = 44100
BLOCKSIZE = 2048
FPS = 30
DECAY = 0.85
MIN_DB = -80.0
MAX_DB = -10.0
HUE_GREEN = 120/360.0
HUE_RED = 0.0

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


def build_led_index_map(num_leds, columns):
    leds_per_col = num_leds // columns
    remainder = num_leds % columns
    map_cols = []
    idx = 0
    for c in range(columns):
        this_col_len = leds_per_col + (1 if c < remainder else 0)
        col_indices = [i + 1 for i in range(idx, idx + this_col_len)]
        map_cols.append(col_indices)
        idx += this_col_len
    return map_cols


def mag_to_db(mag):
    mag = max(mag, 1e-12)
    return 20.0 * math.log10(mag)


def db_scale(db):
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
    
    # Alle Geräte anzeigen
    print(f"\nAnzahl Geräte: {p.get_device_count()}")
    print("\n" + "-"*70)
    
    loopback_devices = []
    output_devices = []
    input_devices = []
    
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        
        device_type = "❓ Unbekannt"
        if info.get('isLoopbackDevice', False):
            device_type = "🔁 LOOPBACK"
            loopback_devices.append((i, info))
        elif info['maxOutputChannels'] > 0:
            device_type = "🔊 OUTPUT"
            output_devices.append((i, info))
        elif info['maxInputChannels'] > 0:
            device_type = "🎤 INPUT"
            input_devices.append((i, info))
        
        print(f"\n[{i}] {device_type}")
        print(f"  Name: {info['name']}")
        print(f"  Input Channels: {info['maxInputChannels']}")
        print(f"  Output Channels: {info['maxOutputChannels']}")
        print(f"  Default Sample Rate: {info['defaultSampleRate']}")
        print(f"  Host API: {info['hostApi']}")
    
    print("\n" + "="*70)
    print("ZUSAMMENFASSUNG:")
    print(f"  🔁 Loopback-Geräte: {len(loopback_devices)}")
    print(f"  🔊 Output-Geräte: {len(output_devices)}")
    print(f"  🎤 Input-Geräte: {len(input_devices)}")
    
    if loopback_devices:
        print("\n✓ LOOPBACK-GERÄTE GEFUNDEN (für System-Audio):")
        for idx, info in loopback_devices:
            print(f"  [{idx}] {info['name']}")
    else:
        print("\n⚠ KEINE Loopback-Geräte gefunden!")
        print("  Versuche Standard-Lautsprecher zu finden...")
        
        # Versuche Loopback über Generator zu finden
        try:
            print("\n  Suche mit get_loopback_device_info_generator():")
            for loopback in p.get_loopback_device_info_generator():
                print(f"  [{loopback['index']}] {loopback['name']}")
                loopback_devices.append((loopback['index'], loopback))
        except Exception as e:
            print(f"  Fehler: {e}")
    
    print("="*70 + "\n")
    
    p.terminate()
    return loopback_devices


def test_audio_capture(device_index=None):
    """Testet Audio-Capture von einem bestimmten Gerät"""
    print("\n" + "="*70)
    print("TEST: Audio-Capture")
    print("="*70)
    
    p = pyaudio.PyAudio()
    
    # Finde Loopback-Gerät
    if device_index is None:
        try:
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            
            print(f"\nStandard-Lautsprecher: {default_speakers['name']}")
            
            # Suche Loopback
            if not default_speakers.get("isLoopbackDevice", False):
                print("Suche Loopback-Version...")
                for loopback in p.get_loopback_device_info_generator():
                    if default_speakers["name"] in loopback["name"]:
                        default_speakers = loopback
                        print(f"✓ Loopback gefunden: {loopback['name']}")
                        break
                else:
                    print("✗ Kein Loopback gefunden!")
                    p.terminate()
                    return
            
            device_index = default_speakers["index"]
            
        except Exception as e:
            print(f"✗ Fehler bei automatischer Erkennung: {e}")
            p.terminate()
            return
    
    device_info = p.get_device_info_by_index(device_index)
    print(f"\nVerwende Gerät [{device_index}]: {device_info['name']}")
    print(f"Kanäle: {device_info['maxInputChannels']}")
    print("\n🎵 Spiele jetzt Audio ab (Spotify, YouTube, etc.)")
    print("🔊 Audio-Level-Anzeige (10 Sekunden):\n")
    
    # Audio-Stream öffnen
    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=device_info['maxInputChannels'],
            rate=int(device_info['defaultSampleRate']),
            input=True,
            input_device_index=device_index,
            frames_per_buffer=1024
        )
        
        stream.start_stream()
        
        # 10 Sekunden Audio testen
        for i in range(50):  # 50 x 0.2s = 10s
            data = stream.read(1024, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Level berechnen
            rms = np.sqrt(np.mean(audio_data**2))
            db = 20 * np.log10(max(rms, 1e-10))
            
            # Visualisierung
            bars = int((db + 60) / 60 * 40)  # -60dB bis 0dB auf 40 chars
            bars = max(0, min(40, bars))
            
            print(f"\r{'█' * bars}{' ' * (40 - bars)} {db:>6.1f} dB", end='', flush=True)
            time.sleep(0.2)
        
        print("\n\n✓ Test abgeschlossen")
        
        stream.stop_stream()
        stream.close()
        
    except Exception as e:
        print(f"\n✗ Fehler beim Audio-Capture: {e}")
    
    p.terminate()
    print("="*70 + "\n")


class EtherlightAudioVisualizer:
    def __init__(self, ether_ip, num_leds=NUM_LEDS, columns=COLUMNS, monitor_only=False):
        self.monitor_only = monitor_only
        
        if not monitor_only:
            self.ether = Etherlight(ether_ip)
            time.sleep(1.0)
        else:
            self.ether = None
        
        self.num_leds = num_leds
        self.columns = columns
        self.col_map = build_led_index_map(num_leds, columns)
        self.leds_per_col = [len(c) for c in self.col_map]
        self.prev_levels = np.zeros(columns)
        self.last_update = 0.0
        self.audio_detected = False
        self.last_audio_check = 0.0
        self.audio_check_interval = 1.0
        self.device_name = "Unbekannt"
        self.p = None
        self.stream = None
        self.running = True

    def process_audio(self, audio_data):
        # DEBUG: Zeige rohe Audio-Daten
        raw_rms = np.sqrt(np.mean(audio_data**2))
        raw_peak = np.max(np.abs(audio_data))
        
        # Apply window
        window = np.hanning(len(audio_data))
        audio_data = audio_data * window
        
        # FFT
        fft = np.abs(np.fft.rfft(audio_data))
        freqs = np.fft.rfftfreq(len(audio_data), 1.0 / SAMPLE_RATE)
        
        # DEBUG: Zeige FFT-Werte
        fft_max = np.max(fft)
        fft_mean = np.mean(fft)
        
        # Frequency bands
        fmin = 20.0
        fmax = 16000.0
        band_edges = np.logspace(math.log10(fmin), math.log10(fmax), num=self.columns + 1)
        band_amps = np.zeros(self.columns)
        
        for i in range(self.columns):
            lo = band_edges[i]
            hi = band_edges[i + 1]
            idx = np.where((freqs >= lo) & (freqs < hi))[0]
            if idx.size > 0:
                band_amps[i] = np.mean(fft[idx])
        
        # DEBUG: Zeige Band-Amplituden VOR Skalierung
        band_max_before = np.max(band_amps)
        band_mean_before = np.mean(band_amps)
        
        # Normalisiere FFT-Werte (wichtig!)
        # FFT gibt sehr große Werte zurück - normalisieren auf 0-1
        band_amps = band_amps / (len(audio_data) / 2)  # Normalisierung
        
        # Convert to dB and scale
        with np.errstate(divide='ignore'):
            band_db = np.array([mag_to_db(a) for a in band_amps])
        band_scaled = np.array([db_scale(d) for d in band_db])
        
        # Smooth
        self.prev_levels = np.maximum(self.prev_levels * DECAY, band_scaled)
        
        # Monitor-Modus mit DEBUG-Ausgabe
        if self.monitor_only:
            max_level = float(np.max(self.prev_levels))
            avg_level = float(np.mean(self.prev_levels))
            now = time.time()
            
            # DEBUG: Zeige alle Zwischenschritte
            if now - self.last_audio_check >= 1.0:  # Jede Sekunde im Debug
                print(f"\n{'='*60}")
                print(f"🔍 DEBUG - Audio-Verarbeitung:")
                print(f"{'='*60}")
                print(f"1. Rohe Audio-Daten:")
                print(f"   RMS: {raw_rms:.6f}, Peak: {raw_peak:.6f}")
                print(f"2. FFT-Werte:")
                print(f"   Max: {fft_max:.2f}, Mean: {fft_mean:.2f}")
                print(f"3. Band-Amplituden (vor Normalisierung):")
                print(f"   Max: {band_max_before:.2f}, Mean: {band_mean_before:.2f}")
                print(f"4. Nach dB-Skalierung (0-1):")
                print(f"   Peak: {max_level:.3f}, Durchschnitt: {avg_level:.3f}")
                print(f"5. Band-Levels einzeln:")
                for i, lvl in enumerate(self.prev_levels):
                    print(f"   Band {i}: {lvl:.3f}")
                
                if max_level > 0.05:
                    print(f"\n✓ Audio erkannt von: {self.device_name}")
                    self.audio_detected = True
                else:
                    print(f"\n✗ Kein Audio (unter Schwellenwert 0.05)")
                    self.audio_detected = False
                
                self.last_audio_check = now
        else:
            # LED-Update
            now = time.time()
            if now - self.last_update >= (1.0 / FPS):
                self.update_lights(self.prev_levels)
                self.last_update = now

    def update_lights(self, levels):
        if self.ether is None:
            return
            
        for c, lvl in enumerate(levels):
            n_lit = int(round(lvl * self.leds_per_col[c]))
            for i_in_col, led_index in enumerate(self.col_map[c]):
                lit = 1 if i_in_col < n_lit else 0
                if lit:
                    hue = HUE_GREEN + (HUE_RED - HUE_GREEN) * lvl
                    value = 0.6 + 0.4 * lvl
                    rgb = hsv_to_rgb255(hue, 1.0, value)
                else:
                    rgb = (0, 0, 0)
                try:
                    self.ether.set_led_color(led_index, rgb)
                except:
                    pass
        try:
            self.ether.flush()
        except:
            pass

    def cleanup(self):
        """Sauberes Beenden - schließt alle Streams und gibt Ressourcen frei"""
        self.running = False
        
        try:
            if self.stream:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
                self.stream = None
        except Exception as e:
            print(f"Fehler beim Schließen des Streams: {e}")
        
        try:
            if self.p:
                self.p.terminate()
                self.p = None
        except Exception as e:
            print(f"Fehler beim Terminieren von PyAudio: {e}")
        
        # Schließe stdout/stderr ordentlich
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except:
            pass

    def run(self, device_index=None):
        try:
            self.p = pyaudio.PyAudio()
            
            # Finde Loopback-Gerät
            if device_index is None:
                try:
                    wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
                    default_speakers = self.p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
                    
                    print(f"Standard-Lautsprecher: {default_speakers['name']}", flush=True)
                    
                    # Suche Loopback
                    if not default_speakers.get("isLoopbackDevice", False):
                        print("Suche Loopback...", flush=True)
                        for loopback in self.p.get_loopback_device_info_generator():
                            if default_speakers["name"] in loopback["name"]:
                                default_speakers = loopback
                                print(f"✓ Gefunden: {loopback['name']}", flush=True)
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
            
            print(f"\n🎵 Audio-Capture von: {self.device_name}", flush=True)
            print("Drücke Ctrl+C zum Beenden\n", flush=True)
            
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
                    
                    # Mix zu Mono
                    if len(audio_data) > BLOCKSIZE:
                        audio_data = audio_data.reshape(-1, device_info['maxInputChannels']).mean(axis=1)
                    
                    self.process_audio(audio_data)
                except Exception as e:
                    if self.running:  # Nur Fehler anzeigen wenn noch aktiv
                        print(f"\n✗ Fehler bei Audio-Verarbeitung: {e}", flush=True)
                    break
                
        except KeyboardInterrupt:
            print("\n⏹ Stoppe...", flush=True)
        except Exception as e:
            print(f"\n✗ Fehler: {e}", flush=True)
        finally:
            self.cleanup()


def music_play(monitor_only=False):
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║  Etherlight Audio Visualizer - System Audio              ║")
    print("╚═══════════════════════════════════════════════════════════╝\n")
    
    if monitor_only:
        print("👁️  Modus: Audio-Monitoring")
    else:
        print("🎨 Modus: LED-Visualisierung")
    
    viz = EtherlightAudioVisualizer(ETH_URL, num_leds=NUM_LEDS, columns=COLUMNS, 
                                     monitor_only=monitor_only)
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
                test_audio_capture()
            elif cmd == 'monitor':
                music_play(monitor_only=True)
            else:
                print("Verwendung:")
                print("  python script.py debug    - Zeigt alle Geräte")
                print("  python script.py test     - Testet Audio-Capture")
                print("  python script.py monitor  - Nur Audio-Monitoring")
                print("  python script.py          - LED-Visualisierung")
        else:
            music_play(monitor_only=False)
    except KeyboardInterrupt:
        print("\n⏹ Programm beendet", flush=True)
    except Exception as e:
        print(f"\n✗ Unerwarteter Fehler: {e}", flush=True)
    finally:
        # Finale Cleanup
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except:
            pass