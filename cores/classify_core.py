import os
import sys
import time
import shutil
import requests

# 允许从 cores/ 目录直接运行（CLI）：把项目根加入 sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from collections import defaultdict
from dataclasses import dataclass

from script.music.music_tag import *
from script.music.load_music import *
from script.common.cache_manager import JsonCache
from script.common.logger import AppLogger
from script.common.rate_limiter import RateLimiter, api_limiter
from script.music.playlist_service import fetch_playlist_songs, SonglistCache

# ✅ 启动性能：sklearn 首次导入开销大（~1s），改为惰性加载——
#    仅在真正执行 AI 语义分类时才 import，启动期零成本
_cosine_similarity = None

def _get_cosine_similarity():
    global _cosine_similarity
    if _cosine_similarity is None:
        from sklearn.metrics.pairwise import cosine_similarity
        _cosine_similarity = cosine_similarity
    return _cosine_similarity

# ---------------- CONFIG ----------------
@dataclass
class Config:
    """分类器全部运行参数（替代原先 9 个模块级全局变量）"""
    music_dir: str = "."
    use_ai: bool = True
    use_net: bool = True
    use_artist: bool = True
    use_era: bool = True
    use_audio: bool = False        # 音频（PANNs）分类开关
    ai_threshold: float = 0.4
    audio_threshold: float = 0.3   # PANNs 概率阈值
    weight_ai: int = 0
    weight_audio: int = 1
    weight_net: int = 1
    net_limit: float = 10

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

    if model is not None:
        return model

    MODEL_PATH = resource_path("./models/models--sentence-transformers--all-MiniLM-L6-v2")
    MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
    has_config = os.path.isfile(os.path.join(MODEL_PATH, "config.json"))
    has_weights = any(
        os.path.isfile(os.path.join(MODEL_PATH, name))
        for name in ("model.safetensors", "pytorch_model.bin")
    )
    if not (has_config and has_weights):
        from huggingface_hub import snapshot_download

        snapshot_download(repo_id=MODEL_ID, local_dir=MODEL_PATH)
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
# SonglistCache 由 script.playlist_service 统一管理（与 fetch_playlist_songs 共用同一实例）

# ✅ 限流器：实际发请求前等待，保证间隔 >= min_interval
# （缓存命中不发请求，因此不占用限流额度）
class_limiter = api_limiter

def wy_search(title, artist, album, cfg: Config):

    BASE = "http://localhost:8080/api/v1"
    url = f"{BASE}/music/search"
    pnames = []

    plylist = []
    try:
        params = {
            "q": title,
            "type": "playlist"}
        data = TitleSLCache.get(title)
        if not data:
            class_limiter.wait()
            r = requests.get(url, params=params, timeout=30)
            # 非 JSON 响应（网关拦截/错误页）时跳过，避免 .json() 崩溃
            if "json" not in (r.headers.get("Content-Type") or "").lower() or not r.text:
                logger.warning(f"    /music/search 非 JSON 响应（HTTP {r.status_code}），跳过网络标签\n")
                return
            data = r.json().get("data",[])
            TitleSLCache.set(title, data)
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

        # ✅ 复用共享抓取（缓存 + 限流 + 请求，内部已捕获异常并返回 []）
        songs_raw = fetch_playlist_songs(pid, source, pname, logger)

        def is_similar(s1, s2):
            return (s1 in s2) or (s2 in s1)
        
        if songs_raw != [] and songs_raw != None:
            for s in songs_raw:
                if is_similar(title, s.get("name")) and is_similar(artist, s.get("artist")):
                    if play_cnt == 0:
                        pscore = 1
                    else:
                        # ✅ 防除零：track_cnt 为 0 时用 play_cnt 作分档
                        pscore = play_cnt / 100 / track_cnt if track_cnt > 0 else 1.0
                    pnames.append({"pname": pname, "pscore": pscore})
                    continue
                
        if pl_cnt > cfg.net_limit:
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
def ai_tags(title, artist, cfg: Config):

    model = get_model()

    text = f"{title} {artist}"
    emb = model.encode(text)

    cosine_sim = _get_cosine_similarity()
    results = []

    for tag, tag_emb in tag_embeddings.items():

        score = cosine_sim([emb], [tag_emb])[0][0]

        if score > cfg.ai_threshold:
            results.append(("AI", tag, score))

    return results

def ai_tags_from_lyric(lyric, cfg: Config):

    model = get_model()
    if not lyric:
        return []

    emb = model.encode(lyric)

    cosine_sim = _get_cosine_similarity()
    results = []

    for tag, tag_emb in tag_embeddings.items():

        score = cosine_sim([emb], [tag_emb])[0][0]

        if score > cfg.ai_threshold:
            results.append(("AI", tag, score))

    return results

# ---------------- 分类 ----------------
def classify(songs, cfg: Config):
    logger.info("歌曲分类中...")
    total = len(songs)
    song_cnt = 0

    # ✅ 每首歌 rank 归零，避免重复运行时累加翻倍
    for s in songs:
        s["rank"] = 0

    for s in songs:
        song_cnt += 1
        keyword = f"{s['title']} {s['artist']}"
        logger.info(f"  状态：处理中 {song_cnt}/{total}--->分析:"+keyword)

        if cfg.use_net:
            logger.info("    在线分类中...")
            names = wy_search(s['title'], s['artist'], s['album'], cfg)

            # ✅ 歌单标签
            tags = []
            for n in names:
                tags += extract_tags(n)

            for tag in tags:
                s["net_tags"][tag["tag"]]["score"] += tag["score"]
        
        if cfg.use_ai:
            # ✅ AI标签：有歌词用歌词语义；无歌词回退到 标题+歌手 语义（纯音乐也能打标）
            logger.info("    AI分类中...\n")
            lyric = s["lyric"]
            if lyric:
                ai = ai_tags_from_lyric(lyric, cfg)
            else:
                ai = ai_tags(s["title"], s["artist"], cfg)

            for source, tag, ai_score in ai:
                s["ai_tags"][f"AI_{tag}"]["score"] += ai_score

        if cfg.use_audio:
            # ✅ 音频（PANNs）标签：对所有歌推理，映射到中文标签
            logger.info("    音频分类中...\n")
            from cores.audio_classify import ai_tags_from_audio, get_cached, set_cached
            cached = get_cached(s["path"])
            if cached:
                audios = cached
            else:
                audios = ai_tags_from_audio(
                    s["path"],
                    threshold=cfg.audio_threshold,
                    log=logger,
                )
                set_cached(s["path"], audios)
            for cn_key, score in audios:
                # cn_key 形如 "AI_🎹_钢琴"，ai_tags 的键同为 f"AI_{tag}"
                if cn_key in s["ai_tags"]:
                    s["ai_tags"][cn_key]["score"] += score * cfg.weight_audio

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
        y = (s.get('year') or '')[:3]
        # ✅ 空/0 年份都跳过，避免生成 0_ERA_📅_0s 空歌单
        if y in ("0", ""):
            continue
        era_best[y].append(s)
        
    for y, y_songs in era_best.items():
       
        ranked = sorted(y_songs, key=lambda x: x["rank"], reverse=True)
        
        file_dir = f"{path}/0_ERA_📅_{y}0s"
        os.makedirs(file_dir, exist_ok=True)
        file_path = f"{file_dir}/0_ERA_📅_{y}0s.m3u"
        shutil.copy(resource_path("assets/covers/cover.jpeg"), file_dir)
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
        shutil.copy(resource_path("assets/covers/cover.jpeg"), file_dir)
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
    # ✅ 标签名形如 NET_🎧_流行 / AI_🎹_钢琴：取 _ 后两段拼封面名；
    #    若段数不符则退回默认封面，避免 IndexError
    pic_parts = tag_name.split('_')
    if len(pic_parts) >= 3:
        pic_name = f"{pic_parts[1]} {pic_parts[2]}"
    else:
        pic_name = ""
    pic_patch = resource_path(f"assets/covers/{pic_name}.png") if pic_name else ""
    
    if pic_patch and os.path.exists(pic_patch):
        shutil.copy(pic_patch, os.path.join(file_dir, "cover.png"))
    else:
        shutil.copy(resource_path("assets/covers/cover.jpeg"), file_dir)

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

def save(songs, cfg: Config):
    logger.info("生成歌单中...")

    # 存储缓存
    TitleSLCache.save()

    path = f"{cfg.music_dir}/AI分类歌单"
    # 保存 NET 标签歌单
    if cfg.use_net:
        logger.info("  生成 NET 标签歌单中...")
        for value in TAG_DEFINITIONS.values():
            for tag in value.keys():
                tag_name = f"NET_{tag}"
                for song in songs:
                    song["rank"] += song["net_tags"][tag_name]["score"] * cfg.weight_net
                save_plylist(songs, tag_name, path, "net_tags")

    # 保存 AI 标签歌单
    if cfg.use_ai:
        logger.info("  生成 AI 标签歌单中...")
        for tag in AI_LYRICS_DEFINITIONS.keys():
            tag_name = f"AI_{tag}"
            for song in songs:
                song["rank"] += song["ai_tags"][tag_name]["score"] * cfg.weight_ai
            save_plylist(songs, tag_name, path, "ai_tags")

    if cfg.use_era:
        logger.info("  生成 年代精选歌单中...")
        save_era(songs, path)

    if cfg.use_artist:
        logger.info("  生成 歌手精选歌单中...")
        save_artist(songs, path)

    # # ✅ DailyMix
    # ranked = sorted(songs, key=lambda x: x["score"], reverse=True)

    # file_dir = f"{path}/DailyMix"
    # os.makedirs(file_dir, exist_ok=True)
    # file_path = f"{file_dir}/DailyMix.m3u"
    # shutil.copy(resource_path("assets/covers/cover.jpeg"), file_dir)

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
    use_audio=False,
    ai_threshold=0.4,
    audio_threshold=0.3,
    weight_ai=0,
    weight_audio=1,
    weight_net=1,
    net_limit=10,
    log=None   # ✅ 接收GUI日志函数
):
    # ✅ 收敛为单一 Config，不再写 9 个 global
    cfg = Config(
        music_dir=music_dir,
        use_ai=use_ai,
        use_net=use_net,
        use_artist=use_artist,
        use_era=use_era,
        use_audio=use_audio,
        ai_threshold=ai_threshold,
        audio_threshold=audio_threshold,
        weight_ai=weight_ai,
        weight_audio=weight_audio,
        weight_net=weight_net,
        net_limit=net_limit,
    )

    if log:
        set_logger(log)

    logger.info("读取本地歌曲\n")
    songs = load_music(cfg.music_dir, log=logger)
    logger.info(f"本地歌曲:{len(songs)}\n")

    songs = classify(songs, cfg)
    save(songs, cfg)

    SonglistCache.save()
    if cfg.use_audio:
        from cores.audio_classify import save_cache as save_audio_cache
        save_audio_cache()
    logger.info("分类完成")

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="本地分类核心（GUI/CLI 双模式）")
    p.add_argument("music_dir", help="音乐目录")
    p.add_argument("--no-ai", action="store_true", help="禁用 AI 标签")
    p.add_argument("--no-net", action="store_true", help="禁用 NET 标签")
    p.add_argument("--no-artist", action="store_true", help="禁用歌手精选")
    p.add_argument("--no-era", action="store_true", help="禁用年代")
    p.add_argument("--ai-threshold", type=float, default=0.4)
    p.add_argument("--audio", action="store_true", help="启用音频（PANNs）分类")
    p.add_argument("--audio-threshold", type=float, default=0.3)
    p.add_argument("--weight-ai", type=int, default=0)
    p.add_argument("--weight-audio", type=int, default=1)
    p.add_argument("--weight-net", type=int, default=1)
    p.add_argument("--net-limit", type=float, default=10)
    ns = p.parse_args()

    run_classifier(
        music_dir=ns.music_dir,
        use_ai=not ns.no_ai,
        use_net=not ns.no_net,
        use_artist=not ns.no_artist,
        use_era=not ns.no_era,
        use_audio=ns.audio,
        ai_threshold=ns.ai_threshold,
        audio_threshold=ns.audio_threshold,
        weight_ai=ns.weight_ai,
        weight_audio=ns.weight_audio,
        weight_net=ns.weight_net,
        net_limit=ns.net_limit,
    )
