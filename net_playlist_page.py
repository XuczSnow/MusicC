# net_playlist_page.py
# ✅ 多平台歌单页面 + 本地匹配

import customtkinter as ctk
import requests

from tkinter import filedialog

from music_tag import *
from load_music import *

# ================= 工具 =================
def normalize(text):
    return text.replace(" ", "").lower()


def build_local_index(songs):
    index = {}
    for s in songs:
        key = normalize(s["title"] + s["artist"])
        index[key] = s
    return index


def match_local(online, index):
    result = []
    for s in online:
        key = normalize(s["title"] + s["artist"])
        if key in index:
            result.append(index[key])
    return result


# ================= 平台实现 =================
def get_netease_multi(keyword, list_limit=30, platform="all", log=None):

    BASE = "http://localhost:8080/api/v1"

    result = []

    # ===== 1️⃣ 搜索歌单 =====
    try:
        r = requests.get(
            f"{BASE}/music/search",
            params={
                "q": keyword,
                "type": "playlist"
            }
        )

        data = r.json().get("data",[])
        playlists = data.get("playlists", [])

    except Exception:
        if log:
            log("❌ 搜索失败\n")
        return []

    # ===== 2️⃣ 遍历歌单 =====
    list_count = 0
    for p in playlists:

        pid = p["id"]
        pname = p["name"]
        source = p["source"]

        if source != platform:
            continue

        list_count += 1
        if list_count == list_limit:
            break

        if log:
            log(f"\n🎧 {pname}\n")

        try:
            r2 = requests.get(
                f"{BASE}/playlist/detail",
                params={
                    "id": pid,
                    "source": source
                }
            )

            detail = r2.json()

            songs_raw = detail.get("data", [])

            songs = [
                {
                    "title": s.get("name", ""),
                    "artist": s.get("artist", ""),
                    "album": s.get("album", "")
                }
                for s in songs_raw
            ]


            if log:
                log(f"✅ 获取: {len(songs)} 首\n")

            result.append({
                "name": pname,
                "source": source,
                "songs": songs
            })

        except Exception as e:
            if log:
                log(f"❌ 获取失败: {e}\n")

    return result

# ================= 保存为 m3u =================

def save_playlist(name, songs):

    import os
    os.makedirs("AI分类歌单", exist_ok=True)

    file_path = f"AI分类歌单/{name}.m3u"

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
            f.write(s["path"] + "\n")

def generate_netease_multi(keyword, songs, limit, platform = "all", min_limit=2, log=None):

    playlists = get_netease_multi(keyword, list_limit=limit, platform=platform, log=log)

    index = build_local_index(songs)

    for p in playlists:

        pname = p["name"]
        source = p["source"]

        if log:
            log(f"\n📀 处理歌单: {pname}\n")

        matched = match_local(p["songs"], index)

        if len(matched) < min_limit:
            if len(matched) == 0:
                log(f"⚠️ 没有匹配到歌曲, 跳过\n")
            else:
                log(f"⚠️ 匹配太少 ({len(matched)})，跳过\n")
            continue

        safe_name = pname.replace("/", "_")

        save_playlist(f"PL_{source}_{safe_name}", matched)

        if log:
            log(f"✅ 匹配: {len(matched)} / {len(p['songs'])}\n")

# ================= 页面组件 =================

def create_net_page(parent):

    # ===== 根 =====
    main_frame = ctk.CTkFrame(parent)
    main_frame.pack(fill="both", expand=True)

    # ================= 路径选择 =================
    frame_path = ctk.CTkFrame(main_frame)
    frame_path.pack(pady=10, padx=20, fill="x")

    path_entry = ctk.CTkEntry(frame_path, placeholder_text="选择音乐目录...")
    path_entry.pack(side="left", fill="x", expand=True, padx=10, pady=10)

    def select_folder():
        folder = filedialog.askdirectory()
        if folder:
            path_entry.delete(0, "end")
            path_entry.insert(0, folder)

    btn_folder = ctk.CTkButton(
        frame_path,
        text="浏览",
        width=80,
        command=select_folder
    )
    btn_folder.pack(side="right", padx=10)

    # ================= 参数区域 =================
    # ----- 平台选择 -----
    platform_ctrl = ctk.CTkFrame(main_frame)
    platform_ctrl.pack(pady=10, padx=20, fill="x")
    platform_var = ctk.StringVar(value="all")

    platform_menu = ctk.CTkOptionMenu(
        platform_ctrl,
        values=["all", "netease",
                "qq",
                "kugou",
                "kuwo",
                "migu",
                "qianqian",
                "soda",
                "fivesing",
                "jamendo",
                "joox"],
        variable=platform_var
    )
    platform_menu.pack(side="left", fill="x", expand=True)

    # ----- 数量 -----
    frame_net = ctk.CTkFrame(main_frame)
    frame_net.pack(pady=10, padx=20, fill="x")

    ctk.CTkLabel(frame_net, text="网络搜索数量").pack(side="left")
    
    entry_limit = ctk.CTkEntry(frame_net)
    entry_limit.insert(0, "30")
    entry_limit.pack(side="right")

    # ----- 最小数量 -----
    frame_min = ctk.CTkFrame(main_frame)
    frame_min.pack(pady=10, padx=20, fill="x")

    ctk.CTkLabel(frame_min, text="歌单最小数量").pack(side="left")
    
    min_limit = ctk.CTkEntry(frame_min)
    min_limit.insert(0, "2")
    min_limit.pack(side="right")

    # ----- 模式选择 -----
    mode_ctrl = ctk.CTkFrame(main_frame)
    mode_ctrl.pack(pady=10, padx=20, fill="x")
    mode_var = ctk.StringVar(value="preset")

    # radio_frame = ctk.CTkFrame(mode_ctrl)
    # radio_frame.pack()

    ctk.CTkRadioButton(
        mode_ctrl,
        text="模板模式",
        variable=mode_var,
        value="preset",
        command=lambda: update_mode()
    ).pack(side="left", padx=10)

    ctk.CTkRadioButton(
        mode_ctrl,
        text="自定义关键词",
        variable=mode_var,
        value="custom",
        command=lambda: update_mode()
    ).pack(side="left", padx=10)

    # ----- 字典选择 -----
    control_container = ctk.CTkFrame(mode_ctrl)
    control_container.pack(fill="x", pady=10, expand=True)

    preset_frame = ctk.CTkFrame(control_container)
    preset_frame.pack(fill="x", expand=True)

    group_var = ctk.StringVar(value=list(TAG_DEFINITIONS.keys())[0])
    tag_var = ctk.StringVar()

    group_menu = ctk.CTkOptionMenu(
        preset_frame,
        values=list(TAG_DEFINITIONS.keys()),
        variable=group_var,
        command=lambda _: update_tags()
    )
    group_menu.pack(side="left", padx=5, fill="x")

    tag_menu = ctk.CTkOptionMenu(
        preset_frame,
        values=[],
        variable=tag_var
    )
    tag_menu.pack(side="left", padx=5, fill="x")

    def update_tags():

        group = group_var.get()
        tags = list(TAG_DEFINITIONS[group].keys())

        # ✅ 加入 ALL
        tags = ["ALL"] + tags

        tag_menu.configure(values=tags)

        if tags:
            tag_var.set(tags[0])
    
    # ----- 输入选择 -----
    custom_frame = ctk.CTkFrame(control_container)
    custom_frame.pack(fill="x", pady=10, expand=True)

    entry_keyword = ctk.CTkEntry(
        custom_frame,
        placeholder_text="输入关键词（例如：失恋歌 / 周杰伦）"
    )
    entry_keyword.pack(fill="x", padx=5)

    def update_mode():

        if mode_var.get() == "preset":
            preset_frame.pack(fill="x", expand=True)
            custom_frame.pack_forget()

        else:
            custom_frame.pack(fill="x", expand=True)
            preset_frame.pack_forget()

    update_mode()
    update_tags()

    # ================= 日志区域 =================
    log_frame = ctk.CTkFrame(main_frame)
    log_frame.pack(padx=20, pady=10, fill="both", expand=True)

    log_box = ctk.CTkTextbox(log_frame, height=200)
    log_box.pack(fill="both", expand=True, padx=10, pady=10)

    # ===== 下：按钮区（固定🔥）=====
    bottom_frame = ctk.CTkFrame(main_frame)
    bottom_frame.pack(pady=10, padx=20, fill="x")

    def log(*args):
        if len(args) == 1:
            msg = args[0]
        else:
            msg = args[0]

        log_box.insert("end", msg)
        log_box.see("end")

    # ----- 按钮 -----
    def run():
                
        folder = path_entry.get()

        if not folder:
            log("❌ 请先选择目录\n")
            return
    
        import threading

        def task():

            songs = load_music(path_entry.get())
            
            limit = int(entry_limit.get())
            min_hj = int(min_limit.get())

            platform = platform_var.get()

            # ================= 模板模式 =================
            if mode_var.get() == "preset":

                group = group_var.get()
                tag = tag_var.get()

                if tag == "ALL":

                    log(f"\n📂 批量生成: {group}\n")

                    for t, keywords in TAG_DEFINITIONS[group].items():

                        log(f"\n👉 {t}\n")

                        generate_netease_multi(
                            keyword=keywords,
                            songs=songs,
                            limit=limit,
                            min_limit = min_hj,
                            platform = platform,
                            log=log
                        )

                else:

                    keywords = TAG_DEFINITIONS[group][tag]

                    log(f"\n🎯 {group} - {tag}\n")
                    print(keywords)

                    generate_netease_multi(
                        keyword=keywords,
                        songs=songs,
                        limit=limit,
                        min_limit = min_hj,
                        platform = platform,
                        log=log
                    )

            # ================= 自定义关键词 =================
            else:

                keyword = entry_keyword.get().strip()

                if not keyword:
                    log("❌ 请输入关键词\n")
                    return

                log(f"\n🔍 自定义搜索: {keyword}\n")

                generate_netease_multi(
                    keyword=keyword,
                    songs=songs,
                    limit=limit,
                    min_limit = min_hj,
                    platform = platform,
                    log=log
                )

        threading.Thread(target=task).start()

    btn = ctk.CTkButton(bottom_frame, text="生成歌单", command=run)
    btn.pack(pady=10)

    return main_frame

if __name__ == "__main__":
    get_netease_multi("test")