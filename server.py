#!/usr/bin/env python3
from __future__ import annotations
import asyncio
import base64
import hashlib
import os
import re
import json
import httpx
import dashscope
from dashscope.aigc.image_generation import ImageGeneration as DSImageGen
from dashscope.api_entities.dashscope_response import Message as DSMessage
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, File, Request, HTTPException, UploadFile
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from typing import Any
from urllib.parse import quote
try:
    from supabase import create_client, Client
except ImportError:  # Supabase is optional when DATABASE_URL is used.
    create_client = None
    Client = Any
from exporter import save_full_script, extract_episode_outlines
from prompts import (
    CHAT_SYSTEM,
    OUTLINE_SYSTEM, OUTLINE_PROMPT,
    OUTLINE_PLANS_SYSTEM, OUTLINE_PLANS_PROMPT, OUTLINE_PLANS_FROM_CHAT_PROMPT,
    REFINE_OUTLINE_SYSTEM, APPLY_OUTLINE_REFINE_SYSTEM, APPLY_OUTLINE_REFINE_PROMPT,
    WORLDBUILDING_SYSTEM, WORLDBUILDING_PROMPT,
    REFINE_WB_SYSTEM, APPLY_WB_REFINE_SYSTEM, APPLY_WB_REFINE_PROMPT,
    EPISODE_SYSTEM, EPISODE_PROMPT,
    REFINE_PROMPT,
    CHARACTER_EXTRACT_SYSTEM, CHARACTER_EXTRACT_PROMPT,
    REFINE_CHAR_BG_SYSTEM, APPLY_CHAR_BG_SYSTEM, APPLY_CHAR_BG_PROMPT,
    EPISODE_PLAN_SYSTEM, EPISODE_PLAN_PROMPT, SINGLE_EPISODE_PLAN_PROMPT,
    REFINE_EP_SYSTEM, APPLY_EP_SYSTEM, APPLY_EP_PROMPT,
    REFINE_SCRIPT_SYSTEM, APPLY_SCRIPT_SYSTEM, APPLY_SCRIPT_PROMPT,
    EPISODE_SUMMARY_PROMPT,
    OUTLINE_FROM_WB_SYSTEM, OUTLINE_FROM_WB_PROMPT,
)

load_dotenv()

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_BASE_URL"],
)
MODEL      = os.environ["OPENAI_MODEL_ID"]
EXPORT_DIR = "./scripts"

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY") or os.environ["OPENAI_API_KEY"]
dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

IMAGE_API_KEY  = os.environ.get("IMAGE_API_KEY") or os.environ["OPENAI_API_KEY"]
IMAGE_BASE_URL = os.environ.get("IMAGE_BASE_URL", "https://api.openai.com/v1")
image_client   = OpenAI(api_key=IMAGE_API_KEY, base_url=IMAGE_BASE_URL)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)
ATTACHMENT_STORAGE = os.environ.get("ATTACHMENT_STORAGE", "local").strip().lower()
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "character-images")
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "uploads"))
UPLOAD_URL_PREFIX = os.environ.get("UPLOAD_URL_PREFIX", "/uploads").rstrip("/") or "/uploads"


def openai_image_bytes(model: str, prompt: str, size: str = "1024x1536") -> bytes:
    """调用 gpt-image 系列生成图片，返回图片字节。兼容返回 b64_json 或 url 两种代理。"""
    res = image_client.images.generate(
        model=model,
        prompt=prompt,
        size=size,
        quality="high",
    )
    item = res.data[0]
    b64 = getattr(item, "b64_json", None)
    if b64:
        return base64.b64decode(b64)
    url = getattr(item, "url", None)
    if url:
        return httpx.get(url, timeout=60).content
    raise RuntimeError("图片生成失败：未返回图像数据")

PROJECT_COLUMNS = [
    "id", "title", "phase", "requirements", "worldbuilding", "outline",
    "episode_count", "episodes_done", "messages", "episodes", "characters",
    "episode_plans", "book_title", "cover_prompt", "cover_image_url",
    "created", "updated",
]
PROJECT_JSON_COLUMNS = {"messages", "episodes", "characters", "episode_plans"}


def _pg_connect():
    import psycopg
    from psycopg.rows import dict_row
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def _pg_json_value(key: str, value):
    if key not in PROJECT_JSON_COLUMNS:
        return value
    from psycopg.types.json import Jsonb
    if value is None:
        value = [] if key in {"messages", "characters"} else {}
    return Jsonb(value)


def _ensure_pg_schema():
    with _pg_connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id text PRIMARY KEY,
            title text NOT NULL DEFAULT '未命名',
            phase text NOT NULL DEFAULT 'chat',
            requirements text NOT NULL DEFAULT '',
            worldbuilding text NOT NULL DEFAULT '',
            outline text NOT NULL DEFAULT '',
            episode_count integer NOT NULL DEFAULT 15,
            episodes_done integer NOT NULL DEFAULT 0,
            messages jsonb NOT NULL DEFAULT '[]'::jsonb,
            episodes jsonb NOT NULL DEFAULT '{}'::jsonb,
            characters jsonb NOT NULL DEFAULT '[]'::jsonb,
            episode_plans jsonb NOT NULL DEFAULT '{}'::jsonb,
            book_title text NOT NULL DEFAULT '',
            cover_prompt text NOT NULL DEFAULT '',
            cover_image_url text NOT NULL DEFAULT '',
            created text NOT NULL DEFAULT '',
            updated text NOT NULL DEFAULT ''
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects (updated DESC)")


def _parse_project_columns(columns: str = "*") -> list[str]:
    if not columns or columns == "*":
        return PROJECT_COLUMNS
    parsed = [c.strip() for c in columns.split(",") if c.strip()]
    unknown = [c for c in parsed if c not in PROJECT_COLUMNS]
    if unknown:
        raise RuntimeError(f"未知项目字段: {', '.join(unknown)}")
    return parsed


db: Any = None
if USE_POSTGRES:
    _ensure_pg_schema()
elif create_client:
    db = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SECRET_KEY"],
    )
else:
    raise RuntimeError("未配置 DATABASE_URL，且 supabase 依赖不可用")

app = FastAPI()

# 进行中的图片生成任务，以及任务引用（防止被 GC）
PENDING_CHAR_IMG: set = set()
PENDING_STORYBOARD_IMG: set = set()
_BG_TASKS: set = set()


def _spawn_bg(coro):
    """启动一个脱离请求生命周期的后台任务（客户端断开/刷新不会取消它）。"""
    task = asyncio.create_task(coro)
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)
    return task


async def _image_bytes_from_prompt(model: str, prompt_text: str, size: str = "1024*1440") -> bytes:
    """Generate one image and return raw bytes, using the same providers as character images."""
    if model.startswith("gpt-image"):
        return await asyncio.to_thread(openai_image_bytes, model, prompt_text, size.replace("*", "x"))

    def _dashscope_gen() -> str:
        msg = DSMessage(role="user", content=[{"text": prompt_text}])
        task = DSImageGen.async_call(
            model=model,
            api_key=DASHSCOPE_API_KEY,
            messages=[msg],
            watermark=False,
            n=1,
            size=size,
        )
        result = DSImageGen.wait(task=task, api_key=DASHSCOPE_API_KEY)
        if result.output.task_status != "SUCCEEDED":
            detail = getattr(result.output, "message", "") or getattr(result.output, "code", "")
            raise RuntimeError(f"图片生成失败：{result.output.task_status} {detail}")
        for choice in result.output.choices:
            for item in choice["message"]["content"]:
                if item.get("type") == "image":
                    return item["image"]
        raise RuntimeError("未获取到图片 URL")

    image_url = await asyncio.to_thread(_dashscope_gen)
    async with httpx.AsyncClient(timeout=120) as hc:
        return (await hc.get(image_url)).content


# ── Helpers ──────────────────────────────────────────────────────────────────

def build_wb_char_sections(body: dict):
    worldbuilding = body.get("worldbuilding", "").strip()
    characters    = body.get("characters", "").strip()
    return (
        f"\n【世界观设定】\n{worldbuilding}\n" if worldbuilding else "",
        f"\n【主要角色】\n{characters}\n" if characters else "",
    )

def build_prev_section(previous_episodes: list) -> str:
    if not previous_episodes:
        return ""
    parts = []
    for ep in previous_episodes:
        header = f"第{ep['episode_num']}集《{ep.get('title', '')}》"
        if ep.get("summary"):
            parts.append(f"{header}\n{ep['summary']}")
        else:
            content = ep.get("content", "")
            excerpt = content[:600] + ("…（略）" if len(content) > 600 else "")
            parts.append(f"{header}\n{excerpt}")
    return "\n【前情回顾】\n" + "\n\n".join(parts) + "\n"


# ── SSE ──────────────────────────────────────────────────────────────────────

def sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def stream_openai(system: str, messages: list, max_tokens: int = 4000):
    full = ""
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=max_tokens, stream=True,
        messages=[{"role": "system", "content": system}] + messages,
    )
    for chunk in resp:
        if not chunk.choices:
            continue
        text = chunk.choices[0].delta.content or ""
        if text:
            full += text
            yield sse({"type": "chunk", "text": text})
    yield sse({"type": "done", "full": full})


def sse_stream(system, messages, max_tokens=4000):
    return StreamingResponse(
        stream_openai(system, messages, max_tokens),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Static ────────────────────────────────────────────────────────────────────

app.mount("/images", StaticFiles(directory="images"), name="images")
app.mount("/lib", StaticFiles(directory="lib"), name="lib")
if ATTACHMENT_STORAGE == "local":
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    app.mount(UPLOAD_URL_PREFIX, StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

IMG_CACHE_DIR = Path("images/cache")
IMG_CACHE_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/img")
async def img_proxy(u: str):
    """代理并本地缓存 Supabase 存储图片，绕过跨区域延迟。首次下载后存本地，之后本地直出。"""
    if ".supabase.co/storage/" not in u:
        raise HTTPException(400, "仅支持代理 Supabase 存储图片")
    key = hashlib.sha1(u.encode("utf-8")).hexdigest()
    fp = IMG_CACHE_DIR / f"{key}.webp"
    if not fp.exists():
        try:
            async with httpx.AsyncClient(timeout=60) as hc:
                r = await hc.get(u)
            if r.status_code != 200:
                raise HTTPException(502, f"源图获取失败：{r.status_code}")
            fp.write_bytes(r.content)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"源图获取失败：{e}")
    return FileResponse(
        str(fp),
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


def _safe_storage_path(path: str) -> str:
    cleaned = str(path).replace("\\", "/")
    parts = [part for part in cleaned.split("/") if part and part not in {".", ".."}]
    if not parts:
        raise HTTPException(400, "无效附件路径")
    return "/".join(parts)


def _local_upload_url(path: str) -> str:
    return f"{UPLOAD_URL_PREFIX}/{quote(path, safe='/')}"


def _storage_upload(path: str, data: bytes, content_type: str = "image/webp") -> str:
    path = _safe_storage_path(path)
    if ATTACHMENT_STORAGE == "local":
        target = UPLOAD_DIR.joinpath(*path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return _local_upload_url(path)
    if not db:
        raise RuntimeError("Supabase Storage 未初始化")
    db.storage.from_(SUPABASE_BUCKET).upload(
        path, data,
        file_options={"content-type": content_type or "image/webp", "upsert": "false"},
    )
    return db.storage.from_(SUPABASE_BUCKET).get_public_url(path)


def _storage_remove(path: str):
    path = _safe_storage_path(path)
    if ATTACHMENT_STORAGE == "local":
        try:
            UPLOAD_DIR.joinpath(*path.split("/")).unlink(missing_ok=True)
        except Exception:
            pass
        return
    if db:
        db.storage.from_(SUPABASE_BUCKET).remove([path])


@app.get("/")
async def index():
    return FileResponse("index.html")

@app.get("/app.js")
async def app_js():
    return FileResponse("app.js", media_type="application/javascript")

@app.get("/styles.css")
async def styles_css():
    return FileResponse("styles.css", media_type="text/css")


# ── AI Streaming ──────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: Request):
    body = await req.json()
    return sse_stream(CHAT_SYSTEM, body.get("messages", []), max_tokens=600)


@app.post("/api/refine-outline")
async def refine_outline(req: Request):
    body = await req.json()
    outline = body.get("outline", "")
    outline_context = f"【当前大纲】\n{outline}\n\n" if outline else ""
    system = REFINE_OUTLINE_SYSTEM.format(outline_context=outline_context)
    return sse_stream(system, body.get("messages", []), max_tokens=800)


@app.post("/api/apply-outline-refine")
async def apply_outline_refine(req: Request):
    body = await req.json()
    outline = body.get("outline", "")
    conv_text = "\n".join(
        f"{'用户' if m.get('role') == 'user' else 'AI'}：{m.get('content', '')}"
        for m in body.get("conversation", [])
    )
    prompt = APPLY_OUTLINE_REFINE_PROMPT.format(outline=outline, conv_text=conv_text)
    return sse_stream(APPLY_OUTLINE_REFINE_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=3000)


@app.post("/api/refine-worldbuilding")
async def refine_worldbuilding(req: Request):
    body = await req.json()
    wb = body.get("worldbuilding", "")
    wb_context = f"【当前世界观】\n{wb}\n\n" if wb else "用户尚未生成世界观，请根据他们的描述给出建议。\n\n"
    system = REFINE_WB_SYSTEM.format(wb_context=wb_context)
    return sse_stream(system, body.get("messages", []), max_tokens=1000)


@app.post("/api/apply-worldbuilding-refine")
async def apply_worldbuilding_refine(req: Request):
    body = await req.json()
    wb = body.get("worldbuilding", "")
    conv_text = "\n".join(
        f"{'用户' if m.get('role') == 'user' else 'AI'}：{m.get('content', '')}"
        for m in body.get("conversation", [])
    )
    wb_original = f"【原始世界观】\n{wb}\n\n" if wb else ""
    prompt = APPLY_WB_REFINE_PROMPT.format(wb_original=wb_original, conv_text=conv_text)
    return sse_stream(APPLY_WB_REFINE_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=3000)


@app.post("/api/worldbuilding")
async def worldbuilding(req: Request):
    body = await req.json()
    outline = body.get("outline", "")
    requirements = body.get("requirements", "")
    ctx = requirements or outline
    prompt = WORLDBUILDING_PROMPT.format(requirements=ctx) if ctx else "请生成一套完整的世界观设定。"
    return sse_stream(WORLDBUILDING_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=3000)


@app.post("/api/outline")
async def outline(req: Request):
    body = await req.json()
    ctx = body.get("requirements", "")
    wb  = body.get("worldbuilding", "")
    if wb:
        ctx = f"{ctx}\n\n【已确认的世界观设定】\n{wb}"
    prompt = OUTLINE_PROMPT.format(requirements=ctx, episode_count=body.get("episode_count", 15))
    return sse_stream(OUTLINE_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=4000)


@app.post("/api/episode")
async def episode(req: Request):
    body      = await req.json()
    ol_text   = body.get("outline", "")
    ep_num    = body.get("episode_num", 1)
    ep_plan   = body.get("episode_plan")
    worldbuilding = body.get("worldbuilding", "").strip()
    characters    = body.get("characters", "").strip()
    ep_list   = extract_episode_outlines(ol_text)
    ep_ol     = ep_list[ep_num - 1] if ep_num <= len(ep_list) else f"第{ep_num}集"
    if ep_plan:
        ep_ol += (
            f"\n\n【第{ep_num}集结构规划】\n"
            f"标题：{ep_plan.get('title','')}\n"
            f"本集目标：{ep_plan.get('goal','')}\n"
            f"主要冲突：{ep_plan.get('conflict','')}\n"
            f"结尾钩子：{ep_plan.get('hook','')}"
        )
    prev_section = build_prev_section(body.get("previous_episodes", []))
    wpm    = 200
    wb_section   = f"\n【世界观设定】\n{worldbuilding}\n" if worldbuilding else ""
    char_section = f"\n【主要角色】\n{characters}\n" if characters else ""
    prompt = EPISODE_PROMPT.format(
        episode_num=ep_num, outline=ol_text, episode_outline=ep_ol,
        duration_min=1, duration_max=3, word_count_min=wpm, word_count_max=3 * wpm,
        worldbuilding_section=wb_section, characters_section=char_section,
        previous_episodes_section=prev_section,
    )
    return sse_stream(EPISODE_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=3000)


@app.post("/api/summarize-episode")
async def summarize_episode(req: Request):
    body   = await req.json()
    prompt = EPISODE_SUMMARY_PROMPT.format(
        episode_num=body.get("episode_num", 1),
        title=body.get("title", ""),
        script_content=body.get("script_content", ""),
    )
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=700, stream=False,
        messages=[{"role": "user", "content": prompt}],
    )
    summary = resp.choices[0].message.content or ""
    return JSONResponse({"summary": summary})


@app.post("/api/outline-from-worldbuilding")
async def outline_from_worldbuilding(req: Request):
    body         = await req.json()
    outline      = body.get("outline", "")
    worldbuilding = body.get("worldbuilding", "")
    characters   = body.get("characters", "").strip()
    char_section = f"\n【主要角色】\n{characters}\n" if characters else ""
    prompt = OUTLINE_FROM_WB_PROMPT.format(
        outline=outline,
        worldbuilding=worldbuilding,
        characters_section=char_section,
    )
    return sse_stream(OUTLINE_FROM_WB_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=2000)


@app.post("/api/refine")
async def refine(req: Request):
    body   = await req.json()
    prompt = REFINE_PROMPT.format(feedback=body.get("feedback", ""), current_content=body.get("content", ""))
    return sse_stream(
        "你是专业短视频剧本编剧，根据用户反馈修改内容，保持风格一致。",
        [{"role": "user", "content": prompt}], max_tokens=4000,
    )


# ── Project CRUD ──────────────────────────────────────────────────────────────

def _row_to_proj(row: dict) -> dict:
    raw_outline = row.get("outline") or ""
    outline_plans = []
    outline_text = raw_outline
    if raw_outline.strip().startswith("["):
        try:
            parsed = json.loads(raw_outline)
            if isinstance(parsed, list):
                outline_plans = parsed
                outline_text = parsed[0].get("content", "") if parsed else ""
        except Exception:
            pass
    if not outline_plans and outline_text:
        outline_plans = [{"id": "plan-1", "title": "方案一", "label": "AI生成",
                          "content": outline_text, "generatedAt": row.get("updated", "")}]
    return {
        "id":           row["id"],
        "title":        row.get("title", "未命名"),
        "phase":        row.get("phase", "chat"),
        "requirements": row.get("requirements") or "",
        "worldbuilding":row.get("worldbuilding") or "",
        "outline":      outline_text,
        "outlinePlans": outline_plans,
        "episodeCount": row.get("episode_count", 15),
        "episodesDone": row.get("episodes_done", 0),
        "messages":     row.get("messages") or [],
        "episodes":     row.get("episodes") or {},
        "characters":    row.get("characters") or [],
        "episodePlans":  row.get("episode_plans") or {},
        "bookTitle":     row.get("book_title", "") or "",
        "coverPrompt":   row.get("cover_prompt", "") or "",
        "coverImageUrl": row.get("cover_image_url", "") or "",
        "created":       row.get("created", ""),
        "updated":       row.get("updated", ""),
    }


def _project_get(pid: str, columns: str = "*") -> dict | None:
    if USE_POSTGRES:
        cols = _parse_project_columns(columns)
        sql_cols = ", ".join(f'"{c}"' for c in cols)
        with _pg_connect() as conn:
            row = conn.execute(f"SELECT {sql_cols} FROM projects WHERE id = %s", (pid,)).fetchone()
        return dict(row) if row else None
    res = db.table("projects").select(columns).eq("id", pid).maybe_single().execute()
    return res.data


def _project_update(pid: str, values: dict):
    if not values:
        return
    if USE_POSTGRES:
        keys = _parse_project_columns(",".join(values.keys()))
        assignments = ", ".join(f'"{key}" = %s' for key in keys)
        params = [_pg_json_value(key, values[key]) for key in keys] + [pid]
        with _pg_connect() as conn:
            conn.execute(f"UPDATE projects SET {assignments} WHERE id = %s", params)
        return
    db.table("projects").update(values).eq("id", pid).execute()


def _project_upsert(values: dict):
    if USE_POSTGRES:
        keys = _parse_project_columns(",".join(values.keys()))
        cols = ", ".join(f'"{key}"' for key in keys)
        placeholders = ", ".join(["%s"] * len(keys))
        updates = ", ".join(f'"{key}" = EXCLUDED."{key}"' for key in keys if key != "id")
        params = [_pg_json_value(key, values[key]) for key in keys]
        with _pg_connect() as conn:
            conn.execute(
                f"INSERT INTO projects ({cols}) VALUES ({placeholders}) "
                f"ON CONFLICT (id) DO UPDATE SET {updates}",
                params,
            )
        return
    db.table("projects").upsert(values).execute()


def _projects_summary_rows() -> list[dict]:
    fields = "id,title,phase,episode_count,episodes_done,created,updated,book_title,cover_prompt,cover_image_url"
    if USE_POSTGRES:
        cols = _parse_project_columns(fields)
        sql_cols = ", ".join(f'"{c}"' for c in cols)
        with _pg_connect() as conn:
            rows = conn.execute(f"SELECT {sql_cols} FROM projects ORDER BY updated DESC").fetchall()
        return [dict(row) for row in rows]
    res = db.table("projects").select(fields).order("updated", desc=True).execute()
    return res.data or []


def _project_delete(pid: str):
    if USE_POSTGRES:
        with _pg_connect() as conn:
            conn.execute("DELETE FROM projects WHERE id = %s", (pid,))
        return
    db.table("projects").delete().eq("id", pid).execute()


def _load_proj(pid: str) -> dict:
    try:
        row = _project_get(pid)
    except Exception as e:
        print(f"[db] 加载项目失败 {pid}: {e}")
        raise HTTPException(503, "数据库连接失败，请检查 DATABASE_URL / Postgres 或 Supabase 配置")
    if not row:
        raise HTTPException(404, "项目不存在")
    return _row_to_proj(row)


def _db_add_char_image(pid: str, cid: str, img_id: str, url: str):
    """把新生成/上传的角色图直接写进 DB，使图片不依赖前端 persist 即可持久化。"""
    try:
        row = _project_get(pid, "characters")
        chars = (row or {}).get("characters") or []
        for c in chars:
            if str(c.get("id")) == str(cid):
                imgs = c.get("images") or []
                imgs.append({"id": img_id, "url": url})
                c["images"] = imgs
                if not c.get("imageUrl"):
                    c["imageUrl"] = url
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                _project_update(pid, {"characters": chars, "updated": now})
                return
    except Exception:
        pass  # 写库失败不阻断图片返回；前端 persist 仍是兜底


def _db_remove_char_image(pid: str, cid: str, img_id: str):
    """从 DB 角色 images 数组里移除一张图。"""
    try:
        row = _project_get(pid, "characters")
        chars = (row or {}).get("characters") or []
        for c in chars:
            if str(c.get("id")) == str(cid):
                imgs = [im for im in (c.get("images") or []) if str(im.get("id")) != str(img_id)]
                c["images"] = imgs
                c["imageUrl"] = imgs[0]["url"] if imgs else ""
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                _project_update(pid, {"characters": chars, "updated": now})
                return
    except Exception:
        pass


def _db_add_storyboard_image(pid: str, ep_num: int, img_id: str, url: str):
    """把分镜图写进 episode_plans[str(ep_num)].storyboardImages。"""
    try:
        row = _project_get(pid, "episode_plans")
        plans = (row or {}).get("episode_plans") or {}
        key = str(ep_num)
        plan = plans.get(key) or {}
        imgs = plan.get("storyboardImages") or []
        imgs.append({"id": img_id, "url": url})
        plan["storyboardImages"] = imgs
        plans[key] = plan
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        _project_update(pid, {"episode_plans": plans, "updated": now})
    except Exception:
        pass


def _db_remove_storyboard_image(pid: str, ep_num: int, img_id: str):
    """从 episode_plans[str(ep_num)].storyboardImages 移除一张图。"""
    try:
        row = _project_get(pid, "episode_plans")
        plans = (row or {}).get("episode_plans") or {}
        key = str(ep_num)
        plan = plans.get(key) or {}
        plan["storyboardImages"] = [
            im for im in (plan.get("storyboardImages") or [])
            if str(im.get("id")) != str(img_id)
        ]
        plans[key] = plan
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        _project_update(pid, {"episode_plans": plans, "updated": now})
    except Exception:
        pass


def _save_proj(data: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    pid = data.get("id") or datetime.now().strftime("%Y%m%d_%H%M%S")
    episodes_done = len(data.get("episodes", {}))
    _project_upsert({
        "id":            pid,
        "title":         data.get("title", "未命名"),
        "phase":         data.get("phase", "chat"),
        "requirements":  data.get("requirements", ""),
        "worldbuilding": data.get("worldbuilding", ""),
        "outline":       (json.dumps(data["outlinePlans"], ensure_ascii=False)
                          if data.get("outlinePlans") else data.get("outline", "")),
        "episode_count": data.get("episodeCount", 15),
        "episodes_done": episodes_done,
        "messages":      data.get("messages", []),
        "episodes":      data.get("episodes", {}),
        "characters":    data.get("characters", []),
        "episode_plans": data.get("episodePlans", {}),
        "book_title":    data.get("bookTitle", ""),
        "cover_prompt":  data.get("coverPrompt", ""),
        "cover_image_url": data.get("coverImageUrl", ""),
        "created":       data.get("created") or now,
        "updated":       now,
    })
    return pid


@app.post("/api/project")
async def project_save(req: Request):
    body = await req.json()
    pid  = _save_proj(body)
    return {"id": pid}


@app.get("/api/projects")
async def projects_list():
    try:
        rows = _projects_summary_rows()
    except Exception as e:
        print(f"[db] 项目列表加载失败: {e}")
        return JSONResponse([], headers={"X-DB-Unavailable": "1"})
    return JSONResponse([{
        "id":           r["id"],
        "title":        r.get("title", "未命名"),
        "phase":        r.get("phase", "chat"),
        "updated":      r.get("updated", ""),
        "created":      r.get("created", ""),
        "episodeCount": r.get("episode_count", 0),
        "episodesDone": r.get("episodes_done", 0),
        "bookTitle":     r.get("book_title", "") or "",
        "coverPrompt":   r.get("cover_prompt", "") or "",
        "coverImageUrl": r.get("cover_image_url", "") or "",
    } for r in rows])


@app.get("/api/project/{pid}")
async def project_load(pid: str):
    return JSONResponse(_load_proj(pid))


@app.patch("/api/project/{pid}")
async def project_patch(pid: str, req: Request):
    body  = await req.json()
    field = body.get("field")
    now   = datetime.now().strftime("%Y-%m-%d %H:%M")

    if field == "worldbuilding":
        _project_update(pid, {"worldbuilding": body["content"], "updated": now})
    elif field == "outline":
        _project_update(pid, {"outline": body["content"], "updated": now})
    elif field == "episode":
        row = _project_get(pid, "episodes")
        if not row:
            raise HTTPException(404, "项目不存在")
        episodes = row.get("episodes") or {}
        episodes[str(body["num"])] = body["content"]
        _project_update(pid, {
            "episodes":      episodes,
            "episodes_done": len(episodes),
            "updated":       now,
        })
    elif field == "chat":
        _project_update(pid, {"messages": body["messages"], "updated": now})
    elif field == "characters":
        _project_update(pid, {
            "characters": body["characters"], "updated": now,
        })
    elif field == "episode_plans":
        _project_update(pid, {
            "episode_plans": body["episodePlans"], "updated": now,
        })
    else:
        raise HTTPException(400, f"未知 field: {field}")
    return {"ok": True}


@app.delete("/api/project/{pid}")
async def project_delete(pid: str):
    _project_delete(pid)
    return {"ok": True}


# ── Characters ───────────────────────────────────────────────────────────────

def _clean_json_obj(raw: str) -> dict:
    """Strip markdown fences and extract the outermost JSON object."""
    raw = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r'```\s*$', '', raw.strip(), flags=re.MULTILINE).strip()
    m = re.search(r'\{[\s\S]*\}', raw)
    return json.loads(m.group(0) if m else raw)

def _extract_json_array(raw: str) -> list:
    """Strip markdown fences, extract outermost JSON array, repair if truncated."""
    raw = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r'```\s*$', '', raw.strip(), flags=re.MULTILINE).strip()
    # Grab from first [ onwards (drop any leading prose)
    start = raw.find('[')
    if start != -1:
        raw = raw[start:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Response was likely truncated; recover all fully-closed objects
        # Find the last }, or } before the truncation point
        last_obj_end = -1
        depth = 0
        in_str = False
        escape = False
        for i, ch in enumerate(raw):
            if escape:
                escape = False
                continue
            if ch == '\\' and in_str:
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    last_obj_end = i
        if last_obj_end != -1:
            repaired = raw[:last_obj_end + 1] + ']'
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
        return []


def _role_prompt_label(role: str) -> str:
    role = (role or "").strip().lower()
    if role in {"protagonist", "主角", "男主", "女主", "正派"}:
        return "正派核心角色"
    if role in {"antagonist", "反派", "敌人"}:
        return "反派/对立阵营角色"
    return "配角/功能性角色"


def _character_image_prompt_payload(character: dict, worldbuilding: str = "", project_title: str = "") -> dict:
    name = character.get("name") or "未命名"
    role = character.get("role") or ""
    role_label = _role_prompt_label(role)
    personality = character.get("personality") or ""
    if isinstance(personality, list):
        personality = "、".join(str(x) for x in personality if x)
    prompt = f"""请为以下角色生成一条专属 AI 绘图提示词，用于生成“角色设定图”。只输出 JSON 对象。

【作品名】
{project_title or "未命名"}

【世界观】
{(worldbuilding or "")[:1200]}

【角色信息】
姓名：{name}
阵营/定位：{role_label}（原始 role：{role}）
年龄：{character.get("age") or ""}
外貌：{character.get("appearance") or ""}
性格：{personality}
小传：{character.get("biography") or character.get("background") or ""}

输出格式：
{{"genPrompt": "完整提示词"}}

要求：
- genPrompt 开头必须是：角色「{name}」。
- 必须根据阵营/定位做差异化设计：
  - 正派核心角色：更强调信念感、主角辨识度、清澈或坚毅的眼神、英雄式轮廓、明亮但不单调的主色。
  - 反派/对立阵营角色：更强调压迫感、危险气质、权力符号、阴影与冷色/暗金/血色等色彩策略，但不要脸谱化。
  - 配角/功能性角色：更强调职业功能、身份工具、生活痕迹、辅助叙事的剪影与道具。
- 必须补全具体外貌差异：发型发色、眼睛、服装材质、体型、标志性道具、配色、背景场景。
- 必须贴合世界观题材，不要使用空泛词堆砌。
- 必须包含“全身多角度展示、头部特写、服饰/道具拆解、高清面料纹理、影视概念美术设定图”等设定图要素。
- 不要保留方括号，不要写解释，不要输出 markdown。"""

    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=900,
        temperature=0.75,
        stream=False,
        messages=[
            {"role": "system", "content": "你是影视概念美术总监，擅长根据角色阵营与故事功能生成差异化角色设定图提示词。只输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
    )
    data = _clean_json_obj(resp.choices[0].message.content or "")
    gen_prompt = str(data.get("genPrompt") or "").strip()
    if not gen_prompt:
        raise HTTPException(500, "角色图提示词生成失败")
    return {"genPrompt": gen_prompt}


@app.post("/api/project/{pid}/extract-characters")
async def extract_characters(pid: str, req: Request):
    body = await req.json()
    worldbuilding = body.get("worldbuilding", "")
    prompt = CHARACTER_EXTRACT_PROMPT.format(worldbuilding=worldbuilding)
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=4096, stream=False,
        messages=[
            {"role": "system", "content": CHARACTER_EXTRACT_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    characters = _extract_json_array(raw)
    if not characters:
        raise HTTPException(status_code=500, detail="角色提取返回空列表，请重试")
    return JSONResponse(characters)


@app.post("/api/project/{pid}/character-image-prompt")
async def generate_character_image_prompt(pid: str, req: Request):
    body = await req.json()
    character = body.get("character") or {}
    if not character.get("name"):
        raise HTTPException(400, "缺少角色信息")
    worldbuilding = body.get("worldbuilding", "")
    project_title = body.get("projectTitle", "")
    return JSONResponse(_character_image_prompt_payload(character, worldbuilding, project_title))


@app.post("/api/project/{pid}/reextract-character")
async def reextract_character(pid: str, req: Request):
    body = await req.json()
    worldbuilding = body.get("worldbuilding", "")
    name = body.get("name", "未命名")
    system = (
        "你是角色信息提取与人设图提示词生成专家。从世界观文档中提取指定角色的详细信息，"
        "只输出 JSON 对象，不输出任何其他内容。"
    )
    prompt = f"""从以下世界观设定文档中提取角色「{name}」的信息，输出 JSON 对象（非数组）。

【世界观文本】
{worldbuilding}

输出格式（纯 JSON 对象，无其他文字）：
{{
  "role": "protagonist",
  "personality": "性格描述，30字内",
  "age": "年龄或年龄段，10字内",
  "appearance": "发型发色、眼睛特征、服装颜色款式、体型气质，60字内，各项顿号分隔",
  "genPrompt": "角色「{name}」，[年龄段]，[发型发色]，[眼睛特征]，[服装描述]，[体型气质]。制作一张高预算院线电影级写实人物设定展板，适配[题材风格]题材，专属定制配色[角色主色调]，背景带有环境光影反射效果。摒弃僵硬网格、对称刻板构图，采用风格化导演提案展板排版，高级概念美术版式。写实真人角色，人体结构精准、比例自然，保留细微的面部与皮肤真实瑕疵，人物情绪张力饱满、人设辨识度极强。包含全套角色设定内容：全身多角度展示视图、多神态头部角度特写、影视级主角肖像、完整服饰拆解细节、服装剪裁工艺展示、高清面料纹理细节、专业影视制作备注。场景背景：[角色标志性场景与氛围]，柔和环境光晕，画面层次丰富，氛围感极致。画面风格：[核心画风]，高对比度电影级光影，院线级曝光质感，浅景深虚化，细腻胶片颗粒质感，情绪表现力拉满，超高细节、照片级写实、8K超高清、对焦清晰、专业概念美术、官方标准人物设定图。"
}}

规则：
- role 只能取 protagonist / antagonist / supporting 之一
- genPrompt 开头必须是角色「{name}」+ 年龄段 + 具体外貌（发型发色/眼睛/服装/气质），这是区分角色相貌的关键
- genPrompt 中 [] 内为填写指导，替换为实际内容，不保留方括号
- 直接输出 JSON，不要加 ```json 标记"""
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=1000, stream=False,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    return JSONResponse(_clean_json_obj(raw))


@app.post("/api/project/{pid}/characters/{cid}/upload-image")
async def upload_character_image(pid: str, cid: str, file: UploadFile = File(...)):
    import time as _time
    img_id = str(int(_time.time() * 1000))
    data = await file.read()
    path = f"{pid}/{cid}_{img_id}.webp"
    url = _storage_upload(path, data, file.content_type or "image/webp")
    _db_add_char_image(pid, cid, img_id, url)
    return {"url": url, "imgId": img_id}


@app.post("/api/project/{pid}/characters/{cid}/generate-image")
async def generate_character_image(pid: str, cid: str, req: Request):
    body = await req.json()
    appearance = body.get("appearance", "神秘人物")
    model = body.get("model", "wan2.7-image-pro")
    custom_prompt = (body.get("prompt") or "").strip()
    prompt_text = custom_prompt if custom_prompt else (
        f"{appearance}，古装写实风格，人物设定图，全身正面站立，"
        "精致五官，华丽古装服饰，衣袂飘逸，细腻笔触，简洁渐变背景，高清插画"
    )

    key = f"{pid}:{cid}"

    async def _run():
        try:
            if model.startswith("gpt-image"):
                img_data = await asyncio.to_thread(openai_image_bytes, model, prompt_text)
            else:
                def _dashscope_gen() -> str:
                    msg = DSMessage(role="user", content=[{"text": prompt_text}])
                    task = DSImageGen.async_call(
                        model=model,
                        api_key=DASHSCOPE_API_KEY,
                        messages=[msg],
                        watermark=False,
                        n=1,
                        size="1024*1440",
                    )
                    result = DSImageGen.wait(task=task, api_key=DASHSCOPE_API_KEY)
                    if result.output.task_status != "SUCCEEDED":
                        raise RuntimeError(f"图片生成失败：{result.output.task_status}")
                    for choice in result.output.choices:
                        for item in choice["message"]["content"]:
                            if item.get("type") == "image":
                                return item["image"]
                    raise RuntimeError("未获取到图片 URL")

                image_url = await asyncio.to_thread(_dashscope_gen)
                async with httpx.AsyncClient(timeout=120) as hc:
                    img_data = (await hc.get(image_url)).content

            import time as _time
            img_id = str(int(_time.time() * 1000))
            path = f"{pid}/{cid}_{img_id}.webp"
            public_url = _storage_upload(path, img_data, "image/webp")
            _db_add_char_image(pid, cid, img_id, public_url)
        except Exception as e:
            print(f"[char-image] 生成失败 {key}: {e}")
        finally:
            PENDING_CHAR_IMG.discard(key)

    PENDING_CHAR_IMG.add(key)
    _spawn_bg(_run())
    return {"status": "started"}


@app.get("/api/project/{pid}/char-images")
async def char_images_status(pid: str):
    """供前端轮询：哪些角色正在生成图，以及各角色最新的图片列表（已写入 DB 的）。"""
    try:
        row = _project_get(pid, "characters")
        chars = (row or {}).get("characters") if row else []
    except Exception as e:
        print(f"[db] 角色图状态加载失败 {pid}: {e}")
        chars = []
    out = [{"id": c.get("id"), "images": c.get("images") or []} for c in (chars or [])]
    prefix = f"{pid}:"
    pending = [k.split(":", 1)[1] for k in PENDING_CHAR_IMG if k.startswith(prefix)]
    return {"pending": pending, "characters": out}


@app.delete("/api/project/{pid}/characters/{cid}/images/{img_id}")
async def delete_character_image(pid: str, cid: str, img_id: str):
    path = f"{pid}/{cid}_{img_id}.webp"
    try:
        _storage_remove(path)
    except Exception:
        pass  # best-effort; storage orphans are acceptable
    _db_remove_char_image(pid, cid, img_id)
    return {"ok": True}


@app.post("/api/project/{pid}/episodes/{ep_num}/generate-storyboard-image")
async def generate_storyboard_image(pid: str, ep_num: int, req: Request):
    body = await req.json()
    model = body.get("model", "wan2.7-image-pro")
    count = max(1, min(int(body.get("count") or 1), 4))
    custom_prompt = (body.get("prompt") or "").strip()
    title = (body.get("title") or "").strip()
    goal = (body.get("goal") or "").strip()
    conflict = (body.get("conflict") or "").strip()
    hook = (body.get("hook") or "").strip()
    script_content = (body.get("scriptContent") or "").strip()
    worldbuilding = (body.get("worldbuilding") or "").strip()
    characters = (body.get("characters") or "").strip()

    if custom_prompt:
        prompt_text = custom_prompt
    else:
        script_excerpt = script_content[:900] + ("…" if len(script_content) > 900 else "")
        prompt_text = f"""第{ep_num}集《{title or '未命名'}》分镜图，横版电影分镜设计稿，6格关键镜头连续画面。
本集目标：{goal}
主要冲突：{conflict}
结尾钩子：{hook}
世界观：{worldbuilding[:700]}
主要角色：{characters[:900]}
正文片段：{script_excerpt}
要求：每格构图清晰，镜头语言明确，包含景别变化、人物走位、动作瞬间、光影氛围和场景调度；统一角色外貌与服装，写实影视概念设计，专业 storyboard sheet，cinematic lighting，高细节，横向构图，不要水印，不要乱码文字。"""

    started = []

    async def _run_one(task_id: str):
        key = f"{pid}:{ep_num}:{task_id}"
        try:
            img_data = await _image_bytes_from_prompt(model, prompt_text, size="1536*1024")
            path = f"{pid}/storyboards/ep{ep_num}_{task_id}.webp"
            public_url = _storage_upload(path, img_data, "image/webp")
            _db_add_storyboard_image(pid, ep_num, task_id, public_url)
        except Exception as e:
            print(f"[storyboard-image] 生成失败 {key}: {e}")
        finally:
            PENDING_STORYBOARD_IMG.discard(key)

    import time as _time
    for i in range(count):
        task_id = f"{int(_time.time() * 1000)}_{i}"
        key = f"{pid}:{ep_num}:{task_id}"
        PENDING_STORYBOARD_IMG.add(key)
        started.append(task_id)
        _spawn_bg(_run_one(task_id))

    return {"status": "started", "count": len(started), "imageIds": started}


@app.get("/api/project/{pid}/storyboard-images")
async def storyboard_images_status(pid: str):
    """供前端轮询：哪些集正在生成分镜图，以及各集最新图片列表。"""
    try:
        row = _project_get(pid, "episode_plans")
        plans = (row or {}).get("episode_plans") if row else {}
    except Exception as e:
        print(f"[db] 分镜图状态加载失败 {pid}: {e}")
        plans = {}
    episodes = []
    for key, plan in (plans or {}).items():
        try:
            num = int(key)
        except (TypeError, ValueError):
            continue
        episodes.append({
            "episodeNumber": num,
            "storyboardImages": plan.get("storyboardImages") or [],
        })

    prefix = f"{pid}:"
    pending_counts = {}
    for key in PENDING_STORYBOARD_IMG:
        if not key.startswith(prefix):
            continue
        parts = key.split(":")
        if len(parts) < 3:
            continue
        pending_counts[parts[1]] = pending_counts.get(parts[1], 0) + 1
    pending = sorted((int(k) for k in pending_counts), key=int)
    return {"pending": pending, "pendingCounts": pending_counts, "episodes": episodes}


@app.delete("/api/project/{pid}/episodes/{ep_num}/storyboard-images/{img_id}")
async def delete_storyboard_image(pid: str, ep_num: int, img_id: str):
    path = f"{pid}/storyboards/ep{ep_num}_{img_id}.webp"
    try:
        _storage_remove(path)
    except Exception:
        pass
    _db_remove_storyboard_image(pid, ep_num, img_id)
    return {"ok": True}


@app.post("/api/project/{pid}/episodes/{ep_num}/upload-storyboard-image")
async def upload_storyboard_image(pid: str, ep_num: int, file: UploadFile = File(...)):
    import time as _time
    img_id = str(int(_time.time() * 1000))
    data = await file.read()
    path = f"{pid}/storyboards/ep{ep_num}_{img_id}.webp"
    url = _storage_upload(path, data, file.content_type or "image/webp")
    _db_add_storyboard_image(pid, ep_num, img_id, url)
    return {"url": url, "imgId": img_id}


# ── Book title & cover ────────────────────────────────────────────────────────

@app.post("/api/project/{pid}/generate-book-title")
async def generate_book_title(pid: str, req: Request):
    body = await req.json()
    title = body.get("title", "").strip()
    worldbuilding = (body.get("worldbuilding") or "").strip()[:400]

    context = f"剧本名：{title}"
    if worldbuilding:
        context += f"\n世界观简介：{worldbuilding}"

    system = (
        "你是一位资深书名顾问。根据用户提供的剧本信息，完成两件事：\n"
        "1. 生成一个2-4个汉字的书名，简洁有力，富有意境，契合题材风格，不要标点符号。\n"
        "2. 根据题材（古风/都市/科幻/悬疑/玄幻等）生成一段封面插画提示词，"
        "描述封面画面内容，以【书籍封面插画，竖版构图，精致细腻】结尾。\n\n"
        "只返回 JSON，格式：{\"bookTitle\": \"xxx\", \"coverPrompt\": \"xxx\"}"
    )

    def _call():
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": context},
            ],
            max_tokens=300,
            temperature=0.9,
        )
        return resp.choices[0].message.content or ""

    raw = await asyncio.to_thread(_call)

    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise HTTPException(500, f"模型返回格式错误：{raw[:100]}")
    data = json.loads(match.group())

    book_title   = str(data.get("bookTitle", "")).strip()[:8]
    cover_prompt = str(data.get("coverPrompt", "")).strip()

    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        _project_update(pid, {
            "book_title":   book_title,
            "cover_prompt": cover_prompt,
            "updated":      now,
        })
    except Exception:
        pass

    return {"bookTitle": book_title, "coverPrompt": cover_prompt}


@app.post("/api/project/{pid}/generate-cover-prompt")
async def generate_cover_prompt(pid: str):
    proj = _load_proj(pid)
    title         = proj.get("title", "") or ""
    book_title    = proj.get("bookTitle", "") or ""
    worldbuilding = (proj.get("worldbuilding") or "")[:600]

    context = f"剧本名：{title}"
    if book_title:
        context += f"\n书名：{book_title}"
    if worldbuilding:
        context += f"\n世界观设定：{worldbuilding}"

    system = (
        "你是书籍封面设计顾问。根据剧本信息和世界观设定，生成一段用于 AI 绘图的封面插画提示词。\n"
        "要求：先判断题材风格（古风/仙侠/都市/科幻/悬疑/玄幻等），再描述具体的封面画面"
        "（主体形象、场景环境、氛围、色调、光影），以【书籍封面插画，竖版构图，精致细腻】结尾。\n"
        "只返回提示词本身，不要任何解释、编号或引号。"
    )

    def _call():
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": context},
            ],
            max_tokens=400,
            temperature=0.9,
        )
        return resp.choices[0].message.content or ""

    raw = await asyncio.to_thread(_call)
    cover_prompt = raw.strip().strip('「」“”"\'')

    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        _project_update(pid, {"cover_prompt": cover_prompt, "updated": now})
    except Exception:
        pass  # 写库失败不影响返回，提示词主要给前端用

    return {"coverPrompt": cover_prompt}


@app.post("/api/project/{pid}/generate-cover")
async def generate_project_cover(pid: str, req: Request):
    import time as _time
    body = await req.json()
    cover_prompt = (body.get("coverPrompt") or "").strip()
    book_title   = (body.get("bookTitle") or "").strip()
    model        = body.get("model", "wan2.7-image-pro")

    if not cover_prompt:
        cover_prompt = f"{book_title}，书籍封面插画，竖版构图，精致细腻" if book_title else "精美书籍封面插画，竖版构图"

    if model.startswith("gpt-image"):
        img_data = await asyncio.to_thread(openai_image_bytes, model, cover_prompt)
    else:
        def _dashscope_gen() -> str:
            msg = DSMessage(role="user", content=[{"text": cover_prompt}])
            task = DSImageGen.async_call(
                model=model,
                api_key=DASHSCOPE_API_KEY,
                messages=[msg],
                watermark=False,
                n=1,
                size="1024*1440",
            )
            result = DSImageGen.wait(task=task, api_key=DASHSCOPE_API_KEY)
            if result.output.task_status != "SUCCEEDED":
                detail = getattr(result.output, "message", "") or getattr(result.output, "code", "")
                raise RuntimeError(f"封面生成失败：{result.output.task_status} {detail}")
            for choice in result.output.choices:
                for item in choice["message"]["content"]:
                    if item.get("type") == "image":
                        return item["image"]
            raise RuntimeError("未获取到封面图 URL")

        image_url = await asyncio.to_thread(_dashscope_gen)
        async with httpx.AsyncClient(timeout=60) as hc:
            img_data = (await hc.get(image_url)).content

    img_id = str(int(_time.time() * 1000))
    path = f"{pid}/cover_{img_id}.webp"
    public_url = _storage_upload(path, img_data, "image/webp")

    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        _project_update(pid, {
            "cover_image_url": public_url,
            "cover_prompt":    cover_prompt,
            "updated":         now,
        })
    except Exception:
        pass

    return {"coverImageUrl": public_url}


@app.post("/api/project/{pid}/upload-cover")
async def upload_project_cover(pid: str, file: UploadFile = File(...)):
    import time as _time
    img_id = str(int(_time.time() * 1000))
    data = await file.read()
    path = f"{pid}/cover_upload_{img_id}.webp"
    public_url = _storage_upload(path, data, file.content_type or "image/webp")
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        _project_update(pid, {
            "cover_image_url": public_url,
            "updated":         now,
        })
    except Exception:
        pass
    return {"coverImageUrl": public_url}


# ── Episode Plans ────────────────────────────────────────────────────────────

@app.post("/api/project/{pid}/generate-episode-plans")
async def generate_episode_plans(pid: str, req: Request):
    body = await req.json()
    outline = body.get("outline", "")
    episode_count = body.get("episode_count", 15)
    wb_section, char_section = build_wb_char_sections(body)
    prompt = EPISODE_PLAN_PROMPT.format(
        outline=outline, episode_count=episode_count,
        worldbuilding_section=wb_section, characters_section=char_section,
    )
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=4096, stream=False,
        messages=[
            {"role": "system", "content": EPISODE_PLAN_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    plans = _clean_json_obj(raw)
    return JSONResponse(plans)


@app.post("/api/project/{pid}/generate-episode-plan/{ep_num}")
async def generate_single_episode_plan(pid: str, ep_num: int, req: Request):
    body = await req.json()
    outline = body.get("outline", "")
    wb_section, char_section = build_wb_char_sections(body)
    neighbor_plans = body.get("neighborPlans", {})
    neighbor_lines = [f"第{k}集：{v.get('title','')} / 目标：{v.get('goal','')} / 钩子：{v.get('hook','')}"
                      for k, v in neighbor_plans.items()]
    neighbor_section = ("\n【相邻集规划参考】\n" + "\n".join(neighbor_lines) + "\n") if neighbor_lines else ""
    prompt = SINGLE_EPISODE_PLAN_PROMPT.format(
        ep_num=ep_num, outline=outline,
        worldbuilding_section=wb_section, characters_section=char_section,
        neighbor_section=neighbor_section,
    )
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=512, stream=False,
        messages=[
            {"role": "system", "content": EPISODE_PLAN_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    plan = _clean_json_obj(raw)
    return JSONResponse(plan)


# ── New-frontend AI endpoints (no pid required) ──────────────────────────────

@app.post("/api/outline-plans")
async def outline_plans_gen(req: Request):
    body = await req.json()
    pos  = body.get("storyPositioning", {})
    episode_count = body.get("episodeCount", 10)
    requirements  = body.get("requirements", "")
    if requirements:
        prompt = OUTLINE_PLANS_FROM_CHAT_PROMPT.format(
            episode_count=episode_count,
            requirements=requirements,
        )
    else:
        prompt = OUTLINE_PLANS_PROMPT.format(
            name          = pos.get("name", "未命名"),
            work_type     = pos.get("workType", "短剧"),
            episode_count = episode_count,
            audience      = "、".join(pos.get("audience", [])) or "不限",
            genres        = "、".join(pos.get("genres", [])) or "不限",
            core_elements = "、".join(pos.get("coreElements", [])) or "不限",
            emotional_tone= "、".join(pos.get("emotionalTone", [])) or "不限",
        )
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=4000, stream=False,
        messages=[
            {"role": "system", "content": OUTLINE_PLANS_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
    )
    raw   = resp.choices[0].message.content.strip()
    plans = _extract_json_array(raw)
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for i, plan in enumerate(plans):
        plan.setdefault("id",    f"plan-{i+1}")
        plan.setdefault("title", f"方案{i+1}")
        plan.setdefault("label", "AI生成")
        plan["generatedAt"] = now
    return JSONResponse({"plans": plans})


@app.post("/api/generate-characters")
async def generate_characters_standalone(req: Request):
    body          = await req.json()
    worldbuilding = body.get("worldbuilding", "")
    prompt        = CHARACTER_EXTRACT_PROMPT.format(worldbuilding=worldbuilding)
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=4096, stream=False,
        messages=[
            {"role": "system", "content": CHARACTER_EXTRACT_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
    )
    raw        = resp.choices[0].message.content.strip()
    characters = _extract_json_array(raw)
    if not characters:
        raise HTTPException(500, "角色提取失败，请重试")
    return JSONResponse(characters)


@app.post("/api/refine-character-background")
async def refine_character_background(req: Request):
    body      = await req.json()
    char_name = body.get("charName", "")
    bg        = body.get("background", "")
    messages  = body.get("messages", [])
    system    = REFINE_CHAR_BG_SYSTEM.format(char_name=char_name, bg_context=bg or "（暂无）")
    return sse_stream(system, messages, max_tokens=800)


@app.post("/api/apply-character-background-refine")
async def apply_character_background_refine(req: Request):
    body      = await req.json()
    char_name = body.get("charName", "")
    bg        = body.get("background", "")
    messages  = body.get("messages", [])
    conv_text = "\n".join(f"{'用户' if m['role']=='user' else 'AI'}：{m['content']}" for m in messages)
    prompt    = APPLY_CHAR_BG_PROMPT.format(char_name=char_name, bg_original=bg or "（暂无）", conv_text=conv_text)
    return sse_stream(APPLY_CHAR_BG_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=600)


@app.post("/api/refine-episode")
async def refine_episode(req: Request):
    body       = await req.json()
    ep_num     = body.get("epNum", 1)
    messages   = body.get("messages", [])
    wb_section, char_section = build_wb_char_sections(body)
    system     = REFINE_EP_SYSTEM.format(
        ep_num=ep_num,
        ep_title=body.get("title", ""),
        ep_goal=body.get("goal", ""),
        ep_conflict=body.get("conflict", ""),
        ep_hook=body.get("hook", ""),
        worldbuilding_section=wb_section,
        characters_section=char_section,
    )
    return sse_stream(system, messages, max_tokens=800)


@app.post("/api/refine-script")
async def refine_script(req: Request):
    body          = await req.json()
    ep_num        = body.get("epNum", 1)
    script_text   = body.get("scriptContent", "")
    preview       = script_text[:800] + ("…" if len(script_text) > 800 else "")
    messages      = body.get("messages", [])
    worldbuilding = body.get("worldbuilding", "").strip()
    characters    = body.get("characters", "").strip()
    system        = REFINE_SCRIPT_SYSTEM.format(
        ep_num=ep_num,
        ep_goal=body.get("goal", ""),
        ep_conflict=body.get("conflict", ""),
        ep_hook=body.get("hook", ""),
        script_preview=preview or "（暂无正文）",
        worldbuilding_section=f"\n世界观：{worldbuilding}\n" if worldbuilding else "",
        characters_section=f"\n主要角色：\n{characters}\n" if characters else "",
    )
    return sse_stream(system, messages, max_tokens=1000)


@app.post("/api/apply-script-refine")
async def apply_script_refine(req: Request):
    body         = await req.json()
    ep_num       = body.get("epNum", 1)
    script_text  = body.get("scriptContent", "")
    messages     = body.get("messages", [])
    worldbuilding = body.get("worldbuilding", "").strip()
    characters    = body.get("characters", "").strip()
    prev_section = build_prev_section(body.get("previous_episodes", []))
    conv_text    = "\n".join(f"{'用户' if m['role']=='user' else 'AI'}：{m['content']}" for m in messages)
    prompt       = APPLY_SCRIPT_PROMPT.format(
        ep_num=ep_num,
        ep_goal=body.get("goal", ""),
        ep_conflict=body.get("conflict", ""),
        ep_hook=body.get("hook", ""),
        script_content=script_text or "（暂无正文）",
        conv_text=conv_text,
        worldbuilding_section=f"\n【世界观设定】\n{worldbuilding}\n" if worldbuilding else "",
        characters_section=f"\n【主要角色】\n{characters}\n" if characters else "",
        previous_episodes_section=prev_section,
    )
    return sse_stream(APPLY_SCRIPT_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=4000)


@app.post("/api/apply-episode-refine")
async def apply_episode_refine(req: Request):
    body       = await req.json()
    ep_num     = body.get("epNum", 1)
    messages   = body.get("messages", [])
    wb_section, char_section = build_wb_char_sections(body)
    conv_text  = "\n".join(f"{'用户' if m['role']=='user' else 'AI'}：{m['content']}" for m in messages)
    prompt     = APPLY_EP_PROMPT.format(
        ep_num=ep_num,
        ep_title=body.get("title", ""),
        ep_goal=body.get("goal", ""),
        ep_conflict=body.get("conflict", ""),
        ep_hook=body.get("hook", ""),
        conv_text=conv_text,
        worldbuilding_section=wb_section,
        characters_section=char_section,
    )
    return sse_stream(APPLY_EP_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=500)


@app.post("/api/episode-plans")
async def episode_plans_standalone(req: Request):
    body          = await req.json()
    outline       = body.get("outline", "")
    episode_count = body.get("episodeCount", 10)
    wb_section, char_section = build_wb_char_sections(body)
    prompt = EPISODE_PLAN_PROMPT.format(
        outline=outline, episode_count=episode_count,
        worldbuilding_section=wb_section, characters_section=char_section,
    )
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=4096, stream=False,
        messages=[
            {"role": "system", "content": EPISODE_PLAN_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
    )
    raw   = resp.choices[0].message.content.strip()
    plans = _clean_json_obj(raw)
    return JSONResponse(plans)


# ── Export ────────────────────────────────────────────────────────────────────

@app.post("/api/export/{pid}")
async def project_export(pid: str):
    data     = _load_proj(pid)
    episodes = [data["episodes"][str(k)] for k in sorted(int(x) for x in data.get("episodes", {}))]
    Path(EXPORT_DIR).mkdir(exist_ok=True)
    path = save_full_script(data.get("outline", ""), episodes, EXPORT_DIR)
    return {"path": path}
