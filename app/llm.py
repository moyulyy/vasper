"""LLM 对话：OpenAI 兼容接口的流式调用，附带当前结构上下文。"""

from __future__ import annotations

import json
from typing import Any, Iterator

from . import config, structures

MODE_PROMPTS = {
    "plan": (
        "\n\n当前对话模式：计划模式（Plan）。\n"
        "- 你的任务是理解目标、指出信息缺口、制定清晰可验证的计划。\n"
        "- 不要假装已经执行任何操作，也不要直接给出最终执行结果。\n"
        "- 输出应包含：目标理解、关键假设、分步骤计划、所需参数/文件、风险点。\n"
        "- 可以给关键参数建议，但不要生成完整的长脚本或最终输入文件，除非用户明确要求。\n"
        "- 最后询问用户是否切换执行模式或确认执行。"
    ),
    "execute": (
        "\n\n当前对话模式：执行模式（Execute）。\n"
        "- 直接完成用户任务，给出可执行、可复现的结果，不要只给计划。\n"
        "- 需要代码或输入文件时，给出完整内容、建议保存路径与运行命令。\n"
        "- 信息不足时先做最合理的假设并明确标注，然后继续完成。\n"
        "- 不要声称已经实际运行命令或修改本地文件，除非用户提供了执行结果。"
    ),
}

DEFAULT_SYSTEM_PROMPT = """你是 Vasper，一位材料科学、凝聚态物理与计算化学方向的 AI 研究助手。
你可以看到用户当前在 3D 查看器中打开的结构文件内容（若提供了结构上下文）。

回答要求：
- 使用简体中文（除非用户使用其他语言）。
- 先给出直接结论，再展开关键理由；必要时分点或使用 Markdown 表格。
- 涉及晶体结构时，注意晶系、空间群、配位环境、晶格常数与周期性边界条件。
- 涉及计算时，说明泛函/赝势/截断能/k 点等关键参数选择及其影响。
- 不要编造不存在的实验数据或文献；不确定时明确指出。
- 代码块使用带语言标记的 Markdown 代码围栏。"""


def _local_fallback(prompt: str) -> Iterator[str]:
    message = (
        "尚未配置模型 API，因此我现在只能本地回应。\n\n"
        "请点击右上角的 **设置**（齿轮图标），填写：\n\n"
        "1. **API Base URL**：例如 `https://api.moonshot.cn/v1`\n"
        "2. **API Key**\n"
        "3. **模型名称**：例如 `deepseek-flash`\n\n"
        "保存后即可开始流式对话。你也可以在设置中一键导入本机 sci-circle 的 LLM 配置。\n\n"
        f"你刚才问的是：**{prompt[:120]}**"
    )
    for chunk in message:
        yield chunk


def iter_chat(
    payload: dict[str, Any],
    should_stop: Any = None,
) -> Iterator[dict[str, Any]]:
    """生成事件：{delta} / {reasoning} / {error} / {done}。"""
    settings = config.llm_config()
    api_key = settings.get("api_key") or ""
    base_url = settings.get("base_url") or None
    model = settings.get("model") or "deepseek-flash"

    messages: list[dict[str, Any]] = []
    system_prompt = payload.get("system") or DEFAULT_SYSTEM_PROMPT
    context_path = payload.get("context_path")
    if isinstance(context_path, str) and context_path.strip():
        try:
            system_prompt = (
                system_prompt
                + "\n\n---\n"
                + structures.structure_context(context_path.strip())
            )
        except Exception as exc:
            system_prompt += f"\n\n[结构上下文读取失败：{exc}]"
    messages.append({"role": "system", "content": system_prompt})

    for message in payload.get("messages") or []:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content[:120000]})

    mode = payload.get("mode", "plan")
    if mode not in MODE_PROMPTS:
        mode = "plan"
    messages[0]["content"] = messages[0]["content"] + MODE_PROMPTS[mode]

    if not any(m["role"] == "user" for m in messages):
        yield {"error": "没有可发送的用户消息"}
        return

    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    if not api_key:
        for chunk in _local_fallback(last_user):
            if should_stop is not None and should_stop():
                return
            yield {"delta": chunk}
        yield {"done": True, "model": "local"}
        return

    try:
        from openai import OpenAI
    except ImportError:
        yield {"error": "未安装 openai 包，请运行 pip install openai"}
        return

    try:
        client = OpenAI(api_key=api_key, base_url=base_url or None, timeout=180.0)
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        usage = None
        for chunk in stream:
            if getattr(chunk, "usage", None):
                try:
                    usage = chunk.usage.model_dump()
                except Exception:
                    usage = None
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            if delta is None:
                continue
            content = getattr(delta, "content", None)
            if content:
                yield {"delta": content}
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                yield {"reasoning": reasoning}
        yield {"done": True, "model": model, "usage": usage}
    except Exception as exc:
        message = str(exc)
        if len(message) > 800:
            message = message[:800] + "…"
        yield {"error": f"{type(exc).__name__}: {message}"}
