# -*- coding: utf-8 -*-
"""
organize_core.py — 音乐整理核心逻辑（无 GUI 依赖，可独立 CLI 运行）。

职责：把音乐文件按 整理方式(歌手/专辑 等) + 文件处理(移动/复制) 重排到输出目录。
GUI 由 organize_page.py 调用 run()；CLI 直接 `python organize_core.py <参数>`。
"""

import os
import shutil
import sys

# 允许从 cores/ 目录直接运行（CLI）：把项目根加入 sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from script.music.load_music import split_artists, load_music
from script.common.logger import AppLogger

logger = AppLogger()


def _run(log):
    """设置日志并返回（供 CLI 注入打印日志）。"""
    global logger
    if log is not None:
        logger = log


def organize(
    root_dir: str,
    out_dir: str,
    mode: str = "歌手/专辑",
    operation: str = "move",
    log=None,
    progress_cb=None,
):
    """执行整理。

    参数:
        root_dir   : 音乐目录
        out_dir    : 输出目录
        mode       : "歌手/专辑" | "歌手" | "专辑"
        operation  : "move" | "copy"
        log        : 日志函数（AppLogger 或 callable，缺省用 AppLogger 默认打印）
        progress_cb: 可选进度回调 (done, total)
    """
    global logger
    logger = log if log is not None else AppLogger()

    if not root_dir or not out_dir:
        logger.warning("请先指定音乐目录与输出目录\n")
        return 0

    # O4: move 模式且输出目录位于音乐目录内部 → 易造成自我嵌套/边扫边移，提示改用 copy 或换输出目录
    if operation == "move":
        r = os.path.realpath(root_dir)
        o = os.path.realpath(out_dir)
        if o.startswith(r + os.sep) or o == r:
            logger.warning("⚠️ 输出目录在音乐目录内部，move 可能乱序；建议改用 copy 或选外部输出目录\n")

    logger.info("扫描音乐库...")
    songs = load_music(root_dir, log=logger)
    total = len(songs)
    logger.info(f"    共发现 {total} 首歌曲\n")

    for idx, song in enumerate(songs):
        try:
            src = song["path"]
            base, ext = os.path.splitext(src)  # O3: 比 src.split('.')[-1] 更稳
            title = song.get("title", "未知歌曲")
            artist = song.get("artist", "未知歌手")
            album = song.get("album", "未知专辑")

            filename = f"{artist} - {title}{ext}" if ext else f"{artist} - {title}"

            if mode == "歌手/专辑":
                dst_dir = os.path.join(out_dir, split_artists(artist)[0], album)
            elif mode == "歌手":
                dst_dir = os.path.join(out_dir, split_artists(artist)[0])
            else:  # 专辑
                dst_dir = os.path.join(out_dir, album)

            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, filename)

            # B3: 目标已存在且不是同一文件 → 加序号，避免覆盖
            if os.path.exists(dst) and os.path.abspath(src) != os.path.abspath(dst):
                stem, e = os.path.splitext(filename)
                n = 1
                while os.path.exists(os.path.join(dst_dir, f"{stem}_{n}{e}")):
                    n += 1
                dst = os.path.join(dst_dir, f"{stem}_{n}{e}")

            if src == dst:
                continue

            if operation == "move":
                shutil.move(src, dst)
                action = "移动"
            else:
                shutil.copy2(src, dst)
                action = "复制"

            logger.info(f"    {action}: {filename}")

            if progress_cb:
                progress_cb(idx + 1, total)

        except Exception as e:
            logger.exception(e)

    logger.info("整理完成\n")
    return total


# ---------------- CLI ----------------
def main():
    import argparse

    p = argparse.ArgumentParser(
        description="音乐整理核心（按 歌手/专辑 移动/复制）"
    )
    p.add_argument("music_dir", help="音乐目录")
    p.add_argument("output_dir", help="输出目录")
    p.add_argument(
        "--mode",
        default="歌手/专辑",
        choices=["歌手/专辑", "歌手", "专辑"],
        help="整理方式（默认 歌手/专辑）",
    )
    p.add_argument(
        "--op",
        default="move",
        choices=["move", "copy"],
        help="文件处理（默认 move）",
    )
    args = p.parse_args()

    organize(
        args.music_dir,
        args.output_dir,
        mode=args.mode,
        operation=args.op,
    )


if __name__ == "__main__":
    main()
