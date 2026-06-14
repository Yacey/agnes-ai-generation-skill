#!/usr/bin/env python3
"""Small CLI for Agnes AI text, image, and video generation APIs."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


BASE_URL = "https://apihub.agnes-ai.com"
TEXT_MODEL = "agnes-2.0-flash"
IMAGE_MODEL = "agnes-image-2.1-flash"
VIDEO_MODEL = "agnes-video-v2.0"
SIZE_RE = re.compile(r"^[1-9]\d*x[1-9]\d*$")


def get_api_key() -> str:
    for name in ("AGNES_API_KEY", "AGNES_API_TOKEN", "APIHUB_AGNES_API_KEY"):
        value = os.environ.get(name)
        if value:
            return value
    raise SystemExit(
        "Missing API key. Set AGNES_API_KEY, AGNES_API_TOKEN, or APIHUB_AGNES_API_KEY."
    )


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {get_api_key()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} from {path}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Request failed for {path}: {exc}") from exc


def request_text(method: str, path: str, payload: dict[str, Any] | None = None) -> str:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + path,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {get_api_key()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} from {path}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Request failed for {path}: {exc}") from exc


def stream_summary(payload: dict[str, Any]) -> dict[str, Any]:
    raw = request_text("POST", "/v1/chat/completions", payload)
    event_count = 0
    done = False
    content_parts: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            done = True
        elif data:
            event_count += 1
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            try:
                delta = event["choices"][0].get("delta", {})
            except (KeyError, IndexError, TypeError, AttributeError):
                continue
            content = delta.get("content")
            if isinstance(content, str):
                content_parts.append(content)
    return {
        "type": "text-stream",
        "content": "".join(content_parts) or None,
        "events": event_count,
        "done": done,
        "raw_prefix": raw[:200],
    }


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def parse_json_arg(name: str, value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON for {name}: {exc.msg} at position {exc.pos}") from exc


def needs_english_translation(prompt: str) -> bool:
    return any(ord(ch) > 127 for ch in prompt)


def translate_prompt_to_english(prompt: str) -> str:
    payload = {
        "model": TEXT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Translate the user's image/video generation prompt into fluent English. "
                    "Preserve all concrete visual details, style words, camera motion, lighting, "
                    "composition constraints, and negative instructions. Return only the English prompt."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 800,
    }
    data = request_json("POST", "/v1/chat/completions", payload)
    try:
        translated = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise SystemExit(f"Prompt translation failed: {json.dumps(data, ensure_ascii=False)}") from exc
    if not translated:
        raise SystemExit("Prompt translation failed: empty translated prompt")
    return translated


def prepare_generation_prompt(prompt: str, translate: bool = True) -> tuple[str, str | None]:
    if translate and needs_english_translation(prompt):
        translated = translate_prompt_to_english(prompt)
        return translated, translated
    return prompt, None


def extract_text_content(data: dict[str, Any]) -> str | None:
    try:
        content = data["choices"][0]["message"].get("content")
    except (KeyError, IndexError, TypeError, AttributeError):
        return None
    return content if isinstance(content, str) else None


def output_result(
    result_type: str,
    raw: dict[str, Any],
    *,
    prompt_used: str | None = None,
    translated_prompt: str | None = None,
    urls: list[str] | None = None,
    status: str | None = None,
    next_steps: list[str] | None = None,
    raw_only: bool = False,
) -> None:
    if raw_only:
        print_json(raw)
        return
    summary: dict[str, Any] = {"type": result_type}
    if status:
        summary["status"] = status
    if urls:
        summary["urls"] = urls
    if prompt_used:
        summary["prompt_used"] = prompt_used
    if translated_prompt:
        summary["translated_prompt"] = translated_prompt
    if next_steps:
        summary["next_steps"] = next_steps
    summary["raw"] = raw
    print_json(summary)


def extract_image_urls(data: dict[str, Any]) -> list[str]:
    urls = []
    if isinstance(data.get("url"), str):
        urls.append(data["url"])
    if isinstance(data.get("image_url"), str):
        urls.append(data["image_url"])
    if isinstance(data.get("data"), list):
        for item in data["data"]:
            if isinstance(item, dict):
                for key in ("url", "image_url"):
                    if isinstance(item.get(key), str):
                        urls.append(item[key])
    return urls


def extract_video_urls(data: dict[str, Any]) -> list[str]:
    urls = []
    for key in ("video_url", "url", "remixed_from_video_id"):
        value = data.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            urls.append(value)
    if isinstance(data.get("data"), list):
        for item in data["data"]:
            if isinstance(item, dict):
                urls.extend(extract_video_urls(item))
    return list(dict.fromkeys(urls))


def validate_size(value: str | None, name: str = "size") -> None:
    if value and not SIZE_RE.match(value):
        raise SystemExit(f"Invalid {name}: {value}. Expected WIDTHxHEIGHT, for example 1024x768.")


def validate_video_args(args: argparse.Namespace) -> None:
    if args.num_frames is not None:
        if args.num_frames > 441 or (args.num_frames - 1) % 8 != 0:
            raise SystemExit("Invalid --num-frames: must be <= 441 and satisfy 8n + 1, for example 81 or 121.")
    if args.frame_rate is not None and not (1 <= args.frame_rate <= 60):
        raise SystemExit("Invalid --frame-rate: supported range is 1-60.")
    for name in ("height", "width"):
        value = getattr(args, name)
        if value is not None and value <= 0:
            raise SystemExit(f"Invalid --{name.replace('_', '-')}: must be a positive integer.")


def cmd_text(args: argparse.Namespace) -> None:
    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": args.prompt})
    payload: dict[str, Any] = {
        "model": TEXT_MODEL,
        "messages": messages,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
    }
    if args.top_p is not None:
        payload["top_p"] = args.top_p
    if args.stream:
        payload["stream"] = True
    if args.tools_json:
        payload["tools"] = parse_json_arg("--tools-json", args.tools_json)
    if args.tool_choice_json:
        payload["tool_choice"] = parse_json_arg("--tool-choice-json", args.tool_choice_json)
    if args.stream:
        print_json(stream_summary(payload))
    else:
        data = request_json("POST", "/v1/chat/completions", payload)
        content = extract_text_content(data)
        wrapped = {
            "type": "text",
            "content": content,
            "raw": data,
        }
        print_json(data if args.raw else wrapped)


def cmd_image(args: argparse.Namespace) -> None:
    validate_size(args.size)
    prompt, translated_prompt = prepare_generation_prompt(args.prompt, not args.no_translate_prompt)
    payload: dict[str, Any] = {
        "model": IMAGE_MODEL,
        "prompt": prompt,
    }
    if args.size:
        payload["size"] = args.size
    extra: dict[str, Any] = {"response_format": "url"}
    if args.image:
        extra["image"] = args.image
    if extra:
        payload["extra_body"] = extra
    data = request_json("POST", "/v1/images/generations", payload)
    urls = extract_image_urls(data)
    output_result(
        "image-to-image" if args.image else "text-to-image",
        data,
        prompt_used=prompt,
        translated_prompt=translated_prompt,
        urls=urls,
        raw_only=args.raw,
    )


def video_payload(args: argparse.Namespace) -> dict[str, Any]:
    validate_video_args(args)
    prompt, translated_prompt = prepare_generation_prompt(args.prompt, not args.no_translate_prompt)
    args._prompt_used = prompt
    args._translated_prompt = translated_prompt
    payload: dict[str, Any] = {
        "model": VIDEO_MODEL,
        "prompt": prompt,
    }
    for name in (
        "height",
        "width",
        "num_frames",
        "frame_rate",
        "num_inference_steps",
        "seed",
        "negative_prompt",
    ):
        value = getattr(args, name)
        if value is not None:
            payload[name] = value
    if args.mode:
        payload["mode"] = args.mode
    if args.image:
        if len(args.image) == 1 and args.mode != "keyframes":
            payload["image"] = args.image[0]
        else:
            payload["extra_body"] = {"image": args.image}
            if args.mode:
                payload["extra_body"]["mode"] = args.mode
    return payload


def pick_video_id(created: dict[str, Any]) -> tuple[str | None, str | None]:
    video_id = created.get("video_id")
    task_id = created.get("id") or created.get("task_id")
    if isinstance(video_id, str) and video_id:
        return video_id, str(task_id) if task_id else None
    return None, str(task_id) if task_id else None


def video_lookup_path(video_id: str | None, task_id: str | None) -> tuple[str, str]:
    if isinstance(video_id, str) and video_id:
        return (
            f"/agnesapi?video_id={urllib.parse.quote(video_id, safe='')}"
            f"&model_name={urllib.parse.quote(VIDEO_MODEL, safe='')}",
            "video_id",
        )
    if not task_id:
        raise SystemExit("Cannot retrieve video: neither video_id nor task_id available.")
    print(
        f"video {task_id}: no video_id available; falling back to /v1/videos/{{task_id}}. "
        "Queuing may be slower; prefer using video_id with /agnesapi for new tasks.",
        file=sys.stderr,
    )
    return f"/v1/videos/{urllib.parse.quote(task_id, safe='')}", "task_id"


def poll_video(
    task_id: str | None,
    timeout: int,
    interval: int,
    *,
    video_id: str | None = None,
) -> dict[str, Any]:
    path, key = video_lookup_path(video_id, task_id)
    display_id = video_id if video_id else task_id
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = request_json("GET", path)
        if last.get("error"):
            raise SystemExit(
                f"Video {key}={display_id} returned error: {json.dumps(last, ensure_ascii=False)}"
            )
        status = str(last.get("status", "")).lower()
        progress = last.get("progress")
        if status:
            print(
                f"video {key}={display_id} endpoint={path.split('?', 1)[0]} status={status} progress={progress}",
                file=sys.stderr,
            )
        if status in {"completed", "failed"}:
            return last
        time.sleep(interval)
    raise SystemExit(
        f"Timed out waiting for video {key}={display_id}. Last response: {json.dumps(last)}"
    )


def cmd_video(args: argparse.Namespace) -> None:
    created = request_json("POST", "/v1/videos", video_payload(args))
    new_video_id, new_task_id = pick_video_id(created)
    if not args.poll:
        next_steps: list[str] = []
        if new_video_id:
            next_steps.append(f"python scripts/agnes_api.py video-get --video-id {new_video_id}")
            next_steps.append(
                f"python scripts/agnes_api.py video-get --video-id {new_video_id}  "
                "# repeat until status is completed"
            )
        elif new_task_id:
            next_steps.append(f"python scripts/agnes_api.py video-get {new_task_id}")
            next_steps.append(f"python scripts/agnes_api.py video-get {new_task_id}  # repeat until status is completed")
        output_result(
            "video-task",
            created,
            prompt_used=getattr(args, "_prompt_used", None),
            translated_prompt=getattr(args, "_translated_prompt", None),
            status=str(created.get("status", "")) if created.get("status") is not None else None,
            next_steps=next_steps,
            raw_only=args.raw,
        )
        return
    if not new_video_id and not new_task_id:
        raise SystemExit(f"Video create response missing both video_id and task_id: {json.dumps(created)}")
    data = poll_video(new_task_id, args.timeout, args.interval, video_id=new_video_id)
    urls = extract_video_urls(data)
    output_result(
        "video-result",
        data,
        prompt_used=getattr(args, "_prompt_used", None),
        translated_prompt=getattr(args, "_translated_prompt", None),
        urls=urls,
        status=str(data.get("status", "")) if data.get("status") is not None else None,
        raw_only=args.raw,
    )


def cmd_video_get(args: argparse.Namespace) -> None:
    video_id = args.video_id
    positional = getattr(args, "task_id", None)
    task_id: str | None = None
    if not video_id and positional:
        if isinstance(positional, str) and positional.startswith("video_"):
            video_id = positional
        else:
            task_id = positional
    path, key = video_lookup_path(video_id, task_id)
    display_id = video_id if video_id else task_id
    data = request_json("GET", path)
    urls = extract_video_urls(data)
    next_steps: list[str] = []
    if not urls:
        if video_id:
            next_steps.append(f"python scripts/agnes_api.py video-get --video-id {video_id}")
        elif task_id:
            next_steps.append(f"python scripts/agnes_api.py video-get {task_id}")
    output_result(
        "video-result",
        data,
        urls=urls,
        status=str(data.get("status", "")) if data.get("status") is not None else None,
        next_steps=next_steps,
        raw_only=args.raw,
    )
    if data.get("error"):
        raise SystemExit(f"Video {key}={display_id} returned error: {json.dumps(data, ensure_ascii=False)}")


def require_ok(name: str, data: dict[str, Any], keys: tuple[str, ...]) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise SystemExit(f"{name} response missing {missing}: {json.dumps(data)}")
    print(f"{name}: ok")


def require_video_ok(name: str, data: dict[str, Any], completed: bool = False) -> None:
    require_ok(name, data, ("id", "status"))
    if data.get("error"):
        raise SystemExit(f"{name} returned error: {json.dumps(data, ensure_ascii=False)}")
    status = str(data.get("status", "")).lower()
    if status == "failed":
        raise SystemExit(f"{name} failed: {json.dumps(data, ensure_ascii=False)}")
    if completed and status != "completed":
        raise SystemExit(f"{name} did not complete: {json.dumps(data, ensure_ascii=False)}")
    if completed and not extract_video_urls(data):
        raise SystemExit(f"{name} completed without a video URL: {json.dumps(data, ensure_ascii=False)}")


def check_tool_call(name: str, data: dict[str, Any], strict: bool = False) -> None:
    try:
        tool_calls = data["choices"][0]["message"].get("tool_calls")
    except (KeyError, IndexError, TypeError, AttributeError):
        tool_calls = None
    if not tool_calls:
        message = f"{name}: request accepted, but response did not include tool_calls"
        if strict:
            raise SystemExit(f"{message}: {json.dumps(data, ensure_ascii=False)}")
        print(message, file=sys.stderr)
        return
    print(f"{name}: ok")


def extract_image_url(data: dict[str, Any]) -> str:
    candidates = extract_image_urls(data)
    if not candidates:
        raise SystemExit(f"Could not find image URL in response: {json.dumps(data, ensure_ascii=False)}")
    return candidates[0]


def create_video_case(name: str, payload: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    created = request_json("POST", "/v1/videos", payload)
    require_video_ok(f"{name}-create", created)
    video_id, task_id = pick_video_id(created)
    if args.poll_video:
        retrieved = poll_video(task_id, args.video_timeout, args.video_interval, video_id=video_id)
    else:
        lookup_path, _ = video_lookup_path(video_id, task_id)
        retrieved = request_json("GET", lookup_path)
    require_video_ok(f"{name}-get", retrieved, completed=args.poll_video)
    return {"create": created, "get": retrieved}


VIDEO_CASES = ("text-to-video", "image-to-video", "multi-image", "keyframes")


def cmd_smoke_test(args: argparse.Namespace) -> None:
    validate_size(args.image_size, "image-size")
    validate_video_args(
        argparse.Namespace(
            num_frames=args.video_num_frames,
            frame_rate=args.video_frame_rate,
            height=args.video_height,
            width=args.video_width,
        )
    )
    text = request_json(
        "POST",
        "/v1/chat/completions",
        {
            "model": TEXT_MODEL,
            "messages": [{"role": "user", "content": "Reply with exactly: Agnes text ok"}],
            "max_tokens": 20,
            "temperature": 0,
        },
    )
    require_ok("text", text, ("choices",))

    text_stream = stream_summary(
        {
            "model": TEXT_MODEL,
            "messages": [{"role": "user", "content": "Reply with exactly: Agnes stream ok"}],
            "max_tokens": 20,
            "temperature": 0,
            "stream": True,
        }
    )
    if text_stream["events"] < 1 and not text_stream["done"]:
        raise SystemExit(f"text-stream response did not look like SSE: {json.dumps(text_stream)}")
    print("text-stream: ok")

    text_tools = request_json(
        "POST",
        "/v1/chat/completions",
        {
            "model": TEXT_MODEL,
            "messages": [{"role": "user", "content": "Use the get_test_value tool."}],
            "max_tokens": 128,
            "temperature": 0,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_test_value",
                        "description": "Return a deterministic smoke test value.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "description": "test label"}
                            },
                            "required": ["label"],
                        },
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "get_test_value"}},
        },
    )
    check_tool_call("text-tools", text_tools, strict=args.strict_tools)

    image_text = request_json(
        "POST",
        "/v1/images/generations",
        {
            "model": IMAGE_MODEL,
            "prompt": "A simple red square icon centered on a white background",
            "size": args.image_size,
            "extra_body": {"response_format": "url"},
        },
    )
    require_ok("image-text-to-image", image_text, ("data",))
    generated_image_url = extract_image_url(image_text)

    image_edit = None
    edited_image_url = None
    selected_cases = set(args.video_case or [])
    needs_second_image = bool(selected_cases.intersection({"multi-image", "keyframes"}))
    if args.include_image_edit or needs_second_image:
        image_edit = request_json(
            "POST",
            "/v1/images/generations",
            {
                "model": IMAGE_MODEL,
                "prompt": "Turn this into a clean blue square icon while preserving the centered composition",
                "size": args.image_size,
                "extra_body": {"image": [generated_image_url], "response_format": "url"},
            },
        )
        require_ok("image-to-image", image_edit, ("data",))
        edited_image_url = extract_image_url(image_edit)

    video_common = {
        "model": VIDEO_MODEL,
    }
    for key, value in (
        ("height", args.video_height),
        ("width", args.video_width),
        ("num_frames", args.video_num_frames),
        ("frame_rate", args.video_frame_rate),
    ):
        if value is not None:
            video_common[key] = value
    video_results = {}
    if "text-to-video" in selected_cases:
        video_results["text_to_video"] = create_video_case(
            "video-text-to-video",
            {
                **video_common,
                "prompt": "A simple cinematic shot of a red square gently moving on a white background",
            },
            args,
        )
    if "image-to-video" in selected_cases:
        video_results["image_to_video"] = create_video_case(
            "video-image-to-video",
            {
                **video_common,
                "prompt": "Animate the icon with subtle floating motion, stable centered composition",
                "image": generated_image_url,
            },
            args,
        )
    if "multi-image" in selected_cases:
        if not edited_image_url:
            raise SystemExit("multi-image test requires an edited image URL")
        video_results["multi_image"] = create_video_case(
            "video-multi-image",
            {
                **video_common,
                "prompt": "Create a smooth transformation from the first icon to the second icon, stable centered composition",
                "extra_body": {"image": [generated_image_url, edited_image_url]},
            },
            args,
        )
    if "keyframes" in selected_cases:
        if not edited_image_url:
            raise SystemExit("keyframes test requires an edited image URL")
        video_results["keyframes"] = create_video_case(
            "video-keyframes",
            {
                **video_common,
                "prompt": "Create a smooth keyframe transition between the two icons, stable centered composition",
                "extra_body": {"image": [generated_image_url, edited_image_url], "mode": "keyframes"},
            },
            args,
        )
    print_json(
        {
            "text": text,
            "text_stream": text_stream,
            "text_tools": text_tools,
            "image_text_to_image": image_text,
            "image_to_image": image_edit,
            "video": video_results,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Call Agnes AI generation APIs.")
    sub = parser.add_subparsers(dest="command", required=True)

    text = sub.add_parser("text", help="Create a chat completion.")
    text.add_argument("--prompt", required=True)
    text.add_argument("--system")
    text.add_argument("--temperature", type=float, default=0.7)
    text.add_argument("--top-p", type=float)
    text.add_argument("--max-tokens", type=int, default=1024)
    text.add_argument("--stream", action="store_true")
    text.add_argument("--tools-json", help="JSON array for OpenAI-compatible tool definitions.")
    text.add_argument("--tool-choice-json", help="JSON object/string for OpenAI-compatible tool_choice.")
    text.add_argument("--raw", action="store_true", help="Print the raw provider response.")
    text.set_defaults(func=cmd_text)

    image = sub.add_parser("image", help="Generate or edit an image.")
    image.add_argument("--prompt", required=True)
    image.add_argument("--size", default="1024x768")
    image.add_argument("--image", action="append", help="Input image URL. Repeat for multiple images.")
    image.add_argument(
        "--no-translate-prompt",
        action="store_true",
        help="Do not translate non-English prompts before sending to the image API.",
    )
    image.add_argument("--raw", action="store_true", help="Print the raw provider response.")
    image.set_defaults(func=cmd_image)

    video = sub.add_parser("video", help="Create a video task.")
    video.add_argument("--prompt", required=True)
    video.add_argument("--image", action="append", help="Input image URL. Repeat for multi-image or keyframes.")
    video.add_argument("--mode", choices=("ti2vid", "keyframes"))
    video.add_argument("--height", type=int)
    video.add_argument("--width", type=int)
    video.add_argument("--num-frames", type=int, default=121)
    video.add_argument("--frame-rate", type=float, default=24)
    video.add_argument("--num-inference-steps", type=int)
    video.add_argument("--seed", type=int)
    video.add_argument("--negative-prompt")
    video.add_argument(
        "--no-translate-prompt",
        action="store_true",
        help="Do not translate non-English prompts before sending to the video API.",
    )
    video.add_argument("--poll", action="store_true")
    video.add_argument("--timeout", type=int, default=900)
    video.add_argument("--interval", type=int, default=5)
    video.add_argument("--raw", action="store_true", help="Print the raw provider response.")
    video.set_defaults(func=cmd_video)

    video_get = sub.add_parser("video-get", help="Retrieve a video task.")
    video_get.add_argument("task_id", nargs="?", default=None, help="task_id for legacy lookup. Omit if --video-id is used.")
    video_get.add_argument(
        "--video-id",
        help="Recommended: video_id returned from POST /v1/videos. Uses /agnesapi for faster queuing.",
    )
    video_get.add_argument("--raw", action="store_true", help="Print the raw provider response.")
    video_get.set_defaults(func=cmd_video_get)

    smoke = sub.add_parser("smoke-test", help="Run live text, image, and video API tests.")
    smoke.add_argument("--image-size", default="1024x768")
    smoke.add_argument("--video-height", type=int)
    smoke.add_argument("--video-width", type=int)
    smoke.add_argument("--video-num-frames", type=int, default=81)
    smoke.add_argument("--video-frame-rate", type=float, default=24)
    smoke.add_argument("--include-image-edit", action="store_true", help="Also test image-to-image editing.")
    smoke.add_argument("--strict-tools", action="store_true", help="Fail if the tool-calling response has no tool_calls.")
    smoke.add_argument("--poll-video", action="store_true")
    smoke.add_argument("--video-timeout", type=int, default=900)
    smoke.add_argument("--video-interval", type=int, default=5)
    smoke.add_argument(
        "--video-case",
        action="append",
        choices=VIDEO_CASES,
        help="Video case to test. Repeat to test multiple cases. Omit to skip video creation.",
    )
    smoke.set_defaults(func=cmd_smoke_test)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
