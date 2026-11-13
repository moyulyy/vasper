"""轻量 Markdown → Qt 富文本 HTML 渲染（无第三方依赖）。"""

from __future__ import annotations

import html
import re

from . import theme

_CODE_FENCE = re.compile(r"^```([\w+.-]*)\s*$")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_UL = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_OL = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
_HR = re.compile(r"^\s*([-*_])\1{2,}\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
_QUOTE = re.compile(r"^\s*>\s?(.*)$")


def _inline(text: str, palette) -> str:
    """行内标记。先转义 HTML，再替换 Markdown。"""
    parts: list[tuple[str, str]] = []
    # 先把行内代码抽出来，避免其中的 * _ 被当作强调
    def stash(match: re.Match) -> str:
        parts.append(("code", match.group(1)))
        return f"\x00{len(parts) - 1}\x00"

    text = re.sub(r"`([^`\n]+)`", stash, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r"\1", text)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        rf'<a href="\2" style="color:{palette.accent};text-decoration:none;">\1</a>',
        text,
    )
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__([^_]+)__", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", text)
    text = re.sub(r"(?<![\w_])_([^_\n]+)_(?![\w_])", r"<i>\1</i>", text)
    text = re.sub(r"~~([^~]+)~~", r"<s>\1</s>", text)

    def restore(match: re.Match) -> str:
        index = int(match.group(1))
        kind, value = parts[index]
        if kind == "code":
            return (
                f'<code style="font-family:\'{theme.mono_family()}\'; font-size:11px; '
                f'background-color:{palette.code_bg}; color:{palette.code_text}; '
                f'padding:1px 4px;">{html.escape(value, quote=False)}</code>'
            )
        return value

    text = re.sub(r"\x00(\d+)\x00", restore, text)
    return text


def _split_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def render(text: str, palette=None) -> str:
    """返回可直接交给 QTextBrowser 的 HTML 片段。"""
    palette = palette or theme.current()
    if not text:
        return ""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output: list[str] = []
    index = 0
    paragraph: list[str] = []
    list_stack: list[str] = []
    quote: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph:
            return
        joined = "<br>".join(_inline(line, palette) for line in paragraph)
        output.append(
            f'<p style="margin:2px 0 7px 0; line-height:1.62;">{joined}</p>'
        )
        paragraph.clear()

    def flush_list() -> None:
        while list_stack:
            output.append(f"</{list_stack.pop()}>")

    def flush_quote() -> None:
        if quote:
            joined = "<br>".join(_inline(line, palette) for line in quote)
            output.append(
                f'<table width="100%" cellspacing="0" cellpadding="0" style="margin:6px 0;">'
                f'<tr><td style="border-left:3px solid {palette.border_strong}; '
                f'padding:1px 0 1px 10px; color:{palette.muted}; font-size:12px;">{joined}</td></tr></table>'
            )
            quote.clear()

    while index < len(lines):
        line = lines[index]
        fence = _CODE_FENCE.match(line)
        if fence:
            flush_paragraph()
            flush_list()
            flush_quote()
            language = fence.group(1) or ""
            index += 1
            block: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                block.append(lines[index])
                index += 1
            index += 1
            code = "\n".join(block) or " "
            code_lines = []
            for raw_line in code.split("\n"):
                expanded = raw_line.expandtabs(4)
                stripped = expanded.lstrip(" ")
                indent = len(expanded) - len(stripped)
                escaped = html.escape(stripped, quote=False).replace(" ", "&nbsp;")
                code_lines.append(("&nbsp;" * indent) + (escaped if escaped else "&nbsp;"))
            code_html = "<br>".join(code_lines)
            label = (
                f'<tr><td style="color:{palette.muted}; font-size:9px; letter-spacing:1px; '
                f'padding:6px 10px 0 10px;">{html.escape(language.upper())}</td></tr>'
                if language
                else ""
            )
            output.append(
                f'<table width="100%" cellspacing="0" cellpadding="0" '
                f'style="margin:7px 0; background-color:{palette.code_bg};">'
                f"{label}"
                f'<tr><td style="padding:7px 10px;">'
                f'<p style="margin:0; font-family:\'{theme.mono_family()}\'; font-size:11px; '
                f'color:{palette.code_text}; line-height:1.45;">{code_html}</p>'
                f"</td></tr></table>"
            )
            continue

        if not line.strip():
            flush_paragraph()
            flush_list()
            flush_quote()
            index += 1
            continue

        heading = _HEADING.match(line)
        if heading:
            flush_paragraph()
            flush_list()
            flush_quote()
            level = len(heading.group(1))
            size = {1: 17, 2: 15.5, 3: 14.5, 4: 13.5}.get(level, 13)
            top = 12 if level <= 2 else 9
            output.append(
                f'<p style="margin:{top}px 0 5px 0; font-size:{size}px; font-weight:600;">'
                f"{_inline(heading.group(2), palette)}</p>"
            )
            index += 1
            continue

        # 表格
        if "|" in line and index + 1 < len(lines) and _TABLE_SEP.match(lines[index + 1]):
            flush_paragraph()
            flush_list()
            flush_quote()
            header_cells = _split_table_row(line)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append(_split_table_row(lines[index]))
                index += 1
            head_html = "".join(
                f'<th align="left" style="padding:5px 9px; font-size:11px; '
                f'color:{palette.text}; border-bottom:1px solid {palette.border_strong};">'
                f"{_inline(cell, palette)}</th>"
                for cell in header_cells
            )
            body_html = "".join(
                "<tr>"
                + "".join(
                    f'<td style="padding:5px 9px; font-size:11.5px; '
                    f'border-bottom:1px solid {palette.border};">{_inline(cell, palette)}</td>'
                    for cell in row
                )
                + "</tr>"
                for row in rows
            )
            output.append(
                f'<table width="100%" cellspacing="0" cellpadding="0" '
                f'style="margin:7px 0; border:1px solid {palette.border};">'
                f"<tr>{head_html}</tr>{body_html}</table>"
            )
            continue

        quote_match = _QUOTE.match(line)
        if quote_match:
            flush_paragraph()
            flush_list()
            quote.append(quote_match.group(1))
            index += 1
            continue

        if _HR.match(line):
            flush_paragraph()
            flush_list()
            flush_quote()
            output.append(
                f'<table width="100%" cellspacing="0" cellpadding="0" style="margin:10px 0;">'
                f'<tr><td style="border-top:1px solid {palette.border};"></td></tr></table>'
            )
            index += 1
            continue

        unordered = _UL.match(line)
        ordered = _OL.match(line)
        if unordered or ordered:
            flush_paragraph()
            flush_quote()
            kind = "ul" if unordered else "ol"
            if not list_stack or list_stack[-1] != kind:
                flush_list()
                list_stack.append(kind)
                output.append(
                    f'<{kind} style="margin:3px 0 8px 0; padding-left:22px;">'
                )
            content = unordered.group(2) if unordered else ordered.group(3)
            output.append(
                f'<li style="margin:2px 0; line-height:1.6;">{_inline(content, palette)}</li>'
            )
            index += 1
            continue

        flush_list()
        paragraph.append(line.strip())
        index += 1

    flush_paragraph()
    flush_list()
    flush_quote()
    return "\n".join(output)


def document(text: str, palette=None, *, streaming: bool = False) -> str:
    palette = palette or theme.current()
    body = render(text, palette)
    if streaming:
        body += (
            f'<p style="margin:0;"><span style="color:{palette.accent}; font-size:11px;">▍</span></p>'
        )
    return (
        f'<html><body style="margin:0; padding:0; color:{palette.text_soft}; '
        f'font-size:12.5px; line-height:1.62;">{body}</body></html>'
    )
