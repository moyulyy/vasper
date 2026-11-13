"""会话持久化：每个会话一个 JSON 文件，存放于 data/sessions。"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config

_ID_RE = re.compile(r"^[a-f0-9]{8,40}$")


def _sessions_dir() -> Path:
    config.ensure_dirs()
    return config.SESSIONS_DIR


def _path(session_id: str) -> Path:
    if not _ID_RE.match(session_id or ""):
        raise ValueError("会话 ID 无效")
    return _sessions_dir() / f"{session_id}.json"


def _write(session: dict[str, Any]) -> None:
    path = _path(session["id"])
    fd, tmp = tempfile.mkstemp(prefix=".session-", suffix=".json", dir=str(_sessions_dir()))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(session, handle, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create(title: str = "新会话", model: str = "") -> dict[str, Any]:
    session = {
        "id": uuid.uuid4().hex[:16],
        "title": (title or "新会话").strip()[:80],
        "created": _now(),
        "updated": _now(),
        "model": model,
        "messages": [],
    }
    _write(session)
    return session


def get(session_id: str) -> dict[str, Any]:
    path = _path(session_id)
    if not path.is_file():
        raise FileNotFoundError("会话不存在")
    return json.loads(path.read_text(encoding="utf-8"))


def save(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    session = get(session_id)
    messages = payload.get("messages")
    if isinstance(messages, list):
        clean = []
        for message in messages[-400:]:
            if not isinstance(message, dict):
                continue
            role = message.get("role")
            if role not in {"user", "assistant", "system"}:
                continue
            content = message.get("content")
            if not isinstance(content, str):
                continue
            item = {"role": role, "content": content[:120000]}
            for extra in ("model", "context_name", "created", "mode"):
                if isinstance(message.get(extra), str):
                    item[extra] = message[extra][:400]
            if isinstance(message.get("error"), bool):
                item["error"] = message["error"]
            clean.append(item)
        session["messages"] = clean
        if clean and session.get("title") in {"", "新会话"}:
            first = next((m["content"] for m in clean if m["role"] == "user"), "")
            if first:
                session["title"] = _title_from(first)
    title = payload.get("title")
    if isinstance(title, str) and title.strip():
        session["title"] = title.strip()[:80]
    model = payload.get("model")
    if isinstance(model, str) and model.strip():
        session["model"] = model.strip()[:80]
    session["updated"] = _now()
    _write(session)
    return session


def _title_from(text: str) -> str:
    line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    line = re.sub(r"^#+\s*", "", line)
    line = re.sub(r"\s+", " ", line)
    return (line[:36] + "…") if len(line) > 36 else (line or "新会话")


def summary(session: dict[str, Any]) -> dict[str, Any]:
    messages = session.get("messages") or []
    last = next((m for m in reversed(messages) if m.get("content")), {})
    preview = re.sub(r"\s+", " ", str(last.get("content", "")))[:90]
    return {
        "id": session.get("id"),
        "title": session.get("title") or "新会话",
        "updated": session.get("updated"),
        "created": session.get("created"),
        "message_count": len(messages),
        "preview": preview,
        "model": session.get("model", ""),
    }


def list_all() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in _sessions_dir().glob("*.json"):
        if path.name.startswith("."):
            continue
        try:
            items.append(summary(json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    items.sort(key=lambda item: item.get("updated") or "", reverse=True)
    return items


def delete(session_id: str) -> None:
    path = _path(session_id)
    if path.exists():
        path.unlink()
