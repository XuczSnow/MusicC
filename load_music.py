import os
import re
from music_tag import *

from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3


pattern = re.compile(r'[^a-zA-Z\u4e00-\u9fff\s ]')

def sanitize_filename(name):
    # 替换非法字符
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'[\x00-\x1f]', '', name)  # 删除控制字符

    # 去掉首尾空格和点
    name = name.strip(' .')

    # 限制长度
    name = name[:100]

    return name

def clean(text):
    return pattern.sub('', text)

def split_path(path):
    title = os.path.splitext(path)[0].split(" ")[0]
    try:
        artist = os.path.splitext(path)[0].split(" ")[2]
    except:
        artist = ''
    return [title, artist]

def get_song_info(path:str, type:str):

    try:
        if type == "flac":
            audio = FLAC(path)
        else:
            audio = EasyID3(path)
        title = audio.get("title", [""])[0]
        artist = audio.get("artist", [""])[0]
        duration = int(audio.info.length)
        album = audio.get("album", ["未知专辑"])[0]
        if not artist:
            artist = audio.get("albumartist", [""])[0]
        year = audio.get("date", [''])[0]

        if type == "flac":
            lyric = clean(str(audio.get("lyrics", [""])[0]))
            cover = True if audio.pictures else False
        elif type == "mp3":
            audio = MP3(path)
            if audio.tags:
                for tag in audio.tags:
                    if tag.startswith("USLT"):
                        lyric = clean(str(audio.tags[tag]))
                        break
            cover = True if audio.getall("APIC") else False
        res = split_path(path)
        if not title:
            title = res[0]
        if not artist:
            artist = res[1]
    except:
        title = ''
        artist = ''
        duration = -1
        album = ''
        lyric = ''
        year = 0
        cover = False

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

def load_music(folder):

    songs = []
    folder = resource_path(folder)

    for root, _, files in os.walk(folder):

        for f in files:

            if f.lower().endswith((".mp3", ".flac", ".m4a")):

                path = os.path.join(root, f)

                if path.lower().endswith(".flac"):
                    song = get_song_info(path, "flac")
                else:
                    song = get_song_info(path, "mp3")
                
                # print(song)
                songs.append(song)

    return songs