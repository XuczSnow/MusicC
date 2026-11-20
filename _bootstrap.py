# _bootstrap.py
# ✅ 页面独立运行时的公共启动样板（4 个 page 复用）
import threading
import customtkinter as ctk

from script.services.start_service import start_go_music_api
from script.ui.theme import apply_user_theme


def bootstrap_page(
    page_title,
    create_fn,
    page_logger,
    start_api=True
):
    """
    独立运行某个 page 的统一入口。

    参数:
        page_title : 窗口标题栏文字（如 "🎧 Net Playlist Page"）
        create_fn  : 页面工厂函数 create_xxx_page(parent)
        page_logger: 该页面在 create_xxx_page 内创建并赋值的 logger
        start_api  : 是否后台启动 go-music-api
    """
    # ✅ 统一主题：优先用用户上次选择的主题偏好
    apply_user_theme()

    app = ctk.CTk()
    app.title("AI Music Classifier")
    app.geometry("600x800")

    title = ctk.CTkLabel(
        app,
        text=page_title,
        font=ctk.CTkFont(size=20, weight="bold")
    )
    title.pack(pady=10)

    frame = create_fn(app)
    frame.pack(fill="both", expand=True)

    if start_api:
        bottom_label = ctk.CTkLabel(app, text="初始化中...")
        bottom_label.pack(side="right")

        threading.Thread(
            target=lambda: start_go_music_api(page_logger, bottom_label),
            daemon=True
        ).start()

    app.mainloop()


def bootstrap_organize():
    """音乐整理页不需要 API，单独入口。"""
    import organize_page
    bootstrap_page(
        page_title="🎧 Organize Page",
        create_fn=organize_page.create_organize_page,
        page_logger=organize_page.logger,
        start_api=False
    )
