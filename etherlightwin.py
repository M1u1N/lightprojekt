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
        try:
            self.ssh.connect(
                hostname=ip,
                username=self.user,
                password=password,
                key_filename=key_filename,
                look_for_keys=True if not password else False,
                allow_agent=True if not password else False
            )
        except Exception as e:
            print(f"SSH-Verbindung fehlgeschlagen: {e}")
            raise
        
        self.write_command('echo "0" > /proc/led/led_mode', True)
        self.led_cache = []

    def write_command(self, command, flush=False):
        try:
            stdin, stdout, stderr = self.ssh.exec_command(command)
            if flush:
                stdout.channel.recv_exit_status()  # Warten bis Befehl abgeschlossen
        except Exception as e:
            print(f"Fehler beim Ausführen des Befehls: {e}")

    def flush(self):
        pass  # Bei paramiko nicht notwendig

    def set_led_values(self, led, r, g, b, a=100):
        command = f'echo "{led} r {r*100}" > /proc/led/led_color; '
        command += f'echo "{led} g {g*100}" > /proc/led/led_color; '
        command += f'echo "{led} b {b*100}" > /proc/led/led_color'
        self.write_command(command)

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

        for chunk in chunks(self.led_cache, 15):
            command = "\\n".join(chunk)
            self.write_command(f'printf "{command}" > /proc/led/led_code', True)

        self.led_cache = []

    def close(self):
        """SSH-Verbindung schließen"""
        if self.ssh:
            self.ssh.close()

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