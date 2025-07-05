import os
import json
import requests
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

class TranslationError(Exception):
    """Exception raised for translation errors"""
    pass

class GeminiTranslator(QObject):
    """Class for translating text using Google's Gemini API"""
    
    # Signals
    translation_progress = pyqtSignal(int, int)  # current, total
    translation_complete = pyqtSignal(list)      # translated segments
    translation_error = pyqtSignal(str)          # error message
    
    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        self._running = True
        
    def stop(self):
        """Signal the translator to stop processing"""
        self._running = False
    
    @pyqtSlot(list, str)
    def translate_segments(self, segments, target_language):
        """
        Translate subtitle segments to the target language in batches
        
        Args:
            segments: List of segments with 'text' field
            target_language: Target language ('english' or 'vietnamese')
        """
        if not segments:
            self.translation_error.emit("No segments to translate")
            return
            
        try:
            # Emit initial progress
            self.translation_progress.emit(0, 100)
            
            # Filter out empty segments or music notations
            valid_segments = []
            segment_texts = []
            for segment in segments:
                text = segment.get('text', '').strip()
                if not text or text in ['(Music)', '(Âm nhạc)']:
                    # Keep original for non-translatable segments
                    valid_segments.append(segment.copy())
                else:
                    # Add to segments that need translation
                    valid_segments.append(segment)
                    segment_texts.append(text)
            
            if not segment_texts:
                # No segments to translate
                self.translation_complete.emit(segments)
                return
                
            # Create a special delimiter that's unlikely to appear in the text
            delimiter = "|||SEP|||"
            
            # Divide into batches of maximum 20 segments to avoid token limits and mismatches
            batch_size = 20
            batches = []
            
            for i in range(0, len(segment_texts), batch_size):
                batch = segment_texts[i:i + batch_size]
                batches.append(batch)
            
            total_batches = len(batches)
            translated_texts_all = []
            
            # Function to translate a single batch recursively
            def translate_batch(batch):
                # Fallback if signaled to stop
                if not self._running:
                    return list(batch)
                # Combine batch text
                combined_text = delimiter.join(batch)
                # Build prompt
                if target_language.lower() == "english":
                    prompt = (f"Translate the following subtitles from their original language to English. "
                              f"Each subtitle segment is separated by {delimiter}. "
                              "Maintain the same number of segments in your response, separated by the same delimiter. "
                              "Only translate the content, don't add any explanations.\n\nSubtitles:\n" + combined_text)
                elif target_language.lower() == "vietnamese":
                    prompt = (f"Translate the following subtitles from their original language to Vietnamese. "
                              f"Each subtitle segment is separated by {delimiter}. "
                              "Maintain the same number of segments in your response, separated by the same delimiter. "
                              "Only translate the content, don't add any explanations.\n\nSubtitles:\n" + combined_text)
                else:
                    raise TranslationError(f"Unsupported target language: {target_language}")
                # Call API
                try:
                    translated_combined = self._call_api(prompt)
                    translated = translated_combined.split(delimiter)
                    if len(translated) == len(batch):
                        return translated
                except Exception as e:
                    pass
                # If mismatch or error and batch > 1, split in half
                if len(batch) <= 1:
                    return list(batch)
                mid = len(batch) // 2
                left = translate_batch(batch[:mid])
                right = translate_batch(batch[mid:])
                return left + right

            # Translate each batch and collect results
            for batch_index, batch in enumerate(batches):
                # Report progress
                progress = int((batch_index / total_batches) * 100)
                self.translation_progress.emit(progress, 100)
                # Extract plain texts to translate
                texts = list(batch)
                # Get translated list
                translated_batch = translate_batch(texts)
                # Ensure final count matches
                if len(translated_batch) < len(texts):
                    # Pad with original if missing
                    for i in range(len(translated_batch), len(texts)):
                        translated_batch.append(texts[i])
                elif len(translated_batch) > len(texts):
                    translated_batch = translated_batch[:len(texts)]
                # Add to overall translations
                translated_texts_all.extend(translated_batch)
            
            # Create translated segments
            translated_segments = []
            valid_segment_index = 0
            
            for original_segment in segments:
                text = original_segment.get('text', '').strip()
                if not text or text in ['(Music)', '(Âm nhạc)']:
                    # Keep original for non-translatable segments
                    translated_segments.append(original_segment.copy())
                else:
                    # Use translated text
                    new_segment = original_segment.copy()
                    if valid_segment_index < len(translated_texts_all):
                        new_segment['text'] = translated_texts_all[valid_segment_index].strip()
                    else:
                        # Fallback to original if we ran out of translations
                        new_segment['text'] = text
                    translated_segments.append(new_segment)
                    valid_segment_index += 1
            
            # Verify we produced the same number of segments
            if len(translated_segments) != len(segments):
                # Fallback: emit error and return original segments
                self.translation_error.emit("Translation failed: segment count mismatch")
                return
            
            # Emit completion signal
            self.translation_progress.emit(100, 100)
            self.translation_complete.emit(translated_segments)
            
        except Exception as e:
            self.translation_error.emit(f"Translation error: {str(e)}")
    
    def _call_api(self, prompt):
        """
        Call the Gemini API with the given prompt
        
        Args:
            prompt: The full prompt text
            
        Returns:
            Translated combined text
        """
        # Prepare API request
        url = f"{self.base_url}?key={self.api_key}"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "topK": 1,
                "topP": 0.95,
                "maxOutputTokens": 8192
            }
        }
        
        # Send API request
        response = requests.post(url, headers=headers, json=data)
        
        # Handle API errors
        if response.status_code != 200:
            error_msg = f"API Error ({response.status_code}): {response.text}"
            raise TranslationError(error_msg)
            
        # Parse response
        try:
            response_data = response.json()
            
            # Extract translated text from the response
            if 'candidates' in response_data and response_data['candidates']:
                candidate = response_data['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    parts = candidate['content']['parts']
                    if parts and 'text' in parts[0]:
                        return parts[0]['text'].strip()
            
            # If we couldn't find the expected structure
            raise TranslationError(f"Unexpected API response format: {response_data}")
            
        except json.JSONDecodeError:
            raise TranslationError("Invalid JSON response from API")
            
        except Exception as e:
            raise TranslationError(f"Error processing API response: {str(e)}") 