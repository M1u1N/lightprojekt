#Example for main.py

import sys
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QVBoxLayout,
    QLabel
)
from etherlight import Etherlight
anything=str(Etherlight)
from music import music_play

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
        self.setFixedSize(300, 200)

        # Buttons
        btn1 = QPushButton("Öffne Fenster A")
        btn2 = QPushButton("Öffne Fenster B")

        # Events
        btn1.clicked.connect(self.open_window_a)
        btn2.clicked.connect(self.open_window_b)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(btn1)
        layout.addWidget(btn2)
        self.setLayout(layout)

        # Referenzen speichern (sonst werden Child-Windows geschlossen)
        self.window_a = None
        self.window_b = None

    def open_window_a(self):
        music_play(True)

    def open_window_b(self):
        self.window_b = ChildWindow("Fenster B")
        self.window_b.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
