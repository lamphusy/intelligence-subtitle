from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
import os
import tempfile
import traceback
import ffmpeg
from core.transcriber import transcribe

class TranscriptionWorker(QObject):
    """
    Worker class that handles the transcription process in a separate thread.
    """
    # Signals
    transcription_progress = pyqtSignal(str)  # To report progress
    transcription_complete = pyqtSignal(list)  # To return the transcribed segments
    transcription_error = pyqtSignal(str)      # To report errors
    
    def __init__(self):
        super().__init__()
        self.video_path = None
        self.temp_dir = tempfile.mkdtemp()
        self._running = True
        
    def stop(self):
        """Signal the worker to stop processing"""
        self._running = False
        # Clean up temporary directory
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                print(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            print(f"Error cleaning up temp directory: {str(e)}")
        
    @pyqtSlot(str)
    def process_video(self, video_path):
        """Process the video and emit results"""
        self.video_path = video_path
        self._running = True
        
        try:
            # Report progress
            self.transcription_progress.emit("Extracting audio from video...")
            
            # Extract audio
            audio_path = os.path.join(self.temp_dir, "audio.wav")
            self.extract_audio(video_path, audio_path)
            
            # Check if we were asked to stop
            if not self._running:
                return
                
            # Report progress
            self.transcription_progress.emit("Transcribing audio with Whisper (this may take a while)...")
            
            # Transcribe
            segments = transcribe(audio_path)
            
            # Check if we were asked to stop
            if not self._running:
                return
                
            # Check if we got any segments
            if not segments:
                self.transcription_error.emit("No speech detected in the audio")
                return
            
            # Report completion
            self.transcription_complete.emit(segments)
            
        except Exception as e:
            # Get full error details
            error_details = traceback.format_exc()
            print(f"Transcription error: {str(e)}")
            print(error_details)
            
            # Create a more user-friendly error message
            error_message = str(e)
            if "ffmpeg" in error_message.lower():
                error_message = "Error extracting audio from video. Please ensure ffmpeg is properly installed."
            elif "cuda" in error_message.lower():
                error_message = "CUDA error during transcription. Try setting fp16=False in transcriber.py"
            elif "whisper" in error_message.lower():
                error_message = f"Whisper model error: {error_message}"
            
            # Report error
            self.transcription_error.emit(error_message)
    
    def extract_audio(self, video_path, audio_path):
        """Extract audio from video using ffmpeg"""
        try:
            # Print more information for debugging
            print(f"Extracting audio from: {video_path}")
            print(f"Saving audio to: {audio_path}")
            
            (
                ffmpeg
                .input(video_path)
                .output(audio_path, acodec='pcm_s16le', ac=1, ar='16k')
                .run(quiet=True, overwrite_output=True)
            )
            
            # Verify the audio file was created
            if not os.path.exists(audio_path):
                raise Exception("Audio extraction failed - no output file created")
                
            print(f"Audio extraction complete: {os.path.getsize(audio_path)} bytes")
            
        except Exception as e:
            print(f"Error extracting audio: {str(e)}")
            raise Exception(f"Error extracting audio: {str(e)}") 