import sys
import os
import tempfile
import json
import shutil
import time
import logging

# Configure logging
logging.basicConfig(level=logging.ERROR)
os.environ["QT_LOGGING_RULES"] = "qt.qml.connections=false;*.debug=false;*.info=false"

# --- PySide6 Imports ---
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                               QFileDialog, QMessageBox, QApplication, QSlider, QStyle,
                               QProgressBar, QGraphicsDropShadowEffect, QSizePolicy)  # Keep if needed
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl, QTimer, Qt, QThread, Signal, QRect, QStandardPaths
from PySide6.QtGui import QFont, QPalette, QColor, QFontMetrics, QPainter, QPen

# --- Dummy Core Classes (Keep as is) ---
try:
    from core.transcriber import transcribe
    from core.worker import TranscriptionWorker
    print("INFO: Using actual 'core' module.")
except ImportError as e:
    print(f"WARNING: Error importing core modules: {e}.")
    print("INFO: Using dummy transcription classes.")

    class TranscriptionWorker(QThread):
        transcription_progress = Signal(str)
        transcription_complete = Signal(list)
        transcription_error = Signal(str)
        def __init__(self, parent=None): super().__init__(parent); self._is_processing=False; self._stop_requested=False
        def process_video(self, path):
            if self._is_processing: return
            self._is_processing=True; self._stop_requested=False; print(f"Dummy Worker: Processing '{os.path.basename(path)}'")
            try:
                self.transcription_progress.emit("Transcribing (dummy)...")
                for i in range(4): # Shorter dummy time
                    if self._stop_requested: self.transcription_error.emit("Cancelled."); return
                    time.sleep(0.5)
                dummy_segments=[{'start':1.0,'end':5.0,'text':'PHỤ ĐỀ TEST 1: Đây là phụ đề thử nghiệm.'},{'start':6.0,'end':10.0,'text':'PHỤ ĐỀ TEST 2: Đây là một phụ đề thử nghiệm khác.'},{'start':11.0,'end':15.0,'text':'PHỤ ĐỀ TEST 3: Đây là phụ đề thử nghiệm thứ ba.'},{'start':16.0,'end':20.0,'text':'PHỤ ĐỀ TEST 4: Phụ đề này nên hiển thị được.'},{'start':21.0,'end':25.0,'text':'PHỤ ĐỀ TEST 5: Đây là phụ đề thử nghiệm thứ năm.'},{'start':26.0,'end':30.0,'text':'PHỤ ĐỀ DÀI: Đây là một phụ đề thử nghiệm dài hơn nhiều, nó nên tự động xuống dòng để kiểm tra hành vi xuống dòng của hệ thống phụ đề trong PySide6.'}]
                if not self._stop_requested: self.transcription_complete.emit(dummy_segments)
            except Exception as ex: self.transcription_error.emit(f"Dummy error: {ex}")
            finally: self._is_processing=False
        def stop(self): self._stop_requested=True
    def transcribe(a, t): print(f"Dummy transcribe {a}"); return []
# --- End Dummy Core ---


class VideoPlayer(QWidget):
    process_video_signal = Signal(str)
    # --- Constants ---
    # SUBTITLE_LR_MARGIN = 20 # Not needed when subtitle is below video in layout
    # SUBTITLE_BOTTOM_MARGIN = 10 # Small margin below subtitle if needed
    SUBTITLE_FONT_SIZE = 18 # Adjust font size as needed
    SUBTITLE_TIMER_INTERVAL = 50 # ms

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Intelligent Subtitle (Video Fills Window)")
        # --- Main Layout ---
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10) # Window Margins
        self.layout.setSpacing(5) # Reduce spacing between elements

        # --- Video Widget ---
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(640, 360)
        # Make video widget expand vertically and horizontally
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # Thêm dòng này

        # --- Subtitle Label ---
        self.subtitle_label = QLabel(" ") # Start with a space to ensure initial height
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        # --- Style for SUBTITLE BELOW video ---
        self.subtitle_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.SUBTITLE_FONT_SIZE}px;
                font-weight: bold;
                padding: 5px 10px;
                min-height: {self.SUBTITLE_FONT_SIZE + 10}px;
            }}
        """)
        # Hide initially until text is set
        self.subtitle_label.hide()
        # Subtitle label should only take the height it needs
        self.subtitle_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum) # Thêm dòng này

        # --- Progress Bar ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(10) # Make it slimmer

        # --- Controls ---
        self.controls_layout = QHBoxLayout()
        # Buttons and Slider setup (same as before)
        self.open_btn = QPushButton("Open Video")
        self.open_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.play_pause_btn = QPushButton()
        self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.play_pause_btn.setEnabled(False)
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_position)
        self.position_slider.setEnabled(False)
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

        # --- Assemble Main Layout ---
        # 1. Add Video Widget (takes most space)
        self.layout.addWidget(self.video_widget, 1) # Stretch factor 1 allows vertical expansion
        # 2. Add Subtitle Label (below video, takes needed height)
        self.layout.addWidget(self.subtitle_label) # Stretch factor 0 (default)
        # 3. Add Progress Bar
        self.layout.addWidget(self.progress_bar)
        # 4. Add Controls Layout
        self.layout.addLayout(self.controls_layout)
        # Set the main layout for the window
        self.setLayout(self.layout)

        # --- Media Player Setup (Same as before) ---
        try:
            self.audio_output = QAudioOutput()
            self.media_player = QMediaPlayer()
            self.media_player.setAudioOutput(self.audio_output)
            self.media_player.setVideoOutput(self.video_widget)
            self.audio_output.setVolume(0.7)
            print("INFO: QMediaPlayer with QAudioOutput initialized.")
        except Exception as e:
            print(f"ERROR: Failed to set up QMediaPlayer with QAudioOutput: {e}")
            QMessageBox.critical(self, "Initialization Error", "Could not initialize media components.")
            # Fallback might be needed or exit
            self.media_player = QMediaPlayer() # Create a basic one anyway
            self.media_player.setVideoOutput(self.video_widget)


        # Connect signals (Same as before)
        self.media_player.errorOccurred.connect(self.handle_error)
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.media_player.playbackStateChanged.connect(self.state_changed)
        self.media_player.mediaStatusChanged.connect(self.media_status_changed)

        # --- State Variables (Same as before) ---
        self.segments = []
        self.current_segment_index = -1
        self.next_segment_index = 0
        self.temp_dir = tempfile.mkdtemp(prefix="subtitle_app_")
        print(f"INFO: Temp directory created: {self.temp_dir}")
        self.video_path = ""
        self.subtitle_timer = QTimer(self)
        self.subtitle_timer.setInterval(self.SUBTITLE_TIMER_INTERVAL)
        self.subtitle_timer.timeout.connect(self.update_subtitle_display)

        # --- Worker Thread Setup (Same as before) ---
        self.setup_worker_thread()
        self.open_btn.clicked.connect(self.open_video_dialog)

    def setup_worker_thread(self):
        # Function remains the same as previous version
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

    # --- Event Handlers (resizeEvent, showEvent) ---
    # NO LONGER NEEDED for manual positioning
    # def resizeEvent(self, event):
    #     super().resizeEvent(event)
    # def showEvent(self, event):
    #     super().showEvent(event)

    # --- position_subtitle_label METHOD IS NO LONGER NEEDED ---
    # Delete this entire method as the layout handles positioning

    def set_subtitle_text(self, text):
        """Sets the subtitle text and updates visibility."""
        new_text_trimmed = text.strip() if text else ""

        # Update the text
        self.subtitle_label.setText(new_text_trimmed if new_text_trimmed else " ") # Use space to maintain height

        # Show or hide the label based on whether there is text
        # The layout will adjust automatically
        if new_text_trimmed:
            if not self.subtitle_label.isVisible():
                self.subtitle_label.show()
        else:
            if self.subtitle_label.isVisible():
                self.subtitle_label.hide()

        # No need to call position_subtitle_label or raise_() anymore
        # No need to call update() usually, layout handles it

    # --- Other Methods (open_video_dialog, load_video, media_status_changed, etc.) ---
    # Keep these methods largely the same as the previous working version.
    # Ensure any references to video_container or manual positioning are removed/adjusted.
    # (Copying the relevant methods from the previous full code example)

    def open_video_dialog(self):
        default_dir = QStandardPaths.writableLocation(QStandardPaths.MoviesLocation)
        if not default_dir: default_dir = os.path.expanduser("~")
        file_dialog = QFileDialog(self)
        file_dialog.setDirectory(default_dir)
        video_url, _ = file_dialog.getOpenFileUrl(self,"Open Video File",QUrl.fromLocalFile(default_dir),"Video Files (*.mp4 *.avi *.mkv *.mov *.wmv *.flv);;All Files (*)")
        if video_url.isValid() and video_url.isLocalFile(): self.load_video(video_url.toLocalFile())
        elif video_url.isValid(): QMessageBox.warning(self, "Unsupported Source","Only local video files are currently supported.")

    def load_video(self, video_path):
        if not os.path.exists(video_path): QMessageBox.critical(self, "File Not Found", f"Video file not found:\n{video_path}"); return
        if not os.path.isfile(video_path): QMessageBox.critical(self, "Invalid Path", f"Path is not a file:\n{video_path}"); return
        self.video_path = video_path; print(f"INFO: Loading video: {self.video_path}")
        self.media_player.stop(); self.segments = []; self.current_segment_index = -1; self.next_segment_index = 0
        self.save_subtitle_btn.setEnabled(False); self.set_subtitle_text("")
        if self.subtitle_timer.isActive(): self.subtitle_timer.stop()
        self.play_pause_btn.setEnabled(False); self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.position_slider.setValue(0); self.position_slider.setEnabled(False); self.duration_label.setText("00:00 / 00:00")
        url = QUrl.fromLocalFile(video_path); self.media_player.setSource(url)
        self.progress_bar.setVisible(True); self.set_subtitle_text("Loading & Transcribing...")
        QTimer.singleShot(100, lambda: self.process_video_signal.emit(self.video_path)); print(f"INFO: Emitted process signal for: {video_path}")

    def media_status_changed(self, status):
        # Use the correct enum names for your PySide6 version
        status_map = { 
            QMediaPlayer.MediaStatus.NoMedia: "NoMedia", 
            QMediaPlayer.MediaStatus.LoadingMedia: "LoadingMedia", 
            QMediaPlayer.MediaStatus.LoadedMedia: "LoadedMedia",
            QMediaPlayer.MediaStatus.StalledMedia: "StalledMedia", 
            QMediaPlayer.MediaStatus.BufferingMedia: "BufferingMedia", 
            QMediaPlayer.MediaStatus.BufferedMedia: "BufferedMedia", 
            QMediaPlayer.MediaStatus.EndOfMedia: "EndOfMedia", 
            QMediaPlayer.MediaStatus.InvalidMedia: "InvalidMedia",
        }
        # print(f"DEBUG: Media Status Changed: {status_map.get(status, 'Other')}")
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            print("INFO: Media Loaded."); self.play_pause_btn.setEnabled(True); self.position_slider.setEnabled(True)
            self.duration_changed(self.media_player.duration()) # Update duration label now
            if self.progress_bar.isVisible(): self.set_subtitle_text("") # Clear loading msg
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            print("INFO: End Of Media."); self.media_player.setPosition(0); self.set_subtitle_text("")
            self.current_segment_index = -1; self.next_segment_index = 0
            if self.subtitle_timer.isActive(): self.subtitle_timer.stop()
            # Let state_changed handle icon
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            print("ERROR: Invalid Media Status."); self.handle_error(QMediaPlayer.MediaError.FormatError, "Invalid/unsupported media.")
        elif status == QMediaPlayer.MediaStatus.LoadingMedia:
            print("INFO: Media Loading..."); self.play_pause_btn.setEnabled(False); self.position_slider.setEnabled(False)
        elif status == QMediaPlayer.MediaStatus.NoMedia:
            print("INFO: No Media."); self.play_pause_btn.setEnabled(False); self.position_slider.setEnabled(False)
            self.position_slider.setValue(0); self.duration_label.setText("00:00 / 00:00"); self.set_subtitle_text("")
            self.save_subtitle_btn.setEnabled(False); self.segments = []
            if self.subtitle_timer.isActive(): self.subtitle_timer.stop()

    def on_transcription_progress(self, message):
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
             print(f"INFO: Transcription Progress: {message}"); self.set_subtitle_text(message)

    def on_transcription_complete(self, segments):
        print(f"INFO: Transcription Complete. Segments: {len(segments)}"); self.segments = segments if segments else []
        self.current_segment_index = -1; self.next_segment_index = 0
        self.save_subtitle_btn.setEnabled(bool(self.segments)); self.progress_bar.setVisible(False)
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
             completion_msg = "Transcription complete!" if self.segments else "Transcription complete (no subs)."
             # Fix the comparison to use the correct MediaStatus enum names
             if self.media_player.mediaStatus() == QMediaPlayer.MediaStatus.LoadedMedia or self.media_player.mediaStatus() == QMediaPlayer.MediaStatus.BufferedMedia: 
                 completion_msg += " Press play."
             self.set_subtitle_text(completion_msg); QTimer.singleShot(4000, self.clear_info_message_if_not_playing)
        else:
             if self.segments and not self.subtitle_timer.isActive():
                 print("INFO: Trans complete while playing, start timer."); self.update_subtitle_display(); self.subtitle_timer.start()

    def clear_info_message_if_not_playing(self):
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            current_msg = self.subtitle_label.text()
            info_msgs = ["Transcription complete", "Loading", "Error", "Press play"]
            if any(msg in current_msg for msg in info_msgs): print("INFO: Clearing info message."); self.set_subtitle_text("")

    def on_transcription_error(self, error_message):
        print(f"ERROR: Transcription Error: {error_message}"); self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Transcription Error", f"Transcription failed:\n{error_message}")
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
             self.set_subtitle_text("Transcription error."); QTimer.singleShot(5000, self.clear_info_message_if_not_playing)

    def toggle_play_pause(self):
        if not self.play_pause_btn.isEnabled(): return
        state = self.media_player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState: print("INFO: Pausing."); self.media_player.pause()
        else: print("INFO: Playing."); self.media_player.play(); self.clear_info_message_if_not_playing()

    def state_changed(self, state):
        state_map = { QMediaPlayer.PlaybackState.StoppedState: "Stopped", QMediaPlayer.PlaybackState.PlayingState: "Playing", QMediaPlayer.PlaybackState.PausedState: "Paused", }
        # print(f"DEBUG: Playback State Changed: {state_map.get(state, 'Other')}")
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            if self.segments and not self.subtitle_timer.isActive():
                print("INFO: Playback started, ensure timer runs."); self.update_subtitle_display(); self.subtitle_timer.start()
            self.clear_info_message_if_not_playing()
        else:
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            if self.subtitle_timer.isActive(): print("INFO: Playback stopped/paused, stop timer."); self.subtitle_timer.stop()

    def update_subtitle_display(self):
        if not self.segments or self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            if self.subtitle_timer.isActive() and self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState: self.subtitle_timer.stop()
            if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState: self.set_subtitle_text("")
            return
        current_time_sec = self.media_player.position() / 1000.0
        text_to_display = ""; found_current = False
        if self.next_segment_index < len(self.segments):
            next_seg = self.segments[self.next_segment_index]
            next_start_time = next_seg.get('start', float('inf'))
            if current_time_sec >= next_start_time:
                self.current_segment_index = self.next_segment_index; self.next_segment_index += 1; current_seg = next_seg
                if current_time_sec < current_seg.get('end', 0): text_to_display = current_seg.get('text', '').strip(); found_current = True
                else: self.current_segment_index = -1; text_to_display = ""; found_current = False
            else:
                 found_current = self.check_current_segment(current_time_sec)
                 text_to_display = self.segments[self.current_segment_index].get('text', '').strip() if found_current else ""
        elif self.current_segment_index >= 0:
            found_current = self.check_current_segment(current_time_sec)
            if found_current: text_to_display = self.segments[self.current_segment_index].get('text', '').strip()
            else: self.current_segment_index = -1; text_to_display = ""
        if self.subtitle_label.text() != text_to_display: self.set_subtitle_text(text_to_display)

    def check_current_segment(self, current_time_sec):
        if self.current_segment_index < 0 or self.current_segment_index >= len(self.segments): return False
        current_seg = self.segments[self.current_segment_index]
        return current_seg.get('start', -1) <= current_time_sec < current_seg.get('end', 0)

    def position_changed(self, position):
        if not self.position_slider.isSliderDown(): self.position_slider.setValue(position)
        self.update_duration_label(position, self.media_player.duration())

    def duration_changed(self, duration):
        if duration < 0: duration = 0; print(f"INFO: Duration changed: {duration} ms"); self.position_slider.setRange(0, duration)
        self.position_slider.setEnabled(duration > 0); self.update_duration_label(self.media_player.position(), duration)

    def set_position(self, position):
        self.media_player.setPosition(position)
        if self.segments:
            current_time_sec = position / 1000.0; self.update_segment_indices(current_time_sec)
            current_text = self.get_current_subtitle_text(current_time_sec); self.set_subtitle_text(current_text)

    def update_segment_indices(self, current_time_sec):
        self.current_segment_index = -1; self.next_segment_index = 0; found_next = False
        if not self.segments: return
        for i, segment in enumerate(self.segments):
            start = segment.get('start', -1); end = segment.get('end', 0)
            if start < 0 or end <= start: continue
            if start <= current_time_sec < end: self.current_segment_index = i; self.next_segment_index = i + 1; return
            elif self.current_segment_index == -1 and current_time_sec < start: self.next_segment_index = i; return
        if self.current_segment_index == -1:
            self.next_segment_index = len(self.segments)
            if self.segments and current_time_sec >= self.segments[-1].get('start', float('inf')): self.current_segment_index = len(self.segments) - 1

    def get_current_subtitle_text(self, current_time_sec):
        if self.current_segment_index >= 0 and self.current_segment_index < len(self.segments):
             segment = self.segments[self.current_segment_index]
             if segment.get('start', -1) <= current_time_sec < segment.get('end', 0): return segment.get('text', '').strip()
        return ""

    def update_duration_label(self, position, duration):
        """Updates the label showing current time / total duration."""
        # Ensure non-negative values
        if duration < 0:
            duration = 0
        if position < 0:
            position = 0
        # Cap position at duration
        position = min(position, duration) # Luôn thực hiện việc giới hạn này

        # Convert milliseconds to seconds
        pos_sec_total = position // 1000
        dur_sec_total = duration // 1000

        # Calculate minutes and seconds
        pos_min, pos_sec = divmod(pos_sec_total, 60)
        dur_min, dur_sec = divmod(dur_sec_total, 60)

        # Format the string
        self.duration_label.setText(f"{pos_min:02d}:{pos_sec:02d} / {dur_min:02d}:{dur_sec:02d}")

    def handle_error(self, error_code, specific_message=""):
        error_string = self.media_player.errorString(); print(f"ERROR: MP Error - Code:{error_code}, Str:'{error_string}', Spec:'{specific_message}'")
        display_message = specific_message or error_string
        if not display_message:
            error_map = { 
                QMediaPlayer.MediaError.ResourceError: "Cannot load resource.", 
                QMediaPlayer.MediaError.FormatError: "Unsupported format.", 
                QMediaPlayer.MediaError.NetworkError: "Network error.", 
                QMediaPlayer.MediaError.AccessDeniedError: "Access denied.", 
                QMediaPlayer.MediaError.ServiceMissingError: "Media service missing.",
            }
            # Remove MediaIsPlaylist which might not exist in your Qt version
            display_message = error_map.get(error_code, f"Unknown media error ({error_code}).")
        QMessageBox.critical(self, "Media Player Error", display_message)
        self.play_pause_btn.setEnabled(False); self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.position_slider.setEnabled(False); self.position_slider.setValue(0); self.duration_label.setText("00:00 / 00:00")
        self.set_subtitle_text(""); self.progress_bar.setVisible(False); self.save_subtitle_btn.setEnabled(False)
        self.segments = [];
        if self.subtitle_timer.isActive(): self.subtitle_timer.stop()

    # --- Subtitle Saving Functions (Keep as is) ---
    def save_subtitles(self):
        if not self.segments: QMessageBox.warning(self, "No Subtitles", "No subtitles to save."); return
        if self.video_path: video_filename = os.path.basename(self.video_path); video_name = os.path.splitext(video_filename)[0]; default_dir = os.path.dirname(self.video_path)
        else: video_name = "subtitles"; default_dir = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        default_filename = os.path.join(default_dir, f"{video_name}.srt")
        filters = "SubRip Subtitles (*.srt);;WebVTT (*.vtt);;JSON (*.json);;All Files (*)"; options = QFileDialog.Options()
        save_path, selected_filter = QFileDialog.getSaveFileName(self, "Save Subtitles As...", default_filename, filters, options=options)
        if not save_path: print("INFO: Save cancelled."); return
        print(f"INFO: Saving subtitles to: {save_path}"); file_format = 'srt'
        if "(*.vtt)" in selected_filter: file_format = 'vtt'
        elif "(*.json)" in selected_filter: file_format = 'json'
        elif "(*.srt)" in selected_filter: file_format = 'srt'
        else:
            _, ext = os.path.splitext(save_path); ext = ext.lower()
            if ext == '.vtt': file_format = 'vtt'
            elif ext == '.json': file_format = 'json'
            elif ext != '.srt':
                 if not ext: save_path += ".srt"; print("INFO: No extension, saving as SRT.")
                 else: print(f"WARN: Unknown ext '{ext}', saving as SRT.")
                 file_format = 'srt'
        print(f"INFO: Saving format: {file_format.upper()}")
        try:
            if file_format == 'srt': self.save_as_srt(save_path)
            elif file_format == 'vtt': self.save_as_vtt(save_path)
            elif file_format == 'json': self.save_as_json(save_path)
            QMessageBox.information(self, "Save Successful", f"Subtitles saved to:\n{save_path}")
        except Exception as e: print(f"ERROR: Save failed: {e}"); QMessageBox.critical(self, "Save Error", f"Failed to save subtitles:\n{str(e)}")
    def save_as_srt(self, filepath):
        count = 0;
        with open(filepath, 'w', encoding='utf-8') as f:
            for segment in self.segments:
                text = segment.get('text','').strip(); start = segment.get('start',-1); end = segment.get('end',-1)
                if text and start >= 0 and end > start: count += 1; start_time = self.format_time_srt(start); end_time = self.format_time_srt(end); f.write(f"{count}\n{start_time} --> {end_time}\n{text}\n\n")
        print(f"INFO: Saved {count} segments to SRT.");
        if count == 0: QMessageBox.warning(self, "Empty File", "No valid segments to save.")
    def save_as_vtt(self, filepath):
        count = 0;
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("WEBVTT\n\n");
            for segment in self.segments:
                text = segment.get('text','').strip(); start = segment.get('start',-1); end = segment.get('end',-1)
                if text and start >= 0 and end > start: count += 1; start_time = self.format_time_vtt(start); end_time = self.format_time_vtt(end); f.write(f"{start_time} --> {end_time}\n{text}\n\n")
        print(f"INFO: Saved {count} segments to VTT.");
        if count == 0: QMessageBox.warning(self, "Empty File", "No valid segments to save.")
    def save_as_json(self, filepath):
        valid_segments = [{'start':float(s.get('start',-1)), 'end':float(s.get('end',-1)), 'text':str(s.get('text',''))} for s in self.segments if s.get('text','').strip() and s.get('start',-1) >= 0 and s.get('end',-1) > s.get('start',-1)]
        if not valid_segments: QMessageBox.warning(self, "Empty Data", "No valid segments to save."); return
        try:
            with open(filepath, 'w', encoding='utf-8') as f: json.dump(valid_segments, f, indent=2, ensure_ascii=False)
            print(f"INFO: Saved {len(valid_segments)} segments to JSON.")
        except Exception as e: raise e # Let save_subtitles handle message box
    def format_time_srt(self, seconds):
        if not isinstance(seconds, (int, float)) or seconds < 0: seconds = 0; total_milliseconds = int(round(seconds * 1000))
        secs, milliseconds = divmod(total_milliseconds, 1000); mins, secs = divmod(secs, 60); hours, mins = divmod(mins, 60)
        return f"{hours:02d}:{mins:02d}:{secs:02d},{milliseconds:03d}"
    def format_time_vtt(self, seconds):
        if not isinstance(seconds, (int, float)) or seconds < 0: seconds = 0; total_milliseconds = int(round(seconds * 1000))
        secs, milliseconds = divmod(total_milliseconds, 1000); mins, secs = divmod(secs, 60); hours, mins = divmod(mins, 60)
        return f"{hours:02d}:{mins:02d}:{secs:02d}.{milliseconds:03d}"
    # --- End Saving Functions ---

    def closeEvent(self, event):
        """Cleans up resources when the window is closed."""
        print("INFO: Close event. Cleaning up..."); self.media_player.stop()
        if self.subtitle_timer.isActive(): self.subtitle_timer.stop()
        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            print("INFO: Quitting worker thread...")
            if hasattr(self.transcription_worker, 'stop'): self.transcription_worker.stop()
            self.worker_thread.quit()
            if not self.worker_thread.wait(3000): print("WARN: Worker terminate needed."); self.worker_thread.terminate(); self.worker_thread.wait(500)
            else: print("INFO: Worker thread finished.")
        try:
            if hasattr(self, 'temp_dir') and self.temp_dir and os.path.exists(self.temp_dir):
                 print(f"INFO: Removing temp dir: {self.temp_dir}"); shutil.rmtree(self.temp_dir, ignore_errors=True); self.temp_dir = None
        except Exception as e: print(f"WARN: Temp dir cleanup error: {e}")
        print("INFO: Cleanup complete. Closing window."); event.accept()

# --- Main Execution ---
if __name__ == '__main__':
    # Enable High DPI scaling
    if hasattr(Qt, 'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.setGeometry(100, 100, 950, 700) # Adjust initial size if needed
    player.show()

    # --- Auto-load test video ---
    test_video_path = r"D:\Download\Video\Alicia Keys - If I Ain't Got You (Official HD Video).mp4" # Change this path
    if os.path.exists(test_video_path):
        print(f"INFO: Auto-loading: {test_video_path}")
        QTimer.singleShot(100, lambda: player.load_video(test_video_path))
    else:
         print(f"WARN: Auto-load video not found: {test_video_path}")
         # Don't show message box on startup, let user open manually
         # QMessageBox.information(player, "Info", "Test video not found. Use 'Open Video'.")

    sys.exit(app.exec())