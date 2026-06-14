# Agnes AI Generation Skill

[中文](README.md)

Agnes AI Generation Skill is a standard Agent Skills package for calling Agnes AI text, image, and video generation APIs. It can be installed into Codex, Claude Code, OpenClaw, Cursor, Windsurf, and other clients that support Agent Skills. After installation, AI agents can use Agnes models for text generation, text-to-image, image-to-image, text-to-video, image-to-video, multi-image video, and keyframe animation workflows.

Official platform: [https://platform.agnes-ai.com/](https://platform.agnes-ai.com/)

## Features

- Text generation with `agnes-2.0-flash`
- Streaming text responses
- OpenAI-compatible tool-calling request shape
- Text-to-image with `agnes-image-2.1-flash`
- Image-to-image editing with `agnes-image-2.1-flash`
- High-information-density image generation
- Text-to-video with `agnes-video-v2.0`
- Image-to-video with `agnes-video-v2.0`
- Multi-image video generation
- Keyframe animation
- Prompt-based motion and scene control
- Cinematic video output
- Asynchronous video task creation
- Polling-based video result retrieval
- Seed-based reproducibility
- Automatic English prompt translation for non-English image/video prompts

## Quick Start

### 1. Apply for an Agnes API Key

1. Open [https://platform.agnes-ai.com/](https://platform.agnes-ai.com/).
2. Register or sign in.
3. Create an API key from the platform.
4. Provide the API key to the AI in a trusted current session, or configure it as a local environment variable.

Do not commit API keys to Git, README files, screenshots, or public chat logs.

### 2. Install This Skill

Install into the current agent:

```powershell
npx skills add Yacey/agnes-ai-generation-skill
```

Install into all supported agents:

```powershell
npx skills add Yacey/agnes-ai-generation-skill --all
```

### 3. Configure the API Key

For the current PowerShell session:

```powershell
$env:AGNES_API_KEY="YOUR_API_KEY"
```

For persistent Windows user-level configuration:

```powershell
[Environment]::SetEnvironmentVariable("AGNES_API_KEY", "YOUR_API_KEY", "User")
```

The script also accepts:

- `AGNES_API_KEY`
- `AGNES_API_TOKEN`
- `APIHUB_AGNES_API_KEY`

### 4. Use the Skill

Ask your AI agent:

```text
Use Agnes to generate a high-information-density futuristic city image.
```

Or:

```text
Use Agnes to turn this image into a cinematic video.
```

## Usage Examples

Text:

```powershell
python scripts/agnes_api.py text --prompt "Write a concise product tagline for an AI assistant."
```

Text-to-image:

```powershell
python scripts/agnes_api.py image --prompt "A luminous floating city above a misty canyon at sunrise, cinematic realism" --size 1024x768
```

Image-to-image:

```powershell
python scripts/agnes_api.py image --prompt "Turn the scene into a rainy cyberpunk night while preserving composition" --image https://example.com/input.png
```

Text-to-video:

```powershell
python scripts/agnes_api.py video --prompt "A cinematic shot of a cat walking on the beach at sunset" --poll
```

Video commands default to `--num-frames 121 --frame-rate 24 --interval 5` to reduce instability from missing core video parameters and to match the officially recommended 5-second polling cadence. The script validates `num_frames` before sending requests: it must satisfy `8n + 1` and be no more than `441`. It also checks frame rate and dimensions. Creating a video task returns both a recommended `video_id` (for the `/agnesapi` endpoint with faster queuing) and a legacy `task_id`; the script prefers `video_id` when available and falls back to `task_id` otherwise.

Image-to-video:

```powershell
python scripts/agnes_api.py video --prompt "Animate subtle camera movement and natural lighting" --image https://example.com/image.png --poll
```

Multi-image / keyframe video:

```powershell
python scripts/agnes_api.py video --prompt "Create a smooth cinematic transition between the two keyframes" --image https://example.com/a.png --image https://example.com/b.png --mode keyframes --poll
```

Retrieve a video result (**recommended**): use the `video_id` returned by the create task, which routes through `/agnesapi` for faster queuing:

```powershell
python scripts/agnes_api.py video-get --video-id video_xxxxxx
```

Legacy retrieval with a task id (kept for compatibility; slower queuing):

```powershell
python scripts/agnes_api.py video-get task_123456
```

By default, command output is normalized with common fields such as `content`, `urls`, `translated_prompt`, and `next_steps`, while preserving the provider response under `raw`.

Streaming text output also includes aggregated `content`, event count, completion status, and a short raw prefix so the result is easier to inspect.

For completed video tasks, the script extracts direct mp4 URLs from `video_url`, `url`, or the live-response field `remixed_from_video_id`, then places them in `urls`.

Add `--raw` to print only the original Agnes response:

```powershell
--raw
```

Light smoke test. By default, this checks text, streaming text, tool-calling request shape, and text-to-image only. It does not create video tasks:

```powershell
python scripts/agnes_api.py smoke-test
```

The tool-calling request can be accepted by Agnes without returning `tool_calls` consistently. By default this is reported as a warning. Use strict mode to fail in that case:

```powershell
python scripts/agnes_api.py smoke-test --strict-tools
```

Image-to-image smoke test:

```powershell
python scripts/agnes_api.py smoke-test --include-image-edit
```

Single video case test:

```powershell
python scripts/agnes_api.py smoke-test --video-case text-to-video
```

## Prompt Language

English prompts are more stable for Agnes video generation. For image and video calls, this skill automatically translates non-English prompts to English before sending them to the Agnes image/video APIs. It preserves subjects, scene details, style, lighting, composition, camera movement, motion, and constraints.

To disable automatic translation:

```powershell
python scripts/agnes_api.py video --prompt "non-English prompt" --no-translate-prompt
```

## Validation Status

Confirmed by live API:

- Basic text
- Streaming text
- Tool-calling request shape
- Text-to-image
- Image-to-image
- High-information-density text-to-image
- Non-English prompt auto-translation for text-to-image
- Non-English prompt auto-translation for text-to-video task creation
- Completed text-to-video retrieval with a direct mp4 URL
- Completed image-to-video retrieval with a direct mp4 URL

Supported but not fully re-tested end-to-end in the latest pass:

- Multi-image video
- Keyframe video

Not fully confirmed end-to-end yet:

- Completed URL retrieval for every multi-image video and keyframe animation task

A previous live text-to-video retrieval returned a provider-side `division by zero` error; a later short text-to-video task completed successfully and returned an mp4 URL. Keep provider errors visible when retrying video modes.

## License

MIT License. See [LICENSE](LICENSE).
