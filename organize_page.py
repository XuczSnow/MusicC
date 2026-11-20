# organize_page.py — 音乐整理页面（GUI 壳 + CLI 入口）
# 核心逻辑由 organize_core.organize 提供；本文件仅负责 UI 与入口分发。
# 双模式：带命令行参数 → CLI；无参数（或 --gui）→ GUI。
import sys
import threading

import customtkinter as ctk

from script.common.logger import AppLogger
from script.ui.widget_factory import (
    folder_picker_row,
    page_shell,
    config_row,
    log_box,
    status_label,
    action_button,
)

logger = None


def create_organize_page(parent, logger=None):
    frame = page_shell(parent)

    # 路径选择
    music_entry = folder_picker_row(frame, placeholder="选择音乐目录...", label_text="音乐目录")
    output_entry = folder_picker_row(frame, placeholder="选择输出目录...", label_text="输出目录")

    # 整理方式：标签 + 下拉
    mode_row, _ = config_row(frame, "整理方式")
    organize_mode = ctk.StringVar(value="歌手/专辑")
    ctk.CTkOptionMenu(
        mode_row,
        values=["歌手/专辑", "歌手", "专辑"],
        variable=organize_mode,
        width=160
    ).pack(side="left", padx=10)

    # 文件处理：标签 + 单选
    op_row, _ = config_row(frame, "文件处理")
    operation_var = ctk.StringVar(value="move")
    ctk.CTkRadioButton(op_row, text="移动", variable=operation_var, value="move").pack(side="left", padx=5)
    ctk.CTkRadioButton(op_row, text="复制", variable=operation_var, value="copy").pack(side="left", padx=5)

    # 状态 + 进度 + 日志
    status = status_label(frame, "状态：等待开始")
    progress = ctk.CTkProgressBar(frame)
    progress.pack(fill="x", padx=20)
    progress.set(0)

    log_widget = log_box(frame)
    page_logger = AppLogger(textbox=log_widget)
    globals()['logger'] = page_logger

    def worker():
        from cores.organize_core import organize

        # ⚠️ worker 跑在子线程，organize 同步调用 progress_cb（仍在子线程）。
        # 因此 progress_cb 不得调 frame.after（非线程安全）；
        # 改为写线程安全变量，由主线程 after 轮询刷新进度条/状态。
        _state = {"done": 0, "total": 1, "finished": False}

        def progress_cb(done, total):
            _state["done"] = done
            _state["total"] = total or 1

        organize(
            root_dir=music_entry.get(),
            out_dir=output_entry.get(),
            mode=organize_mode.get(),
            operation=operation_var.get(),
            log=page_logger,
            progress_cb=progress_cb,
        )
        _state["finished"] = True

    def start():
        def _poll():
            d, t, fin = _state["done"], _state["total"], _state["finished"]
            if d or fin:
                progress.set(d / t)
                status.configure(text=("状态：完成 ✅" if fin else f"状态：处理中 {d}/{t}"))
            if not fin:
                frame.after(150, _poll)

        threading.Thread(target=worker, daemon=True).start()
        frame.after(150, _poll)

    action_button(frame, "🚀 开始整理", start)
    return frame


# ---------------- 双模式入口 ----------------
def _cli(args):
    """按参数跑 CLI（不起窗口）。"""
    import argparse

    p = argparse.ArgumentParser(description="音乐整理（核心 CLI）")
    p.add_argument("music_dir", help="音乐目录")
    p.add_argument("output_dir", help="输出目录")
    p.add_argument("--mode", default="歌手/专辑", choices=["歌手/专辑", "歌手", "专辑"])
    p.add_argument("--op", default="move", choices=["move", "copy"])
    p.add_argument("--gui", action="store_true", help="忽略参数，启动 GUI")
    ns = p.parse_args(args)

    if ns.gui:
        _gui()
        return

    from cores.organize_core import organize
    organize(ns.music_dir, ns.output_dir, mode=ns.mode, operation=ns.op)


def _gui():
    from _bootstrap import bootstrap_page
    bootstrap_page(
        page_title="🎧 Organize Page",
        create_fn=create_organize_page,
        page_logger=logger,
        start_api=False,
    )


if __name__ == "__main__":
    # 带参数 → CLI；无参数 → GUI
    if len(sys.argv) > 1:
        _cli(sys.argv[1:])
    else:
        _gui()
