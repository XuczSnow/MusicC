# AI歌单生成器（AI Music Classifier）

2026.11.20

## Release Note v1.2.0

### 功能更新

1. 新增 **CLI / GUI 双模式**：除"关于"外的四个页面（本地分类、平台歌单、元数据增强、音乐整理）都支持带参数走 CLI、无参数走 GUI，便于定时任务与脚本化
2. 核心逻辑拆分为独立 **core 模块**（`cores/`），无 GUI 依赖，可单独打包 / 运行
3. 元数据增强新增 **AI 同步（对齐歌词时间戳）**：有网络同步歌词时用本地 ASR 校验前几句是否对齐，对齐采用网络 LRC，否则 ASR 全曲生成 LRC
4. 元数据增强新增 **AI 增补（无歌词时生成）**：对没有歌词的歌曲用本地 ASR（faster-whisper）识别生成同步歌词 LRC
5. ASR 采用 **GPU 自动探测回退**（cuda → cpu）与**本地模型优先**（`models/faster-whisper-small`），离线可用
6. 同步歌词 LRC 写入 FLAC `lyrics` 与 MP3 `USLT`，播放器可逐行高亮
7. 本地分类新增 **AI 音频分类（PANNs Cnn14）**：按音频本身（波形/频谱）识别情绪/流派/声音事件，无需歌词，纯音乐也能分类；PANNs 权重存在时优先用 PANNs（torchlibrosa），否则回退轻量 `librosa`，全程本地
8. 本地分类修复：`save_era` 空/0 年份不再生成空歌单、`pscore` 收藏数除零兜底、`save_plylist` 标签名段数不符不再 IndexError；无歌词歌曲改用标题+歌手做 AI 情绪标签（不再留空）
9. **启动检查更新**：软件与 go-music-api 同时查 GitHub 最新 release，弹窗提示是否前往下载；「检查更新」按钮放在关于页按钮行，版本显示在作者同一行
10. **go-music-api 自动更新**：检测到新 API 版本时一键下载 `windows_amd64.zip` 替换本地二进制并写 `version.txt`，自动重启服务
11. **无时间戳歌词 AI 对齐**：歌词非空但无 `[m:ss]` 时间戳时，ASR 逐行对齐补时间戳、**保留原歌词字句**；元数据歌词处理重构为两阶段（信息增补 + 歌词处理），`sync_lyric` 优先，「歌词偏移」单独开启也能对已有歌词生效
12. 歌词脏数据判定修复：`is_dirty_lyric` 不再把"无时间戳的纯文本歌词"误判为脏（改按无效短语/乱码/广告判定）

### 功能无关更新

1. 代码结构整理：`*_core.py` 归类到 `cores/` 目录，页面统一为"薄 GUI 壳 + 双模式入口"
2. 打包相关文件（`*.spec` / `*.iss` / `*.isl` / `icon.ico`）移入 `backup/`，本仓库不再维护打包脚本
3. 依赖更新：新增 `faster-whisper`、`librosa`、`torchlibrosa` 并锁定 `av==18.1.0`（规避 Python 3.14 下新版 PyAV 的 `metadata_errors` 崩溃）
4. 新增本地模型 `models/panns_Cnn14/`（`model.safetensors` + `tags.txt`），用于 AI 音频分类；缺失时自动回退 `librosa`
5. README 增加"架构 / CLI 运行"章节
6. 线程安全：GUI 启动 API 与各页面后台任务不再在子线程直接改 Tk widget（含 `after`），统一改为主线程回调更新，消除 `main thread is not in main loop` 崩溃
7. 平台歌单：preset（模板）模式补传音乐目录，修复此前不写歌单的问题；`save_playlist` 路径统一 `os.path`、`path` 缺失兜底；`pypinyin` 导入提顶
8. 音乐整理：move 目标同名自动加序号避免覆盖；输出目录位于音乐目录内部时给出提示；文件后缀改用 `os.path.splitext`
9. 资源目录整理：歌单封面（emoji 图 + `cover.jpeg`）归入 `assets/covers/`、主题配色归入 `assets/themes/`；README 界面截图归入 `docs/screenshots/`，并同步更新代码与文档中的引用路径
10. 线程安全补全：本地分类 / 元数据 两页的后台任务子线程改 Tk widget 问题（同第 6 条根因）统一修复，四页全部落实"子线程写变量 + 主线程 after 轮询"
11. 网络请求健壮性：歌单/元数据接口对非 JSON 响应（网关拦截等）优雅降级不崩溃；移除"歌单需 cookie"的假设（公开搜索无需登录态）
12. 修复 `version.is_newer` 版本号比较 bug（此前 `v1.0.2` 被误解析为 `v1`，导致更新判定全错）；`start_service.set_logger(None)` 空指针兜底
13. 新增 `docs/页面逻辑梳理.md`：四大页面调用链路 / 数据流 / 开关说明 + Mermaid 框图
14. `.gitignore` 增加临时测试文件与打包产物忽略项

## 项目简介

> 一个集 **本地音乐管理、AI 智能分类、网络歌单生成、元数据补全、音乐库整理** 于一体的桌面音乐管理工具。

*基于 Python + AI(sentence-transformers + faster-whisper) + CustomTkinter + go-music-api*

- 本地AI部署，智能本地音乐分类及权重推荐
- 多平台歌单支持，自动匹配本地歌曲，多钟搜索配置
- 自动生成 M3U 播放列表，包含丰富元数据，兼容各大平台
- 实现多平台推荐与本地收藏融合
- 歌曲元数据增强，自动补全原始文件中缺失的元数据
- 根据歌曲元数据信息自动整理文件结构
- **核心逻辑 CLI 化**，GUI / CLI 双模式

主要支持：

- 🎵 本地音乐管理
- 🎧 多类型歌单生成
- 🤖 AI 标签分类
- 🏷️ 元数据增强
- 📂 M3U 歌单导出
- 🔍 多平台支持
