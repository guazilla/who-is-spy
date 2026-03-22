import threading
import re
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QFrame, QMessageBox, QMenu, QScrollArea)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QTextCursor, QAction

from game.config import cfg
from .widgets import WordWrapButton, MessagePanelWidget
from .dialogs import SettingsDialog
from .worker import GameWorker

class WhoIsSpyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("谁是卧底 AI 法官系统")
        self.resize(800, 700)
        
        self.level_map = {
            "success": "#50FA7B",
            "info_dim": "#6272A4",
            "highlight": "#F1FA8C",
            "error": "#FF5555",
            "error_dim": "#FF5555",
            "highlight_dim": "#F1FA8C",
            "info": "#FFFFFF",
            "critical": "#BD93F9"
        }
        self.role_map = {
            "player": "#8BE9FD",
            "review": "#50FA7B"
        }
        
        self.selected_models_map = {i: None for i in range(1, 5)}
        self.worker = None
        self.ui_queue = []
        self.is_typing = False
        self.init_ui()
        QTimer.singleShot(0, self.check_config_on_start)

    def check_config_on_start(self):
        if not cfg.openrouter_api_key:
            QMessageBox.information(self, "欢迎", "首次运行请先配置 API Key。")
            self.open_settings()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Left Panel (Player List)
        self.left_panel = QFrame()
        self.left_panel.setFixedWidth(250)
        self.left_panel.setStyleSheet("background-color: #383A59; padding: 10px;")
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        title_label = QLabel("玩家列表")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        left_layout.addWidget(title_label)
        
        self.player_widgets = {}
        self.player_colors = {
            1: "#FF79C6",  # Pink
            2: "#50FA7B",  # Green
            3: "#8BE9FD",  # Cyan
            4: "#BD93F9"   # Purple
        }
        for i in range(1, 5):
            btn = WordWrapButton(f"玩家 {i}\n(点击选择模型)")
            bg_color = self.player_colors[i]
            btn.setStyleSheet(f"background-color: {bg_color}; color: #282A36; padding: 10px; border-radius: 10px; margin-bottom: 5px; text-align: center; font-weight: bold;")
            btn.clicked.connect(lambda _, pid=i: self.select_model_for_player(pid))
            left_layout.addWidget(btn)
            self.player_widgets[i] = btn
            if i < 4:
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.HLine)
                separator.setFrameShadow(QFrame.Shadow.Sunken)
                separator.setStyleSheet("color: #6272A4;")
                left_layout.addWidget(separator)
        main_layout.addWidget(self.left_panel)
        
        # Right Panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Control Panel
        config_frame = QFrame()
        config_layout = QHBoxLayout(config_frame)
        config_layout.addWidget(QLabel("平民词:"))
        self.civilian_input = QLineEdit()
        config_layout.addWidget(self.civilian_input)
        config_layout.addWidget(QLabel("卧底词:"))
        self.spy_input = QLineEdit()
        config_layout.addWidget(self.spy_input)
        
        self.start_btn = QPushButton("开始游戏")
        self.start_btn.clicked.connect(self.start_game)
        config_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("终止游戏")
        self.stop_btn.clicked.connect(self.stop_game)
        self.stop_btn.setEnabled(False)
        config_layout.addWidget(self.stop_btn)
        
        self.settings_btn = QPushButton("设置")
        self.settings_btn.clicked.connect(self.open_settings)
        config_layout.addWidget(self.settings_btn)
        
        right_layout.addWidget(config_frame)
        
        # Log Area
        self.status_label = QLabel("准备就绪")
        right_layout.addWidget(self.status_label)
        
        self.log_scroll = QScrollArea()
        self.log_scroll.setWidgetResizable(True)
        self.log_scroll.setStyleSheet("QScrollArea { border: none; background-color: #22222E; } QWidget#log_container { background-color: #22222E; }")
        
        self.log_container = QWidget()
        self.log_container.setObjectName("log_container")
        self.log_layout = QVBoxLayout(self.log_container)
        self.log_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.log_scroll.setWidget(self.log_container)
        right_layout.addWidget(self.log_scroll)
        
        main_layout.addWidget(right_panel)
        
        self.setStyleSheet("""
        QMainWindow, QWidget { background-color: #282A36; }
        QLabel { color: #F8F8F2; font-size: 14px; }
        QLineEdit { background-color: #44475A; color: #F8F8F2; border: 1px solid #6272A4; padding: 8px; border-radius: 4px; }
        QPushButton { background-color: #6272A4; color: #F8F8F2; border: none; padding: 8px 15px; font-weight: bold; border-radius: 4px; }
        QPushButton:hover { background-color: #50FA7B; color: #282A36; }
        QPushButton:disabled { background-color: #44475A; color: #6272A4; }
        #stop_btn { background-color: #FF5555; }
        QTextEdit { background-color: #22222E; color: #F8F8F2; font-family: monospace; }
        QMenu { background-color: #44475A; color: #F8F8F2; border: 1px solid #282A36; }
        QMenu::item:selected { background-color: #6272A4; }
        """)

    def select_model_for_player(self, player_id):
        menu = QMenu(self)
        for model_name in cfg.available_models:
            action = QAction(model_name, self)
            action.triggered.connect(lambda _, p=player_id, m=model_name: self.set_player_model(p, m))
            menu.addAction(action)
        button = self.player_widgets[player_id]
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def set_player_model(self, player_id, model_name):
        self.selected_models_map[player_id] = model_name
        self.player_widgets[player_id].setText(f"玩家 {player_id}\n({model_name})")

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def start_game(self):
        selected_models = [model for model in self.selected_models_map.values() if model]
        if len(selected_models) != 4:
            QMessageBox.warning(self, "模型选择错误", "请为全部4名玩家选择模型！")
            return
        civ_word = self.civilian_input.text().strip()
        spy_word = self.spy_input.text().strip()
        if not civ_word or not spy_word:
            self.append_log("错误: 请先输入平民词和卧底词！", "error", True)
            return
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.civilian_input.setEnabled(False)
        self.spy_input.setEnabled(False)
        for btn in self.player_widgets.values(): btn.setEnabled(False)
        self.ui_queue.clear()
        self.is_typing = False
        while self.log_layout.count():
            item = self.log_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.status_label.setText("游戏开始...")
        for i, btn in self.player_widgets.items():
            btn.setText(f"玩家 {i}\n(等待分配...)")
        
        # 实例化 GameWorker 并启动 QThread
        self.worker = GameWorker(civ_word, spy_word, selected_models)
        self.worker.log_signal.connect(self.append_log)
        self.worker.status_signal.connect(self.update_status)
        self.worker.panel_signal.connect(self.append_panel)
        self.worker.finished_signal.connect(self.game_finished)
        self.worker.ask_retry_signal.connect(self.ask_retry)
        self.worker.init_signal.connect(self.update_players)
        self.worker.highlight_signal.connect(self.highlight_player)
        self.worker.start()

    def stop_game(self):
        if self.worker:
            self.worker.stop()
            self.append_log("正在终止游戏...", "highlight", True)
            self.stop_btn.setEnabled(False)

    def update_players(self, players):
        for pid, model in players:
            if pid in self.player_widgets:
                self.player_widgets[pid].setText(f"玩家 {pid}\n({model})")

    def highlight_player(self, active_pid):
        for pid, btn in self.player_widgets.items():
            base_color = self.player_colors.get(pid, "#44475A")
            style_sheet = "background-color: {bg}; color: #282A36; padding: 10px; border-radius: 10px; margin-bottom: 5px; font-weight: bold; text-align: center; border: {border};"
            if pid == active_pid:
                btn.setStyleSheet(style_sheet.format(bg="#F1FA8C", border="3px solid #FFFFFF"))
            else:
                btn.setStyleSheet(style_sheet.format(bg=base_color, border="none"))

    def ask_retry(self, error_msg, player_id):
        reply = QMessageBox.question(self, f"玩家 {player_id} 出错", f"调用 API 失败:\n{error_msg}\n\n是否重试该玩家发言？", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
        if self.worker:
            self.worker.set_retry_decision(reply == QMessageBox.StandardButton.Yes)

    def update_status(self, msg):
        self.status_label.setText(msg)

    def append_log(self, msg, level="info", bold=False):
        self.ui_queue.append(('log', msg, level, bold))
        self._process_ui_queue()

    def _do_append_log(self, msg, level, bold):
        hex_color = self.level_map.get(level, "#FFFFFF")
        weight = "bold" if bold else "normal"
        lbl = QLabel(f'<span style="color: {hex_color}; font-weight: {weight};">{msg}</span>')
        lbl.setWordWrap(True)
        lbl.setStyleSheet("background: transparent;")
        self.log_layout.addWidget(lbl)
        
        # Scroll to bottom
        bar = self.log_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def append_panel(self, title, analysis, speech, action, role="player"):
        self.ui_queue.append(('panel', title, analysis, speech, action, role))
        self._process_ui_queue()

    def _do_append_panel(self, title, analysis, speech, action, role):
        self.is_typing = True
        border_hex = self.role_map.get(role, "#6272A4")
        panel = MessagePanelWidget(title, analysis, speech, action, role, border_hex, self.log_scroll.verticalScrollBar())
        panel.typing_finished_signal.connect(self._on_panel_typing_finished)
        self.log_layout.addWidget(panel)
        panel.start_typing()

    def _on_panel_typing_finished(self):
        self.is_typing = False
        self._process_ui_queue()

    def _process_ui_queue(self):
        if self.is_typing:
            return
        if not self.ui_queue:
            return
            
        item = self.ui_queue.pop(0)
        if item[0] == 'log':
            _, msg, level, bold = item
            self._do_append_log(msg, level, bold)
            self._process_ui_queue()
        elif item[0] == 'panel':
            _, title, analysis, speech, action, role = item
            self._do_append_panel(title, analysis, speech, action, role)

    def game_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.civilian_input.setEnabled(True)
        self.spy_input.setEnabled(True)
        self.selected_models_map = {i: None for i in range(1, 5)}
        for i, btn in self.player_widgets.items():
            btn.setEnabled(True)
            btn.setText(f"玩家 {i}\n(点击选择模型)")
        self.status_label.setText("游戏结束，可以开始新的一局")
        self.highlight_player(0)
