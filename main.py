import sys
import subprocess
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QVBoxLayout,
    QLabel,
    QMessageBox
)


class ChildWindow(QWidget):
    def __init__(self, title: str):
        super().__init__()
        self.setWindowTitle(title)
        self.setFixedSize(250, 120)
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f"Dies ist das Fenster: {title}"))
        self.setLayout(layout)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Hauptfenster")
        self.setFixedSize(350, 240)

        # Liste für alle gestarteten Subprozesse
        self.processes: list[subprocess.Popen] = []

        # Buttons
        btn1 = QPushButton("Öffne dance 2")
        btn2 = QPushButton("Öffne double Music")
        btn3 = QPushButton("Öffne knight Rider 3.1")
        btn4 = QPushButton("Öffne dancflooor")
        btn_stop_all = QPushButton("Stoppe alle Subprozesse")

        # Events
        btn1.clicked.connect(self.open_window_a)
        btn2.clicked.connect(self.open_window_b)
        btn3.clicked.connect(self.start_knightrider)
        btn4.clicked.connect(self.start_testrider)
        btn_stop_all.clicked.connect(self.stop_all_processes)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(btn1)
        layout.addWidget(btn2)
        layout.addWidget(btn3)
        layout.addWidget(btn4)
        layout.addWidget(btn_stop_all)

        self.setLayout(layout)

        # Falls du Child-Windows referenzieren willst (hier nicht verwendet)
        self.window_a = None
        self.window_b = None

    # Beispiel: originalfunktionen bleiben unverändert (hier nur Platzhalter-Aufrufe)
    def open_window_a(self):
        # Falls music_play ein externes Script starten soll, benutze start_process()
        # hier nur ein Beispiel: subprocess starten
        self.start_process([sys.executable, "dance_floor.py"], "dance_floor.py")

    def open_window_b(self):
        self.start_process([sys.executable, "doubleMusic.py"], "doubleMusic.py")

    # Startet knightrider.py und speichert den Prozess
    def start_knightrider(self):
        self.start_process([sys.executable, "knightrider3.1.py"], "knightrider.3.1.py")

    # Startet testrider.py und speichert den Prozess
    def start_testrider(self):
        self.start_process([sys.executable, "dancflooor.py"], "dancflooor.py")

    # Hilfsfunktion: Prozess starten und referenz speichern
    def start_process(self, cmd: list[str], name: str = ""):
        # vorher beendete Prozesse aus der Liste entfernen
        self.prune_finished_processes()

        try:
            p = subprocess.Popen(cmd)
            p._friendly_name = name or " ".join(cmd)  # optionaler Name zu Debugzwecken
            self.processes.append(p)
            print(f"Starte Prozess: {p._friendly_name} (PID={p.pid})")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Konnte Prozess nicht starten:\n{e}")

    # Entfernt beendete Prozesse aus self.processes
    def prune_finished_processes(self):
        running = []
        for p in self.processes:
            if p.poll() is None:  # None => läuft noch
                running.append(p)
            else:
                print(f"Prozess beendet (PID={getattr(p, 'pid', 'unknown')}) -> wird entfernt")
        self.processes = running

    # Beendet alle laufenden Subprozesse (terminate -> wait -> kill falls nötig)
    def stop_all_processes(self):
        self.prune_finished_processes()
        if not self.processes:
            QMessageBox.information(self, "Info", "Es laufen keine Subprozesse.")
            return

        for p in list(self.processes):  # copy, da wir in loop ggf. modifizieren
            try:
                if p.poll() is None:
                    print(f"Sende terminate() an PID={p.pid} ({getattr(p, '_friendly_name', '')})")
                    p.terminate()
                    try:
                        p.wait(timeout=3)  # kurz warten, ob er vernünftig endet
                        print(f"Prozess PID={p.pid} wurde beendet.")
                    except subprocess.TimeoutExpired:
                        print(f"PID={p.pid} reagiert nicht auf terminate(), sende kill()")
                        p.kill()
                        p.wait(timeout=3)
                        print(f"PID={p.pid} wurde gekillt.")
                else:
                    print(f"PID={p.pid} war bereits beendet.")
            except Exception as e:
                print(f"Fehler beim Beenden von PID={getattr(p, 'pid', 'unknown')}: {e}")
            finally:
                # egal was passiert, entfernen wir ihn aus der Liste
                if p in self.processes:
                    self.processes.remove(p)

        QMessageBox.information(self, "Fertig", "Alle Subprozesse wurden gestoppt (oder versucht zu stoppen).")

    # Beim Schließen der App ebenfalls alle Subprozesse beenden
    def closeEvent(self, event):
        if self.processes:
            # Hinweis an den Nutzer
            reply = QMessageBox.question(
                self,
                "Beenden",
                "Es laufen noch Subprozesse. Beim Beenden werden diese gestoppt. Fortfahren?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_all_processes()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
