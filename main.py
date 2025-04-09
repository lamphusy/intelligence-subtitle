import sys
import os
import importlib.util
import subprocess

def check_dependencies():
    """Check if all required dependencies are installed"""
    
    required_packages = {
        'PyQt5': 'pip install PyQt5',
        'ffmpeg': 'pip install ffmpeg-python',  # The module name is actually 'ffmpeg'
        'whisper': 'pip install git+https://github.com/openai/whisper.git',
        'torch': 'pip install torch'
    }
    
    missing = []
    
    for package, install_cmd in required_packages.items():
        if package == 'whisper':
            # Special check for whisper package
            try:
                import whisper
                if not hasattr(whisper, 'load_model'):
                    missing.append(f"{package} (wrong version) - Install with: {install_cmd}")
            except ImportError:
                missing.append(f"{package} - Install with: {install_cmd}")
        else:
            # Regular check for other packages
            try:
                __import__(package)
            except ImportError:
                missing.append(f"{package} - Install with: {install_cmd}")
    
    if missing:
        print("Missing dependencies:")
        for m in missing:
            print(f"  - {m}")
        print("Please install the missing dependencies and try again.")
        return False
    
    return True

def check_ffmpeg():
    """Check if ffmpeg is properly installed"""
    try:
        # Run ffmpeg -version
        result = subprocess.run(['ffmpeg', '-version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True)
        
        # If the command was successful
        if result.returncode == 0:
            print("FFmpeg is correctly installed.")
            return True
        else:
            print("FFmpeg may not be correctly installed.")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"Error checking ffmpeg: {str(e)}")
        print("Please ensure ffmpeg is correctly installed on your system.")
        return False

if __name__ == "__main__":
    # Check dependencies first
    if not check_dependencies():
        sys.exit(1)
        
    # Check if ffmpeg is correctly installed
    if not check_ffmpeg():
        print("Warning: FFmpeg may not be correctly installed.")
        print("Video transcription might not work properly.")
        
    # Now import and launch the app
    from gui.main_window import launch_app
    launch_app()