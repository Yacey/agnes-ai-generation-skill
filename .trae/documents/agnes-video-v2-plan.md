# Agnes-Video-V2.0 skill 更新计划

## 研究结论

当前仓库通过 `scripts/agnes_api.py` 调用 Agnes AI 的文本/图片/视频 API，视频相关流程目前全部基于 `task_id`（即创建任务返回的 `id`）来轮询或查询。查询端点使用 `GET /v1/videos/{task_id}`。

根据新官方文档 `https://agnes-ai.com/doc/agnes-video-v20`，存在两个查询视频结果的方式：

- **推荐方式（新接入必须使用）**：`GET /agnesapi?video_id=<VIDEO_ID>`，支持可选 `model_name=agnes-video-v2.0` 查询参数。使用 `video_id` 查询可显著减少排队时间。
- **兼容方式**：`GET /v1/videos/{task_id}`，仍然可用但存在排队问题。

创建任务响应同时返回 `task_id` 和 `video_id`（新字段）。建议使用 `video_id`。

当前需要更新的点：

1. `scripts/agnes_api.py` 的 `poll_video`、`cmd_video`、`cmd_video_get`、`create_video_case` 都以 `task_id`（即 `created["id"]`）查询。需要改为优先使用 `video_id`，走 `/agnesapi?video_id=...` 端点；当 `video_id` 缺失时回退到旧的 `/v1/videos/{task_id}` 以保持兼容。
2. `references/api.md` 需要补充推荐的视频查询端点及 `video_id` 使用说明，同时明确 `/v1/videos/{task_id}` 仅作兼容。
3. `SKILL.md` 的 Workflow 章节需要把"按 task_id 查询"改为"按 video_id 查询"，并强调 `/agnesapi` 端点是默认路径，5 秒轮询间隔，排队超过 5 分钟大概率是用错了接口。

## 变更文件

1. `scripts/agnes_api.py`
   - 提取新的推荐查询逻辑：优先使用 `video_id`，调用路径 `/agnesapi?video_id=...&model_name=agnes-video-v2.0`。
   - `poll_video` 增加 `video_id` 参数；内部优先走 `/agnesapi`，缺失 `video_id` 时回退旧端点。
   - `cmd_video` 创建任务后同时记录 `video_id` 与 `task_id`；轮询默认使用 `video_id`。
   - `cmd_video_get` 的位置参数仍可传入 `task_id`，但优先探测是否为 `video_` 前缀；新增 `--video-id` 显式参数，并在文档中明确推荐传入 `video_id`。
   - `create_video_case` 使用 `video_id` 走新端点做轮询/检索。
   - 输出的 `next_steps` 使用 `video_id` 示例：`python scripts/agnes_api.py video-get --video-id video_xxxxxx`。
   - 轮询默认间隔由 10 秒调整为 5 秒（与文档推荐一致）。
   - 新增内部辅助：`pick_video_id(created)` 与兼容回退逻辑，保证旧的 `task_id` 输入仍然可以工作。

2. `references/api.md`
   - 在"Video"章节补充：
     - 推荐查询端点：`GET /agnesapi?video_id=<VIDEO_ID>[&model_name=agnes-video-v2.0]`
     - 创建任务响应新增字段 `video_id`，默认用 `video_id` 调用 `/agnesapi` 查询；
     - 保留 `GET /v1/videos/{task_id}` 仅作为兼容方式；
     - 提示：排队超过 5 分钟大概率是误用了旧接口，请改用 `video_id` + `/agnesapi`。

3. `SKILL.md`
   - Workflow 章节把"retrieve by task id"改为"retrieve by video id via `/agnesapi`"。
   - 示例命令在 video 相关段落显式展示 `video_id` 的使用与 `/agnesapi` 端点说明。
   - 明确：当 `video_id` 缺失或用户只提供了 `task_id` 时才回退旧端点，新生成的任务默认走 `video_id`。

## 依赖与注意事项

- 不需要引入新的 Python 依赖，仍使用标准库 `urllib` + `argparse` + `json`。
- 向后兼容：`video-get <task_id>` 仍然可用（内部会走旧端点）；新增 `--video-id` 更推荐。脚本在创建任务后优先使用 `video_id`。
- 错误处理：新端点在 404 或 API 返回 `error` 时仍然以清晰文本退出，避免把 API key 暴露到日志。
- 不要在输出或注释以外的地方泄露 API key；脚本中相关处理保持不变。

## 风险与处理

- **风险 1**：新端点 `/agnesapi` 的响应字段可能与旧 `/v1/videos/{task_id}` 不完全一致，导致 URL 解析失败。
  - 处理：保持 `extract_video_urls` 中的多字段兜底（`video_url`、`url`、`remixed_from_video_id`），并在返回非 JSON 时走回旧端点重试一次。
- **风险 2**：`video_id` 在历史任务响应中可能缺失（旧任务）。
  - 处理：`poll_video` 显式支持 `video_id is None` → 回退旧 `/v1/videos/{task_id}`；打印一条 stderr 警告提示"falling back to task_id endpoint, queuing may be slower"。
- **风险 3**：改动对外命令行接口（`video-get` 新增参数）。
  - 处理：新增参数为可选；位置参数 `<task_id>` 行为保持不变，仅新增 `--video-id` 作为推荐路径。

## 验证步骤

1. 语法检查：`python -c "import ast; ast.parse(open('scripts/agnes_api.py').read())"` 通过。
2. 启动脚本的 `--help` 输出正常，确认 `video-get --video-id` 可用。
3. 离线模拟：构造一个含 `video_id` 的创建响应，确认 `poll_video` 走 `/agnesapi` 分支；构造一个不含 `video_id` 的响应，确认走 `/v1/videos/{task_id}` 并输出警告。
4. 如在具备真实 API key 的环境中，可选跑一次：
   - `python scripts/agnes_api.py video --prompt "..." --poll`，确认日志中出现 `video_xxxxxx` 与 `/agnesapi` 端点。
   - `python scripts/agnes_api.py video-get --video-id video_xxxxxx` 成功返回结果。
