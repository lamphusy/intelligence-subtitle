import flet as ft
import os
import tempfile
import time
import threading
import base64
import shlex
import urllib.parse
from core.transcriber import transcribe
import pathlib
import subprocess

# VideoPlayer class để tương thích với main.py
class VideoPlayer:
    def __init__(self, parent=None):
        self.app = ft.app(target=self._main_app)
        
    def _main_app(self, page: ft.Page):
        page.title = "Intelligent Subtitle - Speech to Text with Whisper"
        page.window_width = 1280
        page.window_height = 800
        page.padding = 15
        page.bgcolor = ft.colors.BLACK
        page.theme_mode = ft.ThemeMode.DARK
        
        # State variables
        self.temp_dir = tempfile.mkdtemp(prefix="flet_subtitle_")
        self.video_path = ""
        self.segments = []
        self.is_playing = False
        self.duration = 100  # Giả lập thời gian video (giây)
        self.current_time = 0
        
        # Tạo HTML cho video player
        self.html_path = os.path.join(self.temp_dir, "player.html")
        self.html_content = self._create_html_player()
        
        with open(self.html_path, 'w', encoding='utf-8') as f:
            f.write(self.html_content)
        
        # Create WebView for video
        self.video_container = ft.Container(
            content=ft.Column([
                # Hiển thị HTML với iframe
                ft.Text("Chọn video để bắt đầu", 
                       size=22, 
                       weight=ft.FontWeight.BOLD,
                       color=ft.colors.WHITE,
                       text_align=ft.TextAlign.CENTER),
                ft.Container(
                    ft.Stack([
                        ft.Image(
                            src="https://via.placeholder.com/800x450?text=Chọn+video+để+bắt+đầu",
                            width=800,
                            height=450,
                            fit=ft.ImageFit.CONTAIN,
                        ),
                        ft.Container(
                            content=ft.Text(
                                "Video sẽ được phát trong cửa sổ riêng biệt khi chọn Play",
                                size=16,
                                color=ft.colors.WHITE,
                                text_align=ft.TextAlign.CENTER,
                                style=ft.TextStyle(
                                    shadow=ft.BoxShadow(
                                        color=ft.colors.BLACK,
                                        blur_radius=2,
                                        offset=ft.Offset(1, 1)
                                    )
                                )
                            ),
                            alignment=ft.alignment.center
                        ),
                    ]),
                    width=800,
                    height=450,
                    border=ft.border.all(2, ft.colors.WHITE24),
                    border_radius=8
                ),
                ft.Container(
                    ft.Text("", 
                           size=28, 
                           weight=ft.FontWeight.BOLD,
                           color=ft.colors.WHITE,
                           text_align=ft.TextAlign.CENTER,
                           style=ft.TextStyle(
                                shadow=[
                                    ft.BoxShadow(
                                        color=ft.colors.BLACK,
                                        blur_radius=0,
                                        spread_radius=2,
                                        offset=ft.Offset(-2, -2)
                                    ),
                                    ft.BoxShadow(
                                        color=ft.colors.BLACK,
                                        blur_radius=0,
                                        spread_radius=2,
                                        offset=ft.Offset(2, -2)
                                    ),
                                    ft.BoxShadow(
                                        color=ft.colors.BLACK,
                                        blur_radius=0,
                                        spread_radius=2,
                                        offset=ft.Offset(-2, 2)
                                    ),
                                    ft.BoxShadow(
                                        color=ft.colors.BLACK,
                                        blur_radius=0,
                                        spread_radius=2,
                                        offset=ft.Offset(2, 2)
                                    ),
                                    ft.BoxShadow(
                                        color=ft.colors.BLACK54,
                                        blur_radius=4,
                                        spread_radius=1,
                                        offset=ft.Offset(0, 3)
                                    )
                                ]
                            )
                      ),
                    key="subtitle_container",
                    bgcolor=ft.colors.TRANSPARENT,
                    padding=ft.padding.symmetric(vertical=10)
                )
            ]),
            bgcolor=ft.Colors.BLACK,
            border_radius=8,
            width=800,
            height=500,
            alignment=ft.alignment.center,
        )
        
        # Lưu trữ subtitle text để dễ cập nhật
        self.subtitle_text = self.video_container.content.controls[2].content
        
        # Progress indicators
        self.progress_bar = ft.ProgressBar(width=800, visible=False)
        self.progress_text = ft.Text("", style=ft.TextStyle(italic=True), color=ft.Colors.WHITE)
        
        # Time control
        self.time_slider = ft.Slider(
            min=0,
            max=100,
            value=0,
            divisions=100,
            label="{value}%",
            width=600,
            disabled=True,
            on_change=self._on_slider_change
        )
        self.time_display = ft.Text("00:00 / 00:00", color=ft.Colors.WHITE)
        
        # File picker setup
        self.file_picker = ft.FilePicker(on_result=self._on_file_picked)
        page.overlay.append(self.file_picker)
        
        # Save picker
        self.save_picker = ft.FilePicker(on_result=self._on_save_result)
        page.overlay.append(self.save_picker)
        
        # Control buttons
        self.open_button = ft.ElevatedButton(
            "Open Video", 
            icon=ft.Icons.FOLDER_OPEN,
            on_click=lambda _: self._pick_files()
        )
        
        self.play_button = ft.IconButton(
            icon=ft.Icons.PLAY_ARROW,
            disabled=True,
            on_click=lambda _: self._toggle_play()
        )
        
        self.save_button = ft.ElevatedButton(
            "Save Subtitles", 
            icon=ft.Icons.SAVE,
            disabled=True,
            on_click=lambda _: self._save_subtitles()
        )
        
        # Layout - đơn giản nhưng có đủ các điều khiển video
        page.add(
            ft.Column([
                ft.Container(
                    self.video_container,
                    alignment=ft.alignment.center,
                    margin=ft.margin.only(bottom=10, top=10)
                ),
                ft.Row([
                    self.progress_bar,
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([
                    self.progress_text,
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row([
                    self.open_button,
                    self.play_button,
                    ft.Column([
                        self.time_slider,
                    ], expand=True),
                    self.time_display,
                    self.save_button,
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=10)
        )
        
        # Timer cho việc xử lý video
        self.timer = None
        self.video_timer = None
        
        # Save reference to page for updates
        self.page = page
        
        # Register clean-up on close
        page.on_close = self._on_page_close
        page.update()
    
    def _create_html_player(self):
        """Tạo HTML cho video player"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body, html {{
                    margin: 0;
                    padding: 0;
                    width: 100%;
                    height: 100%;
                    overflow: hidden;
                    background-color: #000;
                }}
                #video-container {{
                    width: 100%;
                    height: 100%;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }}
                video {{
                    max-width: 100%;
                    max-height: 100%;
                }}
            </style>
        </head>
        <body>
            <div id="video-container">
                <video id="video" controls></video>
            </div>
            
            <script>
                var video = document.getElementById('video');
            </script>
        </body>
        </html>
        """
        
    def _on_page_close(self, e):
        """Xử lý khi đóng ứng dụng"""
        print("Cleaning up resources...")
        if self.timer:
            self.timer.cancel()
            self.timer = None
            
        if self.video_timer:
            self.video_timer.cancel()
            self.video_timer = None
        
        # Dừng video nếu đang phát
        if hasattr(self, 'video_process') and self.video_process and self.video_process.poll() is None:
            self.video_process.terminate()
            self.video_process = None
            
        # Xóa thư mục tạm
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                print(f"Removed temp directory: {self.temp_dir}")
        except Exception as e:
            print(f"Error cleaning up: {str(e)}")

    def _pick_files(self):
        self.file_picker.pick_files(
            dialog_title="Select Video File",
            allowed_extensions=["mp4", "avi", "mov", "mkv"],
            file_type=ft.FilePickerFileType.CUSTOM
        )
    
    def _on_file_picked(self, e: ft.FilePickerResultEvent):
        if not e.files or len(e.files) == 0:
            return
            
        file_path = e.files[0].path
        filename = os.path.basename(file_path)
        
        # Hiển thị đang xử lý
        self._update_ui_for_processing(filename)
        
        # Cập nhật video container
        self.video_container.content.controls[1] = ft.Container(
            content=ft.Stack([
                ft.Image(
                    src="https://via.placeholder.com/800x450?text=Processing+Video",
                    width=800,
                    height=450,
                    fit=ft.ImageFit.CONTAIN,
                ),
                ft.Container(
                    content=ft.Text(
                        f"Đang xử lý video: {filename}",
                        size=16,
                        color=ft.colors.WHITE,
                        text_align=ft.TextAlign.CENTER,
                        style=ft.TextStyle(
                            shadow=ft.BoxShadow(
                                color=ft.colors.BLACK,
                                blur_radius=2,
                                offset=ft.Offset(1, 1)
                            )
                        )
                    ),
                    alignment=ft.alignment.center
                ),
            ]),
            width=800,
            height=450,
            border=ft.border.all(2, ft.colors.WHITE24),
            border_radius=8
        )
        self.page.update()
        
        # Tạo thư mục tạm mới cho mỗi lần xử lý
        try:
            if os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = tempfile.mkdtemp(prefix="flet_subtitle_")
            print(f"Created new temp directory: {self.temp_dir}")
        except Exception as e:
            print(f"Error recreating temp directory: {str(e)}")
        
        # Trực tiếp sao chép file vào thư mục tạm
        try:
            import shutil
            # Tên file đơn giản trong thư mục tạm
            temp_input_path = os.path.join(self.temp_dir, "input_video" + os.path.splitext(file_path)[1])
            
            # Sao chép file
            with open(file_path, 'rb') as src_file:
                with open(temp_input_path, 'wb') as dst_file:
                    shutil.copyfileobj(src_file, dst_file)
                    
            print(f"Copied {file_path} to {temp_input_path}, size: {os.path.getsize(temp_input_path)}")
            
            # Gán đường dẫn video
            self.video_path = temp_input_path
            
            # Xử lý video
            self._process_video(temp_input_path)
            
            # Bắt đầu timer để theo dõi thời gian video
            self._start_video_timer()
            
        except FileNotFoundError:
            self._show_error("File Not Found", "Cannot find the selected video file.",
                           f"File not found: {file_path}")
        except PermissionError:
            self._show_error("Access Denied", "Cannot access the selected video file.",
                           f"Permission denied: {file_path}")
        except Exception as e:
            self._show_error("File Error", "Error processing the selected file.",
                           f"Error: {str(e)}")
    
    def _start_video_timer(self):
        """Bắt đầu timer để theo dõi thời gian video"""
        if self.video_timer:
            self.video_timer.cancel()
            
        def update_time():
            self.current_time += 0.1
            if self.current_time >= self.duration:
                self.current_time = 0
                self.is_playing = False
                self.play_button.icon = ft.Icons.PLAY_ARROW
                
            self._update_subtitle(self.current_time)
            self._update_time_display(self.current_time)
            
            if self.is_playing:
                self.video_timer = threading.Timer(0.1, update_time)
                self.video_timer.daemon = True
                self.video_timer.start()
        
        self.video_timer = threading.Timer(0.1, update_time)
        self.video_timer.daemon = True
        self.video_timer.start()
    
    def _update_ui_for_processing(self, path):
        # Reset state
        self.segments = []
        self.is_playing = False
        self.current_time = 0
        
        # Update UI
        self.subtitle_text.value = f"Loading: {os.path.basename(path)}"
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.progress_text.value = "Processing..."
        self.page.update()
        
    def _process_video(self, path):
        """Xử lý video thực tế"""
        try:
            # Đường dẫn đã được sao chép vào thư mục tạm với tên đơn giản
            input_video_path = path  # Đây là đường dẫn trong thư mục tạm
            
            # Hiển thị trạng thái
            self.progress_bar.value = 0.05
            self.progress_text.value = "Preparing video..."
            self.page.update()
            
            # Trích xuất audio từ video
            audio_path = os.path.join(self.temp_dir, "audio.wav")
            self.progress_bar.value = 0.1
            self.progress_text.value = "Extracting audio from video..."
            self.page.update()
            
            try:
                # Tạo lệnh ffmpeg để trích xuất audio
                ffmpeg_audio_cmd = [
                    "ffmpeg", "-y", 
                    "-i", input_video_path, 
                    "-vn", "-acodec", "pcm_s16le", 
                    "-ar", "16000", "-ac", "1", 
                    audio_path
                ]
                
                # Chạy lệnh với shell=True và escape đường dẫn
                result = subprocess.run(
                    " ".join([shlex.quote(str(arg)) for arg in ffmpeg_audio_cmd]),
                    shell=True,
                    check=True, 
                    capture_output=True, 
                    text=True
                )
                print(f"Audio extraction completed successfully, output: {audio_path}")
            except subprocess.CalledProcessError as e:
                self._show_error("Audio Extraction Failed", "Could not extract audio from the video.",
                                f"Error extracting audio: {e.stderr}")
                return
            
            # Kiểm tra nếu audio đã được trích xuất
            if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                self._show_error("No Audio Found", "Could not find any audio in the video file.",
                                "Error: No audio found in video or extraction failed")
                return
            
            # Trích xuất ảnh thumbnail
            thumb_path = os.path.join(self.temp_dir, "thumbnail.jpg")
            self.progress_bar.value = 0.2
            self.progress_text.value = "Creating thumbnail..."
            self.page.update()
            
            try:
                # Tạo lệnh ffmpeg để trích xuất thumbnail
                ffmpeg_thumb_cmd = [
                    "ffmpeg", "-y", 
                    "-i", input_video_path, 
                    "-ss", "00:00:01", 
                    "-vframes", "1", 
                    thumb_path
                ]
                
                print(f"Executing thumbnail command: {' '.join(ffmpeg_thumb_cmd)}")
                
                # Chạy lệnh với shell=True và escape đường dẫn
                result = subprocess.run(
                    " ".join([shlex.quote(str(arg)) for arg in ffmpeg_thumb_cmd]),
                    shell=True,
                    check=True, 
                    capture_output=True, 
                    text=True
                )
                
                print(f"Thumbnail extraction completed, output at: {thumb_path}")
                
                if os.path.exists(thumb_path):
                    print(f"Thumbnail size: {os.path.getsize(thumb_path)} bytes")
                    # Cập nhật container với thumbnail
                    self.video_container.content.controls[1] = ft.Container(
                        content=ft.Stack([
                            ft.Image(
                                src=thumb_path,
                                width=800,
                                height=450,
                                fit=ft.ImageFit.CONTAIN,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    "Đang xử lý video với Whisper - vui lòng đợi...",
                                    size=16,
                                    color=ft.colors.WHITE,
                                    text_align=ft.TextAlign.CENTER,
                                    style=ft.TextStyle(
                                        shadow=ft.BoxShadow(
                                            color=ft.colors.BLACK,
                                            blur_radius=2,
                                            offset=ft.Offset(1, 1)
                                        )
                                    )
                                ),
                                alignment=ft.alignment.center
                            ),
                        ]),
                        width=800,
                        height=450,
                        border=ft.border.all(2, ft.colors.WHITE24),
                        border_radius=8
                    )
                    
                    # Giải thích lý do ở container phụ đề
                    self.subtitle_text.value = "Đang xử lý video..."
                    self.page.update()
                else:
                    print(f"Warning: Thumbnail not created at {thumb_path}")
            except subprocess.CalledProcessError as e:
                print(f"Thumbnail creation error: {e.stderr}")
                # Tiếp tục ngay cả khi thumbnail không thể tạo
            except Exception as e:
                print(f"Thumbnail creation error: {str(e)}")
                # Tiếp tục ngay cả khi thumbnail không thể tạo
                
            # Phân tích và tạo phụ đề (transcription)
            self.progress_bar.value = 0.3
            self.progress_text.value = "Transcribing audio with Whisper (this may take a while)..."
            self.page.update()
            
            print(f"Starting transcription of audio: {audio_path}")
            # Sử dụng module transcribe thực tế từ core
            result_segments = transcribe(audio_path)
            print(f"Transcription completed: {len(result_segments)} segments found")
            
            # Cập nhật trạng thái hoàn thành
            self._process_transcription_result(result_segments, input_video_path)
            
        except Exception as e:
            # Hiển thị lỗi nếu có
            self.progress_bar.visible = False
            self.progress_text.value = f"Error processing video: {str(e)}"
            self.page.update()
            print(f"Error processing video: {str(e)}")
    
    def _process_transcription_result(self, segments, input_video_path):
        """Xử lý kết quả transcription thực tế"""
        # Lưu các segments
        self.segments = segments if segments else []
        
        # Cập nhật UI
        self.progress_bar.visible = False
        self.progress_bar.value = 0
        
        if not segments or len(segments) == 0:
            self._show_error("No Speech Detected", "Could not detect any speech in the video. Please check if your video has audio.",
                            "No speech detected in the video.")
            return
            
        # Có phụ đề, tiếp tục xử lý
        self.subtitle_text.value = "Creating video with embedded subtitles..."
        self.progress_text.value = "Creating video with embedded subtitles..."
        self.progress_bar.visible = True
        self.progress_bar.value = 0.7
        self.page.update()
            
        # Tạo file SRT từ segments
        srt_path = os.path.join(self.temp_dir, "subtitles.srt")
        try:
            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(segments):
                    start_time = self._format_srt_time(segment.get('start', 0))
                    end_time = self._format_srt_time(segment.get('end', 0))
                    text = segment.get('text', '').strip()
                    
                    f.write(f"{i+1}\n{start_time} --> {end_time}\n{text}\n\n")
                
            # Tạo video với phụ đề nhúng
            playable_video_path = os.path.join(self.temp_dir, "playable_output.mp4")
            
            # Đọc nội dung tệp SRT vào bộ nhớ
            try:
                with open(srt_path, 'r', encoding='utf-8') as f:
                    srt_content = f.read()
                
                print(f"SRT content loaded ({len(srt_content)} bytes)")
                
                # Tạo tệp tạm với tên đơn giản
                simple_srt_path = os.path.join(self.temp_dir, "simple_subs.srt")
                with open(simple_srt_path, 'w', encoding='utf-8') as f:
                    f.write(srt_content)
                
                print(f"Created simplified SRT at: {simple_srt_path}")
                
                # Tạo video có phụ đề nhúng với đường dẫn tệp đơn giản
                # Giải pháp: đổi đường dẫn về dạng tương đối với thư mục hiện tại
                simple_srt_filename = os.path.basename(simple_srt_path)
                
                # Di chuyển vào thư mục chứa file subtitles
                cwd_cmd = f"cd {shlex.quote(self.temp_dir)} && "
                
                ffmpeg_cmd_str = (
                    cwd_cmd +
                    f"ffmpeg -y -i {shlex.quote(input_video_path)} " +
                    f"-vf \"subtitles={simple_srt_filename}:force_style='FontName=Arial,FontSize=24," +
                    f"PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=3,Outline=1,Shadow=0," +
                    f"BackColour=&H00000000'\" " +
                    f"-c:a copy {shlex.quote(playable_video_path)}"
                )
            except (IOError, OSError) as e:
                raise Exception(f"Error processing subtitle file: {str(e)}")
            
            print(f"Running ffmpeg command: {ffmpeg_cmd_str}")
            
            # Chạy ffmpeg với shell=True
            try:
                result = subprocess.run(
                    ffmpeg_cmd_str,
                    shell=True,
                    check=True, 
                    capture_output=True, 
                    text=True
                )
                
                print(f"FFmpeg completed, output video created at: {playable_video_path}")
                print(f"FFmpeg stdout: {result.stdout}")
                
                # Kiểm tra nếu file đầu ra tồn tại
                if not os.path.exists(playable_video_path):
                    raise Exception(f"Failed to create output file at {playable_video_path}")
                
                if os.path.getsize(playable_video_path) == 0:
                    raise Exception("Output file is empty (0 bytes)")
                    
                print(f"Output video size: {os.path.getsize(playable_video_path)} bytes")
                
            except subprocess.CalledProcessError as e:
                error_message = f"Error embedding subtitles: {e.stderr}"
                self._show_error("Subtitle Embedding Failed", "Could not embed subtitles into the video.",
                                error_message)
                return
            except Exception as e:
                self.subtitle_text.value = f"Error creating video with subtitles: {str(e)}"
                self.progress_text.value = f"Error: {str(e)}"
                print(f"Error embedding subtitles: {str(e)}")
                return
            
            # Cập nhật UI để cho biết phụ đề đã được nhúng
            self.video_container.content.controls[1] = ft.Container(
                content=ft.Stack([
                    ft.Image(
                        src=os.path.join(self.temp_dir, "thumbnail.jpg") if os.path.exists(os.path.join(self.temp_dir, "thumbnail.jpg")) else "https://via.placeholder.com/800x450?text=Video+Ready",
                        width=800,
                        height=450,
                        fit=ft.ImageFit.CONTAIN,
                    ),
                    ft.Container(
                        content=ft.Text(
                            "Nhấn Play để xem video có phụ đề đã được nhúng",
                            size=18,
                            color=ft.colors.WHITE,
                            text_align=ft.TextAlign.CENTER,
                            style=ft.TextStyle(
                                shadow=ft.BoxShadow(
                                    color=ft.colors.BLACK,
                                    blur_radius=2,
                                    offset=ft.Offset(1, 1)
                                )
                            )
                        ),
                        alignment=ft.alignment.center
                    ),
                ]),
                width=800,
                height=450,
                border=ft.border.all(2, ft.colors.WHITE24),
                border_radius=8
            )
            
            self.subtitle_text.value = "Transcription complete! Press play to watch video with embedded subtitles"
            self.progress_text.value = "Processing complete! Subtitles embedded into video."
            self.play_button.disabled = False
            self.time_slider.disabled = False
            self.save_button.disabled = False
            
            # Lấy thời lượng từ đoạn phụ đề cuối cùng
            self.duration = max(segment.get('end', 0) for segment in segments) + 5
            
            # Cập nhật hiển thị thời gian
            self._update_time_display(0)
            
            # Tạo nút chơi/dừng video thực tế
            self.video_process = None
            
            def start_video_playback():
                if self.video_process is None or self.video_process.poll() is not None:
                    # Bắt đầu phát video
                    try:
                        # Tạo lệnh ffplay để phát video
                        ffplay_cmd_str = (
                            f"ffplay -autoexit -loglevel quiet "
                            f"-x 800 -y 450 {shlex.quote(playable_video_path)}"
                        )
                        
                        print(f"Executing ffplay command: {ffplay_cmd_str}")
                        
                        # Chạy ffplay với shell=True
                        self.video_process = subprocess.Popen(
                            ffplay_cmd_str,
                            shell=True,
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE
                        )
                        return True
                    except Exception as e:
                        self._show_error("Playback Error", "Could not start video playback.",
                                        f"Error starting ffplay: {str(e)}")
                        return False
                return True
            
            def stop_video_playback():
                if self.video_process and self.video_process.poll() is None:
                    # Dừng phát video
                    self.video_process.terminate()
            
            # Ghép nối hàm toggle_play với việc phát/dừng video thực tế
            self._original_toggle_play = self._toggle_play
            def new_toggle_play():
                if self.is_playing:
                    stop_video_playback()
                    self._original_toggle_play()
                else:
                    # Chỉ đổi trạng thái nếu bắt đầu video thành công
                    if start_video_playback():
                        self._original_toggle_play()
            
            self._toggle_play = new_toggle_play
            
            # Thay thế hàm tìm kiếm
            def on_slider_change_with_video(e):
                # Cập nhật thời gian dựa trên vị trí slider
                if self.duration > 0:
                    new_time = e.control.value / 100 * self.duration
                    self.current_time = new_time
                    
                    # Nếu đang phát video, dừng và phát lại ở vị trí mới
                    if self.is_playing:
                        if self.video_process and self.video_process.poll() is None:
                            self.video_process.terminate()
                        
                        # Tạo lệnh ffplay để phát video từ vị trí mới
                        ffplay_seek_cmd_str = (
                            f"ffplay -autoexit -loglevel quiet "
                            f"-ss {new_time} -x 800 -y 450 {shlex.quote(os.path.join(self.temp_dir, 'playable_output.mp4'))}"
                        )
                        
                        print(f"Executing ffplay seek command: {ffplay_seek_cmd_str}")
                        
                        # Chạy ffplay với shell=True
                        self.video_process = subprocess.Popen(
                            ffplay_seek_cmd_str,
                            shell=True,
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE
                        )
            
            self.time_slider.on_change = on_slider_change_with_video
            
            self.progress_bar.visible = False    
            self.page.update()
            
        except Exception as e:
            # Hiển thị lỗi nếu có
            self.progress_bar.visible = False
            self.progress_text.value = f"Error processing video: {str(e)}"
            self.page.update()
            print(f"Error processing video: {str(e)}")
    
    def _save_subtitles(self):
        if not self.segments or len(self.segments) == 0:
            return
            
        # Tạo save dialog
        self.save_picker.save_file(
            dialog_title="Save Subtitles",
            file_name=f"{os.path.splitext(os.path.basename(self.video_path))[0]}.srt",
            allowed_extensions=["srt"]
        )
    
    def _on_save_result(self, e):
        if not e.path:
            return  # User cancelled
            
        # Lưu phụ đề dạng SRT
        try:
            with open(e.path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(self.segments):
                    start_time = self._format_srt_time(segment.get('start', 0))
                    end_time = self._format_srt_time(segment.get('end', 0))
                    text = segment.get('text', '').strip()
                    
                    f.write(f"{i+1}\n{start_time} --> {end_time}\n{text}\n\n")
                    
            self.progress_text.value = f"Subtitles saved to {os.path.basename(e.path)}"
            self.page.update()
        except Exception as e:
            self.progress_text.value = f"Error saving subtitles: {str(e)}"
            self.page.update()
    
    def _format_srt_time(self, seconds):
        if seconds < 0:
            seconds = 0
        millisec = int(seconds * 1000) % 1000
        seconds = int(seconds)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millisec:03d}"

    # Thêm các hàm xử lý phát video và cập nhật thanh thời gian
    def _toggle_play(self):
        self.is_playing = not self.is_playing
        
        if self.is_playing:
            self.play_button.icon = ft.Icons.PAUSE
        else:
            self.play_button.icon = ft.Icons.PLAY_ARROW
        
        self.page.update()
    
    def _update_subtitle(self, time_sec):
        """
        Cập nhật thông tin phụ đề hiện tại dựa trên thời gian
        Chỉ để hiển thị thông tin, không cần hiển thị text nữa vì phụ đề đã được nhúng vào video
        """
        if not self.segments:
            return
            
        # Tìm phụ đề đang active
        current_text = ""
        for segment in self.segments:
            if segment.get('start', 0) <= time_sec < segment.get('end', 0):
                current_text = segment.get('text', '')
                break
    
    def _update_time_display(self, time_sec):
        # Cập nhật thanh slider
        if self.duration > 0:
            percentage = min(100, (time_sec / self.duration) * 100)
            self.time_slider.value = percentage
        
        # Cập nhật hiển thị thời gian
        minutes_current, seconds_current = divmod(int(time_sec), 60)
        minutes_total, seconds_total = divmod(int(self.duration), 60)
        self.time_display.value = f"{minutes_current:02d}:{seconds_current:02d} / {minutes_total:02d}:{seconds_total:02d}"
        
        self.page.update()
    
    def _on_slider_change(self, e):
        # Cập nhật thời gian dựa trên vị trí slider
        if self.duration > 0:
            new_time = e.control.value / 100 * self.duration
            self.current_time = new_time
            self._update_subtitle(new_time)
            
            # Nếu đang phát video, dừng và phát lại ở vị trí mới
            if hasattr(self, 'video_process') and self.is_playing:
                if self.video_process and self.video_process.poll() is None:
                    self.video_process.terminate()
                
                # Tạo lệnh ffplay để phát video từ vị trí mới
                ffplay_seek_cmd_str = (
                    f"ffplay -autoexit -loglevel quiet "
                    f"-ss {new_time} -x 800 -y 450 {shlex.quote(os.path.join(self.temp_dir, 'playable_output.mp4'))}"
                )
                
                print(f"Executing ffplay seek command: {ffplay_seek_cmd_str}")
                
                # Chạy ffplay với shell=True
                self.video_process = subprocess.Popen(
                    ffplay_seek_cmd_str,
                    shell=True,
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE
                )

    def _show_error(self, title, message, details=None):
        """Hiển thị lỗi trong UI theo cách thống nhất"""
        # Cập nhật container chính
        self.video_container.content.controls[1] = ft.Container(
            content=ft.Stack([
                ft.Image(
                    src="https://via.placeholder.com/800x450?text=Error",
                    width=800,
                    height=450,
                    fit=ft.ImageFit.CONTAIN,
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text(
                            title,
                            size=22,
                            color=ft.colors.RED,
                            text_align=ft.TextAlign.CENTER,
                            weight=ft.FontWeight.BOLD,
                            style=ft.TextStyle(
                                shadow=ft.BoxShadow(
                                    color=ft.colors.BLACK,
                                    blur_radius=2,
                                    offset=ft.Offset(1, 1)
                                )
                            )
                        ),
                        ft.Text(
                            message,
                            size=16,
                            color=ft.colors.WHITE,
                            text_align=ft.TextAlign.CENTER,
                            style=ft.TextStyle(
                                shadow=ft.BoxShadow(
                                    color=ft.colors.BLACK,
                                    blur_radius=2,
                                    offset=ft.Offset(1, 1)
                                )
                            )
                        )
                    ]),
                    alignment=ft.alignment.center
                ),
            ]),
            width=800,
            height=450,
            border=ft.border.all(2, ft.colors.RED_200),
            border_radius=8
        )
        
        # Cập nhật thông báo lỗi chi tiết
        if details:
            self.progress_text.value = details
        else:
            self.progress_text.value = message
            
        # Ẩn thanh progress
        self.progress_bar.visible = False
        
        # Vô hiệu hóa các nút điều khiển
        self.play_button.disabled = True
        self.time_slider.disabled = True
        self.save_button.disabled = True
        
        # Cập nhật UI
        self.page.update()

# Khởi chạy ứng dụng khi chạy trực tiếp
if __name__ == "__main__":
    player = VideoPlayer()