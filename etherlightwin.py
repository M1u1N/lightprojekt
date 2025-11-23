import paramiko
import time

# ===./led_code
# * Set port[1-52] LED with color code r[0-ff] g[0-ff] b[0-ff] and power level[1-100]
# * Ex. "1 ff cc ff 100" to light port 1 with color code #ffccff and power level 100
# ===./led_mode
# 1
# ===./led_color
# * Set port[1-52] LED with color[r=Red g=Green b=Blue w=White] and follow with value[0-65535]
# * Ex. "1 r 65535" to light port 1 red LED
# ===./led_config
# * Config LED: [0=Cold reset 1=Warm reset 2=Boot done]
# ===./led_version
# 1.0.1
# ===./led_board_id
# 1
# ===./led_test_cmd
# * LED test:
# 	set_port  [port# rH rL gH gL bH bL wH wL]
# 	all_port  [r|g|b|w|off|normal]
# 	marquee   [1-65535]
# 	byte      [1-65535]
# 	solid     [1-65535]
# 	time_calc [1-65535]
# ===./led_all_port_code
# * Set all ports' LED color code for r/g/b [00-FF] with power level [0-100]
# * Ex. "FF 00 FF 100" to set all ports to color code r=FF g=00 b=FF with power level 100
# ===./led_all_port_color
# * Set all ports' LED r/g/b/w color [0-65535]
# * Ex. "65535 32768 16384 0" to set all ports to r=65535 g=32768 b=16384 w=0

class Etherlight:
    def __init__(self, ip, user: str = None, password: str = None, key_filename: str = None):
        self.ip = ip
        self.user = user if user else "root"
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Verbindung herstellen
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
        except paramiko.AuthenticationException:
            print(f"✗ SSH-Verbindung fehlgeschlagen: Authentifizierung abgelehnt")
            raise
        except paramiko.SSHException as e:
            print(f"✗ SSH-Verbindung fehlgeschlagen: SSH-Fehler - {e}")
            raise
        except TimeoutError:
            print(f"✗ SSH-Verbindung fehlgeschlagen: Timeout bei Verbindung zu {ip}")
            raise
        except Exception as e:
            print(f"✗ SSH-Verbindung fehlgeschlagen: {e}")
            raise
        
        self.write_command('echo "0" > /proc/led/led_mode', True, silent=True)
        print("✓ LED-Modus initialisiert")
        self.led_cache = []

    def write_command(self, command, flush=False, silent=False):
        try:
            stdin, stdout, stderr = self.ssh.exec_command(command)
            if flush:
                exit_status = stdout.channel.recv_exit_status()
                error_output = stderr.read().decode('utf-8').strip()
                
                if not silent:
                    if exit_status == 0:
                        print(f"✓ Befehl erfolgreich ausgeführt")
                    else:
                        print(f"✗ Befehl fehlgeschlagen (Exit-Code: {exit_status})")
                        if error_output:
                            print(f"  Fehler: {error_output}")
                
                return exit_status == 0
        except Exception as e:
            if not silent:
                print(f"✗ Fehler beim Ausführen des Befehls: {e}")
            return False

    def flush(self):
        pass  # Bei paramiko nicht notwendig

    def set_led_values(self, led, r, g, b, a=100):
        print(f"Setze LED {led} auf RGB({r}, {g}, {b}) mit Alpha={a}...")
        command = f'echo "{led} r {r*100}" > /proc/led/led_color; '
        command += f'echo "{led} g {g*100}" > /proc/led/led_color; '
        command += f'echo "{led} b {b*100}" > /proc/led/led_color'
        success = self.write_command(command, flush=True, silent=True)
        if success:
            print(f"✓ LED {led} erfolgreich gesetzt")
        else:
            print(f"✗ LED {led} konnte nicht gesetzt werden")
        return success

    def set_led_color(self, led, color, a=100):
        r, g, b = color
        self.set_led_values(led, r, g, b, a)

    def cache_led_color(self, led, color, a=100):
        self.led_cache.append(f'{led} {hex(color[0])[2:]} {hex(color[1])[2:]} {hex(color[2])[2:]} {a}')

    def flush_led_cache(self):
        def chunks(lst, n):
            """Yield successive n-sized chunks from lst."""
            for i in range(0, len(lst), n):
                yield lst[i:i + n]

        print(f"Schreibe {len(self.led_cache)} zwischengespeicherte LED-Befehle...")
        success_count = 0
        chunk_count = 0
        
        for chunk in chunks(self.led_cache, 15):
            chunk_count += 1
            command = "\\n".join(chunk)
            success = self.write_command(f'printf "{command}" > /proc/led/led_code', True, silent=True)
            if success:
                success_count += 1

        if success_count == chunk_count:
            print(f"✓ Alle LED-Cache-Befehle erfolgreich geschrieben ({chunk_count} Chunks)")
        else:
            print(f"⚠ {success_count}/{chunk_count} Chunks erfolgreich geschrieben")
        
        self.led_cache = []

    def close(self):
        """SSH-Verbindung schließen"""
        if self.ssh:
            self.ssh.close()
            print(f"✓ SSH-Verbindung zu {self.user}@{self.ip} geschlossen")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Beispiel für die Verwendung:
if __name__ == "__main__":
    # Mit Passwort:
    # etherlight = Etherlight("192.168.1.100", user="admin", password="password")
    
    # Mit SSH-Key:
    # etherlight = Etherlight("192.168.1.100", user="admin", key_filename="C:\\Users\\YourUser\\.ssh\\id_rsa")
    
    # Mit Context Manager (empfohlen):
    # with Etherlight("192.168.1.100", user="admin", password="password") as etherlight:
    #     etherlight.set_led_color(1, (255, 0, 255), 100)
    
    pass