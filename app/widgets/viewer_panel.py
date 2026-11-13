"""3D 结构面板：QWebEngineView + 3Dmol，工具栏与 Python 侧桥接。"""

from __future__ import annotations

import json

from PyQt6.QtCore import QObject, Qt, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from .. import config, icons, structures, theme
from .components import Card, Divider, IconButton, IconTile


class ViewerBridge(QObject):
    ready = pyqtSignal()
    state_changed = pyqtSignal(dict)
    picked = pyqtSignal(dict)
    failed = pyqtSignal(str)

    @pyqtSlot()
    def onReady(self) -> None:  # noqa: N802
        self.ready.emit()

    @pyqtSlot(str)
    def onState(self, payload: str) -> None:  # noqa: N802
        try:
            self.state_changed.emit(json.loads(payload))
        except Exception:
            pass

    @pyqtSlot(str)
    def onPick(self, payload: str) -> None:  # noqa: N802
        try:
            self.picked.emit(json.loads(payload))
        except Exception:
            pass

    @pyqtSlot(str)
    def onError(self, message: str) -> None:  # noqa: N802
        self.failed.emit(message)


class ViewerPanel(Card):
    notify = pyqtSignal(str, str)
    focus_requested = pyqtSignal(bool)
    structure_opened = pyqtSignal(str, str)
    picked = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, object_name="Panel")
        self._web_ready = False
        self._pending: dict | None = None
        self._current: dict | None = None
        self._theme_mode = "dark"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        self._tile = IconTile("atom", size=38, radius=11, icon_size=21)
        header.addWidget(self._tile)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        self._title = QLabel("未打开结构")
        self._title.setObjectName("Title")
        self._title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._meta = QLabel("从左侧文件树选择 CIF / XYZ / POSCAR")
        self._meta.setObjectName("Subtitle")
        self._meta.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._title_full = "未打开结构"
        self._meta_full = "从左侧文件树选择 CIF / XYZ / POSCAR"
        titles.addWidget(self._title)
        titles.addWidget(self._meta)
        header.addLayout(titles, 1)

        self._cell_button = IconButton("cube", "显示/隐藏晶胞", diameter=32, icon_size=17)
        self._cell_button.setCheckable(True)
        self._cell_button.setChecked(True)
        self._cell_button.setEnabled(False)
        self._cell_button.toggled.connect(self._on_cell)
        self._labels_button = IconButton("tag", "显示元素标签", diameter=32, icon_size=17)
        self._labels_button.setCheckable(True)
        self._labels_button.toggled.connect(self._on_labels)
        self._measure_button = IconButton("ruler", "测量原子间距", diameter=32, icon_size=17)
        self._measure_button.setCheckable(True)
        self._measure_button.toggled.connect(self._on_measure)
        self._reset_button = IconButton("rotate", "重置视角", diameter=32, icon_size=17)
        self._reset_button.clicked.connect(self._on_reset)
        self._focus_button = IconButton("maximize", "专注模式", diameter=32, icon_size=17)
        self._focus_button.setCheckable(True)
        self._focus_button.toggled.connect(self._on_focus)
        for button in (
            self._cell_button, self._labels_button, self._measure_button,
            self._reset_button, self._focus_button,
        ):
            header.addWidget(button)
        layout.addLayout(header)

        self._view = QWebEngineView(self)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._view.page().setBackgroundColor(QColor("#17191F"))
        self._view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._view.setMinimumHeight(280)
        settings = self._view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, False)

        self._bridge = ViewerBridge(self)
        self._bridge.ready.connect(self._on_web_ready)
        self._bridge.state_changed.connect(self._on_state)
        self._bridge.picked.connect(self._on_picked)
        self._bridge.failed.connect(self._on_js_error)

        self._channel = QWebChannel(self._view.page())
        self._channel.registerObject("bridge", self._bridge)
        self._view.page().setWebChannel(self._channel)
        self._view.loadFinished.connect(self._on_load_finished)
        self._view.load(QUrl.fromLocalFile(str(config.PROJECT_ROOT / "assets" / "viewer.html")))
        layout.addWidget(self._view, 1)

    # ------------------------------------------------------------------ 对外
    def open_structure(self, rel: str, name: str) -> bool:
        try:
            payload = structures.load_structure(rel)
        except Exception as exc:
            self.notify.emit(str(exc), "error")
            return False
        self._current = payload
        self._title_full = name or payload["name"]
        self._title.setToolTip(self._title_full)
        self._elide_header()
        self._tile.set_icon("atom")
        has_cell = bool(payload.get("cell"))
        self._cell_button.setEnabled(has_cell)
        if not has_cell:
            self._cell_button.setChecked(False)
        else:
            self._cell_button.setChecked(True)
        self._labels_button.setChecked(False)
        self._measure_button.setChecked(False)
        self._update_meta(payload)
        message = {
            "name": payload["name"],
            "format": payload["format"],
            "content": payload["content"],
            "atoms": payload["atoms"],
            "elements": payload["elements"],
            "hasCell": has_cell,
        }
        self._pending = message
        if self._web_ready:
            self._flush()
        self.structure_opened.emit(rel, name or payload["name"])
        return True

    def clear(self) -> None:
        self._current = None
        self._pending = None
        self._title_full = "未打开结构"
        self._meta_full = "从左侧文件树选择 CIF / XYZ / POSCAR"
        self._title.setToolTip("")
        self._meta.setToolTip("")
        self._elide_header()
        if self._web_ready:
            self._run("VasperViewer.clear()")

    def set_theme(self, mode: str) -> None:
        self._theme_mode = mode
        if self._web_ready:
            self._run(f"VasperViewer.setTheme({json.dumps(mode)})")
        self._tile.set_icon("atom")
        for button in (
            self._cell_button, self._labels_button, self._measure_button,
            self._reset_button, self._focus_button,
        ):
            button.update()

    def set_focus(self, focused: bool) -> None:
        self._focus_button.blockSignals(True)
        self._focus_button.setChecked(focused)
        self._focus_button.set_icon("minimize" if focused else "maximize")
        self._focus_button.setToolTip("退出专注模式" if focused else "专注模式")
        self._focus_button.blockSignals(False)

    def current_name(self) -> str:
        return (self._current or {}).get("name", "")

    # ------------------------------------------------------------------ 内部
    def _update_meta(self, payload: dict | None) -> None:
        if not payload:
            return
        fmt = (payload.get("format") or "").upper()
        atoms = payload.get("atoms") or 0
        elements = payload.get("elements") or {}
        top = " · ".join(
            f"{symbol} {count}"
            for symbol, count in sorted(elements.items(), key=lambda item: -item[1])[:3]
        )
        parts = [fmt, f"{atoms} 原子"]
        if top:
            parts.append(top)
        if payload.get("cell"):
            cell = payload["cell"]
            parts.append(
                f"a={cell['a']:.2f} b={cell['b']:.2f} c={cell['c']:.2f} Å"
            )
        self._meta_full = " · ".join(parts)
        self._meta.setToolTip(self._meta_full)
        self._elide_header()

    def _elide_header(self) -> None:
        available = max(120, self.width() - 310)
        self._title.setText(
            self._title.fontMetrics().elidedText(
                self._title_full, Qt.TextElideMode.ElideMiddle, available
            )
        )
        self._meta.setText(
            self._meta.fontMetrics().elidedText(
                self._meta_full, Qt.TextElideMode.ElideRight, available
            )
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "_title_full"):
            self._elide_header()

    def _run(self, script: str) -> None:
        self._view.page().runJavaScript(script)

    def _flush(self) -> None:
        if not self._pending or not self._web_ready:
            return
        payload = json.dumps(self._pending, ensure_ascii=False)
        self._pending = None
        self._run(f"window.VasperViewer && VasperViewer.load({payload})")

    def _on_load_finished(self, ok: bool) -> None:
        """页面脚本就绪后立即下发待显示结构，不必等待 QWebChannel 建立。"""
        if not ok or self._web_ready:
            return

        def handle(state):
            if state and not self._web_ready:
                self._web_ready = True
                self._run(f"VasperViewer.setTheme({json.dumps(self._theme_mode)})")
                self._flush()

        self._view.page().runJavaScript(
            "typeof VasperViewer !== 'undefined' && !!VasperViewer.isReady()", handle
        )

    def _on_web_ready(self) -> None:
        self._web_ready = True
        self._run(f"VasperViewer.setTheme({json.dumps(self._theme_mode)})")
        if self._pending:
            self._flush()

    def _on_state(self, payload: dict) -> None:
        if "hasCell" in payload:
            self._cell_button.setEnabled(bool(payload["hasCell"]))

    def _on_picked(self, payload: dict) -> None:
        self.picked.emit(payload)

    def _on_js_error(self, message: str) -> None:
        import sys

        print(f"[3D viewer] {message}", file=sys.stderr)
        first = (message or "未知错误").splitlines()[0][:180]
        self.notify.emit(f"3D 渲染失败：{first}", "error")

    def _on_cell(self, checked: bool) -> None:
        self._run(f"VasperViewer.setCell({json.dumps(bool(checked))})")

    def _on_labels(self, checked: bool) -> None:
        self._run(f"VasperViewer.setLabels({json.dumps(bool(checked))})")

    def _on_measure(self, checked: bool) -> None:
        self._run(f"VasperViewer.setMeasure({json.dumps(bool(checked))})")

    def _on_reset(self) -> None:
        self._run("VasperViewer.reset()")

    def _on_focus(self, focused: bool) -> None:
        self._focus_button.set_icon("minimize" if focused else "maximize")
        self._focus_button.setToolTip("退出专注模式" if focused else "专注模式")
        self.focus_requested.emit(focused)

