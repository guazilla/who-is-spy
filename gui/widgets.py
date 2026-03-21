import re
from PyQt6.QtWidgets import QPushButton, QFrame, QVBoxLayout, QLabel, QStyleOptionButton, QStyle
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QFontMetrics

class WordWrapButton(QPushButton):
    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Draw background and borders using the stylesheet/style
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        opt.text = ""  # Clear text so default style doesn't draw it
        self.style().drawControl(QStyle.ControlElement.CE_PushButton, opt, painter, self)
        
        # Draw custom dynamically scaled and word-wrapped text
        font = self.font()
        text = self.text()
        rect = self.rect().adjusted(5, 5, -5, -5)

        while True:
            fm = QFontMetrics(font)
            bounded_rect = fm.boundingRect(rect, Qt.TextFlag.TextWordWrap, text)
            if bounded_rect.height() <= rect.height() or font.pointSize() <= 6:
                break
            font.setPointSize(font.pointSize() - 1)
        
        painter.setFont(font)
        painter.setPen(opt.palette.buttonText().color())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text)

class MessagePanelWidget(QFrame):
    typing_finished_signal = pyqtSignal()

    def __init__(self, title, analysis, speech, action, role, border_hex, mw_scroll_bar):
        super().__init__()
        self.mw_scroll_bar = mw_scroll_bar
        self.setStyleSheet(f"""
            MessagePanelWidget {{
                border: 2px solid {border_hex};
                background-color: #44475A;
                margin-top: 5px;
                margin-bottom: 5px;
            }}
            QLabel {{ border: none; background: transparent; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title_lbl = QLabel(f"【{title}】")
        title_lbl.setStyleSheet(f"color: {border_hex}; font-weight: bold; margin-bottom: 5px;")
        layout.addWidget(title_lbl)
        
        self.content_lbl = QLabel("")
        self.content_lbl.setWordWrap(True)
        self.content_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.content_lbl)
        
        self.parts = []
        if analysis:
            self.parts.append((f"战术分析:\n{analysis}", "#F1FA8C", False))
        self.parts.append((f"发言: {speech}", "#F8F8F2", True))
        if action:
            self.parts.append((f"行动: {action}", "#FF79C6", True))
            
        self.current_part_idx = 0
        self.current_char_idx = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._type_next_char)

    def start_typing(self):
        # We can adjust speed here
        self.timer.start(30) 
        
    def _format_text_for_html(self, text):
        return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text).replace('\n', '<br>')

    def _type_next_char(self):
        if self.current_part_idx >= len(self.parts):
            self.timer.stop()
            if self.mw_scroll_bar:
                self.mw_scroll_bar.setValue(self.mw_scroll_bar.maximum())
            self.typing_finished_signal.emit()
            return
            
        text, color, is_bold = self.parts[self.current_part_idx]
        
        # Type chunk
        chunk_size = 2 # Type 2 characters at a time for snappiness
        self.current_char_idx += chunk_size
        
        if self.current_char_idx > len(text):
            self.current_char_idx = len(text)
            
        # Rebuild HTML
        html = ""
        for i in range(self.current_part_idx):
            t, c, b = self.parts[i]
            formatted_t = self._format_text_for_html(t)
            weight = 'bold' if b else 'normal'
            html += f'<div style="color: {c}; font-weight: {weight}; margin-bottom: 5px;">{formatted_t}</div>'
            
        # Current part
        current_t = text[:self.current_char_idx]
        formatted_t = self._format_text_for_html(current_t)
        weight = 'bold' if is_bold else 'normal'
        html += f'<div style="color: {color}; font-weight: {weight}; margin-bottom: 5px;">{formatted_t}</div>'
        
        self.content_lbl.setText(html)
        
        if self.mw_scroll_bar:
            self.mw_scroll_bar.setValue(self.mw_scroll_bar.maximum())
            
        if self.current_char_idx >= len(text):
            self.current_part_idx += 1
            self.current_char_idx = 0
