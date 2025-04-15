import sys
import os
import tempfile
import json
import shutil
import time
import vlc

# --- PyQt5 Imports ---
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QFileDialog, QMessageBox, QApplication, QSlider, QStyle,
                             QProgressBar)
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal, QRect, QUrl
from PyQt5.QtGui import QFont, QFontMetrics

# --- Giả lập core nếu không tìm thấy ---
try:
    from core.transcriber import transcribe
    from core.worker import TranscriptionWorker
    print("INFO: Using actual 'core' module.")
except ImportError as e:
    print(f"WARNING: Error importing core modules: {e}")
    print("INFO: Using dummy transcription classes.")

    class TranscriptionWorker(QThread):
        transcription_progress = pyqtSignal(str)
        transcription_complete = pyqtSignal(list)
        transcription_error = pyqtSignal(str)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._is_processing = False

        def process_video(self, path):
            if self._is_processing:
                print("Dummy Worker: Already processing.")
                return
            self._is_processing = True
            print(f"Dummy Worker: Processing '{os.path.basename(path)}'")
            try:
                self.transcription_progress.emit("Transcription starting (dummy)...")
                time.sleep(2) # Giả lập thời gian xử lý
                dummy_segments = [
                    {'start': 1.5, 'end': 4.0, 'text': 'Đây là phụ đề thử nghiệm đầu tiên.'},
                    {'start': 5.1, 'end': 8.8, 'text': '(Âm nhạc)'},
                    {'start': 10.0, 'end': 15.5, 'text': 'Phụ đề này dài hơn một chút để chúng ta có thể kiểm tra xem việc ngắt dòng có hoạt động chính xác không.'},
                    {'start': 17.0, 'end': 19.2, 'text': 'Một câu ngắn.'},
                    {'start': 61.0, 'end': 65.0, 'text': 'Phụ đề gần cuối (giả lập).'}
                ]
                print("Dummy Worker: Emitting dummy segments.")
                self.transcription_complete.emit(dummy_segments)
            except Exception as ex:
                 print(f"Dummy Worker Error: {ex}")
                 self.transcription_error.emit(f"Dummy error: {ex}")
            finally:
                 self._is_processing = False

    def transcribe(audio_path, temp_dir):
        print(f"Dummy transcribe called: Path={audio_path}, Temp={temp_dir}")
        return []

class VideoPlayer(QWidget):
    process_video_signal = pyqtSignal(str)
    SUBTITLE_LR_MARGIN = 20
    SUBTITLE_BOTTOM_MARGIN = 20
    SUBTITLE_FONT_SIZE = 18
    SUBTITLE_TIMER_INTERVAL = 50 # ms

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Intelligent Subtitle - Speech to Text with Whisper")
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        # Create VLC instance with macOS specific options if needed
        vlc_options = []
        if sys.platform == "darwin":
            # Explicitly set the video output module for macOS
            # This can help resolve rendering issues like "Failed to create video converter"
            vlc_options.append("--vout=macosx") 
            
        self.instance = vlc.Instance(vlc_options)
        self.mediaplayer = self.instance.media_player_new()
        
        # Create video widget
        self.video_widget = QWidget(self)
        self.video_widget.setMinimumSize(640, 360)
        self.video_widget.setStyleSheet("background-color: black;")
        
        # IMPORTANT: Don't set the video output here for macOS yet
        # We'll do it in showEvent after the widget is visible
        if sys.platform.startswith('linux'): 
            self.mediaplayer.set_xwindow(self.video_widget.winId())
        elif sys.platform == "win32": 
            self.mediaplayer.set_hwnd(self.video_widget.winId())
        # elif sys.platform == "darwin": 
        #     # We will set nsobject in showEvent for macOS
        #     pass 
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(15)

        self.controls_layout = QHBoxLayout()
        self.open_btn = QPushButton("Open Video")
        self.open_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.play_pause_btn = QPushButton()
        self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.play_pause_btn.setEnabled(False)
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_position)
        self.duration_label = QLabel("00:00 / 00:00")
        self.duration_label.setFixedWidth(100)
        self.save_subtitle_btn = QPushButton("Save Subtitles")
        self.save_subtitle_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.save_subtitle_btn.clicked.connect(self.save_subtitles)
        self.save_subtitle_btn.setEnabled(False)

        self.controls_layout.addWidget(self.open_btn)
        self.controls_layout.addWidget(self.play_pause_btn)
        self.controls_layout.addWidget(self.position_slider, 1)
        self.controls_layout.addWidget(self.duration_label)
        self.controls_layout.addWidget(self.save_subtitle_btn)

        self.layout.addWidget(self.video_widget, 1)
        self.layout.addWidget(self.progress_bar)
        self.layout.addLayout(self.controls_layout)
        self.setLayout(self.layout)

        self.segments = []
        self.current_segment_index = -1
        self.next_segment_index = 0
        self.temp_dir = tempfile.mkdtemp(prefix="subtitle_app_")
        print(f"INFO: Temp directory created: {self.temp_dir}")
        self.video_path = ""
        self.subtitle_path = ""
        
        # Timer for updating the UI
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.update_ui)

        self.setup_worker_thread()
        self.open_btn.clicked.connect(self.open_video_dialog)

    def setup_worker_thread(self):
        """Khởi tạo và cấu hình luồng worker."""
        self.worker_thread = QThread(self)
        self.transcription_worker = TranscriptionWorker()
        self.transcription_worker.moveToThread(self.worker_thread)
        self.transcription_worker.transcription_progress.connect(self.on_transcription_progress)
        self.transcription_worker.transcription_complete.connect(self.on_transcription_complete)
        self.transcription_worker.transcription_error.connect(self.on_transcription_error)
        self.process_video_signal.connect(self.transcription_worker.process_video)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()
        print("INFO: Worker thread started.")

    def open_video_dialog(self):
        """Mở hộp thoại chọn tệp video."""
        file_dialog = QFileDialog(self)
        video_path, _ = file_dialog.getOpenFileName(self, "Open Video", "",
                                                    "Video Files (*.mp4 *.avi *.mkv *.mov *.wmv);;All Files (*)")
        if video_path:
            self.load_video(video_path)

    def showEvent(self, event):
        """Called when the widget is shown. Set VLC output for macOS here."""
        super().showEvent(event)
        if sys.platform == "darwin" and self.video_widget.winId() != 0:
            try:
                print(f"INFO: Setting nsobject for VLC: {self.video_widget.winId()}")
                self.mediaplayer.set_nsobject(int(self.video_widget.winId()))
                print("INFO: nsobject set successfully.")
            except Exception as e:
                print(f"ERROR: Failed to set nsobject for VLC: {e}")
                QMessageBox.critical(self, "VLC Error", f"Failed to initialize VLC video output:\n{str(e)}")
        # Also trigger UI update when shown
        QTimer.singleShot(100, self.update_ui) 

    def load_video(self, video_path):
        """Tải video mới, đặt lại trạng thái và bắt đầu gỡ băng."""
        self.video_path = video_path
        print(f"INFO: Loading video: {self.video_path}")
        if not os.path.exists(video_path):
            QMessageBox.critical(self, "Error", f"Video file not found:\n{video_path}")
            return

        # Stop any playing media
        self.mediaplayer.stop()
        
        # Create new media with proper path handling
        try:
            abs_path = os.path.abspath(video_path)
            if sys.platform == "win32":
                abs_path = abs_path.replace('\\', '/')
            
            # Use file URI scheme
            file_uri = QUrl.fromLocalFile(abs_path).toString()
            print(f"INFO: Attempting to load media URI: {file_uri}")
            media = self.instance.media_new(file_uri)
            if not media:
                raise Exception("Failed to create media object from URI")
            
            # Parse media to get duration information sooner
            media.parse()
            
            # Set media to player
            self.mediaplayer.set_media(media)
            
            # Reset state
            self.segments = []
            self.current_segment_index = -1
            self.next_segment_index = 0
            self.save_subtitle_btn.setEnabled(False)
            self.play_pause_btn.setEnabled(True)
            self.position_slider.setValue(0)
            self.position_slider.setEnabled(True)
            self.duration_label.setText("00:00 / 00:00")

            # Set window title to include video name
            self.setWindowTitle(f"Intelligent Subtitle - {os.path.basename(video_path)}")

            # Start transcription
            self.progress_bar.setVisible(True)
            print("INFO: Emitting process_video_signal")
            self.process_video_signal.emit(video_path)
            
            # Trigger UI update after a short delay to allow media parsing
            QTimer.singleShot(500, self.update_ui)
            
        except Exception as e:
            print(f"ERROR: Failed to load video: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load video:\n{str(e)}")
            self.play_pause_btn.setEnabled(False)
            self.position_slider.setEnabled(False)
            self.progress_bar.setVisible(False)

    def on_transcription_progress(self, message):
        """Cập nhật thông báo tiến trình gỡ băng."""
        print(f"INFO: Transcription Progress: {message}")

    def on_transcription_complete(self, segments):
        """Xử lý khi gỡ băng hoàn tất."""
        print(f"INFO: Transcription Complete. Received {len(segments)} segments.")
        self.segments = segments if segments else []
        self.current_segment_index = -1
        self.next_segment_index = 0
        self.save_subtitle_btn.setEnabled(bool(self.segments))
        self.progress_bar.setVisible(False)

        if self.segments:
            try:
                self.subtitle_path = os.path.join(self.temp_dir, "subtitles.srt")
                self.save_as_srt(self.subtitle_path)
                
                # Load subtitles into VLC using file URI
                abs_subtitle_path = os.path.abspath(self.subtitle_path)
                subtitle_uri = QUrl.fromLocalFile(abs_subtitle_path).toString()
                print(f"INFO: Setting subtitle file URI: {subtitle_uri}")
                
                # Add subtitle track
                result = self.mediaplayer.add_slave(vlc.MediaSlaveType.subtitle, subtitle_uri, True)
                if not result:
                     print("WARNING: add_slave returned False, subtitles might not load.")
                
                # Give VLC a moment to process the subtitle file
                QTimer.singleShot(200, self.check_and_enable_subtitles)

            except Exception as e:
                print(f"ERROR: Failed to load subtitles: {e}")
                QMessageBox.warning(self, "Warning", f"Subtitles were generated but could not be loaded:\n{str(e)}")

    def on_transcription_error(self, error_message):
        """Xử lý khi có lỗi trong quá trình gỡ băng."""
        print(f"ERROR: Transcription Error: {error_message}")
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Transcription Error", f"Failed to transcribe audio:\n{error_message}")

    def check_and_enable_subtitles(self):
        """Check available subtitle tracks and enable the first one."""
        try:
            spu_count = self.mediaplayer.video_get_spu_count()
            print(f"INFO: Found {spu_count} subtitle tracks.")
            
            if spu_count > 0:
                # Get description of tracks (index 0 is disable)
                spu_desc = self.mediaplayer.video_get_spu_description()
                print(f"INFO: Subtitle descriptions: {spu_desc}")
                
                # Find the index of our added subtitle (often index 1)
                # The description tuple might look like: [(0, b'Disable'), (1, b'Track 1 - [SubRip]')] 
                # or similar, depending on VLC version and OS.
                # We want the first non-disable track.
                track_id_to_enable = -1
                for track_id, track_name_bytes in spu_desc:
                    if track_id != 0: # Skip the 'Disable' track
                        track_id_to_enable = track_id
                        print(f"INFO: Found subtitle track ID {track_id} to enable.")
                        break
                
                if track_id_to_enable != -1:
                    result = self.mediaplayer.video_set_spu(track_id_to_enable)
                    if result == 0:
                        print(f"INFO: Successfully enabled subtitle track ID {track_id_to_enable}.")
                    else:
                        print(f"WARNING: Failed to enable subtitle track ID {track_id_to_enable} (Error code: {result})")
                else:
                     print("WARNING: No suitable subtitle track ID found to enable.")
            else:
                print("WARNING: No subtitle tracks available to enable.")
        except Exception as e:
            print(f"ERROR: Exception while checking/enabling subtitles: {e}")

    def toggle_play_pause(self):
        """Chuyển đổi giữa trạng thái phát và tạm dừng."""
        if not self.play_pause_btn.isEnabled():
            return
            
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        else:
            # Ensure media is loaded before playing
            if self.mediaplayer.get_media() is None:
                 QMessageBox.warning(self, "Warning", "No video loaded.")
                 return
                 
            if self.mediaplayer.play() == -1:
                QMessageBox.critical(self, "Error", "Unable to play video")
                return
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            self.timer.start()
            # Explicitly call update_ui after starting play
            QTimer.singleShot(50, self.update_ui) 

    def set_position(self, position):
        """Di chuyển vị trí phát media player."""
        self.mediaplayer.set_position(position / 1000.0)

    def update_ui(self):
        """Cập nhật giao diện người dùng."""
        # Update position slider
        position = self.mediaplayer.get_position() * 1000
        self.position_slider.setValue(int(position))

        # Update duration label
        duration = self.mediaplayer.get_length()
        if duration > 0:
            self.update_duration_label(position, duration)

        # Update play/pause button
        if not self.mediaplayer.is_playing():
            self.timer.stop()
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def update_duration_label(self, position, duration):
        """Cập nhật label hiển thị thời gian."""
        if duration <= 0:
            self.duration_label.setText("--:-- / --:--")
            return
        # Ensure calculations result in integers for formatting
        pos_sec_total = int(position // 1000)
        dur_sec_total = int(duration // 1000)
        pos_min, pos_sec = divmod(pos_sec_total, 60)
        dur_min, dur_sec = divmod(dur_sec_total, 60)
        self.duration_label.setText(f"{pos_min:02d}:{pos_sec:02d} / {dur_min:02d}:{dur_sec:02d}")

    def save_subtitles(self):
        """Mở hộp thoại và lưu phụ đề."""
        if not self.segments:
            QMessageBox.warning(self, "No Subtitles", "No subtitles to save.")
            return

        video_filename = os.path.basename(self.video_path) if self.video_path else "video"
        video_name = os.path.splitext(video_filename)[0]
        default_dir = os.path.dirname(self.video_path) if self.video_path else ""
        default_filename = os.path.join(default_dir, f"{video_name}.srt")

        options = QFileDialog.Options()
        save_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Save Subtitles As...", default_filename,
            "SubRip Subtitles (*.srt);;WebVTT (*.vtt);;JSON (*.json);;All Files (*)",
            options=options)

        if not save_path:
            return

        print(f"INFO: Saving subtitles to: {save_path}")
        _, ext = os.path.splitext(save_path)
        ext = ext.lower()

        try:
            if ext == '.srt' or "(*.srt)" in selected_filter:
                self.save_as_srt(save_path)
            elif ext == '.vtt' or "(*.vtt)" in selected_filter:
                self.save_as_vtt(save_path)
            elif ext == '.json' or "(*.json)" in selected_filter:
                self.save_as_json(save_path)
            else:
                if not ext:
                    save_path += ".srt"
                self.save_as_srt(save_path)
                QMessageBox.information(self, "Format Note", f"Saved as SRT format (default).")
            QMessageBox.information(self, "Success", f"Subtitles saved to:\n{save_path}")
        except Exception as e:
            print(f"ERROR: Failed to save subtitles: {e}")
            QMessageBox.critical(self, "Error Saving File", f"Failed to save subtitles:\n{str(e)}")

    def save_as_srt(self, filepath):
        """Lưu segments thành tệp SRT."""
        with open(filepath, 'w', encoding='utf-8') as f:
            count = 1
            for segment in self.segments:
                text = segment.get('text', '').strip()
                if not text:
                    continue
                start_time = self.format_time_srt(segment.get('start', 0))
                end_time = self.format_time_srt(segment.get('end', 0))
                if segment.get('start', 0) >= segment.get('end', 0):
                    continue
                f.write(f"{count}\n{start_time} --> {end_time}\n{text}\n\n")
                count += 1

    def save_as_vtt(self, filepath):
        """Lưu segments thành tệp WebVTT."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("WEBVTT\n\n")
            for segment in self.segments:
                text = segment.get('text', '').strip()
                if not text:
                    continue
                start_time = self.format_time_vtt(segment.get('start', 0))
                end_time = self.format_time_vtt(segment.get('end', 0))
                if segment.get('start', 0) >= segment.get('end', 0):
                    continue
                f.write(f"{start_time} --> {end_time}\n{text}\n\n")

    def save_as_json(self, filepath):
        """Lưu segments thành tệp JSON."""
        try:
            serializable_segments = [{'start': s.get('start',0), 'end':s.get('end',0), 'text':s.get('text','')} for s in self.segments]
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(serializable_segments, f, indent=2, ensure_ascii=False)
        except TypeError as e:
            raise TypeError(f"Data non-serializable: {e}")
        except Exception as e:
            raise e

    def format_time_srt(self, seconds):
        """Định dạng thời gian SRT: HH:MM:SS,mmm"""
        if not isinstance(seconds, (int, float)) or seconds < 0:
            seconds = 0
        millis = round(seconds * 1000)
        secs, millis = divmod(millis, 1000)
        mins, secs = divmod(secs, 60)
        hours, mins = divmod(mins, 60)
        return f"{int(hours):02d}:{int(mins):02d}:{int(secs):02d},{int(millis):03d}"

    def format_time_vtt(self, seconds):
        """Định dạng thời gian WebVTT: HH:MM:SS.mmm"""
        if not isinstance(seconds, (int, float)) or seconds < 0:
            seconds = 0
        millis = round(seconds * 1000)
        secs, millis = divmod(millis, 1000)
        mins, secs = divmod(secs, 60)
        hours, mins = divmod(mins, 60)
        return f"{int(hours):02d}:{int(mins):02d}:{int(secs):02d}.{int(millis):03d}"

    def closeEvent(self, event):
        """Dọn dẹp khi đóng cửa sổ."""
        print("INFO: Close event called. Cleaning up...")
        self.mediaplayer.stop()
        self.timer.stop()

        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            print("INFO: Stopping worker thread...")
            self.worker_thread.quit()
            if not self.worker_thread.wait(3000):
                print("WARNING: Worker thread termination required.")
                self.worker_thread.terminate()
                self.worker_thread.wait()
            else:
                print("INFO: Worker thread finished.")
        elif hasattr(self, 'worker_thread'):
            print("INFO: Worker thread not running.")

        try:
            if self.temp_dir and os.path.exists(self.temp_dir):
                print(f"INFO: Removing temporary directory: {self.temp_dir}")
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                self.temp_dir = None
        except Exception as e:
            print(f"WARNING: Could not remove temp dir {self.temp_dir}: {e}")

        event.accept()
        print("INFO: Window closed.")

# --- Main execution block ---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.setGeometry(100, 100, 850, 600)
    player.show()
    # Bỏ comment dòng dưới để tự động load video test (thay đường dẫn)
    # test_video_path = "/Users/sylam/Project/intelligence-subtitle/sample_videos/Alicia Keys - If I Ain't Got You (Official HD Video)/Alicia Keys - If I Ain't Got You (Official HD Video).mp4"
    # if os.path.exists(test_video_path): player.load_video(test_video_path)
    sys.exit(app.exec_())