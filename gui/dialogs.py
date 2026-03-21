from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QPlainTextEdit, QDialogButtonBox
from game.config import cfg

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(500, 400)
        
        layout = QFormLayout(self)
        
        self.api_key_input = QLineEdit(cfg.openrouter_api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("API Key:", self.api_key_input)
        
        self.api_base_input = QLineEdit(cfg.api_base_url)
        layout.addRow("API Base URL:", self.api_base_input)
        
        self.models_input = QPlainTextEdit()
        self.models_input.setPlainText("\n".join(cfg.available_models))
        layout.addRow("可选模型(每行一个):", self.models_input)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
    def accept(self):
        cfg.openrouter_api_key = self.api_key_input.text().strip()
        cfg.api_base_url = self.api_base_input.text().strip() or "https://openrouter.ai/api/v1"
        models = [m.strip() for m in self.models_input.toPlainText().split('\n') if m.strip()]
        cfg.available_models = models
        cfg.save()
        super().accept()
