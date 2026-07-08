"""OpenAI 兼容 LLM 客户端（DeepSeek / Qwen 通过配置切换，见架构文档 §3.4）。

- DeepSeek：LLM_BASE_URL=https://api.deepseek.com，LLM_MODEL=deepseek-chat
- Qwen：   LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1，LLM_MODEL=qwen-plus
"""

from typing import Protocol

import httpx


class ChatLLM(Protocol):
    def chat(self, system: str, user: str) -> str: ...


class LLMError(RuntimeError):
    pass


class OpenAICompatLLM:
    def __init__(
        self, base_url: str, api_key: str, model: str,
        *, timeout: float = 180, transport: httpx.BaseTransport | None = None,
    ):
        if not api_key:
            raise LLMError("未配置 LLM_API_KEY，无法进行 AI 提炼")
        self._model = model
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    def chat(self, system: str, user: str, temperature: float = 0.3) -> str:
        resp = self._http.post(
            "/chat/completions",
            json={
                "model": self._model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        if resp.status_code != 200:
            raise LLMError(f"LLM 请求失败 {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMError(f"LLM 响应格式异常: {str(data)[:300]}") from e


def chunk_text(text: str, max_chars: int = 6000) -> list[str]:
    """按段落边界把长文本切块（单段超限时硬切），供分块 map-reduce 用。"""
    if len(text) <= max_chars:
        return [text] if text.strip() else []

    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for para in text.split("\n"):
        while len(para) > max_chars:  # 单段超限，硬切
            if buf:
                chunks.append("\n".join(buf))
                buf, size = [], 0
            chunks.append(para[:max_chars])
            para = para[max_chars:]
        if size + len(para) + 1 > max_chars and buf:
            chunks.append("\n".join(buf))
            buf, size = [], 0
        buf.append(para)
        size += len(para) + 1
    if buf and "\n".join(buf).strip():
        chunks.append("\n".join(buf))
    return chunks
