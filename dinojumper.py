from etherlightwin import Etherlight
import time
import keyboard
import random
from threading import Thread, Lock

# Switch Konfiguration
SWITCH_IP = "172.16.26.138"

# LED Layout - 2 Reihen mit je 24 LEDs
FIRST_ROW = [1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33,35,37,39,41,43,45,47]
SECOND_ROW = [2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48]

# Spielfeld-Konfiguration
FIELD_WIDTH = 24  # Breite des Spielfelds
FIELD_HEIGHT = 2  # Höhe (2 Reihen)

# Farben (RGB, Alpha)
COLORS = {
    'player': ((0, 255, 0), 255),      # Grüner Dino
    'obstacle': ((255, 0, 0), 255),    # Rotes Hindernis
    'off': ((0, 0, 0), 0)              # Aus
}

class DinoGame:
    def __init__(self, etherlight):
        self.etherlight = etherlight
        self.lock = Lock()
        
        # Spieler-Position
        self.player_x = 3  # Linke Seite des Spielfelds
        self.player_y = 1  # Untere Reihe (Boden)
        self.player_velocity = 0
        self.is_jumping = False
        
        # Physik
        self.gravity = 0.15
        self.jump_strength = -0.8
        
        # Hindernisse [(x, y), ...]
        self.obstacles = []
        self.obstacle_speed = 0.3
        self.spawn_timer = 0
        self.spawn_interval = random.uniform(2.0, 4.0)
        
        # Spiel-Status
        self.running = True
        self.score = 0
        self.game_over = False
        
        # Alle LEDs
        self.all_leds = FIRST_ROW + SECOND_ROW
        
    def get_led(self, x, y):
        """Konvertiert Spielfeld-Koordinaten zu LED-Nummer"""
        if x < 0 or x >= FIELD_WIDTH or y < 0 or y >= FIELD_HEIGHT:
            return None
        
        if y == 0:  # Obere Reihe
            return FIRST_ROW[x] if x < len(FIRST_ROW) else None
        else:  # Untere Reihe
            return SECOND_ROW[x] if x < len(SECOND_ROW) else None
    
    def handle_input(self):
        """Verarbeitet Tastatur-Eingaben"""
        try:
            if keyboard.is_pressed('up') or keyboard.is_pressed('space'):
                if not self.is_jumping and self.player_y == 1:
                    self.is_jumping = True
                    self.player_velocity = self.jump_strength
            
            if keyboard.is_pressed('esc'):
                self.running = False
                
        except:
            pass
    
    def update_physics(self, dt):
        """Aktualisiert Spieler-Physik"""
        with self.lock:
            # Schwerkraft anwenden
            self.player_velocity += self.gravity * dt * 60
            self.player_y += self.player_velocity * dt * 60
            
            # Boden-Kollision
            if self.player_y >= 1:
                self.player_y = 1
                self.player_velocity = 0
                self.is_jumping = False
            
            # Decken-Kollision
            if self.player_y < 0:
                self.player_y = 0
                self.player_velocity = 0
    
    def update_obstacles(self, dt):
        """Bewegt Hindernisse und spawnt neue"""
        with self.lock:
            # Bewege existierende Hindernisse
            new_obstacles = []
            for obs_x, obs_y in self.obstacles:
                obs_x -= self.obstacle_speed * dt * 60
                if obs_x > -2:  # Behalte nur sichtbare Hindernisse
                    new_obstacles.append((obs_x, obs_y))
            self.obstacles = new_obstacles
            
            # Spawn neues Hindernis
            self.spawn_timer += dt
            if self.spawn_timer >= self.spawn_interval:
                self.spawn_timer = 0
                self.spawn_interval = random.uniform(1.5, 3.5)
                # Hindernis am rechten Rand spawnen
                self.obstacles.append((FIELD_WIDTH - 1, 1))
            
            # Score erhöhen
            self.score += dt * 10
    
    def check_collision(self):
        """Prüft Kollisionen zwischen Spieler und Hindernissen"""
        with self.lock:
            player_y_int = int(round(self.player_y))
            
            for obs_x, obs_y in self.obstacles:
                obs_x_int = int(round(obs_x))
                
                # Kollision prüfen (mit kleiner Toleranz)
                if abs(self.player_x - obs_x_int) <= 1 and player_y_int == obs_y:
                    self.game_over = True
                    return True
        return False
    
    def render(self):
        """Zeichnet das Spielfeld"""
        with self.lock:
            led_updates = []
            
            # Alle LEDs erstmal aus
            for led in self.all_leds:
                led_updates.append((led, COLORS['off'][0], COLORS['off'][1]))
            
            # Spieler zeichnen
            player_y_int = int(round(self.player_y))
            player_led = self.get_led(self.player_x, player_y_int)
            if player_led:
                led_updates.append((player_led, COLORS['player'][0], COLORS['player'][1]))
            
            # Hindernisse zeichnen
            for obs_x, obs_y in self.obstacles:
                obs_x_int = int(round(obs_x))
                if 0 <= obs_x_int < FIELD_WIDTH:
                    obs_led = self.get_led(obs_x_int, obs_y)
                    if obs_led:
                        led_updates.append((obs_led, COLORS['obstacle'][0], COLORS['obstacle'][1]))
            
            # An Switch senden
            try:
                self.etherlight.batch_set_leds(led_updates)
            except Exception as e:
                print(f"Render-Fehler: {e}")
    
    def game_over_animation(self):
        """Zeigt Game Over Animation"""
        print(f"\n🦖 GAME OVER! 🦖")
        print(f"📊 Score: {int(self.score)}")
        
        # Blinke alle LEDs rot
        for _ in range(3):
            led_updates = [(led, COLORS['obstacle'][0], COLORS['obstacle'][1]) for led in self.all_leds]
            self.etherlight.batch_set_leds(led_updates)
            time.sleep(0.3)
            
            led_updates = [(led, COLORS['off'][0], COLORS['off'][1]) for led in self.all_leds]
            self.etherlight.batch_set_leds(led_updates)
            time.sleep(0.3)
    
    def run(self):
        """Haupt-Spiel-Loop"""
        print("🦖 DINO JUMPER")
        print("━" * 40)
        print("🎮 Steuerung:")
        print("   ↑ / SPACE - Springen")
        print("   ESC - Beenden")
        print("━" * 40)
        print("Spiel startet in 3 Sekunden...\n")
        
        time.sleep(3)
        
        last_time = time.time()
        frame_count = 0
        fps_timer = 0
        
        try:
            while self.running and not self.game_over:
                current_time = time.time()
                dt = current_time - last_time
                last_time = current_time
                
                # FPS-Begrenzung
                if dt < 0.016:  # ~60 FPS
                    time.sleep(0.016 - dt)
                    continue
                
                # Eingabe verarbeiten
                self.handle_input()
                
                # Spiel-Logik aktualisieren
                self.update_physics(dt)
                self.update_obstacles(dt)
                
                # Kollision prüfen
                self.check_collision()
                
                # Rendern
                self.render()
                
                # FPS-Counter
                frame_count += 1
                fps_timer += dt
                if fps_timer >= 1.0:
                    print(f"📊 Score: {int(self.score):5d} | FPS: {frame_count:3d}", end='\r')
                    frame_count = 0
                    fps_timer = 0
        
        except KeyboardInterrupt:
            print("\n\n⏸ Spiel beendet")
        
        finally:
            if self.game_over:
                self.game_over_animation()
            
            # Alle LEDs ausschalten
            print("\nSchalte LEDs aus...")
            off_updates = [(led, COLORS['off'][0], COLORS['off'][1]) for led in self.all_leds]
            self.etherlight.batch_set_leds(off_updates)

def main():
    print("Verbinde mit Switch...")
    
    try:
        with Etherlight(SWITCH_IP, "nwlab") as etherlight:
            # Initialisiere alle LEDs
            all_leds = FIRST_ROW + SECOND_ROW
            init_updates = [(led, COLORS['off'][0], COLORS['off'][1]) for led in all_leds]
            etherlight.batch_set_leds(init_updates)
            
            # Starte Spiel
            game = DinoGame(etherlight)
            game.run()
            
    except Exception as e:
        print(f"❌ Fehler: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()