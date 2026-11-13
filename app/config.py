"""应用配置：本地 JSON 设置 + 可选的 sci-circle LLM 配置导入。"""

from __future__ import annotations

import configparser
import copy
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT_ROOT / "web"
WORKSPACES_DIR = PROJECT_ROOT / "workspaces"
DEFAULT_WORKSPACE = WORKSPACES_DIR / "default"


def _resolve_data_dir() -> Path:
    raw = os.environ.get("VASPER_DATA_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return (PROJECT_ROOT / "data").resolve()


DATA_DIR = _resolve_data_dir()
SESSIONS_DIR = DATA_DIR / "sessions"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
SETTINGS_FILE = DATA_DIR / "settings.json"

_LOCK = threading.RLock()

DEFAULT_SETTINGS: dict[str, Any] = {
    "workspace_root": str(DEFAULT_WORKSPACE),
    "llm": {
        "base_url": "",
        "api_key": "",
        "model": "deepseek-flash",
    },
    "appearance": {"theme": "dark"},
    "ui": {"files_open": False, "sessions_open": False, "llm_mode": "plan"},
    "compute": {"nodes": []},
}


def _sci_circle_config() -> dict[str, str] | None:
    """读取同机 sci-circle 的 [llm_api]（仅作为首次运行的种子配置）。"""
    candidates = [
        Path.home() / "桌面" / "sci-circle" / "config.ini",
        Path.home() / "Desktop" / "sci-circle" / "config.ini",
        Path.home() / "sci-circle" / "config.ini",
    ]
    for path in candidates:
        try:
            if not path.is_file():
                continue
            parser = configparser.ConfigParser(interpolation=None)
            parser.read(path, encoding="utf-8")
            if not parser.has_section("llm_api"):
                continue
            section = parser["llm_api"]
            return {
                "base_url": (section.get("baseurl") or section.get("base_url") or "").strip(),
                "api_key": (section.get("api_key") or "").strip(),
                "model": (section.get("model") or "").strip(),
            }
        except Exception:
            continue
    return None


def _seed_llm() -> dict[str, Any]:
    seed = copy.deepcopy(DEFAULT_SETTINGS["llm"])
    base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("VASPER_BASE_URL")
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("VASPER_API_KEY")
    model = os.environ.get("OPENAI_MODEL") or os.environ.get("VASPER_MODEL")
    if base_url:
        seed["base_url"] = base_url.strip()
    if api_key:
        seed["api_key"] = api_key.strip()
    if model:
        seed["model"] = model.strip()

    if not seed["api_key"]:
        imported = _sci_circle_config()
        if imported:
            seed["base_url"] = seed["base_url"] or imported.get("base_url", "")
            seed["api_key"] = imported.get("api_key", "") or seed["api_key"]
    return seed


def _deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def ensure_dirs() -> None:
    for directory in (DATA_DIR, SESSIONS_DIR, SCREENSHOTS_DIR, WORKSPACES_DIR, DEFAULT_WORKSPACE):
        directory.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict[str, Any]:
    with _LOCK:
        settings = _deep_merge(DEFAULT_SETTINGS, {})
        settings["llm"] = _seed_llm()

        if SETTINGS_FILE.is_file():
            try:
                raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                settings = _deep_merge(settings, raw)
            except Exception:
                pass

        root = Path(str(settings.get("workspace_root") or DEFAULT_WORKSPACE)).expanduser()
        try:
            if not root.is_absolute():
                root = (PROJECT_ROOT / root).resolve()
            root.mkdir(parents=True, exist_ok=True)
            settings["workspace_root"] = str(root.resolve())
        except OSError:
            settings["workspace_root"] = str(DEFAULT_WORKSPACE)

        llm = settings.get("llm") or {}
        llm["base_url"] = str(llm.get("base_url") or "").strip()
        llm["api_key"] = str(llm.get("api_key") or "").strip()
        llm["model"] = str(llm.get("model") or "deepseek-flash").strip()
        llm.pop("temperature", None)
        settings["llm"] = llm
        return settings


def save_settings(settings: dict[str, Any]) -> None:
    ensure_dirs()
    payload = json.dumps(settings, ensure_ascii=False, indent=2)
    with _LOCK:
        fd, tmp = tempfile.mkstemp(prefix=".settings-", suffix=".json", dir=str(DATA_DIR))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp, SETTINGS_FILE)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def public_settings() -> dict[str, Any]:
    settings = load_settings()
    llm = settings["llm"]
    key = llm.get("api_key") or ""
    return {
        "workspace_root": settings["workspace_root"],
        "workspace_name": Path(settings["workspace_root"]).name or "workspace",
        "llm": {
            "base_url": llm.get("base_url", ""),
            "model": llm.get("model", ""),
            "has_api_key": bool(key),
            "api_key_hint": ("…" + key[-4:]) if len(key) >= 4 else ("已设置" if key else ""),
        },
        "appearance": settings.get("appearance", {"theme": "auto"}),
        "ui": settings.get("ui", {"files_open": False, "llm_mode": "plan"}),
        "compute": {"nodes": copy.deepcopy(settings.get("compute", {}).get("nodes", []))},
        "data_dir": str(DATA_DIR),
        "writable": os.access(DATA_DIR, os.W_OK),
    }


def update_settings(payload: dict[str, Any]) -> dict[str, Any]:
    """合并前端提交的设置。api_key 留空表示保持不变。"""
    with _LOCK:
        settings = load_settings()
        llm = payload.get("llm")
        if isinstance(llm, dict):
            current = settings["llm"]
            for key in ("base_url", "model"):
                if isinstance(llm.get(key), str):
                    current[key] = llm[key].strip()
            if isinstance(llm.get("api_key"), str) and llm["api_key"].strip():
                current["api_key"] = llm["api_key"].strip()
            if llm.get("clear_api_key") is True:
                current["api_key"] = ""

        appearance = payload.get("appearance")
        if isinstance(appearance, dict):
            settings["appearance"]["theme"] = "dark"

        compute = payload.get("compute")
        if isinstance(compute, dict) and isinstance(compute.get("nodes"), list):
            settings["compute"] = {"nodes": _sanitize_nodes(compute["nodes"])}

        ui = payload.get("ui")
        if isinstance(ui, dict):
            for key in ("files_open", "sessions_open"):
                if key in ui:
                    settings["ui"][key] = bool(ui[key])
            if ui.get("llm_mode") in {"plan", "execute"}:
                settings["ui"]["llm_mode"] = ui["llm_mode"]

        root_raw = payload.get("workspace_root")
        if isinstance(root_raw, str) and root_raw.strip():
            root = Path(root_raw).expanduser()
            if not root.is_absolute():
                root = (PROJECT_ROOT / root).resolve()
            if not root.exists():
                root.mkdir(parents=True, exist_ok=True)
            if not root.is_dir():
                raise ValueError("工作区路径不是文件夹")
            settings["workspace_root"] = str(root.resolve())

        save_settings(settings)
        return public_settings()


def import_sci_circle_llm() -> dict[str, Any] | None:
    """把 sci-circle 的 LLM 配置显式写入本地设置。"""
    imported = _sci_circle_config()
    if not imported:
        return None
    with _LOCK:
        settings = load_settings()
        if imported.get("base_url"):
            settings["llm"]["base_url"] = imported["base_url"]
        if imported.get("api_key"):
            settings["llm"]["api_key"] = imported["api_key"]
        if imported.get("model"):
            settings["llm"]["model"] = imported["model"]
        save_settings(settings)
    return public_settings()


def workspace_root() -> Path:
    settings = load_settings()
    root = Path(settings["workspace_root"])
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def llm_config() -> dict[str, Any]:
    return load_settings()["llm"]


_NODE_FIELDS = (
    "name", "host", "username", "auth", "password", "key_path",
    "workdir", "scheduler", "partition", "submit_cmd",
)


def _sanitize_nodes(nodes: list) -> list[dict]:
    clean: list[dict] = []
    for raw in list(nodes)[:24]:
        if not isinstance(raw, dict):
            continue
        node = {key: str(raw.get(key, "") or "")[:2000] for key in _NODE_FIELDS}
        try:
            node["port"] = max(1, min(65535, int(raw.get("port", 22))))
        except (TypeError, ValueError):
            node["port"] = 22
        clean.append(node)
    return clean
