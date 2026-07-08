# GUI Spotify风格（Modern UI）
import customtkinter as ctk
import threading

from script.start_service import *
from tkinter import filedialog

from script.logger import AppLogger

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
    text="🎧 AI Music Smart Classifier",
    font=ctk.CTkFont(size=20, weight="bold")
)
title.pack(pady=10)

# ================= Tab =================
tabview = ctk.CTkTabview(app)
tabview.pack(fill="both", expand=True)

main_tab = tabview.add("本地分类")
net_tab = tabview.add("平台歌单")
meta_tab = tabview.add("元数据增强")
organize_tab = tabview.add("音乐整理")

def load_net_page():

    from net_playlist_page import create_net_page

    net_frame = create_net_page(net_tab)
    net_frame.pack(fill="both", expand=True)

def load_mate_page():
    from metadata_page import create_metadata_page
    net_frame = create_metadata_page(meta_tab)
    net_frame.pack(fill="both", expand=True)

def load_ori_page():
    from organize_page import create_organize_page

    net_frame = create_organize_page(organize_tab)
    net_frame.pack(fill="both", expand=True)

# ================= 路径选择 =================
frame_path = ctk.CTkFrame(main_tab)
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

# ================= 参数控制 =================
frame_control = ctk.CTkFrame(main_tab)
frame_control.pack(pady=10, padx=20, fill="x")

# ✅ 第一行：开关
frame_switch = ctk.CTkFrame(frame_control)
frame_switch.pack(fill="x", padx=10, pady=10)

var_ai = ctk.BooleanVar(value=True)
var_net = ctk.BooleanVar(value=True)
var_artist = ctk.BooleanVar(value=True)
var_era = ctk.BooleanVar(value=True)

ctk.CTkCheckBox(frame_switch, text="AI标签", variable=var_ai).pack(side="left", padx=10)
ctk.CTkCheckBox(frame_switch, text="NET标签", variable=var_net).pack(side="left", padx=10)
ctk.CTkCheckBox(frame_switch, text="歌手精选", variable=var_artist).pack(side="left", padx=10)
ctk.CTkCheckBox(frame_switch, text="年代", variable=var_era).pack(side="left", padx=10)

# ✅ 第二行：阈值
label_ai = ctk.CTkLabel(frame_control, text="AI阈值（匹配敏感度 0.2-0.8）: 0.4")
label_ai.pack(anchor="w", padx=10)

def ai_slider_changed(value):
    label_ai.configure(text="AI阈值（匹配敏感度 0.2-0.8）: "+format(value, '.2f'))

slider_ai = ctk.CTkSlider(frame_control, from_=0.2, to=0.8)
slider_ai.set(0.4)
slider_ai.configure(command=ai_slider_changed)
slider_ai.pack(fill="x", padx=10)

# ✅ 第三行：权重
label_weight_ai = ctk.CTkLabel(frame_control, text="AI权重（推荐影响 1-5）: 2")
label_weight_ai.pack(anchor="w", padx=10)

def ai_weight_slider_changed(value):
    label_weight_ai.configure(text="AI权重（推荐影响 1-5）: "+str(int(value)))

slider_weight_ai = ctk.CTkSlider(frame_control, from_=1, to=5)
slider_weight_ai.set(2)
slider_weight_ai.configure(command=ai_weight_slider_changed)
slider_weight_ai.pack(fill="x", padx=10)

label_weight_net = ctk.CTkLabel(frame_control, text="网络权重（规则影响 0-5）: 1")
label_weight_net.pack(anchor="w", padx=10)

def net_weight_slider_changed(value):
    label_weight_net.configure(text="网络权重（规则影响 0-5）: "+str(int(value)))

slider_weight_net = ctk.CTkSlider(frame_control, from_=0, to=5)
slider_weight_net.set(1)
slider_weight_net.configure(command=net_weight_slider_changed)
slider_weight_net.pack(fill="x", padx=10)

# ✅ 第四行：样本数
frame_sample = ctk.CTkFrame(frame_control)
frame_sample.pack(fill="x", padx=10, pady=10)

ctk.CTkLabel(frame_sample, text="最大处理歌曲数").pack(side="left")

entry_sample = ctk.CTkEntry(frame_sample, width=80)
entry_sample.insert(0, "1000")
entry_sample.pack(side="right")

# ✅ 网络搜索数量
frame_net = ctk.CTkFrame(frame_control)
frame_net.pack(fill="x", padx=10, pady=5)

ctk.CTkLabel(frame_net, text="网络搜索数量").pack(side="left")

entry_net_limit = ctk.CTkEntry(frame_net, width=80)
entry_net_limit.insert(0, "30")   # 默认5
entry_net_limit.pack(side="right")

# ================= 日志 =================
frame_log = ctk.CTkFrame(main_tab)
frame_log.pack(padx=20, pady=10, fill="both", expand=True)

log_box = ctk.CTkTextbox(frame_log)
log_box.pack(fill="both", expand=True, padx=10, pady=10)

logger = AppLogger(textbox=log_box)
logger.startup_info()
    
# ================= 状态 =================
status_label = ctk.CTkLabel(main_tab, text="状态：空闲 ⏳")
status_label.pack()

# ================= 底部状态 =================

bottom_label = ctk.CTkLabel(
    app,
    text="初始化中..."
)

bottom_label.pack(side="right")

def initialize():

    # 启动API（后台）
    threading.Thread(
        target=lambda: start_go_music_api(logger, bottom_label),
        daemon=True
    ).start()

    # 延迟加载
    app.after(
        500,
        load_net_page
    )

    app.after(
        500,
        load_mate_page
    )

    app.after(
        500,
        load_ori_page
    )

# ================= 运行 =================
def run_task():
    global is_running

    folder = path_entry.get()

    if not folder:
        is_running = False
        main_tab.after(0, reset_button)
        logger.warning("请先选择目录\n")
        return

    # 先输出提示信息
    main_tab.after(0, lambda: status_label.configure(text="状态：运行中 🚀"))

    from smart_music_classifier import run_classifier

    run_classifier(
        music_dir=folder,

        use_ai=var_ai.get(),
        use_net=var_net.get(),
        use_artist=var_artist.get(),
        use_era=var_era.get(),

        ai_threshold=slider_ai.get(),
        weight_ai=int(slider_weight_ai.get()),
        weight_net=int(slider_weight_net.get()),

        max_sample=int(entry_sample.get()),
        net_limit=int(entry_net_limit.get()),

        log=logger
    )

    main_tab.after(0, lambda: status_label.configure(text="状态：完成 ✅"))

    is_running = False

    # ✅ 恢复按钮（主线程）
    main_tab.after(0, reset_button)

# ================= 按钮 =================

is_running = False
loading_index = 0

loading_frames = ["⏳", "⌛", "🔄"]

def update_loading():
    global loading_index

    if not is_running:
        return

    icon = loading_frames[loading_index % len(loading_frames)]
    btn_start.configure(text=f"{icon} 处理中...")
    loading_index += 1

    # 每400ms刷新一次
    main_tab.after(400, update_loading)

def reset_button():
    btn_start.configure(
        text="▶ 开始分类",
        state="normal"
    )
    status_label.configure(text="状态：完成 ✅")

def start():
    global is_running

    if is_running:
        return

    is_running = True

    # ✅ 禁用按钮
    btn_start.configure(state="disabled")

    # ✅ 启动动画
    update_loading()

    # ✅ 启动任务
    threading.Thread(target=run_task).start()

btn_start = ctk.CTkButton(
    main_tab,
    text="▶ 开始分类",
    height=40,
    command=start
)
btn_start.pack(pady=10)

# ================= 关闭 =================
def on_close():
    stop_go_music_api()
    app.destroy()

app.protocol("WM_DELETE_WINDOW", on_close)

# ================= 启动 =================
app.after(
    100,
    initialize
)

app.mainloop()
