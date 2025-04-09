from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QMessageBox, QApplication, QSlider, QStyle, QProgressBar
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl, QTimer, Qt, QThread, pyqtSignal
import os
import tempfile
import ffmpeg
import json
from core.transcriber import transcribe
from core.worker import TranscriptionWorker

class VideoPlayer(QWidget):
    # Signal to start processing in the worker thread
    process_video_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()

        # Create video widget
        self.video_widget = QVideoWidget()
        
        # Create subtitle label
        self.subtitle_label = QLabel("Subtitle will appear here...")
        self.subtitle_label.setStyleSheet("background-color: rgba(0, 0, 0, 100); color: white; padding: 10px; font-size: 14px;")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        
        # Create progress bar for transcription
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.setVisible(False)
        
        # Create controls
        self.controls_layout = QHBoxLayout()
        
        # Open button
        self.open_btn = QPushButton("Open Video")
        self.open_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        
        # Play/Pause button
        self.play_pause_btn = QPushButton()
        self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        
        # Position slider
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_position)
        
        # Duration label
        self.duration_label = QLabel("00:00 / 00:00")
        
        # Add save subtitle button
        self.save_subtitle_btn = QPushButton("Save Subtitles")
        self.save_subtitle_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.save_subtitle_btn.clicked.connect(self.save_subtitles)
        self.save_subtitle_btn.setEnabled(False)  # Disable until we have subtitles
        
        # Add controls to layout
        self.controls_layout.addWidget(self.open_btn)
        self.controls_layout.addWidget(self.play_pause_btn)
        self.controls_layout.addWidget(self.position_slider)
        self.controls_layout.addWidget(self.duration_label)
        self.controls_layout.addWidget(self.save_subtitle_btn)
        
        # Add widgets to main layout
        self.layout.addWidget(self.video_widget)
        self.layout.addWidget(self.subtitle_label)
        self.layout.addWidget(self.progress_bar)
        self.layout.addLayout(self.controls_layout)

        self.setLayout(self.layout)

        # Set up media player
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.setVideoOutput(self.video_widget)
        
        # Connect signals
        self.media_player.error.connect(self.handle_error)
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.media_player.stateChanged.connect(self.state_changed)
        
        # For handling subtitles
        self.segments = []
        self.current_segment_index = 0
        self.temp_dir = tempfile.mkdtemp()
        self.video_path = ""
        
        # Set up worker thread for transcription
        self.setup_worker_thread()

        self.open_btn.clicked.connect(self.open_video_dialog)
    
    def setup_worker_thread(self):
        # Create worker and thread
        self.worker_thread = QThread()
        self.transcription_worker = TranscriptionWorker()
        self.transcription_worker.moveToThread(self.worker_thread)
        
        # Connect worker signals
        self.transcription_worker.transcription_progress.connect(self.on_transcription_progress)
        self.transcription_worker.transcription_complete.connect(self.on_transcription_complete)
        self.transcription_worker.transcription_error.connect(self.on_transcription_error)
        
        # Connect the process trigger
        self.process_video_signal.connect(self.transcription_worker.process_video)
        
        # Start the thread
        self.worker_thread.start()

    def open_video_dialog(self):
        file_dialog = QFileDialog()
        video_path, _ = file_dialog.getOpenFileName(self, "Open Video", "", "Video Files (*.mp4 *.avi *.mkv *.mov)")
        
        if video_path:
            self.load_video(video_path)
    
    def load_video(self, video_path=None):
        # If no video path is provided, use the default demo video
        if video_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            video_path = os.path.join(base_dir, "sample_videos", "demo.mp4")
        
        self.video_path = video_path
        
        if not os.path.exists(video_path):
            QMessageBox.critical(self, "Error", f"Video file not found: {video_path}")
            return
        
        # Start the video playback
        url = QUrl.fromLocalFile(video_path)
        self.media_player.setMedia(QMediaContent(url))
        self.media_player.play()
        
        # Show progress bar and start transcription in background
        self.progress_bar.setVisible(True)
        self.subtitle_label.setText("Starting transcription...")
        
        # Start transcription in background thread
        QApplication.processEvents()  # Force UI update
        self.process_video_signal.emit(video_path)
    
    def on_transcription_progress(self, message):
        self.subtitle_label.setText(message)
        QApplication.processEvents()  # Force UI update
    
    def on_transcription_complete(self, segments):
        self.segments = segments
        self.current_segment_index = 0
        self.save_subtitle_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.subtitle_label.setText("Transcription complete! Subtitles will appear as the video plays.")
    
    def on_transcription_error(self, error_message):
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Transcription Error", f"Failed to transcribe audio: {error_message}")
        self.subtitle_label.setText("Error in transcription. No subtitles available.")
    
    def toggle_play_pause(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()
    
    def state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
    
    def position_changed(self, position):
        # Update the slider position
        self.position_slider.setValue(position)
        
        # Update the duration label
        self.update_duration_label(position, self.media_player.duration())
        
        # Convert position from milliseconds to seconds
        current_time = position / 1000.0
        
        # Find the current segment that matches the playback position
        for i, segment in enumerate(self.segments):
            if segment['start'] <= current_time and segment['end'] >= current_time:
                if i != self.current_segment_index:  # Only update if segment changed
                    self.current_segment_index = i
                    self.subtitle_label.setText(segment['text'])
                return
        
        # If no matching segment, clear the subtitle label
        if self.segments and current_time > 0:
            self.subtitle_label.setText("")
    
    def duration_changed(self, duration):
        self.position_slider.setRange(0, duration)
        self.update_duration_label(self.media_player.position(), duration)
    
    def set_position(self, position):
        self.media_player.setPosition(position)
    
    def update_duration_label(self, position, duration):
        position_sec = position // 1000
        duration_sec = duration // 1000
        position_min, position_sec = divmod(position_sec, 60)
        duration_min, duration_sec = divmod(duration_sec, 60)
        self.duration_label.setText(f"{position_min:02d}:{position_sec:02d} / {duration_min:02d}:{duration_sec:02d}")
        
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

    def save_subtitles(self):
        if not self.segments:
            QMessageBox.warning(self, "No Subtitles", "No subtitles available to save.")
            return
            
        # Get the video filename without extension
        video_filename = os.path.basename(self.video_path)
        video_name = os.path.splitext(video_filename)[0]
        
        # Ask user where to save the subtitles
        options = QFileDialog.Options()
        save_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Subtitles",
            f"{video_name}_subtitles.srt",
            "SubRip Subtitles (*.srt);;WebVTT (*.vtt);;JSON (*.json);;All Files (*)",
            options=options
        )
        
        if not save_path:
            return
            
        # Determine the format based on the file extension
        _, ext = os.path.splitext(save_path)
        ext = ext.lower()
        
        try:
            if ext == '.srt':
                self.save_as_srt(save_path)
            elif ext == '.vtt':
                self.save_as_vtt(save_path)
            elif ext == '.json':
                self.save_as_json(save_path)
            else:
                # Default to SRT format
                self.save_as_srt(save_path)
                
            QMessageBox.information(self, "Success", f"Subtitles saved to {save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save subtitles: {str(e)}")
    
    def save_as_srt(self, filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(self.segments):
                # SRT format: index, time range, text
                start_time = self.format_time_srt(segment['start'])
                end_time = self.format_time_srt(segment['end'])
                
                f.write(f"{i+1}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{segment['text']}\n\n")
    
    def save_as_vtt(self, filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            # WebVTT header
            f.write("WEBVTT\n\n")
            
            for i, segment in enumerate(self.segments):
                # WebVTT format: optional cue identifier, time range, text
                start_time = self.format_time_vtt(segment['start'])
                end_time = self.format_time_vtt(segment['end'])
                
                f.write(f"cue-{i+1}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{segment['text']}\n\n")
    
    def save_as_json(self, filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.segments, f, indent=2, ensure_ascii=False)
    
    def format_time_srt(self, seconds):
        """Format time in SRT format: HH:MM:SS,mmm"""
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = int((seconds - int(seconds)) * 1000)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d},{milliseconds:03d}"
    
    def format_time_vtt(self, seconds):
        """Format time in WebVTT format: HH:MM:SS.mmm"""
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        milliseconds = int((seconds - int(seconds)) * 1000)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}.{milliseconds:03d}"
        
    def closeEvent(self, event):
        # Properly clean up to avoid thread issues
        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(1000)  # Wait up to 1 second
        event.accept()