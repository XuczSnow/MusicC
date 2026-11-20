# -*- coding: utf-8 -*-
"""
metadata_core.py — 元数据增强核心逻辑（无 GUI 依赖，可独立 CLI 运行）。

职责：
  - 从 brainz / go-music-api 抓取 元数据（标题/歌手/专辑/年份/封面/歌词）
  - 写入 FLAC / MP3 标签（含同步歌词 LRC）
  - AI 对齐 / 增补（faster-whisper 惰性）

GUI 由 metadata_page.py 调用；CLI 直接 `python metadata_core.py ...`。
"""

import os
import re
import shutil
import sys
import time
import datetime
import requests

# 允许从 cores/ 目录直接运行（CLI）：把项目根加入 sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from script.common.rate_limiter import api_limiter, lyric_limiter
from script.music.load_music import split_artists, load_music
from script.music.music_tag import MUSIC_PLATFARM
from script.music.music_fetcher import MusicFetcher
from script.common.logger import AppLogger
from script.common.cache_manager import JsonCache
# ASR 对齐/增补模块（faster-whisper 惰性）
from script.music.asr_align import (
    transcribe_head,
    transcribe_full,
    align_first_lines,
    get_cached_asr,
    set_cached_asr,
    save_cache as save_asr_cache,
    write_lrc as asr_write_lrc,
    align_lyric_to_audio,
)

# 限流器
meta_limiter = api_limiter
netease_limiter = lyric_limiter

# 重库惰性导入
_EasyID3 = _FLAC = _Picture = _USLT = _APIC = _MP3 = None
_Image = None
BytesIO = None


def _import_tag_libs():
    global _EasyID3, _FLAC, _Picture, _USLT, _APIC, _MP3, _Image, BytesIO
    if _EasyID3 is not None:
        return
    from mutagen.easyid3 import EasyID3
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import USLT, APIC
    from mutagen.mp3 import MP3
    from PIL import Image
    from io import BytesIO as _BytesIO
    _EasyID3, _FLAC, _Picture = EasyID3, FLAC, Picture
    _USLT, _APIC, _MP3 = USLT, APIC, MP3
    _Image, BytesIO = Image, _BytesIO


BASE_URL = "http://localhost:8080/api/v1/music"
logger = AppLogger()
HEADERS = {"Referer": "http://music.163.com", "User-Agent": "Mozilla/5.0"}

brainz = MusicFetcher(logger)
BrainzSCache = JsonCache("cahce/song_cache_brainz.json")
NetSCache = JsonCache("cahce/song_cache_net.json")


def set_logger(log):
    global logger
    if log is not None:
        logger = log


def get_year_from_netease(title, artist):
    keyword = f"{title} {artist}".strip()
    try:
        netease_limiter.wait()
        r = requests.get(
            "http://music.163.com/api/search/get",
            params={"s": keyword, "type": 1, "limit": 1},
            headers=HEADERS,
            timeout=5,
        )
        data = r.json()
        song_id = data["result"]["songs"][0]["id"]

        r2 = requests.get(
            "http://music.163.com/api/song/detail",
            params={"ids": f"[{song_id}]"},
            headers=HEADERS,
            timeout=5,
        )
        songs = r2.json()["result"]["songs"]

        best_year = ""
        for song in songs:
            pt = song["album"].get("publishTime", 0)
            if pt:
                best_year = datetime.datetime.fromtimestamp(pt / 1000).strftime("%Y-%m-%d")
                break
        return best_year
    except Exception as e:
        logger.exception(e)
    return ""


def fetch_song_meta(title, artist="", plat="kugou", date_en=1):
    keyword = f"{title} {artist}".strip()

    lyric = ""
    sync_lyric = ""
    year = ""

    if plat == "brainz":
        cache_key = f"{artist}-{title}"
        s = BrainzSCache.get(cache_key)
        if not s:
            meta_limiter.wait()
            s = brainz.build_song(title, artist)
            BrainzSCache.set(cache_key, s)
        if not s:
            return None
        year = s.get("year")
        sync_lyric = s.get("synced_lyrics") or ""
        lyric = s.get("lyrics") or ""
        if not lyric:
            lyric = sync_lyric
        s["cover"] = s.get("cover_url")
    else:
        cache_key = f"{artist}-{title}"
        s = NetSCache.get(cache_key)
        if not s:
            meta_limiter.wait()
            try:
                r = requests.get(
                    f"{BASE_URL}/search",
                    params={"keyword": keyword, "page": 1, "size": 1},
                    timeout=30,
                    proxies={"http": None, "https": None},
                )
                data = r.json().get("data", [])
                songs = data.get("songs", [])
                if not songs and isinstance(data.get("data"), dict):
                    songs = data["data"].get("songs", [])
                if not songs:
                    return None

                s = {}

                def str_verify(s1, s2):
                    return s1.lower() in s2.lower() or s2.lower() in s1.lower()

                for song in songs:
                    if song["source"] == plat:
                        s_artists = split_artists(song["artist"])
                        s_name = song["name"]
                        if str_verify(s_name, title) and str_verify(s_artists[0], artist):
                            s = song
                            break
                if s == {}:
                    logger.warning("    对应平台未获取到信息，全平台搜索")
                    for song in songs:
                        s_artists = split_artists(song["artist"])
                        s_name = song["name"]
                        if str_verify(s_name, title) and str_verify(s_artists[0], artist):
                            s = song
                            break
                if s == {}:
                    return None

                cover = s.get("cover") or ""
                s["cover"] = cover.replace("240/", "")
                NetSCache.set(cache_key, s)
            except Exception as e:
                logger.exception(e)
                return None

        lyric_limiter.wait()
        try:
            song_id = s.get("id")
            lr = requests.get(
                f"{BASE_URL}/lyric",
                params={"id": song_id, "source": plat},
                timeout=30,
            )
            lyric_data = lr.json()
            if lyric_data.get("code") != 200:
                lyric = ""
                sync_lyric = ""
            else:
                lyric = lyric_data["data"].get("lyric", "")
                sync_lyric = lyric_data["data"].get("lrc", "") or ""

            if date_en:
                year = get_year_from_netease(s.get("name", title), s.get("artist", artist))
        except Exception as e:
            logger.exception(e)

    return {
        "title": s.get("name", ""),
        "artist": split_artists(s.get("artist", "")),
        "album": s.get("album", ""),
        "cover": s.get("cover"),
        "year": year,
        "lyric": lyric,
        "sync_lyric": sync_lyric,
    }


def download_cover(url):
    if not url:
        return None
    try:
        return requests.get(url, timeout=15).content
    except Exception as e:
        logger.exception(e)
        return None


def make_flac_picture(img, max_size: int = 800):
    _import_tag_libs()
    pic = _Picture()
    pic.type = 3
    pic.desc = "Front Cover"
    with _Image.open(img) as im:
        im = im.convert("RGB")
        if max(im.size) > max_size:
            im.thumbnail((max_size, max_size), _Image.LANCZOS)
        import io
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=92)
        pic.data = buf.getvalue()
        pic.mime = "image/jpeg"
        pic.width, pic.height = im.size
    return pic


def rewrite_songs(overwrite, song, meta, type, pixel=800, force_year=False):
    _import_tag_libs()

    if type == "flac":
        audio = _FLAC(song["path"])
    elif type == "mp3":
        audio = _EasyID3(song["path"])

    if overwrite or not song.get("title"):
        if meta["title"] != '':
            logger.info(f"    -> 重写 title: {meta['title']}")
            audio["title"] = meta["title"]
        else:
            logger.info("    -> 没有获取到 title")

    if overwrite or not song.get("artist"):
        if meta["artist"] != '':
            logger.info(f"    -> 重写 artist: {meta['artist']}")
            audio["artist"] = meta["artist"]
        else:
            logger.info("    -> 没有获取到 artist")

    if overwrite or not song.get("album"):
        if meta["album"] != '':
            logger.info(f"    -> 重写 album: {meta['album']}")
            audio["album"] = meta["album"]
        else:
            logger.info("    -> 没有获取到 album")

    # 年份：强制更新时所有年份都视为脏（规范3）；否则仅缺失/覆盖时写
    if force_year or overwrite or not song.get("year"):
        if meta["year"] != '':
            logger.info(f"    -> 重写 date: {meta['year']}")
            audio["date"] = meta["year"]
        else:
            logger.info("    -> 没有获取到 date")

    audio.save()
    if type == "mp3":
        audio = _MP3(song["path"])

    # 歌词：统一优先用网络 sync_lyric（带时间戳），其次纯文本 lyric（规范4）
    lyric_val = (meta.get("sync_lyric") or meta.get("lyric") or "").strip()
    if type == "flac":
        if (overwrite or not song.get("lyric")) and lyric_val != "":
            logger.info(f"    -> 重写 lyric")
            audio["lyrics"] = lyric_val
        elif overwrite and lyric_val == "":
            logger.info("    -> 未获取到 lyric，保留原歌词")
    elif type == "mp3":
        if (overwrite or not song.get("lyric")) and lyric_val != "":
            audio.tags.delall("USLT")
            logger.info(f"    -> 重写 lyric")
            audio.tags.add(_USLT(encoding=3, text=lyric_val))
        elif overwrite and lyric_val == "":
            logger.info("    -> 未获取到 lyric，保留原歌词")

    if type == "flac":
        if overwrite or not audio.pictures:
            if meta.get("cover") != "":
                cover = download_cover(meta.get("cover"))
                if cover and "404" not in str(cover):
                    logger.info("    -> 写入封面图片")
                    pic = make_flac_picture(BytesIO(cover), max_size=pixel)
                    # 覆盖模式：先删旧封面，避免累积多张
                    if overwrite:
                        audio.clear_pictures()
                    audio.add_picture(pic)
                else:
                    logger.info("    -> 没有获取到 封面")
            else:
                logger.info("    -> 没有获取到 封面")
    elif type == "mp3":
        if overwrite or not audio.tags.getall("APIC"):
            if meta.get("cover") != "":
                cover = download_cover(meta.get("cover"))
                if cover:
                    logger.info(f"    -> 加入封面图片")
                    audio.tags.add(_APIC(
                        encoding=3,
                        mime="image/jpeg",
                        type=3,
                        desc="Cover",
                        data=make_flac_picture(BytesIO(cover), max_size=pixel).data,
                    ))
                else:
                    logger.info(f"    -> 没有获取到 封面")
            else:
                logger.info("    -> 没有获取到 封面")
    audio.save()
    return audio


def rewrite_date(song, meta, type):
    _import_tag_libs()
    if type == "flac":
        audio = _FLAC(song["path"])
    elif type == "mp3":
        audio = _EasyID3(song["path"])
    year = get_year_from_netease(song["title"], song["artist"])
    if year != '':
        if year < song.get("year", "9999"):
            logger.info(f"    -> 重写 date: {year}")
            audio["date"] = year
            audio.save()
        else:
            logger.info("    -> 无需重写 date")
    else:
        logger.info("    -> 没有获取到 date")


def backup_file(song, music_dir):
    """把 song 原文件复制到 源目录/bak/，保留相对子目录结构。

    仅在首次改动前调用一次。返回备份路径或 None。
    """
    src = song["path"]
    try:
        rel = os.path.relpath(src, music_dir)
        dst = os.path.join(music_dir, "bak", rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst):  # 已备份过则不重复（保留最原始版本）
            shutil.copy2(src, dst)
            return dst
    except Exception as e:
        logger.exception(e)
    return None


def write_song_metadata(song, meta, pixel=800, overwrite=False, write_lrc=False,
                        force_year=False):
    path = song["path"]

    if path.lower().endswith(".flac"):
        audio = rewrite_songs(overwrite, song, meta, "flac", pixel, force_year)
    elif path.lower().endswith(".mp3"):
        audio = rewrite_songs(overwrite, song, meta, "mp3", pixel, force_year)
    else:
        return f"不支持的文件类型: {path}"

    if write_lrc and meta.get("lrc"):
        _import_tag_libs()
        ok = asr_write_lrc(_FLAC, _MP3, _USLT, song, meta["lrc"], overwrite=overwrite)
        if ok:
            logger.info(f"    -> 写入同步歌词 LRC")
        else:
            logger.info(f"    -> 未写入同步歌词 LRC")

    return True


# ---------------- AI 对齐/增补 决策 ----------------
def resolve_lrc(song, meta, ai_sync, ai_fill):
    """决定要写入的同步歌词 LRC（可能为 None）。返回 (lrc_text, source_label)。

    优先级：网络 sync_lyric > ai_sync 校验 > ai_fill 生成/对齐
      1. 网络已给出带时间戳的 sync_lyric → 直接采用（最高优先，不依赖开关）
         - 若 ai_sync 开，额外做前3句 ASR 校验；校验失败则回退 ASR 全曲
      2. ai_sync 开但无 sync_lyric → 无 LRC 可校验，退化为 ASR 全曲
      3. ai_fill 开：无歌词→ASR 全曲；有歌词但无时间戳→逐行对齐（保留原词）
    """
    net_sync = (meta.get("sync_lyric") or "").strip()
    net_plain = (meta.get("lyric") or "").strip()
    artist = song.get("artist") or ""
    title = song.get("title") or ""

    def _head_asr():
        try:
            return transcribe_head(song["path"], seconds=30)
        except Exception as e:
            logger.exception(e)
            return None, None

    # 1️⃣ 网络同步 LRC：最高优先，直接采用
    if net_sync:
        if ai_sync:
            head_text, _ = _head_asr()
            if head_text and align_first_lines(head_text, net_sync, top_k=3):
                logger.info(f"    采用网络同步歌词（ai_sync 校验通过）")
                return net_sync, "net_sync"
            logger.info(f"    ai_sync 校验未通过，ASR 全曲生成 LRC")
            return _asr_full_cached(artist, title, song), "asr"
        logger.info(f"    采用网络同步歌词")
        return net_sync, "net_sync"

    # 2️⃣ ai_sync 开但无网络 LRC：退化为 ASR 全曲
    if ai_sync:
        logger.info(f"    无网络同步歌词，ai_sync → ASR 全曲生成 LRC")
        return _asr_full_cached(artist, title, song), "asr"

    # 3️⃣ ai_fill：无歌词→全曲生成；有歌词无时间戳→逐行对齐
    if ai_fill and not net_plain:
        logger.info(f"    AI增补：无歌词，ASR 全曲生成")
        return _asr_full_cached(artist, title, song), "asr"

    if ai_fill and net_plain and not re.search(r'\[\d{1,2}:\d{2}', net_plain):
        logger.info(f"    AI对齐：歌词无时间戳，ASR 逐行对齐（保留原歌词）")
        try:
            aligned = align_lyric_to_audio(net_plain, song["path"])
        except Exception as e:
            logger.exception(e)
            aligned = None
        if aligned:
            return aligned, "align"

    return None, ""


def _asr_full_cached(artist, title, song):
    dur = song.get("duration", 0)
    cached = get_cached_asr(artist, title, dur)
    if cached:
        return cached.get("lrc")
    try:
        text, lrc = transcribe_full(song["path"])
        if lrc:
            set_cached_asr(artist, title, dur, text, lrc)
            return lrc
    except Exception as e:
        logger.exception(e)
    return None


# ---------------- 顶层入口（GUI/CLI 共用） ----------------
def shift_lrc(lrc_text: str, offset_ms: int) -> str:
    """给 LRC 每一行的时间戳加 offset_ms（正=滞后，负=提前）。

    逐行处理 [mm:ss.xxx] 形式的时间戳，保留原有毫秒精度；负值钳制到 0。
    """
    if not lrc_text or offset_ms == 0:
        return lrc_text

    out = []
    for line in lrc_text.splitlines():
        m = re.match(r"\[\s*(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]\s*(.*)$", line)
        if not m:
            out.append(line)
            continue
        mm, ss, frac, text = m.group(1), m.group(2), m.group(3) or "", m.group(4)
        total_ms = ((int(mm) * 60 + int(ss)) * 1000)
        if frac:
            total_ms += int(frac.ljust(3, "0"))
        total_ms = max(0, total_ms + int(offset_ms))
        nmm, rest = divmod(total_ms, 60000)
        nss, nms = divmod(rest, 1000)
        out.append(f"[{nmm:02d}:{nss:02d}.{nms:03d}] {text}")
    return "\n".join(out)


def run_metadata(
    folder,
    plat="brainz",
    overwrite=False,
    overwrite_dirty=False,
    overwrite_date=False,
    pixel=800,
    ai_sync=False,
    ai_fill=False,
    lrc_offset=0,
    backup=False,
    log=None,
    progress_cb=None,
):
    """处理整个目录的元数据增强。"""
    global logger
    logger = log if log is not None else AppLogger()

    logger.info("扫描音乐库...")
    songs = load_music(folder, log=logger)
    logger.info(f"共发现 {len(songs)} 首歌曲\n")

    total = len(songs)
    song_cnt = 0

    for index, song in enumerate(songs, start=1):
        if progress_cb:
            progress_cb(index, total)

        logger.info(f"    {song['artist']} - {song['title']}")

        # ============ 阶段 A：歌曲信息增补（规范1-4）============
        info_list = ["title", "artist", "year", "lyric", "album", "cover"]
        all_info = all(song[i] not in [False, '', [], {}, -1] for i in info_list)
        # 是否需要写信息：覆盖模式全写；否则缺失 / 脏数据 / 强制更新年份
        dirty = song.get("overwrite", False)
        need_info = overwrite or (not all_info) or (overwrite_dirty and dirty) or overwrite_date

        # 取数据（规范2：按平台）
        meta = None
        if need_info:
            meta = fetch_song_meta(song['title'], song['artist'], plat,
                                   date_en=0 if song["year"] else 1)
            if not meta:
                # 无网络信息时，用本地已有信息兜底（保留可写字段）
                meta = {"title": song["title"], "artist": [song["artist"]],
                        "album": song.get("album", ""), "cover": None,
                        "year": song.get("year", ""),
                        "lyric": song.get("lyric", ""), "sync_lyric": ""}

        lrc_text, _src = None, ""

        # 写信息（规范1/3）：覆盖→全写；否则只写缺失/脏；force_year=overwrite_date
        if need_info:
            # ✅ 备份：改动前把原文件复制到 源目录/bak/（仅首次）
            if backup:
                bkp = backup_file(song, folder)
                if bkp:
                    logger.info(f"    -> 已备份原文件: {bkp}")
            eff_overwrite = overwrite or (overwrite_dirty and dirty)
            write_song_metadata(
                song, meta, pixel,
                overwrite=eff_overwrite,
                force_year=overwrite_date,
            )

        # ============ 阶段 B：歌词处理（规范5，对所有歌曲）============
        ai_active = ai_sync or ai_fill
        offset_active = bool(lrc_offset)
        if not (ai_active or offset_active):
            song_cnt += 1
            continue

        # 歌词基础源（规范4）：网络 sync_lyric 优先
        if meta is None:
            meta = {"title": song["title"], "artist": [song["artist"]],
                    "album": song.get("album", ""), "cover": None,
                    "year": song.get("year", ""),
                    "lyric": song.get("lyric", ""), "sync_lyric": ""}
        base_lrc = (meta.get("sync_lyric") or "").strip()

        if ai_active:
            # 5.1 AI 同步/增补（resolve_lrc 内部已按 sync_lyric 优先 + 对齐/全曲）
            lrc_text, _src = resolve_lrc(song, meta, ai_sync, ai_fill)
            # 若 AI 没产出，但有网络 sync_lyric，则直接采用（偏移单独开时也要有歌词可 shift）
            if not lrc_text and base_lrc:
                lrc_text, _src = base_lrc, "net_sync"
        else:
            # 仅偏移开（无 AI）：对"已有歌词"（网络 sync_lyric / 本地 LRC）做偏移
            src_lyric = base_lrc or (song.get("lyric") or "").strip()
            if re.search(r'\[\d{1,2}:\d{2}', src_lyric):
                lrc_text, _src = src_lyric, "existing"

        # 5.2 歌词偏移：对所有处理的歌曲歌词加偏移
        if lrc_text and offset_active:
            lrc_text = shift_lrc(lrc_text, lrc_offset)
            logger.info(f"    歌词偏移 {lrc_offset:+d}ms 已应用")

        if lrc_text:
            meta["lrc"] = lrc_text
            # 直接写 LRC（FLAC lyrics / MP3 USLT）
            _import_tag_libs()
            ok = asr_write_lrc(_FLAC, _MP3, _USLT, song, lrc_text,
                               overwrite=(overwrite or (overwrite_dirty and dirty)))
            logger.info(f"    -> 写入同步歌词 LRC" if ok else f"    -> 未写入同步歌词 LRC")
        else:
            logger.info(f"    歌词：无可写入的同步 LRC，跳过")

        song_cnt += 1

    BrainzSCache.save()
    NetSCache.save()
    save_asr_cache()

    logger.info("所有歌曲处理完成, 重新载入歌曲\n")
    load_music(folder, log=logger, reload=True)
    return song_cnt


# ---------------- CLI ----------------
def main():
    import argparse

    p = argparse.ArgumentParser(description="元数据增强核心（GUI/CLI 双模式）")
    p.add_argument("music_dir", help="音乐目录")
    p.add_argument("--plat", default="brainz", choices=["brainz"] + MUSIC_PLATFARM[1:])
    p.add_argument("--overwrite", action="store_true", help="覆盖原始元数据")
    p.add_argument("--overwrite-dirty", action="store_true", help="强制覆盖脏数据")
    p.add_argument("--overwrite-date", action="store_true", help="强制更新年份")
    p.add_argument("--pixel", type=int, default=800, help="封面最大分辨率")
    p.add_argument("--ai-sync", action="store_true", help="AI 同步（补时间戳）")
    p.add_argument("--ai-fill", action="store_true", help="AI 增补（无歌词）")
    p.add_argument("--backup", action="store_true", help="备份修改过的歌曲到 源目录/bak")
    p.add_argument("--lrc-offset", type=int, default=0, help="歌词偏移(ms)，正=滞后 负=提前")
    p.add_argument("--gui", action="store_true", help="忽略参数，启动 GUI")
    ns = p.parse_args()

    if ns.gui:
        return  # GUI 由 metadata_page 入口处理

    run_metadata(
        folder=ns.music_dir,
        plat=ns.plat,
        overwrite=ns.overwrite,
        overwrite_dirty=ns.overwrite_dirty,
        overwrite_date=ns.overwrite_date,
        pixel=ns.pixel,
        ai_sync=ns.ai_sync,
        ai_fill=ns.ai_fill,
        backup=ns.backup,
        lrc_offset=ns.lrc_offset,
    )


if __name__ == "__main__":
    main()
