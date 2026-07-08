import os
import sys
import time
import shutil
import requests

from collections import defaultdict

from script.music_tag import *
from script.load_music import *
from script.cache_manager import JsonCache
from script.logger import AppLogger

from sklearn.metrics.pairwise import cosine_similarity

# ---------------- CONFIG ----------------
MUSIC_DIR = "."
USE_AI = True
USE_NET = True
USE_ARTIST = True
USE_ERA = True

AI_THRESHOLD = 0.4
WEIGHT_AI = 2
WEIGHT_NET = 1
MAX_SAMPLE = 1000
NET_LIMIT = 30

if len(sys.argv) > 1:
    MUSIC_DIR = sys.argv[1]
    USE_AI = sys.argv[2] == "True"
    USE_NET = sys.argv[3] == "True"
    USE_ARTIST = sys.argv[4] == "True"
    USE_ERA = sys.argv[5] == "True"

    AI_THRESHOLD = float(sys.argv[6])
    WEIGHT_AI = int(sys.argv[7])
    WEIGHT_NET = int(sys.argv[8])
    MAX_SAMPLE = int(sys.argv[9])
# MUSIC_DIR = r"."
# MAX_SAMPLE = 50

# ===== 全局日志函数 =====
logger = AppLogger()

def set_logger(func):
    global logger
    logger = func

# ---------------- AI模型加载 ----------------
model = None
tag_embeddings = {}

def get_model():
    # ✅ AI模型
    from sentence_transformers import SentenceTransformer

    global model
    global tag_embeddings

    if model != None:
        return model

    MODEL_PATH = resource_path("./models/models--sentence-transformers--all-MiniLM-L6-v2")
    model = SentenceTransformer(MODEL_PATH)

# ---------------- AI标签语义 ----------------
    tag_embeddings = {
        tag: model.encode(" ".join(map(str, text)))
        for tag, text in AI_LYRICS_DEFINITIONS.items()
    }

    # tag_embeddings_theme = {
    #     tag: model.encode(" ".join(map(str, text)))
    #     for tag, text in TAG_DEFINITIONS["theme"].items()
    # }
    
    # for tag, text in TAG_DEFINITIONS["theme"].items():
    #     print(" ".join(map(str, text)))

    # tag_embeddings = tag_embeddings_mood | tag_embeddings_theme
    logger.info("    AI模型加载完成\n")

    return model

# ---------------- 年代 ----------------

def year_tag(song):

    try:
        y = int(song["year"][:4])
    except Exception as e:
        logger.exception(e)
        return ""

    if y == 0:
        return ""
    else:
        return ["ERA", "📅_" + str(y)[0:3] + "0s"]
    # elif y < 1990:
    #     return "📅_1980s"
    # elif y < 1990:
    #     return "📅_1980s"
    # elif y < 2000:
    #     return "📅_1990s"
    # elif y < 2010:
    #     return "📅_2000s"
    # elif y < 2020:
    #     return "📅_2010s"
    # else:
    #     return "📅_2020s"

# ---------------- 在线云搜索 ----------------
ArtistSLCache = JsonCache("cahce/songlist_cache_artist.json")
AlbumSLCache = JsonCache("cahce/songlist_cache_album.json")
search_cnt = 0

def wy_search(title, artist, album):
    global search_cnt

    url = "http://localhost:8080/api/v1/music/search"
    results = []

    if search_cnt%20 == 0 and search_cnt != 0:
        logger.info(f"    已网络处理 {search_cnt} 首歌曲，请等待10秒~\n")
        time.sleep(10)
    else:
        time.sleep(0.5)

    try:
        params = {
            "q": artist,
            "type": "playlist"}
        data = ArtistSLCache.get(artist)
        if not data:
            search_cnt +=1
            r = requests.get(url, params=params)
            data = r.json().get("data",[])
            ArtistSLCache.set(artist, data)
        plylist = data.get("playlists",[])
        plylist = sorted(plylist, key=lambda x: x["play_count"], reverse=True)
        for p in plylist[:NET_LIMIT]:
            if p.get("play_count", 0) > 10000:
                results.append(p["name"])
            else:
                break

        params = {
            "q": album,
            "type": "playlist"}
        data = AlbumSLCache.get(album)
        if not data:
            search_cnt +=1
            r = requests.get(url, params=params)
            data = r.json().get("data",[])
            AlbumSLCache.set(album, data)
        plylist = data.get("playlists",[])
        if plylist:
            plylist = sorted(plylist, key=lambda x: x["play_count"], reverse=True)
            for p in plylist[:NET_LIMIT]:
                if p.get("play_count", 0) > 10000:
                    results.append(p["name"])
                else:
                    break
    except Exception as e:
        logger.exception(e)

    return list(set(results))

# ---------------- 简单标签规则 ----------------
def extract_tags(name):

    name_lower = name.lower()
    result = []

    for ilist in TAG_DEFINITIONS.values():
        for tag, keywords in ilist.items():
            for k in keywords:
                if k.lower() in name_lower:
                    result.append(["NET", tag])
                    break

    return result

# ---------------- AI语义标签 ----------------
def ai_tags(title, artist):

    model = get_model()

    text = f"{title} {artist}"
    emb = model.encode(text)

    results = []

    for tag, tag_emb in tag_embeddings.items():

        score = cosine_similarity([emb], [tag_emb])[0][0]

        if score > AI_THRESHOLD:
            results.append(("AI", tag, score))

    return results

def ai_tags_from_lyric(lyric):

    model = get_model()
    if not lyric:
        return []

    emb = model.encode(lyric)

    results = []

    for tag, tag_emb in tag_embeddings.items():

        score = cosine_similarity([emb], [tag_emb])[0][0]

        if score > AI_THRESHOLD:
            results.append(("AI", tag, score))

    return results

# ---------------- 分类 ----------------
def classify(songs):

    logger.info("歌曲分类中...")
    for s in songs[:MAX_SAMPLE]:
        keyword = f"{s['title']} {s['artist']}"
        logger.info("  分析:"+keyword)

        if USE_NET:
            logger.info("    在线分类中...")
            names = wy_search(s['title'], s['artist'], s['album'])

            # ✅ 歌单标签
            for n in names:

                if REMOVE_TEXT in n:
                    continue

                tags = extract_tags(n)

                if USE_ARTIST:
                    for t in tags:
                        # 🎤 歌手精选
                        if "精选" in t[1] and s["artist"] and s["artist"] in n:
                            tag_name = f"🎤_{s['artist']}_精选"
                            if not tag_name in str(s["tags"]):
                                s["tags"].append(["ARTIST", tag_name])
                            s["score"] += WEIGHT_NET + 1
                        else:
                            if not t[1] in str(s["tags"]):
                                s["tags"].append(t)
                            s["score"] += WEIGHT_NET

        if USE_AI:
            # ✅ AI标签
            # ai = ai_tags(s["title"], s["artist"])
            logger.info("    AI分类中...")
            lyric = s["lyric"]
            ai = ai_tags_from_lyric(lyric)

            for source, tag, score in ai:
                s["tags"].append([source, tag])
                s["score"] += score * WEIGHT_AI

        if USE_ERA:
            # ✅ 年代
            logger.info("    年代分类中...\n")
            y = year_tag(s)
            if y:
                s["tags"].append(y)

        # # ✅ 限制标签数量
        # s["tags"] = list(set(s["tags"]))[:5]
    logger.info("歌曲分析完成\n")
    return songs

# ---------------- 输出 ----------------
def save(songs):
    logger.info("生成歌单中...")
    grouped = defaultdict(list)

    # 存储缓存
    ArtistSLCache.save()
    AlbumSLCache.save()

    for s in songs:
        for src, tag in s["tags"]:
            name = f"{src}_{tag}"
            grouped[name].append(s)

    path = f"{MUSIC_DIR}/AI分类歌单"

    os.makedirs(path, exist_ok=True)

    for tag_name, song_objs in grouped.items():

        # ✅ 排序（所有歌单保持一致）
        song_objs = sorted(song_objs, key=lambda x: x["score"], reverse=True)

        tag_name = sanitize_filename(tag_name)
        file_dir = f"{path}/{tag_name}"
        os.makedirs(file_dir, exist_ok=True)
        file_path = f"{file_dir}/{tag_name}.m3u"
        pic_name = tag_name.split('_')
        pic_patch = resource_path(f"asset/{pic_name[1]} {pic_name[2]}.png")
        
        if os.path.exists(pic_patch):
            shutil.copy(pic_patch, file_dir + "/cover.png")
        else:
            shutil.copy(resource_path("asset/cover.jpeg"), file_dir)

        with open(file_path, "w", encoding="utf-8") as f:

            f.write("#EXTM3U\n")
            f.write(f"#PLAYLIST:{tag_name}\n")

            for s in song_objs[:50]:

                title = s.get("title", "未知")
                artist = s.get("artist", "未知")
                album = s.get("album", "未知专辑")

                # ✅ 如果没有duration，先写 -1 或固定值
                duration = s.get("duration", -1)

                f.write(f"#EXTALB:{album}\n")
                f.write(f"#EXTART:{artist}\n")
                f.write(f"#EXTINF:{duration},{artist} - {title}\n")
                f.write(s["path"] + "\n")

        logger.info("  ->生成:"+file_path)

    # ✅ DailyMix
    ranked = sorted(songs, key=lambda x: x["score"], reverse=True)

    file_dir = f"{path}/DailyMix"
    os.makedirs(file_dir, exist_ok=True)
    file_path = f"{file_dir}/DailyMix.m3u"
    shutil.copy(resource_path("asset/cover.jpeg"), file_dir)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("#PLAYLIST:DailyMix\n")

        for s in ranked[:50]:
            title = s.get("title", "未知")
            artist = s.get("artist", "未知")
            album = s.get("album", "未知专辑")
            duration = s.get("duration", -1)

            f.write(f"#EXTALB:{album}\n")
            f.write(f"#EXTART:{artist}\n")
            f.write(f"#EXTINF:{duration},{artist} - {title}\n")
            f.write(s["path"] + "\n")

# ---------------- MAIN ----------------
def run_classifier(
    music_dir,
    use_ai=True,
    use_net=True,
    use_artist=True,
    use_era=True,
    ai_threshold=0.4,
    weight_ai=2,
    weight_net=1,
    max_sample=1000,
    net_limit=30,
    log=None   # ✅ 接收GUI日志函数
):
    global MUSIC_DIR
    global USE_AI
    global USE_NET
    global USE_ARTIST
    global USE_ERA
    global AI_THRESHOLD
    global WEIGHT_AI
    global WEIGHT_NET
    global MAX_SAMPLE
    global NET_LIMIT

    MUSIC_DIR = music_dir
    USE_AI = use_ai
    USE_NET = use_net
    USE_ARTIST = use_artist
    USE_ERA = use_era
    AI_THRESHOLD = ai_threshold
    WEIGHT_AI = weight_ai
    WEIGHT_NET = weight_net
    MAX_SAMPLE = max_sample
    NET_LIMIT = net_limit

    if log:
        set_logger(log)

    songs = load_music(MUSIC_DIR, log=logger)
    logger.info(f"本地歌曲:{len(songs)}\n")

    songs = classify(songs)
    save(songs)

    logger.info("分类完成")

if __name__ == "__main__":
    run_classifier(MUSIC_DIR)
