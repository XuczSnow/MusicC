import subprocess
import time
import requests

# ✅ 启动性能：仅导入需要的 resource_path，避免 star-import 触发
#    load_music → mutagen/regex/hanziconv 等重依赖在启动关键路径加载
from script.music.load_music import resource_path

api_process = None

_logger = print  # ✅ 默认用print

# ✅ 健康检查：服务"在跑"= 能连上并返回任意 HTTP 响应（正常为 200）。
# 只有"连不上"（ConnectionError）才说明没起。
_HEALTH_URL = "http://localhost:8080/api/v1/system/cookies"


def _api_alive():
    """返回 True 表示 go-music-api 在运行。

    判定：2xx/3xx 且响应体是 JSON 或空。
    407/500/502 等一律判死（McAfee 代理劫持 localhost 会返回 407 + HTML）。
    """
    try:
        r = requests.get(_HEALTH_URL, timeout=3)
        if r.status_code >= 400:
            return False
        ct = (r.headers.get("Content-Type") or "").lower()
        # HTML 响应体（代理网关/错误页）不算存活
        if "text/html" in ct and r.text.strip():
            return False
        return True
    except requests.exceptions.ConnectionError:
        return False
    except Exception:
        return False


def set_logger(func):
    global _logger
    _logger = func.info if func is not None else print

def start_go_music_api(log = None, label = None):
    """启动/确认 go-music-api。⚠️ 可能在子线程调用，内部不得触碰任何 Tk widget。
    返回状态字符串（'API运行中' / 'API未启动, 请重启软件'），由调用方在主线程更新 UI。"""

    global api_process

    set_logger(log)

    # ✅ 检查服务是否已经启动（能连上即算运行）
    if _api_alive():
        _logger("go-music-api 已运行\n")
        return "API运行中"

    _logger("启动 go-music-api...")

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    api_process = subprocess.Popen(
        [resource_path("./bin/go-music-api_windows_amd64/go-music-api.exe")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    # ✅ 等待服务启动：前密后疏（前 4 次 0.2s，后 6 次 0.5s，总 ~6.8s）
    for i in range(10):
        if _api_alive():
            _logger("go-music-api 启动成功\n")
            return "API运行中"
        _logger(f"等待启动({i+1}/10)...\n")
        time.sleep(0.2 if i < 4 else 0.5)

    _logger("启动失败")
    return "API未启动, 请重启软件"

def stop_go_music_api():

    global api_process

    if api_process and api_process.poll() is None:
        _logger("关闭 go-music-api...\n")
        api_process.terminate()   # ✅ 温和关闭

        try:
            api_process.wait(timeout=5)
        except:
            api_process.kill()  # ✅ 强制关闭（兜底）

        _logger("已关闭\n")

