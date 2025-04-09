from PyQt5.QtWidgets import QApplication, QMainWindow
from gui.video_player import VideoPlayer
import sys

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.player = VideoPlayer()
        self.setCentralWidget(self.player)
        self.setWindowTitle("Intelligent Subtitle - Speech to Text with Whisper")
        self.resize(900, 700)
    
    def closeEvent(self, event):
        # Ensure the video player's close event gets called for proper thread cleanup
        self.player.closeEvent(event)

def launch_app():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())