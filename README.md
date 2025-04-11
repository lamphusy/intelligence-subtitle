# Intelligence Subtitle

Speech-to-text automated subtitles using OpenAI's Whisper model.

## Features

- Extract audio from video files with FFmpeg
- Transcribe speech using OpenAI's Whisper model
- Display subtitles in real-time as the video plays
- Save subtitles in SRT, VTT, or JSON format
- Configurable Whisper model size (tiny, base, small, medium, large)
- Language selection support
- Embedded subtitles directly on the video

## Requirements

- Python 3.7+
- FFmpeg
- PyQt5
- openai-whisper
- ffmpeg-python

## Installation

1. Clone the repository:
```
git clone https://github.com/yourusername/intelligence-subtitle.git
cd intelligence-subtitle
```

2. Install the dependencies:
```
pip install PyQt5 ffmpeg-python
pip install git+https://github.com/openai/whisper.git
```

3. Make sure FFmpeg is installed on your system.

## Usage

Run the application:

```
python main.py
```

### Command Line Options

- `--model-size {tiny,base,small,medium,large}`: Choose the Whisper model size (default: small)
- `--language LANGUAGE`: Specify a language code for transcription (default: auto-detect)
- `--no-warnings`: Suppress resource warning messages

## Model Sizes

- **tiny**: ~75MB, fastest, lowest accuracy
- **base**: ~142MB, fast, better accuracy than tiny
- **small**: ~461MB, slower, better accuracy than base
- **medium**: ~1.5GB, even slower, better accuracy than small
- **large**: ~3GB, slowest, highest accuracy

Choose the model size based on your system's capabilities and your requirements for transcription accuracy.

## Technical Notes

### Resource Management

The application includes a comprehensive resource management system (`cleanup_resources.py`) that handles:

1. Proper cleanup of multiprocessing resources
2. Temporary file removal
3. Thread termination

This system prevents resource leaks that can occur with Python's multiprocessing module, particularly on application exit. If you encounter any resource warnings, you can use the `--no-warnings` flag to suppress them.

### SSL Certificate Handling

The application includes a workaround for SSL certificate verification issues on macOS systems. This ensures that model downloads work correctly without manual intervention.

## Troubleshooting

If you encounter problems:

1. **Memory Issues**: Try using a smaller model with `--model-size tiny` or `--model-size base`
2. **Slow Transcription**: Smaller models are faster but less accurate; choose based on your needs
3. **Resource Warnings**: Use the `--no-warnings` flag to suppress multiprocessing resource warnings
4. **Model Download Errors**: The application will attempt to work around SSL issues, but if problems persist, check your internet connection

## License

[MIT License](LICENSE)