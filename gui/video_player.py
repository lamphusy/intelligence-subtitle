import sys
import os
import tempfile
import json
import shutil
import time
import vlc
import qtawesome as qta

# --- PyQt5 Imports ---
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QFileDialog, QMessageBox, QApplication, QSlider, QStyle,
                             QProgressBar, QFrame, QToolButton, QMenu, QAction)
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal, QRect, QUrl, QPropertyAnimation, QEasingCurve, QPoint, pyqtProperty, QSize
from PyQt5.QtGui import QFont, QFontMetrics, QPainter, QColor, QIcon, QCursor

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

class PlayPauseOverlay(QWidget):
    """Overlay widget for play/pause animation"""
    
    # Define the opacity property for Qt
    opacity = pyqtProperty(float, lambda self: self._opacity, lambda self, value: self.set_opacity(value))
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedSize(100, 100)
        self.move(parent.width()//2 - 50, parent.height()//2 - 50)
        self._opacity = 0.0
        self.is_play = True
        self.animation = QPropertyAnimation(self, b"opacity")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.finished.connect(self.hide)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw semi-transparent background
        painter.fillRect(self.rect(), QColor(0, 0, 0, int(150 * self._opacity)))
        
        # Draw play/pause icon
        painter.setPen(QColor(255, 255, 255, int(255 * self._opacity)))
        painter.setBrush(QColor(255, 255, 255, int(255 * self._opacity)))
        
        if self.is_play:
            # Draw play triangle
            points = [
                QPoint(40, 30),
                QPoint(40, 70),
                QPoint(70, 50)
            ]
            painter.drawPolygon(points)
        else:
            # Draw pause bars
            painter.drawRect(35, 30, 15, 40)
            painter.drawRect(55, 30, 15, 40)
            
    def show_play(self):
        """Show play icon with animation"""
        self.is_play = True
        self.show()
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.start()
        
    def show_pause(self):
        """Show pause icon with animation"""
        self.is_play = False
        self.show()
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.start()
        
    def set_opacity(self, value):
        """Set opacity value and trigger update"""
        self._opacity = float(value)
        self.update()

class VideoFrame(QFrame):
    """Custom QFrame for VLC video output"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self.setStyleSheet("background-color: black;")
        if sys.platform == "darwin":
            self.setAttribute(Qt.WA_DontCreateNativeAncestors)
            self.setAttribute(Qt.WA_NativeWindow)
            
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'play_pause_overlay'):
            self.play_pause_overlay.move(self.width()//2 - 50, self.height()//2 - 50)

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
        self.layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for fullscreen
        self.layout.setSpacing(0)
        
        # Create VLC instance with plugin options
        vlc_options = [
            "--no-video-title-show",
            "--no-audio-time-stretch",
            "--avcodec-hw=any",
            "--avcodec-fast",
            "--avcodec-skiploopfilter=all",
            "--avcodec-skip-frame=nonref",
            "--avcodec-skip-idct=nonref",
            "--no-sout-rtp-sap",
            "--no-sout-standard-sap",
            "--sout-keep",
            "--no-sout-audio",
            "--no-sout-video",
            "--sout-mux-caching=1000",
            "--network-caching=1000",
            "--file-caching=1000",
            "--live-caching=1000",
            "--disc-caching=1000",
            "--clock-synchro=0",
            "--clock-jitter=0"
        ]
        # On macOS, use macosx video output only to avoid converter recursion errors
        if sys.platform == "darwin":
            vlc_options.append("--vout=macosx")
        
        self.instance = vlc.Instance(vlc_options)
        self.mediaplayer = self.instance.media_player_new()
        
        # Create video widget
        self.video_widget = VideoFrame(self)
        
        # Create play/pause overlay
        self.video_widget.play_pause_overlay = PlayPauseOverlay(self.video_widget)
        self.video_widget.play_pause_overlay.hide()
        
        # Set mouse tracking for hover events
        self.video_widget.setMouseTracking(True)
        self.setMouseTracking(True)
        
        # Create controls container
        self.controls_container = QWidget(self)
        self.controls_container.setStyleSheet("background-color: #000000;")
        self.controls_container.hide()  # Initially hidden
        
        # Create controls layout
        self.controls_layout = QHBoxLayout()
        self.controls_layout.setContentsMargins(10, 5, 10, 5)
        
        # Define icon size for crisp icons
        icon_size = QSize(16, 16)  # use 16px for icons
        self.icon_size = icon_size  # store for use elsewhere
        # Determine device pixel ratio for crisp pixmaps
        self._dpr = self.devicePixelRatioF() if hasattr(self, 'devicePixelRatioF') else 1.0
        
        # Create controls with high-DPI icons
        self.open_btn = QPushButton("Open Video")
        # Load and set crisp icon
        button_size = QSize(int(self.icon_size.width() * self._dpr), int(self.icon_size.height() * self._dpr))
        raw = qta.icon('fa5s.folder-open', color='white')
        pix = raw.pixmap(QSize(int(self.icon_size.width()*self._dpr), int(self.icon_size.height()*self._dpr)))
        pix.setDevicePixelRatio(self._dpr)
        self.open_btn.setIcon(QIcon(pix))
        self.open_btn.setIconSize(self.icon_size)
        # Create play/pause icon using QLabel
        self.play_pause_icon = QLabel()
        play_size = QSize(int(self.icon_size.width() * self._dpr), int(self.icon_size.height() * self._dpr))
        play_pix = qta.icon('fa5s.play', color='white').pixmap(play_size)
        play_pix.setDevicePixelRatio(self._dpr)
        self.play_pause_icon.setFixedSize(self.icon_size)
        self.play_pause_icon.setPixmap(play_pix)
        self.play_pause_icon.setCursor(Qt.PointingHandCursor)
        self.play_pause_icon.mousePressEvent = lambda e: self.toggle_play_pause()
        self.play_pause_icon.setEnabled(False)
        # Create Slider Style
        slider_style_sheet = """
            QSlider::groove:horizontal {
                border: 1px solid #323232;
                height: 2px;
            }

            QSlider::handle:horizontal {
                background: #ca0100;
                border: 1px solid #ca0100;
                width: 10px;  
                margin: -5px -1px; 
                border-radius: 5px;
            }

            QSlider::add-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #323232, stop:1 #323232);
            }

            QSlider::sub-page:horizontal {
                background: #ca0100;
            }
        """
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setStyleSheet(slider_style_sheet)
        self.position_slider.setRange(0, 0)
        # Enable tracking for smooth updates while dragging
        self.position_slider.setTracking(True)
        # Connect signals
        self.position_slider.sliderMoved.connect(self.set_position)
        # Enable clicking anywhere on the slider
        self.position_slider.mousePressEvent = self.handle_slider_click
        self.duration_label = QLabel("00:00 / 00:00")
        self.duration_label.setFixedWidth(100)
        self.save_subtitle_btn = QPushButton("Save Subtitles")
        raw = qta.icon('fa5s.save', color='white')
        pix = raw.pixmap(QSize(int(self.icon_size.width()*self._dpr), int(self.icon_size.height()*self._dpr)))
        pix.setDevicePixelRatio(self._dpr)
        self.save_subtitle_btn.setIcon(QIcon(pix))
        self.save_subtitle_btn.setIconSize(self.icon_size)
        self.save_subtitle_btn.clicked.connect(self.save_subtitles)
        self.save_subtitle_btn.setEnabled(False)

        # Create fullscreen icon using QLabel
        self.fullscreen_icon = QLabel()
        fullscreen_size = QSize(int(self.icon_size.width() * self._dpr), int(self.icon_size.height() * self._dpr))
        fullscreen_pix = qta.icon('fa5s.expand', color='white').pixmap(fullscreen_size)
        fullscreen_pix.setDevicePixelRatio(self._dpr)
        self.fullscreen_icon.setFixedSize(self.icon_size)
        self.fullscreen_icon.setPixmap(fullscreen_pix)
        self.fullscreen_icon.setCursor(Qt.PointingHandCursor)
        self.fullscreen_icon.mousePressEvent = lambda event: self.toggle_fullscreen()

        # Create volume slider for audio control
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setStyleSheet(slider_style_sheet)
        self.volume_slider.setRange(0, 100)
        initial_vol = self.mediaplayer.audio_get_volume()
        if initial_vol < 0:
            initial_vol = 100
        self.volume_slider.setValue(initial_vol)
        # Store previous volume for mute/unmute toggling
        self._previous_volume = initial_vol
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.set_volume)

        # Create volume icon next to slider
        self.volume_icon = QLabel()
        vol_size = QSize(int(self.icon_size.width() * self._dpr), int(self.icon_size.height() * self._dpr))
        vol_pix = qta.icon('fa5s.volume-up', color='white').pixmap(vol_size)
        vol_pix.setDevicePixelRatio(self._dpr)
        self.volume_icon.setFixedSize(self.icon_size)
        self.volume_icon.setPixmap(vol_pix)
        # Make volume icon clickable to toggle mute/unmute
        self.volume_icon.setCursor(Qt.PointingHandCursor)
        self.volume_icon.mousePressEvent = self.toggle_mute_icon

        # Bottom controls (options menu, play/pause, slider, volume, fullscreen)
        self.options_lbl = QLabel(self)
        opt_size = QSize(int(self.icon_size.width() * self._dpr), int(self.icon_size.height() * self._dpr))
        opt_pix = qta.icon('fa5s.bars', color='white').pixmap(opt_size)
        opt_pix.setDevicePixelRatio(self._dpr)
        self.options_lbl.setFixedSize(self.icon_size)
        self.options_lbl.setPixmap(opt_pix)
        self.options_lbl.setCursor(Qt.PointingHandCursor)

        # Tạo menu ẩn
        option_menu_style_sheet = """
        QMenu {
        background-color: black;
        border: 1px solid white; /* reserve space for selection border */
        }
 
        QMenu::item {
        padding: 2px 20px 2px 20px;
        border: 1px solid transparent; /* reserve space for selection border */
        spacing: 20px;
        }
 
        QMenu::item:selected {
            border-color: darkblue;
            background: #a0a0a0;
            color:white;
        }
        """
        self.options_menu = QMenu(self)
        self.options_menu.setStyleSheet(option_menu_style_sheet)
        open_action = self.options_menu.addAction("Open Video")
        open_action.triggered.connect(self.open_video_dialog)
        save_action = self.options_menu.addAction("Save Subtitles")
        save_action.triggered.connect(self.save_subtitles)

        # Bắt sự kiện click để hiện menu
        def show_options(event):
            # Hiển thị menu phía trên nút options_lbl
            pos = self.options_lbl.mapToGlobal(QPoint(0, -self.options_menu.sizeHint().height()))
            self.options_menu.exec_(pos)

        self.options_lbl.mousePressEvent = show_options

        # Thêm vào layout
        self.controls_layout.addWidget(self.options_lbl)
        self.controls_layout.addWidget(self.play_pause_icon)
        self.controls_layout.addWidget(self.position_slider, 1)
        self.controls_layout.addWidget(self.duration_label)
        self.controls_layout.addWidget(self.volume_icon)
        self.controls_layout.addWidget(self.volume_slider)
        self.controls_layout.addWidget(self.fullscreen_icon)
        
        # Set controls layout to container
        self.controls_container.setLayout(self.controls_layout)
        
        # Add widgets to main layout
        self.layout.addWidget(self.video_widget, 1)
        self.layout.addWidget(self.controls_container)
        self.setLayout(self.layout)
        
        # Add progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(15)
        self.layout.addWidget(self.progress_bar)
        
        # Mouse tracking timer for controls
        self.mouse_timer = QTimer(self)
        self.mouse_timer.setInterval(2000)  # 2 seconds
        self.mouse_timer.timeout.connect(self.hide_controls)
        self.mouse_timer.setSingleShot(True)
        
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
                
                # Removed advanced VLC video configuration to avoid filter recursion errors
                # NOTE: Relying on default scaling and filter behavior
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
            
            # Add media options for better seeking
            media.add_option(":no-audio-time-stretch")
            media.add_option(":avcodec-hw=any")
            media.add_option(":avcodec-fast")
            media.add_option(":avcodec-skiploopfilter=all")
            media.add_option(":avcodec-skip-frame=nonref")
            media.add_option(":avcodec-skip-idct=nonref")
            media.add_option(":clock-synchro=0")
            media.add_option(":clock-jitter=0")
            
            # Parse media to get duration information sooner
            media.parse()
            
            # Set media to player
            self.mediaplayer.set_media(media)
            
            # Reset state
            self.segments = []
            self.current_segment_index = -1
            self.next_segment_index = 0
            self.save_subtitle_btn.setEnabled(False)
            self.play_pause_icon.setEnabled(True)
            # Set slider range to video duration in ms
            duration = self.mediaplayer.get_length()
            if duration > 0:
                self.position_slider.setRange(0, duration)
            else:
                self.position_slider.setRange(0, 0)
            self.position_slider.setEnabled(True)
            self.position_slider.setValue(0)
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
            self.play_pause_icon.setEnabled(False)
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
        """Toggle play/pause state"""
        if not self.play_pause_icon.isEnabled():
            return
            
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.video_widget.play_pause_overlay.show_play()
            self.update_play_pause_icon(False)
        else:
            if self.mediaplayer.get_media() is None:
                QMessageBox.warning(self, "Warning", "No video loaded.")
                return
                
            if self.mediaplayer.play() == -1:
                QMessageBox.critical(self, "Error", "Unable to play video")
                return
            self.video_widget.play_pause_overlay.show_pause()
            self.timer.start()
            self.update_play_pause_icon(True)

    def update_play_pause_icon(self, is_playing):
        """Update play/pause icon based on playing state"""
        icon_name = 'fa5s.pause' if is_playing else 'fa5s.play'
        raw = qta.icon(icon_name, color='white')
        pix = raw.pixmap(QSize(int(self.icon_size.width() * self._dpr), int(self.icon_size.height() * self._dpr)))
        pix.setDevicePixelRatio(self._dpr)
        self.play_pause_icon.setPixmap(pix)

    def set_position(self, position):
        """Di chuyển vị trí phát media player."""
        try:
            # Validate position is within valid range
            if position < 0:
                position = 0
            duration = self.mediaplayer.get_length()
            if duration > 0 and position > duration:
                position = duration
                
            # Convert position to integer and ensure it's not too large
            position = int(position)
            if position > 2**31 - 1:  # Maximum 32-bit signed integer
                position = 2**31 - 1
                
            # Seek to the specified playback time in milliseconds
            result = self.mediaplayer.set_time(position)
            if result == -1:
                print(f"WARNING: Seeking to position {position} failed")
        except Exception as e:
            print(f"ERROR: Failed to seek to position {position}: {e}")

    def set_volume(self, value):
        """Set VLC audio volume."""
        self.mediaplayer.audio_set_volume(value)

    def toggle_mute_icon(self, event):
        """Toggle mute/unmute and update volume icon."""
        current_mute = bool(self.mediaplayer.audio_get_mute())
        new_mute = not current_mute
        if new_mute:
            # Muting: save current volume and set slider to 0
            self._previous_volume = self.volume_slider.value()
            self.volume_slider.setValue(0)
        else:
            # Unmuting: restore previous volume
            restored = getattr(self, '_previous_volume', 100)
            self.volume_slider.setValue(restored)
        # Update mute state and icon
        self.mediaplayer.audio_set_mute(new_mute)
        # Create high-DPI pixmap for updated volume icon
        pix_size = QSize(int(self.icon_size.width() * self._dpr), int(self.icon_size.height() * self._dpr))
        icon_name = 'fa5s.volume-mute' if new_mute else 'fa5s.volume-up'
        icon_pix = qta.icon(icon_name, color='white').pixmap(pix_size)
        icon_pix.setDevicePixelRatio(self._dpr)
        self.volume_icon.setPixmap(icon_pix)

    def update_ui(self):
        """Cập nhật giao diện người dùng."""
        # Get current playback time and total duration in ms
        position = self.mediaplayer.get_time()
        duration = self.mediaplayer.get_length()
        if duration > 0:
            # Adjust slider range if necessary
            if self.position_slider.maximum() != duration:
                self.position_slider.setRange(0, duration)
            # Update slider position and duration label
            self.position_slider.setValue(position)
            self.update_duration_label(position, duration)

        # Update play/pause icon based on playing state
        self.update_play_pause_icon(self.mediaplayer.is_playing())

        # Stop timer if playback paused or ended
        if not self.mediaplayer.is_playing():
            self.timer.stop()

    def update_duration_label(self, position, duration):
        """Cập nhật label hiển thị thời gian."""
        if duration <= 0:
            self.duration_label.setText("--:-- / --:--")
            return
        # Ensure calculations result in integers for formatting
        pos_sec_total = int(position // 1000)
        dur_sec_total = int(duration // 1000)
        # Compute hours, minutes, seconds
        pos_hours, pos_rem = divmod(pos_sec_total, 3600)
        pos_min, pos_sec = divmod(pos_rem, 60)
        dur_hours, dur_rem = divmod(dur_sec_total, 3600)
        dur_min, dur_sec = divmod(dur_rem, 60)
        # Format strings with hours if present
        if pos_hours > 0:
            pos_str = f"{pos_hours}:{pos_min:02d}:{pos_sec:02d}"
        else:
            pos_str = f"{pos_min:02d}:{pos_sec:02d}"
        if dur_hours > 0:
            dur_str = f"{dur_hours}:{dur_min:02d}:{dur_sec:02d}"
        else:
            dur_str = f"{dur_min:02d}:{dur_sec:02d}"
        self.duration_label.setText(f"{pos_str} / {dur_str}")

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

    def mouseMoveEvent(self, event):
        """Handle mouse movement to show/hide controls"""
        self.show_controls()
        self.mouse_timer.start()  # Restart timer on mouse move
        super().mouseMoveEvent(event)

    def enterEvent(self, event):
        """Show controls when mouse enters the widget"""
        self.show_controls()
        self.mouse_timer.start()  # Start timer when mouse enters
        
    def leaveEvent(self, event):
        """Hide controls when mouse leaves"""
        self.hide_controls()
        self.mouse_timer.stop()
        
    def show_controls(self):
        """Show the controls"""
        self.controls_container.show()
        self.mouse_timer.stop()
        
    def hide_controls(self):
        """Hide bottom controls only in fullscreen mode"""
        if self.window().isFullScreen():
            self.controls_container.hide()

    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        # Toggle fullscreen on the top-level window
        window = self.window()
        if window.isFullScreen():
            window.showNormal()
            # Show both control containers in windowed mode
            if hasattr(self, 'top_controls_container'):
                self.top_controls_container.show()
            self.controls_container.show()
            # Update fullscreen button icon
            # Create high-DPI pixmap for fullscreen expand icon
            size = QSize(int(self.icon_size.width() * self._dpr), int(self.icon_size.height() * self._dpr))
            raw = qta.icon('fa5s.expand', color='white')
            pix = raw.pixmap(size)
            pix.setDevicePixelRatio(self._dpr)
            self.fullscreen_icon.setPixmap(pix)
        else:
            window.showFullScreen()
            # Show bottom controls in fullscreen
            self.show_controls()
            # Hide top controls in fullscreen
            if hasattr(self, 'top_controls_container'):
                self.top_controls_container.hide()
            # Update fullscreen button icon
            # Create high-DPI pixmap for fullscreen compress icon
            size = QSize(int(self.icon_size.width() * self._dpr), int(self.icon_size.height() * self._dpr))
            raw = qta.icon('fa5s.compress', color='white')
            pix = raw.pixmap(size)
            pix.setDevicePixelRatio(self._dpr)
            self.fullscreen_icon.setPixmap(pix)

    def keyPressEvent(self, event):
        """Handle keyboard events"""
        window = self.window()
        if event.key() == Qt.Key_Escape:
            # Exit fullscreen if in fullscreen
            if window.isFullScreen():
                self.toggle_fullscreen()
        elif event.key() == Qt.Key_Space:
            self.toggle_play_pause()
        elif event.key() == Qt.Key_F:
            self.toggle_fullscreen()
        else:
            super().keyPressEvent(event)

    def video_clicked(self, event):
        """Handle video widget click event"""
        if self.mediaplayer.get_media() is None:
            return
            
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.video_widget.play_pause_overlay.show_play()
            self.update_play_pause_icon(False)
        else:
            if self.mediaplayer.play() == -1:
                QMessageBox.critical(self, "Error", "Unable to play video")
                return
            self.video_widget.play_pause_overlay.show_pause()
            self.timer.start()
            self.update_play_pause_icon(True)
            
        # Show controls
        self.show_controls()

    def handle_slider_click(self, event):
        """Handle slider click event to allow clicking anywhere"""
        if event.button() == Qt.LeftButton:
            # Calculate position based on click location
            pos = event.pos().x()
            value = QStyle.sliderValueFromPosition(
                self.position_slider.minimum(),
                self.position_slider.maximum(),
                pos,
                self.position_slider.width()
            )
            # Set the slider value
            self.position_slider.setValue(value)
            # Seek to the new position
            self.set_position(value)
            event.accept()
        else:
            event.ignore()

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