"""iOS 风格配色、字体与全局 QSS。"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication


@dataclass(frozen=True)
class Palette:
    mode: str
    bg1: str
    bg2: str
    surface: str
    surface_alt: str
    surface_sunken: str
    text: str
    text_soft: str
    muted: str
    faint: str
    border: str
    border_strong: str
    accent: str
    accent_hover: str
    accent_soft: str
    accent_text: str
    success: str
    danger: str
    warning: str
    code_bg: str
    code_text: str
    selection: str
    bubble_from: str
    bubble_to: str
    overlay: str
    frame: str


DARK = Palette(
    mode="dark",
    bg1="#0B0C10",
    bg2="#13151C",
    surface="#17191F",
    surface_alt="#20232B",
    surface_sunken="#1B1D24",
    text="#F5F5F7",
    text_soft="#D8D8DE",
    muted="#8E8E93",
    faint="#636366",
    border="#262932",
    border_strong="#343845",
    accent="#0A84FF",
    accent_hover="#3D9BFF",
    accent_soft="#122A42",
    accent_text="#FFFFFF",
    success="#30D158",
    danger="#FF453A",
    warning="#FFD60A",
    code_bg="#101116",
    code_text="#E5E5EA",
    selection="#1D3B5A",
    bubble_from="#0A84FF",
    bubble_to="#5E5CE6",
    overlay="#000000",
    frame="#05060A",
)

_current: Palette = DARK
_mode: str = "dark"
_font_family: str = ""


def resolve(mode: str) -> str:
    """Vasper 固定使用深色主题。"""
    return "dark"


def set_mode(mode: str) -> Palette:
    global _current, _mode
    _mode = "dark"
    _current = DARK
    return _current


def current() -> Palette:
    return _current


def mode() -> str:
    return _mode


def font_family() -> str:
    global _font_family
    if _font_family:
        return _font_family
    families = set(QFontDatabase.families())
    for candidate in (
        "PingFang SC", "SF Pro Text", "Inter", "Noto Sans CJK SC",
        "Source Han Sans SC", "WenQuanYi Micro Hei", "Microsoft YaHei UI",
        "Segoe UI", "DejaVu Sans",
    ):
        if candidate in families:
            _font_family = candidate
            break
    else:
        _font_family = QFont().defaultFamily()
    return _font_family


def mono_family() -> str:
    families = set(QFontDatabase.families())
    for candidate in ("SF Mono", "JetBrains Mono", "Cascadia Code", "Menlo", "Consolas", "DejaVu Sans Mono", "Noto Sans Mono"):
        if candidate in families:
            return candidate
    return "monospace"


def apply(app: QApplication, mode: str) -> Palette:
    palette = set_mode(mode)
    app.setStyle("Fusion")
    font = QFont(font_family(), 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    app.setStyleSheet(qss(palette))
    return palette


def qss(p: Palette) -> str:
    mapping = {
        "font": font_family(),
        "mono": mono_family(),
        "bg1": p.bg1,
        "bg2": p.bg2,
        "surface": p.surface,
        "surface_alt": p.surface_alt,
        "surface_sunken": p.surface_sunken,
        "text": p.text,
        "text_soft": p.text_soft,
        "muted": p.muted,
        "faint": p.faint,
        "border": p.border,
        "border_strong": p.border_strong,
        "accent": p.accent,
        "accent_hover": p.accent_hover,
        "accent_soft": p.accent_soft,
        "accent_text": p.accent_text,
        "success": p.success,
        "danger": p.danger,
        "warning": p.warning,
        "code_bg": p.code_bg,
        "code_text": p.code_text,
        "selection": p.selection,
        "bubble_from": p.bubble_from,
        "bubble_to": p.bubble_to,
        "frame": p.frame,
    }
    template = QSS_TEMPLATE
    for key, value in mapping.items():
        template = template.replace(f"%({key})s", str(value))
    return template


QSS_TEMPLATE = """
* { outline: none; }
QWidget {
    color: %(text)s;
    font-family: "%(font)s";
    font-size: 13px;
}
QMainWindow { background: transparent; }
QDialog { background: %(surface)s; }
QDialog#SheetDialog { background: transparent; }
#Root { background: transparent; }
#Body, #MessageArea { background: transparent; }
#TopBar { background: transparent; }

#Card, #Panel {
    background: %(surface)s;
    border: 1px solid %(border)s;
    border-radius: 18px;
}
QFrame#Sheet {
    background: %(surface)s;
    border: 1px solid %(border_strong)s;
    border-radius: 20px;
}
#SubCard {
    background: %(surface_alt)s;
    border: 1px solid %(border)s;
    border-radius: 14px;
}
#FloatingPanel {
    background: %(surface)s;
    border: 1px solid %(border)s;
    border-radius: 18px;
}
#Divider { background: %(border)s; border: none; }

QLabel { background: transparent; }
QLabel#AppTitle { font-size: 17px; font-weight: 700; letter-spacing: 0.2px; }
QLabel#Title { font-size: 15px; font-weight: 600; }
QLabel#Strong { font-size: 13px; font-weight: 600; }
QLabel#Subtitle { color: %(muted)s; font-size: 11px; }
QLabel#Muted { color: %(muted)s; font-size: 12px; }
QLabel#Faint { color: %(faint)s; font-size: 11px; }
QLabel#Section {
    color: %(muted)s; font-size: 11px; font-weight: 600; letter-spacing: 0.7px;
}
QLabel#Chip {
    background: %(surface_alt)s;
    border-radius: 10px;
    padding: 3px 9px;
    color: %(text_soft)s;
    font-size: 11px;
}
QLabel#Badge {
    background: %(accent_soft)s;
    color: %(accent)s;
    border-radius: 9px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#CountBadge {
    background: %(surface_alt)s;
    color: %(muted)s;
    border-radius: 9px;
    padding: 2px 7px;
    font-size: 10px;
    font-weight: 600;
}

QToolTip {
    background: %(text)s;
    color: %(surface)s;
    border: none;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 11px;
}

QLineEdit {
    background: %(surface_alt)s;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 7px 11px;
    color: %(text)s;
    selection-background-color: %(selection)s;
    selection-color: %(text)s;
}
QLineEdit:hover { border-color: %(border_strong)s; }
QLineEdit:focus { background: %(surface)s; border-color: %(accent)s; }
QLineEdit#Search { padding-left: 30px; }
#SubCard QLineEdit { background: %(surface)s; border: 1px solid %(border)s; }
#SubCard QLineEdit:focus { border-color: %(accent)s; }

QTextEdit, QPlainTextEdit {
    background: %(surface_alt)s;
    border: 1px solid transparent;
    border-radius: 12px;
    padding: 7px;
    color: %(text)s;
    selection-background-color: %(selection)s;
    selection-color: %(text)s;
}
QTextEdit:focus, QPlainTextEdit:focus {
    background: %(surface)s;
    border-color: %(accent)s;
}
QTextEdit#Composer {
    background: transparent;
    border: none;
    padding: 2px;
    font-size: 13px;
}

QPushButton {
    background: %(surface_alt)s;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 7px 13px;
    color: %(text_soft)s;
    font-size: 12px;
}
QPushButton:hover { background: %(surface_sunken)s; color: %(text)s; }
QPushButton:pressed { background: %(border)s; }
QPushButton:disabled { color: %(faint)s; background: %(surface_alt)s; }
QPushButton[variant="primary"] {
    background: %(accent)s;
    color: %(accent_text)s;
    font-weight: 600;
    padding: 8px 16px;
}
QPushButton[variant="primary"]:hover { background: %(accent_hover)s; }
QPushButton[variant="primary"]:pressed { background: %(accent_hover)s; }
QPushButton[variant="primary"]:disabled { background: %(border_strong)s; color: %(surface)s; }
QPushButton[variant="ghost"] { background: transparent; color: %(muted)s; }
QPushButton[variant="ghost"]:hover { background: %(surface_alt)s; color: %(text)s; }
QPushButton[variant="chip"] {
    background: %(surface_alt)s;
    border: 1px solid %(border)s;
    border-radius: 14px;
    padding: 6px 12px;
    color: %(text_soft)s;
}
QPushButton[variant="chip"]:hover { border-color: %(accent)s; color: %(accent)s; background: %(accent_soft)s; }
QPushButton[variant="danger"] { background: transparent; color: %(danger)s; border: 1px solid %(border)s; }
QPushButton[variant="danger"]:hover { background: %(danger)s; color: white; border-color: %(danger)s; }
QPushButton[variant="destructive"] {
    background: %(danger)s;
    color: white;
    border: none;
    font-weight: 600;
    padding: 8px 16px;
}
QPushButton[variant="destructive"]:hover { background: #FF5A50; }
QPushButton[variant="destructive"]:pressed { background: #E0342B; }
QPushButton[variant="seg"] {
    background: transparent;
    border: none;
    border-radius: 7px;
    padding: 4px 9px;
    color: %(muted)s;
    font-size: 11px;
}
QPushButton[variant="seg"]:hover { color: %(text)s; }
QPushButton[variant="seg"]:checked {
    background: %(surface)s;
    color: %(text)s;
    font-weight: 600;
}
#Segmented { background: %(surface_alt)s; border-radius: 9px; border: 1px solid %(border)s; }

QFrame#BubbleAssistant {
    background: %(surface_alt)s;
    border: 1px solid %(border)s;
    border-radius: 16px;
    border-top-left-radius: 5px;
}
QFrame#BubbleError {
    background: %(surface_alt)s;
    border: 1px solid %(danger)s;
    border-radius: 14px;
}
QTextBrowser {
    background: transparent;
    border: none;
    padding: 0;
}
QTextBrowser#BubbleBody { selection-background-color: %(selection)s; }

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical {
    background: transparent; width: 8px; margin: 2px 1px 2px 1px;
}
QScrollBar::handle:vertical {
    background: %(border_strong)s; min-height: 28px; border-radius: 3px;
}
QScrollBar::handle:vertical:hover { background: %(faint)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 1px 2px; }
QScrollBar::handle:horizontal { background: %(border_strong)s; min-width: 28px; border-radius: 3px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

QTreeWidget, QTreeView {
    background: transparent;
    border: none;
    show-decoration-selected: 1;
    outline: none;
    padding: 0;
}
QTreeWidget::item {
    height: 32px;
    border-radius: 8px;
    color: %(text_soft)s;
    padding: 0 4px;
}
QTreeWidget::item:hover { background: %(surface_alt)s; }
QTreeWidget::item:selected { background: %(accent_soft)s; color: %(accent)s; }
QTreeView::branch { background: transparent; }
QTreeView::branch:hover { background: transparent; }

QListWidget {
    background: transparent;
    border: none;
    outline: none;
}
QListWidget::item {
    border-radius: 12px;
    padding: 0;
    margin: 2px 0;
    color: %(text_soft)s;
}
QListWidget::item:hover { background: %(surface_alt)s; }
QListWidget::item:selected { background: %(accent_soft)s; color: %(text)s; }
QListWidget#SettingsNav {
    background: %(surface_alt)s;
    border: 1px solid %(border)s;
    border-radius: 12px;
    padding: 6px;
}
QListWidget#SettingsNav::item {
    height: 34px;
    padding: 0 8px;
    border-radius: 8px;
    color: %(muted)s;
    font-size: 12px;
}
QListWidget#SettingsNav::item:hover { background: %(surface_sunken)s; }
QListWidget#SettingsNav::item:selected {
    background: %(accent_soft)s;
    color: %(accent)s;
    font-weight: 600;
}
QListWidget#NodeList {
    background: %(surface_alt)s;
    border: 1px solid %(border)s;
    border-radius: 12px;
    padding: 6px;
}
QListWidget#NodeList::item {
    height: 54px;
    padding: 6px 8px;
    border-radius: 8px;
    color: %(muted)s;
    font-size: 11px;
}
QListWidget#NodeList::item:selected {
    background: %(accent_soft)s;
    color: %(accent)s;
}
QListWidget#AgentList {
    background: %(surface_alt)s;
    border: 1px solid %(border)s;
    border-radius: 12px;
    padding: 6px;
}
QListWidget#AgentList::item {
    height: 52px;
    padding: 6px 8px;
    border-radius: 8px;
    color: %(muted)s;
    font-size: 11px;
}
QListWidget#AgentList::item:selected {
    background: %(accent_soft)s;
    color: %(accent)s;
}
QTreeWidget#AgentTree {
    background: %(surface_alt)s;
    border: 1px solid %(border)s;
    border-radius: 12px;
    padding: 6px;
}
QTreeWidget#AgentTree::item {
    height: 27px;
    border-radius: 6px;
    color: %(text_soft)s;
    font-size: 11.5px;
}
QTreeWidget#AgentTree::item:hover { background: %(surface_sunken)s; }
QTreeWidget#AgentTree::item:selected { background: %(accent_soft)s; color: %(accent)s; }

QMenu {
    background: %(surface)s;
    border: 1px solid %(border)s;
    border-radius: 12px;
    padding: 6px;
}
QMenu::item {
    padding: 7px 26px 7px 12px;
    border-radius: 7px;
    color: %(text_soft)s;
    font-size: 12px;
}
QMenu::item:selected { background: %(accent_soft)s; color: %(accent)s; }
QMenu::item:disabled { color: %(faint)s; }
QMenu::separator { height: 1px; background: %(border)s; margin: 5px 8px; }

QComboBox {
    background: %(surface_alt)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
    padding: 7px 11px;
    color: %(text)s;
}
QComboBox:hover { border-color: %(border_strong)s; }
QSpinBox {
    background: %(surface_alt)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
    padding: 7px 11px;
    color: %(text)s;
    selection-background-color: %(selection)s;
}
QSpinBox:focus { border-color: %(accent)s; }
QSpinBox QLineEdit {
    background: transparent;
    border: none;
    padding: 0;
}
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: %(surface)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
    padding: 5px;
    selection-background-color: %(accent_soft)s;
    selection-color: %(accent)s;
    outline: none;
}

QSlider::groove:horizontal {
    height: 4px; background: %(surface_alt)s; border-radius: 2px;
}
QSlider::sub-page:horizontal { background: %(accent)s; border-radius: 2px; }
QSlider::handle:horizontal {
    width: 16px; height: 16px; margin: -6px 0;
    background: %(surface)s; border: 2px solid %(accent)s; border-radius: 8px;
}

QCheckBox { color: %(text_soft)s; spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid %(border_strong)s; background: %(surface)s;
}
QCheckBox::indicator:checked { background: %(accent)s; border-color: %(accent)s; }

QSplitter::handle { background: transparent; }
QSplitter::handle:horizontal { width: 7px; }

QProgressBar {
    background: %(surface_alt)s; border: none; border-radius: 3px; height: 6px;
    text-align: center; color: transparent;
}
QProgressBar::chunk { background: %(accent)s; border-radius: 3px; }

QPushButton#SendButton {
    background: %(accent)s;
}
QPushButton#SendButton:hover { background: %(accent_hover)s; }

QScrollArea#ChatScroll { background: transparent; border: none; }
QScrollBar#ChatScroll:vertical { width: 6px; }
QToolButton { background: transparent; border: none; padding: 0; }
"""
