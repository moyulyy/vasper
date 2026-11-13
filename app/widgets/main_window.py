"""主窗口：顶栏、可折叠文件面板、3D 查看器与聊天/会话区。"""

from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve, QEvent, QPropertyAnimation, QSize, Qt, QTimer,
)
from PyQt6.QtGui import QFont, QGuiApplication, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLayout, QMainWindow,
    QPushButton, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from .. import config, icons, sessions, theme
from .chat_panel import ChatPanel
from .components import IconButton, RootBackground, Toast
from .file_panel import FilePanel
from .session_panel import SessionPanel
from .settings_dialog import SettingsDialog
from .sheets import ConfirmSheet
from .viewer_panel import ViewerPanel

FILES_WIDTH = 274
SESSIONS_WIDTH = 286
WINDOW_MARGIN = 12


class WindowBar(QWidget):
    """无边框窗口的拖动区域。"""

    def __init__(self, window: "MainWindow") -> None:
        super().__init__()
        self._window = window
        self._drag = None
        self.setMouseTracking(True)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        handle = self._window.windowHandle()
        if handle is not None and handle.startSystemMove():
            event.accept()
            return
        self._drag = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._drag)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._window.toggle_maximize()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Vasper · Materials Copilot")
        self.setWindowIcon(QIcon(icons.pixmap("atom", "#0A84FF", 64, 1.8)))
        self.setMinimumSize(1180, 660)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._settings = config.load_settings()
        self._files_open = bool(self._settings.get("ui", {}).get("files_open", False))
        self._sessions_open = bool(self._settings.get("ui", {}).get("sessions_open", False))
        self._focus_active = False
        self._focus_prev: tuple[bool, bool] = (True, False)
        self._animations: dict[str, QPropertyAnimation] = {}

        central = RootBackground()
        central.set_floating(True)
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(WINDOW_MARGIN, WINDOW_MARGIN, WINDOW_MARGIN, WINDOW_MARGIN)
        outer.setSpacing(0)
        self._outer_layout = outer

        outer.addWidget(self._build_topbar())
        body = QWidget()
        body.setObjectName("Body")
        self._body = QHBoxLayout(body)
        self._body.setContentsMargins(16, 2, 16, 16)
        self._body.setSpacing(12)

        self.files = FilePanel()
        self.files.layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.files.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._body.addWidget(self.files)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(7)
        self.viewer = ViewerPanel()
        self.chat = ChatPanel()
        self.splitter.addWidget(self.viewer)
        self.splitter.addWidget(self.chat)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes([880, 480])
        self._body.addWidget(self.splitter, 1)

        self.session_panel = SessionPanel()
        self.session_panel.layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.session_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._body.addWidget(self.session_panel)
        outer.addWidget(body, 1)

        self._toast = Toast(self)
        self._toast.raise_()

        self._wire()
        self._apply_initial_widths()
        self._apply_theme()
        self._refresh_sessions()
        self._restore_last_session()
        self._restore_geometry()
        self.chat.set_model_name(config.llm_config().get("model", ""))
        self._update_workspace_button()
        QTimer.singleShot(250, self._toast.reposition)


    # ------------------------------------------------------------------ 顶栏
    def _build_topbar(self) -> QWidget:
        bar = WindowBar(self)
        bar.setObjectName("TopBar")
        bar.setFixedHeight(58)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 7, 16, 3)
        layout.setSpacing(8)

        self._files_button = IconButton("panel-left", "显示/隐藏文件管理器  Ctrl+B", diameter=34, icon_size=18)
        self._files_button.setCheckable(True)
        self._files_button.setChecked(self._files_open)
        self._files_button.clicked.connect(self.toggle_files)
        layout.addWidget(self._files_button)

        self._workspace_button = QPushButton()
        self._workspace_button.setProperty("variant", "chip")
        self._workspace_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._workspace_button.setToolTip("切换工作区")
        self._workspace_button.setIcon(icons.icon("folder", theme.current().text_soft, 14))
        self._workspace_button.setIconSize(QSize(14, 14))
        self._workspace_button.setMaximumWidth(260)
        self._workspace_button.clicked.connect(self.open_settings)
        layout.addWidget(self._workspace_button)

        layout.addStretch(1)

        self._sessions_button = IconButton("panel-right", "会话管理  Ctrl+Shift+B", diameter=34, icon_size=18)
        self._sessions_button.setCheckable(True)
        self._sessions_button.setChecked(self._sessions_open)
        self._sessions_button.clicked.connect(self.toggle_sessions)
        layout.addWidget(self._sessions_button)

        self._settings_button = IconButton("settings", "设置  Ctrl+,", diameter=34, icon_size=18)
        self._settings_button.clicked.connect(self.open_settings)
        layout.addWidget(self._settings_button)

        layout.addSpacing(6)
        self._min_button = IconButton("minus", "最小化", diameter=28, icon_size=14)
        self._min_button.clicked.connect(self.showMinimized)
        layout.addWidget(self._min_button)
        self._max_button = IconButton("maximize", "最大化", diameter=28, icon_size=14)
        self._max_button.clicked.connect(self.toggle_maximize)
        layout.addWidget(self._max_button)
        self._close_button = IconButton("x", "关闭", diameter=28, icon_size=14)
        self._close_button.clicked.connect(self.close)
        layout.addWidget(self._close_button)
        return bar

    # ------------------------------------------------------------------ 连接
    def _wire(self) -> None:
        self.files.structure_selected.connect(self.open_structure)
        self.files.notify.connect(self.toast)
        self.viewer.notify.connect(self.toast)
        self.viewer.focus_requested.connect(self.set_focus)
        self.chat.notify.connect(self.toast)
        self.chat.sessions_changed.connect(self._refresh_sessions)
        self.chat.request_sessions.connect(self.toggle_sessions)
        self.session_panel.selected.connect(self._select_session)
        self.session_panel.new_requested.connect(self._new_chat)
        self.session_panel.rename_requested.connect(self._rename_session)
        self.session_panel.delete_requested.connect(self._delete_session)
        self.session_panel.close_requested.connect(lambda: self.toggle_sessions(False))

        QShortcut(QKeySequence("Ctrl+B"), self, activated=self.toggle_files)
        QShortcut(QKeySequence("Ctrl+Shift+B"), self, activated=self.toggle_sessions)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self._new_chat)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings)
        QShortcut(QKeySequence("Escape"), self, activated=self._on_escape)

    # ------------------------------------------------------------------ 面板
    def _apply_initial_widths(self) -> None:
        self.files.setMaximumWidth(FILES_WIDTH if self._files_open else 0)
        self.files.setVisible(self._files_open)
        self.session_panel.setMaximumWidth(SESSIONS_WIDTH if self._sessions_open else 0)
        self.session_panel.setVisible(self._sessions_open)
        self._files_button.setChecked(self._files_open)
        self._sessions_button.setChecked(self._sessions_open)

    def _animate_panel(self, key: str, panel: QWidget, target: int, opening: bool) -> None:
        previous = self._animations.get(key)
        if previous is not None:
            previous.stop()
        if opening:
            panel.setVisible(True)
        start = panel.maximumWidth()
        if start > target and panel.isVisible() is False:
            start = 0
        animation = QPropertyAnimation(panel, b"maximumWidth", self)
        animation.setDuration(230)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.setStartValue(max(0, start))
        animation.setEndValue(target)
        if not opening:
            def finish() -> None:
                if panel.maximumWidth() <= 1:
                    panel.setVisible(False)
            animation.finished.connect(finish)
        animation.start()
        self._animations[key] = animation

    def toggle_files(self, checked: bool | None = None) -> None:
        if self._focus_active:
            self.set_focus(False)
        self._files_open = (not self._files_open) if checked is None else bool(checked)
        self._files_button.setChecked(self._files_open)
        self._animate_panel("files", self.files, FILES_WIDTH if self._files_open else 0, self._files_open)
        self._save_ui_state()

    def toggle_sessions(self, checked: bool | None = None) -> None:
        if self._focus_active:
            self.set_focus(False)
        if isinstance(checked, bool):
            self._sessions_open = checked
        else:
            self._sessions_open = not self._sessions_open
        self._sessions_button.setChecked(self._sessions_open)
        self._sessions_open_panel(self._sessions_open)
        self._save_ui_state()

    def _sessions_open_panel(self, opening: bool) -> None:
        self._animate_panel(
            "sessions", self.session_panel, SESSIONS_WIDTH if opening else 0, opening
        )

    def _save_ui_state(self) -> None:
        try:
            config.update_settings(
                {"ui": {"files_open": self._files_open, "sessions_open": self._sessions_open}}
            )
        except Exception:
            pass

    def set_focus(self, focused: bool) -> None:
        if focused == self._focus_active:
            self.viewer.set_focus(focused)
            return
        if focused:
            self._focus_prev = (self._files_open, self._sessions_open)
            self.files.setVisible(False)
            self.session_panel.setVisible(False)
            self.chat.setVisible(False)
            self._focus_active = True
        else:
            self.files.setVisible(self._focus_prev[0])
            self.files.setMaximumWidth(FILES_WIDTH if self._focus_prev[0] else 0)
            self.session_panel.setVisible(self._focus_prev[1])
            self.session_panel.setMaximumWidth(SESSIONS_WIDTH if self._focus_prev[1] else 0)
            self.chat.setVisible(True)
            self._focus_active = False
        self.viewer.set_focus(focused)

    def toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event) -> None:  # noqa: N802
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "_outer_layout"):
            maximized = self.isMaximized()
            margin = 0 if maximized else WINDOW_MARGIN
            self._outer_layout.setContentsMargins(margin, margin, margin, margin)
            self.centralWidget().set_floating(not maximized)
            if hasattr(self, "_max_button"):
                self._max_button.set_icon("minimize" if maximized else "maximize")
                self._max_button.setToolTip("还原" if maximized else "最大化")
            self.centralWidget().update()
        super().changeEvent(event)

    def _on_escape(self) -> None:
        if self._focus_active:
            self.set_focus(False)
        elif self._sessions_open:
            self.toggle_sessions(False)

    # ------------------------------------------------------------------ 结构
    def open_structure(self, rel: str, name: str) -> None:
        if self.viewer.open_structure(rel, name):
            self.chat.set_structure_context(rel, name)

    # ------------------------------------------------------------------ 会话
    def _refresh_sessions(self) -> None:
        items = sessions.list_all()
        self.session_panel.set_sessions(items, self.chat.session_id)
        self.session_panel.set_current(self.chat.session_id)

    def _restore_last_session(self) -> None:
        items = sessions.list_all()
        if not items:
            return
        try:
            self._select_session(items[0]["id"])
        except Exception:
            pass

    def _select_session(self, session_id: str) -> None:
        try:
            session = sessions.get(session_id)
        except Exception as exc:
            self.toast(f"读取会话失败：{exc}", "error")
            return
        self.chat.load_session(session)
        self.session_panel.set_current(session_id)
        self.session_panel.set_sessions(sessions.list_all(), session_id)

    def _new_chat(self) -> None:
        self.chat.new_chat()
        self.session_panel.set_current("")
        self._refresh_sessions()

    def _rename_session(self, session_id: str, title: str) -> None:
        try:
            sessions.save(session_id, {"title": title})
        except Exception as exc:
            self.toast(f"重命名失败：{exc}", "error")
            return
        if self.chat.session_id == session_id:
            self.chat.set_session_title(title)
        self._refresh_sessions()
        self.toast("会话已重命名", "success")

    def _delete_session(self, session_id: str) -> None:
        if not ConfirmSheet.ask(
            self, "删除会话", "确定要删除这个会话吗？此操作不可撤销。", "删除"
        ):
            return
        try:
            sessions.delete(session_id)
        except Exception as exc:
            self.toast(f"删除失败：{exc}", "error")
            return
        if self.chat.session_id == session_id:
            self.chat.new_chat()
        self._refresh_sessions()
        self.toast("会话已删除", "success")

    # ------------------------------------------------------------------ 设置/主题
    def open_settings(self) -> None:
        dialog = SettingsDialog(self)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _on_settings_saved(self, public: dict) -> None:
        old_workspace = self._settings.get("workspace_root")
        self._settings = config.load_settings()
        self._apply_theme()
        self.chat.set_model_name(public.get("llm", {}).get("model", ""))
        self._update_workspace_button(public.get("workspace_name", ""))
        if old_workspace != public.get("workspace_root"):
            self.viewer.clear()
            self.chat.clear_context()
            self.files.refresh()
        self.toast("设置已保存", "success")

    def _update_workspace_button(self, name: str | None = None) -> None:
        label = name or self._settings.get("workspace_root", "").split("/")[-1]
        metrics = self._workspace_button.fontMetrics()
        shown = metrics.elidedText(label, Qt.TextElideMode.ElideMiddle, 190)
        self._workspace_button.setText(f"  {shown}  ")
        self._workspace_button.setToolTip(f"工作区：{self._settings.get('workspace_root', '')}")
        self._workspace_button.setIcon(icons.icon("folder", theme.current().text_soft, 14))

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        theme.apply(app, "dark")
        self._files_button.update()
        self._sessions_button.update()
        self._settings_button.update()
        self.files.apply_theme()
        self.viewer.set_theme("dark")
        self.chat.apply_theme()
        self.session_panel.apply_theme()
        self._update_workspace_button()
        if hasattr(self, "_toast"):
            self._toast.update()

    # ------------------------------------------------------------------ 其他
    def toast(self, text: str, kind: str = "info") -> None:
        self._toast.show_message(text, kind)

    def _restore_geometry(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(1520, 900)
            return
        available = screen.availableGeometry()
        width = min(1560, int(available.width() * 0.94))
        height = min(960, int(available.height() * 0.90))
        self.resize(max(1180, width), max(660, height))
        self.move(
            available.x() + (available.width() - self.width()) // 2,
            available.y() + (available.height() - self.height()) // 2,
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "_toast"):
            self._toast.reposition()

    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            self.chat.shutdown()
        except Exception:
            pass
        self._save_ui_state()
        super().closeEvent(event)
