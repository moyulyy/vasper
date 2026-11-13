"""右侧会话管理面板：历史列表、搜索、重命名与删除。"""

from __future__ import annotations

from datetime import date, datetime

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMenu, QSizePolicy, QVBoxLayout, QWidget,
)

from .. import icons, theme
from .components import Card, IconButton
from .sheets import InputSheet

SESSION_ROLE = Qt.ItemDataRole.UserRole


def _parse_time(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value or "")
    except (TypeError, ValueError):
        return None


def _time_label(value: str | None) -> str:
    stamp = _parse_time(value)
    if stamp is None:
        return ""
    today = date.today()
    if stamp.date() == today:
        return stamp.strftime("%H:%M")
    if (today - stamp.date()).days == 1:
        return "昨天"
    return stamp.strftime("%m-%d")


class SessionRow(QWidget):
    def __init__(self, session: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        palette = theme.current()
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(3)

        top = QHBoxLayout()
        top.setSpacing(6)
        title = QLabel()
        full_title = session.get("title") or "新会话"
        title.setText(title.fontMetrics().elidedText(full_title, Qt.TextElideMode.ElideRight, 196))
        title.setToolTip(full_title)
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        title_font = QFont(theme.font_family(), 10)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {palette.text}; background: transparent;")
        top.addWidget(title, 1)
        time_label = QLabel(_time_label(session.get("updated")))
        time_label.setStyleSheet(f"color: {palette.faint}; font-size: 9.5px; background: transparent;")
        top.addWidget(time_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)

        preview = QLabel()
        text = " ".join((session.get("preview") or "还没有消息").split())
        if len(text) > 34:
            text = text[:34] + "…"
        preview.setText(text)
        preview.setStyleSheet(f"color: {palette.muted}; font-size: 10px; background: transparent;")
        layout.addWidget(preview)


class SessionPanel(Card):
    selected = pyqtSignal(str)
    new_requested = pyqtSignal()
    rename_requested = pyqtSignal(str, str)
    delete_requested = pyqtSignal(str)
    close_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, object_name="FloatingPanel")
        self.setMinimumWidth(0)
        self.setMaximumWidth(300)
        self._sessions: list[dict] = []
        self._current_id = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title = QLabel("会话")
        title.setObjectName("Title")
        self._count = QLabel("0")
        self._count.setObjectName("CountBadge")
        subtitle_row = QHBoxLayout()
        subtitle_row.setSpacing(6)
        subtitle = QLabel("历史对话")
        subtitle.setObjectName("Subtitle")
        subtitle_row.addWidget(subtitle)
        subtitle_row.addWidget(self._count)
        subtitle_row.addStretch(1)
        title_box.addWidget(title)
        title_box.addLayout(subtitle_row)
        header.addLayout(title_box)
        header.addStretch(1)
        self._new_button = IconButton("plus", "新建对话", diameter=28, icon_size=15)
        self._new_button.clicked.connect(self.new_requested.emit)
        header.addWidget(self._new_button)
        self._close_button = IconButton("x", "收起会话", diameter=28, icon_size=14)
        self._close_button.clicked.connect(self.close_requested.emit)
        header.addWidget(self._close_button)
        layout.addLayout(header)

        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索会话…")
        self._search.setClearButtonEnabled(True)
        self._search_action = self._search.addAction(
            icons.icon("search", theme.current().muted, 15),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self._search.textChanged.connect(lambda _text: self._rebuild())
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.setObjectName("SessionList")
        self._list.setFrameShape(QFrame.Shape.NoFrame)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setSpacing(1)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.itemClicked.connect(self._on_clicked)
        self._list.customContextMenuRequested.connect(self._on_menu)
        layout.addWidget(self._list, 1)

        self._empty = QLabel("还没有历史会话\n开始一段新的对话吧")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setObjectName("Faint")
        self._empty.setStyleSheet(f"color: {theme.current().faint}; font-size: 11px; line-height: 1.7;")
        layout.addWidget(self._empty, 1)

    # ------------------------------------------------------------------ 数据
    def set_sessions(self, items: list[dict], current_id: str | None = None) -> None:
        self._sessions = items
        if current_id is not None:
            self._current_id = current_id
        self._count.setText(str(len(items)))
        self._rebuild()
        self._apply_selection()

    def set_current(self, session_id: str | None) -> None:
        self._current_id = session_id or ""
        self._apply_selection()

    def _filtered(self) -> list[dict]:
        needle = self._search.text().strip().casefold()
        if not needle:
            return self._sessions
        return [
            item for item in self._sessions
            if needle in (item.get("title") or "").casefold()
            or needle in (item.get("preview") or "").casefold()
        ]

    def _rebuild(self) -> None:
        self._list.clear()
        items = self._filtered()
        self._empty.setVisible(not items)
        palette = theme.current()
        groups: dict[str, list[dict]] = {"今天": [], "昨天": [], "更早": []}
        for item in items:
            stamp = _parse_time(item.get("updated"))
            if stamp is None:
                groups["更早"].append(item)
                continue
            delta = (date.today() - stamp.date()).days
            if delta <= 0:
                groups["今天"].append(item)
            elif delta == 1:
                groups["昨天"].append(item)
            else:
                groups["更早"].append(item)

        for group_name, group_items in groups.items():
            if not group_items:
                continue
            header = QListWidgetItem(group_name)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            header.setSizeHint(QSize(0, 26))
            header.setFont(QFont(theme.font_family(), 8))
            header.setForeground(Qt.GlobalColor.gray)
            self._list.addItem(header)
            for session in group_items:
                item = QListWidgetItem()
                item.setData(SESSION_ROLE, session.get("id"))
                item.setSizeHint(QSize(0, 62))
                widget = SessionRow(session)
                self._list.addItem(item)
                self._list.setItemWidget(item, widget)
        self._apply_selection()

    def _apply_selection(self) -> None:
        for index in range(self._list.count()):
            item = self._list.item(index)
            sid = item.data(SESSION_ROLE)
            if sid == self._current_id and sid:
                self._list.setCurrentItem(item)
                return
        self._list.clearSelection()

    # ------------------------------------------------------------------ 交互
    def _on_clicked(self, item: QListWidgetItem) -> None:
        session_id = item.data(SESSION_ROLE)
        if session_id:
            self._current_id = session_id
            self.selected.emit(session_id)

    def _on_menu(self, position) -> None:
        item = self._list.itemAt(position)
        if item is None:
            return
        session_id = item.data(SESSION_ROLE)
        if not session_id:
            return
        session = next((entry for entry in self._sessions if entry.get("id") == session_id), {})
        menu = QMenu(self)
        rename = menu.addAction(icons.icon("pencil", theme.current().text_soft, 14), "重命名")
        delete = menu.addAction(icons.icon("trash", theme.current().danger, 14), "删除")
        chosen = menu.exec(self._list.viewport().mapToGlobal(position))
        if chosen is rename:
            title, ok = InputSheet.get_text(
                self, "重命名会话", "会话标题",
                text=session.get("title") or "", placeholder="输入会话标题",
            )
            if ok and title.strip():
                self.rename_requested.emit(session_id, title.strip())
        elif chosen is delete:
            self.delete_requested.emit(session_id)

    def apply_theme(self) -> None:
        self._search_action.setIcon(icons.icon("search", theme.current().muted, 15))
        self._empty.setStyleSheet(
            f"color: {theme.current().faint}; font-size: 11px; line-height: 1.7;"
        )
        self._count.setStyleSheet("")
        self._rebuild()
