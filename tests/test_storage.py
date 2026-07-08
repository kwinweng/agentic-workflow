import json

from pipeline.models import Segment, Transcript, VideoRef
from pipeline.storage import render_markdown, save_transcript, video_dir

VIDEO = VideoRef(
    bvid="BV1GJ411x7h7", aid=100, cid=2222, part_no=2, total_parts=3,
    title="测试/课程: 高级篇", part_title="第二集", duration_sec=4000,
    up_name="某UP", url="https://www.bilibili.com/video/BV1GJ411x7h7?p=2",
)

TRANSCRIPT = Transcript(
    source="cc",
    segments=[
        Segment(start=0.0, end=2.0, text="大家好"),
        Segment(start=2.1, end=4.0, text="今天讲架构"),
        Segment(start=10.0, end=12.0, text="第二段开始"),  # 间隔>2.5s，另起段落
    ],
)


def test_video_dir_sanitizes_title(tmp_path):
    d = video_dir(tmp_path, VIDEO)
    assert d.parent == tmp_path / "videos"
    assert "/" not in d.name.replace(tmp_path.name, "")
    assert d.name.startswith("BV1GJ411x7h7-p2-")


def test_render_markdown_paragraphs_and_meta():
    md = render_markdown(VIDEO, TRANSCRIPT)
    assert "P2: 第二集" in md
    assert "人工 CC 字幕" in md
    assert "**[00:00]** 大家好今天讲架构" in md
    assert "**[00:10]** 第二段开始" in md
    assert "01:06:40" in md  # duration 4000s → hh:mm:ss


def test_save_transcript_writes_three_files(tmp_path):
    vdir = save_transcript(tmp_path, VIDEO, TRANSCRIPT)
    assert (vdir / "meta.json").exists()
    assert (vdir / "transcript.md").exists()
    data = json.loads((vdir / "transcript.json").read_text(encoding="utf-8"))
    assert data["source"] == "cc"
    assert len(data["segments"]) == 3
