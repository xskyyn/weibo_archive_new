# WeiboArchive · 微博归档工具

> 纯本地运行的微博数据备份工具：把个人微博动态、长文、图片、视频、评论完整归档到本机，支持可视化浏览、中文全文检索与离线导出。

基于 **FastAPI + Vue 3 + PyWebView** 构建，所有数据仅保存在本地，服务只监听 `127.0.0.1`，不向任何第三方上传数据。

## ✨ 功能特性

- **完整归档**：微博正文、长文、图片、视频（含 LivePhoto）、发布位置、一二级评论、用户头像全量抓取
- **断点续抓**：按微博 mid 去重，归档中断后重新运行可自动跳过已抓内容、继续补抓缺失数据
- **反爬对抗**：httpx 异步并发 + 随机延迟 + 指数退避重试 + XSRF-TOKEN 自动续期，识别并暂停验证码
- **中文全文检索**：SQLite FTS5 + jieba 分词，毫秒级中文关键词搜索
- **可视化浏览**：仪表盘统计热力图、无限滚动时间线、媒体瀑布流画廊、实时任务控制台（WebSocket 日志）
- **数据导出**：单条微博 → Markdown；全量 → HTML 离线包（ZIP）
- **数据目录可配置**：数据库与媒体文件目录可在应用内「设置」页自由切换
- **扫码登录 / 多账号**：支持扫码登录、Cookie 导入、多账号切换与按目标用户隔离归档

## 📦 下载安装（Windows）

从 [GitHub Releases](https://github.com/xskyyn/weibo_archive_new/releases) 下载最新正式版本：

| 文件 | 说明 |
|------|------|
| `WeiboArchive-Setup-*.exe` | 一键安装包：可自选安装目录，自动创建桌面/开始菜单快捷方式，含卸载程序 |
| `WeiboArchive.exe` | 免安装绿色版：单文件双击即用 |
| `WeiboArchive-*-md5.txt` | MD5 校验文档，用于核对下载文件完整性 |

> 无需安装 Python / Node / 浏览器环境。首次启动后，在「账号管理」中扫码登录或导入 Cookie，再到「任务中心」启动归档即可。

## 🚀 源码运行

```bash
# 1. 安装依赖（自动创建 .venv）
./start.sh

# 或手动：
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
(cd frontend && npm install && npm run build)

# 2. 启动
./.venv/bin/python -m backend.main
# 浏览器访问 http://127.0.0.1:8964
```

### Windows 打包

```bat
# 构建前端 → 安装依赖 → PyInstaller 打包 EXE → 生成绿色版 zip
build_windows.bat

# 安装包：用 Inno Setup 编译 WeiboArchive.iss
```

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| 后端 | FastAPI · SQLAlchemy 2.0 (async) · aiosqlite · httpx · tenacity |
| 搜索 | SQLite FTS5 + jieba 中文分词 |
| 前端 | Vue 3 · Vite · TypeScript · Element Plus · ECharts · Pinia |
| 桌面壳 | PyWebView（打包版内嵌窗口） |
| 打包 | PyInstaller + Inno Setup |

## 📁 项目结构

```
backend/                 # Python 后端 (FastAPI)
  main.py                # 启动入口与生命周期
  config.py              # 端口/路径/并发配置
  database.py            # SQLAlchemy 模型 + FTS5 + jieba 分词
  desktop.py             # Windows 桌面壳（PyWebView 内嵌窗口）
  routers/               # auth / task / posts / export / settings
  scraper/
    client.py            # httpx 封装 + 风控 + Token 刷新
    parser.py            # 微博/评论/媒体/位置解析
    media_downloader.py  # 媒体 + 头像下载
    task_manager.py      # 后台调度 + 断点续抓 + WebSocket
  utils/logger.py        # 日志 + Cookie 脱敏
  templates/             # HTML 离线包模板
frontend/                # Vue 3 前端
workspace/               # 运行时数据（数据库与媒体，自动生成，不入库）
```

## 🔒 隐私与安全

- 所有网络请求仅发往 `weibo.com / m.weibo.cn / sinaimg.cn`，服务仅监听 `127.0.0.1`
- Cookie 等登录凭证仅保存在本地，日志自动脱敏，不入 git
- `workspace/`（数据库与媒体）、`cookie.json` 等运行时数据均已被 `.gitignore` 忽略

## 📄 License

本项目仅用于个人数据备份与学习交流，请遵守微博平台服务条款，合理使用。
