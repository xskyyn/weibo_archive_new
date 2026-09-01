# Changelog

本文件遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/)（`主.次.修订`），并遵循 `VERSIONING.md` 的提交/发版/打 Tag 规范。新版本区块一律从顶部追加，不在历史版本上编辑。

## [1.1.0] - 2026-09-01

### 🚀 新功能

- **扫码登录（原生 CDP 驱动本机 Edge/Chrome）**：点击「账号管理 → 扫码登录」自动弹出浏览器并打开微博扫码页，前端回显二维码，手机微博 App 扫码确认后自动抓取 Cookie、解析本人 UID/昵称并保存为当前账号
  - 复用本机 Chrome/Edge，无需额外安装浏览器驱动
  - 二维码提取失败时兜底整页截图，并支持「直接在弹窗浏览器窗口扫码」

- **多账号管理**：新增「账号管理」页（`AccountManager`，替代原 CookieDialog）
  - 支持扫码登录、手动导入 Cookie、设为当前账号、退出（清除登录态）、删除账号
  - 多账号 Cookie 按 `accounts/<id>/cookie.json` 持久化，元数据存 `accounts.json`

- **抓取/浏览不同用户数据**：侧栏可设置「会话目标 UID」，归档与浏览自动切换到该用户；各目标用户数据（数据库 + 媒体 + 头像）按 `workspace/<uid>/` 完全隔离

### 🐛 修复

- **扫码登录在 Edge 上点击无法打开浏览器**：根因是新浪收紧匿名 SSO 后纯 httpx 方案失效，且改用 DrissionPage 4.1 时与本机 Edge 152 存在兼容缺陷（初始化会对同一 `/devtools/browser/<id>` 建第二条 websocket，被 Edge 以 404 拒绝）→ 修复方案为弃用 DrissionPage，改用 `websocket-client` 直连本机浏览器的原生 CDP；已在真机 + headless 双路径验证二维码生成、轮询、Cookie 提取均正常

### ♻️ 重构

- `backend/login.py` 重写为 `CdpSession`（JSON-RPC over websocket 极简客户端 + 外部启动 Edge 指定调试端口）

### 🔧 技术变更

- 依赖：移除 `drissionpage`，新增 `websocket-client>=1.7`
- 浏览器用户数据目录（含登录 Cookie）移入 `WORKSPACE_DIR` 之外的 `.weibo_browser_profiles`，防止被 `/media` 静态路由暴露
- `.gitignore` 新增忽略 `logs/`、`.weibo_browser_profiles/`、`qr_cache/`