from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog, QMessageBox
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl
import os

class VideoPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()

        self.video_widget = QVideoWidget()
        self.open_btn = QPushButton("Open Video")
        self.subtitle_label = QLabel("Subtitle will appear here...")

        self.layout.addWidget(self.video_widget)
        self.layout.addWidget(self.subtitle_label)
        self.layout.addWidget(self.open_btn)

        self.setLayout(self.layout)

        self.media_player = QMediaPlayer()
        self.media_player.setVideoOutput(self.video_widget)
        
        # Connect error signal
        self.media_player.error.connect(self.handle_error)

        self.open_btn.clicked.connect(self.load_video)

    def load_video(self):
        # Use absolute path to ensure correct resolution
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        video_path = os.path.join(base_dir, "sample_videos", "demo.mp4")
        
        if not os.path.exists(video_path):
            QMessageBox.critical(self, "Error", f"Video file not found: {video_path}")
            return
            
        url = QUrl.fromLocalFile(video_path)
        self.media_player.setMedia(QMediaContent(url))
        self.media_player.play()
        
    def handle_error(self, error):
        error_messages = {
            QMediaPlayer.NoError: "No error",
            QMediaPlayer.ResourceError: "Resource error - file not found or not supported",
            QMediaPlayer.FormatError: "Format error - unsupported format",
            QMediaPlayer.NetworkError: "Network error",
            QMediaPlayer.AccessDeniedError: "Access denied error",
        }
        
        error_message = error_messages.get(error, f"Unknown error: {error}")
        QMessageBox.critical(self, "Media Player Error", error_message)