"""B 站 Web API 客户端：视频信息、字幕列表、字幕下载、合集展开。

限频策略：每次请求前保证与上次请求间隔 >= bili_min_interval 秒，另加 0~1s 随机抖动，
降低风控触发概率（见 docs/01-开源方案调研.md §5）。
"""

import logging
import random
import time

import httpx

from .wbi import sign_params

logger = logging.getLogger(__name__)

API_VIEW = "https://api.bilibili.com/x/web-interface/view"
API_NAV = "https://api.bilibili.com/x/web-interface/nav"
API_PLAYER = "https://api.bilibili.com/x/player/wbi/v2"
API_SEASON = "https://api.bilibili.com/x/polymer/web-space/seasons_archives_list"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class BiliApiError(RuntimeError):
    def __init__(self, code: int, message: str):
        super().__init__(f"bilibili api error {code}: {message}")
        self.code = code


class BiliClient:
    def __init__(self, sessdata: str = "", min_interval: float = 3.0):
        cookies = {"SESSDATA": sessdata} if sessdata else {}
        self._http = httpx.Client(
            headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/"},
            cookies=cookies,
            timeout=20,
            follow_redirects=False,
        )
        self._min_interval = min_interval
        self._last_request_at = 0.0
        self._wbi_keys: tuple[str, str] | None = None

    def close(self) -> None:
        self._http.close()

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = self._min_interval - elapsed
        if wait > 0:
            time.sleep(wait + random.uniform(0, 1))
        self._last_request_at = time.monotonic()

    def _get_json(self, url: str, params: dict | None = None) -> dict:
        self._throttle()
        resp = self._http.get(url, params=params, follow_redirects=True)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code", 0) != 0:
            raise BiliApiError(payload.get("code", -1), payload.get("message", ""))
        return payload.get("data") or {}

    # -- 基础接口 -----------------------------------------------------------

    def resolve_short_url(self, url: str) -> str:
        """跟随 b23.tv 短链重定向，返回最终 URL。"""
        self._throttle()
        resp = self._http.get(url)
        if resp.status_code in (301, 302, 307, 308):
            return resp.headers.get("location", url)
        return str(resp.url)

    def get_view(self, bvid: str) -> dict:
        """视频元信息：aid、cid、标题、分 P 列表、UP 主等。"""
        return self._get_json(API_VIEW, {"bvid": bvid})

    def _get_wbi_keys(self) -> tuple[str, str]:
        if self._wbi_keys is None:
            data = self._get_json(API_NAV)
            img_url = data["wbi_img"]["img_url"]
            sub_url = data["wbi_img"]["sub_url"]
            self._wbi_keys = (
                img_url.rsplit("/", 1)[-1].split(".")[0],
                sub_url.rsplit("/", 1)[-1].split(".")[0],
            )
        return self._wbi_keys

    # -- 字幕（transcriber 路线 A）-----------------------------------------

    def list_subtitles(self, aid: int, cid: int) -> list[dict]:
        """返回字幕列表 [{lan, lan_doc, subtitle_url}, ...]，可能为空。"""
        img_key, sub_key = self._get_wbi_keys()
        params = sign_params({"aid": aid, "cid": cid}, img_key, sub_key)
        data = self._get_json(API_PLAYER, params)
        return (data.get("subtitle") or {}).get("subtitles") or []

    def fetch_subtitle_body(self, subtitle_url: str) -> list[dict]:
        """下载字幕 JSON，返回 [{from, to, content}, ...]。"""
        if subtitle_url.startswith("//"):
            subtitle_url = "https:" + subtitle_url
        self._throttle()
        resp = self._http.get(subtitle_url, follow_redirects=True)
        resp.raise_for_status()
        return resp.json().get("body") or []

    # -- 合集展开（resolver 用）---------------------------------------------

    def list_season_bvids(self, mid: int, season_id: int) -> list[str]:
        """展开 UP 主合集为 bvid 列表（按合集内顺序）。"""
        bvids: list[str] = []
        page = 1
        while True:
            data = self._get_json(
                API_SEASON,
                {"mid": mid, "season_id": season_id, "page_num": page, "page_size": 30},
            )
            archives = data.get("archives") or []
            bvids.extend(a["bvid"] for a in archives)
            total = (data.get("page") or {}).get("total", 0)
            if page * 30 >= total or not archives:
                break
            page += 1
        return bvids
