import sys
import os
import tempfile
import json
import shutil
import time # Import time cho dummy worker

# --- PyQt5 Imports ---
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QFileDialog, QMessageBox, QApplication, QSlider, QStyle,
                             QProgressBar, QGraphicsDropShadowEffect) # Thêm QGraphicsDropShadowEffect nếu muốn thử
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl, QTimer, Qt, QThread, pyqtSignal, QRect
from PyQt5.QtGui import QFont, QPalette, QColor, QFontMetrics, QPainter

# --- Giả lập core nếu không tìm thấy ---
try:
    # Điều chỉnh đường dẫn nếu thư mục 'core' không nằm cùng cấp
    # Ví dụ: sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
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
# --- Kết thúc phần giả lập ---

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

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(640, 360)
        self.video_widget.setAutoFillBackground(True)

        self.subtitle_label = QLabel(self)
        self.subtitle_label.setAttribute(Qt.WA_TranslucentBackground)
        self.subtitle_label.setAutoFillBackground(False)

        # --- Tắt Debug Visuals mặc định ---
        debug_style = False # Đặt thành True để bật nền đỏ/viền vàng
        # ----------------------------------
        temp_bg = "background-color: rgba(255, 0, 0, 0.4);" if debug_style else "background-color: transparent;"
        temp_border = "border: 1px solid yellow;" if debug_style else "border: none;"

        # --- Stylesheet KHÔNG CÓ text-shadow ---
        self.subtitle_label.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: {self.SUBTITLE_FONT_SIZE}px;
                font-weight: bold;
                padding: 5px;
                margin: 0px;
                {temp_border}  /* DEBUG BORDER */
                {temp_bg}      /* DEBUG BACKGROUND */
                background: none; /* Đảm bảo nền trong suốt */
                /* text-shadow: ... ; ĐÃ BỊ XÓA */
            }}
        """)
        # --- Tùy chọn: Thêm hiệu ứng đổ bóng bằng QGraphicsDropShadowEffect ---
        # shadow = QGraphicsDropShadowEffect(self)
        # shadow.setBlurRadius(5)
        # shadow.setColor(QColor(0, 0, 0, 190))
        # shadow.setOffset(1.5, 1.5)
        # self.subtitle_label.setGraphicsEffect(shadow)
        # -------------------------------------------------------------------

        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.hide()
        self.subtitle_label.raise_()

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

        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.error.connect(self.handle_error)
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.media_player.stateChanged.connect(self.state_changed)
        self.media_player.mediaStatusChanged.connect(self.media_status_changed)

        self.segments = []
        self.current_segment_index = -1
        self.next_segment_index = 0
        self.temp_dir = tempfile.mkdtemp(prefix="subtitle_app_")
        print(f"INFO: Temp directory created: {self.temp_dir}")
        self.video_path = ""
        self.subtitle_timer = QTimer(self)
        self.subtitle_timer.setInterval(self.SUBTITLE_TIMER_INTERVAL)
        self.subtitle_timer.timeout.connect(self.update_subtitle_display)

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
        # self.transcription_worker.finished.connect(self.transcription_worker.deleteLater) # Chỉ khi worker là QObject
        self.worker_thread.start()
        print("INFO: Worker thread started.")

    def resizeEvent(self, event):
        """Xử lý thay đổi kích thước cửa sổ."""
        super().resizeEvent(event)
        QTimer.singleShot(0, self.position_subtitle_label)

    def showEvent(self, event):
        """Gọi khi widget được hiển thị."""
        super().showEvent(event)
        # print("DEBUG: showEvent called")
        QTimer.singleShot(50, self.position_subtitle_label)

    def position_subtitle_label(self):
        """Tính toán và đặt vị trí, kích thước cho label phụ đề."""
        if not self.video_widget.isVisible():
            return

        video_rect = self.video_widget.geometry()
        if not video_rect.isValid() or video_rect.width() <= 0 or video_rect.height() <= 0:
            # print("DEBUG: position_subtitle_label - Invalid video_rect, trying parent rect")
            video_rect = self.rect()
            if not video_rect.isValid() or video_rect.width() <= 0 or video_rect.height() <= 0:
                # print("DEBUG: position_subtitle_label - Parent rect also invalid, cannot position")
                return

        label_width = video_rect.width() - (2 * self.SUBTITLE_LR_MARGIN)
        if label_width < 50: label_width = 50

        current_text = self.subtitle_label.text()
        fm = QFontMetrics(self.subtitle_label.font())
        min_label_height = fm.height() + 10

        if not current_text:
             label_height = min_label_height
        else:
             bounding_rect = fm.boundingRect(QRect(0, 0, label_width, 1000),
                                               Qt.AlignCenter | Qt.TextWordWrap,
                                               current_text)
             label_height = bounding_rect.height() + 10

        if label_height < min_label_height: label_height = min_label_height
        if label_height <= 0: label_height = min_label_height

        label_x = video_rect.x() + self.SUBTITLE_LR_MARGIN
        label_y = video_rect.y() + video_rect.height() - label_height - self.SUBTITLE_BOTTOM_MARGIN

        self.subtitle_label.setGeometry(label_x, label_y, label_width, label_height)
        self.subtitle_label.raise_()

    def set_subtitle_text(self, text):
        """Đặt nội dung cho label phụ đề và cập nhật hiển thị."""
        current_text_on_label = self.subtitle_label.text()
        is_currently_visible = self.subtitle_label.isVisible()
        new_text_trimmed = text.strip() if text else "" # Xử lý None và strip

        if not new_text_trimmed:
            if is_currently_visible:
                self.subtitle_label.hide()
                self.subtitle_label.clear()
            return

        if new_text_trimmed != current_text_on_label or not is_currently_visible:
            self.subtitle_label.setText(new_text_trimmed)
            self.position_subtitle_label() # Định vị lại TRƯỚC khi show
            if not is_currently_visible:
                self.subtitle_label.show()

    def open_video_dialog(self):
        """Mở hộp thoại chọn tệp video."""
        file_dialog = QFileDialog(self)
        video_path, _ = file_dialog.getOpenFileName(self, "Open Video", "",
                                                    "Video Files (*.mp4 *.avi *.mkv *.mov *.wmv);;All Files (*)")
        if video_path:
            self.load_video(video_path)

    def load_video(self, video_path):
        """Tải video mới, đặt lại trạng thái và bắt đầu gỡ băng."""
        self.video_path = video_path
        print(f"INFO: Loading video: {self.video_path}")
        if not os.path.exists(video_path):
            QMessageBox.critical(self, "Error", f"Video file not found:\n{video_path}")
            return

        self.media_player.stop()
        self.segments = []
        self.current_segment_index = -1
        self.next_segment_index = 0
        self.save_subtitle_btn.setEnabled(False)
        self.set_subtitle_text("")
        if self.subtitle_timer.isActive(): self.subtitle_timer.stop()
        self.play_pause_btn.setEnabled(False)
        self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.position_slider.setValue(0)
        self.position_slider.setEnabled(False)
        self.duration_label.setText("00:00 / 00:00")

        url = QUrl.fromLocalFile(video_path)
        self.media_player.setMedia(QMediaContent(url))

        self.progress_bar.setVisible(True)
        self.set_subtitle_text("Loading video & starting transcription...")
        print("INFO: Emitting process_video_signal")
        self.process_video_signal.emit(video_path)

    def media_status_changed(self, status):
        """Xử lý thay đổi trạng thái của media."""
        # print(f"DEBUG: media_status_changed - Status: {status}")
        if status == QMediaPlayer.LoadedMedia:
            print("INFO: Media Loaded.")
            self.play_pause_btn.setEnabled(True)
            self.position_slider.setEnabled(True)
            QTimer.singleShot(0, self.position_subtitle_label)
        elif status == QMediaPlayer.EndOfMedia:
             print("INFO: End Of Media.")
             self.media_player.setPosition(0)
             self.media_player.pause()
             self.set_subtitle_text("")
             self.current_segment_index = -1
             self.next_segment_index = 0
        elif status == QMediaPlayer.InvalidMedia:
            print("ERROR: Invalid Media.")
            self.handle_error(QMediaPlayer.FormatError)
        elif status == QMediaPlayer.LoadingMedia:
            print("INFO: Media Loading...")
            self.position_slider.setEnabled(False)
        elif status == QMediaPlayer.NoMedia:
            print("INFO: No Media.")
            self.play_pause_btn.setEnabled(False)
            self.position_slider.setEnabled(False)
            self.duration_label.setText("00:00 / 00:00")
            self.set_subtitle_text("")

    def on_transcription_progress(self, message):
        """Cập nhật thông báo tiến trình gỡ băng."""
        if self.media_player.state() != QMediaPlayer.PlayingState or not self.subtitle_label.isVisible():
             print(f"INFO: Transcription Progress: {message}")
             self.set_subtitle_text(message)

    def on_transcription_complete(self, segments):
        """Xử lý khi gỡ băng hoàn tất."""
        print(f"INFO: Transcription Complete. Received {len(segments)} segments.")
        self.segments = segments if segments else []
        self.current_segment_index = -1
        self.next_segment_index = 0
        self.save_subtitle_btn.setEnabled(bool(self.segments))
        self.progress_bar.setVisible(False)

        if self.media_player.state() != QMediaPlayer.PlayingState:
             completion_msg = "Transcription complete!" if self.segments else "Transcription complete (no subtitles found)."
             self.set_subtitle_text(completion_msg + " Press play.")
             QTimer.singleShot(4000, self.clear_info_message_if_not_playing)
        else:
             if self.segments:
                 print("INFO: Transcription complete while playing, starting subtitle timer.")
                 self.update_subtitle_display()
                 if not self.subtitle_timer.isActive(): self.subtitle_timer.start()

    def clear_info_message_if_not_playing(self):
        """Xóa các thông báo trạng thái nếu video không đang phát."""
        if self.media_player.state() != QMediaPlayer.PlayingState:
            current_msg = self.subtitle_label.text()
            info_msgs = ["Transcription complete", "Loading video", "Error in transcription"]
            if any(msg in current_msg for msg in info_msgs):
                 print("INFO: Clearing info message.")
                 self.set_subtitle_text("")

    def on_transcription_error(self, error_message):
        """Xử lý khi có lỗi trong quá trình gỡ băng."""
        print(f"ERROR: Transcription Error: {error_message}")
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Transcription Error", f"Failed to transcribe audio:\n{error_message}")
        self.set_subtitle_text("Error in transcription.")
        QTimer.singleShot(5000, self.clear_info_message_if_not_playing)

    def toggle_play_pause(self):
        """Chuyển đổi giữa trạng thái phát và tạm dừng."""
        if not self.play_pause_btn.isEnabled(): return
        if self.media_player.state() == QMediaPlayer.PlayingState:
            print("INFO: Pausing media.")
            self.media_player.pause()
        else:
            print("INFO: Playing media.")
            self.media_player.play()

    def state_changed(self, state):
        """Xử lý thay đổi trạng thái của media player."""
        # print(f"DEBUG: state_changed - State: {state}")
        if state == QMediaPlayer.PlayingState:
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            if self.segments and not self.subtitle_timer.isActive():
                print("INFO: Player playing, starting subtitle timer.")
                current_time_sec = self.media_player.position() / 1000.0
                self.update_segment_indices(current_time_sec)
                current_text = self.get_current_subtitle_text(current_time_sec)
                self.set_subtitle_text(current_text)
                self.subtitle_timer.start()
            self.clear_info_message_if_not_playing()
        else: # Paused, Stopped
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            if self.subtitle_timer.isActive():
                print("INFO: Player not playing, stopping subtitle timer.")
                self.subtitle_timer.stop()

    def update_subtitle_display(self):
        """Cập nhật hiển thị phụ đề dựa trên thời gian hiện tại."""
        if not self.segments or self.media_player.state() != QMediaPlayer.PlayingState:
            if self.subtitle_timer.isActive(): self.subtitle_timer.stop()
            return

        current_time = self.media_player.position() / 1000.0
        text_to_display = "" # Mặc định là không hiển thị gì

        # Tìm segment phù hợp
        target_segment = None
        # Tối ưu: kiểm tra segment tiếp theo trước nếu hợp lệ
        if self.next_segment_index < len(self.segments):
            next_seg = self.segments[self.next_segment_index]
            if current_time >= next_seg['start']:
                 target_segment = next_seg
                 self.current_segment_index = self.next_segment_index
                 self.next_segment_index += 1 # Chuẩn bị cho lần sau

        # Nếu không phải next_segment, kiểm tra current_segment
        if target_segment is None and self.current_segment_index >= 0 and self.current_segment_index < len(self.segments):
             current_seg = self.segments[self.current_segment_index]
             if current_time >= current_seg['start'] and current_time < current_seg['end']:
                 target_segment = current_seg

        # Lấy text từ segment tìm được (hoặc để trống nếu không tìm thấy hoặc đã qua thời gian kết thúc)
        if target_segment and current_time < target_segment['end']:
            text_to_display = target_segment.get('text', '')

        # Chỉ cập nhật QLabel nếu text thực sự thay đổi
        if self.subtitle_label.text() != text_to_display:
            self.set_subtitle_text(text_to_display)

    def position_changed(self, position):
        """Cập nhật vị trí slider."""
        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(position)
        self.update_duration_label(position, self.media_player.duration())

    def duration_changed(self, duration):
        """Cập nhật khoảng giá trị của slider."""
        print(f"INFO: Duration changed: {duration} ms")
        self.position_slider.setRange(0, duration)
        self.position_slider.setEnabled(duration > 0)
        self.update_duration_label(self.media_player.position(), duration)

    def set_position(self, position):
        """Di chuyển vị trí phát media player."""
        self.media_player.setPosition(position)
        if self.segments:
            current_time_sec = position / 1000.0
            self.update_segment_indices(current_time_sec)
            current_text = self.get_current_subtitle_text(current_time_sec)
            self.set_subtitle_text(current_text)

    def update_segment_indices(self, current_time):
        """Cập nhật index phụ đề (current và next) sau khi seek."""
        self.current_segment_index = -1
        self.next_segment_index = 0
        found_current = False
        for i, segment in enumerate(self.segments):
            if not found_current and current_time < segment['start']:
                self.next_segment_index = i
                break
            elif current_time < segment['end']:
                self.current_segment_index = i
                self.next_segment_index = i + 1
                found_current = True
                break
        if not found_current and self.segments:
            self.current_segment_index = len(self.segments) - 1
            self.next_segment_index = len(self.segments)

    def get_current_subtitle_text(self, current_time):
        """Lấy text phụ đề chính xác cho thời điểm cụ thể."""
        for segment in self.segments:
             if segment['start'] <= current_time < segment['end']:
                 return segment.get('text', '')
        return ""

    def update_duration_label(self, position, duration):
        """Cập nhật label hiển thị thời gian."""
        if duration <= 0:
            self.duration_label.setText("--:-- / --:--")
            return
        pos_sec_total = position // 1000
        dur_sec_total = duration // 1000
        pos_min, pos_sec = divmod(pos_sec_total, 60)
        dur_min, dur_sec = divmod(dur_sec_total, 60)
        self.duration_label.setText(f"{pos_min:02d}:{pos_sec:02d} / {dur_min:02d}:{dur_sec:02d}")

    def handle_error(self, error_unused): # Tham số error không dùng vì lấy từ media_player
        """Xử lý lỗi từ QMediaPlayer."""
        error_code = self.media_player.error()
        error_string = self.media_player.errorString()
        print(f"ERROR: Media Player Error - Code: {error_code}, String: '{error_string}'")
        if not error_string:
            error_map = { QMediaPlayer.ResourceError: "Cannot load resource.", QMediaPlayer.FormatError: "Unsupported media format.", QMediaPlayer.NetworkError: "Network error.", QMediaPlayer.AccessDeniedError: "Access denied.", }
            error_string = error_map.get(error_code, f"Unknown error code: {error_code}")
        QMessageBox.critical(self, "Media Player Error", error_string)
        self.play_pause_btn.setEnabled(False)
        self.position_slider.setEnabled(False)
        self.position_slider.setValue(0)
        self.duration_label.setText("--:-- / --:--")
        self.set_subtitle_text("")
        self.progress_bar.setVisible(False)
        self.save_subtitle_btn.setEnabled(False)

    def save_subtitles(self):
        """Mở hộp thoại và lưu phụ đề."""
        if not self.segments:
            QMessageBox.warning(self, "No Subtitles", "No subtitles to save.")
            return

        video_filename = os.path.basename(self.video_path) if self.video_path else "video"
        video_name = os.path.splitext(video_filename)[0]
        default_dir = os.path.dirname(self.video_path) if self.video_path else ""
        default_filename = os.path.join(default_dir, f"{video_name}.srt") # Mặc định .srt

        options = QFileDialog.Options()
        save_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Save Subtitles As...", default_filename,
            "SubRip Subtitles (*.srt);;WebVTT (*.vtt);;JSON (*.json);;All Files (*)",
            options=options)

        if not save_path: return

        print(f"INFO: Saving subtitles to: {save_path}")
        _, ext = os.path.splitext(save_path)
        ext = ext.lower()

        try:
            if ext == '.srt' or "(*.srt)" in selected_filter: self.save_as_srt(save_path)
            elif ext == '.vtt' or "(*.vtt)" in selected_filter: self.save_as_vtt(save_path)
            elif ext == '.json' or "(*.json)" in selected_filter: self.save_as_json(save_path)
            else:
                if not ext: save_path += ".srt"
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
                if not text: continue
                start_time = self.format_time_srt(segment.get('start', 0))
                end_time = self.format_time_srt(segment.get('end', 0))
                if segment.get('start', 0) >= segment.get('end', 0): continue # Bỏ qua nếu time không hợp lệ
                f.write(f"{count}\n{start_time} --> {end_time}\n{text}\n\n")
                count += 1

    def save_as_vtt(self, filepath):
        """Lưu segments thành tệp WebVTT."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("WEBVTT\n\n")
            for segment in self.segments:
                text = segment.get('text', '').strip()
                if not text: continue
                start_time = self.format_time_vtt(segment.get('start', 0))
                end_time = self.format_time_vtt(segment.get('end', 0))
                if segment.get('start', 0) >= segment.get('end', 0): continue
                f.write(f"{start_time} --> {end_time}\n{text}\n\n")

    def save_as_json(self, filepath):
        """Lưu segments thành tệp JSON."""
        try:
            serializable_segments = [{'start': s.get('start',0), 'end':s.get('end',0), 'text':s.get('text','')} for s in self.segments]
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(serializable_segments, f, indent=2, ensure_ascii=False)
        except TypeError as e: raise TypeError(f"Data non-serializable: {e}")
        except Exception as e: raise e

    def format_time_srt(self, seconds):
        """Định dạng thời gian SRT: HH:MM:SS,mmm"""
        if not isinstance(seconds, (int, float)) or seconds < 0: seconds = 0
        millis = round(seconds * 1000)
        secs, millis = divmod(millis, 1000)
        mins, secs = divmod(secs, 60)
        hours, mins = divmod(mins, 60)
        return f"{int(hours):02d}:{int(mins):02d}:{int(secs):02d},{int(millis):03d}"

    def format_time_vtt(self, seconds):
        """Định dạng thời gian WebVTT: HH:MM:SS.mmm"""
        if not isinstance(seconds, (int, float)) or seconds < 0: seconds = 0
        millis = round(seconds * 1000)
        secs, millis = divmod(millis, 1000)
        mins, secs = divmod(secs, 60)
        hours, mins = divmod(mins, 60)
        return f"{int(hours):02d}:{int(mins):02d}:{int(secs):02d}.{int(millis):03d}"

    def closeEvent(self, event):
        """Dọn dẹp khi đóng cửa sổ."""
        print("INFO: Close event called. Cleaning up...")
        self.media_player.stop()
        if self.subtitle_timer.isActive(): self.subtitle_timer.stop()

        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            print("INFO: Stopping worker thread...")
            self.worker_thread.quit()
            if not self.worker_thread.wait(3000):
                print("WARNING: Worker thread termination required.")
                self.worker_thread.terminate()
                self.worker_thread.wait()
            else: print("INFO: Worker thread finished.")
        elif hasattr(self, 'worker_thread'): print("INFO: Worker thread not running.")

        try:
            if self.temp_dir and os.path.exists(self.temp_dir):
                 print(f"INFO: Removing temporary directory: {self.temp_dir}")
                 shutil.rmtree(self.temp_dir, ignore_errors=True)
                 self.temp_dir = None
        except Exception as e: print(f"WARNING: Could not remove temp dir {self.temp_dir}: {e}")

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