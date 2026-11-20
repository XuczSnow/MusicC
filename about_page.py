import webbrowser
import threading
import customtkinter as ctk

from script.music.load_music import resource_path
from script.common.logger import AppLogger
from script.common.version import SOFTWARE_VERSION, software_version_str, GOMUSIC_RELEASES_URL
from script.common.update_check import check_updates, _read_local_api_version
from script.ui.widget_factory import theme_selector

VERSION = software_version_str()

AUTHOR = "Xucz"

GITHUB_URL = "https://github.com/XuczSnow/MusicC"

RELEASE_URL = f"{GITHUB_URL}/releases"

ISSUE_URL = f"{GITHUB_URL}/issues"

import tkinter.messagebox as msgbox

def open_url(url):

    try:
        webbrowser.open(url)

    except Exception as e:
        AppLogger().error(f"open_url 失败: {e}")

def create_about_page(parent):

    frame = ctk.CTkFrame(parent)

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
    # 主题设置（单行）
    # =====================

    theme_selector(frame)

    # =====================
    # 作者 + 版本（同一行：左作者，右软件/API 版本）
    # =====================

    version_row = ctk.CTkFrame(frame, fg_color="transparent")
    version_row.pack(fill="x", padx=20, pady=5)

    ctk.CTkLabel(
        version_row,
        text=f"👨‍💻 作者：{AUTHOR}",
    ).pack(side="left")

    # 软件版本 + go-music-api 版本（右对齐，静态显示）
    sw_ver_label = ctk.CTkLabel(
        version_row,
        text=f"📌 软件 {VERSION}",
    )
    sw_ver_label.pack(side="right")

    api_ver_label = ctk.CTkLabel(
        version_row,
        text=f"🔌 go-music-api {_read_local_api_version()}",
    )
    api_ver_label.pack(side="right", padx=(0, 12))

    # ---- 自动更新 go-music-api（后台下载 + 重启服务）----
    def _auto_update_api(latest_tag):
        from script.common.update_check import download_and_update_api
        from script.services.start_service import start_go_music_api, stop_go_music_api

        busy = ctk.CTkLabel(frame, text=f"正在更新 go-music-api {latest_tag}…",
                            text_color="gray")
        busy.pack()

        def _worker():
            try:
                stop_go_music_api()          # 先停服务，避免 exe 被占用
                ok = download_and_update_api(latest_tag)
                start_go_music_api()          # 重启（会加载新 exe + 新 version.txt）
            except Exception as e:
                ok = False
                _err = str(e)
            else:
                _err = None
            frame.after(0, lambda ok=ok, e=_err: _on_api_update_done(ok, e, busy))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_api_update_done(ok, err, busy):
        busy.destroy()
        if ok:
            msgbox.showinfo("更新完成",
                            f"go-music-api 已更新到最新版本，服务已重启。")
        else:
            msgbox.showerror("更新失败",
                             f"自动更新 go-music-api 失败{('：' + err) if err else '。'}\n"
                             "可前往 GitHub release 页手动下载。")

    # ---- 检查更新：结果用弹窗提示，不修改界面 ----
    def run_update_check():
        """后台检查，结果在主线程弹窗提示（不阻塞、不跨线程改 widget）。"""
        busy = ctk.CTkLabel(frame, text="检查更新中…", text_color="gray")
        busy.pack()

        def _worker():
            try:
                res = check_updates()
            except Exception as e:
                res = {"error": str(e)}
            frame.after(0, lambda r=res: _on_update_result(r, busy))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_update_result(res, busy):
        busy.destroy()
        sw = res.get("software", {})
        gm = res.get("gomusic", {})

        if res.get("error") and not sw.get("ok") and not gm.get("ok"):
            msgbox.showerror("检查更新失败", "无法连接 GitHub，请检查网络后重试。")
            return

        sw_up = bool(sw.get("has_update"))
        gm_up = bool(gm.get("has_update"))
        # 本地 API 版本未知但线上有版本，也提示
        gm_unknown = bool(gm.get("local_unknown"))

        # 没有任何更新 → 提示已是最新
        if not (sw_up or gm_up or gm_unknown):
            msgbox.showinfo(
                "检查更新",
                f"✅ 软件 {VERSION}、go-music-api {gm.get('current','?')} 均为最新版本",
            )
            return

        # 组装"有更新"的提示文本
        lines = ["发现以下更新：", ""]
        if sw_up:
            lines.append(f"  📦 软件  {sw.get('current')} → {sw.get('latest')}")
        if gm_up:
            lines.append(f"  🔌 go-music-api  {gm.get('current')} → {gm.get('latest')}")
        if gm_unknown:
            lines.append(f"  🔌 go-music-api  本地未知 · 最新 {gm.get('latest')}")
        lines.append("")

        # ---- 软件更新：只能跳转 GitHub release 页手动下载 ----
        if sw_up:
            if msgbox.askyesno("发现软件新版本",
                               f"📦 软件 {sw.get('current')} → {sw.get('latest')}\n\n"
                               "是否前往 GitHub 下载最新版本？"):
                open_url(sw.get("url") or RELEASE_URL)

        # ---- go-music-api 更新：自动下载并更新本地二进制 ----
        if (gm_up or gm_unknown) and gm.get("latest") != "unknown":
            if msgbox.askyesno("更新 go-music-api",
                               f"🔌 go-music-api {gm.get('current','未知')} → {gm.get('latest')}\n\n"
                               "将自动下载并替换本地 go-music-api，然后重启服务。\n"
                               "是否继续？"):
                _auto_update_api(gm.get("latest"))
        # API 更新成功后刷新版本行（重读本地 version.txt）
        if gm_up:
            api_ver_label.configure(text=f"🔌 go-music-api {gm.get('latest')}")

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
        (0, 1, 2, 3),
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

    ctk.CTkButton(
        button_frame,
        text="🔄 检查更新",
        command=run_update_check
    ).grid(
        row=0,
        column=3,
        padx=10
    )

    # =====================
    # 开源协议
    # =====================

    license_text = """📜 开源协议
本项目采用 Apache License 2.0 开源协议:
https://www.apache.org/licenses/LICENSE-2.0"""

    license_box = ctk.CTkTextbox(
        frame,
        height=70
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
            resource_path("assets/wechat_pay.png")
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

    thanks = """    ❤️ 特别感谢

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


if __name__ == "__main__":
    from _bootstrap import bootstrap_page
    bootstrap_page(
        page_title="🎧 About Page",
        create_fn=create_about_page,
        page_logger=None,
        start_api=False
    )