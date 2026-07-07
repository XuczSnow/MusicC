import os
import re

from script.music_tag import *

from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

from pathlib import Path

songs = []
global_path = ""

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

pattern = re.compile(r'[^a-zA-Z\u4e00-\u9fff\s ]')
def clean(text):
    return pattern.sub('', text)

def split_path(path):
    path_split = path.split('/')[-1].split('\\')[-1].split(' - ')
    # print(path_split)
    artist = path_split[0]
    try:
        title = path_split[1].split('.')[0]
    except:
        title = ''
    return [title, artist]

def get_song_info(path:str, type:str):
    lyric = ''
    try:
        if type == "flac":
            audio = FLAC(path)
        elif type == "mp3":
            audio = EasyID3(path)
        title = audio.get("title", [""])[0]
        artist = audio.get("artist", [""])[0]
        album = audio.get("album", ["未知专辑"])[0]
        if not artist:
            artist = audio.get("albumartist", [""])[0]
        year = audio.get("date", [''])[0]

        if type == "flac":
            duration = int(audio.info.length)
            lyric = clean(str(audio.get("lyrics", [""])[0]))
            cover = True if audio.pictures else False
        elif type == "mp3":
            audio = MP3(path)
            duration = int(audio.info.length)
            if audio.tags:
                for tag in audio.tags:
                    if tag.startswith("USLT"):
                        lyric = clean(str(audio.tags[tag]))
                        break
            cover = True if audio.tags.getall("APIC") else False
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
        "path": Path(path).as_posix(),
        "lyric": lyric,
        "duration": duration,
        "album": album,
        "cover": cover,
        "tags": [],
        "score": 0
    }

def load_music(folder):
    global songs, global_path

    if songs and global_path == folder:
        return songs
    else:
        songs = []

    global_path = resource_path(folder)

    unique = {}
    song_idx = 0

    for root, _, files in os.walk(global_path):

        for f in files:

            if f.lower().endswith((".mp3", ".flac")):

                path = os.path.join(root, f)

                if path.lower().endswith(".flac"):
                    song = get_song_info(path, "flac")
                else:
                    song = get_song_info(path, "mp3")
                
                key = (
                    song["title"].strip().lower(),
                    song["artist"].strip().lower()
                )

                if key in unique:
                    print(f"歌曲重复：{song}")
                    print(f"已存在：{songs[unique[key]]}")
                    if path.lower().endswith(".flac") and songs[unique[key]]['path'].lower().endswith(".mp3"):
                        print("优先选取flac文件")
                        songs[unique[key]] = song
                    continue
                
                unique[key] = song_idx
                songs.append(song)
                song_idx += 1

    return songs