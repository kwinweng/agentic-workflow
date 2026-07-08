import httpx
import pytest

from pipeline.llm import LLMError, OpenAICompatLLM, chunk_text


def _mock_llm(handler) -> OpenAICompatLLM:
    return OpenAICompatLLM(
        "https://api.deepseek.com", "sk-test", "deepseek-chat",
        transport=httpx.MockTransport(handler),
    )


def test_chat_posts_openai_format_and_returns_content():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode()
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": "答复"}}]
        })

    llm = _mock_llm(handler)
    assert llm.chat("系统", "用户") == "答复"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert "deepseek-chat" in captured["body"]


def test_chat_raises_on_http_error():
    llm = _mock_llm(lambda r: httpx.Response(401, text="bad key"))
    with pytest.raises(LLMError, match="401"):
        llm.chat("s", "u")


def test_missing_api_key_rejected():
    with pytest.raises(LLMError, match="LLM_API_KEY"):
        OpenAICompatLLM("https://api.deepseek.com", "", "m")


def test_chunk_text_short_passthrough():
    assert chunk_text("短文本", max_chars=100) == ["短文本"]
    assert chunk_text("   ", max_chars=100) == []


def test_chunk_text_splits_on_paragraphs():
    text = "\n".join(f"第{i}段" + "x" * 50 for i in range(10))
    chunks = chunk_text(text, max_chars=120)
    assert len(chunks) > 1
    assert all(len(c) <= 120 for c in chunks)
    assert "".join(chunks).replace("\n", "") == text.replace("\n", "")


def test_chunk_text_hard_splits_oversize_paragraph():
    text = "a" * 250
    chunks = chunk_text(text, max_chars=100)
    assert [len(c) for c in chunks] == [100, 100, 50]
