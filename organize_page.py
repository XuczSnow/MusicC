import os
import shutil
import threading

import customtkinter as ctk

from tkinter import filedialog

from script.load_music import *
from script.logger import AppLogger

logger = None

def unique_path(path):

    if not os.path.exists(path):
        return path

    base, ext = os.path.splitext(path)

    i = 1

    while True:

        new_path = f"{base}({i}){ext}"

        if not os.path.exists(new_path):
            return new_path

        i += 1


def create_organize_page(parent):

    global logger

    frame = ctk.CTkFrame(parent)

    # ==========================
    # 标题
    # ==========================

    # title = ctk.CTkLabel(
    #     frame,
    #     text="📁 音乐整理",
    #     font=ctk.CTkFont(
    #         size=20,
    #         weight="bold"
    #     )
    # )

    # title.pack(pady=10)

    # ==========================
    # 路径选择
    # ==========================

    path_frame = ctk.CTkFrame(frame)

    path_frame.pack(
        fill="x",
        padx=20,
        pady=10
    )

    music_entry = ctk.CTkEntry(
        path_frame,
        placeholder_text="选择音乐目录..."
    )

    music_entry.pack(
        side="left",
        fill="x",
        expand=True,
        padx=(10, 5),
        pady=10
    )

    def browse_folder():

        folder = filedialog.askdirectory()

        if folder:

            music_entry.delete(0, "end")
            music_entry.insert(0, folder)

    ctk.CTkButton(
        path_frame,
        text="浏览",
        width=80,
        command=browse_folder
    ).pack(
        side="right",
        padx=10
    )
    
    out_path_frame = ctk.CTkFrame(frame)

    out_path_frame.pack(
        fill="x",
        padx=20,
        pady=10
    )
    
    output_entry = ctk.CTkEntry(
        out_path_frame,
        placeholder_text="选择输出目录..."
    )

    output_entry.pack(
        side="left",
        fill="x",
        expand=True,
        padx=(10, 5),
        pady=10
    )

    def out_browse_folder():

        folder = filedialog.askdirectory()

        if folder:
            output_entry.delete(0, "end")
            output_entry.insert(0, folder)

    ctk.CTkButton(
        out_path_frame,
        text="浏览",
        width=80,
        command=out_browse_folder
    ).pack(
        side="right",
        padx=10
    )

    # ==========================
    # 整理模式
    # ==========================

    mode_frame = ctk.CTkFrame(frame)

    mode_frame.pack(
        fill="x",
        padx=20,
        pady=10
    )

    ctk.CTkLabel(
        mode_frame,
        text="整理方式："
    ).pack(
        side="left",
        padx=(10, 5)
    )

    organize_mode = ctk.StringVar(
        value="歌手/专辑"
    )

    ctk.CTkOptionMenu(
        mode_frame,
        values=[
            "歌手/专辑",
            "歌手",
            "专辑"
        ],
        variable=organize_mode
    ).pack(
        side="left"
    )

    # ==========================
    # 操作方式
    # ==========================

    operation_frame = ctk.CTkFrame(frame)

    operation_frame.pack(
        fill="x",
        padx=20,
        pady=10
    )

    operation_var = ctk.StringVar(
        value="move"
    )

    ctk.CTkLabel(
        operation_frame,
        text="文件处理："
    ).pack(
        side="left",
        padx=(10, 5)
    )

    ctk.CTkRadioButton(
        operation_frame,
        text="移动",
        variable=operation_var,
        value="move"
    ).pack(
        side="left",
        padx=5
    )

    ctk.CTkRadioButton(
        operation_frame,
        text="复制",
        variable=operation_var,
        value="copy"
    ).pack(
        side="left",
        padx=5
    )

    # ==========================
    # 选项
    # ==========================

    # option_frame = ctk.CTkFrame(frame)

    # option_frame.pack(
    #     fill="x",
    #     padx=20,
    #     pady=10
    # )

    # rename_var = ctk.BooleanVar(
    #     value=True
    # )

    # ctk.CTkCheckBox(
    #     option_frame,
    #     text="同名文件自动重命名",
    #     variable=rename_var
    # ).pack(
    #     side="left",
    #     padx=10
    # )

    # ==========================
    # 状态
    # ==========================

    status_label = ctk.CTkLabel(
        frame,
        text="状态：等待开始"
    )

    status_label.pack(
        pady=5
    )

    # ==========================
    # 进度条
    # ==========================

    progress = ctk.CTkProgressBar(
        frame
    )

    progress.pack(
        fill="x",
        padx=20
    )

    progress.set(0)

    # ==========================
    # 日志
    # ==========================

    log_box = ctk.CTkTextbox(
        frame
    )

    log_box.pack(
        fill="both",
        expand=True,
        padx=20,
        pady=10
    )

    logger = AppLogger(textbox=log_box)

    # ==========================
    # 整理逻辑
    # ==========================

    def organize_worker():

        root_dir = music_entry.get()
        out_dir = output_entry.get()

        if not root_dir or not out_dir:
            logger.warning("请先选择目录\n")
            return

        logger.info("扫描音乐库...")

        songs = load_music(root_dir)

        total = len(songs)

        logger.info(f"    共发现 {total} 首歌曲\n")

        mode = organize_mode.get()

        operation = operation_var.get()

        # auto_rename = rename_var.get()

        for idx, song in enumerate(songs):

            try:

                src = song["path"]

                ext = src.split(".")[-1]
                title = song.get("title","未知歌曲")
                artist = song.get("artist","未知歌手")
                album = song.get("album","未知专辑")
                print(f"整理: {artist} - {title} - {album}")

                filename = f"{artist} - {title}.{ext}"

                if mode == "歌手/专辑":

                    dst_dir = os.path.join(
                        out_dir,
                        artist,
                        album
                    )

                elif mode == "歌手":

                    dst_dir = os.path.join(
                        out_dir,
                        artist
                    )

                else:
                    album = sanitize_filename(album)
                    dst_dir = os.path.join(
                        out_dir,
                        album
                    )

                os.makedirs(
                    dst_dir,
                    exist_ok=True
                )

                dst = os.path.join(
                    dst_dir,
                    filename
                )

                # if auto_rename:

                #     dst = unique_path(dst)

                if src == dst: continue

                if operation == "move":

                    shutil.move(
                        src,
                        dst
                    )

                    action = "移动"

                else:
                    print(f"复制: {src} -> {dst}")
                    shutil.copy2(
                        src,
                        dst
                    )

                    action = "复制"

                logger.info(f"    {action}: {filename}")

                progress_value = (
                    idx + 1
                ) / total

                frame.after(
                    0,
                    lambda p=progress_value:
                    progress.set(p)
                )

                frame.after(
                    0,
                    lambda n=idx+1:
                    status_label.configure(
                        text=f"状态：处理中 {n}/{total}"
                    )
                )

            except Exception as e:

                logger.exception(e)

        frame.after(
            0,
            lambda:
            status_label.configure(
                text="状态：完成 ✅"
            )
        )

        logger.info("整理完成\n")

    # ==========================
    # 开始按钮
    # ==========================

    def start():

        threading.Thread(
            target=organize_worker,
            daemon=True
        ).start()

    ctk.CTkButton(
        frame,
        text="🚀 开始整理",
        height=40,
        command=start
    ).pack(
        pady=10
    )

    return frame

if __name__ == "__main__":
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
        text="🎧 Net Playlist Page",
        font=ctk.CTkFont(size=20, weight="bold")
    )
    title.pack(pady=10)
    
    net_frame = create_organize_page(app)
    net_frame.pack(fill="both", expand=True)

    from script.start_service import *
    import threading

    bottom_label = ctk.CTkLabel(
    app,
    text="初始化中..."
    )

    bottom_label.pack(side="right")

    threading.Thread(
        target=lambda: start_go_music_api(logger, bottom_label),
        daemon=True
    ).start()

    app.mainloop()
