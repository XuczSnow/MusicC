# -*- coding: utf-8 -*-
"""
pann_tag_map.py — PANNs Cnn14 (527类) 标签 → 本项目中文标签 映射表。

PANNs 用的是标准 AudioSet 527 类 display_name（见 models/panns_Cnn14/tags.txt），
本表把其中有意义的 PANNs 标签映射到本项目 AI_XX 中文标签。

规则：
  - 能映射：value = 中文 tag_key（形如 "AI_🎹_钢琴"，与 AI_LYRICS_DEFINITIONS 的 key 一致）
  - 无法映射 / 暂不需要：value = ""（保留 key 占位，便于以后补）

同一中文标签可由多个 PANNs 标签贡献，audio_classify 里按 PANNS_WEIGHT 加权求和。
"""

PANNS_TO_CN = {
    # ===== 乐器 / 编制（form） =====
    "Piano":            "AI_🎹_钢琴",
    "Electric piano":   "AI_🎹_钢琴",
    "Guitar":           "AI_🎸_吉他",
    "Electric guitar":  "AI_🎸_吉他",
    "Acoustic guitar":  "AI_🎸_吉他",
    "Steel guitar, slide guitar": "AI_🎸_吉他",
    "Tapping (guitar technique)": "AI_🎸_吉他",
    "Synthesizer":      "AI_🎧_电子",
    "Saxophone":        "AI_🎧_爵士",
    "Trumpet":          "AI_🎧_爵士",
    "Trombone":         "AI_🎧_爵士",
    "Drum":             "",
    "Drum kit":         "",
    "Drum machine":     "AI_🎧_电子",
    "Organ":            "",
    "Electronic organ": "",
    "Hammond organ":    "",
    "Violin, fiddle":   "",
    "Cello":            "",
    "Flute":            "",
    "Singing":          "",
    "Male singing":     "",
    "Female singing":   "",
    "Bass guitar":      "",
    "Double bass":      "",

    # ===== 风格 / 流派（genre） =====
    "Classical music":  "",
    "Country":          "AI_🎧_民谣",
    "Rock music":       "AI_🎧_摇滚",
    "Punk rock":        "AI_🎧_摇滚",
    "Progressive rock": "AI_🎧_摇滚",
    "Rock and roll":    "AI_🎧_摇滚",
    "Psychedelic rock": "AI_🎧_摇滚",
    "Grunge":           "AI_🎧_摇滚",
    "Pop music":        "AI_🎧_流行",
    "Jazz":             "AI_🎧_爵士",
    "Blues":            "AI_🎧_爵士",
    "Rhythm and blues": "AI_🎧_爵士",
    "Soul music":       "AI_🎧_爵士",
    "Folk music":       "AI_🎧_民谣",
    "Reggae":           "AI_🎧_民谣",
    "Heavy metal":      "AI_🎧_摇滚",
    "Electronic music": "AI_🎧_电子",
    "Electronica":      "AI_🎧_电子",
    "Electronic dance music": "AI_🎧_电子",
    "Dance music":      "AI_🎧_电子",
    "Hip hop music":    "AI_🎧_说唱",
    "Rapping":          "AI_🎧_说唱",
    "Ambient music":    "AI_🌿_轻松",

    # ===== 情绪（mood）=====
    "Happy music":      "AI_😊_开心",
    "Sad music":        "AI_😢_悲伤",
    "Angry music":      "AI_🔥_热血",
    "Grunge":           "AI_🔥_热血",

    # ===== 场景（scene）=====
    "Dance music":      "AI_🎉_派对",
    "Electronic dance music": "AI_🎉_派对",
    "Concert":          "",
    "Stadium":          "",
    "Run":              "AI_🏃_运动",
    "Bicycle":          "AI_🏃_运动",
    "Journey":          "",
    "Car passing by":   "AI_🚗_车载",
    "Rain":             "",
    "Raindrop":         "",
    "Bird":             "AI_🌿_轻松",
    "Wind":             "",

    # ===== 保留占位（暂不映射） =====
    "Baby cry, infant cry": "",
    "Baby laughter":        "",
    "Laughter":            "AI_😊_开心",
    "Applause":            "",
    "Speech":              "",
}

# 反向：中文 tag_key -> [panns标签...]
def build_cn_to_panns():
    m = {}
    for p, cn in PANNS_TO_CN.items():
        if cn:
            m.setdefault(cn, []).append(p)
    return m


CN_TO_PANNS = build_cn_to_panns()

# 每个中文标签命中时的权重（乐器/流派略高于粗粒度场景）
PANNS_WEIGHT = {
    "AI_🎹_钢琴": 1.2,
    "AI_🎸_吉他": 1.2,
    "AI_🎧_电子": 0.9,
    "AI_🎧_爵士": 0.9,
    "AI_🎧_摇滚": 0.9,
    "AI_🎧_流行": 0.9,
    "AI_🎧_说唱": 0.9,
    "AI_🎧_民谣": 0.9,
}
