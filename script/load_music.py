import os
import re
import regex

from script.music_tag import *
from script.dirty_data import *
from script.logger import AppLogger

from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

from pathlib import Path

songs = []
global_path = ""
logger = AppLogger()


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def set_logger(func):
    global logger
    logger = func
    
# chinese_convert.py
from hanziconv import HanziConv

def to_simplified(text):

    if not text:
        return ""

    return HanziConv.toSimplified(text)


def to_traditional(text):

    if not text:
        return ""

    return HanziConv.toTraditional(text)

def split_artists(text):

    if not text:
        return []

    text = text.strip()

    artists = re.split(
        r'\s*(?:;|,|/|&|feat\.?|ft\.?| x )\s*',
        text,
        flags=re.IGNORECASE
    )

    artists = [
        a.strip()
        for a in artists
        if a.strip()
    ]

    # 如果没有分隔符
    # 且全是中文
    # 连续两个以上空格视为分隔
    if len(artists) == 1:

        artists = re.split(
            r'\s{2,}',
            artists[0]
        )

        artists = [
            a.strip()
            for a in artists
            if a.strip()
        ]

    return artists

def keep_newest(path_a, payh_b):

    t1 = os.path.getmtime(path_a)
    t2 = os.path.getmtime(payh_b)

    return t1 > t2

def sanitize_filename(name):
    # 替换非法字符
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'[\x00-\x1f]', '', name)  # 删除控制字符

    # 去掉首尾空格和点
    name = name.strip(' .')

    # 限制长度
    name = name[:100]

    return name

def clean_text(text: str, keep_numbers: bool = False) -> str:
    """
    保留所有语言文字（中文、英文、日文、韩文、俄文、阿拉伯文等）。
    其它字符替换为空格，并压缩连续空格。

    Args:
        text: 输入文本
        keep_numbers: 是否保留数字

    Returns:
        清洗后的文本
    """
    if keep_numbers:
        pattern = r"[^\p{Letter}\p{Number}\s]"
    else:
        pattern = r"[^\p{Letter}\s]"

    text = regex.sub(pattern, "", text)
    text = regex.sub(r"\s+", " ", text).strip()

    return text

# pattern = re.compile(r'[^a-zA-Z\u4e00-\u9fff\s ]')
# def clean(text):
#     # 非中英文替换
#     return pattern.sub('', text)

def extract_song_artist(filepath):
    # 提取文件名（不含扩展名）
    filename = Path(filepath).stem

    # 去掉前缀序号
    filename = re.sub(r'^\d+\s*[\.\-_、]+\s*', '', filename)

    # 去掉括号内容
    filename = re.sub(r'[\(\（].*?[\)\）]', '', filename)

    # 去掉常见版本标识
    filename = re.sub(
        r'\s*-\s*(live|remix|demo|伴奏|纯音乐|现场版)$',
        '',
        filename,
        flags=re.IGNORECASE
    )

    parts = [x.strip() for x in filename.split("-")]

    if len(parts) == 1:
        return {
            "song": parts[0],
            "artist": parts[0]
        }

    if len(parts) >= 2:
        return {
            "song": f"{parts[0]} {parts[1]}",
            "artist": f"{parts[0]} {parts[1]}"
        }

    return {
        "song": filename,
        "artist": filename
    }

def get_song_info(path:str, type:str):
    lyric = ''
    try:
        if type == "flac":
            audio = FLAC(path)
        elif type == "mp3":
            audio = EasyID3(path)
        title = audio.get("title", [""])[0]
        artist = ""
        for ar in audio.get("artist", [""]):
            artist += " ".join(split_artists(clean_text(ar, keep_numbers=True))) + " "
        artist = artist[:-1]
        # print(artist, audio.get("albumartist", [""]))
        album = audio.get("album", [""])[0]
        if not artist:
            artist = audio.get("albumartist", [""])[0].replace(" / ", " ")
        year = audio.get("date", [''])[0]
        
        #清除非法字符
        artist = to_simplified(artist)
        title = to_simplified(sanitize_filename(title))
        album = to_simplified(sanitize_filename(album))

        if type == "flac":
            duration = int(audio.info.length)
            lyric = clean_text(str(audio.get("lyrics", [""])[0]))
            cover = True if audio.pictures else False
        elif type == "mp3":
            audio = MP3(path)
            duration = int(audio.info.length)
            if audio.tags:
                for tag in audio.tags:
                    if tag.startswith("USLT"):
                        lyric = clean_text(str(audio.tags[tag]))
                        break
            cover = True if audio.tags.getall("APIC") else False
            
        # 检查是否有脏数据
        if contain_all_dirtydata(title, DIRTY_METADATA_RULES) or len(title) > 50:
            logger.warning(f"title: {title} 为脏数据，忽略")
            title = ""
        if contain_all_dirtydata(artist, DIRTY_METADATA_RULES) or len(artist) > 50:
            logger.warning(f"artist: {artist} 为脏数据，忽略")
            artist = ""
        if contain_all_dirtydata(album, DIRTY_METADATA_RULES) or len(album) > 50:
            logger.warning(f"album: {album} 为脏数据，忽略")
            album = ""
        if is_dirty_lyric(lyric):
            logger.warning(f"lyric: {lyric} 为脏数据，忽略")
            lyric = ""
        
        # 如果获取不到，从文件名获取
        res = extract_song_artist(path)
        if title.strip() == "":
            title = res["song"]
        if artist.strip() == "":
            artist = res["artist"]
        
        #如果没有获取到title，返回失败   
        if title.strip() == "":
            logger.error(f"读取 {path} 失败，获取不到歌曲名，请检查文件")
            return None
            
    except Exception as e:
        logger.exception(e)
        logger.error(f"读取 {path} 失败，出现未知错误，请检查log")
        return None
        
    return {
        "title": title,
        "artist": artist,
        "year": year,
        "path": path,
        "lyric": lyric,
        "duration": duration,
        "album": album,
        "cover": cover,
        "tags": [],
        "score": 0
    }

def load_music(folder, log = None, reload = False):
    global songs, global_path, logger

    logger = log if log else logger
    path = resource_path(folder)
    if songs == [] or global_path != path or reload:
        songs = []
    else:
        return songs

    global_path = path

    unique = {}
    song_idx = 0

    for root, _, files in os.walk(global_path):

        for f in files:

            if f.lower().endswith((".mp3", ".flac")):

                path = Path(os.path.join(root, f)).as_posix()
                
                if path.lower().endswith(".flac"):
                    song = get_song_info(path, "flac")
                else:
                    song = get_song_info(path, "mp3")
                
                if song == None:
                    continue
                
                key = (
                    song["title"].strip().lower(),
                    song["artist"].strip().lower()
                )

                if key in unique:
                    logger.warning(f"歌曲重复：{song['artist']} - {song['title']}")
                    print(f"已存在：{songs[unique[key]]}")
                    if path.lower().endswith(".flac") and songs[unique[key]]['path'].lower().endswith(".mp3"):
                        logger.info("优先选取flac文件")
                        songs[unique[key]] = song
                    continue
                
                unique[key] = song_idx
                songs.append(song)
                song_idx += 1

    return songs

if __name__ == "__main__":
    load_music("../Music")