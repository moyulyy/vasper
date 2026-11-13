"""后台线程：在 QThread 中消费 LLM 流式响应，避免阻塞界面。"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from . import llm


class ChatWorker(QThread):
    delta = pyqtSignal(str)
    reasoning = pyqtSignal(str)
    completed = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, payload: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self._payload = payload
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    @property
    def stopped(self) -> bool:
        return self._stop

    def run(self) -> None:  # noqa: D401
        try:
            for event in llm.iter_chat(self._payload, should_stop=lambda: self._stop):
                if self._stop:
                    break
                if "delta" in event:
                    self.delta.emit(str(event["delta"]))
                elif "reasoning" in event:
                    self.reasoning.emit(str(event["reasoning"]))
                elif "error" in event:
                    self.failed.emit(str(event["error"]))
                    return
                elif event.get("done"):
                    self.completed.emit(event)
                    return
            self.completed.emit({"done": True, "stopped": True})
        except Exception as exc:  # pragma: no cover - 网络异常兜底
            self.failed.emit(f"{type(exc).__name__}: {exc}")
