import paramiko
import time
from threading import Lock

class Etherlight:
    def __init__(self, ip, user: str = "nwlab"):
        self.ip = ip
        self.user = user
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._lock = Lock()
        self._channel = None
        
        print(f"Versuche SSH-Verbindung zu {self.user}@{ip} herzustellen...")
        try:
            self.ssh.connect(ip, username=user)
            
            # Keep-Alive aktivieren
            transport = self.ssh.get_transport()
            transport.set_keepalive(30)
            
            print(f"✓ SSH-Verbindung erfolgreich hergestellt zu {self.user}@{ip}")
            
            # Persistenten Channel für Shell-Zugriff öffnen
            self._open_channel()
            
        except paramiko.AuthenticationException:
            print(f"✗ SSH-Verbindung fehlgeschlagen: Authentifizierung abgelehnt")
            raise
        except Exception as e:
            print(f"✗ SSH-Verbindung fehlgeschlagen: {e}")
            raise
        
        self.write_command('echo "0" > /proc/led/led_mode', True, silent=True)
        print("✓ LED-Modus initialisiert")
        self.led_cache = []

    def _open_channel(self):
        """Öffnet einen neuen Channel"""
        try:
            self._channel = self.ssh.invoke_shell()
            self._channel.settimeout(0.5)
            time.sleep(0.1)
            self._channel.recv(4096)
        except Exception as e:
            print(f"⚠ Fehler beim Öffnen des Channels: {e}")
            self._channel = None

    def write_command(self, command, flush=False, silent=False):
        """Optimierte Befehlsausführung mit automatischem Reconnect"""
        try:
            with self._lock:
                # Channel-Check und ggf. neu öffnen
                if not self._channel or not self._channel.active:
                    if not silent:
                        print("⚠ Channel inaktiv, öffne neu...")
                    self._open_channel()
                
                if self._channel and self._channel.active:
                    self._channel.send(command + '\n')
                    
                    if flush:
                        time.sleep(0.02)
                        try:
                            self._channel.recv(2048)
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
            # Versuche Channel neu zu öffnen
            try:
                self._open_channel()
            except:
                pass
            return False

    def set_led_values(self, led, r, g, b, a=100):
        """Direktes Setzen ohne Cache - optimiert für einzelne LEDs"""
        command = f'echo "{led} {hex(r)[2:].zfill(2)} {hex(g)[2:].zfill(2)} {hex(b)[2:].zfill(2)} {a}" > /proc/led/led_code'
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
        
        chunk_size = 50
        chunks = [self.led_cache[i:i + chunk_size] for i in range(0, len(self.led_cache), chunk_size)]
        
        all_commands = []
        for chunk in chunks:
            command = "\\n".join(chunk)
            all_commands.append(f'printf "{command}" > /proc/led/led_code')
        
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
        if not led_colors:
            return True
            
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
            try:
                self._channel.close()
            except:
                pass
        if self.ssh:
            try:
                self.ssh.close()
                print(f"✓ SSH-Verbindung zu {self.user}@{self.ip} geschlossen")
            except:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()