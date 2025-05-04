from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, 
                             QPushButton, QLineEdit, QGroupBox, QButtonGroup, QMessageBox)
from PyQt5.QtCore import Qt

class LanguageSelectionDialog(QDialog):
    """Dialog for selecting subtitle language"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Subtitle Language Selection")
        self.resize(400, 250)
        self.api_key = ""
        self.selected_language = "auto"
        
        self.init_ui()
        
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
        self.api_key_input.setPlaceholderText("Paste your Gemini API Key here")
        api_layout.addWidget(self.api_key_input)
        
        self.api_key_info = QLabel("You can get a Gemini API Key from <a href='https://makersuite.google.com/app/apikey'>Google AI Studio</a>")
        self.api_key_info.setOpenExternalLinks(True)
        api_layout.addWidget(self.api_key_info)
        
        self.api_group.setLayout(api_layout)
        layout.addWidget(self.api_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.on_next_clicked)
        self.next_btn.setDefault(True)
        button_layout.addWidget(self.next_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def on_language_selected(self):
        """Handle language selection changes"""
        # Only enable API key input if a specific language is selected
        self.api_group.setEnabled(not self.auto_radio.isChecked())
    
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