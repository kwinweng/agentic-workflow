"""B 站 wbi 接口签名。

算法来源：bilibili-API-collect 文档
https://socialsisteryi.github.io/bilibili-API-collect/docs/misc/sign/wbi.html
img_key / sub_key 从 nav 接口获取，混淆成 mixin_key 后对请求参数做 MD5 签名。
"""

import time
import urllib.parse
from hashlib import md5

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]

_FILTERED_CHARS = "!'()*"


def get_mixin_key(img_key: str, sub_key: str) -> str:
    raw = img_key + sub_key
    return "".join(raw[i] for i in MIXIN_KEY_ENC_TAB)[:32]


def sign_params(params: dict, img_key: str, sub_key: str, wts: int | None = None) -> dict:
    """返回追加了 wts 与 w_rid 的新参数字典。"""
    mixin_key = get_mixin_key(img_key, sub_key)
    signed = dict(params)
    signed["wts"] = wts if wts is not None else int(time.time())
    signed = dict(sorted(signed.items()))
    signed = {
        k: "".join(ch for ch in str(v) if ch not in _FILTERED_CHARS)
        for k, v in signed.items()
    }
    query = urllib.parse.urlencode(signed)
    signed["w_rid"] = md5((query + mixin_key).encode()).hexdigest()
    return signed
