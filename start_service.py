import subprocess
import time
import requests

api_process = None

_logger = print  # ✅ 默认用print

def set_logger(func):
    global _logger
    _logger = func

def start_go_music_api(log = None):

    global api_process

    set_logger(log)
    
    try:
        # ✅ 检查服务是否已经启动
        r = requests.get("http://localhost:8080/api/v1/system/cookies")
        print(r)
        if r.status_code == 200:
            _logger("✅ go-music-api 已经运行")
            return
    except:
        pass

    _logger("🚀 启动 go-music-api...")

    api_process = subprocess.Popen(
        "./bin/go-music-api_windows_amd64/go-music-api.exe",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # ✅ 等待服务启动
    for i in range(10):
        try:
            r = requests.get("http://localhost:8080/api/v1/system/cookies")
            print(r)
            if r.status_code == 200:
                _logger("✅ 启动成功")
                return
        except:
            pass

        time.sleep(1)

    _logger("❌ 启动失败")

def stop_go_music_api():

    global api_process

    if api_process and api_process.poll() is None:
        print("🛑 关闭 go-music-api...")
        api_process.terminate()   # ✅ 温和关闭

        try:
            api_process.wait(timeout=5)
        except:
            api_process.kill()  # ✅ 强制关闭（兜底）

        print("✅ 已关闭")

