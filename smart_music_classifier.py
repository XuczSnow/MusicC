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
WEIGHT_AI = 0
WEIGHT_NET = 1
# MAX_SAMPLE = 1000
NET_LIMIT = 10

if len(sys.argv) > 1:
    MUSIC_DIR = sys.argv[1]
    USE_AI = sys.argv[2] == "True"
    USE_NET = sys.argv[3] == "True"
    USE_ARTIST = sys.argv[4] == "True"
    USE_ERA = sys.argv[5] == "True"

    AI_THRESHOLD = float(sys.argv[6])
    WEIGHT_AI = int(sys.argv[7])
    WEIGHT_NET = int(sys.argv[8])
    NET_LIMIT = float(sys.argv[9])
    # MAX_SAMPLE = int(sys.argv[9])

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

# def year_tag(song):

#     try:
#         y = int(song["year"][:4])
#     except Exception as e:
#         logger.exception(e)
#         return ""

#     if y == 0:
#         return ""
#     else:
#         return {"tag": f"ERA_📅_{str(y)[0:3]}0s", "score": 0}

# ---------------- 在线云搜索 ----------------
TitleSLCache = JsonCache("cahce/songlist_cache_title.json")
SonglistCache = JsonCache("cahce/songlist_cache.json")
search_cnt = 0

def wy_search(title, artist, album):
    global search_cnt

    BASE = "http://localhost:8080/api/v1"
    url = f"{BASE}/music/search"
    pnames = []

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

    pl_cnt = 0 
    for p in plylist:
        pid = p["id"]
        pname = p["name"]
        source = p["source"]
        play_cnt = p.get("play_count", 0)
        track_cnt = p.get("track_count", 0)
            
        if is_dirty_playlist(pname, play_cnt, track_cnt):
            continue
        else:
            pl_cnt += 1
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
            
        def is_similar(s1, s2):
            return (s1 in s2) or (s2 in s1)
        
        if songs_raw != [] and songs_raw != None:
            for s in songs_raw:
                if is_similar(title, s.get("name")) and is_similar(artist, s.get("artist")):
                    if play_cnt == 0:
                        pscore = 1
                    else:
                        pscore = play_cnt/100/track_cnt
                    pnames.append({"pname":pname, "pscore":pscore})
                    continue
                
        if pl_cnt > NET_LIMIT:
            break

    return pnames

# ---------------- 简单标签规则 ----------------
def extract_tags(name):

    name_lower = name["pname"].lower()
    result = []

    for ilist in TAG_DEFINITIONS.values():
        for tag, keywords in ilist.items():
            for k in keywords:
                if k.lower() in name_lower:
                    result += [{"tag": f"NET_{tag}", "score": name["pscore"]}]
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
    total = len(songs)
    song_cnt = 0
    
    for s in songs:
        song_cnt += 1
        keyword = f"{s['title']} {s['artist']}"
        logger.info(f"  状态：处理中 {song_cnt}/{total}--->分析:"+keyword)

        if USE_NET:
            net_tags = []
            logger.info("    在线分类中...")
            names = wy_search(s['title'], s['artist'], s['album'])
            
            tags = []
            # ✅ 歌单标签
            for n in names:
                tags += extract_tags(n)
            
            for tag in tags:
                if tag == []:
                    continue
                s["net_tags"][tag["tag"]]["score"] += tag["score"]
        
        if USE_AI:
            # ✅ AI标签
            # ai = ai_tags(s["title"], s["artist"])
            logger.info("    AI分类中...\n")
            lyric = s["lyric"]
            ai = ai_tags_from_lyric(lyric)

            for source, tag, ai_score in ai:
                s["ai_tags"][f"AI_{tag}"]["score"] += ai_score

        # if USE_ERA:
        #     # ✅ 年代
        #     logger.info("    年代分类中...\n")
        #     y = year_tag(s)
        #     if y:
        #         s["tags"][y]["score"] += 1
                
        # # ✅ 限制标签数量
        # s["tags"] = list(set(s["tags"]))[:5]
    logger.info("歌曲分析完成\n")
    return songs

# ---------------- 输出 ----------------
def save_era(songs, path):
    era_best = defaultdict(list)
    
    for s in songs:
        y = s['year'][:3]
        if y == "0" or y == "":
            continue
        era_best[y].append(s)
        
    for y, y_songs in era_best.items():
       
        ranked = sorted(y_songs, key=lambda x: x["rank"], reverse=True)
        
        file_dir = f"{path}/0_ERA_📅_{y}0s"
        os.makedirs(file_dir, exist_ok=True)
        file_path = f"{file_dir}/0_ERA_📅_{y}0s.m3u"
        shutil.copy(resource_path("assets/cover.jpeg"), file_dir)
        logger.info("  ->生成:"+file_path)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(f"#PLAYLIST:0_ERA_📅_{y}0s\n")

            for s in ranked[:50]:
                title = s.get("title", "未知")
                artist = s.get("artist", "未知")
                album = s.get("album", "未知专辑")
                duration = s.get("duration", -1)

                f.write(f"#EXTALB:{album}\n")
                f.write(f"#EXTART:{artist}\n")
                f.write(f"#EXTINF:{duration},{artist} - {title}\n")
                f.write(s["path"] + "\n")
            
def save_artist(songs, path):

    artist_best = defaultdict(list)

    for s in songs:
        at = s['artist'].split(" ")[0].lower()
        artist_best[at].append(s)
        
    for at, at_songs in artist_best.items():
        if len(at_songs) < 20:
            continue
        
        ranked = sorted(at_songs, key=lambda x: x["rank"], reverse=True)
        
        file_dir = f"{path}/0_{at}_🎤_精选"
        os.makedirs(file_dir, exist_ok=True)
        file_path = f"{file_dir}/0_{at}_🎤_精选.m3u"
        shutil.copy(resource_path("assets/cover.jpeg"), file_dir)
        logger.info("  ->生成:"+file_path)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(f"#PLAYLIST:0_{at}_🎤_精选\n")

            for s in ranked[:50]:
                title = s.get("title", "未知")
                artist = s.get("artist", "未知")
                album = s.get("album", "未知专辑")
                duration = s.get("duration", -1)

                f.write(f"#EXTALB:{album}\n")
                f.write(f"#EXTART:{artist}\n")
                f.write(f"#EXTINF:{duration},{artist} - {title}\n")
                f.write(s["path"] + "\n")

def save_plylist(songs, tag_name, path, type):
    song_objs = sorted(songs, key=lambda x: x[type][tag_name]["score"], reverse=True)

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
        f.write(f"#PLAYLIST:0_{tag_name}\n")

        for s in song_objs[:50]:

            if s[type][tag_name]["score"] <= 0:
                break

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

def save(songs):
    logger.info("生成歌单中...")

    # 存储缓存
    TitleSLCache.save()

    path = f"{MUSIC_DIR}/AI分类歌单"
    # 保存 NET 标签歌单
    if USE_NET:
        logger.info("  生成 NET 标签歌单中...")
        for value in TAG_DEFINITIONS.values():
            for tag in value.keys():
                tag_name = f"NET_{tag}"
                for song in songs:
                    song["rank"] += song["net_tags"][tag_name]["score"] * WEIGHT_NET
                save_plylist(songs, tag_name, path, "net_tags")

    # 保存 AI 标签歌单
    if USE_AI:
        logger.info("  生成 AI 标签歌单中...")
        for tag in AI_LYRICS_DEFINITIONS.keys():
            tag_name = f"AI_{tag}"
            for song in songs:
                song["rank"] += song["ai_tags"][tag_name]["score"] * WEIGHT_AI
            save_plylist(songs, tag_name, path, "ai_tags")
    
    if USE_ERA:
        logger.info("  生成 年代精选歌单中...")
        save_era(songs, path)
    
    if USE_ARTIST:
        logger.info("  生成 歌手精选歌单中...")
        save_artist(songs, path)

    # # ✅ DailyMix
    # ranked = sorted(songs, key=lambda x: x["score"], reverse=True)

    # file_dir = f"{path}/DailyMix"
    # os.makedirs(file_dir, exist_ok=True)
    # file_path = f"{file_dir}/DailyMix.m3u"
    # shutil.copy(resource_path("assets/cover.jpeg"), file_dir)

    # with open(file_path, "w", encoding="utf-8") as f:
    #     f.write("#EXTM3U\n")
    #     f.write("#PLAYLIST:DailyMix\n")

    #     for s in ranked[:50]:
    #         title = s.get("title", "未知")
    #         artist = s.get("artist", "未知")
    #         album = s.get("album", "未知专辑")
    #         duration = s.get("duration", -1)

    #         f.write(f"#EXTALB:{album}\n")
    #         f.write(f"#EXTART:{artist}\n")
    #         f.write(f"#EXTINF:{duration},{artist} - {title}\n")
    #         f.write(s["path"] + "\n")

# ---------------- MAIN ----------------
def run_classifier(
    music_dir,
    use_ai=True,
    use_net=True,
    use_artist=True,
    use_era=True,
    ai_threshold=0.4,
    weight_ai=0,
    weight_net=1,
    net_limit=10,
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
    global NET_LIMIT

    MUSIC_DIR = music_dir
    USE_AI = use_ai
    USE_NET = use_net
    USE_ARTIST = use_artist
    USE_ERA = use_era
    AI_THRESHOLD = ai_threshold
    WEIGHT_AI = weight_ai
    WEIGHT_NET = weight_net
    NET_LIMIT = net_limit

    if log:
        set_logger(log)

    logger.info("读取本地歌曲\n")
    songs = load_music(MUSIC_DIR, log=logger)
    logger.info(f"本地歌曲:{len(songs)}\n")

    songs = classify(songs)
    save(songs)

    SonglistCache.save()
    logger.info("分类完成")

if __name__ == "__main__":
    run_classifier(MUSIC_DIR)
