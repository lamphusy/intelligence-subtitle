from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, 
                             QPushButton, QLineEdit, QGroupBox, QButtonGroup, QMessageBox)
from PyQt5.QtCore import Qt
import os
import json

class LanguageSelectionDialog(QDialog):
    """Dialog for selecting subtitle language"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Subtitle Language Selection")
        self.resize(400, 250)
        self.api_key = ""
        self.selected_language = "auto"
        
        # Cache file path
        self.cache_file = os.path.join(os.path.expanduser("~"), ".intelligence_subtitle_cache.json")
        
        self.init_ui()
        self.load_cached_api_key()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Language selection
        lang_group = QGroupBox("Select Subtitle Language")
        lang_layout = QVBoxLayout()
        
        # Create radio buttons
        self.lang_group = QButtonGroup(self)
        
        self.auto_radio = QRadioButton("Auto Detect (Default)")
        self.auto_radio.setChecked(True)
        self.auto_radio.toggled.connect(self.on_language_selected)
        self.lang_group.addButton(self.auto_radio)
        lang_layout.addWidget(self.auto_radio)
        
        self.english_radio = QRadioButton("English")
        self.english_radio.toggled.connect(self.on_language_selected)
        self.lang_group.addButton(self.english_radio)
        lang_layout.addWidget(self.english_radio)
        
        self.vietnamese_radio = QRadioButton("Vietnamese")
        self.vietnamese_radio.toggled.connect(self.on_language_selected)
        self.lang_group.addButton(self.vietnamese_radio)
        lang_layout.addWidget(self.vietnamese_radio)
        
        lang_group.setLayout(lang_layout)
        layout.addWidget(lang_group)
        
        # API Key input
        self.api_group = QGroupBox("Gemini API Key (Required for translation)")
        self.api_group.setEnabled(False)
        api_layout = QVBoxLayout()
        
        self.api_key_label = QLabel("Enter your Gemini API Key:")
        api_layout.addWidget(self.api_key_label)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("Enter your Gemini API key here...")
        api_layout.addWidget(self.api_key_input)
        
        # Add checkbox for caching
        self.cache_checkbox = QRadioButton("Remember API key for next time")
        self.cache_checkbox.setChecked(True)
        api_layout.addWidget(self.cache_checkbox)
        
        # Add status label for cached key
        self.cache_status_label = QLabel("")
        self.cache_status_label.setStyleSheet("color: green; font-size: 10px;")
        api_layout.addWidget(self.cache_status_label)
        
        self.api_group.setLayout(api_layout)
        layout.addWidget(self.api_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.on_next_clicked)
        
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.next_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
    def has_cached_api_key(self):
        """Check if there's a cached API key available"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    return bool(cache_data.get('api_key', ''))
            return False
        except Exception:
            return False
    
    def load_cached_api_key(self):
        """Load cached API key if available"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    cached_key = cache_data.get('api_key', '')
                    if cached_key:
                        self.api_key_input.setText(cached_key)
                        self.cache_status_label.setText("✓ Using cached API key")
                        print("INFO: Loaded cached API key")
                    else:
                        self.cache_status_label.setText("")
            else:
                self.cache_status_label.setText("")
        except Exception as e:
            print(f"WARNING: Failed to load cached API key: {e}")
            self.cache_status_label.setText("")
    
    def save_cached_api_key(self, api_key):
        """Save API key to cache if user chose to remember it"""
        if not self.cache_checkbox.isChecked():
            return
            
        try:
            cache_data = {'api_key': api_key}
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f)
            print("INFO: Cached API key")
        except Exception as e:
            print(f"WARNING: Failed to cache API key: {e}")
    
    def clear_cached_api_key(self):
        """Clear cached API key"""
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
                print("INFO: Cleared cached API key")
        except Exception as e:
            print(f"WARNING: Failed to clear cached API key: {e}")
    
    def on_language_selected(self):
        """Enable/disable API key input based on language selection"""
        if self.auto_radio.isChecked():
            self.api_group.setEnabled(False)
        else:
            self.api_group.setEnabled(True)
    
    def on_next_clicked(self):
        """Validate and accept the dialog"""
        if self.auto_radio.isChecked():
            self.selected_language = "auto"
            self.accept()
        else:
            # Check if API key is provided for translation
            api_key = self.api_key_input.text().strip()
            if not api_key:
                QMessageBox.warning(self, "API Key Required", 
                                  "Please enter a Gemini API Key for translation.")
                return
            
            self.api_key = api_key
            
            # Cache the API key if user chose to remember it
            self.save_cached_api_key(api_key)
            
            if self.english_radio.isChecked():
                self.selected_language = "english"
            elif self.vietnamese_radio.isChecked():
                self.selected_language = "vietnamese"
                
            self.accept()
    
    def get_selection(self):
        """Return the selected language and API key"""
        return {
            "language": self.selected_language,
            "api_key": self.api_key
        } 