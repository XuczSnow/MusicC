# net_playlist_page.py — 平台歌单页面（GUI 壳 + CLI 入口）
# 核心逻辑由 net_playlist_core 提供；本文件仅负责 UI 与入口分发。
# 双模式：带命令行参数 → CLI；无参数（或 --gui）→ GUI。
import sys
import threading

import customtkinter as ctk

from script.music.music_tag import TAG_DEFINITIONS, MUSIC_PLATFARM
from script.common.logger import AppLogger
from script.ui.widget_factory import (
    folder_picker_row,
    page_shell,
    log_box,
    status_label,
    action_button,
)

logger = None


def create_net_page(parent, logger=None):
    main_frame = page_shell(parent)
    page_logger = logger if logger is not None else AppLogger()

    # 路径选择
    path_entry = folder_picker_row(main_frame, placeholder="选择音乐目录...")

    # 平台选择（前缀文字 + 下拉框）
    platform_ctrl = ctk.CTkFrame(main_frame, fg_color="transparent")
    platform_ctrl.pack(pady=5, padx=20, fill="x")
    platform_var = ctk.StringVar(value="all")
    ctk.CTkLabel(platform_ctrl, text="平台").pack(side="left", padx=(0, 8))
    platform_menu = ctk.CTkOptionMenu(
        platform_ctrl, values=MUSIC_PLATFARM, variable=platform_var
    )
    platform_menu.pack(side="left", fill="x", expand=True)

    # 数量
    frame_net = ctk.CTkFrame(main_frame, fg_color="transparent")
    frame_net.pack(pady=5, padx=20, fill="x")
    ctk.CTkLabel(frame_net, text="网络搜索数量").pack(side="left")
    entry_limit = ctk.CTkEntry(frame_net)
    entry_limit.insert(0, "30")
    entry_limit.pack(side="right")

    # 最小数量
    frame_min = ctk.CTkFrame(main_frame, fg_color="transparent")
    frame_min.pack(pady=5, padx=20, fill="x")
    ctk.CTkLabel(frame_min, text="歌单最小数量").pack(side="left")
    min_limit = ctk.CTkEntry(frame_min)
    min_limit.insert(0, "2")
    min_limit.pack(side="right")

    # 模式选择
    mode_ctrl = ctk.CTkFrame(main_frame, fg_color="transparent")
    mode_ctrl.pack(pady=5, padx=20, fill="x")
    mode_var = ctk.StringVar(value="preset")

    radio_frame = ctk.CTkFrame(mode_ctrl, fg_color="transparent")
    radio_frame.pack(pady=5)

    ctk.CTkRadioButton(radio_frame, text="模板模式", variable=mode_var, value="preset",
                       command=lambda: update_mode()).pack(side="left", padx=10)
    ctk.CTkRadioButton(radio_frame, text="自定义关键词", variable=mode_var, value="custom",
                       command=lambda: update_mode()).pack(side="left", padx=10)
    ctk.CTkRadioButton(radio_frame, text="随机本地歌曲", variable=mode_var, value="local",
                       command=lambda: update_mode()).pack(side="left", padx=10)

    # 字典选择 / 输入
    control_container = ctk.CTkFrame(mode_ctrl, fg_color="transparent")
    control_container.pack(fill="x", pady=5, expand=True)

    preset_frame = ctk.CTkFrame(control_container, fg_color="transparent")
    preset_frame.pack(fill="x", expand=True)
    group_var = ctk.StringVar(value=list(TAG_DEFINITIONS.keys())[0])
    tag_var = ctk.StringVar()

    group_menu = ctk.CTkOptionMenu(
        preset_frame,
        values=list(TAG_DEFINITIONS.keys()),
        variable=group_var,
        command=lambda _: update_tags(),
    )
    group_menu.pack(side="left", padx=5, fill="x", expand=True)
    tag_menu = ctk.CTkOptionMenu(preset_frame, values=[], variable=tag_var)
    tag_menu.pack(side="left", padx=5, fill="x", expand=True)

    def update_tags():
        group = group_var.get()
        tags = ["ALL"] + list(TAG_DEFINITIONS[group].keys())
        tag_menu.configure(values=tags)
        if tags:
            tag_var.set(tags[0])

    custom_frame = ctk.CTkFrame(control_container, fg_color="transparent")
    custom_frame.pack(fill="x", pady=5, expand=True)
    entry_keyword = ctk.CTkEntry(custom_frame, placeholder_text="输入关键词（例如：失恋歌 / 周杰伦）")
    entry_keyword.pack(fill="x", padx=5)

    local_frame = ctk.CTkFrame(control_container, fg_color="transparent")
    local_frame.pack(fill="x", pady=5, expand=True)
    ctk.CTkLabel(local_frame, text="随机选择本地歌曲搜索歌单").pack(padx=5)

    def update_mode():
        if mode_var.get() == "preset":
            preset_frame.pack(fill="x", expand=True)
            local_frame.pack_forget()
            custom_frame.pack_forget()
        elif mode_var.get() == "local":
            preset_frame.pack_forget()
            local_frame.pack(fill="x", expand=True)
            custom_frame.pack_forget()
        else:
            preset_frame.pack_forget()
            local_frame.pack_forget()
            custom_frame.pack(fill="x", expand=True)

    update_mode()
    update_tags()

    # 状态 + 日志
    status = status_label(main_frame, "状态：等待开始")
    log_widget = log_box(main_frame)
    page_logger = AppLogger(textbox=log_widget)
    globals()['logger'] = page_logger

    def run():
        music_dir = path_entry.get()
        if not music_dir:
            logger.warning("请先选择目录\n")
            return
        if btn.cget("state") == "disabled":
            return

        def task():
            from cores.net_playlist_core import run_playlist

            run_playlist(
                music_dir=music_dir,
                mode=mode_var.get(),
                group=group_var.get(),
                tag=tag_var.get(),
                keyword=entry_keyword.get().strip(),
                limit=int(entry_limit.get()),
                min_limit=int(min_limit.get()),
                platform=platform_var.get(),
                log=page_logger,
            )

        # ⚠️ 子线程不直接改 Tk（after 也非线程安全）。
        # 用 threading.Event + 守护线程等待，一次性回主线程恢复按钮（事件驱动，零轮询）。
        _done = threading.Event()

        def _worker():
            task()
            _done.set()

        threading.Thread(target=_worker, daemon=True).start()
        main_frame.after(0, lambda: btn.configure(state="disabled"))

        def _wait_and_finish():
            _done.wait()
            main_frame.after(0, lambda: btn.configure(state="enabled"))

        threading.Thread(target=_wait_and_finish, daemon=True).start()

    btn = action_button(main_frame, "▶ 生成歌单", run)
    return main_frame


# ---------------- 双模式入口 ----------------
def _cli(args):
    import argparse

    p = argparse.ArgumentParser(description="平台歌单（核心 CLI）")
    p.add_argument("music_dir", help="音乐目录")
    p.add_argument("--mode", default="custom", choices=["preset", "local", "custom"])
    p.add_argument("--group", default=None)
    p.add_argument("--tag", default=None)
    p.add_argument("--keyword", default=None)
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--min", type=int, default=2, dest="min_limit")
    p.add_argument("--platform", default="all", choices=MUSIC_PLATFARM)
    p.add_argument("--gui", action="store_true", help="忽略参数，启动 GUI")
    ns = p.parse_args(args)

    if ns.gui:
        _gui()
        return

    from cores.net_playlist_core import run_playlist
    run_playlist(
        music_dir=ns.music_dir,
        mode=ns.mode,
        group=ns.group,
        tag=ns.tag,
        keyword=ns.keyword,
        limit=ns.limit,
        min_limit=ns.min_limit,
        platform=ns.platform,
    )


def _gui():
    from _bootstrap import bootstrap_page
    bootstrap_page(
        page_title="🎧 Net Playlist Page",
        create_fn=create_net_page,
        page_logger=logger,
        start_api=True,
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        _cli(sys.argv[1:])
    else:
        _gui()
