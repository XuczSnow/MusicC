# -*- coding: utf-8 -*-
"""
audio_classify.py — 音频分类核心（PANNs 优先，librosa 声学启发式兜底）。

设计：
  - 本地无 PANNs 权重时按需从 Hugging Face 下载到 models/panns_Cnn14/
  - PANNs 可用时出 527 类标签概率；下载或加载失败时回退 librosa 声学启发式
  - 两者都通过 pann_tag_map 聚合到本项目中文标签
  - 结果缓存（路径+大小+mtime），避免重复推理

惰性加载，未启用「音频分类」时零成本。
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from script.common.cache_manager import JsonCache
from script.common.logger import AppLogger
from cores.pann_tag_map import PANNS_TO_CN, PANNS_WEIGHT

logger = AppLogger()

# ===== 惰性状态 =====
_backend = None            # "panns" | "librosa"
_panns_model = None
_panns_labels = None
_panns_device = "cpu"
_READY = False

_audio_cache = JsonCache("cahce/song_cache_audio.json")
_MODEL_DIR = os.path.join(_ROOT, "models", "panns")
_PANNS_MODEL_DIR = os.path.join(_ROOT, "models", "panns_Cnn14")
_PANNS_REPO_ID = "nicofarr/panns_Cnn14"


# ------------------------------------------------------------------
# PANNs Cnn14（官方 qiuqiangkong/audioset_tagging_cnn 定义，自包含）
# 依赖 torchlibrosa（Spectrogram / LogmelFilterBank）
# ------------------------------------------------------------------
def _build_official_cnn14(mel_bins=64):
    """官方 PANNs Cnn14（qiuqiangkong/audioset_tagging_cnn）。

    nicofarr 的 panns_Cnn14 用 mel_bins=64、n_fft=1024、hop=320、sr=32000、527 类。
    依赖 torchlibrosa（Spectrogram / LogmelFilterBank / SpecAugmentation）。
    """
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torchlibrosa.stft import Spectrogram, LogmelFilterBank
    from torchlibrosa.augmentation import SpecAugmentation

    def init_layer(layer):
        nn.init.xavier_uniform_(layer.weight)
        if hasattr(layer, "bias") and layer.bias is not None:
            layer.bias.data.fill_(0.)

    def init_bn(bn):
        bn.bias.data.fill_(0.)
        bn.weight.data.fill_(1.)

    class ConvBlock(nn.Module):
        def __init__(self, in_c, out_c):
            super().__init__()
            self.conv1 = nn.Conv2d(in_c, out_c, (3, 3), (1, 1), (1, 1), bias=False)
            self.conv2 = nn.Conv2d(out_c, out_c, (3, 3), (1, 1), (1, 1), bias=False)
            self.bn1 = nn.BatchNorm2d(out_c)
            self.bn2 = nn.BatchNorm2d(out_c)
            init_layer(self.conv1); init_layer(self.conv2); init_bn(self.bn1); init_bn(self.bn2)

        def forward(self, x, pool_size=(2, 2), pool_type="avg"):
            x = F.relu_(self.bn1(self.conv1(x)))
            x = F.relu_(self.bn2(self.conv2(x)))
            x = F.max_pool2d(x, pool_size) if pool_type == "max" else F.avg_pool2d(x, pool_size)
            return x

    class Cnn14(nn.Module):
        def __init__(self, sample_rate=32000, window_size=1024, hop_size=320,
                     mel_bins=64, fmin=50, fmax=14000, classes_num=527):
            super().__init__()
            self.spectrogram_extractor = Spectrogram(
                n_fft=window_size, hop_length=hop_size, win_length=window_size,
                window="hann", center=True, pad_mode="reflect", freeze_parameters=False)
            self.logmel_extractor = LogmelFilterBank(
                sr=sample_rate, n_fft=window_size, n_mels=mel_bins, fmin=fmin, fmax=fmax,
                ref=1.0, amin=1e-10, top_db=None, freeze_parameters=False)
            self.spec_augmenter = SpecAugmentation(
                time_drop_width=64, time_stripes_num=2, freq_drop_width=8, freq_stripes_num=2)
            self.bn0 = nn.BatchNorm2d(64)
            self.conv_block1 = ConvBlock(1, 64)
            self.conv_block2 = ConvBlock(64, 128)
            self.conv_block3 = ConvBlock(128, 256)
            self.conv_block4 = ConvBlock(256, 512)
            self.conv_block5 = ConvBlock(512, 1024)
            self.conv_block6 = ConvBlock(1024, 2048)
            self.fc1 = nn.Linear(2048, 2048, bias=True)
            self.fc_audioset = nn.Linear(2048, classes_num, bias=True)
            init_bn(self.bn0); init_layer(self.fc1); init_layer(self.fc_audioset)

        def forward(self, x):
            # x: (batch, data_length) 波形
            x = self.spectrogram_extractor(x)
            x = self.logmel_extractor(x)
            x = x.transpose(1, 3)
            x = self.bn0(x)
            x = x.transpose(1, 3)
            x = self.conv_block1(x, (2, 2), "avg"); x = F.dropout(x, 0.2, self.training)
            x = self.conv_block2(x, (2, 2), "avg"); x = F.dropout(x, 0.2, self.training)
            x = self.conv_block3(x, (2, 2), "avg"); x = F.dropout(x, 0.2, self.training)
            x = self.conv_block4(x, (2, 2), "avg"); x = F.dropout(x, 0.2, self.training)
            x = self.conv_block5(x, (2, 2), "avg"); x = F.dropout(x, 0.2, self.training)
            x = self.conv_block6(x, (1, 1), "avg"); x = F.dropout(x, 0.2, self.training)
            x = torch.mean(x, dim=3)
            x1, _ = torch.max(x, dim=2)
            x = x1 + x.mean(dim=2)
            x = F.dropout(x, 0.5, self.training)
            x = F.relu_(self.fc1(x))
            return torch.sigmoid(self.fc_audioset(x))

    return Cnn14()


# ------------------------------------------------------------------
# PANNs 加载（本地优先；缺失时自动下载，失败后回退 librosa）
# ------------------------------------------------------------------
def _find_panns_weights():
    """定位模型目录（models/panns_Cnn14 或 models/panns/...），返回 (权重, 标签) 路径。"""
    cands = [
        _PANNS_MODEL_DIR,
        os.path.join(_ROOT, "models", "panns", "panns_Cnn14"),
        os.path.join(_ROOT, "models", "panns"),
    ]
    for d in cands:
        if not os.path.isdir(d):
            continue
        w = None
        for f in ("model.safetensors", "panns_cnn14.pt", "panns_cnn14.pth"):
            if os.path.exists(os.path.join(d, f)):
                w = os.path.join(d, f)
                break
        t = None
        for f in ("tags.txt", "panns_cnn14_tags.txt"):
            if os.path.exists(os.path.join(d, f)):
                t = os.path.join(d, f)
                break
        if w:
            return w, t
    return None, None


def _load_panns_state_dict(path):
    import torch
    if path.endswith(".safetensors"):
        from safetensors.torch import load_file
        return load_file(path)
    return torch.load(path, map_location="cpu")


def _ensure_backend():
    global _backend, _panns_model, _panns_labels, _panns_device, _READY
    if _READY:
        return _backend

    weights, tags = _find_panns_weights()
    if not weights:
        try:
            from huggingface_hub import snapshot_download

            snapshot_download(repo_id=_PANNS_REPO_ID, local_dir=_PANNS_MODEL_DIR)
            weights, tags = _find_panns_weights()
            if not weights:
                raise FileNotFoundError(
                    f"PANNs 仓库 {_PANNS_REPO_ID} 中未找到可识别的模型权重"
                )
        except Exception as e:
            logger.warning(f"PANNs 自动下载失败，回退 librosa 声学启发式: {e}")

    if weights:
        try:
            import torch
            _panns_device = "cuda" if torch.cuda.is_available() else "cpu"
            model = _build_official_cnn14(mel_bins=64)
            sd = _load_panns_state_dict(weights)
            # 兼容前缀：kynxio 的权重带 "backbone."，官方的无前缀
            if any(k.startswith("backbone.") for k in sd):
                sd = {k[len("backbone."):]: v for k, v in sd.items()}
            elif any(k.startswith("module.") for k in sd):
                sd = {k[len("module."):]: v for k, v in sd.items()}
            missing, unexpected = model.load_state_dict(sd, strict=False)
            if len(missing) > 0:
                logger.warning(f"PANNs load_state_dict 缺失 {len(missing)} 键: {missing[:5]}")
            if len(unexpected) > 0:
                logger.warning(f"PANNs load_state_dict 多 {len(unexpected)} 键: {unexpected[:5]}")
            model.eval()
            model.to(_panns_device)
            _panns_model = model
            _panns_labels = None
            if tags:
                _panns_labels = [l.strip() for l in open(tags, encoding="utf-8") if l.strip()]
            _backend = "panns"
            _READY = True
            logger.info(f"PANNs 已加载: {os.path.basename(weights)} @ {_panns_device} "
                        f"(labels={len(_panns_labels or [])})")
            return _backend
        except Exception as e:
            logger.warning(f"PANNs 加载失败，回退 librosa 声学启发式: {e}")

    _backend = "librosa"
    _READY = True
    return _backend


# ------------------------------------------------------------------
# 声学特征（librosa 兜底）→ 粗粒度情绪
# ------------------------------------------------------------------
def _librosa_tags(path):
    import librosa
    import numpy as np

    try:
        y, sr = librosa.load(path, sr=20480, duration=30)
    except Exception as e:
        logger.exception(e)
        return []

    if len(y) < 100:
        return []

    rms = float(np.mean(np.abs(y)))
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(y)))
    spec_cent = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    tempo = float(librosa.feature.tempo(y=y, sr=sr)[0]) if len(y) > 2 else 0.0

    energy = min(rms / 0.15, 1.0)
    fast = min(tempo / 180.0, 1.0)
    bright = min(spec_cent / 3000.0, 1.0)
    calm = 1.0 - min(energy, fast)

    scores = {
        "Happy": min(0.5 + 0.4 * (bright * 0.5 + fast * 0.5), 1.0),
        "Sad": min(0.3 + 0.5 * (1.0 - bright) * (1.0 - fast), 1.0),
        "Calm": min(calm, 1.0),
        "Tense": min(0.3 + 0.5 * fast, 1.0),
        "Aggressive": min(0.3 + 0.6 * energy * fast, 1.0),
        "Energizing": min(0.4 + 0.5 * fast, 1.0),
        "Peaceful": min(0.3 + 0.5 * (1.0 - energy), 1.0),
        "Rock": min(0.2 + 0.6 * energy, 1.0) if fast > 0.6 else 0.0,
        "Pop": 0.3,
        "Piano": 0.2 * (1.0 - zcr),
        "Guitar": 0.2 * (1.0 - fast),
    }
    return [(k, round(v, 3)) for k, v in scores.items() if v > 0.15]


# ------------------------------------------------------------------
# PANNs 推理（有模型时）
# ------------------------------------------------------------------
def _panns_tags(path):
    """用官方 Cnn14 跑 PANNs（喂波形，模型内部做 STFT+logmel）。

    返回 [(panns_tag, prob)]（prob>0.15）。缺标签清单返回 None（交由调用方兜底）。
    """
    import torch
    import numpy as np

    labels = _panns_labels
    if not labels:
        return None

    # 取 10s 波形 @32000Hz（PANNs 标准），补零到 320000（10s）
    import librosa
    try:
        y, sr = librosa.load(path, sr=32000, duration=10)
    except Exception as e:
        logger.exception(e)
        return []

    want = 320000  # 10s * 32000
    if len(y) < want:
        y = np.pad(y, (0, want - len(y)))
    else:
        y = y[:want]

    x = torch.from_numpy(y).unsqueeze(0).to(_panns_device)  # [1, data_length]
    with torch.no_grad():
        probs = _panns_model(x).cpu().numpy()[0]

    out = [(labels[i], float(p)) for i, p in enumerate(probs) if i < len(labels) and p > 0.15]
    out.sort(key=lambda t: t[1], reverse=True)
    return out


# ------------------------------------------------------------------
# 对外接口
# ------------------------------------------------------------------
def panns_tags(path):
    """返回 [(panns_tag, prob)]，按当前后端。PANNs 缺标签清单时回退 librosa。"""
    b = _ensure_backend()
    if b == "panns":
        res = _panns_tags(path)
        if res is None:
            logger.warning("PANNs 缺少 tags.txt，本曲回退 librosa 兜底")
            return _librosa_tags(path)
        return res
    return _librosa_tags(path)


def ai_tags_from_audio(path, cn_tags=None, threshold=0.3, log=None):
    """音频 → 本项目中文 AI 标签 [(cn_tag_key, score)]，按映射表加权聚合。"""
    log = log or logger
    from collections import defaultdict

    res = panns_tags(path)
    if not res:
        return []

    agg = defaultdict(float)
    for ptag, prob in res:
        cn = PANNS_TO_CN.get(ptag)
        if cn:
            agg[cn] += prob * PANNS_WEIGHT.get(cn, 1.0)

    allowed = set(cn_tags) if cn_tags else None
    results = [
        (cn, round(min(s, 1.0), 4))
        for cn, s in agg.items()
        if s >= threshold and (allowed is None or cn in allowed)
    ]
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def cache_key(path):
    try:
        st = os.stat(path)
        return f"{path}|{st.st_size}|{int(st.st_mtime)}"
    except Exception:
        return f"{path}|?"


def get_cached(path):
    return _audio_cache.get(cache_key(path))


def set_cached(path, cn_tags_list):
    _audio_cache.set(cache_key(path), cn_tags_list)


def save_cache():
    _audio_cache.save()
