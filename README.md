# Smart Context Capture

一个面向 Codex Desktop/CLI 的统一上下文 Skill 原型：Python Gateway 负责来源识别、能力探测、适配器路由和统一 `ContextPacket`；真正访问 Chrome/Figma 的权限仍由对应的 CDP、MCP、扩展或 API token 提供。

## 快速开始

```powershell
python -m pip install --editable . --no-deps
smart-context --doctor --pretty
smart-context .\planning\PLAN.md --pretty
# 可选持久缓存（只在显式指定目录时启用）
smart-context .\planning\PLAN.md --cache-dir .\.smart-context-cache --pretty
# 如果当前 shell 没有安装 smart-context，可从任意目录运行插件内置启动器
python .\skills\smart-context-capture\scripts\run_capture.py --doctor --pretty
python .\scripts\check_release.py
```

当前内置能力：

- 本地只读：TXT/Markdown/代码、HTML、CSV/TSV、JSON；带大小限制、编码回退、结构化数据、来源追踪和截断警告。
- 可选富文档：安装 `pip install markitdown` 后，PDF/DOCX/PPTX/XLSX 等会自动走 `local-rich` 适配器；未安装时不会伪装成成功读取。
- 公开网页低权限读取：普通 `http(s)` URL 会先走 `public-http`，只请求公开响应，不使用浏览器 Cookie、不执行 JavaScript，也不需要 Computer Use。
- Chrome 只读：标准 Chrome DevTools Protocol。设置 `SMART_CONTEXT_CDP_URL`，默认访问 `http://127.0.0.1:9222`。
- Figma 只读：Figma REST API。设置显式 `FIGMA_ACCESS_TOKEN`；支持文件/节点链接、节点树、组件/样式摘要和可选渲染 URL。
- PDF、Office、图片 OCR 和官方 MCP：通过同一 Gateway 注册可选适配器，不把第三方依赖硬编码进核心包。

运行时要求 Python 3.10+。如果 Codex 当前环境没有 Python，Skill 会报告缺少运行时；它不会把一个本可用的低权限读取偷偷升级成 Computer Use。

## Chrome 前提

普通 Chrome 进程不会因为 Python 存在就自动开放当前标签页。必须由用户显式启动一个带远程调试端口的 Chrome 实例，或配置一个兼容的 Chrome Relay/MCP。示例（使用独立临时 profile，避免触碰普通 profile）：

```powershell
start chrome --remote-debugging-port=9222 --user-data-dir="$env:TEMP\smart-context-chrome"
$env:SMART_CONTEXT_CDP_URL = "http://127.0.0.1:9222"
smart-context current --source chrome_tab --pretty
```

只有一个页面时 `current` 才是无歧义的；多个页面请传精确 URL、标题或 target id。CDP 本身不保证暴露前台标签页，若必须读取“用户当前正在看的 tab”，应使用 Chrome connector/relay。端口不存在时，命令会快速返回 `unavailable` 和具体原因，不会读取 cookies、密码或无关标签页。

普通公开 URL 默认先走低权限 HTTP，即使本机 CDP 可用也不会主动打开浏览器会话。只有需要登录态、JavaScript 渲染或当前标签页时，才显式加 `--browser-session`：

```powershell
smart-context "https://example.com" --source chrome_tab --pretty
smart-context "https://private.example/app" --source chrome_tab --browser-session --pretty
```

## 权限阶梯

Skill 会按最低权限优先路由：

```text
本地/公开 HTTP
    → 已配置 Connector / MCP
    → Chrome CDP / 浏览器 DOM
    → Computer Use 视觉操作
```

公开网页如果不依赖登录态或 JavaScript，直接走 `public-http`；需要当前标签页、登录状态、动态渲染或视觉判断时才升级。Skill 不能绕过 Codex 或操作系统的授权提示，但可以避免不必要地升级到最高权限。

## Figma 前提

```powershell
$env:FIGMA_ACCESS_TOKEN = "<user-provided-token>"
smart-context "https://www.figma.com/design/<file-key>/<slug>?node-id=10-20" --source figma_node --pretty
# 下载节点渲染资源必须显式确认
smart-context "https://www.figma.com/design/<file-key>/<slug>?node-id=10-20" --source figma_node --download-dir .\artifacts --confirm-download --pretty
```

Token 不写入项目文件，也不会从浏览器登录态中提取。若已配置官方 Figma MCP，可让 Skill 将 MCP 适配器注册为同一来源的主提供方。

## Codex Skill / Plugin

- 开发 Skill：`skills/smart-context-capture/SKILL.md`
- 兼容旧目录的 Skill 草稿：`skill/smart-context-capture/SKILL.md`
- Plugin manifest：`.codex-plugin/plugin.json`
- Python 核心：`src/smart_context/`

项目现阶段适合本地安装和测试；正式发布时可把 GitHub 源码作为开发分发，再按 Codex Plugin 提交流程提交审核。第三方扩展、MCP、Chrome 登录态和 Figma token 都必须由最终用户单独配置。

发布准备材料位于 `submission/`：包括 listing 文案、隐私/条款草稿、5 个正向和 3 个负向测试用例，以及 0.3.1 release notes。公开提交仍需要真实的开发者身份、公开 HTTPS 网站/支持/隐私/条款 URL、公开仓库和生产级品牌素材；这些不能用占位信息代替。

正式上传包：`dist/smart-context-capture-0.3.1-release.zip`；校验值见同目录 `.sha256` 文件。发布包已通过 Plugin validator，并排除了测试缓存、`.env`、`pyc` 和本机 egg-info。
