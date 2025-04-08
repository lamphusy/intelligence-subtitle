from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl

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

        self.open_btn.clicked.connect(self.load_video)

    def load_video(self):
        url = QUrl.fromLocalFile("sample_videos/demo.mp4")
        self.media_player.setMedia(QMediaContent(url))
        self.media_player.play()