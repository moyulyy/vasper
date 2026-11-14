"""子智能体目录与工具清单。

每个子智能体是 data/agents/<id>/ 下的独立文件夹，包含：

    skills/   可复用技能说明（Markdown）
    mcp/      MCP 服务配置（servers.json）
    tools/    工具清单（tools.json）
    data/     该子智能体的专属数据

当前版本负责目录、技能与工具清单的登记和展示；实际执行器可在后续接入。
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

from . import config

CATEGORIES: tuple[dict[str, str], ...] = (
    {"id": "skills", "label": "Skills", "title": "技能", "icon": "sparkles",
     "description": "可复用的方法、提示与工作流（Markdown）"},
    {"id": "mcp", "label": "MCP", "title": "MCP 服务", "icon": "layers",
     "description": "MCP 服务配置（servers.json）"},
    {"id": "tools", "label": "Tools", "title": "工具", "icon": "wrench",
     "description": "可调用工具的清单与参数说明（JSON）"},
    {"id": "data", "label": "Data", "title": "数据", "icon": "database",
     "description": "该子智能体的专属工作数据"},
)

_TOOL = lambda name, description, props=None, required=None: {
    "name": name,
    "description": description,
    "input_schema": {
        "type": "object",
        "properties": props or {"path": {"type": "string", "description": "工作区内的相对路径"}},
        "required": required or ["path"],
    },
}

BUILTINS: tuple[dict[str, Any], ...] = (
    {
        "id": "file-ops",
        "name": "文件操作",
        "icon": "file-code",
        "description": "文本文件增删改查、路径创建、复制与移动，操作限制在工作区内。",
        "system_prompt": "你是文件操作子智能体。只操作当前工作区内的路径，修改前先读取内容，删除或覆盖前必须确认目标。",
        "skill": "# 文件操作技能\n\n- 所有路径相对于当前工作区，禁止 `..` 与绝对路径逃逸。\n- 修改前先读取文件内容，保留原有编码与换行。\n- 创建目录使用递归创建；复制/移动前检查目标是否存在。\n- 删除文件或目录前确认目标，不删除工作区根目录。\n",
        "tools": [
            _TOOL("file_read", "读取工作区内的文本文件"),
            _TOOL("file_write", "写入文本文件（覆盖）", {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
            _TOOL("file_append", "在文本文件末尾追加内容", {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
            _TOOL("file_delete", "删除工作区内的文件或目录"),
            _TOOL("path_create", "创建目录（递归）"),
            _TOOL("path_copy", "复制文件或目录", {"source": {"type": "string"}, "target": {"type": "string"}}, ["source", "target"]),
            _TOOL("path_move", "移动/重命名文件或目录", {"source": {"type": "string"}, "target": {"type": "string"}}, ["source", "target"]),
            _TOOL("file_list", "列出目录内容"),
        ],
    },
    {
        "id": "coding",
        "name": "编程助手",
        "icon": "terminal",
        "description": "编写、修改和检查代码，生成可复现的脚本与补丁。",
        "system_prompt": "你是编程子智能体。优先给出最小可行修改，保持项目现有风格；修改代码前列出受影响文件，完成后说明如何验证。",
        "skill": "# 编程技能\n\n- 先理解项目结构与现有约定，再修改代码。\n- 修改尽量小，避免无关重构。\n- 代码块标注语言，给出运行/测试命令。\n- 不执行未经确认的危险命令。\n",
        "tools": [
            _TOOL("code_write", "写入代码文件", {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
            _TOOL("code_patch", "应用代码补丁", {"path": {"type": "string"}, "patch": {"type": "string"}}, ["path", "patch"]),
            _TOOL("code_read", "读取代码文件"),
            _TOOL("code_run", "在项目环境中运行脚本", {"command": {"type": "string"}}, ["command"]),
            _TOOL("test_run", "运行测试命令", {"command": {"type": "string"}}, ["command"]),
            _TOOL("format_code", "格式化代码文件"),
        ],
    },
    {
        "id": "ssh",
        "name": "SSH 连接",
        "icon": "key",
        "description": "使用设置中的计算节点建立 SSH 连接并执行远端命令。",
        "system_prompt": "你是 SSH 子智能体。使用已保存的计算节点配置，不泄露密码或私钥；执行危险命令前先说明影响。",
        "skill": "# SSH 技能\n\n- 节点来自「设置 → 计算节点」。\n- 先测试连接，再执行命令。\n- 不把密码写入日志或文件。\n- 删除、覆盖、重启等操作需要明确说明。\n",
        "tools": [
            _TOOL("ssh_test", "测试节点 SSH 端口连通性"),
            _TOOL("ssh_exec", "在远端执行命令", {"node": {"type": "string"}, "command": {"type": "string"}}, ["node", "command"]),
            _TOOL("ssh_upload", "通过 SSH 上传文件", {"node": {"type": "string"}, "local": {"type": "string"}, "remote": {"type": "string"}}, ["node", "local", "remote"]),
            _TOOL("ssh_download", "通过 SSH 下载文件", {"node": {"type": "string"}, "remote": {"type": "string"}, "local": {"type": "string"}}, ["node", "remote", "local"]),
        ],
    },
    {
        "id": "sftp",
        "name": "SFTP 传输",
        "icon": "upload",
        "description": "在本地工作区与远端节点之间上传、下载和管理文件。",
        "system_prompt": "你是 SFTP 子智能体。只传输明确指定的文件，覆盖远端文件前先确认，保留远端目录结构。",
        "skill": "# SFTP 技能\n\n- 传输前确认本地文件与远端目标路径。\n- 记录文件大小与传输结果。\n- 不删除远端目录，除非用户明确要求。\n",
        "tools": [
            _TOOL("sftp_upload", "上传本地文件到远端", {"node": {"type": "string"}, "local": {"type": "string"}, "remote": {"type": "string"}}, ["node", "local", "remote"]),
            _TOOL("sftp_download", "下载远端文件到本地", {"node": {"type": "string"}, "remote": {"type": "string"}, "local": {"type": "string"}}, ["node", "remote", "local"]),
            _TOOL("sftp_list", "列出远端目录"),
            _TOOL("sftp_mkdir", "创建远端目录"),
            _TOOL("sftp_delete", "删除远端文件"),
        ],
    },
    {
        "id": "slurm",
        "name": "Slurm 作业",
        "icon": "layers",
        "description": "通过 SSH 管理 Slurm 作业：提交、查询、取消与查看日志。",
        "system_prompt": "你是 Slurm 子智能体。通过设置中的节点与提交命令操作作业；提交前核对脚本、分区与资源，取消或覆盖操作必须确认。",
        "skill": "# Slurm 技能\n\n- 使用节点的调度器、分区与提交命令配置。\n- 提交前检查脚本路径与参数。\n- 查询使用 squeue/sacct，取消使用 scancel。\n- 日志读取优先使用 tail，避免一次读入超大文件。\n",
        "tools": [
            _TOOL("slurm_submit", "提交 Slurm 作业", {"node": {"type": "string"}, "script": {"type": "string"}}, ["node", "script"]),
            _TOOL("slurm_status", "查询作业状态", {"node": {"type": "string"}, "job_id": {"type": "string"}}, ["node", "job_id"]),
            _TOOL("slurm_queue", "查看队列 / 分区", {"node": {"type": "string"}}, ["node"]),
            _TOOL("slurm_cancel", "取消作业", {"node": {"type": "string"}, "job_id": {"type": "string"}}, ["node", "job_id"]),
            _TOOL("slurm_logs", "读取作业日志", {"node": {"type": "string"}, "path": {"type": "string"}}, ["node", "path"]),
        ],
    },
    {
        "id": "viewer-ops",
        "name": "结构视图操作",
        "icon": "atom",
        "description": "操作左侧 3D 结构视图：视角、选中、测量、结构编辑、晶面/超胞/异质结与固定原子。",
        "system_prompt": "你是结构视图操作子智能体。修改结构前说明将改变哪些原子与晶格；删除、晶面切割、超胞和异质结构建前确认参数，操作后报告新的原子数与晶格信息。",
        "skill": "# 结构视图操作技能\n\n"
                 "- 视角：旋转、平移、缩放、重置，不改变结构。\n"
                 "- 选中与测量：按原子序号/元素定位，选中后显示坐标与距离。\n"
                 "- 编辑：增删改原子前先读取结构；所有坐标同时支持分数坐标与笛卡尔坐标。\n"
                 "- 晶面：按 Miller 指数切割表面，设置层数与真空层；超胞需给出 nx/ny/nz。\n"
                 "- 晶格旋转与异质结：保持周期性，异质结需指定两层、晶面、应变与界面间距。\n"
                 "- 固定原子：用序号/元素/区域选择，固定状态需在视图中可识别。\n",
        "tools": [
            _TOOL("view_rotate", "旋转 3D 视角", {"axis": {"type": "string", "enum": ["x", "y", "z"]}, "angle": {"type": "number"}}, ["axis", "angle"]),
            _TOOL("view_pan", "平移 3D 视图", {"dx": {"type": "number"}, "dy": {"type": "number"}}, ["dx", "dy"]),
            _TOOL("view_zoom", "缩放 3D 视图", {"factor": {"type": "number", "description": "大于 1 放大，小于 1 缩小"}}, ["factor"]),
            _TOOL("view_reset", "重置 3D 视角"),
            _TOOL("select_atom", "选中指定原子", {"index": {"type": "integer"}, "element": {"type": "string"}}, []),
            _TOOL("inspect_atom", "查看原子元素、序号、坐标与配位", {"index": {"type": "integer"}}, ["index"]),
            _TOOL("measure_distance", "测量两个原子的距离", {"atom_a": {"type": "integer"}, "atom_b": {"type": "integer"}}, ["atom_a", "atom_b"]),
            _TOOL("add_atom", "在结构中增加原子", {"element": {"type": "string"}, "x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}}, ["element", "x", "y", "z"]),
            _TOOL("modify_atom", "修改原子的元素或坐标", {"index": {"type": "integer"}, "element": {"type": "string"}, "x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}}, ["index"]),
            _TOOL("delete_atom", "删除指定原子", {"index": {"type": "integer"}}, ["index"]),
            _TOOL("cut_surface", "按 Miller 指数切割晶面", {"h": {"type": "integer"}, "k": {"type": "integer"}, "l": {"type": "integer"}, "layers": {"type": "integer"}, "vacuum": {"type": "number"}}, ["h", "k", "l"]),
            _TOOL("build_supercell", "构建超胞", {"nx": {"type": "integer"}, "ny": {"type": "integer"}, "nz": {"type": "integer"}}, ["nx", "ny", "nz"]),
            _TOOL("rotate_lattice", "旋转晶格矢量", {"axis": {"type": "string", "enum": ["x", "y", "z"]}, "angle": {"type": "number"}}, ["axis", "angle"]),
            _TOOL("build_heterojunction", "搭建两层异质结", {"layer_a": {"type": "string"}, "layer_b": {"type": "string"}, "miller": {"type": "string"}, "strain": {"type": "number"}, "gap": {"type": "number"}}, ["layer_a", "layer_b"]),
            _TOOL("fix_atoms", "固定指定原子", {"indices": {"type": "array", "items": {"type": "integer"}}, "mode": {"type": "string"}}, ["indices"]),
        ],
    },

)


def agents_root() -> Path:
    root = config.DATA_DIR / "agents"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _agent_dir(agent_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", agent_id or ""):
        raise ValueError("子智能体 ID 无效")
    return agents_root() / agent_id


def _write_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _meta(spec: dict[str, Any], builtin: bool) -> dict[str, Any]:
    return {
        "id": spec["id"],
        "name": spec["name"],
        "description": spec.get("description", ""),
        "system_prompt": spec.get("system_prompt", ""),
        "icon": spec.get("icon", "sparkles"),
        "builtin": builtin,
        "tools": [tool["name"] for tool in spec.get("tools", [])],
        "categories": [category["id"] for category in CATEGORIES],
    }


def _ensure_agent(spec: dict[str, Any], builtin: bool) -> dict[str, Any]:
    directory = _agent_dir(spec["id"])
    directory.mkdir(parents=True, exist_ok=True)
    for category in CATEGORIES:
        (directory / category["id"]).mkdir(exist_ok=True)
    meta = _meta(spec, builtin)
    meta_path = directory / "agent.json"
    if not meta_path.exists():
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_missing(directory / "skills" / "overview.md", spec.get("skill", f"# {spec['name']}\n"))
    _write_missing(
        directory / "mcp" / "servers.json",
        '{\n  "mcpServers": {}\n}\n',
    )
    _write_missing(
        directory / "tools" / "tools.json",
        json.dumps(spec.get("tools", []), ensure_ascii=False, indent=2) + "\n",
    )
    _write_missing(
        directory / "data" / "README.md",
        f"# {spec['name']} 数据\n\n该目录用于保存「{spec['name']}」子智能体的工作数据。\n",
    )
    _write_missing(
        directory / "README.md",
        f"# {spec['name']}\n\n{spec.get('description', '')}\n\n"
        "目录：`skills/` · `mcp/` · `tools/` · `data/`。\n",
    )
    return meta


def ensure_builtins() -> None:
    for spec in BUILTINS:
        _ensure_agent(spec, True)


def _read_meta(directory: Path) -> dict[str, Any] | None:
    meta_path = directory / "agent.json"
    if not meta_path.is_file():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    data.setdefault("id", directory.name)
    data.setdefault("name", directory.name)
    data.setdefault("description", "")
    data.setdefault("builtin", False)
    return data


def _files_for(directory: Path, category: str) -> list[dict[str, Any]]:
    category_dir = directory / category
    if not category_dir.is_dir():
        return []
    files: list[dict[str, Any]] = []
    for path in sorted(category_dir.rglob("*")):
        if path.is_file():
            files.append({
                "name": path.name,
                "path": path.relative_to(directory).as_posix(),
                "size": path.stat().st_size,
            })
    return files


def list_agents() -> list[dict[str, Any]]:
    ensure_builtins()
    agents: list[dict[str, Any]] = []
    order = {spec["id"]: index for index, spec in enumerate(BUILTINS)}
    for directory in agents_root().iterdir():
        if not directory.is_dir():
            continue
        meta = _read_meta(directory)
        if meta is None:
            continue
        meta["path"] = str(directory)
        meta["categories"] = [
            {**category, "files": _files_for(directory, category["id"])}
            for category in CATEGORIES
        ]
        agents.append(meta)
    agents.sort(key=lambda item: (not item.get("builtin", False), order.get(item["id"], 999), item["name"]))
    return agents


def get_agent(agent_id: str) -> dict[str, Any]:
    directory = _agent_dir(agent_id)
    meta = _read_meta(directory)
    if meta is None:
        raise FileNotFoundError("子智能体不存在")
    meta["path"] = str(directory)
    meta["categories"] = [
        {**category, "files": _files_for(directory, category["id"])}
        for category in CATEGORIES
    ]
    return meta


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slug = slug[:32].strip("-")
    return slug or f"agent-{int(time.time())}"


def create_agent(name: str, description: str = "") -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValueError("子智能体名称不能为空")
    ensure_builtins()
    base = _slug(name)
    agent_id = base
    counter = 2
    while _agent_dir(agent_id).exists():
        agent_id = f"{base}-{counter}"
        counter += 1
    spec = {
        "id": agent_id,
        "name": name,
        "description": description.strip() or f"{name} 自定义子智能体",
        "system_prompt": f"你是「{name}」子智能体。",
        "icon": "sparkles",
        "skill": f"# {name}\n\n在 `skills/` 中补充该子智能体的技能说明。\n",
        "tools": [],
    }
    _ensure_agent(spec, False)
    return get_agent(agent_id)


def delete_agent(agent_id: str) -> None:
    meta = get_agent(agent_id)
    if meta.get("builtin"):
        raise ValueError("内置子智能体不能删除")
    shutil.rmtree(_agent_dir(agent_id))


def save_agent_meta(agent_id: str, name: str, description: str, system_prompt: str) -> dict[str, Any]:
    directory = _agent_dir(agent_id)
    meta = _read_meta(directory)
    if meta is None:
        raise FileNotFoundError("子智能体不存在")
    meta["name"] = name.strip() or meta["name"]
    meta["description"] = description.strip()
    meta["system_prompt"] = system_prompt.strip()
    (directory / "agent.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return get_agent(agent_id)
