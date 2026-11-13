"""左侧可折叠文件管理器：懒加载目录树、搜索、右键菜单、上传与预览。"""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QPlainTextEdit, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)

from .. import config, files, icons, theme
from .components import Card, IconButton, IconTile, Pill
from .sheets import ConfirmSheet, InputSheet, SheetDialog

PATH_ROLE = Qt.ItemDataRole.UserRole
TYPE_ROLE = Qt.ItemDataRole.UserRole + 1
LOADED_ROLE = Qt.ItemDataRole.UserRole + 2
STRUCT_ROLE = Qt.ItemDataRole.UserRole + 3
EXT_ROLE = Qt.ItemDataRole.UserRole + 4

STRUCTURE_COLOR = "#0A84FF"


def human_size(size: int) -> str:
    value = float(size or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return ""


class StructureTree(QTreeWidget):
    files_dropped = pyqtSignal(list, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(15)
        self.setAnimated(True)
        self.setUniformRowHeights(True)
        self.setRootIsDecorated(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setFont(QFont(theme.font_family(), 10))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def dropEvent(self, event) -> None:  # noqa: N802
        paths: list[str] = []
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    paths.append(url.toLocalFile())
        if not paths:
            return
        item = self.itemAt(event.position().toPoint())
        folder = ""
        while item is not None and item.data(0, TYPE_ROLE) != "dir":
            item = item.parent()
        if item is not None:
            folder = item.data(0, PATH_ROLE) or ""
        event.acceptProposedAction()
        self.files_dropped.emit(paths, folder)


class PreviewDialog(SheetDialog):
    def __init__(self, parent: QWidget | None, name: str, path: str, text: str) -> None:
        super().__init__(parent, name, path, icon="file-code", width=760)
        self.setFixedHeight(660)
        layout = self.body

        meta = QHBoxLayout()
        meta.addWidget(Pill(human_size(len(text.encode("utf-8")))))
        meta.addStretch(1)
        layout.addLayout(meta)

        editor = QPlainTextEdit()
        editor.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        editor.setPlainText(text)
        editor.setReadOnly(True)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        editor.setStyleSheet(
            f"font-family: '{theme.mono_family()}'; font-size: 12px;"
            f" background: {theme.current().surface_alt}; border-radius: 12px; padding: 12px;"
        )
        layout.addWidget(editor, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        copy_button = QPushButton("复制路径")
        copy_button.clicked.connect(lambda: self._copy(path))
        close_button = QPushButton("关闭")
        close_button.setProperty("variant", "primary")
        close_button.clicked.connect(self.accept)
        footer.addWidget(copy_button)
        footer.addWidget(close_button)
        layout.addLayout(footer)

    def _copy(self, text: str) -> None:
        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText(text)


class FilePanel(Card):
    structure_selected = pyqtSignal(str, str)
    notify = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, object_name="Panel")
        self.setMinimumWidth(0)
        self.setMaximumWidth(280)
        self._root_name = ""
        self._show_hidden = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title = QLabel("文件")
        title.setObjectName("Title")
        self._subtitle = QLabel("工作区")
        self._subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(self._subtitle)
        header.addLayout(title_box)
        header.addStretch(1)

        self._new_folder_button = IconButton("plus", "新建文件夹", diameter=28, icon_size=15)
        self._new_folder_button.clicked.connect(self._new_folder)
        self._collapse_button = IconButton("chevrons-down-up", "折叠所有目录", diameter=28, icon_size=15)
        self._collapse_button.clicked.connect(self._collapse_all)
        self._upload_button = IconButton("upload", "上传文件", diameter=28, icon_size=15)
        self._upload_button.clicked.connect(self._upload)
        self._refresh_button = IconButton("refresh", "刷新", diameter=28, icon_size=15)
        self._refresh_button.clicked.connect(self.refresh)
        for button in (self._collapse_button, self._new_folder_button, self._upload_button, self._refresh_button):
            header.addWidget(button)
        layout.addLayout(header)

        self._search = QLineEdit()
        self._search.setObjectName("Search")
        self._search.setPlaceholderText("搜索文件…")
        self._search.setClearButtonEnabled(True)
        self._search_action = QAction(icons.icon("search", theme.current().muted, 15), "", self._search)
        self._search.addAction(self._search_action, QLineEdit.ActionPosition.LeadingPosition)
        self._search.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

        self._tree = StructureTree(self)
        self._tree.itemExpanded.connect(self._on_expanded)
        self._tree.itemClicked.connect(self._on_clicked)
        self._tree.itemDoubleClicked.connect(self._on_double_clicked)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.files_dropped.connect(self._on_dropped)
        layout.addWidget(self._tree, 1)

        self._footer = QLabel("拖入结构文件即可上传")
        self._footer.setObjectName("Faint")
        self._footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._footer)

        self._apply_branch_style()
        self.refresh()

    def _apply_branch_style(self) -> None:
        """用生成的 PNG 作为展开箭头，保持与主题一致的 iOS 风格。"""
        palette = theme.current()
        folder = config.DATA_DIR / "icons"
        folder.mkdir(parents=True, exist_ok=True)
        paths: dict[str, str] = {}
        for state, name in (("closed", "chevron-right"), ("open", "chevron-down")):
            target = folder / f"branch-{state}-{palette.mode}.png"
            pix = icons.pixmap(name, palette.muted, 10, 2.1)
            image = pix.toImage().scaled(
                10,
                10,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            image.save(str(target))
            paths[state] = target.as_posix()
        self._tree.setStyleSheet(
            'QTreeView::branch:has-children:closed { image: url("%s"); }'
            'QTreeView::branch:has-children:open { image: url("%s"); }'
            % (paths["closed"], paths["open"])
        )

    # ------------------------------------------------------------------ 数据
    def refresh(self) -> None:
        expanded = self._expanded_paths()
        self._tree.clear()
        try:
            payload = files.list_dir("")
        except Exception as exc:
            self.notify.emit(f"读取工作区失败：{exc}", "error")
            return
        self._root_name = payload.get("name") or "工作区"
        self._subtitle.setText(f"工作区 · {self._root_name}")
        root = self._tree.invisibleRootItem()
        if not payload["entries"]:
            self._footer.setText("工作区为空，拖入结构文件开始")
        else:
            self._footer.setText("拖入结构文件即可上传")
        for entry in payload["entries"]:
            self._add_entry(root, entry)
        for path in sorted(expanded):
            self._expand_path(path)
        self._apply_filter(self._search.text())

    def _add_entry(self, parent: QTreeWidgetItem, entry: dict) -> None:
        item = QTreeWidgetItem(parent)
        item.setData(0, PATH_ROLE, entry["path"])
        item.setData(0, TYPE_ROLE, entry["type"])
        item.setData(0, STRUCT_ROLE, bool(entry.get("structure")))
        item.setData(0, EXT_ROLE, entry.get("ext", ""))
        item.setData(0, LOADED_ROLE, entry["type"] != "dir")
        self._decorate(item, entry)
        if entry["type"] == "dir":
            placeholder = QTreeWidgetItem(item)
            placeholder.setText(0, "…")
            placeholder.setData(0, PATH_ROLE, "")
            placeholder.setData(0, TYPE_ROLE, "placeholder")
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)

    def _decorate(self, item: QTreeWidgetItem, entry: dict) -> None:
        palette = theme.current()
        name = entry["name"]
        if entry["type"] == "dir":
            item.setText(0, name)
            item.setIcon(0, icons.icon("folder", palette.accent if entry.get("expanded") else palette.muted, 16, 1.7))
            font = QFont(theme.font_family(), 10)
            font.setWeight(QFont.Weight.DemiBold)
            item.setFont(0, font)
        else:
            item.setText(0, name)
            if entry.get("structure"):
                item.setIcon(0, icons.icon("atom", STRUCTURE_COLOR, 16, 1.7))
            elif entry.get("ext") in {"py", "js", "sh", "c", "cpp", "h", "f90", "f"}:
                item.setIcon(0, icons.icon("file-code", palette.muted, 16, 1.7))
            else:
                item.setIcon(0, icons.icon("file", palette.muted, 16, 1.7))
            item.setToolTip(0, f"{entry['path']}\n{human_size(entry.get('size', 0))}")

    def _load_dir(self, item: QTreeWidgetItem) -> None:
        if item.data(0, LOADED_ROLE):
            return
        path = item.data(0, PATH_ROLE) or ""
        item.takeChildren()
        try:
            payload = files.list_dir(path)
        except Exception as exc:
            self.notify.emit(f"读取文件夹失败：{exc}", "error")
            item.setData(0, LOADED_ROLE, True)
            return
        for entry in payload["entries"]:
            self._add_entry(item, entry)
        item.setData(0, LOADED_ROLE, True)
        if not payload["entries"]:
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)

    def _expanded_paths(self) -> set[str]:
        result: set[str] = set()

        def walk(item: QTreeWidgetItem) -> None:
            if item.data(0, TYPE_ROLE) == "dir" and item.isExpanded():
                path = item.data(0, PATH_ROLE)
                if path:
                    result.add(path)
            for index in range(item.childCount()):
                walk(item.child(index))

        root = self._tree.invisibleRootItem()
        for index in range(root.childCount()):
            walk(root.child(index))
        return result

    def _expand_path(self, path: str) -> None:
        current = self._tree.invisibleRootItem()
        for part in path.split("/"):
            found = None
            for index in range(current.childCount()):
                child = current.child(index)
                if child.text(0) == part and child.data(0, TYPE_ROLE) == "dir":
                    found = child
                    break
            if found is None:
                return
            self._load_dir(found)
            found.setExpanded(True)
            current = found

    # ------------------------------------------------------------------ 交互
    def _on_expanded(self, item: QTreeWidgetItem) -> None:
        if item.data(0, TYPE_ROLE) == "dir":
            self._load_dir(item)

    def _on_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        kind = item.data(0, TYPE_ROLE)
        if kind == "dir":
            # 目录的展开 / 折叠交给树的默认分支箭头与双击处理，
            # 避免单击行时和默认行为相互抵消。
            return
        if kind != "file":
            return
        path = item.data(0, PATH_ROLE) or ""
        name = item.text(0)
        if item.data(0, STRUCT_ROLE):
            self.structure_selected.emit(path, name)
        else:
            self._preview(path, name)

    def _on_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if item.data(0, TYPE_ROLE) == "dir":
            self._load_dir(item)

    def _collapse_all(self) -> None:
        self._tree.collapseAll()
        item = self._tree.currentItem()
        if item is not None:
            self._tree.setCurrentItem(item)
        self.notify.emit("已折叠全部目录", "info")

    def _preview(self, path: str, name: str) -> None:
        try:
            payload = files.read_text(path)
        except Exception as exc:
            self.notify.emit(str(exc), "error")
            return
        PreviewDialog(self.window(), name, path, payload["text"]).exec()

    def _new_folder(self) -> None:
        item = self._tree.currentItem()
        base = ""
        while item is not None and item.data(0, TYPE_ROLE) != "dir":
            item = item.parent()
        if item is not None:
            base = item.data(0, PATH_ROLE) or ""
        name, ok = InputSheet.get_text(
            self, "新建文件夹", "文件夹名称", placeholder="例如 structures"
        )
        if not ok or not name.strip():
            return
        try:
            entry = files.make_dir(base, name.strip())
        except Exception as exc:
            self.notify.emit(str(exc), "error")
            return
        self.notify.emit(f"已创建 {entry['name']}", "success")
        self.refresh()

    def _upload(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "上传到工作区")
        if not paths:
            return
        self._copy_files(paths, self._current_folder())

    def _current_folder(self) -> str:
        item = self._tree.currentItem()
        while item is not None and item.data(0, TYPE_ROLE) != "dir":
            item = item.parent()
        return (item.data(0, PATH_ROLE) or "") if item is not None else ""

    def _copy_files(self, paths: list[str], folder: str) -> None:
        saved = []
        errors = []
        for path in paths:
            try:
                with open(path, "rb") as handle:
                    saved.append(files.save_upload(folder, Path(path).name, handle))
            except Exception as exc:
                errors.append(f"{Path(path).name}: {exc}")
        if saved:
            self.notify.emit(f"已上传 {len(saved)} 个文件", "success")
            self._reload_folder(folder)
        if errors:
            self.notify.emit(errors[0], "error")

    def _reload_folder(self, folder: str) -> None:
        if not folder:
            self.refresh()
            return
        current = self._tree.invisibleRootItem()
        target = None
        for part in folder.split("/"):
            found = None
            for index in range(current.childCount()):
                child = current.child(index)
                if child.text(0) == part and child.data(0, TYPE_ROLE) == "dir":
                    found = child
                    break
            if found is None:
                self.refresh()
                return
            current = found
            target = found
        if target is None:
            self.refresh()
            return
        target.setData(0, LOADED_ROLE, False)
        target.setExpanded(False)
        self._load_dir(target)
        target.setExpanded(True)

    def _on_dropped(self, paths: list[str], folder: str) -> None:
        self._copy_files(paths, folder)

    def _on_context_menu(self, position) -> None:
        item = self._tree.itemAt(position)
        menu = QMenu(self)
        new_action = menu.addAction(icons.icon("plus", theme.current().text_soft, 14), "新建文件夹")
        if item is not None and item.data(0, TYPE_ROLE) in {"dir", "file"}:
            path = item.data(0, PATH_ROLE) or ""
            name = item.text(0)
            if item.data(0, TYPE_ROLE) == "file":
                open_action = menu.addAction(
                    icons.icon("eye", theme.current().text_soft, 14),
                    "预览" if not item.data(0, STRUCT_ROLE) else "在 3D 中查看",
                )
                open_action.triggered.connect(
                    lambda: self.structure_selected.emit(path, name)
                    if item.data(0, STRUCT_ROLE)
                    else self._preview(path, name)
                )
            rename_action = menu.addAction(icons.icon("pencil", theme.current().text_soft, 14), "重命名")
            delete_action = menu.addAction(icons.icon("trash", theme.current().danger, 14), "删除")
            menu.addSeparator()
            reveal_action = menu.addAction(icons.icon("external", theme.current().text_soft, 14), "在文件管理器中显示")
            rename_action.triggered.connect(lambda: self._rename(item))
            delete_action.triggered.connect(lambda: self._delete(item))
            reveal_action.triggered.connect(lambda: self._reveal(path))
        chosen = menu.exec(self._tree.viewport().mapToGlobal(position))
        if chosen is new_action:
            self._new_folder()

    def _rename(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, PATH_ROLE) or ""
        old = item.text(0)
        name, ok = InputSheet.get_text(
            self, "重命名", "新名称", text=old, placeholder="输入新名称"
        )
        if not ok or not name.strip() or name.strip() == old:
            return
        try:
            files.rename(path, name.strip())
        except Exception as exc:
            self.notify.emit(str(exc), "error")
            return
        self.notify.emit("已重命名", "success")
        self.refresh()

    def _delete(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, PATH_ROLE) or ""
        name = item.text(0)
        confirmed = ConfirmSheet.ask(
            self,
            "删除文件",
            f"确定要删除“{name}”吗？此操作不可撤销。",
            "删除",
        )
        if not confirmed:
            return
        try:
            files.delete(path)
        except Exception as exc:
            self.notify.emit(str(exc), "error")
            return
        self.notify.emit(f"已删除 {name}", "success")
        self.refresh()

    def _reveal(self, path: str) -> None:
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices

            target = files.safe_path(path, must_exist=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target if target.is_dir() else target.parent)))
        except Exception as exc:
            self.notify.emit(str(exc), "error")

    # ------------------------------------------------------------------ 过滤/主题
    def _apply_filter(self, text: str) -> None:
        needle = text.strip().casefold()

        def visit(item: QTreeWidgetItem) -> bool:
            if item.data(0, TYPE_ROLE) == "placeholder":
                return False
            match = not needle or needle in item.text(0).casefold()
            child_match = False
            for index in range(item.childCount()):
                child = item.child(index)
                if visit(child):
                    child_match = True
            item.setHidden(not (match or child_match))
            return match or child_match

        root = self._tree.invisibleRootItem()
        for index in range(root.childCount()):
            visit(root.child(index))

    def apply_theme(self) -> None:
        self._search_action.setIcon(icons.icon("search", theme.current().muted, 15))
        self._apply_branch_style()
        for button in (self._new_folder_button, self._upload_button, self._refresh_button):
            button.update()
        root = self._tree.invisibleRootItem()

        def walk(item: QTreeWidgetItem) -> None:
            kind = item.data(0, TYPE_ROLE)
            if kind in {"dir", "file"}:
                entry = {
                    "name": item.text(0),
                    "path": item.data(0, PATH_ROLE),
                    "type": kind,
                    "structure": bool(item.data(0, STRUCT_ROLE)),
                    "ext": item.data(0, EXT_ROLE) or "",
                    "expanded": item.isExpanded(),
                }
                self._decorate(item, entry)
            for index in range(item.childCount()):
                walk(item.child(index))

        for index in range(root.childCount()):
            walk(root.child(index))
