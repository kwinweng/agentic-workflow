"""链接解析器：任意形态的 B 站链接 → 标准化 VideoRef 列表。

支持：
- https://www.bilibili.com/video/BV...（含 ?p=n 分 P）
- b23.tv 短链（跟随重定向后重新解析）
- 纯 BV 号
- 合集链接：space.bilibili.com/{mid}/channel/collectiondetail?sid={sid}
           space.bilibili.com/{mid}/lists/{sid}?type=season
"""

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from .bili_client import BiliClient
from .models import VideoRef

_BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
_SHORT_RE = re.compile(r"https?://b23\.tv/\w+")
_COLLECTION_RE = re.compile(
    r"space\.bilibili\.com/(?P<mid>\d+)/channel/collectiondetail"
)
_LISTS_RE = re.compile(r"space\.bilibili\.com/(?P<mid>\d+)/lists/(?P<sid>\d+)")


@dataclass
class ParsedLink:
    kind: str  # "video" | "season"
    bvid: str = ""
    page: int | None = None   # 指定分 P 时非 None
    mid: int = 0
    season_id: int = 0


class UnsupportedLinkError(ValueError):
    pass


def parse_link(text: str) -> ParsedLink:
    """纯解析，不发网络请求（短链除外，由 resolve() 先展开）。"""
    text = text.strip()

    m = _LISTS_RE.search(text)
    if m:
        return ParsedLink(kind="season", mid=int(m["mid"]), season_id=int(m["sid"]))

    m = _COLLECTION_RE.search(text)
    if m:
        qs = parse_qs(urlparse(text).query)
        sid = qs.get("sid", ["0"])[0]
        if sid.isdigit() and int(sid) > 0:
            return ParsedLink(kind="season", mid=int(m["mid"]), season_id=int(sid))
        raise UnsupportedLinkError(f"合集链接缺少 sid 参数: {text}")

    m = _BV_RE.search(text)
    if m:
        page: int | None = None
        if "?" in text:
            qs = parse_qs(urlparse(text).query)
            p = qs.get("p", [""])[0]
            if p.isdigit():
                page = int(p)
        return ParsedLink(kind="video", bvid=m.group(1), page=page)

    raise UnsupportedLinkError(f"无法识别的链接: {text}")


def _video_refs_from_view(view: dict, page: int | None) -> list[VideoRef]:
    pages = view.get("pages") or []
    total = len(pages) or 1
    up_name = (view.get("owner") or {}).get("name", "")
    base_url = f"https://www.bilibili.com/video/{view['bvid']}"

    if not pages:  # 极少数情况没有 pages 字段，退化为单 P
        return [
            VideoRef(
                bvid=view["bvid"], aid=view["aid"], cid=view["cid"],
                title=view.get("title", ""), duration_sec=view.get("duration", 0),
                up_name=up_name, url=base_url,
            )
        ]

    selected = pages
    if page is not None:
        if not 1 <= page <= total:
            raise UnsupportedLinkError(f"{view['bvid']} 没有第 {page} P（共 {total} P）")
        selected = [pages[page - 1]]

    return [
        VideoRef(
            bvid=view["bvid"], aid=view["aid"], cid=p["cid"],
            part_no=p["page"], total_parts=total,
            title=view.get("title", ""),
            part_title=p.get("part", "") if total > 1 else "",
            duration_sec=p.get("duration", 0),
            up_name=up_name,
            url=base_url + (f"?p={p['page']}" if total > 1 else ""),
        )
        for p in selected
    ]


def resolve(text: str, client: BiliClient) -> list[VideoRef]:
    """一条链接 → VideoRef 列表（分 P / 合集自动展开）。"""
    m = _SHORT_RE.search(text)
    if m:
        text = client.resolve_short_url(m.group(0))

    parsed = parse_link(text)

    if parsed.kind == "season":
        refs: list[VideoRef] = []
        for bvid in client.list_season_bvids(parsed.mid, parsed.season_id):
            refs.extend(_video_refs_from_view(client.get_view(bvid), page=None))
        return refs

    view = client.get_view(parsed.bvid)
    return _video_refs_from_view(view, parsed.page)
