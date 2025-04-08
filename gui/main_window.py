from PyQt5.QtWidgets import QApplication, QMainWindow
from gui.video_player import VideoPlayer
import sys

def launch_app():
    app = QApplication(sys.argv)
    window = QMainWindow()
    player = VideoPlayer()
    window.setCentralWidget(player)
    window.setWindowTitle("Realtime Subtitle App")
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())