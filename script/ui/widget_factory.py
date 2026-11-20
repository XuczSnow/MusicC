# widget_factory.py
# ✅ 跨页面复用的 UI 组件工厂，消除各页面重复的"目录选择行"样板
import customtkinter as ctk
from tkinter import filedialog


def folder_picker_row(
    parent,
    placeholder="选择音乐目录...",
    label_text=None,
):
    """构建一行"目录选择"UI：输入框 + 浏览按钮。

    参数:
        parent     : 挂载的父容器
        placeholder: 输入框占位文字
        label_text: 可选，左侧标签文字

    返回:
        entry : ctk.CTkEntry（已 pack）
    """
    # ✅ 透明分组框（不产生视觉层），仅用于对齐 输入框+按钮
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=20, pady=10)

    if label_text:
        ctk.CTkLabel(row, text=label_text).pack(side="left", padx=10)

    entry = ctk.CTkEntry(
        row,
        placeholder_text=placeholder
    )
    entry.pack(side="left", fill="x", expand=True, padx=10, pady=10)

    def _select():
        folder = filedialog.askdirectory()
        if folder:
            entry.delete(0, "end")
            entry.insert(0, folder)

    ctk.CTkButton(
        row,
        text="浏览",
        width=80,
        command=_select
    ).pack(side="right", padx=10)

    return entry


# ==================================================================
# 统一页面布局原语：保证 4 个 page 风格一致
# ==================================================================

def page_shell(parent):
    """页面根容器。所有 page 统一用它作为最外层 frame。"""
    frame = ctk.CTkFrame(parent)
    frame.pack(fill="both", expand=True)
    return frame


def _theme_colors():
    """从当前已加载主题取 主色/背景（用于 Tabview 等需显式配色的控件）。"""
    th = ctk.ThemeManager().theme
    dark_idx = 1 if ctk.get_appearance_mode().lower() == "dark" else 0
    def pick(comp, key, default):
        v = th.get(comp, {}).get(key, None)
        if isinstance(v, list) and len(v) > dark_idx:
            return v[dark_idx]
        if isinstance(v, str):
            return v
        return default
    primary = pick("CTkButton", "fg_color", "#5b7cfa")
    bg = pick("CTk", "fg_color", "#1b1e27")
    card = pick("CTkSegmentedButton", "fg_color", bg)
    return primary, bg, card


def make_tabview(parent):
    """主题适配的 CTkTabview：选中标签用主色，未选中用卡片色，内容区用背景色。"""
    primary, bg, card = _theme_colors()
    tv = ctk.CTkTabview(
        parent,
        fg_color=bg,
        corner_radius=8,
        segmented_button_selected_color=primary,
        segmented_button_selected_hover_color=primary,
        segmented_button_unselected_color=card,
        segmented_button_unselected_hover_color=primary,
    )
    tv.pack(fill="both", expand=True)
    return tv


def section_frame(parent, title=None):
    """透明分组框（不产生视觉层叠）。可选标题。"""
    sec = ctk.CTkFrame(parent, fg_color="transparent")
    sec.pack(fill="x", padx=20, pady=5)
    if title:
        ctk.CTkLabel(
            sec,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=5)
    return sec


def log_box(parent, side="top"):
    """统一日志框：直接挂 parent，无额外套壳，统一高度/边距。

    参数 side="top"/"bottom"：与按钮区配合时，日志框通常 side="top"
    展开填充，按钮/底部栏用 side="bottom" 锚定到窗口底部。
    """
    box = ctk.CTkTextbox(parent)
    box.pack(side=side, fill="both", expand=True, padx=20, pady=10)
    return box


def status_label(parent, text="状态：等待开始"):
    """统一状态标签。"""
    label = ctk.CTkLabel(parent, text=text)
    label.pack(pady=5)
    return label


def action_button(parent, text, command, side="bottom"):
    """统一主操作按钮（高度/样式一致）。

    默认 side="bottom"：锚定到窗口底部，避免被上方 expand 的日志框挤出视野。
    """
    btn = ctk.CTkButton(parent, text=text, height=40, command=command)
    btn.pack(side=side, padx=20, pady=10)
    return btn


def config_row(parent, label_text):
    """一行的"标签 + 控件槽"布局（标签固定宽度，右侧留给控件）。

    返回 (row_frame, label_widget)，控件应挂在 row_frame 上（side 排列）。
    用于让"整理方式/文件处理"这类 标签 与 下拉/单选 保持同一列对齐。
    """
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=20, pady=5)
    lbl = ctk.CTkLabel(
        row,
        text=label_text,
        width=90,
        anchor="w",
    )
    lbl.pack(side="left", padx=5)
    return row, lbl


def bottom_bar(parent, side="bottom"):
    """统一底部栏（状态信息/版本等占位区）。

    默认 side="bottom"：锚定到窗口底部（位于按钮之上）。
    """
    bar = ctk.CTkFrame(parent, fg_color="transparent")
    bar.pack(side=side, fill="x", padx=20, pady=(5, 10))
    return bar


def theme_selector(parent):
    """统一"主题设置"：配色主题下拉 + 深浅色切换，全部放在一行。

    - 配色主题切换：保存偏好并【重启应用】生效（CustomTkinter 主题文件
      只作用于新建控件，重启是最可靠的完整刷新方式）。
    - 深浅色切换：即时生效（无需重启）。
    返回 (theme_var, appearance_var)。
    """
    import sys
    import os
    from script.ui import theme as _theme

    # 外层：撑满宽度用于居中定位
    outer = ctk.CTkFrame(parent, fg_color="transparent")
    outer.pack(fill="x", padx=20, pady=5)

    # 内层：仅容纳内容宽度 → 可用 side 居中
    row = ctk.CTkFrame(outer, fg_color="transparent")
    row.pack()  # 默认居中（不 fill x）

    ctk.CTkLabel(row, text="🎨 主题", anchor="w").pack(side="left", padx=(0, 5))

    pref = _theme.load_user_theme()
    # ✅ 统一用"裸名"（modern/warm/...），避免 theme_ 前缀重复
    bare_themes = _theme.available_themes() or ["modern"]
    cur_bare = pref.get("theme_file", "modern")
    theme_var = ctk.StringVar(
        value=cur_bare if cur_bare in bare_themes else bare_themes[0]
    )
    appearance_var = ctk.StringVar(value=pref.get("appearance", "dark"))

    def _relaunch():
        """重启应用使新主题完整生效。

        步骤：
          1. 停止后台 go-music-api（避免残留进程）
          2. 起一个新进程接管
          3. 硬退出当前进程（os._exit）——确保 daemon 线程/残留状态干净结束，
             否则旧进程会挂着不退（GUI 关了但后台线程还在）。
        """
        try:
            # 1) 停后台 API
            try:
                from script.services.start_service import stop_go_music_api
                stop_go_music_api()
            except Exception:
                pass

            import subprocess
            if getattr(sys, "frozen", False):
                # PyInstaller 打包：用同一 exe 起新实例
                new_cmd = [sys.executable]
                cwd = os.path.dirname(sys.executable)
            else:
                new_cmd = [sys.executable] + sys.argv
                cwd = os.path.dirname(os.path.abspath(sys.argv[0]))

            # 2) 起新进程
            subprocess.Popen(
                new_cmd,
                cwd=cwd,
                # 独立进程组，避免与旧进程共享句柄
                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) |
                              getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                if os.name == "nt" else 0,
            )

            # 3) 硬退出当前进程（不触发 finally / 信号处理，干净结束）
            os._exit(0)
        except Exception:
            # 兜底：起新进程失败则只销毁当前窗口（至少 GUI 关得上）
            try:
                root = row.winfo_toplevel()
                root.destroy()
            except Exception:
                pass

    # ✅ CTkOptionMenu 的 command 回调会传入当前选中值，必须接收 1 个参数
    #    theme_var 存裸名（modern/...），保存偏好直接用，无需去前缀
    def _on_theme(value=None):
        name = value or theme_var.get()
        _theme.save_user_theme(name, appearance_var.get())
        _relaunch()

    def _on_appearance(value=None):
        app = value or appearance_var.get()
        _theme.switch_appearance(app)
        # 深浅色也记入偏好（theme 保持当前选择）
        _theme.save_user_theme(theme_var.get(), app)

    ctk.CTkOptionMenu(
        row, values=bare_themes, variable=theme_var,
        command=_on_theme, width=130,
    ).pack(side="left", padx=5)

    ctk.CTkOptionMenu(
        row, values=["dark", "light"], variable=appearance_var,
        command=_on_appearance, width=80,
    ).pack(side="left", padx=5)

    return theme_var, appearance_var
