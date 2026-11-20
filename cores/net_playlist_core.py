# -*- coding: utf-8 -*-
"""
net_playlist_core.py — 平台歌单核心逻辑（无 GUI 依赖，可独立 CLI 运行）。

职责：
  - 从 go-music-api 拉取歌单（多平台）
  - 本地歌曲匹配
  - 保存为 m3u 歌单 + 封面

GUI 由 net_playlist_page.py 调用；CLI 直接 `python net_playlist_core.py ...`。
"""

import os
import sys
import random
import threading
import requests
from pathlib import Path

# 允许从 cores/ 目录直接运行（CLI）：把项目根加入 sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from script.music.music_tag import TAG_DEFINITIONS, MUSIC_PLATFARM
from script.music.load_music import (
    split_artists,
    load_music,
    sanitize_filename,
    is_dirty_playlist,
)
from script.common.logger import AppLogger
from script.common.cache_manager import JsonCache
from script.common.rate_limiter import api_limiter
from script.music.playlist_service import fetch_playlist_songs, SonglistCache
from pypinyin import lazy_pinyin, Style

logger = AppLogger()
KeySLCache = JsonCache("cahce/songlist_cache_key.json")
net_limiter = api_limiter


def set_logger(log):
    global logger
    if log is not None:
        logger = log


# ================= 工具 =================
def normalize(text):
    return text.replace(" ", "").lower()


def build_local_index(songs):
    index = {}
    for s in songs:
        key = normalize(s["title"] + split_artists(s["artist"])[0])
        index[key] = s
    return index


def match_local(online, index):
    result = []
    for s in online:
        key = normalize(s["title"] + split_artists(s["artist"])[0])
        if key in index:
            result.append(index[key])
    return result


def save_playlist_cover(playlist_name, cover_url, save_dir="playlists/covers"):
    if not cover_url:
        return None
    os.makedirs(save_dir, exist_ok=True)
    try:
        r = requests.get(cover_url, timeout=15)
        if r.status_code != 200:
            return None
        filename = sanitize_filename(playlist_name) + ".jpg"
        filepath = os.path.join(save_dir, filename)
        with open(filepath, "wb") as f:
            f.write(r.content)
        return filepath
    except Exception as e:
        logger.exception(e)
        return None


# ================= 平台实现 =================
def get_netease_multi(keyword, list_limit=30, platform="all"):
    BASE = "http://localhost:8080/api/v1"
    result = []

    # ===== 1️⃣ 搜索歌单 =====
    try:
        data = KeySLCache.get(keyword)
        if not data:
            net_limiter.wait()
            r = requests.get(
                f"{BASE}/music/search",
                params={"q": keyword, "type": "playlist"},
                timeout=30,
            )
            # 健壮性：响应非 JSON 时（如网关拦截/错误页）跳过，避免 .json() 崩溃
            ctype = (r.headers.get("Content-Type") or "").lower()
            if "json" not in ctype or not r.text:
                logger.warning(
                    f"    /music/search 非 JSON 响应（HTTP {r.status_code}），跳过\n"
                )
                return []
            data = r.json().get("data", [])
            KeySLCache.set(keyword, data)
        playlists = data.get("playlists", [])
    except Exception as e:
        logger.exception(e)
        return []

    # ===== 2️⃣ 遍历歌单 =====
    list_count = 0
    playlists = sorted(playlists, key=lambda x: x["play_count"], reverse=True)
    for p in playlists:
        pid = p["id"]
        pname = p["name"]
        source = p["source"]
        cover = p["cover"]
        play_cnt = p.get("play_count", 0)
        track_cnt = p.get("track_count", 0)

        if source != platform and platform != "all":
            continue
        if list_count == list_limit:
            break

        if is_dirty_playlist(pname, play_cnt, track_cnt):
            continue
        elif play_cnt == 0:
            if random.random() > 0.5:
                continue
        else:
            list_count += 1
            logger.info(f"    读取歌单: {pname}")

        try:
            songs_raw = fetch_playlist_songs(pid, source, pname, logger)
            songs = [
                {
                    "title": s.get("name", ""),
                    "artist": s.get("artist", ""),
                    "album": s.get("album", ""),
                }
                for s in songs_raw
            ]
            logger.info(f"    获取: {len(songs)} 首\n")
            result.append(
                {"name": pname, "source": source, "cover": cover, "songs": songs}
            )
        except Exception as e:
            logger.exception(e)

    return result


# ================= 保存为 m3u =================
def save_playlist(name, songs, cover_url="", music_dir=None):
    if not music_dir:
        logger.warning("    未指定音乐目录，跳过保存\n")
        return

    # O1: 统一用 os.path（Windows 原生），避免 as_posix 风格混用
    base_dir = os.path.join(music_dir, "AI分类歌单")
    name = sanitize_filename(name)
    path = os.path.join(base_dir, name)
    os.makedirs(path, exist_ok=True)

    file_path = os.path.join(path, f"{name}.m3u")
    if cover_url != "":
        save_playlist_cover(name, cover_url, path)
    logger.info(f"    ->生成:{file_path}")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(f"#PLAYLIST:{name}\n")
        for s in songs:
            title = s.get("title", "未知")
            artist = s.get("artist", "未知")
            album = s.get("album", "未知专辑")
            duration = s.get("duration", -1)
            f.write(f"#EXTALB:{album}\n")
            f.write(f"#EXTART:{artist}\n")
            f.write(f"#EXTINF:{duration},{artist} - {title}\n")
            f.write((s.get("path", "") or "") + "\n")


def generate_netease_multi(
    keyword, songs, limit, platform="all", min_limit=2, music_dir=None
):
    playlists = get_netease_multi(keyword, list_limit=limit, platform=platform)
    index = build_local_index(songs)

    for p in playlists:
        pname = p["name"]
        source = p["source"]
        logger.info(f"    处理歌单: {pname}")

        matched = match_local(p["songs"], index)

        if len(matched) < min_limit:
            if len(matched) == 0:
                logger.warning("    没有匹配到歌曲, 跳过\n")
            else:
                logger.warning(f"    只匹配到({len(matched)})首歌曲，跳过\n")
            continue

        first = lazy_pinyin(pname, style=Style.FIRST_LETTER)
        for i in first:
            if i.isalpha():
                break

        save_playlist(f"{i.upper()}_{pname}_{source}", matched, p["cover"], music_dir)
        logger.info(f"    匹配: {len(matched)} / {len(p['songs'])}\n")


# ================= 顶层入口（GUI/CLI 共用） =================
def run_playlist(
    music_dir,
    mode="preset",
    group=None,
    tag=None,
    keyword=None,
    limit=30,
    min_limit=2,
    platform="all",
    log=None,
):
    """按指定模式生成歌单。

    mode:
      - "preset" : 按 TAG_DEFINITIONS[group][tag] 关键词生成（tag 可 "ALL" 表示该组全部）
      - "local"  : 随机取本地歌曲作为关键词
      - "custom" : 用自定义 keyword
    """
    global logger
    logger = log if log is not None else AppLogger()

    songs = load_music(music_dir, log=logger)

    if mode == "preset":
        group = group or list(TAG_DEFINITIONS.keys())[0]
        if tag == "ALL":
            logger.info(f"批量生成: {group}")
            for t, keywords in TAG_DEFINITIONS[group].items():
                logger.info(f"  {t}")
                generate_netease_multi(
                    keyword=" ".join(keywords),
                    songs=songs,
                    limit=limit,
                    min_limit=min_limit,
                    platform=platform,
                    music_dir=music_dir,
                )
        else:
            keywords = TAG_DEFINITIONS[group][tag]
            logger.info(f"{group} - {tag}")
            generate_netease_multi(
                keyword=" ".join(keywords),
                songs=songs,
                limit=limit,
                min_limit=min_limit,
                platform=platform,
                music_dir=music_dir,
            )
    elif mode == "local":
        num_song = len(songs)
        page = int((limit - 1) / 5) + 1
        label_en = [0] * num_song
        loop_count = (page if num_song > page else num_song)

        i = 0
        while i < loop_count:
            idx = random.randint(0, num_song - 1)
            if label_en[idx] != 1:
                label_en[idx] = 1
                i += 1
            else:
                continue
            title = songs[idx]["title"]
            artist = songs[idx]["artist"]
            keywords = title + " " + artist
            logger.info(f"随机选择歌曲: {title} - {artist}\n")
            generate_netease_multi(
                keyword=keywords,
                songs=songs,
                limit=5,
                min_limit=min_limit,
                platform=platform,
                music_dir=music_dir,
            )
    elif mode == "custom":
        if not keyword:
            logger.warning("请输入关键词\n")
            return
        logger.info(f"自定义搜索: {keyword}")
        generate_netease_multi(
            keyword=keyword,
            songs=songs,
            limit=limit,
            min_limit=min_limit,
            platform=platform,
            music_dir=music_dir,
        )

    KeySLCache.save()
    SonglistCache.save()
    logger.info("生成完成\n")


# ---------------- CLI ----------------
def main():
    import argparse

    p = argparse.ArgumentParser(description="平台歌单核心（GUI/CLI 双模式）")
    p.add_argument("music_dir", help="音乐目录")
    p.add_argument("--mode", default="custom", choices=["preset", "local", "custom"])
    p.add_argument("--group", default=None, help="preset 模式：标签组")
    p.add_argument("--tag", default=None, help="preset 模式：具体标签或 ALL")
    p.add_argument("--keyword", default=None, help="custom 模式：搜索关键词")
    p.add_argument("--limit", type=int, default=30, help="网络搜索数量")
    p.add_argument("--min", type=int, default=2, dest="min_limit", help="歌单最小数量")
    p.add_argument("--platform", default="all", choices=MUSIC_PLATFARM)
    args = p.parse_args()

    run_playlist(
        music_dir=args.music_dir,
        mode=args.mode,
        group=args.group,
        tag=args.tag,
        keyword=args.keyword,
        limit=args.limit,
        min_limit=args.min_limit,
        platform=args.platform,
    )


if __name__ == "__main__":
    main()
