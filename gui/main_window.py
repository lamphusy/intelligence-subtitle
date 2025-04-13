from gui.video_player import VideoPlayer
import sys

# Import our cleanup module if available
try:
    from cleanup_resources import cleanup
except ImportError:
    def cleanup():
        pass  # Fallback if module not found

def launch_app():
    player = VideoPlayer()
    # Không cần điều khiển PyQt nữa, vì Flet sẽ xử lý tất cả giao diện