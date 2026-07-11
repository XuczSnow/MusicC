from script.logger import AppLogger

logger = AppLogger()

DIRTY_PLAYLIST_RULES = {

    # ==========================
    # 无效歌单名称
    # ==========================

    "bad_playlist_names": {
        "未命名",
        "默认歌单",
        "新建歌单",
        "我的歌单",
        "my playlist",
        "test",
        "demo",
        "我喜欢的音乐",
        "抖音",
        "dj",
        "收藏夹",
        "未知歌单"
    },

    # ==========================
    # 广告营销类
    # ==========================

    "marketing_keywords": {
        "免费",
        "vip",
        "会员",
        "下载",
        "免费下载",
        "高速下载",
        "资源包",
        "资源群",
        "加微信",
        "微信",
        "加qq",
        "qq群",
        "联系客服",
        "福利",
        "推广",
        "广告",
        "私信",
        "引流",
        "扫码",
        "领取"
    },

    # ==========================
    # 搬运采集类
    # ==========================

    "crawler_keywords": {
        "合集",
        "大全",
        "打包",
        "资源库",
        "全收录",
        "最全",
        "全网最全",
        "全平台",
        "搜集整理",
        "持续更新",
        "搬运",
        "转载",
        "全集"
    },

    # ==========================
    # 测试歌单
    # ==========================

    "test_keywords": {
        "test",
        "demo",
        "测试",
        "试试",
        "aaa",
        "bbb",
        "ccc",
        "123",
        "1234",
        "111",
        "222",
        "333"
    },

    # ==========================
    # 乱码
    # ==========================

    "garbled_keywords": {
        "�",
        "□",
        "????",
        "?????",
        "����",
        "乱码"
    },

    # ==========================
    # 低质量描述
    # ==========================

    "low_quality_keywords": {
        "随便听听",
        "乱七八糟",
        "不知道叫什么",
        "自己听",
        "哈哈",
        "嘻嘻",
        "嘿嘿",
        "收藏一下",
        "备用",
        "留着"
    },

    # ==========================
    # 关键词黑名单
    # ==========================

    "spam_keywords": {
        "兼职",
        "赚钱",
        "网赚",
        "投资",
        "股票",
        "理财",
        "福彩",
        "彩票",
        "赌博",
        "博彩"
    },

    # ==========================
    # 默认封面
    # ==========================

    "default_cover_keywords": {
        "default",
        "unknown",
        "placeholder",
        "nocover"
    },
}

PARAMS_PLAYLIST_RULES = {
    # ==========================
    # 参数规则
    # ==========================

    "rules": {

        # 最少歌曲数
        "min_song_count": 3,

        # 超过视为垃圾合集
        "max_song_count": 5000,

        # 歌单标题最大长度
        "max_title_length": 80,

        # 重复率超过30%
        "max_duplicate_rate": 0.3,

        # 推荐最低评分
        "minimum_score": 70
    }
}

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
        # "伴奏",
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
    
def is_dirty_playlist(pname, play_cnt, track_cnt):
    if contain_all_dirtydata(pname, DIRTY_PLAYLIST_RULES) or len(pname) < 7:
        logger.info(f"    脏数据，忽略歌单: {pname}")
        return True
    elif play_cnt < 10000 and play_cnt != 0:
        logger.info(f"    播放较少（{play_cnt}），忽略歌单: {pname}")
        return True
    elif track_cnt > 200:
        logger.info(f"    歌单杂乱（{track_cnt}），忽略歌单: {pname}")
        return True
    else:
        return False

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

def contain_all_dirtydata(text, rule_dict: dict):

    if not text:
        return True
    
    # if len(text) > 50:
    #     return True

    text = text.strip().lower()
    
    for data in rule_dict.values():
        for v in data:
            if v in text:
                return True

    if text.isdigit():
        return True

    # if re.match(
    #     r'^(track)?[_\- ]?\d+$',
    #     text
    # ):
    #     return True

    return False
