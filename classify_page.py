# classify_page.py
# ✅ 本地分类页面（可作 Tab / 可独立运行；CLI/GUI 双模式）
#    核心逻辑由 classify_core.run_classifier 提供
import sys
import threading

import customtkinter as ctk

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


def create_classify_page(parent, logger=None):
    """构建"本地分类"页面，挂载到 parent。

    与三个 page 保持统一格式：
      - 路径选择（folder_picker_row）
      - 功能开关 / AI阈值 / 网络采样数量
      - 日志框
      - 状态标签 + 开始按钮
    后台线程调用 classify_core.run_classifier。
    """
    # ✅ E收敛：logger 通过参数注入，缺省用模块级全局（保持 Tab 流程不变）
    page_logger = logger if logger is not None else globals()['logger']

    # ===== 根 =====
    main_frame = page_shell(parent)

    # ================= 路径选择 =================
    path_entry = folder_picker_row(
        main_frame,
        placeholder="选择音乐目录..."
    )

    # ================= 参数控制（统一 section） =================
    frame_control = section_frame(main_frame, "参数控制")

    # ✅ 统一行格式：标签列 width=90 左对齐 + 控件对齐（与其他页 config_row 一致）
    LABEL_W = 90

    # 功能开关（复选框：加左缩进，与其它行的控件列对齐）
    frame_switch = ctk.CTkFrame(frame_control, fg_color="transparent")
    frame_switch.pack(fill="x", padx=5, pady=5)
    ctk.CTkLabel(frame_switch, text="分类开关", width=LABEL_W, anchor="w").pack(side="left", padx=5)
    switch_row = ctk.CTkFrame(frame_switch, fg_color="transparent")
    switch_row.pack(side="left")

    var_ai = ctk.BooleanVar(value=True)
    var_net = ctk.BooleanVar(value=True)
    var_artist = ctk.BooleanVar(value=True)
    var_era = ctk.BooleanVar(value=True)
    var_audio = ctk.BooleanVar(value=False)   # 音频（PANNs）分类，默认关

    ctk.CTkCheckBox(switch_row, text="AI歌词", variable=var_ai, width=62).pack(side="left", padx=(0, 8))
    ctk.CTkCheckBox(switch_row, text="AI音频", variable=var_audio, width=62).pack(side="left", padx=(0, 8))
    ctk.CTkCheckBox(switch_row, text="NET标签", variable=var_net, width=74).pack(side="left", padx=(0, 8))
    ctk.CTkCheckBox(switch_row, text="歌手精选", variable=var_artist, width=86).pack(side="left", padx=(0, 8))
    ctk.CTkCheckBox(switch_row, text="年代", variable=var_era, width=54).pack(side="left", padx=(0, 0))

    # AI阈值（标签 + 滑块 同一行，标签列与其它行对齐）
    frame_slider = ctk.CTkFrame(frame_control, fg_color="transparent")
    frame_slider.pack(fill="x", padx=5, pady=5)

    label_ai = ctk.CTkLabel(frame_slider, text="AI阈值 0.4", width=LABEL_W, anchor="w")
    label_ai.pack(side="left", padx=5)

    def ai_slider_changed(value):
        label_ai.configure(text="AI阈值 " + format(value, '.2f'))

    slider_ai = ctk.CTkSlider(frame_slider, from_=0.2, to=0.8, width=160)
    slider_ai.set(0.4)
    slider_ai.configure(command=ai_slider_changed)
    slider_ai.pack(side="left", padx=10, fill="x", expand=True)

    # 网络采样数量（标签列对齐 + 输入框）
    frame_net = ctk.CTkFrame(frame_control, fg_color="transparent")
    frame_net.pack(fill="x", padx=5, pady=5)

    ctk.CTkLabel(frame_net, text="最大网络采样数量", width=LABEL_W, anchor="w").pack(side="left", padx=5)

    entry_net_limit = ctk.CTkEntry(frame_net, width=80)
    entry_net_limit.insert(0, "10")
    entry_net_limit.pack(side="right", padx=10)

    # ================= 状态 + 日志（统一顺序：状态在上，日志在下） =================
    status = status_label(main_frame, "状态：空闲 ⏳")

    log_widget = log_box(main_frame)
    page_logger = AppLogger(textbox=log_widget)

    # ================= 运行 =================
    is_running = False
    loading_index = 0
    loading_frames = ["⏳", "⌛", "🔄"]

    def update_loading():
        nonlocal loading_index

        if not is_running:
            return

        icon = loading_frames[loading_index % len(loading_frames)]
        btn_start.configure(text=f"{icon} 处理中...")
        loading_index += 1

        main_frame.after(400, update_loading)

    def reset_button():
        btn_start.configure(text="▶ 开始分类", state="normal")
        status.configure(text="状态：完成 ✅")

    def run_task(folder, page_logger):
        """子线程：只做核心逻辑 + 产出结果，不碰任何 Tk widget。"""
        try:
            from cores.classify_core import run_classifier
            run_classifier(
                music_dir=folder,
                use_ai=var_ai.get(),
                use_net=var_net.get(),
                use_artist=var_artist.get(),
                use_era=var_era.get(),
                use_audio=var_audio.get(),
                ai_threshold=slider_ai.get(),
                net_limit=int(entry_net_limit.get()),
                log=page_logger,
            )
        except Exception as e:
            page_logger.exception(e)

    def start():
        nonlocal is_running
        if is_running:
            return

        folder = path_entry.get()
        if not folder:
            page_logger.warning("请先选择目录\n")
            return

        is_running = True
        btn_start.configure(state="disabled")
        status.configure(text="状态：运行中 🚀")
        update_loading()

        _done = threading.Event()

        def _worker():
            run_task(folder, page_logger)
            _done.set()

        threading.Thread(target=_worker, daemon=True).start()

        def _poll():
            if _done.is_set():
                status.configure(text="状态：完成 ✅")
                is_running = False
                reset_button()
            else:
                main_frame.after(200, _poll)

        main_frame.after(200, _poll)

    # ================= 按钮（统一 action_button，锚定底部） =================
    btn_start = action_button(main_frame, "▶ 开始分类", start)

    return main_frame


# ---------------- 双模式入口 ----------------
def _cli(args):
    import argparse

    p = argparse.ArgumentParser(description="本地分类（核心 CLI）")
    p.add_argument("music_dir", help="音乐目录")
    p.add_argument("--no-ai", action="store_true", help="禁用 AI 标签")
    p.add_argument("--no-net", action="store_true", help="禁用 NET 标签")
    p.add_argument("--no-artist", action="store_true", help="禁用歌手精选")
    p.add_argument("--no-era", action="store_true", help="禁用年代")
    p.add_argument("--ai-threshold", type=float, default=0.4)
    p.add_argument("--audio", action="store_true", help="启用音频（PANNs）分类")
    p.add_argument("--net-limit", type=int, default=10)
    p.add_argument("--gui", action="store_true", help="忽略参数，启动 GUI")
    ns = p.parse_args(args)

    if ns.gui:
        _gui()
        return

    from cores.classify_core import run_classifier
    run_classifier(
        music_dir=ns.music_dir,
        use_ai=not ns.no_ai,
        use_net=not ns.no_net,
        use_artist=not ns.no_artist,
        use_era=not ns.no_era,
        use_audio=ns.audio,
        ai_threshold=ns.ai_threshold,
        net_limit=ns.net_limit,
    )


def _gui():
    from _bootstrap import bootstrap_page
    bootstrap_page(
        page_title="🎧 Classify Page",
        create_fn=create_classify_page,
        page_logger=logger,
        start_api=True
    )


if __name__ == "__main__":
    # 带参数 → CLI；无参数 → GUI
    if len(sys.argv) > 1:
        _cli(sys.argv[1:])
    else:
        _gui()
