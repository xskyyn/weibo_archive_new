# Changelog

本文件遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/)（`主.次.修订`），并遵循 `VERSIONING.md` 的提交/发版/打 Tag 规范。新版本区块一律从顶部追加，不在历史版本上编辑。

## [1.1.3] - 2026-09-01

### 🐛 修复

- **扫码弹窗出现 Edge 自带的"附加条款"占位页**：
  - 根因：用全新的 `--user-data-dir` profile 启动 Edge/Chrome 时，浏览器会自行弹出首启·附加条款页（页面上的 "This space intentionally blank / In official builds this space will show the terms of service." 占位框即来自该页，而非微博页；此前注入微博 DOM 自然无效）
  - 修复：`backend/login.py` 启动参数增加 `--no-first-run`、`--no-default-browser-check`、`--disable-background-networking`、`--disable-sync`、`--disable-features=msEdgeFirstRunExperience,msEdgeFirstRunExperienceOptIn`，抑制首启/附加条款/欢迎页；连接调试端口后关闭其余多余 page 标签、将微博登录页 `Page.bringToFront`
  - 验证：headless 启动后仅剩 1 个 page 标签且 URL 为 `passport.weibo.com/sso/signin`

### 📝 关键经验

- 无头/可控浏览器启动务必带上 `--no-first-run` 等参数，否则新 profile 会叠加浏览器自带首启页，干扰自动化目标与 DOM 注入

## [1.1.2] - 2026-09-01

### 🐛 修复

- **扫码隐私提示在真实浏览器中未生效，仍显示占位文本**：
  - 根因一（主因）：微博 passport 页面占位文本为小写（"This space intentionally blank"），而 v1.1.1 注入匹配标记为大写且大小写敏感，直接脱靶
  - 根因二：该占位可能位于登录 iframe（passport.weibo.com 登录框）内，而 v1.1.1 仅遍历顶层 `document.body`
  - 修复：`backend/login.py` 注入改为**忽略大小写**匹配特征短语（`this space intentionally` / `in official builds this space`），并对**顶层文档 + 全部同源 iframe 递归遍历**；同时调整为幂等（`#wbar-privacy-panel` 哨兵），并在二维码捕获后再注入一次兜底
  - 验证：headless 注入实测 `replaced:2`（顶层替换为提示面板、iframe 内占位被清除），且重复注入不产生重复内容

### 📝 关键经验

- 跨站文案注入不要假设目标文本的大小写；匹配一律 `toLowerCase` 做包含判断
- 页面登录表单若可能位于 iframe，注入逻辑必须能递归进入 `iframe.contentDocument`（同源），否则静默脱靶

## [1.1.1] - 2026-09-01

### 🎨 样式/UI

- **扫码登录弹窗增加自定义隐私/安全提示**：替换浏览器窗口中的默认占位文本（"This Space Intentionally Blank / In official builds this space will show the terms of service."）
  - **方案B（CDP 注入）**：`backend/login.py` 在打开登录页后通过 `Runtime.evaluate` 注入 JS，遍历 DOM 文本节点定位并替换占位文案为「🔒 隐私与安全说明」（数据仅存本地 / 安全可靠 / 自主可控 + 同意提示），Edge 与 Chrome 通用
  - **方案A（前端渲染）**：`AccountManager.vue` 在二维码下方渲染同款隐私提示，二维码提取失败兜底整页截图场景下同样可见

### 🐛 修复

- **扫码弹窗显示英文占位文本，缺少隐私说明**：根因是微博登录页内置的占位模板文案 → 通过 CDP 注入自动替换，无需改动微博页面源码

### 📝 关键经验

- 需自绘浏览器页面文案时，不要依赖微博页面的 class/选择器（易随页面改版失效）；改用「按文本节点内容定位 + 替换」最稳
- 后端注入需在截图兜底逻辑之前执行，才能保证整页截图也包含自定义文案

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