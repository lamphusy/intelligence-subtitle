import os
import sys
import ssl
import urllib.request
import warnings

# Check if we have the correct whisper package
try:
    import whisper
    if not hasattr(whisper, 'load_model'):
        print("Error: Wrong whisper package installed.")
        print("Please install OpenAI's whisper package with: pip install git+https://github.com/openai/whisper.git")
        sys.exit(1)
except ImportError:
    print("Error: whisper module not found.")
    print("Please install OpenAI's whisper package with: pip install git+https://github.com/openai/whisper.git")
    sys.exit(1)

# Handle SSL certificate issues (common on macOS)
def fix_ssl_certificate_issues():
    """Fix SSL certificate verification issues on macOS"""
    if sys.platform == 'darwin':
        # For macOS, we might need to install certificates
        try:
            # Try to create an unverified context for downloading models
            ssl._create_default_https_context = ssl._create_unverified_context
            print("SSL certificate verification disabled (required on some macOS systems)")
        except Exception as e:
            print(f"Warning: Could not disable SSL verification: {e}")

# Apply the SSL fix
fix_ssl_certificate_issues()

# Check if model is already downloaded
def is_model_downloaded(model_name="tiny"):
    """Check if the model is already downloaded to avoid SSL issues"""
    whisper_cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "whisper")
    model_path = os.path.join(whisper_cache_dir, f"{model_name}.pt")
    return os.path.exists(model_path)

def download_model_manually(model_name="tiny"):
    """Download the model manually with SSL verification disabled"""
    try:
        print(f"Manually downloading whisper {model_name} model...")
        
        # Create directories if they don't exist
        whisper_cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "whisper")
        os.makedirs(whisper_cache_dir, exist_ok=True)
        
        # Model URLs
        model_urls = {
            "tiny": "https://openaipublic.azureedge.net/main/whisper/models/d3dd57d32accea0b295c96e26691aa14d8822fac7d9d27d5dc00b4ca2826dd03/tiny.pt",
            "base": "https://openaipublic.azureedge.net/main/whisper/models/ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e/base.pt",
        }
        
        # Download the model
        model_url = model_urls.get(model_name)
        if not model_url:
            print(f"No manual URL for {model_name} model. Using whisper's downloader.")
            return False
            
        # Create an SSL context that doesn't verify certificates
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        # Download the model
        model_path = os.path.join(whisper_cache_dir, f"{model_name}.pt")
        urllib.request.urlretrieve(model_url, model_path)
        
        print(f"Model downloaded to {model_path}")
        return True
    except Exception as e:
        print(f"Manual download failed: {e}")
        return False

def transcribe(audio_path):
    """
    Transcribe audio using OpenAI's Whisper model.
    
    Args:
        audio_path: Path to the audio file
        
    Returns:
        List of segments with start time, end time, and text
    """
    # Load the Whisper model
    # Options: 'tiny', 'base', 'small', 'medium', 'large'
    model_size = os.environ.get("WHISPER_MODEL_SIZE", "tiny")  # Default to tiny for faster processing
    print(f"Loading Whisper model: {model_size}")
    
    # Check if we need to manually download the model
    if not is_model_downloaded(model_size):
        downloaded = download_model_manually(model_size)
        if not downloaded:
            print("Could not manually download model, trying standard method...")
    
    try:
        model = whisper.load_model(model_size)
        
        # Transcribe the audio
        print(f"Transcribing audio: {audio_path}")
        result = model.transcribe(
            audio_path,
            verbose=True,  # Set to True to show progress
            fp16=False     # Set to True if GPU is available for faster processing
        )
        
        # Return the segments which contain start time, end time, and text
        if "segments" not in result:
            print("Warning: No segments found in transcription result")
            return []
            
        print(f"Transcription complete: {len(result['segments'])} segments identified")
        return result["segments"]
    
    except Exception as e:
        print(f"Error during transcription: {str(e)}")
        raise