# Agnes AI Generation Skill

[English](README_EN.md)

用于 Agent Skills 的 Agnes AI 生成技能，封装 Agnes 官方文本、图片、视频 API。它采用标准 `SKILL.md` 结构，可安装到 Codex、Claude Code、OpenClaw、Cursor、Windsurf 等支持 Agent Skills 的客户端。安装后，你可以让 AI 直接调用 Agnes 模型完成文生图、图生图、文生视频、图生视频、多图视频、关键帧动画等操作。

官网与 API 平台：[https://platform.agnes-ai.com/](https://platform.agnes-ai.com/)

## 功能

- 文本生成：`agnes-2.0-flash`
- 流式文本响应
- OpenAI 兼容的工具调用请求结构
- 文生图：`agnes-image-2.1-flash`
- 图生图 / 图片编辑：`agnes-image-2.1-flash`
- 高信息密度图片生成
- 文本转视频：`agnes-video-v2.0`
- 图像转视频：`agnes-video-v2.0`
- 多图像视频生成
- 关键帧动画
- 基于提示词的运动与场景控制
- 电影感视觉输出
- 异步视频任务创建
- 轮询式视频结果检索
- 基于 seed 的可重复生成
- 自动将非英文图片/视频提示词翻译为英文提示词，提高 Agnes 视频生成稳定性

## 快速开始

### 1. 申请 Agnes API Key

1. 打开 Agnes API 平台：[https://platform.agnes-ai.com/](https://platform.agnes-ai.com/)
2. 注册或登录账号。
3. 在平台中申请 / 创建 API Key。
4. 拿到 API Key 后，可以在可信任的当前 AI 会话里发送给 AI，或配置为本机环境变量。

安全提醒：不要把 API Key 写入 Git 仓库、README、截图或公开聊天记录。

### 2. 安装本 Skill

安装到当前 Agent：

```powershell
npx skills add Yacey/agnes-ai-generation-skill
```

安装到所有支持的 Agent：

```powershell
npx skills add Yacey/agnes-ai-generation-skill --all
```

安装后，当你要求已安装的 AI Agent 使用 Agnes 生成图片或视频时，AI 会自动触发本 skill。

### 3. 配置 API Key

临时配置当前 PowerShell 会话：

```powershell
$env:AGNES_API_KEY="YOUR_API_KEY"
```

Windows 用户级持久配置：

```powershell
[Environment]::SetEnvironmentVariable("AGNES_API_KEY", "YOUR_API_KEY", "User")
```

脚本也会识别以下变量名：

- `AGNES_API_KEY`
- `AGNES_API_TOKEN`
- `APIHUB_AGNES_API_KEY`

### 4. 开始使用

你可以直接对 AI 说：

```text
使用 Agnes 帮我生成一张高信息密度的未来城市图片。
```

或：

```text
使用 Agnes 把这张图片生成一段电影感视频。
```

如果你已经把 API Key 发送给当前 AI，AI 可以配置环境变量并调用本 skill。之后即可解锁生图、生视频等相关操作。

## 命令示例

文本生成：

```powershell
python scripts/agnes_api.py text --prompt "Write a concise product tagline for an AI assistant."
```

文生图：

```powershell
python scripts/agnes_api.py image --prompt "A luminous floating city above a misty canyon at sunrise, cinematic realism" --size 1024x768
```

中文提示词文生图，脚本会先自动翻译成英文：

```powershell
python scripts/agnes_api.py image --prompt "一座高信息密度的未来城市集市，拥挤人群，飞行汽车，全息招牌，电影感写实风格"
```

图生图：

```powershell
python scripts/agnes_api.py image --prompt "Turn the scene into a rainy cyberpunk night while preserving composition" --image https://example.com/input.png
```

文生视频：

```powershell
python scripts/agnes_api.py video --prompt "A cinematic shot of a cat walking on the beach at sunset" --poll
```

视频命令默认使用 `--num-frames 121 --frame-rate 24 --interval 5`，以减少缺少关键视频参数导致的不稳定，并按官方推荐的 5 秒间隔轮询。脚本会在请求前检查 `num_frames` 是否满足 `8n + 1` 且不超过 `441`，并检查帧率、尺寸等基础参数。创建视频任务后会同时返回 `video_id`（推荐）与 `task_id`（兼容），优先使用 `video_id` 走 `/agnesapi` 端点可明显降低排队时间。

图生视频：

```powershell
python scripts/agnes_api.py video --prompt "Animate subtle camera movement and natural lighting" --image https://example.com/image.png --poll
```

多图 / 关键帧视频：

```powershell
python scripts/agnes_api.py video --prompt "Create a smooth cinematic transition between the two keyframes" --image https://example.com/a.png --image https://example.com/b.png --mode keyframes --poll
```

查询视频结果（推荐：使用创建任务返回的 `video_id`，走 `/agnesapi` 以缩短排队时间）：

```powershell
python scripts/agnes_api.py video-get --video-id video_xxxxxx
```

使用旧的 `task_id` 查询仍可用，作为兼容方式（排队可能较慢）：

```powershell
python scripts/agnes_api.py video-get task_123456
```

默认输出会整理出常用字段，例如 `content`、`urls`、`translated_prompt`、`next_steps`，同时保留 `raw` 原始响应，方便 AI 和人工继续处理。

流式文本也会聚合输出 `content`，同时保留事件数量、是否完成和原始响应前缀，便于快速判断流式接口是否正常。

视频完成后，脚本会从 `video_url`、`url` 或 Agnes 实测返回中的 `remixed_from_video_id` 提取可直接访问的 mp4 链接，并放入 `urls`。

若只想看 Agnes 原始响应，可以加：

```powershell
--raw
```

运行测试：

```powershell
python scripts/agnes_api.py smoke-test
```

默认测试覆盖文本、流式文本、工具调用请求结构和文生图，不会创建视频任务。工具调用请求有时会被 Agnes 接收但不返回 `tool_calls`，默认只输出 warning；如果你想把这种情况视为失败，可以使用：

```powershell
python scripts/agnes_api.py smoke-test --strict-tools
```

测试图生图：

```powershell
python scripts/agnes_api.py smoke-test --include-image-edit
```

单独测试某个视频能力，避免一次创建太多视频任务：

```powershell
python scripts/agnes_api.py smoke-test --video-case text-to-video
```

可选的视频测试项：

- `text-to-video`
- `image-to-video`
- `multi-image`
- `keyframes`

## 提示词语言策略

Agnes 视频生成使用英文提示词更稳定。因此本 skill 的脚本默认会检测图片/视频提示词中的非英文字符，并先调用 `agnes-2.0-flash` 翻译成英文生成提示词，再调用图片或视频 API。

翻译时会保留：

- 主体
- 场景
- 风格
- 光照
- 构图
- 镜头运动
- 动作描述
- 负面提示词或约束

如果你确实想跳过自动翻译，可以加：

```powershell
--no-translate-prompt
```

示例：

```powershell
python scripts/agnes_api.py video --prompt "中文提示词" --no-translate-prompt
```

## 测试状态

已通过真实 API 测试：

- 基础文本生成
- 流式文本
- 工具调用请求结构
- 文生图
- 图生图
- 高信息密度文生图
- 中文提示词自动翻译后文生图
- 中文提示词自动翻译后文生视频任务创建
- 文生视频完成并返回 mp4 URL
- 图生视频完成并返回 mp4 URL

已支持但本轮未完整端到端重测：

- 多图视频
- 关键帧视频

尚未完整端到端验证：

- 每一种多图视频 / 关键帧视频任务都成功返回最终视频 URL

说明：曾有一次真实文生视频任务在查询时返回 Agnes 服务端 `division by zero` 错误；后续短文生视频任务已成功完成并返回 mp4 URL。因此视频能力在 skill 中已支持，但仍建议逐个模式测试并保留 provider 错误信息。

## 仓库结构

```text
.
├── SKILL.md
├── README.md
├── README_EN.md
├── LICENSE
├── agents/
│   └── openai.yaml
├── references/
│   └── api.md
└── scripts/
    └── agnes_api.py
```

## 许可证

MIT License. See [LICENSE](LICENSE).
