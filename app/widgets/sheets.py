"""统一的 iOS 风格弹窗：无边框圆角卡片、图标标题、底部操作区。"""

from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from .. import theme
from .components import Divider, IconButton, IconTile


class SheetDialog(QDialog):
    """深色圆角 Sheet。替代原生 QMessageBox / QInputDialog 的视觉基础。"""

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        subtitle: str = "",
        *,
        icon: str = "info",
        width: int = 440,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SheetDialog")
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self._drag_offset = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(0)

        self._card = QFrame()
        self._card.setObjectName("Sheet")
        shadow = QGraphicsDropShadowEffect(self._card)
        shadow.setBlurRadius(48)
        shadow.setColor(QColor(0, 0, 0, 165))
        shadow.setOffset(0, 14)
        self._card.setGraphicsEffect(shadow)
        outer.addWidget(self._card)

        body = QVBoxLayout(self._card)
        body.setContentsMargins(22, 20, 22, 18)
        body.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        self._tile = IconTile(icon, size=38, radius=11, icon_size=20)
        header.addWidget(self._tile)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        title_label = QLabel(title)
        title_label.setObjectName("Title")
        titles.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("Subtitle")
            subtitle_label.setWordWrap(True)
            titles.addWidget(subtitle_label)
        header.addLayout(titles, 1)
        close_button = IconButton("x", "关闭", diameter=28, icon_size=14)
        close_button.clicked.connect(self.reject)
        header.addWidget(close_button)
        body.addLayout(header)
        body.addWidget(Divider())
        self.body = body

        self.setFixedWidth(width + 36)

    def add_footer(
        self,
        cancel_text: str = "取消",
        primary_text: str = "确定",
        *,
        destructive: bool = False,
    ) -> QPushButton:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)
        cancel = QPushButton(cancel_text)
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        primary = QPushButton(primary_text)
        primary.setProperty("variant", "destructive" if destructive else "primary")
        primary.setCursor(Qt.CursorShape.PointingHandCursor)
        primary.setDefault(True)
        row.addWidget(cancel)
        row.addWidget(primary)
        self.body.addLayout(row)
        return primary

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.adjustSize()
        parent = self.parentWidget()
        if parent is not None:
            QTimer.singleShot(0, self._center_on_parent)

    def _center_on_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        frame = parent.window().frameGeometry()
        self.move(frame.center() - self.rect().center())

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class ConfirmSheet(SheetDialog):
    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        confirm_text: str = "删除",
        destructive: bool = True,
    ) -> None:
        super().__init__(
            parent,
            title,
            "",
            icon="trash" if destructive else "info",
            width=420,
        )
        label = QLabel(message)
        label.setObjectName("Muted")
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color: {theme.current().text_soft}; font-size: 12.5px; line-height: 1.7;"
        )
        self.body.addWidget(label)
        primary = self.add_footer("取消", confirm_text, destructive=destructive)
        primary.clicked.connect(self.accept)

    @classmethod
    def ask(
        cls,
        parent: QWidget | None,
        title: str,
        message: str,
        confirm_text: str = "删除",
        *,
        destructive: bool = True,
    ) -> bool:
        dialog = cls(
            parent, title, message,
            confirm_text=confirm_text, destructive=destructive,
        )
        return dialog.exec() == QDialog.DialogCode.Accepted


class InputSheet(SheetDialog):
    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        label_text: str,
        *,
        text: str = "",
        placeholder: str = "",
        confirm_text: str = "确定",
    ) -> None:
        super().__init__(parent, title, "", icon="pencil", width=420)
        label = QLabel(label_text)
        label.setObjectName("Muted")
        self.body.addWidget(label)
        self._edit = QLineEdit(text)
        self._edit.setPlaceholderText(placeholder)
        self._edit.setClearButtonEnabled(False)
        self._edit.returnPressed.connect(self._accept)
        self.body.addWidget(self._edit)
        self._error = QLabel("名称不能为空")
        self._error.setStyleSheet(f"color: {theme.current().danger}; font-size: 11px;")
        self._error.hide()
        self.body.addWidget(self._error)
        primary = self.add_footer("取消", confirm_text)
        primary.clicked.connect(self._accept)
        QTimer.singleShot(0, self._focus_edit)

    def _focus_edit(self) -> None:
        self._edit.setFocus()
        self._edit.selectAll()

    def _accept(self) -> None:
        if not self._edit.text().strip():
            self._error.show()
            self._edit.setFocus()
            return
        self._error.hide()
        self.accept()

    def value(self) -> str:
        return self._edit.text().strip()

    @classmethod
    def get_text(
        cls,
        parent: QWidget | None,
        title: str,
        label_text: str,
        *,
        text: str = "",
        placeholder: str = "",
        confirm_text: str = "确定",
    ) -> tuple[str, bool]:
        dialog = cls(
            parent, title, label_text,
            text=text, placeholder=placeholder, confirm_text=confirm_text,
        )
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return dialog.value(), accepted
