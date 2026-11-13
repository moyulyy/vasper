"""Vasper 启动入口。"""

from __future__ import annotations

import os
import sys

# 无独显/虚拟机的 Linux 环境下 WebGL 常被 Chromium 拉黑，启用 SwiftShader 兜底。
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "--enable-unsafe-swiftshader --ignore-gpu-blocklist --disable-gpu-compositing",
)

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

# QtWebEngine 需要在创建 QApplication 前设置共享 OpenGL 上下文。
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

from app import config, icons, subagents, theme  # noqa: E402
from app.widgets.main_window import MainWindow  # noqa: E402

# 首次运行：确保数据目录与工作区存在。
config.ensure_dirs()
subagents.ensure_builtins()


def _prepare_webengine() -> None:
    """把 Chromium 缓存放到可写的数据目录，避免只读 HOME 导致的报错。"""
    from PyQt6.QtWebEngineCore import QWebEngineProfile

    cache = config.DATA_DIR / "webengine-cache"
    storage = config.DATA_DIR / "webengine-storage"
    cache.mkdir(parents=True, exist_ok=True)
    storage.mkdir(parents=True, exist_ok=True)
    profile = QWebEngineProfile.defaultProfile()
    profile.setCachePath(str(cache))
    profile.setPersistentStoragePath(str(storage))


def main() -> int:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    app = QApplication(sys.argv)
    app.setApplicationName("Vasper")
    app.setOrganizationName("Vasper")
    app.setApplicationDisplayName("Vasper")
    _prepare_webengine()

    theme.apply(app, "dark")
    app.setWindowIcon(QIcon(icons.pixmap("atom", "#0A84FF", 64, 1.8)))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
