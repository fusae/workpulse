"""兼容 OpenAI 风格接口的 LLM 客户端。"""

import json
import os
import urllib.error
import urllib.request
from typing import Dict, List

from workpulse.settings import load_settings


class LLMError(RuntimeError):
    pass


def llm_is_configured() -> bool:
    settings = load_settings()
    return bool(os.environ.get(settings.llm_api_key_env))


def analyze_with_llm(snapshot: Dict[str, object], heuristic: Dict[str, List[str]]) -> Dict[str, object]:
    settings = load_settings()
    api_key = os.environ.get(settings.llm_api_key_env)
    if not api_key:
        raise LLMError(f"缺少环境变量 {settings.llm_api_key_env}")

    payload = {
        "model": settings.llm_model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一个工作效率分析助手。请基于用户提供的活动摘要输出 JSON，"
                    "字段必须包含 summary, findings, suggestions。"
                    "summary 是一段简短中文总结；findings 和 suggestions 是字符串数组。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "snapshot": snapshot,
                        "heuristic": heuristic,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }

    request = urllib.request.Request(
        settings.llm_endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.llm_timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise LLMError(str(exc)) from exc

    try:
        result = json.loads(body)
        content = result["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise LLMError(f"LLM 返回格式无法解析: {exc}") from exc

    return {
        "summary": str(parsed.get("summary", "")),
        "findings": [str(item) for item in parsed.get("findings", [])],
        "suggestions": [str(item) for item in parsed.get("suggestions", [])],
    }
