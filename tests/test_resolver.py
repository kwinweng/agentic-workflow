import pytest

from pipeline.resolver import ParsedLink, UnsupportedLinkError, _video_refs_from_view, parse_link


def test_parse_plain_bv():
    p = parse_link("BV1GJ411x7h7")
    assert p == ParsedLink(kind="video", bvid="BV1GJ411x7h7", page=None)


def test_parse_standard_url_with_page():
    p = parse_link("https://www.bilibili.com/video/BV1GJ411x7h7?p=3&spm_id_from=x")
    assert p.kind == "video"
    assert p.bvid == "BV1GJ411x7h7"
    assert p.page == 3


def test_parse_url_without_page():
    p = parse_link("https://www.bilibili.com/video/BV1GJ411x7h7/")
    assert p.page is None


def test_parse_collection_link():
    p = parse_link(
        "https://space.bilibili.com/12345/channel/collectiondetail?sid=678&ctype=0"
    )
    assert p == ParsedLink(kind="season", mid=12345, season_id=678)


def test_parse_lists_season_link():
    p = parse_link("https://space.bilibili.com/12345/lists/678?type=season")
    assert p == ParsedLink(kind="season", mid=12345, season_id=678)


def test_parse_garbage_raises():
    with pytest.raises(UnsupportedLinkError):
        parse_link("https://example.com/whatever")


VIEW_MULTI_PART = {
    "bvid": "BV1GJ411x7h7",
    "aid": 100,
    "cid": 1111,
    "title": "测试课程",
    "duration": 3600,
    "owner": {"name": "某UP"},
    "pages": [
        {"cid": 1111, "page": 1, "part": "第一集", "duration": 1800},
        {"cid": 2222, "page": 2, "part": "第二集", "duration": 1800},
    ],
}


def test_expand_all_parts():
    refs = _video_refs_from_view(VIEW_MULTI_PART, page=None)
    assert [r.cid for r in refs] == [1111, 2222]
    assert refs[0].total_parts == 2
    assert refs[1].part_title == "第二集"
    assert refs[1].url.endswith("?p=2")


def test_select_single_part():
    refs = _video_refs_from_view(VIEW_MULTI_PART, page=2)
    assert len(refs) == 1
    assert refs[0].cid == 2222


def test_out_of_range_part_raises():
    with pytest.raises(UnsupportedLinkError):
        _video_refs_from_view(VIEW_MULTI_PART, page=5)
