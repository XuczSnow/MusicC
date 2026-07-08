DIRTY_METADATA_RULES = {

    # =====================
    # Title
    # =====================

    "bad_title": {
        "unknown",
        "untitled",
        "track",
        "track01",
        "track1",
        "audio",
        "music",
        "song",
        "demo",
        "sample",
        "test",
        "new",
        "新建",
        "录音",
        "未命名",
        "曲目"
    },

    # =====================
    # Artist
    # =====================

    "bad_artist": {
        "unknown",
        "unknown artist",
        "artist",
        "test",
        "demo",
        "va",
        "various artists",
        "various",
        "未知",
        "未知歌手",
        "未指定艺术家",
        "群星"
    },

    # =====================
    # Album
    # =====================

    "bad_album": {
        "unknown",
        "album",
        "test",
        "demo",
        "default",
        "我的专辑",
        "未命名",
        "未知专辑"
    },

    # =====================
    # 广告词
    # =====================

    "ad_words": {

        "320k",
        "128k",
        "192k",
        "flac",
        "ape",
        "wav",
        "mp3",
        "hq",
        "vip",
        "无损",
        "高品质",
        "超品质",
        "试听",
        "下载",
        "免费下载",
        "在线听",
        "在线试听",
        "伴奏",
        "纯伴奏",
        "铃声",
        "手机铃声",
        "酷狗音乐",
        "qq音乐",
        "网易云音乐",
        "酷我音乐",
        "kugou",
        "kuwo",
        "netease"
    },

    # =====================
    # 乱码字符
    # =====================

    "garbled_chars": {

        "�",
        "□",
        "????",
        "?????",
        "����",
        "乱码"
    },
}

BAD_LYRIC_RULES = {
    # =====================
    # 无效歌词
    # =====================

    "invalid_lyric": {
        "暂无歌词",
        "无歌词",
        "纯音乐",
        "此歌曲为纯音乐",
        "没有歌词",
        "歌词获取失败"
    },
}

BAD_METADATA_RULES = {
    # =====================
    # 可疑标题前缀
    # =====================

    "bad_title_prefix": {

        "track",
        "track_",
        "track-",
        "audio",
        "audio_",
        "audio-",
        "song",
        "song_",
        "song-"
    },

    # =====================
    # 可疑扩展说明
    # =====================

    "extra_tags": {

        "(live)",
        "(demo)",
        "(伴奏)",
        "(翻唱)",
        "(cover)",
        "(dj)",
        "(remix)",
        "(完整版)",
        "(无损版)",

        "[live]",
        "[demo]",
        "[cover]",
        "[remix]",

        "live版",
        "翻唱版",
        "无损版",
        "dj版",
        "伴奏版",
        "remix版"
    }
}

import re

def is_dirty_title(title):

    if not title:
        return True

    title = title.strip().lower()

    if title in DIRTY_METADATA_RULES["bad_title"]:
        return True

    if title.isdigit():
        return True

    if re.match(
        r'^(track)?[_\- ]?\d+$',
        title
    ):
        return True

    return False

def is_dirty_artist(artist):

    if not artist:
        return True

    artist = artist.strip().lower()

    return artist in DIRTY_METADATA_RULES["bad_artist"]

def is_dirty_lyric(lyric):
    if len(lyric) < 100:
        return True

def contains_ad_words(text):

    text = text.lower()

    return any(
        word in text
        for word in DIRTY_METADATA_RULES["ad_words"]
    )

def contains_garbled(text):

    return any(
        item in text
        for item in DIRTY_METADATA_RULES["garbled_chars"]
    )

def contain_all_dirtydata(text):

    if not text:
        return True
    
    if len(text) > 50:
        return True

    text = text.strip().lower()
    
    for data in DIRTY_METADATA_RULES.values():
        for v in data:
            if v in text:
                return True

    if text in DIRTY_METADATA_RULES["bad_title"]:
        return True

    if text.isdigit():
        return True

    # if re.match(
    #     r'^(track)?[_\- ]?\d+$',
    #     text
    # ):
    #     return True

    return False


