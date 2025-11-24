import paramiko
import time
from threading import Lock

class Etherlight:
    def __init__(self, ip, user: str = "nwlab", password: str = None, key_filename: str = None):
        self.ip = ip
        self.user = user if user else "root"
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._lock = Lock()
        self._channel = None
        
        print(f"Versuche SSH-Verbindung zu {self.user}@{ip} herzustellen...")
        try:
            self.ssh.connect(
                hostname=ip,
                username=self.user,
                password=password,
                key_filename=key_filename,
                look_for_keys=True if not password else False,
                allow_agent=True if not password else False,
                timeout=10
            )
            print(f"✓ SSH-Verbindung erfolgreich hergestellt zu {self.user}@{ip}")
            
            # Persistenten Channel für Shell-Zugriff öffnen
            self._channel = self.ssh.invoke_shell()
            self._channel.settimeout(0.5)
            time.sleep(0.1)  # Kurz warten bis Shell bereit ist
            self._channel.recv(4096)  # Initial prompt lesen und verwerfen
            
        except paramiko.AuthenticationException:
            print(f"✗ SSH-Verbindung fehlgeschlagen: Authentifizierung abgelehnt")
            raise
        except Exception as e:
            print(f"✗ SSH-Verbindung fehlgeschlagen: {e}")
            raise
        
        self.write_command('echo "0" > /proc/led/led_mode', True, silent=True)
        print("✓ LED-Modus initialisiert")
        self.led_cache = []

    def write_command(self, command, flush=False, silent=False):
        """Optimierte Befehlsausführung mit persistentem Channel"""
        try:
            with self._lock:
                if self._channel and self._channel.active:
                    # Verwende persistenten Channel (viel schneller!)
                    self._channel.send(command + '\n')
                    
                    if flush:
                        time.sleep(0.01)  # Minimal delay
                        try:
                            self._channel.recv(1024)  # Output verwerfen
                        except:
                            pass
                    return True
                else:
                    # Fallback auf exec_command
                    stdin, stdout, stderr = self.ssh.exec_command(command)
                    if flush:
                        exit_status = stdout.channel.recv_exit_status()
                        return exit_status == 0
                    return True
        except Exception as e:
            if not silent:
                print(f"✗ Fehler beim Ausführen des Befehls: {e}")
            return False

    def set_led_values(self, led, r, g, b, a=100):
        """Direktes Setzen ohne Cache - optimiert für einzelne LEDs"""
        # Alle drei Befehle in einem einzigen SSH-Aufruf
        command = (f'echo "{led} r {r*100}" > /proc/led/led_color && '
                  f'echo "{led} g {g*100}" > /proc/led/led_color && '
                  f'echo "{led} b {b*100}" > /proc/led/led_color')
        return self.write_command(command, flush=True, silent=True)

    def set_led_color(self, led, color, a=100):
        r, g, b = color
        return self.set_led_values(led, r, g, b, a)

    def cache_led_color(self, led, color, a=100):
        """LED-Befehl zum Cache hinzufügen"""
        self.led_cache.append(f'{led} {hex(color[0])[2:].zfill(2)} {hex(color[1])[2:].zfill(2)} {hex(color[2])[2:].zfill(2)} {a}')

    def flush_led_cache(self):
        """Optimiertes Cache-Flush mit größeren Chunks"""
        if not self.led_cache:
            return
        
        # Größere Chunks für bessere Performance (50 statt 15)
        chunk_size = 50
        chunks = [self.led_cache[i:i + chunk_size] for i in range(0, len(self.led_cache), chunk_size)]
        
        # Alle Chunks in EINEM einzigen Befehl senden
        all_commands = []
        for chunk in chunks:
            command = "\\n".join(chunk)
            all_commands.append(f'printf "{command}" > /proc/led/led_code')
        
        # Mit && verketten für maximale Geschwindigkeit
        combined_command = " && ".join(all_commands)
        self.write_command(combined_command, flush=True, silent=True)
        
        self.led_cache = []

    def set_all_leds(self, color, a=100):
        """Optimierte Methode um alle LEDs gleichzeitig zu setzen"""
        r, g, b = color
        command = f'echo "{hex(r)[2:].zfill(2)} {hex(g)[2:].zfill(2)} {hex(b)[2:].zfill(2)} {a}" > /proc/led/led_all_port_code'
        return self.write_command(command, flush=True, silent=True)

    def batch_set_leds(self, led_colors):
        """
        Optimierte Batch-Operation für mehrere LEDs
        led_colors: Liste von (led, (r, g, b), alpha) Tupeln
        """
        commands = []
        for led, color, a in led_colors:
            r, g, b = color
            commands.append(f'echo "{led} {hex(r)[2:].zfill(2)} {hex(g)[2:].zfill(2)} {hex(b)[2:].zfill(2)} {a}" > /proc/led/led_code')
        
        # Alle Befehle mit && verketten
        combined = " && ".join(commands)
        return self.write_command(combined, flush=True, silent=True)

    def close(self):
        """SSH-Verbindung schließen"""
        if self._channel:
            self._channel.close()
        if self.ssh:
            self.ssh.close()
            print(f"✓ SSH-Verbindung zu {self.user}@{self.ip} geschlossen")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Beispiele für optimale Nutzung:
if __name__ == "__main__":
    with Etherlight("192.168.1.100", user="nwlab", password="password") as eth:
        
        # Methode 1: Einzelne LED (schnell)
        eth.set_led_color(1, (255, 0, 255), 100)
        
        # Methode 2: Alle LEDs gleichzeitig (am schnellsten für alle)
        eth.set_all_leds((255, 0, 255), 100)
        
        # Methode 3: Mehrere spezifische LEDs (optimal für Batch)
        led_colors = [
            (1, (255, 0, 0), 100),
            (2, (0, 255, 0), 100),
            (3, (0, 0, 255), 100),
        ]
        eth.batch_set_leds(led_colors)
        
        # Methode 4: Cache nutzen (gut für viele LEDs)
        for i in range(1, 53):
            eth.cache_led_color(i, (255, 255, 255), 50)
        eth.flush_led_cache()