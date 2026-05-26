#!/usr/bin/env python3
import asyncio
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
from openai import OpenAI
from supabase import create_client, Client
from exporter import save_full_script, extract_episode_outlines
from prompts import (OUTLINE_SYSTEM, OUTLINE_PROMPT, EPISODE_SYSTEM, EPISODE_PROMPT,
                     REFINE_PROMPT, WORLDBUILDING_SYSTEM, WORLDBUILDING_PROMPT,
                     CHARACTER_EXTRACT_SYSTEM, CHARACTER_EXTRACT_PROMPT)

load_dotenv()

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_BASE_URL"],
)
MODEL      = os.environ["OPENAI_MODEL_ID"]
EXPORT_DIR = "./scripts"

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY") or os.environ["OPENAI_API_KEY"]
dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

db: Client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SECRET_KEY"],
)

app = FastAPI()


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

@app.get("/")
async def index():
    return FileResponse("index.html")


# ── AI Streaming ──────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(req: Request):
    body = await req.json()
    system = """你是一个短视频剧本创作助手，专注于古装/玄幻类型。
通过友好对话收集用户的故事需求：主角设定、故事核心、世界观类型、情感基调、想要的爽点。
每次最多问2个问题，聊天式交流，语气亲切自然。
当信息已足够时，在回复末尾单独一行写：READY"""
    return sse_stream(system, body.get("messages", []), max_tokens=600)


@app.post("/api/worldbuilding")
async def worldbuilding(req: Request):
    body = await req.json()
    prompt = WORLDBUILDING_PROMPT.format(requirements=body.get("requirements", ""))
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
    body     = await req.json()
    ol_text  = body.get("outline", "")
    ep_num   = body.get("episode_num", 1)
    ep_list  = extract_episode_outlines(ol_text)
    ep_ol    = ep_list[ep_num - 1] if ep_num <= len(ep_list) else f"第{ep_num}集"
    wpm      = 200
    prompt   = EPISODE_PROMPT.format(
        episode_num=ep_num, outline=ol_text, episode_outline=ep_ol,
        duration_min=1, duration_max=3, word_count_min=wpm, word_count_max=3 * wpm,
    )
    return sse_stream(EPISODE_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=3000)


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
    return {
        "id":           row["id"],
        "title":        row.get("title", "未命名"),
        "phase":        row.get("phase", "chat"),
        "requirements": row.get("requirements") or "",
        "worldbuilding":row.get("worldbuilding") or "",
        "outline":      row.get("outline") or "",
        "episodeCount": row.get("episode_count", 15),
        "episodesDone": row.get("episodes_done", 0),
        "messages":     row.get("messages") or [],
        "episodes":     row.get("episodes") or {},
        "characters":   row.get("characters") or [],
        "created":      row.get("created", ""),
        "updated":      row.get("updated", ""),
    }


def _load_proj(pid: str) -> dict:
    res = db.table("projects").select("*").eq("id", pid).maybe_single().execute()
    if not res.data:
        raise HTTPException(404, "项目不存在")
    return _row_to_proj(res.data)


def _save_proj(data: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    pid = data.get("id") or datetime.now().strftime("%Y%m%d_%H%M%S")
    episodes_done = len(data.get("episodes", {}))
    db.table("projects").upsert({
        "id":            pid,
        "title":         data.get("title", "未命名"),
        "phase":         data.get("phase", "chat"),
        "requirements":  data.get("requirements", ""),
        "worldbuilding": data.get("worldbuilding", ""),
        "outline":       data.get("outline", ""),
        "episode_count": data.get("episodeCount", 15),
        "episodes_done": episodes_done,
        "messages":      data.get("messages", []),
        "episodes":      data.get("episodes", {}),
        "characters":    data.get("characters", []),
        "created":       data.get("created") or now,
        "updated":       now,
    }).execute()
    return pid


@app.post("/api/project")
async def project_save(req: Request):
    body = await req.json()
    pid  = _save_proj(body)
    return {"id": pid}


@app.get("/api/projects")
async def projects_list():
    res = db.table("projects").select(
        "id,title,phase,episode_count,episodes_done,created,updated"
    ).order("updated", desc=True).execute()
    return JSONResponse([{
        "id":           r["id"],
        "title":        r.get("title", "未命名"),
        "phase":        r.get("phase", "chat"),
        "updated":      r.get("updated", ""),
        "created":      r.get("created", ""),
        "episodeCount": r.get("episode_count", 0),
        "episodesDone": r.get("episodes_done", 0),
    } for r in (res.data or [])])


@app.get("/api/project/{pid}")
async def project_load(pid: str):
    return JSONResponse(_load_proj(pid))


@app.patch("/api/project/{pid}")
async def project_patch(pid: str, req: Request):
    body  = await req.json()
    field = body.get("field")
    now   = datetime.now().strftime("%Y-%m-%d %H:%M")

    if field == "worldbuilding":
        db.table("projects").update({"worldbuilding": body["content"], "updated": now}).eq("id", pid).execute()
    elif field == "outline":
        db.table("projects").update({"outline": body["content"], "updated": now}).eq("id", pid).execute()
    elif field == "episode":
        res = db.table("projects").select("episodes").eq("id", pid).maybe_single().execute()
        if not res.data:
            raise HTTPException(404, "项目不存在")
        episodes = res.data.get("episodes") or {}
        episodes[str(body["num"])] = body["content"]
        db.table("projects").update({
            "episodes":      episodes,
            "episodes_done": len(episodes),
            "updated":       now,
        }).eq("id", pid).execute()
    elif field == "chat":
        db.table("projects").update({"messages": body["messages"], "updated": now}).eq("id", pid).execute()
    elif field == "characters":
        db.table("projects").update({
            "characters": body["characters"], "updated": now,
        }).eq("id", pid).execute()
    else:
        raise HTTPException(400, f"未知 field: {field}")
    return {"ok": True}


@app.delete("/api/project/{pid}")
async def project_delete(pid: str):
    db.table("projects").delete().eq("id", pid).execute()
    return {"ok": True}


# ── Characters ───────────────────────────────────────────────────────────────

def _extract_json_array(raw: str) -> list:
    """Strip markdown fences and extract the outermost JSON array."""
    raw = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
    raw = re.sub(r'```\s*$', '', raw.strip(), flags=re.MULTILINE).strip()
    m = re.search(r'\[[\s\S]*\]', raw)
    return json.loads(m.group(0) if m else raw)


@app.post("/api/project/{pid}/extract-characters")
async def extract_characters(pid: str, req: Request):
    body = await req.json()
    worldbuilding = body.get("worldbuilding", "")
    prompt = CHARACTER_EXTRACT_PROMPT.format(worldbuilding=worldbuilding)
    resp = client.chat.completions.create(
        model=MODEL, max_tokens=1500, stream=False,
        messages=[
            {"role": "system", "content": CHARACTER_EXTRACT_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    characters = _extract_json_array(raw)
    return JSONResponse(characters)


@app.post("/api/project/{pid}/characters/{cid}/upload-image")
async def upload_character_image(pid: str, cid: str, file: UploadFile = File(...)):
    data = await file.read()
    path = f"{pid}/{cid}.webp"
    db.storage.from_("character-images").upload(
        path, data,
        file_options={"content-type": "image/webp", "upsert": "true"},
    )
    url = db.storage.from_("character-images").get_public_url(path)
    return {"url": url}


@app.post("/api/project/{pid}/characters/{cid}/generate-image")
async def generate_character_image(pid: str, cid: str, req: Request):
    body = await req.json()
    appearance = body.get("appearance", "神秘人物")
    model = body.get("model", "wan2.1-t2i-turbo")
    custom_prompt = (body.get("prompt") or "").strip()
    prompt_text = custom_prompt if custom_prompt else (
        f"{appearance}，古装写实风格，人物设定图，全身正面站立，"
        "精致五官，华丽古装服饰，衣袂飘逸，细腻笔触，简洁渐变背景，高清插画"
    )

    def _generate_sync() -> str:
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

    image_url = await asyncio.to_thread(_generate_sync)

    async with httpx.AsyncClient(timeout=60) as hc:
        img_data = (await hc.get(image_url)).content

    path = f"{pid}/{cid}.webp"
    db.storage.from_("character-images").upload(
        path, img_data,
        file_options={"content-type": "image/webp", "upsert": "true"},
    )
    public_url = db.storage.from_("character-images").get_public_url(path)
    return {"url": public_url}


# ── Export ────────────────────────────────────────────────────────────────────

@app.post("/api/export/{pid}")
async def project_export(pid: str):
    data     = _load_proj(pid)
    episodes = [data["episodes"][str(k)] for k in sorted(int(x) for x in data.get("episodes", {}))]
    Path(EXPORT_DIR).mkdir(exist_ok=True)
    path = save_full_script(data.get("outline", ""), episodes, EXPORT_DIR)
    return {"path": path}
