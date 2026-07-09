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
TitleSLCache = JsonCache("cahce/songlist_cache_title.json")
SonglistCache = JsonCache("cahce/songlist_cache.json",expire_days=100)
search_cnt = 0

def wy_search(title, artist, album):
    global search_cnt

    BASE = "http://localhost:8080/api/v1"
    url = f"{BASE}/music/search"
    pnames = []
    score = 0

    if search_cnt%100 == 0 and search_cnt != 0:
        logger.info(f"    已网络处理 {search_cnt} 首歌曲，请等待10秒~\n")
        time.sleep(10)
    else:
        time.sleep(0.5)
        
    plylist = []
    try:
        params = {
            "q": title,
            "type": "playlist"}
        data = TitleSLCache.get(title)
        if not data:
            search_cnt +=1
            r = requests.get(url, params=params)
            data = r.json().get("data",[])
            TitleSLCache.set(artist, data)
        plylist = data.get("playlists",[])
        plylist = sorted(plylist, key=lambda x: x["play_count"], reverse=True)
        
    except Exception as e:
        logger.exception(e)
        
    for p in plylist[:NET_LIMIT]:
        pid = p["id"]
        pname = p["name"]
        source = p["source"]
        play_cnt = p.get("play_count", 0)
        
        if contain_all_dirtydata(pname, DIRTY_PLAYLIST_RULES) or len(pname) < 10:
            logger.info(f"    脏数据，忽略歌单: {pname}")
            continue
        elif play_cnt < 10000 and play_cnt != 0:
            logger.info(f"    播放较少（{play_cnt}），忽略歌单: {pname}")
            continue
        else:
            logger.info(f"    读取歌单: {pname}")
            
        try:
            songs_raw = SonglistCache.get(f"{pname}_{pid}")
            if not songs_raw:
                r2 = requests.get(
                    f"{BASE}/playlist/detail",
                    params={
                        "id": pid,
                        "source": source
                    }
                )

                detail = r2.json()
                if detail:
                    songs_raw = detail.get("data", [])
                    SonglistCache.set(f"{pname}_{pid}", songs_raw)
        except Exception as e:
            logger.exception(e)
        
        if songs_raw != [] and songs_raw != None:
            for s in songs_raw:
                if title == s.get("name") and artist == s.get("artist"):
                    pnames.append(pname)
                    score += play_cnt/10000
                    continue

        # params = {
        #     "q": album,
        #     "type": "playlist"}
        # data = AlbumSLCache.get(album)
        # if not data:
        #     search_cnt +=1
        #     r = requests.get(url, params=params)
        #     data = r.json().get("data",[])
        #     AlbumSLCache.set(album, data)
        # plylist = data.get("playlists",[])
        # if plylist:
        #     plylist = sorted(plylist, key=lambda x: x["play_count"], reverse=True)
        #     for p in plylist[:NET_LIMIT]:
        #         if p.get("play_count", 0) > 10000:
        #             results.append(p["name"])
        #         else:
        #             break

    return [list(set(pnames)), score]

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
    artist_best = defaultdict(list)
    for s in songs[:MAX_SAMPLE]:
        keyword = f"{s['title']} {s['artist']}"
        logger.info("  分析:"+keyword)

        if USE_NET:
            logger.info("    在线分类中...")
            [names, score] = wy_search(s['title'], s['artist'], s['album'])
                        
            if USE_ARTIST:
                at = s['artist'].split(" ")[0]
                artist_best[at].append({"song":s, "score":score})

            # ✅ 歌单标签
            for n in names[:5]:
                tags = extract_tags(n)
                s["tags"] += tags
                s["score"] += WEIGHT_NET

                # if USE_ARTIST:
                #     for t in tags:
                #         # 🎤 歌手精选
                #         if "精选" in t[1] and s["artist"] and s["artist"] in n:
                #             tag_name = f"🎤_{s['artist']}_精选"
                #             if not tag_name in str(s["tags"]):
                #                 s["tags"].append(["ARTIST", tag_name])
                #             s["score"] += WEIGHT_NET + 1
                #         else:
                #             if not t[1] in str(s["tags"]):
                #                 s["tags"].append(t)
                #             s["score"] += WEIGHT_NET
        
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
    return [songs, artist_best]

# ---------------- 输出 ----------------
def save(songs):
    logger.info("生成歌单中...")
    grouped = defaultdict(list)

    # 存储缓存
    TitleSLCache.save()

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
        file_dir = f"{path}/0_{tag_name}"
        os.makedirs(file_dir, exist_ok=True)
        file_path = f"{file_dir}/0_{tag_name}.m3u"
        pic_name = tag_name.split('_')
        pic_patch = resource_path(f"assets/{pic_name[1]} {pic_name[2]}.png")
        
        if os.path.exists(pic_patch):
            shutil.copy(pic_patch, file_dir + "/cover.png")
        else:
            shutil.copy(resource_path("assets/cover.jpeg"), file_dir)

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
    shutil.copy(resource_path("assets/cover.jpeg"), file_dir)

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
            
def save_artist(artist_best):
    for at, songs in artist_best.items():
        if len(songs) < 30:
            continue
        
        ranked = sorted(songs, key=lambda x: x["score"], reverse=True)
        
        path = f"{MUSIC_DIR}/AI分类歌单"
        file_dir = f"{path}/0_{at}_🎤_精选"
        os.makedirs(file_dir, exist_ok=True)
        file_path = f"{file_dir}/0_{at}_🎤_精选.m3u"
        shutil.copy(resource_path("assets/cover.jpeg"), file_dir)
        logger.info("  ->生成:"+file_path)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(f"#PLAYLIST:0_{at}_🎤_精选n")

            for song in ranked[:50]:
                s = song["song"]
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

    [songs, artist_best] = classify(songs)
    save(songs)
    if USE_ARTIST:
        save_artist(artist_best)

    SonglistCache.save()
    logger.info("分类完成")

if __name__ == "__main__":
    run_classifier(MUSIC_DIR)
