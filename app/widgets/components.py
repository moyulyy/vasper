"""通用 iOS 风格控件：图标按钮、分段控件、胶囊、Toast、渐变头像等。"""

from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve, QPoint, QPropertyAnimation, QRectF, QSize, Qt, QTimer, pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QAbstractButton, QButtonGroup, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from .. import icons, theme


class RootBackground(QWidget):
    """带柔和光斑的渐变背景，替代 macOS 毛玻璃的层次感。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Root")
        self._floating = True
        self._margin = 12
        self.setMouseTracking(True)

    def set_floating(self, floating: bool) -> None:
        self._floating = floating
        self.update()

    def _resize_edges(self, position) -> Qt.Edge:
        margin = self._margin if self._floating else 5
        edges = Qt.Edge(0)
        if position.x() <= margin:
            edges |= Qt.Edge.LeftEdge
        if position.x() >= self.width() - margin - 1:
            edges |= Qt.Edge.RightEdge
        if position.y() <= margin:
            edges |= Qt.Edge.TopEdge
        if position.y() >= self.height() - margin - 1:
            edges |= Qt.Edge.BottomEdge
        return edges

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        edges = self._resize_edges(event.position().toPoint()) if self._floating else Qt.Edge(0)
        if edges in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edges in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif edges in (Qt.Edge.TopEdge | Qt.Edge.LeftEdge, Qt.Edge.BottomEdge | Qt.Edge.RightEdge):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edges in (Qt.Edge.TopEdge | Qt.Edge.RightEdge, Qt.Edge.BottomEdge | Qt.Edge.LeftEdge):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._floating and event.button() == Qt.MouseButton.LeftButton:
            edges = self._resize_edges(event.position().toPoint())
            if edges:
                handle = self.window().windowHandle()
                if handle is not None and handle.startSystemResize(edges):
                    event.accept()
                    return
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        palette = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        full = QRectF(self.rect())
        window = self.window()
        maximized = bool(window and window.isMaximized())
        margin = 0.0 if (maximized or not self._floating) else float(self._margin)
        radius = 0.0 if maximized else 22.0
        rect = full.adjusted(margin + 0.5, margin + 0.5, -margin - 0.5, -margin - 0.5)

        if margin > 0:
            for step in range(int(margin), 0, -1):
                alpha = max(3, int(17 * (1 - step / (margin + 1))))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(0, 0, 0, alpha))
                painter.drawRoundedRect(
                    rect.adjusted(-step, -step, step, step + 1),
                    radius + step,
                    radius + step,
                )

        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, QColor(palette.bg1))
        gradient.setColorAt(0.55, QColor(palette.bg1))
        gradient.setColorAt(1.0, QColor(palette.bg2))
        painter.fillPath(path, gradient)
        painter.save()
        painter.setClipPath(path)

        blob = QRadialGradient(rect.width() * 0.18, rect.height() * 0.05, rect.width() * 0.55)
        accent = QColor(palette.accent)
        accent.setAlpha(34)
        blob.setColorAt(0.0, accent)
        accent_end = QColor(accent)
        accent_end.setAlpha(0)
        blob.setColorAt(1.0, accent_end)
        painter.fillRect(rect, blob)

        blob2 = QRadialGradient(rect.width() * 0.92, rect.height() * 0.92, rect.width() * 0.45)
        violet = QColor("#5E5CE6")
        violet.setAlpha(30)
        blob2.setColorAt(0.0, violet)
        violet_end = QColor(violet)
        violet_end.setAlpha(0)
        blob2.setColorAt(1.0, violet_end)
        painter.fillRect(rect, blob2)
        painter.restore()

        if not maximized:
            painter.setPen(QColor(palette.border_strong))
            painter.drawPath(path)
        painter.end()


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, object_name: str = "Card") -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class Divider(QFrame):
    def __init__(self, parent: QWidget | None = None, horizontal: bool = True) -> None:
        super().__init__(parent)
        self.setObjectName("Divider")
        if horizontal:
            self.setFixedHeight(1)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        else:
            self.setFixedWidth(1)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)


class IconButton(QAbstractButton):
    """圆形悬停背景的线性图标按钮，自动跟随主题。"""

    def __init__(
        self,
        name: str,
        tooltip: str = "",
        parent: QWidget | None = None,
        *,
        diameter: int = 34,
        icon_size: int = 18,
        color_key: str = "text_soft",
        stroke: float = 1.8,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._icon_size = icon_size
        self._color_key = color_key
        self._stroke = stroke
        self._diameter = diameter
        self.setFixedSize(diameter, diameter)
        self.setIconSize(QSize(icon_size, icon_size))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def set_icon(self, name: str) -> None:
        self._name = name
        self.update()

    def set_color_key(self, key: str) -> None:
        self._color_key = key
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        palette = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        radius = rect.width() / 2

        color = getattr(palette, self._color_key)
        if not self.isEnabled():
            color = palette.faint
        elif self.isChecked():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(palette.accent_soft))
            painter.drawRoundedRect(rect, radius, radius)
            color = palette.accent
        elif self.underMouse():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(palette.surface_alt))
            painter.drawRoundedRect(rect, radius, radius)
        if self.isDown() and self.isEnabled():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(palette.surface_sunken))
            painter.drawRoundedRect(rect, radius, radius)

        pix = icons.pixmap(self._name, color, self._icon_size, self._stroke)
        x = (self.width() - self._icon_size) / 2
        y = (self.height() - self._icon_size) / 2
        painter.drawPixmap(int(round(x)), int(round(y)), pix)
        painter.end()

    def enterEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(event)


class TextButton(QPushButton):
    def __init__(
        self,
        text: str,
        parent: QWidget | None = None,
        *,
        variant: str = "",
        icon_name: str | None = None,
        icon_size: int = 15,
    ) -> None:
        super().__init__(text, parent)
        if variant:
            self.setProperty("variant", variant)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if icon_name:
            color = "#FFFFFF" if variant == "primary" else theme.current().text_soft
            self.setIcon(icons.icon(icon_name, color, icon_size, 1.9))
            self.setIconSize(QSize(icon_size, icon_size))


class Pill(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None, *, kind: str = "Chip") -> None:
        super().__init__(text, parent)
        self.setObjectName(kind)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


class SegmentedControl(QFrame):
    changed = pyqtSignal(str)

    def __init__(self, options: list[tuple[str, str]], parent: QWidget | None = None, *, current: str | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Segmented")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        for key, label in options:
            button = QPushButton(label)
            button.setProperty("variant", "seg")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda _checked, k=key: self._on_click(k))
            self._group.addButton(button)
            self._buttons[key] = button
            layout.addWidget(button)
        if current is None and options:
            current = options[0][0]
        if current in self._buttons:
            self._buttons[current].setChecked(True)

    def _on_click(self, key: str) -> None:
        self.changed.emit(key)

    def current(self) -> str | None:
        for key, button in self._buttons.items():
            if button.isChecked():
                return key
        return None

    def set_current(self, key: str, *, emit: bool = False) -> None:
        button = self._buttons.get(key)
        if button is None or button.isChecked():
            return
        button.setChecked(True)
        if emit:
            self.changed.emit(key)


class IconTile(QWidget):
    """渐变圆角方块 + 白色图标，用作 App 标志/结构缩略图。"""

    def __init__(
        self,
        name: str = "atom",
        parent: QWidget | None = None,
        *,
        size: int = 34,
        radius: int = 10,
        colors: tuple[str, str] = ("#0A84FF", "#5E5CE6"),
        icon_size: int = 19,
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._radius = radius
        self._colors = colors
        self._icon_size = icon_size
        self.setFixedSize(size, size)

    def set_icon(self, name: str) -> None:
        self._name = name
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, QColor(self._colors[0]))
        gradient.setColorAt(1.0, QColor(self._colors[1]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(rect, self._radius, self._radius)
        pix = icons.pixmap(self._name, "#FFFFFF", self._icon_size, 1.9)
        x = (self.width() - self._icon_size) / 2
        y = (self.height() - self._icon_size) / 2
        painter.drawPixmap(int(round(x)), int(round(y)), pix)
        painter.end()


class Avatar(QWidget):
    def __init__(self, letter: str = "V", parent: QWidget | None = None, *, size: int = 28) -> None:
        super().__init__(parent)
        self._letter = letter
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, QColor("#0A84FF"))
        gradient.setColorAt(1.0, QColor("#5E5CE6"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(rect)
        painter.setPen(QColor("#FFFFFF"))
        font = QFont(theme.font_family(), 10)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._letter)
        painter.end()


class Toast(QFrame):
    """窗口底部的浮层提示，淡入淡出。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._label = QLabel("", self)
        self._label.setTextFormat(Qt.TextFormat.PlainText)
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(520)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 18, 10)
        layout.setSpacing(9)
        layout.addWidget(self._label)
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)
        self._animation = QPropertyAnimation(self._effect, b"opacity", self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self.hide()

    def paintEvent(self, event) -> None:  # noqa: N802
        palette = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(palette.overlay)
        color.setAlpha(232 if palette.mode == "light" else 240)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0, 0, -1, -1), 14, 14)
        painter.end()

    def show_message(self, text: str, kind: str = "info", timeout: int = 2600) -> None:
        palette = theme.current()
        text = " ".join(str(text).split())
        if len(text) > 240:
            text = text[:240] + "…"
        color = {
            "success": palette.success,
            "error": palette.danger,
            "warning": palette.warning,
        }.get(kind, "#FFFFFF")
        pix = icons.pixmap(
            {"success": "check", "error": "x", "warning": "info"}.get(kind, "info"),
            color,
            16,
            2.0,
        )
        self._label.clear()
        self._label.setText(text)
        self._label.setStyleSheet("color: #FFFFFF; font-size: 12px;")
        # 用一个带图标的前缀标签重新排版
        layout = self.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget and widget is not self._label:
                widget.deleteLater()
        icon_label = QLabel(self)
        icon_label.setPixmap(pix)
        icon_label.setStyleSheet("background: transparent;")
        layout.addWidget(icon_label)
        layout.addWidget(self._label)
        self.adjustSize()
        parent = self.parentWidget()
        if parent:
            x = (parent.width() - self.width()) // 2
            y = parent.height() - self.height() - 34
            self.move(max(12, x), max(12, y))
        self.raise_()
        self.show()
        self._effect.setOpacity(0.0)
        self._animation.stop()
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.start()
        self._timer.start(timeout)

    def _fade_out(self) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._effect.opacity())
        self._animation.setEndValue(0.0)
        try:
            self._animation.finished.disconnect()
        except TypeError:
            pass
        self._animation.finished.connect(self.hide)
        self._animation.start()

    def reposition(self) -> None:
        if not self.isVisible():
            return
        parent = self.parentWidget()
        if parent:
            self.move(max(12, (parent.width() - self.width()) // 2), parent.height() - self.height() - 34)
