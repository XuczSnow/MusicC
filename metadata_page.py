# metadata_page.py — 元数据增强页面（GUI 壳 + CLI 入口）
# 核心逻辑由 metadata_core 提供；本文件仅负责 UI 与入口分发。
# 双模式：带命令行参数 → CLI；无参数（或 --gui）→ GUI。
import sys
import threading

import customtkinter as ctk

from script.music.music_tag import MUSIC_PLATFARM
from script.common.logger import AppLogger
from script.ui.widget_factory import (
    folder_picker_row,
    page_shell,
    section_frame,
    log_box,
    status_label,
    action_button,
)

logger = None


def create_metadata_page(parent, logger=None):
    frame = page_shell(parent)

    # 路径选择
    path_entry = folder_picker_row(frame, placeholder="选择音乐目录")

    # 选项（第 1 行：覆盖类）
    option_frame = section_frame(frame, "选项")
    row1 = ctk.CTkFrame(option_frame, fg_color="transparent")
    row1.pack(fill="x", padx=4)

    overwrite_var = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(row1, text="覆盖原始元数据", variable=overwrite_var).pack(side="left", padx=10, pady=5)
    overwrite_dirty_var = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(row1, text="强制覆盖脏数据", variable=overwrite_dirty_var).pack(side="left", padx=10, pady=5)
    overwrite_date_var = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(row1, text="强制更新年份", variable=overwrite_date_var).pack(side="left", padx=10, pady=5)

    # 选项（第 2 行：AI 类，另起一行）
    ai_row = ctk.CTkFrame(option_frame, fg_color="transparent")
    ai_row.pack(fill="x", padx=4, pady=(2, 0))

    ai_sync_var = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(ai_row, text="AI 同步（补时间戳）", variable=ai_sync_var).pack(side="left", padx=10, pady=5)
    ai_fill_var = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(ai_row, text="AI 增补（无歌词）", variable=ai_fill_var).pack(side="left", padx=10, pady=5)

    # 备份：把修改过的歌曲复制到 源目录/bak/
    backup_var = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(ai_row, text="备份修改歌曲", variable=backup_var).pack(side="left", padx=10, pady=5)

    # 平台与参数
    platform_frame = section_frame(frame, "平台与参数")
    ctk.CTkLabel(platform_frame, text="元数据来源平台").pack(side="left", padx=5)
    platform_var = ctk.StringVar(value="brainz")
    ctk.CTkOptionMenu(
        platform_frame,
        values=["brainz"] + MUSIC_PLATFARM[1:],
        variable=platform_var
    ).pack(side="left", padx=5)

    # 图像最大分辨率（输入框在左，文字在右，避免右侧被挤）
    pixel_limit = ctk.CTkEntry(platform_frame, width=80)
    pixel_limit.insert(0, "800")
    pixel_limit.pack(side="right", padx=5)
    ctk.CTkLabel(platform_frame, text="图像最大分辨率").pack(side="right", padx=5)

    # 歌词偏移（ms）：正=滞后，负=提前；0 表示不偏移
    offset_frame = section_frame(frame, "歌词偏移")
    ctk.CTkLabel(offset_frame, text="歌词时间偏移 (ms)").pack(side="left", padx=5)
    ctk.CTkLabel(offset_frame, text="正数=滞后  负数=提前  0=不偏移").pack(side="left", padx=5)
    lrc_offset = ctk.CTkEntry(offset_frame, width=80)
    lrc_offset.insert(0, "0")
    lrc_offset.pack(side="right", padx=5)

    # 状态 + 日志
    status = status_label(frame, "状态：等待开始")
    log_widget = log_box(frame)
    page_logger = AppLogger(textbox=log_widget)
    globals()['logger'] = page_logger

    def start_task():
        btn.configure(state="disabled")
        status.configure(text="状态：运行中 🚀")

        # 子线程写进度变量；主线程 after 轮询刷新（frame.after 非线程安全，不可在子线程调）
        _shared = {"done": 0, "total": 1, "finished": False}

        def _worker():
            from cores.metadata_core import run_metadata
            folder = path_entry.get().strip()
            if not folder:
                page_logger.warning("请先选择目录\n")
                _shared["finished"] = True
                return

            def progress_cb(done, total):
                _shared["done"] = done
                _shared["total"] = total or 1

            run_metadata(
                folder=folder,
                plat=platform_var.get(),
                overwrite=overwrite_var.get(),
                overwrite_dirty=overwrite_dirty_var.get(),
                overwrite_date=overwrite_date_var.get(),
                pixel=int(pixel_limit.get()),
                ai_sync=ai_sync_var.get(),
                ai_fill=ai_fill_var.get(),
                backup=backup_var.get(),
                lrc_offset=int(lrc_offset.get() or 0),
                log=page_logger,
                progress_cb=progress_cb,
            )
            _shared["finished"] = True

        def _poll():
            d, t, fin = _shared["done"], _shared["total"], _shared["finished"]
            if d:
                status.configure(text=f"状态：处理中 {d}/{t}")
            if fin:
                status.configure(text="状态：完成 ✅")
                btn.configure(state="normal")
            else:
                frame.after(150, _poll)

        threading.Thread(target=_worker, daemon=True).start()
        frame.after(150, _poll)

    btn = action_button(frame, "🚀 开始获取", start_task)
    return frame


# ---------------- 双模式入口 ----------------
def _cli(args):
    import argparse

    p = argparse.ArgumentParser(description="元数据增强（核心 CLI）")
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
    ns = p.parse_args(args)

    if ns.gui:
        _gui()
        return

    from cores.metadata_core import run_metadata
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


def _gui():
    from _bootstrap import bootstrap_page
    bootstrap_page(
        page_title="🎧 Metadata Page",
        create_fn=create_metadata_page,
        page_logger=logger,
        start_api=True,
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        _cli(sys.argv[1:])
    else:
        _gui()
