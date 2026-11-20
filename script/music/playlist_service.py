# playlist_service.py
# ✅ 歌单详情抓取公共逻辑（缓存 + 限流 + 请求），供
#    net_playlist_page 与 classify_core 复用，消除重复。
import requests

from script.common.cache_manager import JsonCache
from script.common.rate_limiter import api_limiter

SonglistCache = JsonCache("cahce/songlist_cache.json")

BASE = "http://localhost:8080/api/v1"
_limiter = api_limiter


def fetch_playlist_songs(pid, source, pname, logger=None):
    """获取某歌单的歌单详情（本地歌曲列表）。

    命中 SonglistCache 则直接返回（不占限流额度）；
    未命中则限流后请求 go-music-api 并写回缓存。

    返回歌曲原始 dict 列表（每项含 name/artist/album 等字段），失败返回 []。
    """
    cache_key = f"{pname}_{pid}"
    songs_raw = SonglistCache.get(cache_key)
    if songs_raw:
        return songs_raw

    _limiter.wait()
    try:
        r = requests.get(
            f"{BASE}/playlist/detail",
            params={"id": pid, "source": source},
            timeout=30
        )
        # 非 JSON 响应（网关拦截/错误页）时跳过，避免 .json() 崩溃
        if "json" not in (r.headers.get("Content-Type") or "").lower() or not r.text:
            if logger is not None:
                logger.warning(f"    /playlist/detail 非 JSON 响应（HTTP {r.status_code}），跳过\n")
            return []
        detail = r.json()
        songs_raw = detail.get("data", [])
        SonglistCache.set(cache_key, songs_raw)
        return songs_raw
    except Exception as e:
        if logger is not None:
            logger.exception(e)
        return []
