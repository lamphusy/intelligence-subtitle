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
            "small": "https://openaipublic.azureedge.net/main/whisper/models/25a8566e1d0c1e2231d1c762132cd20e0f96a85d16145c3a00adf5d1ac670ead/small.pt",
            "medium": "https://openaipublic.azureedge.net/main/whisper/models/1f8c3074a43963a1a28018281ff7a9e9a3414307eef58966f7cacb3af7c08977/medium.pt",
            "large": "https://openaipublic.azureedge.net/main/whisper/models/e4b87e7e0bf463eb8e6956e646f1e277e901512310def2c24bf0e11bd3c28e9a/large.pt"
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
        
        # Download the model with progress indicator
        model_path = os.path.join(whisper_cache_dir, f"{model_name}.pt")
        
        def report_progress(block_num, block_size, total_size):
            """Report download progress"""
            if total_size > 0:
                percent = block_num * block_size * 100 / total_size
                # Only report progress every 2%
                if int(percent) % 2 == 0:
                    mb_downloaded = block_num * block_size / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    print(f"\rDownloading model: {percent:.1f}% ({mb_downloaded:.1f} MB / {mb_total:.1f} MB)", end="", flush=True)
        
        print(f"Starting download of {model_name} model...")
        urllib.request.urlretrieve(model_url, model_path, reporthook=report_progress)
        print("\nModel downloaded successfully!")
        
        # Verify the download was successful
        if os.path.exists(model_path):
            model_size_mb = os.path.getsize(model_path) / (1024 * 1024)
            print(f"Model downloaded to {model_path} ({model_size_mb:.1f} MB)")
            return True
        else:
            print(f"Failed to download model to {model_path}")
            return False
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
    # Models and approximate sizes:
    # - tiny: ~75MB, fastest, lowest accuracy
    # - base: ~142MB, fast, better accuracy than tiny
    # - small: ~461MB, slower, better accuracy than base
    # - medium: ~1.5GB, even slower, better accuracy than small
    # - large: ~3GB, slowest, highest accuracy
    model_size = os.environ.get("WHISPER_MODEL_SIZE", "small")  # Default to small for balancing speed and accuracy
    print(f"Loading Whisper model: {model_size}")
    
    # Get the language if specified
    language = os.environ.get("WHISPER_LANGUAGE", None)
    if language:
        print(f"Using specified language: {language}")
    
    # Model info for users
    model_info = {
        "tiny": "Smallest model (75MB) - fastest but lowest accuracy",
        "base": "Small model (142MB) - fast with decent accuracy",
        "small": "Medium model (461MB) - good balance of speed and accuracy",
        "medium": "Large model (1.5GB) - high accuracy but slower",
        "large": "Largest model (3GB) - highest accuracy but slowest"
    }
    
    if model_size in model_info:
        print(f"Model info: {model_info[model_size]}")
    
    # Check if we need to manually download the model
    if not is_model_downloaded(model_size):
        print(f"Model not found locally. Downloading {model_size} model (this may take a while)...")
        downloaded = download_model_manually(model_size)
        if not downloaded:
            print("Could not manually download model, trying standard method...")
    
    try:
        model = whisper.load_model(model_size)
        
        # Transcribe the audio
        print(f"Transcribing audio: {audio_path}")
        
        # Prepare transcription options
        transcribe_options = {
            "verbose": True,  # Show progress
            "fp16": False     # Set to True if GPU is available for faster processing
        }
        
        # Add language if specified
        if language:
            transcribe_options["language"] = language
        
        result = model.transcribe(audio_path, **transcribe_options)
        
        # Return the segments which contain start time, end time, and text
        if "segments" not in result:
            print("Warning: No segments found in transcription result")
            return []
            
        print(f"Transcription complete: {len(result['segments'])} segments identified")
        return result["segments"]
    
    except Exception as e:
        print(f"Error during transcription: {str(e)}")
        raise 