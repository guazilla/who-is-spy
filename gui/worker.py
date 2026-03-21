import threading
import re
from PyQt6.QtCore import pyqtSignal, QObject
from game.engine import GameEngine

class WorkerSignals(QObject):
    log_signal = pyqtSignal(str, str, bool)
    status_signal = pyqtSignal(str)
    panel_signal = pyqtSignal(str, str, str, str, str)
    finished_signal = pyqtSignal()
    ask_retry_signal = pyqtSignal(str, int)
    init_signal = pyqtSignal(list)
    highlight_signal = pyqtSignal(int)

class GameWorker(QObject):
    def __init__(self, civilian_word, spy_word, selected_models):
        super().__init__()
        self.civilian_word = civilian_word
        self.spy_word = spy_word
        self.selected_models = selected_models
        self.signals = WorkerSignals()
        self.wait_for_retry_cond = threading.Condition()
        self.retry_decision = False
        self.engine = None

    def run(self):
        self.engine = GameEngine(
            log_cb=self._log_callback,
            status_cb=self._status_callback,
            panel_cb=self._panel_callback,
            ask_retry_cb=self._ask_retry_callback,
            init_cb=self._init_callback
        )
        try:
            self.engine.run(self.civilian_word, self.spy_word, self.selected_models)
        except Exception as e:
            self._log_callback(f"游戏发生异常: {str(e)}", "error", True)
        finally:
            self.signals.finished_signal.emit()

    def stop(self):
        if self.engine:
            self.engine.stop()
        with self.wait_for_retry_cond:
            self.wait_for_retry_cond.notify_all()

    def _init_callback(self, players):
        self.signals.init_signal.emit(players)

    def _log_callback(self, msg, level="info", bold=False):
        self.signals.log_signal.emit(msg, level, bold)

    def _status_callback(self, msg):
        match = re.search(r'等待 (\d+) 号玩家', msg)
        if match:
            self.signals.highlight_signal.emit(int(match.group(1)))
        elif not msg:
            self.signals.highlight_signal.emit(0)
        self.signals.status_signal.emit(msg)

    def _panel_callback(self, title, analysis, speech, action, role="player"):
        self.signals.panel_signal.emit(title, analysis, speech, action, role)

    def _ask_retry_callback(self, error_msg, player_id):
        self.retry_decision = False
        self.signals.ask_retry_signal.emit(error_msg, player_id)
        with self.wait_for_retry_cond:
            self.wait_for_retry_cond.wait()
        return self.retry_decision

    def set_retry_decision(self, decision):
        with self.wait_for_retry_cond:
            self.retry_decision = decision
            self.wait_for_retry_cond.notify()
