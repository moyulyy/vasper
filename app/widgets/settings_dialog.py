"""设置面板：模型服务、计算节点、工作区与关于，使用左侧分页。"""

from __future__ import annotations

import copy
import socket

from PyQt6.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QGuiApplication, QIntValidator
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSlider,
    QStackedWidget, QVBoxLayout, QWidget,
)

from .. import __version__, config, icons
from .components import Divider, IconButton, TextButton
from .sheets import SheetDialog


class ConnectionTester(QThread):
    result = pyqtSignal(bool, str)

    def __init__(self, host: str, port: int, parent=None) -> None:
        super().__init__(parent)
        self._host = host
        self._port = port

    def run(self) -> None:  # noqa: D401
        try:
            with socket.create_connection((self._host, self._port), timeout=3.0):
                self.result.emit(True, f"连接成功：{self._host}:{self._port}")
        except Exception as exc:
            self.result.emit(False, f"连接失败：{exc}")


class SettingsDialog(SheetDialog):
    settings_saved = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, "设置", "模型服务、计算节点与工作区", icon="settings", width=780)
        screen = (parent.window().screen() if parent is not None else None) or QGuiApplication.primaryScreen()
        available = screen.availableGeometry().height() if screen is not None else 900
        self.setFixedHeight(min(720, max(560, available - 70)))
        self._public = config.public_settings()
        self._nodes: list[dict] = [dict(node) for node in self._public.get("compute", {}).get("nodes", [])]
        self._current_node = -1
        self._loading_node = False
        self._tester: ConnectionTester | None = None
        public = self._public

        root = self.body
        root.setSpacing(12)

        content = QHBoxLayout()
        content.setSpacing(14)
        self._nav = QListWidget()
        self._nav.setObjectName("SettingsNav")
        self._nav.setFixedWidth(168)
        self._nav.setFrameShape(QFrame.Shape.NoFrame)
        self._nav.setIconSize(QSize(16, 16))
        for label, icon_name in (
            ("模型服务", "settings"),
            ("计算节点", "flask"),
            ("工作区", "folder"),
            ("关于", "info"),
        ):
            item = QListWidgetItem(icons.icon(icon_name, "#8E8E93", 16), label)
            item.setSizeHint(QSize(0, 38))
            self._nav.addItem(item)
        self._nav.currentRowChanged.connect(self._on_page_changed)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._scroll_page(self._build_llm_page(public)))
        self._stack.addWidget(self._scroll_page(self._build_compute_page()))
        self._stack.addWidget(self._scroll_page(self._build_workspace_page(public)))
        self._stack.addWidget(self._scroll_page(self._build_about_page(public)))
        content.addWidget(self._nav)
        content.addWidget(self._stack, 1)
        root.addLayout(content, 1)

        root.addWidget(Divider())
        footer = QHBoxLayout()
        footer.setSpacing(8)
        self._footer_status = QLabel(f"数据目录：{public['data_dir']}")
        self._footer_status.setObjectName("Faint")
        self._footer_status.setWordWrap(True)
        footer.addWidget(self._footer_status, 1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存")
        save.setProperty("variant", "primary")
        save.clicked.connect(self._save)
        footer.addWidget(cancel)
        footer.addWidget(save)
        root.addLayout(footer)

        self._nav.setCurrentRow(0)
        self._refresh_node_list(0 if self._nodes else -1)

    # ------------------------------------------------------------------ 页面
    def _scroll_page(self, page: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        return scroll

    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)
        return page, layout

    def _section(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setObjectName("Section")
        return label

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Muted")
        return label

    def _labeled(self, text: str, widget: QWidget) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._field_label(text))
        layout.addWidget(widget)
        return box

    def _card_frame(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("SubCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)
        return card, layout

    def _build_llm_page(self, public: dict) -> QWidget:
        page, layout = self._page()
        layout.addWidget(self._section("模型服务"))
        card, model_layout = self._card_frame()

        model_layout.addWidget(self._field_label("API Base URL"))
        self._base_url = QLineEdit(public["llm"]["base_url"])
        self._base_url.setPlaceholderText("https://api.example.com/v1（留空使用 OpenAI 官方地址）")
        model_layout.addWidget(self._base_url)

        model_layout.addWidget(self._field_label("API Key"))
        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        if public["llm"]["has_api_key"]:
            self._api_key.setPlaceholderText(f"已保存（{public['llm']['api_key_hint']}），留空保持不变")
        else:
            self._api_key.setPlaceholderText("sk-…")
        key_row.addWidget(self._api_key, 1)
        self._eye_button = IconButton("eye", "显示/隐藏", diameter=30, icon_size=16)
        self._eye_button.setCheckable(True)
        self._eye_button.toggled.connect(self._toggle_eye)
        key_row.addWidget(self._eye_button)
        model_layout.addLayout(key_row)

        model_layout.addWidget(self._field_label("模型名称"))
        self._model = QLineEdit(public["llm"]["model"])
        self._model.setPlaceholderText("例如 kimi-k3 / gpt-4o / deepseek-chat")
        model_layout.addWidget(self._model)

        temp_row = QHBoxLayout()
        temp_row.setSpacing(10)
        temp_row.addWidget(self._field_label("温度"))
        self._temperature = QSlider(Qt.Orientation.Horizontal)
        self._temperature.setRange(0, 20)
        self._temperature.setValue(int(round(float(public["llm"]["temperature"]) * 10)))
        self._temperature.setPageStep(2)
        self._temperature.setMinimumWidth(300)
        temp_row.addWidget(self._temperature, 1)
        self._temperature_value = QLabel(f"{public['llm']['temperature']:.1f}")
        self._temperature_value.setObjectName("Muted")
        self._temperature_value.setMinimumWidth(28)
        self._temperature_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        temp_row.addWidget(self._temperature_value)
        self._temperature.valueChanged.connect(
            lambda value: self._temperature_value.setText(f"{value / 10:.1f}")
        )
        model_layout.addLayout(temp_row)

        hint_row = QHBoxLayout()
        self._llm_status = QLabel("")
        self._llm_status.setObjectName("Faint")
        self._llm_status.setWordWrap(True)
        hint_row.addWidget(self._llm_status, 1)
        self._import_button = TextButton("导入 sci-circle 配置", variant="ghost", icon_name="download")
        self._import_button.clicked.connect(self._import_sci)
        hint_row.addWidget(self._import_button)
        model_layout.addLayout(hint_row)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_compute_page(self) -> QWidget:
        page, layout = self._page()
        layout.addWidget(self._section("计算节点"))
        info = QLabel("保存 SSH 节点与调度器配置；当前版本不会自动提交作业。密码仅保存在本机设置文件中。")
        info.setObjectName("Faint")
        info.setWordWrap(True)
        layout.addWidget(info)

        body = QHBoxLayout()
        body.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(6)
        self._node_list = QListWidget()
        self._node_list.setObjectName("NodeList")
        self._node_list.setFrameShape(QFrame.Shape.NoFrame)
        self._node_list.setWordWrap(True)
        self._node_list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self._node_list.setFixedWidth(184)
        self._node_list.currentRowChanged.connect(self._load_node)
        left.addWidget(self._node_list, 1)
        add_button = TextButton("添加节点", variant="chip", icon_name="plus")
        add_button.clicked.connect(self._add_node)
        left.addWidget(add_button)
        remove_button = TextButton("删除", variant="ghost", icon_name="trash")
        remove_button.clicked.connect(self._remove_node)
        left.addWidget(remove_button)
        body.addLayout(left)

        form_box = QWidget()
        form_layout = QVBoxLayout(form_box)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)
        self._node_form = QWidget()
        grid = QGridLayout(self._node_form)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        self._node_name = QLineEdit()
        self._node_name.setPlaceholderText("例如 计算节点 A")
        self._node_host = QLineEdit()
        self._node_host.setPlaceholderText("hostname 或 IP")
        self._node_port = QLineEdit("22")
        self._node_port.setValidator(QIntValidator(1, 65535, self))
        self._node_port.setPlaceholderText("22")
        self._node_user = QLineEdit()
        self._node_user.setPlaceholderText("ssh 用户名")
        self._node_auth = QComboBox()
        self._node_auth.addItems(["密码", "密钥"])
        self._node_auth.currentIndexChanged.connect(self._on_auth_changed)
        self._node_password = QLineEdit()
        self._node_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._node_password.setPlaceholderText("SSH 密码")
        self._node_key_path = QLineEdit()
        self._node_key_path.setPlaceholderText("~/.ssh/id_rsa")
        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        key_row.addWidget(self._node_key_path, 1)
        key_button = TextButton("浏览", variant="ghost", icon_name="folder")
        key_button.clicked.connect(self._browse_key)
        key_row.addWidget(key_button)
        key_widget = QWidget()
        key_widget.setLayout(key_row)
        self._node_workdir = QLineEdit()
        self._node_workdir.setPlaceholderText("/home/user/vasper-jobs")
        self._node_scheduler = QComboBox()
        self._node_scheduler.addItems(["SLURM", "PBS", "LSF", "本地"])
        self._node_partition = QLineEdit()
        self._node_partition.setPlaceholderText("队列 / 分区，例如 cpu")
        self._node_submit = QLineEdit()
        self._node_submit.setPlaceholderText("例如 sbatch {script}")

        grid.addWidget(self._labeled("节点名称", self._node_name), 0, 0)
        grid.addWidget(self._labeled("主机 / IP", self._node_host), 0, 1)
        grid.addWidget(self._labeled("端口", self._node_port), 1, 0)
        grid.addWidget(self._labeled("用户名", self._node_user), 1, 1)
        grid.addWidget(self._labeled("认证方式", self._node_auth), 2, 0)
        grid.addWidget(self._labeled("调度器", self._node_scheduler), 2, 1)
        grid.addWidget(self._labeled("密码", self._node_password), 3, 0)
        grid.addWidget(self._labeled("密钥路径", key_widget), 3, 1)
        grid.addWidget(self._labeled("远程工作目录", self._node_workdir), 4, 0)
        grid.addWidget(self._labeled("分区 / 队列", self._node_partition), 4, 1)
        grid.addWidget(self._labeled("提交命令", self._node_submit), 5, 0, 1, 2)
        form_layout.addWidget(self._node_form)
        self._node_name.textChanged.connect(self._sync_node_item)
        self._node_host.textChanged.connect(self._sync_node_item)

        test_row = QHBoxLayout()
        test_row.setSpacing(8)
        self._test_button = TextButton("测试连接", variant="ghost", icon_name="external")
        self._test_button.setToolTip("仅检测主机 TCP 端口是否可达，不会登录 SSH")
        self._test_button.clicked.connect(self._test_connection)
        test_row.addWidget(self._test_button)
        self._test_status = QLabel("")
        self._test_status.setObjectName("Faint")
        self._test_status.setWordWrap(True)
        test_row.addWidget(self._test_status, 1)
        form_layout.addLayout(test_row)
        form_layout.addStretch(1)
        body.addWidget(form_box, 1)
        layout.addLayout(body, 1)
        return page

    def _build_workspace_page(self, public: dict) -> QWidget:
        page, layout = self._page()
        layout.addWidget(self._section("工作区"))
        card, workspace_layout = self._card_frame()
        workspace_layout.addWidget(self._field_label("工作区根目录"))
        row = QHBoxLayout()
        row.setSpacing(8)
        self._workspace = QLineEdit(public["workspace_root"])
        row.addWidget(self._workspace, 1)
        browse = TextButton("选择…", variant="ghost", icon_name="folder")
        browse.clicked.connect(self._browse_workspace)
        row.addWidget(browse)
        workspace_layout.addLayout(row)
        hint = QLabel("结构文件、会话与本地数据都会保存在这个目录及其子目录中。")
        hint.setObjectName("Faint")
        hint.setWordWrap(True)
        workspace_layout.addWidget(hint)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_about_page(self, public: dict) -> QWidget:
        page, layout = self._page()
        layout.addWidget(self._section("关于"))
        card, about = self._card_frame()
        title = QLabel(f"Vasper {__version__}")
        font = QFont()
        font.setPointSize(16)
        font.setWeight(QFont.Weight.DemiBold)
        title.setFont(font)
        about.addWidget(title)
        description = QLabel(
            "本地材料结构与 LLM 协作工作台。\n"
            "PyQt6 原生界面 · QtWebEngine + 3Dmol 结构渲染 · OpenAI 兼容接口。"
        )
        description.setObjectName("Muted")
        description.setWordWrap(True)
        about.addWidget(description)
        about.addWidget(Divider())
        paths = QLabel(
            f"数据目录：{public['data_dir']}\n"
            "计划 / 执行模式只改变模型输出策略，不会自动运行命令或修改文件。"
        )
        paths.setObjectName("Faint")
        paths.setWordWrap(True)
        about.addWidget(paths)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    # ------------------------------------------------------------------ 节点
    def _on_auth_changed(self, index: int) -> None:
        password = index == 0
        self._node_password.setEnabled(password)
        self._node_key_path.setEnabled(not password)

    def _refresh_node_list(self, select: int = -1) -> None:
        self._node_list.blockSignals(True)
        self._node_list.clear()
        for node in self._nodes:
            item = QListWidgetItem(f"{node.get('name') or '未命名节点'}\n{node.get('host') or '未设置主机'}")
            item.setSizeHint(QSize(0, 56))
            self._node_list.addItem(item)
        self._node_list.blockSignals(False)
        if select >= 0 and select < len(self._nodes):
            self._node_list.setCurrentRow(select)
            self._load_node(select)
        else:
            self._current_node = -1
            self._set_node_form_enabled(False)

    def _set_node_form_enabled(self, enabled: bool) -> None:
        self._node_form.setEnabled(enabled)
        self._test_button.setEnabled(enabled)

    def _load_node(self, index: int) -> None:
        if index < 0 or index >= len(self._nodes):
            self._current_node = -1
            self._set_node_form_enabled(False)
            return
        self._commit_node()
        self._current_node = index
        node = self._nodes[index]
        self._loading_node = True
        self._node_name.setText(node.get("name", ""))
        self._node_host.setText(node.get("host", ""))
        self._node_port.setText(str(node.get("port", 22)))
        self._node_user.setText(node.get("username", ""))
        self._node_auth.setCurrentIndex(0 if node.get("auth", "password") == "password" else 1)
        self._node_password.setText(node.get("password", ""))
        self._node_key_path.setText(node.get("key_path", ""))
        self._node_workdir.setText(node.get("workdir", ""))
        scheduler = node.get("scheduler", "SLURM")
        self._node_scheduler.setCurrentText(scheduler if scheduler in {"SLURM", "PBS", "LSF", "本地"} else "SLURM")
        self._node_partition.setText(node.get("partition", ""))
        self._node_submit.setText(node.get("submit_cmd", "sbatch {script}"))
        for field in (self._node_key_path, self._node_workdir, self._node_submit):
            field.setToolTip(field.text())
            field.deselect()
        QTimer.singleShot(0, lambda: [field.setCursorPosition(0) for field in (
            self._node_key_path, self._node_workdir, self._node_submit,
        )])
        self._loading_node = False
        self._on_auth_changed(self._node_auth.currentIndex())
        self._set_node_form_enabled(True)
        self._test_status.setText("")

    def _sync_node_item(self) -> None:
        if self._loading_node:
            return
        row = self._node_list.currentRow()
        if 0 <= row < len(self._nodes):
            item = self._node_list.item(row)
            if item is not None:
                item.setText(
                    f"{self._node_name.text().strip() or '未命名节点'}\n"
                    f"{self._node_host.text().strip() or '未设置主机'}"
                )

    def _node_port_value(self) -> int:
        try:
            return max(1, min(65535, int(self._node_port.text().strip() or "22")))
        except ValueError:
            return 22

    def _commit_node(self) -> None:
        if self._loading_node or self._current_node < 0 or self._current_node >= len(self._nodes):
            return
        self._nodes[self._current_node] = {
            "name": self._node_name.text().strip(),
            "host": self._node_host.text().strip(),
            "port": self._node_port_value(),
            "username": self._node_user.text().strip(),
            "auth": "password" if self._node_auth.currentIndex() == 0 else "key",
            "password": self._node_password.text(),
            "key_path": self._node_key_path.text().strip(),
            "workdir": self._node_workdir.text().strip(),
            "scheduler": self._node_scheduler.currentText(),
            "partition": self._node_partition.text().strip(),
            "submit_cmd": self._node_submit.text().strip(),
        }
        self._sync_node_item()

    def _add_node(self) -> None:
        self._commit_node()
        self._nodes.append(
            {
                "name": "新节点",
                "host": "",
                "port": 22,
                "username": "",
                "auth": "password",
                "password": "",
                "key_path": "",
                "workdir": "",
                "scheduler": "SLURM",
                "partition": "",
                "submit_cmd": "sbatch {script}",
            }
        )
        self._refresh_node_list(len(self._nodes) - 1)

    def _remove_node(self) -> None:
        index = self._node_list.currentRow()
        if index < 0 or index >= len(self._nodes):
            return
        self._nodes.pop(index)
        self._refresh_node_list(min(index, len(self._nodes) - 1))

    def _browse_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 SSH 私钥")
        if path:
            self._node_key_path.setText(path)

    def _test_connection(self) -> None:
        self._commit_node()
        host = self._node_host.text().strip()
        if not host:
            self._test_status.setText("请先填写主机地址")
            return
        if self._tester is not None and self._tester.isRunning():
            return
        self._test_button.setEnabled(False)
        port = self._node_port_value()
        self._test_status.setText(f"正在连接 {host}:{port} …")
        self._tester = ConnectionTester(host, port, self)
        self._tester.result.connect(self._on_test_result)
        self._tester.finished.connect(self._tester.deleteLater)
        self._tester.start()

    def _on_test_result(self, ok: bool, message: str) -> None:
        self._test_status.setText(message)
        self._test_status.setStyleSheet(
            f"color: {'#30D158' if ok else '#FF453A'}; font-size: 11px;"
        )
        self._test_button.setEnabled(True)

    # ------------------------------------------------------------------ 其他
    def _on_page_changed(self, index: int) -> None:
        if index == 1:
            self._commit_node()
        self._stack.setCurrentIndex(index)

    def _toggle_eye(self, checked: bool) -> None:
        self._api_key.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self._eye_button.set_icon("eye-off" if checked else "eye")

    def _browse_workspace(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "选择工作区目录", self._workspace.text() or str(config.PROJECT_ROOT)
        )
        if directory:
            self._workspace.setText(directory)

    def _import_sci(self) -> None:
        try:
            public = config.import_sci_circle_llm()
        except Exception as exc:
            self._llm_status.setText(f"导入失败：{exc}")
            return
        if not public:
            self._llm_status.setText("未找到 sci-circle/config.ini 中的 [llm_api] 配置")
            return
        self._base_url.setText(public["llm"]["base_url"])
        self._model.setText(public["llm"]["model"])
        if public["llm"]["has_api_key"]:
            self._api_key.setPlaceholderText(f"已保存（{public['llm']['api_key_hint']}），留空保持不变")
            self._llm_status.setText("已导入 sci-circle 的 LLM 配置，点击保存生效")
        else:
            self._llm_status.setText("已导入地址与模型，但未读取到 API Key")

    def _stop_tester(self) -> None:
        if self._tester is not None and self._tester.isRunning():
            self._tester.wait(3500)

    def accept(self) -> None:
        self._stop_tester()
        super().accept()

    def reject(self) -> None:
        self._stop_tester()
        super().reject()

    def _save(self) -> None:
        self._commit_node()
        llm: dict = {
            "base_url": self._base_url.text().strip(),
            "model": self._model.text().strip(),
            "temperature": self._temperature.value() / 10,
        }
        if self._api_key.text().strip():
            llm["api_key"] = self._api_key.text().strip()
        payload = {
            "llm": llm,
            "workspace_root": self._workspace.text().strip(),
            "compute": {"nodes": copy.deepcopy(self._nodes)},
        }
        try:
            public = config.update_settings(payload)
        except Exception as exc:
            self._footer_status.setText(f"保存失败：{exc}")
            self._footer_status.setStyleSheet("color: #FF453A; font-size: 11px;")
            return
        self.settings_saved.emit(public)
        self.accept()
