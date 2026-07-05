# AI歌单生成器（AI Music Classifier）

## 项目简介

一个基于 Python + AI(sentence-transformers) + CustomTkinter + go-music-api 的本地音乐歌单生成工具:

- 本地AI部署，智能本地音乐分类及权重推荐
- 多平台歌单支持，自动匹配本地歌曲，多钟搜索配置
- 自动生成 M3U 播放列表，包含丰富元数据，兼容各大平台
- 实现多平台推荐与本地收藏融合
- 歌曲元数据增强，自动补全原始文件中缺失的元数据
- 根据歌曲元数据信息自动整理文件结构

主要支持：
- 🎵 本地音乐管理
- 🎧 多类型歌单生成
- 🤖 AI 标签分类
- 🏷️ 元数据增强
- 📂 M3U 歌单导出
- 🔍 多平台支持

---

## 功能特性

### 🎵 本地音乐管理

用于管理和分析本地音乐库：

- 扫描指定目录
- 自动读取歌曲信息
- 提取标题、歌手、专辑
- 自动整理文件结构
- 元数据增强

### 🎧 多类型歌单生成

支持多种类型歌单生成：

- AI分类歌单生成、网路分类歌单生成
- 单关键词、多关键词生成歌单
- 手动搜索歌单生成
- 随机搜索歌单生成

### 🤖 AI 标签分类

使用AI工具，分析歌曲匹配不通标签，主要支持：

```
💔 失恋
😢 悲伤
😌 治愈
😊 开心
🔥 热血
🌙 夜晚
📖 学习
🚗 车载
🏃 运动
🛌 睡眠
💍 爱情
📼 回忆
🌈 青春
```

### 🏷️ 元数据增强

自动从网络补全歌曲信息：

- 基础信息：标题、歌手、专辑（如果原文件没有，则需要从文件名获取搜索信息）
- 歌词内置到歌曲文件中
- 专辑封面，可自定义最大分辨率（主要用于适配不同播放器）


### 📂 M3U 歌单导出

```
#EXTM3U
#PLAYLIST:NET_🌈_青春
#EXTALB:在我心里有个你
#EXTART:周传雄
#EXTINF:293,周传雄 - 关不上的窗
D:/Work/Personal/MusicC/py_version\关不上的窗 - 周传雄.flac
#EXTALB:最伟大的作品
#EXTART:周杰伦
#EXTINF:244,周杰伦 - 最伟大的作品
D:/Work/Personal/MusicC/py_version\周杰伦\最伟大的作品 - 周杰伦.flac
```

### 🔍 多平台支持

| 平台       | Source   |
| ---------- | -------- |
| 网易云音乐 | netease  |
| QQ 音乐    | qq       |
| 酷狗音乐   | kugou    |
| 酷我音乐   | kuwo     |
| 咪咕音乐   | migu     |
| 千千音乐   | qianqian |
| 汽水音乐   | soda     |
| 5sing      | fivesing |
| Jamendo    | jamendo  |
| JOOX       | joox     |

*基于 go-music-api 集成*

## GUI界面

*基于 CustomTkinter 开发*

### AI歌曲分类

![](./asset/local.png)

### 网络歌单匹配

![](./asset/net.png)

### 歌曲元数据增强

![](./asset/meta.png)

### 音乐文件整理

![](./asset/class.png)

## License

Apache License 2.0

## 现有问题记录

1. mp3文件支持有bug
2. 音乐年份获取统一使用netease源
