"""wbi 签名算法测试，测试向量来自 bilibili-API-collect 官方文档示例。"""

from pipeline.wbi import get_mixin_key, sign_params

IMG_KEY = "7cd084941338484aae1ad9425b84077c"
SUB_KEY = "4932caff0ff746eab6f01bf08b70ac45"


def test_mixin_key_matches_documented_vector():
    assert get_mixin_key(IMG_KEY, SUB_KEY) == "ea1db124af3c7062474693fa704f4ff8"


def test_sign_params_deterministic_and_complete():
    params = {"foo": "114", "bar": "514", "zab": 1919810}
    signed = sign_params(params, IMG_KEY, SUB_KEY, wts=1702204169)
    assert signed["wts"] == "1702204169"  # 签名过程统一转为字符串参与 urlencode
    assert signed["w_rid"] == "8f6f2b5b3d485fe1886cec6a0be8c5d4"


def test_sign_params_filters_special_chars():
    signed = sign_params({"q": "a'b*(c)!"}, IMG_KEY, SUB_KEY, wts=1)
    assert signed["q"] == "abc"


def test_sign_params_does_not_mutate_input():
    params = {"a": 1}
    sign_params(params, IMG_KEY, SUB_KEY, wts=1)
    assert params == {"a": 1}
