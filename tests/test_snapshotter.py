from pathlib import Path

from _samples import TRANSCRIPT, VIDEO
from pipeline.snapshotter import build_article, render_article, select_frame_timestamps


def test_select_frame_timestamps_thins_by_min_gap():
    assert select_frame_timestamps([0, 10, 65, 70, 200], min_gap=60) == [0, 65, 200]
    assert select_frame_timestamps([], min_gap=60) == []


def test_render_article_interleaves_images():
    images = {0.0: "images/0001_00-00.jpg"}
    md = render_article(VIDEO, TRANSCRIPT, images)
    img_pos = md.index("![00:00](images/0001_00-00.jpg)")
    text_pos = md.index("**[00:00]** 大家好")
    assert img_pos < text_pos          # 截图在对应段落之前
    assert "图文稿" in md
    assert "**[00:10]** 第二段开始" in md


def test_build_article_with_fake_extractor(tmp_path):
    calls = []

    def fake_downloader(video, work_dir, tool):
        p = tmp_path / "fake.mp4"
        p.write_bytes(b"x")
        return p

    def fake_extractor(video_path: Path, ts: float, out: Path):
        calls.append(ts)
        out.write_bytes(b"jpg")

    article, count = build_article(
        VIDEO, TRANSCRIPT, tmp_path / "kb", tmp_path / "work",
        frame_extractor=fake_extractor, video_downloader=fake_downloader, min_gap=5,
    )
    assert article.exists()
    assert count == len(calls) == 2   # 段落起点 0.0 与 10.0，间隔≥5s
    content = article.read_text(encoding="utf-8")
    assert "images/0001_00-00.jpg" in content
    assert (article.parent / "images" / "0001_00-00.jpg").exists()


def test_build_article_skips_failed_frames(tmp_path):
    def fake_downloader(video, work_dir, tool):
        p = tmp_path / "fake.mp4"
        p.write_bytes(b"x")
        return p

    def broken_extractor(video_path, ts, out):
        raise RuntimeError("ffmpeg boom")

    article, count = build_article(
        VIDEO, TRANSCRIPT, tmp_path / "kb", tmp_path / "work",
        frame_extractor=broken_extractor, video_downloader=fake_downloader, min_gap=5,
    )
    assert article.exists()   # 全部抽帧失败仍产出纯文字图文稿
    assert count == 0
    assert "![" not in article.read_text(encoding="utf-8")
