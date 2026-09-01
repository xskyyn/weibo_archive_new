# WeiboArchive · 微博归档工具

基于 **FastAPI + Vue 3** 的本地微博数据归档工具。归档并可视化浏览个人微博动态、长文、图片、视频与多级评论，支持中文全文检索与离线导出。

## 功能

- 🥷 反爬对抗：httpx 异步 + 随机延迟 + 指数退避重试 + XSRF-TOKEN 自动续期，识别并暂停验证码(-100)。
- 🧵 异步归档引擎：`asyncio.Semaphore` 并发控制，`since_id` 游标分页，支持断点续传。
- 🎞 媒体下载：图片/视频流式下载，特殊封装自动调用 ffmpeg 转 mp4。
- 💬 评论树：一级 + 二级评论递归归档，构建互动关系网。
- 🔍 中文全文检索：SQLite FTS5 + jieba 分词，毫秒级搜索，解决中文分词痛点。
- 📊 可视化：仪表盘热力图、无限滚动时间线、媒体瀑布流画廊、实时任务控制台。
- 📦 导出：单条微博 → Markdown；全量 → HTML 离线包(ZIP)。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI · SQLAlchemy 2.0(async) · aiosqlite · httpx · tenacity |
| 搜索 | SQLite FTS5 + jieba |
| 前端 | Vue 3 · Vite · TypeScript · Element Plus · ECharts · Pinia |

## 快速开始

```bash
# 1. 安装依赖（自动创建 .venv）
./start.sh

# 或手动：
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
(cd frontend && npm install && npm run build)

# 2. 准备登录凭证
# 将微博登录后的 Cookie 导出为 JSON 保存为 /opt/webo_archive/cookie.json
# 格式：{"SUB":"...","SUBP":"...","XSRF-TOKEN":"...", ...}

# 3. 启动
./.venv/bin/python -m backend.main
# 浏览器访问 http://127.0.0.1:8964
```

接口文档：启动后访问 `http://127.0.0.1:8964/docs`。

## 项目结构

```
backend/
  main.py            # 启动入口与生命周期
  config.py          # 端口/路径/并发配置
  database.py        # SQLAlchemy 模型 + FTS5 + jieba 分词
  schemas.py         # Pydantic 模型
  routers/           # auth / task / posts / export
  scraper/
    client.py        # httpx 封装 + 风控 + Token 刷新
    parser.py        # 微博/评论/媒体解析
    media_downloader.py
    task_manager.py  # 后台调度 + WebSocket
  utils/logger.py    # 日志 + Cookie 脱敏
  templates/         # HTML 离线包模板
frontend/            # Vue 3 前端
workspace/           # SQLite 与媒体文件（自动生成）
cookie.json          # 登录凭证（本地，勿提交）
```

## 说明

- 所有网络请求仅发往 `m.weibo.cn / sinaimg.cn`，服务仅监听 `127.0.0.1`，Cookie 仅存本地。
- 首次使用请先在“导入/校验 Cookie”中粘贴 Cookie 并校验，再到“任务中心”启动归档。
- ffmpeg 非必需；仅当微博返回特殊视频封装时才需要，未安装会自动跳过并提示。