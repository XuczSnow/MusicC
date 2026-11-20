# -*- coding: utf-8 -*-
"""
asr_align.py
AI 歌词对齐 / 增补模块。

功能：
  - 惰性加载 faster-whisper（重依赖，仅在实际调用 ASR 时才加载，避免拖慢启动）
  - GPU 自动探测回退：优先 cuda(float16)，失败退回 cpu(int8)
  - transcribe_head(audio, seconds)：识别前 N 秒，用于"前 3 句"对齐校验
  - transcribe_full(audio) → (text, lrc)：全曲识别，生成纯文本 + 同步 LRC
  - align_first_lines(asr_text, net_sync, top_k=3)：前 K 句模糊匹配判定对齐
  - ASR 结果缓存（按 艺术家-标题-时长），命中不重算
  - 写 LRC 到 FLAC/MP3 标签

设计原则：
  - 不改变现有纯文本歌词流程；仅当勾选「AI 同步/增补」时才触发
  - 模型规格/设备可通过 init 参数配置
"""

import os
import re
import difflib
from pathlib import Path

from script.common.cache_manager import JsonCache
from script.music.load_music import to_simplified, clean_text

# ===== 模块级惰性状态 =====
_whisper_model = None
_whisper_device = "cpu"
_whisper_compute = "int8"
_WHISPER_READY = False

# ASR 结果缓存（本地算力产物，不走网络限流）
_asr_cache = JsonCache("cahce/song_cache_asr.json")


# ------------------------------------------------------------------
# 本地模型目录解析
# ------------------------------------------------------------------
def _model_root(model_size: str = "small") -> Path:
    return Path(__file__).resolve().parents[2] / "models" / f"faster-whisper-{model_size}"


def _local_model_dir(model_size: str = "small") -> str | None:
    """返回项目内 models/faster-whisper-{size} 的绝对路径（存在则用，离线可用）。

    以本文件所在目录(script/music/asr_align.py)向上 3 级定位项目根。
    """
    try:
        cand = _model_root(model_size)
        if cand.is_dir() and (cand / "model.bin").exists():
            return str(cand)
    except Exception:
        pass
    return None


# ------------------------------------------------------------------
# 模型加载（惰性 + 本地优先 + GPU 自动回退）
# ------------------------------------------------------------------
def _ensure_whisper(model_size: str = "small"):
    """首次调用时加载 faster-whisper 模型。

    加载优先级：
      1. 本地 models/faster-whisper-{size}（存在则离线加载）
      2. 本地缺失时下载到 models/faster-whisper-{size}（需联网）
    设备自动探测回退：cuda/float16 → cpu/int8。
    返回 (model, device, compute_type)。
    """
    global _whisper_model, _whisper_device, _whisper_compute, _WHISPER_READY
    if _WHISPER_READY and _whisper_model is not None:
        return _whisper_model, _whisper_device, _whisper_compute

    from faster_whisper import WhisperModel  # 重库，惰性导入

    model_root = _model_root(model_size)
    local_dir = _local_model_dir(model_size)
    # 本地目录存在 → 用本地路径；否则用模型名走 HF 下载
    model_arg = local_dir if local_dir else model_size

    cands = [
        ("cuda", "float16"),
        ("cpu", "int8"),
    ]
    last_err = None
    for device, compute in cands:
        try:
            _whisper_model = WhisperModel(
                model_arg,
                device=device,
                compute_type=compute,
                download_root=str(model_root),
            )
            _whisper_device = device
            _whisper_compute = compute
            _WHISPER_READY = True
            return _whisper_model, _whisper_device, _whisper_compute
        except Exception as e:  # GPU 不可用 / 模型缺失等，继续回退
            last_err = e
            continue

    raise RuntimeError(
        f"faster-whisper 加载失败（GPU 与 CPU 均不可用）: {last_err}"
    )


# ------------------------------------------------------------------
# 音频解码（供 whisper 直接读文件）
# ------------------------------------------------------------------
def _audio_path(audio):
    """audio 为 mutagen 对象或路径字符串，返回可读取的路径。"""
    if isinstance(audio, (str, Path)):
        return str(audio)
    return getattr(audio, "path", None) or getattr(audio, "filename", None)


# ------------------------------------------------------------------
# 识别 → LRC
# ------------------------------------------------------------------
def _to_lrc(segments) -> str:
    """whisper segments（含 start/end/text）转 LRC 文本。"""
    lines = []
    for seg in segments:
        start = seg.start
        mm, ss = divmod(int(start), 60)
        ms = int(round((start - int(start)) * 1000))
        text = (seg.text or "").strip()
        if not text:
            continue
        lines.append(f"[{mm:02d}:{ss:02d}.{ms:03d}] {text}")
    return "\n".join(lines)


def align_lyric_to_audio(lyric: str, audio, model_size: str = "small",
                         threshold: float = 0.35) -> str:
    """把**已有纯文本歌词**逐行对齐音频时间戳，生成 LRC（保留原歌词字句）。

    用于"歌词非空但无 [m:ss] 时间戳"的情况：不重新识别文本，
    只把每行歌词匹配到 ASR 句段，取该段开始时间作为时间戳。
    匹配不上的行沿用上一行时间 +1s 兜底，保证 LRC 单调递增。
    无法对齐（ASR 无段）时返回 ""。
    """
    import difflib

    if not lyric or not lyric.strip():
        return ""
    model, device, compute = _ensure_whisper(model_size)
    path = _audio_path(audio)
    segments, _info = model.transcribe(
        path,
        language="zh" if _looks_chinese(path) else None,
        vad_filter=True,
        word_timestamps=False,
    )
    asr_segs = [(s.start, s.end, _norm(s.text)) for s in segments if s.text.strip()]
    if not asr_segs:
        return ""

    # 歌词行：去掉可能已存在的 [..] 时间戳，取纯文本行
    raw_lines = [re.sub(r"^\[[\d:.]+\]\s*", "", l).strip() for l in lyric.splitlines()]
    lyric_lines = [l for l in raw_lines if l]
    if not lyric_lines:
        return ""

    lines_out = []
    last_time = 0.0
    last_seg_idx = -1
    for line in lyric_lines:
        ln = _norm(line)
        if not ln:
            last_time = max(last_time, last_time + 1.0)
            _emit(line, last_time, lines_out)
            continue
        # 在 ASR 段里找与该行最相似的段（限制在上一匹配段之后，歌词顺序≈音频顺序）
        best_ratio, best_time = 0.0, None
        start_scan = max(0, last_seg_idx + 1 - 3)  # 允许回看 3 段
        for i in range(start_scan, len(asr_segs)):
            st, en, txt = asr_segs[i]
            if st > last_time + 30:  # 太远就不再往后找
                break
            r = difflib.SequenceMatcher(None, ln, txt).ratio()
            if r > best_ratio:
                best_ratio, best_time, best_idx = r, st, i
        if best_ratio >= threshold:
            last_time = best_time
            last_seg_idx = best_idx
        else:
            last_time = last_time + 1.0  # 匹配不上，递增兜底
        _emit(line, last_time, lines_out)
    return "\n".join(lines_out)


def _emit(line: str, t: float, out: list) -> None:
    mm, ss = divmod(int(t), 60)
    ms = int(round((t - int(t)) * 1000))
    if ms >= 1000:
        mm, ss, ms = mm + 1, 0, 0
    out.append(f"[{mm:02d}:{ss:02d}.{ms:03d}] {line}")


def transcribe_head(audio, seconds: int = 30, model_size: str = "small"):
    """识别音频前 seconds 秒，返回 (text, lrc)。用于前 3 句对齐校验。"""
    model, device, compute = _ensure_whisper(model_size)
    path = _audio_path(audio)
    segments, _info = model.transcribe(
        path,
        language="zh" if _looks_chinese(path) else None,
        vad_filter=True,
        word_timestamps=False,
    )
    segs = []
    for seg in segments:
        if seg.start >= seconds:
            break
        segs.append(seg)
    text = " ".join(s.text.strip() for s in segs if s.text.strip())
    return text, _to_lrc(segs)


def transcribe_full(audio, model_size: str = "small"):
    """全曲识别，返回 (text, lrc)。用于 AI 增补 / 对齐兜底。"""
    model, device, compute = _ensure_whisper(model_size)
    path = _audio_path(audio)
    segments, _info = model.transcribe(
        path,
        language="zh",
        vad_filter=True,
        word_timestamps=False,
    )
    segs = list(segments)
    text = "\n".join(s.text.strip() for s in segs if s.text.strip())
    return text, _to_lrc(segs)


def _looks_chinese(path: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", os.path.basename(path or "")))


# ------------------------------------------------------------------
# 前 K 句对齐判定
# ------------------------------------------------------------------
def _norm(s: str) -> str:
    """归一化：繁转简 + 去标点/空白，仅保留文字与数字。"""
    s = to_simplified(s or "")
    s = re.sub(r"[^\w\u4e00-\u9fff]", "", s, flags=re.UNICODE)
    return s.lower()


def _to_chars(s: str):
    """归一化后拆成字符列表（中文按字、英文按词），便于按 token 比较。"""
    return list(_norm(s))


def align_first_lines(
    asr_text: str,
    net_sync: str,
    top_k: int = 3,
    threshold: float = 0.7,
) -> bool:
    """判断 ASR 识别结果与网络同步歌词是否对齐。

    ASR 文本是空格串（单行或几行），网络 LRC 是逐行带时间戳。
    策略：把两边的字符流都归一化成"字符序列"，取前 N 个字符做相似度。
    若前 N 字符相似度 >= threshold，认为"前几句对得上"，可信任网络 LRC。

    N = 前 top_k 句近似长度（按字符数）。用前 24 个归一化字符作为窗口。
    """
    if not asr_text or not net_sync:
        return False

    # ASR 侧：整段文字归一化
    asr_chars = _to_chars(asr_text)
    # 网络 LRC 侧：剥掉 [mm:ss.xx]，合并所有行的文字归一化
    net_chars_list = []
    for l in net_sync.splitlines():
        m = re.sub(r"^\[[\d:.]+\]\s*", "", l.strip())
        net_chars_list.append(_to_chars(m))
    # 把所有 LRC 行拼成一条字符流（顺序即歌词顺序）
    net_chars = [c for seg in net_chars_list for c in seg]

    if not asr_chars or not net_chars:
        return False

    # 取前 24 个字符窗口做相似度（避免 ASR 把多行合一行导致长度差异）
    window = 24
    a = asr_chars[:window]
    n = net_chars[:window]
    if not a or not n:
        return False
    ratio = difflib.SequenceMatcher(None, a, n).ratio()
    return ratio >= threshold


# ------------------------------------------------------------------
# 缓存包装（供 metadata_page 调用）
# ------------------------------------------------------------------
def asr_cache_key(artist: str, title: str, duration: int) -> str:
    return f"{artist}-{title}-{int(duration or 0)}"


def get_cached_asr(artist, title, duration):
    """返回缓存的 {text, lrc} 或 None。"""
    s = _asr_cache.get(asr_cache_key(artist, title, duration))
    if s and s.get("lrc"):
        return s
    return None


def set_cached_asr(artist, title, duration, text, lrc):
    _asr_cache.set(
        asr_cache_key(artist, title, duration),
        {"text": text, "lrc": lrc, "device": _whisper_device},
    )


def save_cache():
    _asr_cache.save()


# ------------------------------------------------------------------
# 写 LRC 到标签（FLAC lyrics / MP3 USLT）
# 显式传入重库类，由调用方先 _import_tag_libs() 再取用
# ------------------------------------------------------------------
def write_lrc(
    FLAC,
    MP3,
    USLT,
    song,
    lrc_text: str,
    overwrite: bool = False,
):
    """把 LRC 同步歌词写入标签。

    FLAC/MP3/USLT: mutagen 类（由 metadata_page._import_tag_libs 提供）
    song: get_song_info 返回的 dict（含 path / lyric 等）
    lrc_text: 同步歌词文本（[mm:ss.xx] ...）
    """
    if not lrc_text:
        return False
    path = song["path"]

    if path.lower().endswith(".flac"):
        audio = FLAC(path)
        if overwrite or not song.get("lyric"):
            audio["lyrics"] = lrc_text
            audio.save()
            return True
    elif path.lower().endswith(".mp3"):
        audio = MP3(path)
        if overwrite or not song.get("lyric"):
            audio.tags.delall("USLT")
            audio.tags.add(USLT(encoding=3, text=lrc_text))
            audio.save()
            return True
    return False
