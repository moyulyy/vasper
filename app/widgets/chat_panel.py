"""聊天面板：消息气泡、流式回复、Markdown 渲染与输入区。"""

from __future__ import annotations

import datetime as _dt

from PyQt6.QtCore import QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QTextOption,
)
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from .. import config, icons, markdown_render, sessions, theme
from ..workers import ChatWorker
from .components import Avatar, Card, IconButton, IconTile, Pill, SegmentedControl, TextButton


class ComposerEdit(QTextEdit):
    submitted = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Composer")
        self.setAcceptRichText(False)
        self.setPlaceholderText("询问结构、计算方案或材料问题…")
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(42)
        self.document().setDocumentMargin(2)
        self.textChanged.connect(self._adjust_height)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submitted.emit()
                event.accept()
            return
        super().keyPressEvent(event)

    def _adjust_height(self) -> None:
        doc_height = int(self.document().size().height())
        self.setFixedHeight(max(38, min(132, doc_height + 14)))

    def insert_text(self, text: str) -> None:
        self.setPlainText(text)
        self.moveCursor(self.textCursor().MoveOperation.End)
        self.setFocus()


class BubbleSurface(QFrame):
    """自绘渐变胶囊，避免 QSS 渐变在不同平台上的解析差异。"""

    def __init__(self, parent: QWidget | None = None, radius: int = 16) -> None:
        super().__init__(parent)
        self.setObjectName("UserBubbleSurface")
        self._radius = radius

    def paintEvent(self, event) -> None:  # noqa: N802
        palette = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, QColor(palette.bubble_from))
        gradient.setColorAt(1.0, QColor(palette.bubble_to))
        painter.fillPath(path, gradient)
        painter.end()


class SendButton(QPushButton):
    """圆形渐变发送/停止按钮。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._busy = False
        self._hover = False
        self.setToolTip("发送")

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.setToolTip("停止生成" if busy else "发送")
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        palette = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addEllipse(rect)

        if not self.isEnabled() and not self._busy:
            painter.fillPath(path, QColor(palette.surface_sunken))
            icon_name, color = "arrow-up", palette.faint
        elif self._busy:
            painter.fillPath(path, QColor(palette.surface_alt))
            painter.setPen(QColor(palette.border))
            painter.drawPath(path)
            icon_name, color = "square", palette.danger
        else:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0.0, QColor(palette.accent_hover if self._hover else palette.bubble_from))
            gradient.setColorAt(1.0, QColor(palette.bubble_to))
            painter.fillPath(path, gradient)
            icon_name, color = "arrow-up", "#FFFFFF"

        pix = icons.pixmap(icon_name, color, 17, 2.1)
        painter.drawPixmap(
            int((self.width() - 17) / 2),
            int((self.height() - 17) / 2),
            pix,
        )
        painter.end()


class AssistantBubble(QWidget):
    def __init__(self, text: str, model: str = "", mode: str = "", streaming: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self._model = model
        self._mode = mode
        self._streaming = streaming
        self._bubbles: list = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)

        self._avatar = Avatar("V", size=26)
        layout.addWidget(self._avatar, 0, Qt.AlignmentFlag.AlignTop)

        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)
        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 2, 0)
        header.setSpacing(7)
        name = QLabel("Vasper")
        font = QFont(theme.font_family(), 9)
        font.setWeight(QFont.Weight.DemiBold)
        name.setFont(font)
        name.setStyleSheet(f"color: {theme.current().text_soft};")
        header.addWidget(name)
        if mode in {"plan", "execute"}:
            label = "计划" if mode == "plan" else "执行"
            self._mode_pill = Pill(label, kind="Badge" if mode == "execute" else "CountBadge")
            header.addWidget(self._mode_pill)
        else:
            self._mode_pill = None
        if model:
            self._model_pill = Pill(model, kind="CountBadge")
            header.addWidget(self._model_pill)
        else:
            self._model_pill = None
        header.addStretch(1)
        self._copy_button = IconButton("copy", "复制内容", diameter=24, icon_size=13)
        self._copy_button.clicked.connect(self._copy)
        header.addWidget(self._copy_button)
        column.addLayout(header)

        self._frame = QFrame()
        self._frame.setObjectName("BubbleAssistant")
        inner = QVBoxLayout(self._frame)
        inner.setContentsMargins(12, 9, 12, 9)
        inner.setSpacing(0)
        self._browser = QTextBrowser()
        self._browser.setObjectName("BubbleBody")
        self._browser.setOpenExternalLinks(True)
        self._browser.setFrameShape(QFrame.Shape.NoFrame)
        self._browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._browser.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self._browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._browser.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self._browser.setStyleSheet("background: transparent; border: none;")
        inner.addWidget(self._browser)
        column.addWidget(self._frame)
        layout.addLayout(column, 1)
        self._refresh()

    def _refresh(self) -> None:
        html = markdown_render.document(self._text, streaming=self._streaming)
        self._browser.setHtml(html)
        QTimer.singleShot(0, self._fit)

    def _fit(self) -> None:
        if not self._browser.isVisible() and self._browser.viewport().width() <= 0:
            return
        width = max(80, self._browser.viewport().width())
        doc = self._browser.document()
        doc.setTextWidth(width)
        self._browser.setFixedHeight(max(20, int(doc.size().height()) + 6))

    def set_available_width(self, width: int) -> None:
        self.setMaximumWidth(max(240, width))
        QTimer.singleShot(0, self._fit)

    def set_text(self, text: str, streaming: bool | None = None) -> None:
        self._text = text
        if streaming is not None:
            self._streaming = streaming
        self._refresh()

    def finish(self) -> None:
        self._streaming = False
        self._refresh()

    def apply_theme(self) -> None:
        self._avatar.update()
        for label in self.findChildren(QLabel):
            if label.text() == "Vasper":
                label.setStyleSheet(f"color: {theme.current().text_soft};")
        self._refresh()

    def _copy(self) -> None:
        QApplication.clipboard().setText(self._text)
        self._copy_button.set_icon("check")
        QTimer.singleShot(1400, lambda: self._copy_button.set_icon("copy"))


class UserBubble(QWidget):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        self._frame = BubbleSurface()
        self._frame.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        inner = QVBoxLayout(self._frame)
        inner.setContentsMargins(13, 9, 13, 9)
        self._label = QLabel(text)
        self._label.setObjectName("BubbleUserText")
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.TextFormat.PlainText)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        inner.addWidget(self._label)
        layout.addWidget(self._frame, 0, Qt.AlignmentFlag.AlignRight)

    def set_available_width(self, width: int) -> None:
        max_width = max(180, int(width * 0.78))
        metrics = self._label.fontMetrics()
        needed = metrics.horizontalAdvance(self._label.text()) + 30
        self._frame.setFixedWidth(max(96, min(max_width, needed)))


class ErrorBubble(QWidget):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        palette = theme.current()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(36, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName("BubbleError")
        inner = QHBoxLayout(frame)
        inner.setContentsMargins(12, 9, 14, 9)
        inner.setSpacing(9)
        icon = QLabel()
        from .. import icons

        icon.setPixmap(icons.pixmap("info", palette.danger, 16, 2.0))
        icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        inner.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setStyleSheet(f"color: {palette.danger}; font-size: 12px;")
        inner.addWidget(body, 1)
        layout.addWidget(frame, 1)

    def set_available_width(self, width: int) -> None:
        self.setMaximumWidth(max(260, width))


class WelcomePanel(QWidget):
    suggestion = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        palette = theme.current()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 18, 12, 8)
        layout.setSpacing(8)
        layout.addStretch(1)
        tile = IconTile("sparkles", size=54, radius=16, icon_size=27)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(tile)
        row.addStretch(1)
        layout.addLayout(row)
        title = QLabel("开始新的对话")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont(theme.font_family(), 15)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        layout.addWidget(title)
        self._subtitle = QLabel("打开左侧结构文件，我可以结合 3D 模型一起分析")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle.setWordWrap(True)
        self._subtitle.setStyleSheet(f"color: {palette.muted}; font-size: 11.5px;")
        layout.addWidget(self._subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self._suggestions = [
            ("analyze", "分析当前结构"),
            ("symmetry", "解释对称性与空间群"),
            ("dft", "设计一套 DFT 计算方案"),
            ("check", "检查结构是否合理"),
        ]
        self._buttons: list[QPushButton] = []
        for index, (key, label) in enumerate(self._suggestions):
            button = TextButton(label, variant="chip")
            button.clicked.connect(lambda _c=False, text=label: self.suggestion.emit(text))
            grid.addWidget(button, index // 2, index % 2)
            self._buttons.append(button)
        layout.addSpacing(6)
        layout.addLayout(grid)
        layout.addStretch(2)
        self._has_context = False

    def set_has_context(self, has_context: bool) -> None:
        self._has_context = has_context
        if self._buttons:
            self._buttons[0].setText("分析当前结构" if has_context else "什么是钙钛矿结构？")
        self._subtitle.setText(
            "已附加当前结构，我可以读取原子与晶胞信息"
            if has_context
            else "打开左侧结构文件，我可以结合 3D 模型一起分析"
        )


class ChatPanel(Card):
    notify = pyqtSignal(str, str)
    sessions_changed = pyqtSignal()
    request_sessions = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, object_name="Panel")
        self.setMinimumWidth(400)
        self.session_id: str | None = None
        self.messages: list[dict] = []
        self._bubbles: list[QWidget] = []
        self._context: tuple[str, str] | None = None
        self._worker: ChatWorker | None = None
        self._streaming = False
        self._stopping = False
        self._stream_text = ""
        self._active_bubble: AssistantBubble | None = None
        self._title_text = "新对话"
        settings = config.load_settings()
        stored_mode = settings.get("ui", {}).get("llm_mode", "plan")
        self._mode = stored_mode if stored_mode in {"plan", "execute"} else "plan"
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(70)
        self._flush_timer.timeout.connect(self._flush_stream)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        self._title = QLabel("新对话")
        self._title.setObjectName("Title")
        self._title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._title.setMinimumWidth(80)
        self._model = QLabel(config.llm_config().get("model") or "未配置模型")
        self._model.setObjectName("Subtitle")
        titles.addWidget(self._title)
        titles.addWidget(self._model)
        header.addLayout(titles, 1)
        self._new_button = IconButton("message-plus", "新建对话", diameter=32, icon_size=17)
        self._new_button.clicked.connect(self.new_chat)
        header.addWidget(self._new_button)
        self._sessions_button = IconButton("panel-right", "会话管理", diameter=32, icon_size=17)
        self._sessions_button.clicked.connect(self.request_sessions.emit)
        header.addWidget(self._sessions_button)
        layout.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("ChatScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._messages = QWidget()
        self._messages.setObjectName("MessageArea")
        self._messages_layout = QVBoxLayout(self._messages)
        self._messages_layout.setContentsMargins(0, 4, 4, 4)
        self._messages_layout.setSpacing(16)
        self._welcome = WelcomePanel()
        self._welcome.suggestion.connect(self._on_suggestion)
        self._messages_layout.addWidget(self._welcome)
        self._messages_layout.addStretch(1)
        self._scroll.setWidget(self._messages)
        layout.addWidget(self._scroll, 1)

        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(2, 0, 2, 0)
        mode_row.setSpacing(8)
        self._mode_control = SegmentedControl(
            [("plan", "计划"), ("execute", "执行")],
            current=self._mode,
        )
        self._mode_control.changed.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_control)
        mode_row.addStretch(1)
        self._mode_hint = QLabel("")
        self._mode_hint.setObjectName("Faint")
        mode_row.addWidget(self._mode_hint)
        layout.addLayout(mode_row)

        self._composer_frame = QFrame()
        self._composer_frame.setObjectName("SubCard")
        composer_layout = QVBoxLayout(self._composer_frame)
        composer_layout.setContentsMargins(10, 8, 8, 8)
        composer_layout.setSpacing(5)

        self._context_row = QWidget()
        context_layout = QHBoxLayout(self._context_row)
        context_layout.setContentsMargins(2, 0, 2, 0)
        context_layout.setSpacing(6)
        palette = theme.current()
        self._context_label = QLabel("")
        self._context_label.setMaximumWidth(240)
        self._context_label.setStyleSheet(
            f"background: {palette.accent_soft}; color: {palette.accent};"
            "border-radius: 9px; padding: 3px 9px; font-size: 11px; font-weight: 500;"
        )
        context_layout.addWidget(self._context_label)
        self._context_close = IconButton("x", "移除结构上下文", diameter=22, icon_size=12)
        self._context_close.clicked.connect(self.clear_context)
        context_layout.addWidget(self._context_close)
        context_layout.addStretch(1)
        self._context_row.hide()
        composer_layout.addWidget(self._context_row)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self._input = ComposerEdit()
        self._input.submitted.connect(self.send)
        self._input.textChanged.connect(self._update_send_button)
        input_row.addWidget(self._input, 1)
        self._send = SendButton()
        self._send.clicked.connect(self._on_send_clicked)
        input_row.addWidget(self._send, 0, Qt.AlignmentFlag.AlignBottom)
        composer_layout.addLayout(input_row)

        self._hint = QLabel("Enter 发送 · Shift + Enter 换行")
        self._hint.setObjectName("Faint")
        self._hint.setContentsMargins(6, 0, 0, 0)
        composer_layout.addWidget(self._hint)
        layout.addWidget(self._composer_frame)

        self._update_send_button()
        self._apply_model_name()
        self._apply_mode(self._mode)
        self._refresh_welcome()

    # ------------------------------------------------------------------ 会话
    def new_chat(self) -> None:
        self.stop_generation()
        self.session_id = None
        self.messages = []
        self._clear_messages()
        self._set_title("新对话")
        self._input.clear()
        self._welcome.setVisible(True)
        self.sessions_changed.emit()

    def load_session(self, session: dict) -> None:
        self.stop_generation()
        self.session_id = session.get("id")
        self.messages = list(session.get("messages") or [])
        self._clear_messages()
        self._set_title(session.get("title") or "对话")
        for message in self.messages:
            self._render_message(message)
        if not self.messages:
            self._welcome.setVisible(True)
        self._scroll_to_bottom()

    def _render_message(self, message: dict) -> None:
        self._welcome.setVisible(False)
        role = message.get("role")
        content = message.get("content") or ""
        if role == "user":
            bubble = UserBubble(content)
        elif message.get("error"):
            bubble = ErrorBubble(content)
        else:
            bubble = AssistantBubble(
                content,
                message.get("model") or "",
                mode=message.get("mode") or "",
            )
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, bubble)
        self._bubbles.append(bubble)
        bubble.set_available_width(self._available_width())
        QTimer.singleShot(0, lambda b=bubble: b.set_available_width(self._available_width()))

    def _clear_messages(self) -> None:
        for bubble in self._bubbles:
            bubble.setParent(None)
            bubble.deleteLater()
        self._bubbles = []
        self._welcome.setVisible(True)

    def _available_width(self) -> int:
        width = self._scroll.viewport().width() - 34 if self._scroll.viewport().width() else self.width() - 60
        return max(260, width)

    def apply_theme(self) -> None:
        palette = theme.current()
        self._context_label.setStyleSheet(
            f"background: {palette.accent_soft}; color: {palette.accent};"
            "border-radius: 9px; padding: 3px 9px; font-size: 11px; font-weight: 500;"
        )
        self._welcome._subtitle.setStyleSheet(f"color: {palette.muted}; font-size: 11.5px;")
        self._welcome.update()
        for bubble in self._bubbles:
            if hasattr(bubble, "apply_theme"):
                bubble.apply_theme()
            else:
                bubble.update()
        self._update_send_button()

    def set_model_name(self, model: str) -> None:
        self._model.setText(model or "未配置模型")
        self._apply_model_name()

    def set_session_title(self, title: str) -> None:
        self._set_title(title or "新对话")

    def _set_title(self, title: str) -> None:
        self._title_text = title or "新对话"
        self._title.setToolTip(self._title_text)
        self._elide_title()

    def _elide_title(self) -> None:
        available = self._title.width() if self._title.width() > 20 else max(90, self.width() - 190)
        metrics = self._title.fontMetrics()
        self._title.setText(metrics.elidedText(self._title_text, Qt.TextElideMode.ElideRight, available))

    def _apply_model_name(self) -> None:
        model = config.llm_config().get("model") or ""
        self._model.setText(model or "未配置模型")
        if model and self._model.palette().window().color().isValid():
            self._model.setToolTip("在设置中可以更换模型与 API")

    # ------------------------------------------------------------------ 上下文
    def set_structure_context(self, path: str, name: str) -> None:
        self._context = (path, name)
        self._update_context_label()
        self._context_row.show()
        self._welcome.set_has_context(True)
        self._hint.setText("已附加当前结构，Enter 发送 · Shift + Enter 换行")

    def _update_context_label(self) -> None:
        if not self._context:
            return
        path, name = self._context
        available = max(120, min(230, self.width() - 190))
        text = self._context_label.fontMetrics().elidedText(
            f"结构上下文 · {name}", Qt.TextElideMode.ElideMiddle, available
        )
        self._context_label.setText(text)
        self._context_label.setToolTip(path)

    def clear_context(self) -> None:
        self._context = None
        self._context_row.hide()
        self._welcome.set_has_context(False)
        self._hint.setText("Enter 发送 · Shift + Enter 换行")

    def _refresh_welcome(self) -> None:
        self._welcome.set_has_context(self._context is not None)

    def _on_suggestion(self, text: str) -> None:
        self._input.insert_text(text)

    # ------------------------------------------------------------------ 发送
    def _on_send_clicked(self) -> None:
        if self._streaming:
            self.stop_generation()
        else:
            self.send()

    def send(self) -> None:
        if self._streaming:
            return
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        self._welcome.setVisible(False)
        user_message = {
            "role": "user",
            "content": text,
            "created": _dt.datetime.now().isoformat(timespec="seconds"),
        }
        self.messages.append(user_message)
        self._render_message(user_message)
        self._persist()
        self._start_streaming()

    def _start_streaming(self) -> None:
        payload = {
            "messages": [
                {"role": message["role"], "content": message["content"]}
                for message in self.messages
                if message.get("role") in {"user", "assistant"} and not message.get("error")
            ],
        }
        if self._context:
            payload["context_path"] = self._context[0]
        payload["mode"] = self._mode
        self._stream_text = ""
        self._stopping = False
        self._streaming = True
        self._active_bubble = AssistantBubble(
            "",
            config.llm_config().get("model", ""),
            mode=self._mode,
            streaming=True,
        )
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, self._active_bubble)
        self._bubbles.append(self._active_bubble)
        self._active_bubble.set_available_width(self._available_width())
        self._update_send_button()
        self._hint.setText("正在生成… 点击停止按钮可中断")
        self._scroll_to_bottom()

        self._worker = ChatWorker(payload, self)
        self._worker.delta.connect(self._on_delta)
        self._worker.completed.connect(self._on_completed)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_thread_finished)
        self._worker.start()

    def _on_delta(self, text: str) -> None:
        if not self._streaming:
            return
        self._stream_text += text
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _flush_stream(self) -> None:
        if not self._active_bubble:
            return
        self._active_bubble.set_text(self._stream_text, streaming=True)
        self._scroll_to_bottom()

    def _on_completed(self, info: dict) -> None:
        if not self._streaming:
            return
        self._flush_timer.stop()
        self._flush_stream()
        bubble = self._active_bubble
        self._finish_streaming()
        text = self._stream_text.strip()
        if not text:
            text = "（模型没有返回内容）"
            if bubble is not None:
                bubble.set_text(text, streaming=False)
        message = {
            "role": "assistant",
            "content": text,
            "model": config.llm_config().get("model", ""),
            "mode": self._mode,
            "created": _dt.datetime.now().isoformat(timespec="seconds"),
        }
        self.messages.append(message)
        self._persist()
        self.sessions_changed.emit()

    def _on_failed(self, error: str) -> None:
        if not self._streaming:
            return
        self._flush_timer.stop()
        if self._active_bubble:
            self._active_bubble.setParent(None)
            self._active_bubble.deleteLater()
            try:
                self._bubbles.remove(self._active_bubble)
            except ValueError:
                pass
            self._active_bubble = None
        self._streaming = False
        message = {
            "role": "assistant",
            "content": f"请求失败：{error}",
            "error": True,
            "created": _dt.datetime.now().isoformat(timespec="seconds"),
        }
        self.messages.append(message)
        self._render_message(message)
        self._persist()
        self._update_send_button()
        self._hint.setText("Enter 发送 · Shift + Enter 换行")
        self.notify.emit(f"请求失败：{error}", "error")
        self.sessions_changed.emit()

    def _finish_streaming(self) -> None:
        self._streaming = False
        self._stopping = False
        self._stream_text = self._stream_text.strip()
        if self._active_bubble:
            self._active_bubble.set_text(self._stream_text, streaming=False)
            self._active_bubble.finish()
        self._active_bubble = None
        self._update_send_button()
        self._hint.setText("Enter 发送 · Shift + Enter 换行")
        self._scroll_to_bottom()

    def stop_generation(self) -> None:
        if not self._streaming:
            return
        self._stopping = True
        if self._worker:
            self._worker.stop()
        self._flush_timer.stop()
        self._flush_stream()
        text = self._stream_text.strip()
        self._finish_streaming()
        if text:
            message = {
                "role": "assistant",
                "content": text + "\n\n*[已停止生成]*",
                "model": config.llm_config().get("model", ""),
                "mode": self._mode,
                "created": _dt.datetime.now().isoformat(timespec="seconds"),
            }
            self.messages.append(message)
            self._persist()
            self.sessions_changed.emit()
        self._stopping = False

    def _on_thread_finished(self) -> None:
        worker = self.sender()
        if worker is self._worker:
            self._worker = None
        if worker is not None:
            worker.deleteLater()

    # ------------------------------------------------------------------ 持久化
    def _persist(self) -> None:
        try:
            if not self.session_id:
                model = config.llm_config().get("model", "")
                session = sessions.create("新会话", model)
                self.session_id = session["id"]
            session = sessions.save(
                self.session_id,
                {"messages": self.messages, "model": config.llm_config().get("model", "")},
            )
            self._set_title(session.get("title") or "新对话")
        except Exception as exc:
            self.notify.emit(f"会话保存失败：{exc}", "error")
        self.sessions_changed.emit()

    def shutdown(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            if not self._worker.wait(2000):
                self._worker.terminate()
                self._worker.wait(800)
            self._worker = None

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._elide_title()
        width = self._available_width()
        for bubble in self._bubbles:
            bubble.set_available_width(width)
        self._update_context_label()

    def _on_mode_changed(self, mode: str) -> None:
        if self._streaming or mode not in {"plan", "execute"}:
            return
        self._mode = mode
        self._apply_mode(mode)
        try:
            config.update_settings({"ui": {"llm_mode": mode}})
        except Exception:
            pass

    def _apply_mode(self, mode: str) -> None:
        self._mode_control.set_current(mode)
        if mode == "execute":
            self._mode_hint.setText("直接给出可执行结果")
            self._input.setPlaceholderText("描述任务，我会直接给出完整结果…")
        else:
            self._mode_hint.setText("先规划，不直接执行")
            self._input.setPlaceholderText("描述目标，我会先给出执行计划…")

    def _update_send_button(self) -> None:
        if self._streaming:
            self._send.set_busy(True)
        else:
            self._send.set_busy(False)
        if hasattr(self, "_mode_control"):
            self._mode_control.setEnabled(not self._streaming)
        self._send.setEnabled(bool(self._input.toPlainText().strip()) or self._streaming)

    def _scroll_to_bottom(self) -> None:
        def scroll() -> None:
            bar = self._scroll.verticalScrollBar()
            bar.setValue(bar.maximum())

        QTimer.singleShot(0, scroll)
