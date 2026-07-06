import time
import threading
import requests

import musicbrainzngs
import customtkinter as ctk

from tkinter import filedialog
from datetime import datetime

from load_music import load_music
from music_tag import *
from music_fetcher import MusicFetcher

from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC, Picture
from mutagen.id3 import USLT, APIC
from mutagen.mp3 import MP3

from PIL import Image
from io import BytesIO

BASE_URL = "http://localhost:8080/api/v1/music"
__log = None

musicbrainzngs.set_useragent("MusicClassifier", "1.0")

import base64
import requests

import base64
import requests


def get_kugou_lyrics(song_name):
    r = requests.get(
        "http://mobilecdn.kugou.com/api/v3/search/song",
        params={
            "format": "json",
            "keyword": song_name,
            "page": 1,
            "pagesize": 1
        }
    )

    song = r.json()["data"]["info"][0]

    hash_value = song["hash"]
    duration = song["duration"] * 1000

    lyric_search = requests.get(
        "http://lyrics.kugou.com/search",
        params={
            "ver": 1,
            "man": "yes",
            "client": "pc",
            "hash": hash_value,
            "duration": duration
        }
    ).json()

    candidate = lyric_search["candidates"][0]

    lyric = requests.get(
        "http://lyrics.kugou.com/download",
        params={
            "ver": 1,
            "client": "pc",
            "id": candidate["id"],
            "accesskey": candidate["accesskey"],
            "fmt": "lrc",
            "charset": "utf8"
        }
    ).json()

    return base64.b64decode(
        lyric["content"]
    ).decode(
        "utf-8",
        errors="ignore"
    )


def get_publish_date_brainz(song, artist):
    result = musicbrainzngs.search_recordings(
        recording=song,
        artist=artist,
        limit=1
    )

    if not result["recording-list"]:
        return None

    recording_id = result["recording-list"][0]["id"]

    data = musicbrainzngs.get_recording_by_id(
        recording_id,
        includes=["releases"]
    )

    dates = []

    for release in data["recording"]["release-list"]:
        date = release.get("date")

        if date:
            dates.append(date)

    return min(dates) if dates else None

HEADERS = {
    "Referer": "http://music.163.com",
    "User-Agent": "Mozilla/5.0"
}

def get_year_from_netease(title, artist):
    keyword = f"{title} {artist}".strip()
    try:
        # 1️⃣ 搜索歌曲
        r = requests.get(
            "http://music.163.com/api/search/get",
            params={
                "s": keyword,
                "type": 1,
                "limit": 1
            },
            headers=HEADERS,
            timeout=5
        )

        data = r.json()
        song_id = data["result"]["songs"][0]["id"]

        # 2️⃣ 获取歌曲详情
        r2 = requests.get(
            "http://music.163.com/api/song/detail",
            params={"ids": f"[{song_id}]"},
            headers=HEADERS,
            timeout=5
        )

        songs = r.json()["result"]["songs"]

        best_year = ""

        for song in songs:
            pt = song["album"].get("publishTime", 0)
            if pt:
                year = datetime.fromtimestamp(pt / 1000).strftime("%Y-%m-%d")
                best_year = year
                break

        return best_year

    except:
        pass

    return ''

def fetch_song_meta(title, artist="", plat="kugou", date_en = 1):
  
    keyword = f"{title} {artist}".strip()
    
    brainz = MusicFetcher()
    lyric = ""
    year = ""
    
    if plat == "brainz":
        s = brainz.build_song(title, artist)
        year = s.get("year")
        lyric = s.get("lyrics")
        if lyric == "":
            __log("⚠️ 未获取到歌词，kugou搜索")
            lyric = get_kugou_lyrics(keyword)
        s["cover"] = s.get("cover_url")
    else:
        r = requests.get(
            f"{BASE_URL}/search",
            params={
                "keyword": keyword,
                "page": 1,
                "size": 1
            },
            timeout=5,
            proxies={"http": None, "https": None},
        )

        data = r.json().get("data", [])

        songs = data.get("songs", [])
        if not songs and isinstance(data.get("data"), dict):
            songs = data["data"].get("songs", [])

        if not songs:
            return None
        
        s = {}

        for song in songs:
            if song["source"] == plat:
                if song["name"] in title and song["artist"] in artist:
                    s = song
                    break
        
        if s == {}:
            __log("⚠️ 对应平台未获取到信息，全平台搜索")
            for song in songs:
                if song["name"] in title and song["artist"] in artist:
                    s = song
                    break
        
        if s == {}: 
            return None
        
        s["cover"] = s.get("cover").replace("240/","")
        
        song_id = s.get("id")
        # platform = s.get("platform", "qq")

        time.sleep(0.5)

        lr = requests.get(
            f"{BASE_URL}/lyric",
            params={
                "id": song_id,
                "source": plat,
            },
            timeout=5,
        )

        lyric_data = lr.json()
        if lyric_data.get("code") != 200:
            lyric =  ""
        else:
            lyric = lyric_data["data"].get("lyric", "")
            
        if date_en:
            year = get_year_from_netease(s.get("name", title), s.get("artist", artist))
        print(year)
    
    return {
        "title": "".join(s.get("name", title)),
        "artist": "".join(s.get("artist", artist)),
        "album": "".join(s.get("album", "")),
        "cover": s.get("cover"),
        "year": "".join(year),
        "lyric": lyric,
    }



def download_cover(url):
    if not url:
        return None

    # try:
    return requests.get(url, timeout=15).content
    # except Exception:
    #     return None

def make_flac_picture(img, max_size: int = 800) -> Picture:
    """把任意图片转成 FLAC 能接受的 Picture 对象"""
    pic = Picture()
    pic.type = 3               # 封面（Front Cover）
    pic.desc = "Front Cover"
 
    # 打开并压缩图片
    with Image.open(img) as im:
        im = im.convert("RGB")
        if max(im.size) > max_size:
            im.thumbnail((max_size, max_size), Image.LANCZOS)
 
        import io
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=92)
        pic.data = buf.getvalue()
        pic.mime = "image/jpeg"
        pic.width, pic.height = im.size
 
    return pic

def rewrite_songs(overwrite, path, meta, type, pixel=800):

    if type == "flac":
        audio = FLAC(path)
    elif type == "mp3":
        audio = EasyID3(path)

    # 基础数据
    if overwrite or not audio.get("title"):
        if meta["title"] != '':
            __log(f"  -> 重写 title: {meta["title"]}")
            audio["title"] = meta["title"]

    if overwrite or not audio.get("artist"):
        if meta["artist"] != '':
            __log(f"  -> 重写 artist: {meta["artist"]}")
            audio["artist"] = meta["artist"]

    if overwrite or not audio.get("album"):
        if meta["album"] != '':
            __log(f"  -> 重写 album: {meta["album"]}")
            audio["album"] = meta["album"]

    if overwrite or not audio.get("date"):
        if meta["year"] != '':
            __log(f"  -> 重写 date: {meta["year"]}")
            audio["date"] = meta["year"]
    
    audio.save()
    if type == "mp3":
        audio = MP3(path)

    #歌词
    if meta.get("lyric") != "":
        if type == "flac":
            if overwrite or not audio.get("lyrics"):
                __log(f"  -> 重写 lyric")
                audio["lyrics"] = meta["lyric"]
        elif type == "mp3":
            if overwrite or not audio.tags.getall("USLT"):
                audio.tags.delall("USLT")
                __log(f"  -> 重写 lyric")
                audio.tags.add(USLT(encoding=3, text=meta["lyric"]))
    #封面
    if meta.get("cover") != "":
        cover = download_cover(meta.get("cover"))
        if cover:
            if type == "flac":
                if overwrite or not audio.pictures:
                    __log(f"  -> 加入封面图片")
                    pic = make_flac_picture(BytesIO(cover), max_size=pixel)
                    audio.add_picture(pic)
            elif type == "mp3":
                if cover:
                    if overwrite or not audio.tags.getall("APIC"):
                        __log(f"  -> 加入封面图片")
                        audio.tags.add(APIC(
                            encoding=3,
                            mime="image/jpeg",
                            type=3,
                            desc="Cover",
                            data=make_flac_picture(BytesIO(cover), max_size=pixel).data,
                        ))
    audio.save()
    return audio

def write_song_metadata(song, meta, pixel=800, overwrite=False):
    path = song["path"]

    # try:
    if path.lower().endswith(".flac"):
        audio = rewrite_songs(overwrite, path, meta, "flac", pixel)
    elif path.lower().endswith(".mp3"):
        audio = rewrite_songs(overwrite, path, meta, "mp3", pixel)
    else:
        return f"不支持的文件类型: {path}"

    return True

    # except Exception as e:
    #     return str(e)
    
def create_metadata_page(parent):
    global __log
    
    frame = ctk.CTkFrame(parent)

    path_frame = ctk.CTkFrame(frame)
    path_frame.pack(fill="x", padx=20, pady=10)

    path_entry = ctk.CTkEntry(
        path_frame,
        placeholder_text="选择音乐目录"
    )
    path_entry.pack(side="left", fill="x", expand=True, padx=10, pady=10)

    def select_folder():
        folder = filedialog.askdirectory()
        if folder:
            path_entry.delete(0, "end")
            path_entry.insert(0, folder)
    
    ctk.CTkButton(
        path_frame,
        text="浏览",
        width=80,
        command=select_folder
    ).pack(side="right", padx=10)

    option_frame = ctk.CTkFrame(frame)
    option_frame.pack(fill="x", padx=20, pady=10)

    # 是否覆盖
    overwrite_var = ctk.BooleanVar(value=False)

    ctk.CTkCheckBox(
        option_frame,
        text="覆盖原始元数据",
        variable=overwrite_var
    ).pack(side="left", padx=3, pady=5)

    # 平台选择
    # platform_frame = ctk.CTkFrame(option_frame)
    # platform_frame.pack(fill="x", padx=10, pady=5)

    ctk.CTkLabel(
        option_frame,
        text="| 元数据来源平台"
    ).pack(side="left", padx=3)

    platform_var = ctk.StringVar(value="brainz")

    platform_menu = ctk.CTkOptionMenu(
        option_frame,
        values=["brainz"] + MUSIC_PLATFARM[1:],
        variable=platform_var
    )

    platform_menu.pack(side="left", padx=3)

    ctk.CTkLabel(
        option_frame,
        text="| 图像最大分辨率: "
    ).pack(side="left", padx=3)

    pixel_limit = ctk.CTkEntry(option_frame)
    pixel_limit.insert(0, "800")
    pixel_limit.pack(side="right")

    status_label = ctk.CTkLabel(frame, text="状态：等待开始")
    status_label.pack(pady=5)

    log_box = ctk.CTkTextbox(frame)
    log_box.pack(fill="both", expand=True, padx=20, pady=10)

    def log(msg):
        frame.after(0, lambda: (
            log_box.insert("end", msg + "\n"),
            log_box.see("end")
        ))
    __log = log

    def select_folder():
        folder = filedialog.askdirectory()
        if folder:
            path_entry.delete(0, "end")
            path_entry.insert(0, folder)

    def start_task():
        threading.Thread(target=worker, daemon=True).start()

    def worker():
        folder = path_entry.get().strip()

        if not folder:
            log("❌ 请先选择目录")
            return
        
        btn.configure(state="disabled")

        overwrite = overwrite_var.get()
        plat = platform_var.get()
        pixel = int(pixel_limit.get())

        log("\n🔍 扫描音乐库...")
        songs = load_music(folder)

        log(f"✅ 共发现 {len(songs)} 首歌曲")

        total = len(songs)
        song_cnt = 0

        for index, song in enumerate(songs, start=1):


            frame.after(
                0,
                lambda i=index: status_label.configure(
                    text=f"状态：处理中 {i}/{total}"
                )
            )

            log(f"\n🎵 {song['title']} - {song['artist']}")

            info_list = ["title",
                        "artist",
                        "year",
                        "lyric",
                        "album",
                        "cover"]
            all_info = True

            for info in info_list:
                if song[info] in [False, '', [], {}, -1]:
                    all_info = False
                    break

            if all_info:
                log("⚠️  跳过-歌曲信息完整")
                continue

            meta = fetch_song_meta(song['title'], song['artist'], plat, date_en = 0 if song["year"] else 1)

            if not meta:
                log("⚠️ 未获取到网络信息")
                continue

            result = write_song_metadata(
                song,
                meta,
                pixel,
                overwrite=overwrite
            )

            if result is True:
                log("✅ 更新成功")
            else:
                log(f"❌ 更新失败: {result}")

            song_cnt += 1
            time.sleep(1)
            if song_cnt%100 == 0:
                log(f"⏳ 已网络处理 {song_cnt} 首歌曲，请等待10秒~")
                time.sleep(10)

        frame.after(
            0,
            lambda: status_label.configure(text="状态：完成 ✅")
        )

        log("🎉 所有歌曲处理完成")
        btn.configure(state="enabled")

    btn = ctk.CTkButton(
        frame,
        text="🚀 开始获取",
        height=40,
        command=start_task
    )
    btn.pack(pady=10)

    return frame


# class MetadataEnhancerApp(ctk.CTk):

#     def __init__(self):
#         super().__init__()

#         self.title("🎵 歌曲元数据增强")
#         self.geometry("900x700")

#         ctk.CTkLabel(
#             self,
#             text="🎵 本地音乐元数据增强",
#             font=ctk.CTkFont(size=24, weight="bold")
#         ).pack(pady=10)

#         path_frame = ctk.CTkFrame(self)
#         path_frame.pack(fill="x", padx=20, pady=10)

#         self.path_entry = ctk.CTkEntry(
#             path_frame,
#             placeholder_text="选择音乐目录"
#         )
#         self.path_entry.pack(side="left", fill="x", expand=True, padx=10, pady=10)

#         ctk.CTkButton(
#             path_frame,
#             text="浏览",
#             command=self.select_folder
#         ).pack(side="right", padx=10)

#         option_frame = ctk.CTkFrame(self)
#         option_frame.pack(fill="x", padx=20)

#         self.overwrite_var = ctk.BooleanVar(value=False)

#         ctk.CTkCheckBox(
#             option_frame,
#             text="覆盖原始元数据",
#             variable=self.overwrite_var
#         ).pack(anchor="w", padx=10, pady=10)

#         self.status_label = ctk.CTkLabel(self, text="状态：等待开始")
#         self.status_label.pack(pady=5)

#         self.log_box = ctk.CTkTextbox(self)
#         self.log_box.pack(fill="both", expand=True, padx=20, pady=10)

#         ctk.CTkButton(
#             self,
#             text="🚀 开始增强",
#             height=40,
#             command=self.start_task
#         ).pack(pady=10)

#     def log(self, msg):
#         self.after(0, lambda: (
#             self.log_box.insert("end", msg + "\n"),
#             self.log_box.see("end")
#         ))

#     def select_folder(self):
#         folder = filedialog.askdirectory()
#         if folder:
#             self.path_entry.delete(0, "end")
#             self.path_entry.insert(0, folder)

#     def start_task(self):
#         threading.Thread(target=self.worker, daemon=True).start()

#     def worker(self):
#         folder = self.path_entry.get().strip()

#         if not folder:
#             self.log("❌ 请先选择目录")
#             return

#         overwrite = self.overwrite_var.get()

#         self.log("🔍 扫描音乐库...")
#         songs = load_music(folder)

#         self.log(f"✅ 共发现 {len(songs)} 首歌曲")

#         total = len(songs)

#         for index, song in enumerate(songs, start=1):

#             self.after(
#                 0,
#                 lambda i=index: self.status_label.configure(
#                     text=f"状态：处理中 {i}/{total}"
#                 )
#             )

#             self.log(f"🎵 {song['title']} - {song['artist']}")

#             meta = fetch_song_meta(song['title'], song['artist'])

#             if not meta:
#                 self.log("⚠️ 未获取到网络信息")
#                 continue

#             result = write_song_metadata(
#                 song,
#                 meta,
#                 overwrite=overwrite
#             )

#             if result is True:
#                 self.log("✅ 更新成功")
#             else:
#                 self.log(f"❌ 更新失败: {result}")

#         self.after(
#             0,
#             lambda: self.status_label.configure(text="状态：完成 ✅")
#         )

#         self.log("🎉 所有歌曲处理完成")


if __name__ == "__main__":
    # ctk.set_appearance_mode("dark")
    # ctk.set_default_color_theme("green")

    # app = MetadataEnhancerApp()
    # app.mainloop()

    # ✅ 全局主题
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")

    # ================= 窗口 =================
    app = ctk.CTk()
    app.title("AI Music Classifier")
    app.geometry("600x800")

    # ================= 标题 =================
    title = ctk.CTkLabel(
        app,
        text="🎧 Net Metadate Page",
        font=ctk.CTkFont(size=20, weight="bold")
    )
    title.pack(pady=10)
    
    net_frame = create_metadata_page(app)
    net_frame.pack(fill="both", expand=True)

    from start_service import *
    import threading

    bottom_label = ctk.CTkLabel(
    app,
    text="初始化中..."
    )

    bottom_label.pack(side="right")

    threading.Thread(
        target=lambda: start_go_music_api(
            lambda msg: app.after(0, __log, msg + "\n"), bottom_label),
        daemon=True
    ).start()

    app.mainloop()
