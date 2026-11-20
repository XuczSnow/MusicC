# -*- coding: utf-8 -*-
"""cores — 各功能的"核心"逻辑包（无 GUI 依赖，可独立 CLI 运行 / 可单独打包）。

每个子模块对应一个 page：
  - classify_core     本地 AI/网络分类
  - net_playlist_core 平台歌单抓取与匹配
  - metadata_core     元数据增强 + ASR 对齐/增补
  - organize_core     音乐整理
"""
