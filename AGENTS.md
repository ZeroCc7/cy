# 幕启 Script Studio — Project Guide

## Stack

- **Frontend**: Vanilla JS (`app.js`) + CSS (`styles.css`) — no build step, no framework
- **Backend**: FastAPI (`server.py`) + Supabase (PostgreSQL)
- **AI**: OpenAI-compatible SSE streaming via `sse_stream(system, messages, max_tokens)`

---

## 6-Step Flow

| Step | Phase key | Title |
|------|-----------|-------|
| 1 | `chat` | 作品需求 |
| 2 | `outline` | 故事大纲 |
| 3 | `worldbuilding` | 世界观 |
| 4 | `characters` | 角色设定 |
| 5 | `planning` | 分集规划 |
| 6 | `scripts` | 正文创作 |

`phaseToStep` / `stepToPhase` map between DB phase strings and step numbers.

---

## AI Step Panel Pattern

**Every step with AI generation uses this layout and interaction model.** Replicate it exactly for new steps.

### Layout: Left content + Right chat (split)

```
┌─ wb-layout (grid: 1fr 320px) ────────────────────────────┐
│  ┌─ left panel (panel panel-pad) ──┐  ┌─ right chat ───┐ │
│  │ Content display or editor       │  │ AI chat panel  │ │
│  │ [预览 / 编辑] toggle            │  │ (sticky top)   │ │
│  └─────────────────────────────────┘  └────────────────┘ │
└───────────────────────────────────────────────────────────┘
```

- Right panel: `position: sticky; top: 16px` — stays in view while left scrolls
- Right panel height: `height: calc(100vh - 200px); min-height: 480px`
- Messages area: `flex: 1; overflow-y: auto; min-height: 0`
- Input textarea: `min-height: 80px; max-height: 200px`

### Chat interaction flow (3 phases)

1. **Discuss** — user types → `send-{step}-chat` → POST `/api/refine-{step}` (SSE streaming)
   - AI responds in character, gives suggestions
   - When satisfied, AI appends signal on its own line: `{STEP}_READY` (e.g. `WB_READY`)
   - Frontend detects signal → strips it → sets `script._${step}RefineReady = true` → confirm button glows

2. **Confirm** — user clicks "确认，重新生成" → `apply-{step}-refine` → `runGeneration("{step}-refine-apply")`

3. **Apply** — POST `/api/apply-{step}-refine` (SSE streaming) → `applyGeneratedResult("{step}-refine-apply", ...)` → replaces content, clears conversation

### Server endpoints for each step

```python
# Conversation endpoint — discuss changes
@app.post("/api/refine-{step}")
async def refine_{step}(req):
    # system: role + current content as context + ready signal instruction
    # signal: "如果用户满意，在回复末尾单独一行写：{STEP}_READY"
    return sse_stream(system, messages, max_tokens=1000)

# Apply endpoint — generate full new content
@app.post("/api/apply-{step}-refine")  
async def apply_{step}_refine(req):
    # system: generate complete updated content based on original + conversation
    # prompt: 【原始内容】 + 【讨论记录】
    return sse_stream(system, [{"role":"user","content":prompt}], max_tokens=3000)
```

### Frontend functions for each step

```js
// Conversation streaming
async function gen{Step}Chat(script, runId) { /* POST /api/refine-{step}, SSE, detect {STEP}_READY */ }

// Apply streaming  
async function gen{Step}RefineApply(script, runId) { /* POST /api/apply-{step}-refine, SSE */ }

// Scroll helper
function scroll{Step}ToBottom() { /* getElementById("{step}-msgs").scrollTop = scrollHeight */ }
```

### Script fields per step

Each step adds to `createBlankScript()` and `serverProjectToScript()`:
```js
{step}Conversation: [],   // chat history [{id, role: "user"|"ai", content}]
_{step}RefineReady: false, // true when AI signals satisfaction
```

### applyGeneratedResult cases

```js
if (kind === "{step}-refine-apply") {
  script.{field} = data;          // replace content
  script._{step}RefineReady = false;
  script.{step}Conversation = []; // clear chat
  // do NOT advance currentStep here
  persist(); toast("已更新。");
}
```

---

## Generation System

### runGeneration(kind)

Central dispatcher. Add each new kind:
```js
else if (kind === "{step}-refine-apply") await gen{Step}RefineApply(script, runId);
```

### generationMeta(kind)

Add loading overlay text:
```js
"{step}-refine-apply": { title: "AI 正在重新生成…", subtitle: "…" },
```

### SSE Pattern

All streaming functions follow the same structure:
```js
while (true) {
  if (runId !== generationRun) { reader.cancel(); return; } // stale check
  const { done, value } = await reader.read();
  if (done) break;
  // parse "data: {...}" lines
  // evt.type === "chunk" → append to state.generation.text, render()
  // evt.type === "done"  → applyGeneratedResult(), state.generation = null, persist(), render()
}
```

For conversation streaming (not apply), push `aiMsg` to `script.{step}Conversation` on done.

---

## Markdown Rendering

- `renderMd(text)` wraps `marked.parse()` — use for all AI-generated content
- User-typed content: always `escapeHtml()`
- Add `class="md-content"` to any div using `renderMd()`
- `white-space: normal` is set for `.md-content` (overrides `pre-line`)

---

## Persistence

- `persist()` — immediate save (use after AI generation completes)
- `scheduleSave()` — 650ms debounce (use after user edits)
- `syncToServer(script)` — called inside `persist()` when `_serverLoaded`

---

## CSS Conventions

- Step split layout class: `.{step}-layout` → `grid: 1fr 320px`
- Left panel: `.{step}-main`
- Right chat wrapper: `.{step}-chat-panel` (sticky)
- Inner chat box: `.{step}-chat-inner` (fixed height flex column)
- Messages list: `.{step}-msgs` (flex: 1, overflow-y: auto)
- Reuse: `.chat-bubble`, `.chat-avatar`, `.chat-input-row`, `.chat-send-btn`, `.refine-apply-btn`
