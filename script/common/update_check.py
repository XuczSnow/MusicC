# -*- coding: utf-8 -*-
"""update_check.py — 启动时检查软件与 go-music-api 是否有新版本。

设计：
  - 全部网络请求在后台线程调用，不阻塞 UI；结果通过调用方（主线程 after）呈现。
  - 查 GitHub latest release（两个仓库各一次）。
  - go-music-api 本地版本：优先从 bin/ 下可选的 version.txt 读取；
    若没有则标记为"未知"，仍提示"可前往 GitHub 查看最新版"。

返回结构（dict）：
  {
    "software": {"latest": "v1.3.0", "current": "1.2.0", "has_update": True,
                  "url": "https://github.com/XuczSnow/MusicC/releases/tag/v1.3.0",
                  "ok": True},
    "gomusic":  {"latest": "v1.0.2", "current": "unknown", "has_update": False,
                  "url": "...", "ok": True},
    "error": None,
  }
"""

import json
import os
import re
import zipfile
import tempfile
import shutil
import requests

from script.common.version import (
    SOFTWARE_VERSION,
    SOFTWARE_REPO,
    GOMUSIC_REPO,
    GOMUSIC_LOCAL_BIN,
    GOMUSIC_RELEASES_URL,
    software_version_str,
    is_newer,
)

_GH_RELEASES = "https://api.github.com/repos/{repo}/releases/latest"
_TIMEOUT = 8
_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "MusicC-updater"}


def _latest_release(repo: str, log=None):
    """取仓库最新 release 的 (tag, html_url)。失败返回 (None, None)。"""
    try:
        r = requests.get(_GH_RELEASES.format(repo=repo), headers=_HEADERS, timeout=_TIMEOUT)
        if r.status_code == 403:
            if log:
                log(f"    更新检查 {repo}: GitHub 限流(403)，稍后重试\n")
            return None, None
        if r.status_code != 200:
            return None, None
        data = r.json()
        return data.get("tag_name"), data.get("html_url")
    except Exception as e:
        if log:
            log(f"    更新检查 {repo} 失败: {e}\n")
        return None, None


def _read_local_api_version() -> str:
    """读取本地 go-music-api 版本。优先 bin/<...>/version.txt，否则 'unknown'。"""
    from script.music.load_music import resource_path

    # version.txt 与 exe 同目录（若存在）
    vfile = os.path.join(os.path.dirname(GOMUSIC_LOCAL_BIN), "version.txt")
    try:
        p = resource_path(vfile)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                txt = f.read().strip()
                if txt:
                    return txt if txt.startswith("v") or txt.isdigit() else f"v{txt}"
    except Exception:
        pass
    return "unknown"


def check_updates(log=None):
    """检查软件 + go-music-api 更新。可在子线程调用。返回结果 dict。"""
    log = log or (lambda *_: None)

    api_version = _read_local_api_version()

    sw_tag, sw_url = _latest_release(SOFTWARE_REPO, log)
    gm_tag, gm_url = _latest_release(GOMUSIC_REPO, log)

    sw_ok = sw_tag is not None
    gm_ok = gm_tag is not None

    sw_has_update = bool(sw_ok and is_newer(sw_tag, SOFTWARE_VERSION))
    gm_has_update = bool(gm_ok and api_version != "unknown" and is_newer(gm_tag, api_version))
    # 本地 API 版本未知时，不判定"有更新"，但标记 unknown 让 UI 提示可前往查看

    result = {
        "software": {
            "latest": sw_tag or "unknown",
            "current": SOFTWARE_VERSION,
            "has_update": sw_has_update,
            "url": sw_url,
            "ok": sw_ok,
        },
        "gomusic": {
            "latest": gm_tag or "unknown",
            "current": api_version,
            "has_update": gm_has_update,
            "url": gm_url or GOMUSIC_RELEASES_URL,
            "ok": gm_ok,
            "local_unknown": api_version == "unknown",
        },
        "error": None,
    }

    if not sw_ok and not gm_ok:
        result["error"] = "网络检查失败（GitHub API 不可达）"

    log(
        f"更新检查: 软件 {SOFTWARE_VERSION}→{result['software']['latest']}"
        f" (有更新:{sw_has_update}); "
        f"go-music-api {api_version}→{result['gomusic']['latest']}"
        f" (有更新:{gm_has_update})\n"
    )
    return result


def any_update(result) -> bool:
    """是否有任一组件存在更新（或本地 API 版本未知需手动确认）。"""
    if not isinstance(result, dict):
        return False
    return result["software"].get("has_update") or result["gomusic"].get("has_update")


# ============ go-music-api 自动更新 ============
# Windows 版 release asset：go-music-api_windows_amd64.zip
# 解压后得到 go-music-api.exe，覆盖到 bin/go-music-api_windows_amd64/ 并写 version.txt
_WIN_ASSET = "go-music-api_windows_amd64.zip"
_DL_BASE = f"https://github.com/{GOMUSIC_REPO}/releases/download"


def download_and_update_api(latest_tag: str, log=None) -> bool:
    """下载 go-music-api 最新 Windows 版并更新本地 bin/ + version.txt。

    在后台线程调用。成功返回 True；失败/无 asset 返回 False。
    会保留 bin/go-music-api_windows_amd64/ 下原有的 LICENSE/README 等文件，
    只替换可执行文件（go-music-api.exe）。
    """
    log = log or (lambda *_: None)
    from script.music.load_music import resource_path

    bin_dir = os.path.dirname(resource_path(GOMUSIC_LOCAL_BIN))
    exe_dst = os.path.join(bin_dir, "go-music-api.exe")
    if not os.path.isdir(bin_dir):
        log(f"    自动更新: bin 目录不存在 {bin_dir}\n")
        return False

    url = f"{_DL_BASE}/{latest_tag}/{_WIN_ASSET}"
    log(f"    自动更新 go-music-api {latest_tag} ... {url}\n")

    try:
        # 1. 下载到临时 zip
        tmp_zip = os.path.join(tempfile.gettempdir(), "musicc_gomusic.zip")
        with requests.get(url, stream=True, timeout=60) as r:
            if r.status_code != 200:
                log(f"    自动更新失败: HTTP {r.status_code}\n")
                return False
            with open(tmp_zip, "wb") as f:
                for chunk in r.iter_content(1024 * 1024):
                    if chunk:
                        f.write(chunk)

        # 2. 解压，找到 go-music-api.exe 覆盖目标
        with zipfile.ZipFile(tmp_zip) as zf:
            for name in zf.namelist():
                base = os.path.basename(name)
                if base.lower().endswith(".exe"):
                    with zf.open(name) as src, open(exe_dst, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    log(f"    已更新可执行文件: {exe_dst}\n")
                    break
            else:
                log(f"    自动更新失败: zip 内未找到 go-music-api.exe\n")
                return False

        # 3. 写 version.txt（带 v 前缀，与 GitHub tag 一致）
        vfile = os.path.join(bin_dir, "version.txt")
        with open(vfile, "w", encoding="utf-8") as f:
            f.write(latest_tag if latest_tag.lower().startswith("v") else f"v{latest_tag}")
        log(f"    已写入版本: {vfile} = {latest_tag}\n")

        os.remove(tmp_zip)
        return True
    except Exception as e:
        log(f"    自动更新 go-music-api 失败: {e}\n")
        return False
