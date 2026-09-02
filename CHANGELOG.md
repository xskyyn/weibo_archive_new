# Changelog

本文件遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/)（`主.次.修订`），并遵循 `VERSIONING.md` 的提交/发版/打 Tag 规范。新版本区块一律从顶部追加，不在历史版本上编辑。

## [1.3.2] - 2026-09-02

### 🐛 修复

- **断点续抓失效**：归档循环以「本页新增 0 条」作为终止条件，导致重跑时第 1 页（最新微博均已归档）就提前 break，永远到不了缺失的旧微博页（实测重装后仍停在中断位置）。已移除该终止条件，改为仅依赖接口返回空列表判定归档结束，并把已归档的本人微博 mid 载入 `seen_ids` 实现断点续抓
- 修复后重新归档会先跳过已抓内容，继续向后翻页补抓缺失微博（附单元测试验证：前两页全为已归档、第三页新增、第四页空列表时正确翻页补抓）

## [1.3.1] - 2026-09-02

### 🐛 修复

- **归档任务崩溃**：`task_manager.py` 在 `except WeiboAuthError` 中使用了未导入的异常类，导致微博接口返回认证错误（`http_code=400`，账号受限或 Cookie 失效）时任务以 `NameError` 崩溃、归档中断。已补全 `WeiboAuthError` 导入，认证错误将按预期以清晰报错结束任务
- 归档任务按 mid 去重，修复后重新归档可续抓缺失微博，无需清库重来

## [1.3.0] - 2026-09-02

### 🚀 新功能

- **安装目录可自选**：Inno Setup 安装包显式开启目录选择页（`DisableDirPage=no`），用户可在向导中自由选择安装位置（默认 `%LOCALAPPDATA%\Programs\WeiboArchive`，无需管理员权限）
- **数据目录可配置**：新增「设置」页（侧栏入口），可查看/修改数据文件存放位置
  - 数据目录涵盖数据库、图片、视频、导出文件等全部运行时数据
  - 后端新增 `GET/PUT /api/settings/workspace`（读取/保存数据目录）、`POST /api/settings/pick-dir`（系统目录选择对话框）、`POST /api/settings/restart`（重启应用）
  - 设置持久化到独立于数据目录的 `settings.json`（打包版位于 `%APPDATA%\WeiboArchive\settings.json`），切换数据目录后设置不丢失
  - 保存新目录后自动重启应用生效（桌面壳检测重启标志并 `os.execv` 重启）

### 🔧 技术变更

- `backend/config.py`：新增 `SETTINGS_FILE` 与设置读写（`get_settings`/`save_workspace_dir`）、重启标志（`request_restart`/`consume_restart_flag`）；数据目录优先级调整为「环境变量 > 设置文件 > 默认」
- `backend/routers/settings.py`：新增设置路由
- `backend/desktop.py`：窗口关闭后检测重启标志并自动重启
- `frontend/src/views/SettingsView.vue`：新增设置页（数据目录输入/浏览/保存重启）
- `WeiboArchive.iss`：`DisableDirPage=no` 开启安装目录选择

### 📝 关键经验

- 数据目录是模块级常量（`WORKSPACE_DIR`），运行时不可热切换，变更后必须重启进程；重启标志写入独立文件，由桌面壳在退出时检测并 `os.execv` 拉起新进程

## [1.2.0] - 2026-09-02

### 🚀 新功能

- **微博视频爬取**：支持新版混合媒体结构 `mix_media_info.items` 中的视频与 livephoto
  - 视频：优先取 `media_info.playback_list` 最高清晰度 mp4（如 1080p），回退 `media_info` 各档地址（`mp4_720p_mp4` / `mp4_hd_url` / `stream_url` 等）
  - livephoto：提取 `data.video` 的 `.mov` 源，经 ffmpeg 转封装为 mp4
  - 兼容旧结构 `page_info.urls` 视频解析，按 URL 去重
  - **媒体补齐**：归档任务新增 `backfill_missing_fields`，为已入库历史微博从 `raw_json` 补齐缺失媒体（旧版本未解析出的视频等）与发布位置，幂等执行
  - **ffmpeg 转封装修复**：特殊封装先下载到本地临时文件再转封装，兼容 `--disable-network` 精简版 ffmpeg（此前直接传 URL 给 ffmpeg 会失败）

- **发布位置抓取与展示**：新增 `Post.region_name` 字段（如"发布于 北京"）
  - 解析新微博时抓取 `region_name`；`init_db` 增加轻量迁移，已存在的库自动 `ALTER TABLE` 补列
  - API 返回 `region_name`，前端 `PostCard` 在发布时间旁展示位置
  - 历史数据补齐：已入库历史微博自动回填发布位置

### 🐛 修复

- **视频未抓取**：此前解析器只处理 `pics`/`pic_ids`/`page_info`，新版接口的 `mix_media_info` 视频被漏掉；全库视频数为 0，现已补齐并下载

### 📝 关键经验

- 微博新版接口的媒体可能位于 `mix_media_info.items`（含 `type:"video"` 与 livephoto），解析需兼容多套结构
- 精简版 ffmpeg（`--disable-network`）无法直接拉取 URL，转封装前必须先把源文件下载到本地

## [1.1.7] - 2026-09-02

### 🐛 修复

- **归档浏览：输入关键词点「搜索」后页面仍显示初始数据，接口其实已返回正确结果**：
  - 根因：模板 `@click="doSearch"` / `@keyup.enter="doSearch"` 会把**事件对象**作为第一个实参传入，导致 `loadMore = <Event>`（真值），`if (!loadMore)` 判断为假 → **跳过了 `posts.value = []` 清空**，搜索结果被 `push` 追加到原有全量列表之后（如 20 + 3 = 23 条），顶部看到的仍是"最开始的数据"
  - 修复：`ArchivesView.vue` 将参数判断改为 `const more = loadMore === true`（严格布尔），杜绝 Event 对象被当作 truthy
  - 附带健壮性修复：
    - `resetFilters` 补上 `keyword.value = ''`（此前重置不清关键词，会再次以旧词搜索）
    - `doSearch` 增加递增请求序号 `_searchSeq` 守卫，丢弃过期/乱序响应，消除 watch 与显式调用、初始挂载与搜索之间的竞态覆盖
    - `doSearch` 增加 `catch` 分支，异常时不再让列表静默停在空态
  - 验证：headless 驱动真实页面四场景全通过——搜索"剑来"→3 条、重置→20 条且清空关键词、搜索"剑落"(0 命中)→0 条、回车搜索"剑来"→3 条

### 📝 关键经验

- Vue 模板 `@click="fn"` 无括号调用会把原生 Event 作为首参传入；带默认值的可选布尔参数务必用 `=== true` 严格判断，勿用 `!param` 真值判断

## [1.1.6] - 2026-09-01

### 🐛 修复

- **扫码弹出的浏览器顶部出现"不受支持的命令行标志:--no-sandbox"警告条**：
  - 根因：启动浏览器固定带 `--no-sandbox`，在普通用户桌面运行时触发 Chrome/Edge 的安全警告条
  - 修复：新增 `_is_root()`，仅当以 root（POSIX `os.geteuid()==0`）运行时才追加 `--no-sandbox`，普通用户省略；同时增加 `--disable-infobars` 抑制信息条
  - Windows 恒为 False（`geteuid` 不可用），故 Windows EXE 不再传 `--no-sandbox`，无警告

## [1.1.5] - 2026-09-01

### 🎨 样式/UI

- **移除账号管理「扫码登录」页内嵌二维码展示**：对话框内回显的二维码扫描后并不会真正写入 Cookie（真实有效的二维码在弹出浏览器窗口中的 passport.weibo.com 页面），展示它误导用户。改为明确文案引导用户在弹出窗口扫码并用手机 App 确认，保留状态轮询 + 「我已扫码，获取Cookie」/「取消」按钮与隐私说明。

### ♻️ 重构

- `AccountManager.vue` 移除死代码 `refreshQrImg`（内嵌二维码相关）

## [1.1.4] - 2026-09-01

### 🐛 修复

- **扫码后点「我已扫码，获取Cookie」提示未读取到登录**：
  - 根因：登录态检测与 Cookie 提取原先依赖 `document.cookie`，而微博登录凭证（SUB/gsid）可能是 HttpOnly，`document.cookie` 读不到 → 被误判为"未登录/无有效 Cookie"，进入确认时的校验失败
  - 修复：新增 `_all_cookies()`，优先 `Network.enable` + `Network.getAllCookies` 读取（**能拿到 HttpOnly 凭证**），失败才回退 `document.cookie`；登录态判定改为基于是否含 SUB/SUBSCRIBE/gsid；`Network.enable` 一次性初始化
  - 附带：确认接口增加明确的登录态校验，未检测到登录时给出可操作提示（确认手机已扫码并点击「确认登录」）
  - 验证：headless 下 `_all_cookies` 可读到 `X-CSRF-TOKEN`（HttpOnly），证明 Network 读取路径正常；登录前 `has_auth_cookie=False`

### 📝 关键经验

- 读取浏览器 Cookie 优先走 CDP `Network.getAllCookies`（含 HttpOnly），切勿依赖 `document.cookie`（对 HttpOnly 无可见性）

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