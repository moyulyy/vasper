"""工作区文件操作：目录树、文本读取、上传与轻量文件管理。"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config

STRUCTURE_EXTS = {
    ".cif",
    ".mcif",
    ".xyz",
    ".extxyz",
    ".pdb",
    ".ent",
    ".mol",
    ".mol2",
    ".sdf",
    ".sd",
    ".vasp",
    ".poscar",
    ".contcar",
    ".res",
    ".xsf",
}

TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".py", ".js", ".ts", ".html", ".css", ".sh", ".bash", ".zsh", ".c", ".h", ".cpp", ".hpp",
    ".f90", ".f", ".for", ".incar", ".kpoints", ".potcar", ".log", ".out", ".csv", ".tsv",
    ".dat", ".xml", ".sql", ".rst", ".tex", ".bib",
}

MAX_ENTRIES = 3000
MAX_PREVIEW_BYTES = 512 * 1024


def _root() -> Path:
    return config.workspace_root()


def safe_path(rel: str, *, must_exist: bool = False) -> Path:
    """把相对路径安全地解析到工作区内部，阻止目录穿越。"""
    root = _root()
    raw = (rel or "").strip().replace("\\", "/")
    if raw.startswith("/"):
        raise ValueError("只允许工作区内的相对路径")
    target = (root / raw).resolve() if raw else root
    if target != root and root not in target.parents:
        raise ValueError("路径超出工作区范围")
    if must_exist and not target.exists():
        raise FileNotFoundError("文件或目录不存在")
    return target


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(_root()).as_posix()
    except ValueError:
        return path.name


def is_structure(path: Path) -> bool:
    upper = path.name.upper()
    if upper.startswith(("POSCAR", "CONTCAR")) or upper == "VASP":
        return True
    return path.suffix.lower() in STRUCTURE_EXTS


def _entry(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
        size = stat.st_size
    except OSError:
        mtime, size = "", 0
    is_dir = path.is_dir()
    return {
        "name": path.name,
        "path": relative(path),
        "type": "dir" if is_dir else "file",
        "ext": "" if is_dir else path.suffix.lower().lstrip("."),
        "size": size,
        "mtime": mtime,
        "structure": False if is_dir else is_structure(path),
    }


def list_dir(rel: str = "", *, show_hidden: bool = False) -> dict[str, Any]:
    directory = safe_path(rel, must_exist=True)
    if not directory.is_dir():
        raise ValueError("不是文件夹")
    entries: list[dict[str, Any]] = []
    try:
        children = sorted(
            directory.iterdir(),
            key=lambda p: (not p.is_dir(), p.name.casefold()),
        )
    except PermissionError as exc:
        raise ValueError("没有权限读取该文件夹") from exc

    for child in children:
        if len(entries) >= MAX_ENTRIES:
            break
        if not show_hidden and child.name.startswith("."):
            continue
        if child.name in {".conda", "__pycache__", "node_modules"}:
            continue
        try:
            entries.append(_entry(child))
        except OSError:
            continue
    return {
        "path": relative(directory) if directory != _root() else "",
        "name": directory.name,
        "entries": entries,
    }


def read_text(rel: str, *, max_bytes: int = MAX_PREVIEW_BYTES) -> dict[str, Any]:
    path = safe_path(rel, must_exist=True)
    if path.is_dir():
        raise ValueError("这是一个文件夹")
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f"文件过大（{size / 1024 / 1024:.1f} MB），暂不支持预览")
    raw = path.read_bytes()
    if b"\x00" in raw[:4096] and path.suffix.lower() not in STRUCTURE_EXTS:
        raise ValueError("这是二进制文件，暂不支持预览")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    return {"path": relative(path), "name": path.name, "text": text, "size": size}


def make_dir(parent_rel: str, name: str) -> dict[str, Any]:
    name = (name or "").strip()
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise ValueError("文件夹名称无效")
    parent = safe_path(parent_rel, must_exist=True)
    target = parent / name
    if target.exists():
        raise ValueError("同名文件或文件夹已存在")
    target.mkdir(parents=False)
    return _entry(target)


def rename(rel: str, name: str) -> dict[str, Any]:
    name = (name or "").strip()
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise ValueError("名称无效")
    source = safe_path(rel, must_exist=True)
    if source == _root():
        raise ValueError("不能重命名工作区根目录")
    target = source.parent / name
    if target.exists():
        raise ValueError("同名文件或文件夹已存在")
    source.rename(target)
    return _entry(target)


def delete(rel: str) -> None:
    target = safe_path(rel, must_exist=True)
    if target == _root():
        raise ValueError("不能删除工作区根目录")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()


def save_upload(folder_rel: str, filename: str, stream) -> dict[str, Any]:
    filename = Path(str(filename or "")).name.strip()
    if not filename:
        raise ValueError("文件名无效")
    folder = safe_path(folder_rel, must_exist=True)
    if not folder.is_dir():
        raise ValueError("目标不是文件夹")
    target = folder / filename
    if target.exists():
        stem, suffix = target.stem, target.suffix
        index = 2
        while target.exists():
            target = folder / f"{stem} ({index}){suffix}"
            index += 1
    with target.open("wb") as handle:
        shutil.copyfileobj(stream, handle, length=1024 * 1024)
    return _entry(target)


def count_entries(rel: str = "") -> int:
    try:
        return len(list_dir(rel)["entries"])
    except Exception:
        return 0
