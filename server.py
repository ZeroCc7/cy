#!/usr/bin/env python3
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from openai import OpenAI
from exporter import save_full_script, extract_episode_outlines
from prompts import (OUTLINE_SYSTEM, OUTLINE_PROMPT, EPISODE_SYSTEM, EPISODE_PROMPT,
                     REFINE_PROMPT, WORLDBUILDING_SYSTEM, WORLDBUILDING_PROMPT)

load_dotenv()

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_BASE_URL"],
)
MODEL        = os.environ["OPENAI_MODEL_ID"]
PROJECT_DIR  = "./projects"
EXPORT_DIR   = "./scripts"

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

def _proj_path(pid: str) -> Path:
    if ".." in pid or "/" in pid:
        raise HTTPException(400, "非法项目ID")
    return Path(PROJECT_DIR) / f"{pid}.json"


def _load_proj(pid: str) -> dict:
    p = _proj_path(pid)
    if not p.exists():
        raise HTTPException(404, "项目不存在")
    return json.loads(p.read_text(encoding="utf-8"))


def _save_proj(data: dict) -> str:
    Path(PROJECT_DIR).mkdir(exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    pid = data.get("id") or datetime.now().strftime("%Y%m%d_%H%M%S")
    data["id"] = pid
    data.setdefault("created", now)
    data["updated"] = now
    data["episodesDone"] = len(data.get("episodes", {}))
    _proj_path(pid).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return pid


@app.post("/api/project")
async def project_save(req: Request):
    """全量保存（创作流程中调用）。"""
    body = await req.json()
    pid  = _save_proj(body)
    return {"id": pid}


@app.get("/api/projects")
async def projects_list():
    """返回所有项目的摘要（不含 messages/episodes 内容）。"""
    d = Path(PROJECT_DIR)
    if not d.exists():
        return JSONResponse([])
    result = []
    for f in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            result.append({
                "id":           data["id"],
                "title":        data.get("title", "未命名"),
                "phase":        data.get("phase", "chat"),
                "updated":      data.get("updated", ""),
                "created":      data.get("created", ""),
                "episodeCount": data.get("episodeCount", 0),
                "episodesDone": len(data.get("episodes", {})),
            })
        except Exception:
            pass
    return JSONResponse(result)


@app.get("/api/project/{pid}")
async def project_load(pid: str):
    """加载完整项目（含 messages/episodes）。"""
    return JSONResponse(_load_proj(pid))


@app.patch("/api/project/{pid}")
async def project_patch(pid: str, req: Request):
    """局部更新：修改世界观/大纲/某集/对话记录。"""
    data  = _load_proj(pid)
    body  = await req.json()
    field = body.get("field")
    if field == "worldbuilding":
        data["worldbuilding"] = body["content"]
    elif field == "outline":
        data["outline"] = body["content"]
    elif field == "episode":
        data.setdefault("episodes", {})[str(body["num"])] = body["content"]
        data["episodesDone"] = len(data["episodes"])
    elif field == "chat":
        data["messages"] = body["messages"]
    else:
        raise HTTPException(400, f"未知 field: {field}")
    _save_proj(data)
    return {"ok": True}


# ── Export ────────────────────────────────────────────────────────────────────

@app.post("/api/export/{pid}")
async def project_export(pid: str):
    """将项目内容导出为 scripts/ 下的 Markdown 文件。"""
    data     = _load_proj(pid)
    episodes = [data["episodes"][str(k)] for k in sorted(int(x) for x in data.get("episodes", {}))]
    Path(EXPORT_DIR).mkdir(exist_ok=True)
    path = save_full_script(data.get("outline", ""), episodes, EXPORT_DIR)
    return {"path": path}
