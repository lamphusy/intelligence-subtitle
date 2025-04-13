import sys
import os
import tempfile
import json
import shutil
import time # Import time cho dummy worker
import logging

# Configure logging to suppress AV1 warnings
logging.basicConfig(level=logging.ERROR)
os.environ["QT_LOGGING_RULES"] = "qt.qml.connections=false;*.debug=false;*.info=false"

# --- PySide6 Imports ---
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QFileDialog, QMessageBox, QApplication, QSlider, QStyle,
                             QProgressBar, QGraphicsDropShadowEffect) # Giữ lại nếu muốn thử
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput # Cần QAudioOutput
from PySide6.QtCore import QUrl, QTimer, Qt, QThread, Signal, QRect
from PySide6.QtGui import QFont, QPalette, QColor, QFontMetrics, QPainter, QPen # Thêm QPen

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
        transcription_progress = Signal(str)
        transcription_complete = Signal(list)
        transcription_error = Signal(str)

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

                # More comprehensive test subtitles at shorter intervals for better debugging
                dummy_segments = [
                    {'start': 1.0, 'end': 5.0, 'text': 'PHỤ ĐỀ TEST 1: Đây là phụ đề thử nghiệm.'},
                    {'start': 6.0, 'end': 10.0, 'text': 'PHỤ ĐỀ TEST 2: Đây là một phụ đề thử nghiệm khác.'},
                    {'start': 11.0, 'end': 15.0, 'text': 'PHỤ ĐỀ TEST 3: Đây là phụ đề thử nghiệm thứ ba.'},
                    {'start': 16.0, 'end': 20.0, 'text': 'PHỤ ĐỀ TEST 4: Phụ đề này nên hiển thị được.'},
                    {'start': 21.0, 'end': 25.0, 'text': 'PHỤ ĐỀ TEST 5: Đây là phụ đề thử nghiệm thứ năm.'},
                    {'start': 26.0, 'end': 30.0, 'text': 'PHỤ ĐỀ DÀI: Đây là một phụ đề thử nghiệm dài hơn nhiều, nó nên tự động xuống dòng để kiểm tra hành vi xuống dòng của hệ thống phụ đề trong PySide6.'}
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
        # Cần trả về định dạng giống như worker thật nếu bạn muốn test save
        return [ {'start': 1.0, 'end': 5.0, 'text': 'Dummy Subtitle'}]
# --- Kết thúc phần giả lập ---

class VideoPlayer(QWidget):
    process_video_signal = Signal(str)
    SUBTITLE_LR_MARGIN = 20
    SUBTITLE_BOTTOM_MARGIN = 30 # Khoảng cách từ đáy video lên đáy phụ đề
    SUBTITLE_FONT_SIZE = 24     # Giảm cỡ chữ một chút
    SUBTITLE_TIMER_INTERVAL = 50 # ms

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Intelligent Subtitle - Speech to Text with Whisper")
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        # Create a wrapper widget to contain both video and subtitles
        self.video_wrapper = QWidget()
        self.video_wrapper_layout = QVBoxLayout(self.video_wrapper)
        self.video_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        self.video_wrapper_layout.setSpacing(0)
        
        # Video widget setup
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(640, 360)
        self.video_widget.setAutoFillBackground(True)
        
        # Add video to the wrapper
        self.video_wrapper_layout.addWidget(self.video_widget, 1)
        
        # Create subtitle label with maximum visibility
        self.subtitle_label = QLabel()
        self.subtitle_label.setStyleSheet(f"""
            QLabel {{
                color: white; /* Giữ màu chữ trắng (hoặc đổi màu khác nếu muốn) */
                font-size: {self.SUBTITLE_FONT_SIZE}px;
                font-weight: bold;
                /* XÓA BỎ các dòng sau: */
                /* background-color: rgba(0, 0, 0, 0.9); */
                /* border: 2px solid white; */
                /* border-radius: 8px; */
                /* Có thể giữ lại padding nếu muốn có khoảng trống quanh chữ, */
                /* hoặc xóa luôn nếu muốn chữ sát lề hơn */
                padding: 5px; /* Giảm padding hoặc xóa dòng này */
            }}
        """)
        
        # Apply shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 255))
        shadow.setOffset(2, 2)
        self.subtitle_label.setGraphicsEffect(shadow)
        
        # Configure subtitle properties
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        
        # Add a spacer in the wrapper layout to push subtitle to bottom
        self.video_wrapper_layout.addStretch(1)
        # Add subtitle label at the bottom of the wrapper
        self.video_wrapper_layout.addWidget(self.subtitle_label)
        
        # Add the wrapper to the main layout
        self.layout.addWidget(self.video_wrapper, 1)

        # Create MediaPlayer with proper audio output for PySide6
        try:
            # PySide6 requires explicit audio output
            from PySide6.QtMultimedia import QAudioOutput
            self.audio_output = QAudioOutput()
            self.media_player = QMediaPlayer()
            self.media_player.setAudioOutput(self.audio_output) 
            self.media_player.setVideoOutput(self.video_widget)
            # Set audio volume to 70%
            self.audio_output.setVolume(0.7)
        except ImportError:
            # Fallback for older versions
            self.media_player = QMediaPlayer()
            self.media_player.setVideoOutput(self.video_widget)
        
        # Progress bar and controls
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

        # Add all widgets to main layout
        self.layout.addWidget(self.video_wrapper, 1)
        self.layout.addWidget(self.progress_bar)
        self.layout.addLayout(self.controls_layout)
        self.setLayout(self.layout)

        # Kết nối tín hiệu
        self.media_player.errorOccurred.connect(self.handle_error)
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.media_player.playbackStateChanged.connect(self.state_changed)
        self.media_player.mediaStatusChanged.connect(self.media_status_changed)

        # --- Các biến trạng thái ---
        self.segments = []
        self.current_segment_index = -1
        self.next_segment_index = 0
        self.temp_dir = tempfile.mkdtemp(prefix="subtitle_app_")
        print(f"INFO: Temp directory created: {self.temp_dir}")
        self.video_path = ""
        self.subtitle_timer = QTimer(self)
        self.subtitle_timer.setInterval(self.SUBTITLE_TIMER_INTERVAL)
        self.subtitle_timer.timeout.connect(self.update_subtitle_display)

        # --- Thiết lập luồng worker ---
        self.setup_worker_thread()
        self.open_btn.clicked.connect(self.open_video_dialog)

    def setup_worker_thread(self):
        """Khởi tạo và cấu hình luồng worker."""
        self.worker_thread = QThread(self)
        self.transcription_worker = TranscriptionWorker()
        self.transcription_worker.moveToThread(self.worker_thread)
        # Kết nối tín hiệu từ worker
        self.transcription_worker.transcription_progress.connect(self.on_transcription_progress)
        self.transcription_worker.transcription_complete.connect(self.on_transcription_complete)
        self.transcription_worker.transcription_error.connect(self.on_transcription_error)
        # Kết nối tín hiệu để bắt đầu xử lý
        self.process_video_signal.connect(self.transcription_worker.process_video)
        # Dọn dẹp khi luồng kết thúc
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        # Không cần deleteLater cho worker nếu nó không phải QObject
        # self.transcription_worker.finished.connect(self.transcription_worker.deleteLater)
        self.worker_thread.start()
        print("INFO: Worker thread started.")

    def resizeEvent(self, event):
        """Handle window resize events to ensure subtitle is properly positioned."""
        super().resizeEvent(event)
        QTimer.singleShot(0, self.position_subtitle_label)

    def showEvent(self, event):
        """Called when the widget is shown."""
        super().showEvent(event)
        QTimer.singleShot(100, self.position_subtitle_label)

    def position_subtitle_label(self):
        """Position subtitles at the bottom of the video display area"""
        # In our layout-based approach, we don't need to manually position the label
        # as it's already positioned by the wrapper layout at the bottom
        
        # However, we should ensure it's visible and has the right size
        video_width = self.video_widget.width()
        if video_width < 100:
            video_width = self.video_wrapper.width()
        
        # Calculate optimal label width (with margins)
        label_width = video_width - (2 * self.SUBTITLE_LR_MARGIN)
        if label_width < 200: 
            label_width = 200
        
        # Set minimum and maximum width for the subtitle label
        self.subtitle_label.setMinimumWidth(label_width)
        self.subtitle_label.setMaximumWidth(label_width)
        
        # Ensure it's visible and on top    
        self.subtitle_label.raise_()
        
        print(f"DEBUG: Subtitle sized to width: {label_width}px")

    def set_subtitle_text(self, text):
        """Đặt nội dung cho label phụ đề và cập nhật hiển thị."""
        new_text_trimmed = text.strip() if text else ""

        # Chỉ cập nhật nếu text thực sự thay đổi để tránh tính toán lại không cần thiết
        # if self.subtitle_label.text() == new_text_trimmed and self.subtitle_label.isVisible() == bool(new_text_trimmed):
        #     return

        self.subtitle_label.setText(new_text_trimmed)

        # Nếu có text mới, định vị lại và hiển thị
        if new_text_trimmed:
            # print(f"DEBUG: Setting subtitle text: '{new_text_trimmed}'")
            self.position_subtitle_label() # Tính toán vị trí/kích thước MỚI
            if not self.subtitle_label.isVisible():
                self.subtitle_label.show()
            self.subtitle_label.raise_() # Đảm bảo luôn ở trên cùng
            self.subtitle_label.update() # Yêu cầu vẽ lại nếu cần
        else:
            # Nếu không có text, ẩn đi
            if self.subtitle_label.isVisible():
                # print("DEBUG: Hiding subtitle label (empty text).")
                self.subtitle_label.hide()

    def open_video_dialog(self):
        """Mở hộp thoại chọn tệp video."""
        file_dialog = QFileDialog(self)
        # Sử dụng getOpenFileUrl để lấy QUrl trực tiếp, tốt hơn cho QMediaPlayer
        video_url, _ = file_dialog.getOpenFileUrl(self, "Open Video", QUrl(),
                                                  "Video Files (*.mp4 *.avi *.mkv *.mov *.wmv);;All Files (*)")
        if video_url.isValid() and video_url.isLocalFile():
            self.load_video(video_url.toLocalFile()) # Chuyển về path string để dùng trong worker
        elif video_url.isValid():
             QMessageBox.warning(self, "Unsupported", "Only local video files are currently supported.")

    def load_video(self, video_path):
        """Tải video mới, đặt lại trạng thái và bắt đầu gỡ băng."""
        self.video_path = video_path
        print(f"INFO: Loading video: {self.video_path}")
        if not os.path.exists(video_path):
            QMessageBox.critical(self, "Error", f"Video file not found:\n{video_path}")
            return

        # Dừng player và reset trạng thái
        self.media_player.stop()
        self.segments = []
        self.current_segment_index = -1
        self.next_segment_index = 0
        self.save_subtitle_btn.setEnabled(False)
        self.set_subtitle_text("") # Xóa phụ đề cũ
        if self.subtitle_timer.isActive(): self.subtitle_timer.stop()
        self.play_pause_btn.setEnabled(False) # Vô hiệu hóa nút play cho đến khi media sẵn sàng
        self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.position_slider.setValue(0)
        self.position_slider.setEnabled(False) # Vô hiệu hóa slider
        self.duration_label.setText("00:00 / 00:00")

        # Đặt nguồn media
        url = QUrl.fromLocalFile(video_path)
        self.media_player.setSource(url) # Đặt nguồn cho player

        # Hiển thị thanh tiến trình và bắt đầu gỡ băng
        self.progress_bar.setVisible(True)
        self.set_subtitle_text("Loading video & starting transcription...")
        # Đợi một chút để UI cập nhật trước khi bắt đầu tác vụ nặng
        QTimer.singleShot(100, lambda: self.process_video_signal.emit(self.video_path))
        print("INFO: Emitted process_video_signal for:", video_path)

    def media_status_changed(self, status):
        """Xử lý thay đổi trạng thái của media."""
        # print(f"DEBUG: Media Status Changed: {status}")
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            print("INFO: Media Loaded.")
            self.play_pause_btn.setEnabled(True) # Kích hoạt nút play/pause
            self.position_slider.setEnabled(True) # Kích hoạt slider
            # Định vị lại phụ đề phòng trường hợp kích thước video thay đổi
            QTimer.singleShot(0, self.position_subtitle_label)
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
             print("INFO: End Of Media.")
             # Quay về đầu và dừng
             self.media_player.setPosition(0)
             # Không tự động pause, để state_changed xử lý icon
             # self.media_player.pause()
             self.set_subtitle_text("") # Xóa phụ đề cuối
             self.current_segment_index = -1
             self.next_segment_index = 0
             if self.subtitle_timer.isActive(): self.subtitle_timer.stop()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            print("ERROR: Invalid Media.")
            # Kích hoạt xử lý lỗi cụ thể
            self.handle_error(QMediaPlayer.MediaError.FormatError, "Invalid or unsupported media format.")
        elif status == QMediaPlayer.MediaStatus.LoadingMedia:
            print("INFO: Media Loading...")
            # Vô hiệu hóa điều khiển trong khi tải
            self.play_pause_btn.setEnabled(False)
            self.position_slider.setEnabled(False)
        elif status == QMediaPlayer.MediaStatus.NoMedia:
            print("INFO: No Media.")
            # Vô hiệu hóa điều khiển
            self.play_pause_btn.setEnabled(False)
            self.position_slider.setEnabled(False)
            self.position_slider.setValue(0)
            self.duration_label.setText("00:00 / 00:00")
            self.set_subtitle_text("")
            self.save_subtitle_btn.setEnabled(False)
        # Các trạng thái khác như Buffering, Buffered có thể được xử lý nếu cần

    def on_transcription_progress(self, message):
        """Cập nhật thông báo tiến trình gỡ băng."""
        # Chỉ hiển thị thông báo tiến trình nếu video không đang phát
        # hoặc nếu label phụ đề đang không hiển thị phụ đề thật
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
             print(f"INFO: Transcription Progress: {message}")
             self.set_subtitle_text(message)

    def on_transcription_complete(self, segments):
        """Xử lý khi gỡ băng hoàn tất."""
        print(f"INFO: Transcription Complete. Received {len(segments)} segments.")
        self.segments = segments if segments else []
        self.current_segment_index = -1 # Reset chỉ số
        self.next_segment_index = 0
        self.save_subtitle_btn.setEnabled(bool(self.segments)) # Kích hoạt nút lưu nếu có segment
        self.progress_bar.setVisible(False) # Ẩn thanh tiến trình

        # Hiển thị thông báo hoàn thành nếu không đang phát
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
             completion_msg = "Transcription complete!" if self.segments else "Transcription complete (no subtitles found)."
             self.set_subtitle_text(completion_msg + " Press play.")
             # Tự động xóa thông báo sau vài giây nếu không phát
             QTimer.singleShot(4000, self.clear_info_message_if_not_playing)
        else:
             # Nếu đang phát và có segments, bắt đầu hiển thị phụ đề
             if self.segments:
                 print("INFO: Transcription complete while playing, updating display.")
                 self.update_subtitle_display() # Cập nhật ngay lập tức
                 if not self.subtitle_timer.isActive():
                      self.subtitle_timer.start() # Bắt đầu timer nếu chưa chạy

    def clear_info_message_if_not_playing(self):
        """Xóa các thông báo trạng thái nếu video không đang phát."""
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            current_msg = self.subtitle_label.text()
            # Các thông báo cần xóa
            info_msgs = ["Transcription complete", "Loading video", "Error in transcription", "Press play"]
            if any(msg in current_msg for msg in info_msgs):
                 print("INFO: Clearing info message.")
                 self.set_subtitle_text("") # Xóa nội dung label

    def on_transcription_error(self, error_message):
        """Xử lý khi có lỗi trong quá trình gỡ băng."""
        print(f"ERROR: Transcription Error: {error_message}")
        self.progress_bar.setVisible(False) # Ẩn thanh tiến trình
        QMessageBox.critical(self, "Transcription Error", f"Failed to transcribe audio:\n{error_message}")
        self.set_subtitle_text("Error in transcription.") # Hiển thị lỗi
        # Tự động xóa thông báo lỗi sau vài giây nếu không phát
        QTimer.singleShot(5000, self.clear_info_message_if_not_playing)

    def toggle_play_pause(self):
        """Chuyển đổi giữa trạng thái phát và tạm dừng."""
        if not self.play_pause_btn.isEnabled(): return # Không làm gì nếu nút bị vô hiệu hóa
        current_state = self.media_player.playbackState()
        if current_state == QMediaPlayer.PlaybackState.PlayingState:
            print("INFO: Pausing media.")
            self.media_player.pause()
        elif current_state == QMediaPlayer.PlaybackState.PausedState or current_state == QMediaPlayer.PlaybackState.StoppedState:
            print("INFO: Playing media.")
            self.media_player.play()
            # Khi bắt đầu phát, đảm bảo xóa các thông báo thông tin cũ
            self.clear_info_message_if_not_playing()

    def state_changed(self, state):
        """Xử lý thay đổi trạng thái của media player."""
        # print(f"DEBUG: Playback State Changed: {state}")
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            # Nếu có phụ đề và timer chưa chạy, khởi động nó
            if self.segments and not self.subtitle_timer.isActive():
                print("INFO: Player playing, starting subtitle timer.")
                self.update_subtitle_display() # Cập nhật hiển thị ngay
                self.subtitle_timer.start()
            # Xóa thông báo khi bắt đầu phát
            self.clear_info_message_if_not_playing()

        else: # Trạng thái Paused hoặc Stopped
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            # Dừng timer nếu đang chạy
            if self.subtitle_timer.isActive():
                print("INFO: Player not playing, stopping subtitle timer.")
                self.subtitle_timer.stop()

    def update_subtitle_display(self):
        """Cập nhật hiển thị phụ đề dựa trên thời gian hiện tại."""
        # Dừng nếu không có segment hoặc player không chạy
        if not self.segments or self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            # Đảm bảo timer dừng nếu player không chạy
            if self.subtitle_timer.isActive() and self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                 self.subtitle_timer.stop()
                 # print("DEBUG: Timer stopped because player is not playing.")
            # Nếu không có segment và đang phát, xóa text
            if not self.segments and self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                 self.set_subtitle_text("")
            return

        current_time_ms = self.media_player.position()
        current_time_sec = current_time_ms / 1000.0
        # print(f"DEBUG: update_subtitle_display at {current_time_sec:.2f}s")

        # Tối ưu hóa: Kiểm tra segment tiếp theo trước
        text_to_display = ""
        found_current = False

        # Kiểm tra xem segment tiếp theo có nên bắt đầu chưa
        if self.next_segment_index < len(self.segments):
            next_seg = self.segments[self.next_segment_index]
            if current_time_sec >= next_seg.get('start', float('inf')):
                # print(f"DEBUG: Switching to next segment {self.next_segment_index}")
                self.current_segment_index = self.next_segment_index
                self.next_segment_index += 1
                text_to_display = next_seg.get('text', '').strip()
                found_current = True

        # Nếu không chuyển sang segment mới, kiểm tra segment hiện tại có còn hợp lệ không
        if not found_current and self.current_segment_index >= 0:
            current_seg = self.segments[self.current_segment_index]
            if current_time_sec < current_seg.get('end', 0):
                # Vẫn trong segment hiện tại
                text_to_display = current_seg.get('text', '').strip()
                found_current = True
            else:
                # Segment hiện tại đã kết thúc, không tìm thấy segment mới -> xóa text
                # print(f"DEBUG: Current segment {self.current_segment_index} ended.")
                self.current_segment_index = -1 # Đánh dấu không còn segment hiện tại
                text_to_display = ""
        elif not found_current:
             # Không có segment hiện tại và chưa đến lúc cho segment tiếp theo
             text_to_display = ""


        # --- Gỡ lỗi hiển thị ---
        # Bỏ comment dòng dưới để luôn thấy thời gian và trạng thái
        # debug_text = f"T:{current_time_sec:.1f}s | Curr:{self.current_segment_index} | Next:{self.next_segment_index} | Text: {text_to_display}"
        # self.set_subtitle_text(debug_text)
        # --- Kết thúc gỡ lỗi ---

        # Chỉ đặt text nếu tìm thấy segment hoặc cần xóa text cũ
        # (Tránh gọi set_subtitle_text liên tục nếu không có gì thay đổi)
        if self.subtitle_label.text() != text_to_display:
            self.set_subtitle_text(text_to_display)

    def position_changed(self, position):
        """Cập nhật vị trí slider khi media player thay đổi vị trí."""
        # Chỉ cập nhật slider nếu người dùng không đang kéo nó
        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(position)
        # Cập nhật nhãn thời gian
        self.update_duration_label(position, self.media_player.duration())

    def duration_changed(self, duration):
        """Cập nhật khoảng giá trị của slider khi thời lượng media thay đổi."""
        print(f"INFO: Duration changed: {duration} ms")
        self.position_slider.setRange(0, duration)
        # Kích hoạt slider nếu thời lượng hợp lệ
        self.position_slider.setEnabled(duration > 0)
        # Cập nhật nhãn thời gian
        self.update_duration_label(self.media_player.position(), duration)

    def set_position(self, position):
        """Di chuyển vị trí phát media player khi người dùng kéo slider."""
        # print(f"DEBUG: User set position to {position} ms")
        self.media_player.setPosition(position)
        # Cập nhật lại hiển thị phụ đề ngay lập tức sau khi seek
        if self.segments:
            current_time_sec = position / 1000.0
            self.update_segment_indices(current_time_sec) # Tìm index mới
            current_text = self.get_current_subtitle_text(current_time_sec) # Lấy text tại vị trí mới
            self.set_subtitle_text(current_text) # Hiển thị text đó

    def update_segment_indices(self, current_time_sec):
        """Cập nhật index phụ đề (current và next) sau khi seek."""
        # print(f"DEBUG: Updating segment indices for time {current_time_sec:.2f}s")
        self.current_segment_index = -1
        self.next_segment_index = 0 # Mặc định là segment đầu tiên
        if not self.segments: return # Không có gì để làm

        found_next = False
        for i, segment in enumerate(self.segments):
            start = segment.get('start', -1)
            end = segment.get('end', -1)

            # Tìm segment hiện tại (nếu có)
            if start <= current_time_sec < end:
                self.current_segment_index = i
                self.next_segment_index = i + 1
                found_next = True # Đã tìm thấy cả next
                # print(f"DEBUG: Found current segment {i} for time {current_time_sec:.2f}")
                break # Tìm thấy segment hiện tại là đủ

            # Nếu chưa tìm thấy next và thời gian hiện tại nhỏ hơn start của segment này
            # thì đây chính là segment tiếp theo
            elif not found_next and current_time_sec < start:
                 self.next_segment_index = i
                 found_next = True
                 # print(f"DEBUG: Found next segment {i} for time {current_time_sec:.2f}")
                 # Không break ở đây vì có thể thời gian nằm trong segment sau đó

        # Nếu duyệt hết mà không tìm thấy next (nghĩa là thời gian ở sau segment cuối)
        if not found_next:
             self.next_segment_index = len(self.segments)
             # Nếu thời gian nằm sau hoặc bằng start của segment cuối, đặt nó là current
             if len(self.segments) > 0 and current_time_sec >= self.segments[-1].get('start', float('inf')):
                  self.current_segment_index = len(self.segments) -1
             # print(f"DEBUG: Time is after last segment. Next index: {self.next_segment_index}")

        # print(f"DEBUG: Indices updated - Current: {self.current_segment_index}, Next: {self.next_segment_index}")


    def get_current_subtitle_text(self, current_time_sec):
        """Lấy text phụ đề chính xác cho thời điểm cụ thể (sau khi seek)."""
        # Tối ưu: chỉ cần kiểm tra segment tại self.current_segment_index nếu nó hợp lệ
        if self.current_segment_index >= 0 and self.current_segment_index < len(self.segments):
             segment = self.segments[self.current_segment_index]
             # Kiểm tra lại lần nữa cho chắc chắn (mặc dù update_segment_indices đã làm)
             if segment.get('start', -1) <= current_time_sec < segment.get('end', -1):
                 return segment.get('text', '').strip()

        # Nếu index không hợp lệ hoặc thời gian không khớp (hiếm khi xảy ra sau update_segment_indices),
        # thì trả về chuỗi rỗng. Không cần lặp lại toàn bộ list ở đây.
        return ""


    def update_duration_label(self, position, duration):
        """Cập nhật label hiển thị thời gian."""
        if duration < 0: duration = 0 # Đảm bảo không âm
        if position < 0: position = 0
        if position > duration: position = duration # Không vượt quá thời lượng

        pos_sec_total = position // 1000
        dur_sec_total = duration // 1000
        pos_min, pos_sec = divmod(pos_sec_total, 60)
        dur_min, dur_sec = divmod(dur_sec_total, 60)
        self.duration_label.setText(f"{pos_min:02d}:{pos_sec:02d} / {dur_min:02d}:{dur_sec:02d}")

    def handle_error(self, error_code, specific_message=""): # Chấp nhận thông báo lỗi cụ thể
        """Xử lý lỗi từ QMediaPlayer."""
        # Lấy thông báo lỗi từ player nếu có
        error_string = self.media_player.errorString()
        print(f"ERROR: Media Player Error - Code: {error_code}, String: '{error_string}', Specific: '{specific_message}'")

        # Ưu tiên thông báo lỗi cụ thể được truyền vào (ví dụ từ media_status_changed)
        display_message = specific_message

        # Nếu không có thông báo cụ thể, thử lấy từ player
        if not display_message and error_string:
            display_message = error_string
        # Nếu vẫn không có, dùng map lỗi cơ bản
        elif not display_message:
            error_map = {
                QMediaPlayer.MediaError.ResourceError: "Cannot load resource.",
                QMediaPlayer.MediaError.FormatError: "Unsupported media format.",
                QMediaPlayer.MediaError.NetworkError: "Network error.",
                QMediaPlayer.MediaError.AccessDeniedError: "Access denied.",
                QMediaPlayer.MediaError.ServiceMissingError: "Media service missing.", # Thêm lỗi này
                QMediaPlayer.MediaError.MediaIsPlaylist: "Media is a playlist (not supported)." # Thêm lỗi này
            }
            display_message = error_map.get(error_code, f"Unknown error (Code: {error_code})")

        QMessageBox.critical(self, "Media Player Error", display_message)

        # Reset UI về trạng thái không có media
        self.play_pause_btn.setEnabled(False)
        self.position_slider.setEnabled(False)
        self.position_slider.setValue(0)
        self.duration_label.setText("00:00 / 00:00")
        self.set_subtitle_text("")
        self.progress_bar.setVisible(False)
        self.save_subtitle_btn.setEnabled(False)
        self.segments = []
        if self.subtitle_timer.isActive(): self.subtitle_timer.stop()


    # --- Các hàm lưu phụ đề (save_subtitles, save_as_srt, save_as_vtt, save_as_json) ---
    # --- và các hàm định dạng thời gian (format_time_srt, format_time_vtt) ---
    # --- Giữ nguyên như trong code gốc của bạn, đã khá tốt ---
    # --- (Copy và paste phần đó vào đây) ---
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
        # Sử dụng cú pháp filter chuẩn hơn của PySide6
        filters = "SubRip Subtitles (*.srt);;WebVTT (*.vtt);;JSON (*.json);;All Files (*)"
        save_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Save Subtitles As...", default_filename, filters, options=options)

        if not save_path: return

        print(f"INFO: Saving subtitles to: {save_path}")
        # Xác định định dạng dựa trên đuôi tệp hoặc bộ lọc đã chọn
        _, ext = os.path.splitext(save_path)
        ext = ext.lower()
        file_format = 'srt' # Mặc định
        if ext == '.vtt' or "(*.vtt)" in selected_filter: file_format = 'vtt'
        elif ext == '.json' or "(*.json)" in selected_filter: file_format = 'json'
        elif ext == '.srt' or "(*.srt)" in selected_filter: file_format = 'srt'
        else: # Nếu không có đuôi hoặc không khớp filter, thêm .srt
            if not ext:
                save_path += ".srt"
                print("INFO: No extension provided, saving as SRT.")
            else: # Nếu có đuôi lạ, vẫn lưu dạng SRT nhưng cảnh báo
                print(f"WARNING: Unknown extension '{ext}', saving as SRT format.")


        try:
            if file_format == 'srt': self.save_as_srt(save_path)
            elif file_format == 'vtt': self.save_as_vtt(save_path)
            elif file_format == 'json': self.save_as_json(save_path)

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
                start_time_sec = segment.get('start', -1)
                end_time_sec = segment.get('end', -1)
                # Chỉ lưu nếu thời gian hợp lệ và end > start
                if start_time_sec < 0 or end_time_sec <= start_time_sec: continue
                start_time = self.format_time_srt(start_time_sec)
                end_time = self.format_time_srt(end_time_sec)

                f.write(f"{count}\n{start_time} --> {end_time}\n{text}\n\n")
                count += 1
        print(f"INFO: Saved {count-1} segments to SRT: {filepath}")


    def save_as_vtt(self, filepath):
        """Lưu segments thành tệp WebVTT."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("WEBVTT\n\n")
            count = 0
            for segment in self.segments:
                text = segment.get('text', '').strip()
                if not text: continue
                start_time_sec = segment.get('start', -1)
                end_time_sec = segment.get('end', -1)
                if start_time_sec < 0 or end_time_sec <= start_time_sec: continue
                start_time = self.format_time_vtt(start_time_sec)
                end_time = self.format_time_vtt(end_time_sec)

                # VTT không bắt buộc có số thứ tự, nhưng có thể thêm comment nếu muốn
                # f.write(f"NOTE segment {count+1}\n")
                f.write(f"{start_time} --> {end_time}\n{text}\n\n")
                count += 1
        print(f"INFO: Saved {count} segments to VTT: {filepath}")


    def save_as_json(self, filepath):
        """Lưu segments thành tệp JSON."""
        # Lọc ra các segment hợp lệ trước khi lưu
        serializable_segments = []
        for segment in self.segments:
             start = segment.get('start', -1)
             end = segment.get('end', -1)
             text = segment.get('text', '').strip()
             if start >= 0 and end > start and text:
                 serializable_segments.append({'start': start, 'end': end, 'text': text})

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(serializable_segments, f, indent=2, ensure_ascii=False)
            print(f"INFO: Saved {len(serializable_segments)} segments to JSON: {filepath}")
        except TypeError as e:
            raise TypeError(f"Data non-serializable for JSON: {e}")
        except Exception as e:
            raise e

    def format_time_srt(self, seconds):
        """Định dạng thời gian SRT: HH:MM:SS,mmm"""
        if not isinstance(seconds, (int, float)) or seconds < 0: seconds = 0
        # Tránh lỗi làm tròn không mong muốn bằng cách làm việc với integer ms
        total_milliseconds = int(round(seconds * 1000))
        secs, milliseconds = divmod(total_milliseconds, 1000)
        mins, secs = divmod(secs, 60)
        hours, mins = divmod(mins, 60)
        return f"{hours:02d}:{mins:02d}:{secs:02d},{milliseconds:03d}"

    def format_time_vtt(self, seconds):
        """Định dạng thời gian WebVTT: HH:MM:SS.mmm"""
        if not isinstance(seconds, (int, float)) or seconds < 0: seconds = 0
        total_milliseconds = int(round(seconds * 1000))
        secs, milliseconds = divmod(total_milliseconds, 1000)
        mins, secs = divmod(secs, 60)
        hours, mins = divmod(mins, 60)
        return f"{hours:02d}:{mins:02d}:{secs:02d}.{milliseconds:03d}"
    # --- Kết thúc phần copy-paste ---


    def closeEvent(self, event):
        """Dọn dẹp khi đóng cửa sổ."""
        print("INFO: Close event called. Cleaning up...")
        self.media_player.stop() # Dừng media player
        if self.subtitle_timer.isActive(): self.subtitle_timer.stop() # Dừng timer

        # Dừng luồng worker một cách an toàn
        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            print("INFO: Requesting worker thread to quit...")
            self.worker_thread.quit() # Yêu cầu luồng thoát vòng lặp sự kiện
            # Đợi luồng kết thúc, với timeout
            if not self.worker_thread.wait(3000): # Chờ tối đa 3 giây
                print("WARNING: Worker thread did not finish gracefully. Terminating...")
                self.worker_thread.terminate() # Buộc dừng nếu không phản hồi
                self.worker_thread.wait() # Đợi sau khi terminate
            else:
                print("INFO: Worker thread finished.")
        elif hasattr(self, 'worker_thread'):
            print("INFO: Worker thread was not running.")

        # Xóa thư mục tạm
        try:
            if self.temp_dir and os.path.exists(self.temp_dir):
                 print(f"INFO: Removing temporary directory: {self.temp_dir}")
                 # ignore_errors=True để tránh crash nếu xóa thất bại
                 shutil.rmtree(self.temp_dir, ignore_errors=True)
                 self.temp_dir = None # Đánh dấu đã xóa
        except Exception as e:
            # Chỉ cảnh báo, không làm dừng ứng dụng
            print(f"WARNING: Could not remove temp dir {self.temp_dir}: {e}")

        # Chấp nhận sự kiện đóng
        event.accept()
        print("INFO: Window closed.")

# --- Main execution block ---
if __name__ == '__main__':
    # Nên đặt QApplication trước mọi thứ khác của Qt
    app = QApplication(sys.argv)

    player = VideoPlayer()
    player.setGeometry(100, 100, 900, 650) # Tăng kích thước cửa sổ một chút
    player.show()

    # Tự động load video test nếu có đường dẫn (thay đổi cho phù hợp)
    # Linux/macOS example:
    # test_video_path = "/path/to/your/sample_videos/demo.mp4"
    # Windows example:
    test_video_path = r"D:\Download\Video\Alicia Keys - If I Ain't Got You (Official HD Video).mp4" # Thêm 'r' cho raw string

    if os.path.exists(test_video_path):
        print(f"INFO: Auto-loading test video: {test_video_path}")
        player.load_video(test_video_path)
    else:
         print(f"INFO: Test video path not found: {test_video_path}")

    sys.exit(app.exec())