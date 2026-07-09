import webbrowser
import customtkinter as ctk

from script.load_music import resource_path


VERSION = "v1.0.0"

AUTHOR = "Xucz"

GITHUB_URL = "https://github.com/XuczSnow/MusicC"

RELEASE_URL = f"{GITHUB_URL}/releases"

ISSUE_URL = f"{GITHUB_URL}/issues"

import tkinter.messagebox as msgbox

def open_url(url):

    try:
        ok = webbrowser.open(url)
        print("打开链接")

    except Exception as e:
        print(e)

def create_about_page(parent):

    frame = ctk.CTkFrame(parent)

    # # =====================
    # # 标题
    # # =====================

    # ctk.CTkLabel(
    #     frame,
    #     text="🎵 AI Music Playlist Generator",
    #     font=ctk.CTkFont(
    #         size=24,
    #         weight="bold"
    #     )
    # ).pack(pady=(20, 10))

    # ctk.CTkLabel(
    #     frame,
    #     text=f"Version {VERSION}"
    # ).pack()

    # =====================
    # 软件介绍
    # =====================

    intro = "一个集 本地音乐分类、网络歌单生成、元数据增强、音乐库整理于一体的音乐管理工具。"

    ctk.CTkLabel(
        frame,
        text=intro,
        justify="left"
    ).pack(
        padx=20,
        pady=10
    )

    # =====================
    # 作者
    # =====================

    ctk.CTkLabel(
        frame,
        text=f"👨‍💻 作者：{AUTHOR}"
    ).pack(
        pady=5
    )

    # =====================
    # 下载
    # =====================
    download_frame = ctk.CTkFrame(frame)

    download_frame.pack(
        fill="x",
        padx=20,
        pady=10
    )

    button_frame = ctk.CTkFrame(
        download_frame,
        fg_color="transparent"
    )

    button_frame.pack(pady=10)

    button_frame.grid_columnconfigure(
        (0, 1, 2),
        weight=1
    )

    ctk.CTkButton(
        button_frame,
        text="📦 GitHub主页",
        command=lambda: open_url(GITHUB_URL)
    ).grid(
        row=0,
        column=0,
        padx=10
    )

    ctk.CTkButton(
        button_frame,
        text="🚀 下载最新版本",
        command=lambda: open_url(RELEASE_URL)
    ).grid(
        row=0,
        column=1,
        padx=10
    )

    ctk.CTkButton(
        button_frame,
        text="🐞 提交Issue",
        command=lambda: open_url(ISSUE_URL)
    ).grid(
        row=0,
        column=2,
        padx=10
    )

    # =====================
    # 开源协议
    # =====================

    license_text = """📜 开源协议
本项目采用 Apache License 2.0 开源协议:
https://www.apache.org/licenses/LICENSE-2.0
"""

    ctk.CTkTextbox(
        frame,
        height=120
    )

    license_box = ctk.CTkTextbox(
        frame,
        height=60
    )

    license_box.pack(
        fill="x",
        padx=20,
        pady=10
    )

    license_box.insert(
        "1.0",
        license_text
    )

    # =====================
    # 捐赠
    # =====================

    ctk.CTkLabel(
        frame,
        text="☕ 如果项目对您有帮助，欢迎支持开发"
    ).pack(
        pady=10
    )

    donate_frame = ctk.CTkFrame(frame)

    donate_frame.pack(
        pady=10
    )

    # 微信二维码
    from PIL import Image

    wechat_img = ctk.CTkImage(
        Image.open(
            resource_path("assets/wechat_pay.jpg")
        ),
        size=(180,180)
    )

    ctk.CTkLabel(
        donate_frame,
        image=wechat_img,
        text=""
    ).pack()

    # =====================
    # 鸣谢
    # =====================

    thanks = """
❤️ 特别感谢

• CustomTkinter
• go-music-api
• Mutagen
• SentenceTransformers
• Python Community

"""

    thanks_box = ctk.CTkTextbox(frame)

    thanks_box.pack(
        fill="x",
        padx=20,
        pady=10
    )

    thanks_box.insert(
        "1.0",
        thanks
    )

    return frame