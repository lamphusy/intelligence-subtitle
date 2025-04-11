from PyQt5.QtWidgets import QApplication, QMainWindow
from gui.video_player import VideoPlayer
import sys

# Import our cleanup module if available
try:
    from cleanup_resources import cleanup
except ImportError:
    def cleanup():
        pass  # Fallback if module not found

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.player = VideoPlayer()
        self.setCentralWidget(self.player)
        self.setWindowTitle("Intelligent Subtitle - Speech to Text with Whisper")
        self.resize(1280, 800)
    
    def closeEvent(self, event):
        # Ensure the video player's close event gets called for proper thread cleanup
        print("Closing application, cleaning up resources...")
        
        # Close the video player
        self.player.closeEvent(event)
        
        # Make sure no references remain to the player
        if hasattr(self, 'player'):
            self.player.deleteLater()
            
        # Run our cleanup function
        cleanup()
            
        print("Application closed successfully")

def launch_app():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    # Make sure cleanup is called when the application exits
    app.aboutToQuit.connect(cleanup)
    
    sys.exit(app.exec_())