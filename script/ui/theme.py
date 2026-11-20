# script/ui/theme.py
# ✅ 统一 GUI 主题：集中管理外观模式 + 自定义配色 + 字体
#    主入口与各 page 独立运行都调用 apply_theme()，确保全局一致
#
# ⚠️ 必须在 app = ctk.CTk() 之前、且【不能创建临时 CTk() 窗口】调用：
#    CustomTkinter 的外观模式绑定在 Tk 根环境上，临时窗口一旦销毁会把
#    外观设置"带走"，导致后续真正的窗口回落默认（背景变白）。
import os
import json

import customtkinter as ctk

# 用户主题偏好持久化文件（记住上次选择的 主题/外观，重启后自动应用）
_PREF_FILE = "theme_pref.json"


def _project_root() -> str:
    """定位项目根目录（本文件位于 <root>/script/ui/theme.py，上溯 3 级）。

    用绝对路径而非 CWD，避免从不同工作目录启动时找不到偏好文件。
    """
    return os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
    )


def _pref_path() -> str:
    return os.path.join(_project_root(), _PREF_FILE)


def load_user_theme() -> dict:
    """读取用户主题偏好（theme_file / appearance），缺省 modern/dark。"""
    default = {"theme_file": "modern", "appearance": "dark"}
    try:
        if os.path.exists(_pref_path()):
            with open(_pref_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            default.update({k: data[k] for k in default if k in data})
    except Exception:
        pass
    return default


def save_user_theme(theme_file: str, appearance: str) -> None:
    """保存用户主题偏好，供下次启动 apply_user_theme() 自动应用。"""
    try:
        with open(_pref_path(), "w", encoding="utf-8") as f:
            json.dump({"theme_file": theme_file, "appearance": appearance}, f,
                      ensure_ascii=False, indent=2)
    except Exception:
        pass


def apply_user_theme() -> None:
    """应用用户上次的主题偏好（启动时调用一次）。"""
    pref = load_user_theme()
    apply_theme(appearance=pref.get("appearance", "dark"),
                theme_file=pref.get("theme_file", "modern"))


def _theme_path(theme_file: str = "modern") -> str:
    """定位 assets/themes/theme_<name>.json（兼容 PyInstaller 打包）。

    参数 theme_file 为不含前缀的主题名（如 "modern"），
    实际文件名为 assets/themes/theme_modern.json。
    """
    fname = theme_file if theme_file.startswith("theme_") else f"theme_{theme_file}"
    if hasattr(os, "_MEIPASS"):
        return os.path.join(os._MEIPASS, "assets", "themes", f"{fname}.json")
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, "assets", "themes", f"{fname}.json")


def available_themes() -> list:
    """返回 assets/themes/ 下可用的主题文件名列表（不含 .json 后缀）。"""
    if hasattr(os, "_MEIPASS"):
        theme_dir = os.path.join(os._MEIPASS, "assets", "themes")
    else:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        theme_dir = os.path.join(root, "assets", "themes")
    if not os.path.isdir(theme_dir):
        return []
    out = []
    for fn in os.listdir(theme_dir):
        if fn.endswith(".json") and fn.startswith("theme_"):
            out.append(fn[:-5])
    return sorted(out)


def apply_theme(
    appearance: str = "dark",
    theme_file: str = "modern",
    base_font: str = "Segoe UI",
    base_size: int = 13,
) -> None:
    """应用统一主题（纯配置，不创建任何窗口，可安全在主窗口前调用）。

    参数:
        appearance : "dark" / "light"
        theme_file : 自定义主题 JSON 文件名（assets/themes/ 下），缺省 "modern"
        base_font  : 基础字体族
        base_size  : 基础字号

    说明:
        优先加载 assets/themes/theme_modern.json（若存在），否则回落到内置 "blue"。
        主题与外观设置后，后续创建的 ctk 控件自动继承。
    """
    # 直接设置全局外观模式（AppearanceModeTracker，不经过临时窗口）
    # ✅ 容错：外观值统一转小写（避免 "Dark"/"Light" 大小写问题导致取色分支错）
    ctk.set_appearance_mode(str(appearance).lower())

    # 加载自定义配色主题（仅修改 ThemeManager 字典，无需窗口）
    theme_json = _theme_path(theme_file)
    if os.path.exists(theme_json):
        ctk.ThemeManager().load_theme(theme_json)
    else:
        ctk.set_default_color_theme("blue")

    # 基础字体（对未显式指定字体的控件生效）
    try:
        import tkinter.font as tkfont
        tkfont.nametofont("TkDefaultFont").configure(family=base_font, size=base_size)
        tkfont.nametofont("TkTextFont").configure(family=base_font, size=base_size)
        tkfont.nametofont("TkMenuFont").configure(family=base_font, size=base_size)
    except Exception:
        pass


def switch_appearance(appearance: str) -> None:
    """仅切换 深色/浅色 外观（保留当前配色主题），对已存在控件即时生效。"""
    ctk.set_appearance_mode(str(appearance).lower())


def refresh_all(widget=None) -> None:
    """遍历控件树，强制已存在的 CTk 控件重新读取当前主题配色。

    CustomTkinter 的 load_theme 只影响【之后创建】的控件；对已渲染的
    控件需手动刷新。这里遍历 root 下所有 CTk 控件并触发其重新应用外观。
    """
    import tkinter as tk
    if widget is None:
        widget = ctk.CTk()  # 仅用于取 root
        widget.withdraw()

    root = widget if isinstance(widget, (tk.Tk, tk.Widget)) else None
    target = root if root is not None else widget
    # 找到最顶层 Tk 根
    top = target.winfo_toplevel() if hasattr(target, "winfo_toplevel") else widget

    def _walk(w):
        for child in w.winfo_children():
            # 只对 CustomTkinter 控件刷新（有 _apply_appearance 或 set_default 行为）
            cls = type(child).__name__
            if cls.startswith("CTk"):
                try:
                    if hasattr(child, "_canvas"):
                        # 重新触发外观回调（CustomTkinter 内部方法）
                        if hasattr(child, "_apply_appearance"):
                            child._apply_appearance()
                        elif hasattr(child, "update"):
                            child.update_idletasks()
                except Exception:
                    pass
            _walk(child)

    _walk(top)
    try:
        top.update()
    except Exception:
        pass
