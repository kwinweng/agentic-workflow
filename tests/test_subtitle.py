from pipeline.transcriber.subtitle import body_to_segments, pick_best_subtitle


def test_prefer_cc_over_ai():
    subs = [
        {"lan": "ai-zh", "subtitle_url": "//x/ai.json"},
        {"lan": "zh-CN", "subtitle_url": "//x/cc.json"},
    ]
    assert pick_best_subtitle(subs)["lan"] == "zh-CN"


def test_ai_subtitle_used_when_only_option():
    subs = [{"lan": "ai-zh", "subtitle_url": "//x/ai.json"}]
    assert pick_best_subtitle(subs)["lan"] == "ai-zh"


def test_skip_entries_without_url():
    # 未登录时 subtitle_url 可能为空串（见调研文档 §3.1）
    subs = [{"lan": "zh-CN", "subtitle_url": ""}, {"lan": "ai-zh", "subtitle_url": None}]
    assert pick_best_subtitle(subs) is None


def test_empty_list():
    assert pick_best_subtitle([]) is None


def test_body_to_segments_strips_empty():
    body = [
        {"from": 0.5, "to": 2.0, "content": " 大家好 "},
        {"from": 2.0, "to": 3.0, "content": "   "},
        {"from": 3.0, "to": 5.0, "content": "今天讲架构"},
    ]
    segs = body_to_segments(body)
    assert len(segs) == 2
    assert segs[0].text == "大家好"
    assert segs[1].start == 3.0
