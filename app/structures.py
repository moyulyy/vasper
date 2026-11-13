"""结构文件解析：读取视图内容、格式识别、原子/晶胞摘要与 POSCAR→CIF 转换。"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from . import files

MAX_STRUCTURE_BYTES = 24 * 1024 * 1024
CONTEXT_LIMIT = 28000

_ELEMENTS = {
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne", "Na", "Mg", "Al", "Si", "P", "S",
    "Cl", "Ar", "K", "Ca", "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn", "Ga",
    "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Tc", "Ru", "Rh", "Pd",
    "Ag", "Cd", "In", "Sn", "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Ce", "Pr", "Nd", "Pm",
    "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu", "Hf", "Ta", "W", "Re", "Os",
    "Ir", "Pt", "Au", "Hg", "Tl", "Pb", "Bi", "Po", "At", "Rn", "Fr", "Ra", "Ac", "Th", "Pa",
    "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr", "Rf", "Db", "Sg",
    "Bh", "Hs", "Mt", "Ds", "Rg", "Cn", "Nh", "Fl", "Mc", "Lv", "Ts", "Og",
}


def _format_for(path: Path) -> str:
    name = path.name.upper()
    if name.startswith(("POSCAR", "CONTCAR")) or name == "VASP" or path.suffix.lower() in {".vasp", ".poscar", ".contcar"}:
        return "poscar"
    ext = path.suffix.lower()
    mapping = {
        ".cif": "cif", ".mcif": "cif", ".xyz": "xyz", ".extxyz": "xyz", ".pdb": "pdb", ".ent": "pdb",
        ".mol": "mol", ".mol2": "mol2", ".sdf": "sdf", ".sd": "sdf", ".res": "mol2",
        ".xsf": "xsf",
    }
    return mapping.get(ext, ext.lstrip(".") or "xyz")


def _element_from_label(label: str) -> str:
    match = re.match(r"([A-Za-z]{1,2})", label or "")
    if not match:
        return "X"
    symbol = match.group(1)
    if symbol in _ELEMENTS:
        return symbol
    candidate = symbol[0].upper() + symbol[1:].lower()
    if candidate in _ELEMENTS:
        return candidate
    return symbol.capitalize()


def _bump(counter: dict[str, int], symbol: str) -> None:
    symbol = _element_from_label(symbol)
    counter[symbol] = counter.get(symbol, 0) + 1


def _xyz_summary(text: str) -> tuple[int, dict[str, int]]:
    lines = text.splitlines()
    if not lines:
        return 0, {}
    try:
        declared = int(lines[0].strip())
    except ValueError:
        declared = 0
    counts: dict[str, int] = {}
    for line in lines[2:]:
        parts = line.split()
        if len(parts) >= 4:
            _bump(counts, parts[0])
    count = sum(counts.values())
    return (declared or count), counts


def _pdb_summary(text: str) -> tuple[int, dict[str, int]]:
    counts: dict[str, int] = {}
    total = 0
    for line in text.splitlines():
        if line.startswith(("ATOM  ", "HETATM")):
            total += 1
            symbol = line[76:78].strip() if len(line) >= 78 else ""
            if not symbol:
                symbol = line[12:16].strip()
            _bump(counts, symbol)
    return total, counts


def _cif_summary(text: str) -> tuple[int, dict[str, int], dict[str, float] | None]:
    counts: dict[str, int] = {}
    cell: dict[str, float] = {}
    for tag, key in (
        ("_cell_length_a", "a"), ("_cell_length_b", "b"), ("_cell_length_c", "c"),
        ("_cell_angle_alpha", "alpha"), ("_cell_angle_beta", "beta"), ("_cell_angle_gamma", "gamma"),
    ):
        match = re.search(rf"^{tag}\s+([-+0-9.]+)", text, re.MULTILINE | re.IGNORECASE)
        if match:
            try:
                cell[key] = float(match.group(1))
            except ValueError:
                pass

    lines = text.splitlines()
    total = 0
    in_loop = False
    headers: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower() == "loop_":
            in_loop = True
            headers = []
            continue
        if in_loop:
            if stripped.startswith("_"):
                headers.append(stripped.split()[0].lower())
                continue
            if not stripped or stripped.startswith("#") or stripped.startswith("loop_"):
                in_loop = False
                continue
            if not headers or not any("_atom_site" in h for h in headers):
                in_loop = False
                continue
            parts = re.findall(r"'[^']*'|\"[^\"]*\"|\S+", stripped)
            if len(parts) < len(headers):
                continue
            record = dict(zip(headers, parts))
            symbol = record.get("_atom_site_type_symbol", "")
            if not symbol:
                symbol = record.get("_atom_site_label", "")
            _bump(counts, symbol.strip("'\""))
            total += 1

    if total == 0:
        for match in re.finditer(r"^\s*([A-Z][a-z]?)\s+\d", text, re.MULTILINE):
            if match.group(1) in _ELEMENTS:
                _bump(counts, match.group(1))
        total = sum(counts.values())
    return total, counts, (cell if len(cell) == 6 else None)


def _mol_summary(text: str) -> tuple[int, dict[str, int]]:
    counts: dict[str, int] = {}
    lines = text.splitlines()
    if len(lines) >= 4 and "V2000" in lines[3] or (len(lines) >= 4 and "V3000" in lines[3]):
        try:
            natoms = int(lines[3][0:3])
        except ValueError:
            natoms = 0
        for line in lines[4:4 + natoms]:
            if len(line) >= 4:
                _bump(counts, line[31:34].strip())
        return sum(counts.values()), counts
    for line in lines:
        parts = line.split()
        if len(parts) >= 4 and parts[0].isdigit():
            _bump(counts, parts[3].split(".")[0])
    return sum(counts.values()), counts


def _parse_poscar(text: str) -> dict[str, Any]:
    lines = [line for line in text.splitlines()]
    if len(lines) < 6:
        raise ValueError("POSCAR 文件不完整")
    index = 0
    comment = lines[index].strip()
    index += 1
    scale = float(lines[index].split()[0])
    index += 1
    lattice = []
    for _ in range(3):
        parts = [float(x) for x in lines[index].split()[:3]]
        lattice.append(parts)
        index += 1

    if scale < 0:
        volume = abs(
            lattice[0][0] * (lattice[1][1] * lattice[2][2] - lattice[1][2] * lattice[2][1])
            - lattice[0][1] * (lattice[1][0] * lattice[2][2] - lattice[1][2] * lattice[2][0])
            + lattice[0][2] * (lattice[1][0] * lattice[2][1] - lattice[1][1] * lattice[2][0])
        )
        scale = (abs(scale) / volume) ** (1 / 3) if volume else 1.0
    lattice = [[value * scale for value in row] for row in lattice]

    tokens = lines[index].split()
    if all(re.fullmatch(r"[A-Za-z]+", token) for token in tokens):
        species = tokens
        index += 1
    else:
        species = [token for token in re.split(r"[-,\s]+", comment) if token in _ELEMENTS]
    counts = [int(x) for x in lines[index].split()]
    index += 1
    if index >= len(lines):
        raise ValueError("POSCAR 缺少坐标")
    mode = lines[index].strip().lower()
    if mode.startswith(("s", "v", "d")):
        index += 1
    direct = not (mode.startswith("c") or mode.startswith("k"))

    symbols: list[str] = []
    for symbol, count in zip(species, counts):
        symbols.extend([symbol] * count)
    positions: list[list[float]] = []
    for line in lines[index:]:
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            positions.append([float(parts[0]), float(parts[1]), float(parts[2])])
        except ValueError:
            continue
        if len(positions) >= len(symbols):
            break
    symbols = symbols[:len(positions)]

    if not direct:
        inv = _inverse_3x3(lattice)
        fractional = []
        for pos in positions:
            fractional.append([
                sum(inv[row][col] * pos[col] for col in range(3)) for row in range(3)
            ])
    else:
        fractional = positions

    lengths = [math.sqrt(sum(v * v for v in row)) for row in lattice]
    angles = []
    for i, j in ((1, 2), (0, 2), (0, 1)):
        dot = sum(lattice[i][k] * lattice[j][k] for k in range(3))
        denom = lengths[i] * lengths[j] or 1.0
        angles.append(math.degrees(math.acos(max(-1.0, min(1.0, dot / denom)))))

    cif_lines = [
        "data_vasper_poscar",
        f"_chemical_name_common '{comment or 'POSCAR'}'",
        f"_cell_length_a {lengths[0]:.8f}",
        f"_cell_length_b {lengths[1]:.8f}",
        f"_cell_length_c {lengths[2]:.8f}",
        f"_cell_angle_alpha {angles[0]:.6f}",
        f"_cell_angle_beta {angles[1]:.6f}",
        f"_cell_angle_gamma {angles[2]:.6f}",
        "_symmetry_space_group_name_H-M 'P 1'",
        "_symmetry_Int_Tables_number 1",
        "loop_",
        "_space_group_symop_operation_xyz",
        "'x, y, z'",
        "loop_",
        "_atom_site_label",
        "_atom_site_type_symbol",
        "_atom_site_fract_x",
        "_atom_site_fract_y",
        "_atom_site_fract_z",
        "_atom_site_occupancy",
    ]
    for idx, (symbol, frac) in enumerate(zip(symbols, fractional), start=1):
        cif_lines.append(
            f"{symbol}{idx} {symbol} {frac[0]:.8f} {frac[1]:.8f} {frac[2]:.8f} 1.0"
        )
    cif_text = "\n".join(cif_lines) + "\n"

    counts: dict[str, int] = {}
    for symbol in symbols:
        counts[symbol] = counts.get(symbol, 0) + 1
    cell = {
        "a": lengths[0], "b": lengths[1], "c": lengths[2],
        "alpha": angles[0], "beta": angles[1], "gamma": angles[2],
    }
    return {
        "cif": cif_text,
        "atoms": len(symbols),
        "elements": counts,
        "cell": cell,
    }


def _inverse_3x3(matrix: list[list[float]]) -> list[list[float]]:
    a, b, c = matrix[0]
    d, e, f = matrix[1]
    g, h, i = matrix[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-12:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    inv = [
        [(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
        [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
        [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det],
    ]
    return inv


def load_structure(rel: str) -> dict[str, Any]:
    path = files.safe_path(rel, must_exist=True)
    if path.is_dir():
        raise ValueError("请选择一个结构文件")
    if not files.is_structure(path):
        raise ValueError("不支持的结构格式")
    if path.stat().st_size > MAX_STRUCTURE_BYTES:
        raise ValueError("结构文件过大")

    fmt = _format_for(path)
    raw = path.read_text(encoding="utf-8", errors="replace")
    content = raw
    atoms = 0
    elements: dict[str, int] = {}
    cell = None
    converted = None

    if fmt == "poscar":
        parsed = _parse_poscar(raw)
        content = parsed["cif"]
        atoms = parsed["atoms"]
        elements = parsed["elements"]
        cell = parsed["cell"]
        converted = "cif"
        fmt = "cif"
    elif fmt == "cif":
        atoms, elements, cell = _cif_summary(raw)
    elif fmt == "xyz":
        atoms, elements = _xyz_summary(raw)
    elif fmt == "pdb":
        atoms, elements = _pdb_summary(raw)
    elif fmt in {"mol", "mol2", "sdf"}:
        atoms, elements = _mol_summary(raw)
    else:
        atoms, elements = _xyz_summary(raw)

    return {
        "path": files.relative(path),
        "name": path.name,
        "format": fmt,
        "content": content,
        "atoms": atoms,
        "elements": elements,
        "cell": cell,
        "converted": converted,
        "size": path.stat().st_size,
    }


def structure_context(rel: str, *, limit: int = CONTEXT_LIMIT) -> str:
    path = files.safe_path(rel, must_exist=True)
    if path.stat().st_size > MAX_STRUCTURE_BYTES:
        return f"[结构文件 {path.name} 过大，未附加上下文]"
    raw = path.read_text(encoding="utf-8", errors="replace")
    fmt = _format_for(path)
    summary = load_structure(rel)
    element_text = ", ".join(f"{k} {v}" for k, v in sorted(summary["elements"].items()))
    head = [
        f"当前在 3D 查看器中打开的结构文件：{path.name}（格式 {summary['format']}，"
        f"约 {summary['atoms']} 个原子）",
    ]
    if element_text:
        head.append(f"元素统计：{element_text}")
    if summary.get("cell"):
        cell = summary["cell"]
        head.append(
            "晶胞：a={a:.4f} Å, b={b:.4f} Å, c={c:.4f} Å, α={alpha:.2f}°, β={beta:.2f}°, γ={gamma:.2f}°".format(**cell)
        )
    head.append("文件内容如下：")
    body = raw[:limit]
    if len(raw) > limit:
        body += "\n…（文件已截断）"
    return "\n".join(head) + "\n```\n" + body + "\n```"
