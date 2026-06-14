# Agnes AI API Reference

Base host: `https://apihub.agnes-ai.com`

Authentication: `Authorization: Bearer YOUR_API_KEY`

Content type: `application/json`

## Text

Endpoint: `POST /v1/chat/completions`

Model: `agnes-2.0-flash`

Required:

- `model`: fixed as `agnes-2.0-flash`
- `messages`: OpenAI-compatible chat messages

Optional:

- `temperature`: number
- `top_p`: number
- `max_tokens`: number
- `stream`: boolean
- `tools`: array
- `tool_choice`: string or object

Response is OpenAI-compatible and includes `choices[].message.content` and `usage`.

## Image

Endpoint: `POST /v1/images/generations`

Model: `agnes-image-2.1-flash`

Required:

- `model`: fixed as `agnes-image-2.1-flash`
- `prompt`: text instruction for image generation or editing

Optional:

- `size`: output size such as `1024x768`
- `extra_body.image`: array of input image URLs for image-to-image
- `extra_body.response_format`: use `url` for image URLs

Prompt structure:

`[Subject] + [Scene / Environment] + [Style] + [Lighting] + [Composition] + [Quality Requirements]`

For image-to-image, state what should change and what must remain unchanged.

For non-English user prompts, translate to English before sending the request. Preserve visual specifics and constraints.

## Video

Create task endpoint: `POST /v1/videos`

Retrieve video result (**recommended**): `GET /agnesapi?video_id=<VIDEO_ID>[&model_name=agnes-video-v2.0]`

Retrieve task (legacy, kept for compatibility): `GET /v1/videos/{task_id}`

Model: `agnes-video-v2.0`

The video API is asynchronous. Create a task first, then poll or retrieve using the returned `video_id` with `/agnesapi` to avoid long queuing. The create response also returns `task_id` / `id`, which can still be used with `/v1/videos/{task_id}` but is more likely to queue for longer than 5 minutes (if a task takes longer than ~5 minutes, the caller is probably using the task_id endpoint by mistake).

Polling interval recommendation: 5 seconds.

Use English prompts for video generation whenever possible. If the user prompt is not English, translate it to English first, preserving subject, action, scene, camera movement, lighting, style, and constraints.

Required:

- `model`: fixed as `agnes-video-v2.0`
- `prompt`: text description of the video

Optional:

- `image`: input image URL or image URL array for image-to-video
- `mode`: generation mode such as `ti2vid` or `keyframes`
- `height`: integer, default `768`
- `width`: integer, default `1152`
- `num_frames`: integer, must be `<= 441` and satisfy `8n + 1`
- `num_inference_steps`: integer
- `seed`: integer
- `frame_rate`: number, supported range `1-60`
- `negative_prompt`: string
- `extra_body.image`: array for multi-image video or keyframe mode
- `extra_body.mode`: set to `keyframes` for keyframe animation

Create-task response fields:

- `id` / `task_id`: legacy task id
- `video_id`: recommended id for `/agnesapi`
- `object`, `model`, `status`, `progress`, `created_at`, `seconds`, `size`

Common status values:

- `queued`
- `in_progress`
- `completed`
- `failed`

The completed response usually includes a video URL. In live responses this may appear as `video_url`, `url`, or `remixed_from_video_id`, plus `size`, `seconds`, and `usage.duration_seconds`.

Recommended video defaults:

- Standard: `width=1152`, `height=768`, `num_frames=121`, `frame_rate=24`
- Short smoke test: `num_frames=81`, `frame_rate=24`
- Reproducibility: set `seed`

Query usage reminder:

- Prefer `GET /agnesapi?video_id=<VIDEO_ID>&model_name=agnes-video-v2.0` for new work.
- `GET /v1/videos/{task_id}` remains available for backward compatibility, but queuing can be much slower.
- If a task queues longer than ~5 minutes, double-check that the caller is using `video_id` with `/agnesapi`.

## Error Codes

- `400`: invalid request
- `401`: unauthorized; check API key
- `404`: task not found
- `500`: server error
- `503`: service busy; retry later
