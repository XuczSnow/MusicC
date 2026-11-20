# -*- coding: utf-8 -*-
"""version.py — 单一版本信息源（避免版本号散落在多处）。

软件与 go-music-api 的版本、仓库地址统一在此维护；
update_check.py 与 about_page.py 都从这里读取。
"""

import re

# ============ 软件 ============
# 软件当前版本（与 release_note 保持一致）
SOFTWARE_VERSION = "1.2.0"

# 软件 GitHub 仓库（用于查最新 release 与跳转）
SOFTWARE_REPO = "XuczSnow/MusicC"
SOFTWARE_GITHUB_URL = f"https://github.com/{SOFTWARE_REPO}"
SOFTWARE_RELEASES_URL = f"{SOFTWARE_GITHUB_URL}/releases"

# ============ go-music-api ============
# go-music-api GitHub 仓库
GOMUSIC_REPO = "guohuiyuan/go-music-api"
GOMUSIC_GITHUB_URL = f"https://github.com/{GOMUSIC_REPO}"
GOMUSIC_RELEASES_URL = f"{GOMUSIC_GITHUB_URL}/releases"

# 本地 go-music-api 二进制路径（相对项目根）
GOMUSIC_LOCAL_BIN = "bin/go-music-api_windows_amd64/go-music-api.exe"


def software_version_str() -> str:
    """带 v 前缀的软件版本，如 'v1.2.0'。"""
    return f"v{SOFTWARE_VERSION}"


# ============ 版本比较 ============
def _to_tuple(v: str):
    """把 'v1.2.0' / '1.2.0' / 'v2' / 'v1.0.2-rc1' 解析为 (major, minor, patch)。"""
    if not v:
        return (0, 0, 0)
    v = str(v).lstrip("vV").strip()
    # 只取第一段（-rc / +build 等后缀之前的部分），保留完整数字序列
    v = re.split(r"[-+]", v)[0]
    nums = re.findall(r"\d+", v)
    if not nums:
        return (0, 0, 0)
    nums = (nums + ["0", "0", "0"])[:3]
    return tuple(int(x) for x in nums)


def is_newer(latest: str, current: str) -> bool:
    """latest 是否比 current 新（版本号比较，非字符串比较）。"""
    return _to_tuple(latest) > _to_tuple(current)
