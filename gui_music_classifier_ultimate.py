# GUI Spotify风格（Modern UI）
import customtkinter as ctk
import threading
import webbrowser

# ✅ 具名导入（避免 star-import 引入未用符号）
from script.services.start_service import start_go_music_api, stop_go_music_api

from script.common.logger import AppLogger
from script.ui.theme import apply_user_theme, apply_theme

# ✅ 统一主题：优先用用户上次选择的主题偏好，缺省 modern/dark
apply_user_theme()


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
from script.ui.widget_factory import make_tabview
tabview = make_tabview(app)

main_tab = tabview.add("本地分类")
net_tab = tabview.add("平台歌单")
meta_tab = tabview.add("元数据增强")
organize_tab = tabview.add("音乐整理")
about_tab = tabview.add("关于软件")

def load_classify_page():
    from classify_page import create_classify_page
    cls_frame = create_classify_page(main_tab, logger=logger)
    cls_frame.pack(fill="both", expand=True)

def load_net_page():
    from net_playlist_page import create_net_page
    net_frame = create_net_page(net_tab)
    net_frame.pack(fill="both", expand=True)

def load_mate_page():
    from metadata_page import create_metadata_page
    mate_frame = create_metadata_page(meta_tab)
    mate_frame.pack(fill="both", expand=True)

def load_ori_page():
    from organize_page import create_organize_page
    ori_frame = create_organize_page(organize_tab)
    ori_frame.pack(fill="both", expand=True)

def load_aboout_page():
    from about_page import create_about_page
    about_frame = create_about_page(about_tab)
    about_frame.pack(fill="both", expand=True)


# ================= 底部状态 =================

bottom_label = ctk.CTkLabel(
    app,
    text="初始化中..."
)

bottom_label.pack(side="right")

# ✅ GUI 级 logger（供 API 启动状态使用；各 page 自带日志框）
logger = AppLogger()
logger.startup_info()

def open_url(event=None):
    webbrowser.open_new_tab("https://www.aliyun.com/minisite/goods?userCode=0resrw6k")

ad_link = ctk.CTkLabel(
    app,
    text="🔗 阿里云专属优惠",
    text_color="#4EA1FF",
    cursor="hand2"
)

ad_link.pack(
    side="left",
)

ad_link.bind(
    "<Button-1>",
    open_url
)

# ================= 启动检查更新 =================
from script.common.update_check import check_updates, any_update
from script.common.version import SOFTWARE_RELEASES_URL, GOMUSIC_RELEASES_URL

# 更新提示 label（默认隐藏；后台检查到更新才显示，点击跳对应 release 页）
_update_info = {"res": None}
update_link = ctk.CTkLabel(
    app,
    text="",
    text_color="#FFB000",
    cursor="hand2",
)
# 先不 pack，有更新时再 pack 到底部左侧

def _on_update_check(res):
    """主线程回调：根据检查结果决定是否显示更新提示。"""
    _update_info["res"] = res
    if not any_update(res):
        update_link.configure(text="")
        return
    sw = res.get("software", {})
    gm = res.get("gomusic", {})
    parts = []
    if sw.get("has_update"):
        parts.append(f"📦 软件 {sw.get('latest')}")
    if gm.get("has_update") or gm.get("local_unknown"):
        parts.append(f"🔌 go-music-api {gm.get('latest')}")
    update_link.configure(text="⬆️ " + "  ".join(parts) + "  点击查看")
    update_link.pack(side="left", padx=(10, 4))

def _click_update(_event=None):
    res = _update_info.get("res") or {}
    sw = res.get("software", {})
    gm = res.get("gomusic", {})
    if sw.get("has_update") and sw.get("url"):
        webbrowser.open_new_tab(sw["url"])
    elif gm.get("latest") != "unknown":
        webbrowser.open_new_tab(gm.get("url") or GOMUSIC_RELEASES_URL)
    else:
        webbrowser.open_new_tab(SOFTWARE_RELEASES_URL)

update_link.bind("<Button-1>", _click_update)

def _run_update_check():
    """子线程检查，结果经 app.after 回主线程显示（不跨线程改 widget）。"""
    def _worker():
        try:
            res = check_updates()
        except Exception:
            res = {}
        app.after(0, lambda r=res: _on_update_check(r))
    threading.Thread(target=_worker, daemon=True).start()

def initialize():

    # 启动API（后台，不阻塞 UI）
    # ⚠️ 子线程不得直接改 Tk widget（含 .after/.configure）；
    #    子线程只产出状态字符串，由主线程 after 回调更新 bottom_label。
    _api_result = {"status": None}
    _api_done = threading.Event()

    def _api_worker():
        _api_result["status"] = start_go_music_api(logger)  # 不传 label，不碰 Tk
        _api_done.set()

    threading.Thread(target=_api_worker, daemon=True).start()

    def _poll_api():
        if _api_done.is_set() and _api_result["status"] is not None:
            bottom_label.configure(text=_api_result["status"])
        else:
            app.after(200, _poll_api)

    app.after(200, _poll_api)

    # ✅ 性能：页面均为轻量 UI 壳（重库已惰性化），无需阶梯延迟，
    #    一次性顺序加载，首屏更快可用
    load_classify_page()
    load_net_page()
    load_mate_page()
    load_ori_page()
    load_aboout_page()

    # 启动检查更新（后台，不阻塞首屏；延迟 500ms 避开渲染高峰）
    app.after(500, _run_update_check)

# ================= 关闭 =================
def on_close():
    stop_go_music_api()
    app.destroy()

app.protocol("WM_DELETE_WINDOW", on_close)

# ================= 启动 =================
app.after(
    50,
    initialize
)

app.mainloop()
