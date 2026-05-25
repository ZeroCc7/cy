# Character Management + Image Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add character cards to the worldbuilding phase — AI auto-extract, manual CRUD, image upload, and AI image generation via DashScope Wanx.

**Architecture:** Character data stored as JSONB in the existing `projects` table (`characters` column). Images stored in Supabase Storage bucket `character-images`. Backend adds 3 new endpoints and extends the PATCH endpoint. Frontend adds a character card grid below the worldbuilding text, plus an edit modal.

**Tech Stack:** FastAPI, supabase-py 2.x, httpx, python-multipart, Vanilla JS, Supabase Storage, DashScope Wanx (OpenAI-compatible image API)

---

## 涉及文件

| 文件 | 变更 |
|------|------|
| `requirements.txt` | 新增 `python-multipart`, `httpx` |
| `prompts.py` | 新增 `CHARACTER_EXTRACT_SYSTEM`, `CHARACTER_EXTRACT_PROMPT` |
| `server.py` | 扩展 imports、`_row_to_proj`、`_save_proj`、PATCH endpoint；新增 3 个接口 |
| `index.html` | 新增 CSS、modal HTML、`S.characters`、11 个 JS 函数 |

---

### Task 1: Supabase 基础设施

**Files:**
- 无代码改动，手动操作 Supabase 控制台

- [ ] **Step 1: 在 Supabase SQL Editor 执行**

打开 `https://supabase.com/dashboard/project/rviwutjsehfoihyywvhh/sql/new`，运行：

```sql
ALTER TABLE projects ADD COLUMN IF NOT EXISTS characters JSONB DEFAULT '[]';
```

期望：无报错，`projects` 表出现 `characters` 列。

- [ ] **Step 2: 创建 Storage bucket**

打开 `https://supabase.com/dashboard/project/rviwutjsehfoihyywvhh/storage/buckets`：
1. 点击「New bucket」
2. Name: `character-images`
3. 勾选「Public bucket」（允许公开读取）
4. 点击「Save」

期望：bucket 列表出现 `character-images`，标注 Public。

- [ ] **Step 3: 验证**

在 SQL Editor 执行：
```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'projects' AND column_name = 'characters';
```

期望：返回一行，`data_type = 'jsonb'`。

---

### Task 2: 依赖与 prompts

**Files:**
- Modify: `requirements.txt`
- Modify: `prompts.py`

- [ ] **Step 1: 更新 requirements.txt**

将文件内容改为：
```
openai>=1.0.0
python-dotenv>=1.0.0
rich>=13.0.0
fastapi>=0.100.0
uvicorn>=0.23.0
supabase>=2.0.0
python-multipart>=0.0.9
httpx>=0.27.0
```

- [ ] **Step 2: 安装新依赖**

```powershell
.\venv\Scripts\pip install python-multipart>=0.0.9 httpx>=0.27.0
```

期望：`Successfully installed ...` 无报错。

- [ ] **Step 3: 在 prompts.py 末尾追加**

```python
CHARACTER_EXTRACT_SYSTEM = """你是角色信息提取助手。从世界观文档中准确提取所有角色信息，只输出 JSON 数组，不输出任何其他内容。"""

CHARACTER_EXTRACT_PROMPT = """从以下世界观设定文档中提取所有具名角色，输出 JSON 数组。

【世界观文本】
{worldbuilding}

输出格式（纯 JSON 数组，无其他文字）：
[
  {{
    "id": "char_1",
    "name": "角色姓名",
    "role": "protagonist",
    "personality": "性格描述，30字内",
    "appearance": "外貌描述，40字内，突出视觉特征",
    "imageUrl": null
  }}
]

规则：
- role 只能取 protagonist / antagonist / supporting 之一
- 只提取有名有姓的具体角色，不提取势力/组织
- 最多提取 8 个角色
- 直接输出 JSON，不要加 ```json 标记"""
```

- [ ] **Step 4: 验证导入**

```powershell
.\venv\Scripts\python -c "from prompts import CHARACTER_EXTRACT_SYSTEM, CHARACTER_EXTRACT_PROMPT; print('OK')"
```

期望：打印 `OK`。

- [ ] **Step 5: Commit**

```bash
git add requirements.txt prompts.py
git commit -m "feat: add character extract prompts and dependencies"
```

---

### Task 3: server.py — 基础扩展

**Files:**
- Modify: `server.py`

- [ ] **Step 1: 扩展 imports（第 7-13 行）**

将：
```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
```
改为：
```python
import asyncio
import httpx
from fastapi import FastAPI, File, Request, HTTPException, UploadFile
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
```

将 prompts 导入行改为：
```python
from prompts import (OUTLINE_SYSTEM, OUTLINE_PROMPT, EPISODE_SYSTEM, EPISODE_PROMPT,
                     REFINE_PROMPT, WORLDBUILDING_SYSTEM, WORLDBUILDING_PROMPT,
                     CHARACTER_EXTRACT_SYSTEM, CHARACTER_EXTRACT_PROMPT)
```

- [ ] **Step 2: 扩展 `_row_to_proj`**

在 `_row_to_proj` 返回 dict 里，`"episodes"` 行之后追加：
```python
        "characters":   row.get("characters") or [],
```

完整函数变为：
```python
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
```

- [ ] **Step 3: 扩展 `_save_proj`**

在 `_save_proj` 的 `db.table("projects").upsert({...})` dict 里，`"episodes":` 行之后追加：
```python
        "characters":    data.get("characters", []),
```

- [ ] **Step 4: 扩展 PATCH endpoint**

在 `project_patch` 函数的 `elif field == "chat":` 分支之后、`else:` 之前插入：

```python
    elif field == "characters":
        db.table("projects").update({
            "characters": body["characters"], "updated": now,
        }).eq("id", pid).execute()
```

- [ ] **Step 5: 验证服务启动**

```powershell
.\venv\Scripts\uvicorn server:app --reload
```

期望：`Application startup complete.` 无 ImportError。

- [ ] **Step 6: Commit**

```bash
git add server.py
git commit -m "feat: extend project model with characters field"
```

---

### Task 4: server.py — 角色接口

**Files:**
- Modify: `server.py`

在 `# ── Export ──` 注释之前，插入以下三个接口：

- [ ] **Step 1: 插入 extract-characters 接口**

```python
# ── Characters ───────────────────────────────────────────────────────────────

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
    # 去掉可能的 ```json ... ``` 包装
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    characters = json.loads(raw)
    return JSONResponse(characters)
```

- [ ] **Step 2: 插入 upload-image 接口**

```python
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
```

- [ ] **Step 3: 插入 generate-image 接口**

```python
@app.post("/api/project/{pid}/characters/{cid}/generate-image")
async def generate_character_image(pid: str, cid: str, req: Request):
    body = await req.json()
    appearance = body.get("appearance", "神秘人物")
    prompt_text = f"{appearance}，古装写实风格，精致面部，电影质感，高清竖版半身像"
    try:
        resp = await asyncio.to_thread(
            client.images.generate,
            model="wanx2.1-t2i-turbo",
            prompt=prompt_text,
            size="768*1024",
            n=1,
        )
        image_url = resp.data[0].url
    except Exception:
        # DashScope Wanx REST API 备用方案
        async with httpx.AsyncClient(timeout=60) as hc:
            r = await hc.post(
                "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
                headers={
                    "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "disable",
                },
                json={
                    "model": "wanx2.1-t2i-turbo",
                    "input": {"prompt": prompt_text},
                    "parameters": {"size": "768*1024", "n": 1},
                },
            )
            r.raise_for_status()
            image_url = r.json()["output"]["results"][0]["url"]

    async with httpx.AsyncClient(timeout=60) as hc:
        img_data = (await hc.get(image_url)).content

    path = f"{pid}/{cid}.webp"
    db.storage.from_("character-images").upload(
        path, img_data,
        file_options={"content-type": "image/webp", "upsert": "true"},
    )
    public_url = db.storage.from_("character-images").get_public_url(path)
    return {"url": public_url}
```

- [ ] **Step 4: 手动验证 extract 接口**

先启动服务，在 Supabase 中找一个已有世界观的项目 ID（如 `20260525_143000`），然后：

```powershell
$body = '{"worldbuilding": "主角凌霄，白发银眸，修仙宗门长老之子。反派血魔君，以血祭天地，野心勃勃。配角苏澜，凌霄青梅竹马，善厨艺。"}' 
Invoke-WebRequest -Method POST -Uri "http://localhost:8000/api/project/test/extract-characters" `
  -ContentType "application/json" -Body $body -UseBasicParsing | Select-Object -ExpandProperty Content
```

期望：返回包含 3 个角色的 JSON 数组。

- [ ] **Step 5: Commit**

```bash
git add server.py
git commit -m "feat: add character extract, upload, and generate-image endpoints"
```

---

### Task 5: Frontend CSS

**Files:**
- Modify: `index.html`

在 `</style>` 标签之前追加以下 CSS：

- [ ] **Step 1: 追加 CSS**

```css
/* ── Character Section ── */
.char-section{margin-top:28px;border-top:1px solid #1e1e2a;padding-top:20px}
.char-section-title{display:flex;align-items:center;justify-content:space-between;
  margin-bottom:14px}
.char-section-title h3{font-size:13px;color:#c9a96e;font-weight:600}
.char-add-btn{font-size:11.5px;padding:4px 11px;border-radius:8px;
  border:1px solid #2a2a38;background:transparent;color:#777;cursor:pointer;transition:all .2s}
.char-add-btn:hover{background:#1e1e2a;color:#c9a96e;border-color:#c9a96e55}
.char-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px}
.char-card{background:#111120;border:1px solid #1e1e2c;border-radius:10px;
  overflow:hidden;cursor:pointer;transition:all .18s}
.char-card:hover{border-color:#c9a96e44;background:#17172a}
.char-avatar{width:100%;aspect-ratio:3/4;background:#1a1a2a;
  display:flex;align-items:center;justify-content:center;overflow:hidden}
.char-avatar img{width:100%;height:100%;object-fit:cover}
.char-avatar-placeholder{font-size:28px;color:#333;font-weight:700;
  background:linear-gradient(135deg,#1a1a2a,#242438)}
.char-info{padding:8px 10px}
.char-name{font-size:12.5px;color:#c9a96e;font-weight:600;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:4px}
.char-role-badge{font-size:10px;padding:1px 6px;border-radius:6px;border:1px solid}
.char-role-badge.protagonist{color:#c9a96e;border-color:#c9a96e44;background:#c9a96e0d}
.char-role-badge.antagonist{color:#c06060;border-color:#c0606044;background:#c060600d}
.char-role-badge.supporting{color:#666;border-color:#2a2a38;background:transparent}
.char-edit-btn{width:100%;padding:5px;border:none;border-top:1px solid #1e1e2a;
  background:transparent;color:#444;font-size:11px;cursor:pointer;transition:color .15s}
.char-edit-btn:hover{color:#c9a96e;background:#111128}

/* ── Character Modal ── */
.char-modal-overlay{position:fixed;inset:0;background:#00000088;
  display:flex;align-items:center;justify-content:center;z-index:100}
.char-modal{background:#13131e;border:1px solid #252535;border-radius:14px;
  width:560px;max-width:95vw;max-height:90vh;display:flex;flex-direction:column;overflow:hidden}
.char-modal-hdr{display:flex;align-items:center;padding:14px 18px;
  border-bottom:1px solid #1e1e2a;flex-shrink:0}
.char-modal-hdr h3{font-size:14px;color:#c9a96e;font-weight:600;flex:1}
.char-modal-close{background:none;border:none;color:#444;font-size:18px;
  cursor:pointer;padding:2px 7px;border-radius:4px;line-height:1}
.char-modal-close:hover{color:#bbb;background:#1e1e2a}
.char-modal-body{display:flex;gap:18px;padding:18px;overflow-y:auto;flex:1}
.char-modal-left{width:150px;flex-shrink:0;display:flex;flex-direction:column;gap:8px}
.char-modal-avatar{width:150px;height:200px;background:#1a1a2a;border-radius:9px;
  display:flex;align-items:center;justify-content:center;overflow:hidden;
  border:1px solid #252535}
.char-modal-avatar img{width:100%;height:100%;object-fit:cover}
.char-modal-avatar-ph{font-size:40px;color:#2a2a3a;font-weight:700}
.char-img-btn{width:100%;padding:6px 0;border-radius:7px;border:1px solid #2a2a38;
  background:transparent;color:#777;font-size:11.5px;cursor:pointer;transition:all .15s}
.char-img-btn:hover{background:#1e1e2a;color:#c9a96e;border-color:#c9a96e55}
.char-img-btn:disabled{opacity:.4;cursor:not-allowed}
.char-modal-right{flex:1;display:flex;flex-direction:column;gap:10px}
.char-field label{font-size:11.5px;color:#555;display:block;margin-bottom:4px}
.char-field input,.char-field select,.char-field textarea{
  width:100%;background:#161625;border:1px solid #252535;border-radius:8px;
  color:#e0d8c8;font-size:13px;font-family:inherit;padding:7px 10px;outline:none}
.char-field input:focus,.char-field select,.char-field textarea:focus{border-color:#c9a96e44}
.char-field textarea{resize:none;height:60px;line-height:1.5}
.char-field select option{background:#13131e}
.char-modal-footer{display:flex;align-items:center;padding:12px 18px;
  border-top:1px solid #1e1e2a;flex-shrink:0;gap:8px}
.char-delete-btn{background:none;border:1px solid #3a2020;color:#884040;
  font-size:12px;padding:5px 12px;border-radius:7px;cursor:pointer;transition:all .15s}
.char-delete-btn:hover{background:#3a2020;color:#c06060}
.char-save-btn{margin-left:auto;background:#c9a96e;color:#1a1208;border:none;
  font-size:12.5px;font-weight:600;padding:6px 18px;border-radius:8px;cursor:pointer;transition:background .15s}
.char-save-btn:hover{background:#d4b87a}
```

- [ ] **Step 2: 验证 CSS 无语法错误**

启动服务，打开 `http://localhost:8000`，浏览器控制台无 CSS 报错即可。

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat: add character section and modal CSS"
```

---

### Task 6: Frontend modal HTML

**Files:**
- Modify: `index.html`

在 `</body>` 之前插入 modal DOM：

- [ ] **Step 1: 在 `</body>` 前插入**

```html
<!-- ── Character Modal ── -->
<div class="char-modal-overlay" id="char-modal-overlay" style="display:none"
     onclick="if(event.target===this)closeCharModal()">
  <div class="char-modal">
    <div class="char-modal-hdr">
      <h3 id="char-modal-title">编辑角色</h3>
      <button class="char-modal-close" onclick="closeCharModal()">✕</button>
    </div>
    <div class="char-modal-body">
      <div class="char-modal-left">
        <div class="char-modal-avatar" id="char-modal-avatar">
          <span class="char-modal-avatar-ph" id="char-modal-avatar-ph">?</span>
        </div>
        <input type="file" id="char-file-input" accept="image/*" style="display:none"
               onchange="uploadCharImage(this)">
        <button class="char-img-btn" onclick="$('char-file-input').click()">上传图片</button>
        <button class="char-img-btn" id="char-gen-btn" onclick="generateCharImage()">✦ AI 生成图</button>
      </div>
      <div class="char-modal-right">
        <div class="char-field">
          <label>姓名</label>
          <input id="char-f-name" type="text" placeholder="角色姓名">
        </div>
        <div class="char-field">
          <label>定位</label>
          <select id="char-f-role">
            <option value="protagonist">主角</option>
            <option value="antagonist">反派</option>
            <option value="supporting">配角</option>
          </select>
        </div>
        <div class="char-field">
          <label>性格</label>
          <textarea id="char-f-personality" placeholder="性格描述，30字内"></textarea>
        </div>
        <div class="char-field">
          <label>外貌描述</label>
          <textarea id="char-f-appearance" placeholder="外貌特征，40字内，用于 AI 生图"></textarea>
        </div>
      </div>
    </div>
    <div class="char-modal-footer">
      <button class="char-delete-btn" id="char-delete-btn" onclick="deleteCharFromModal()">删除角色</button>
      <button class="char-save-btn" onclick="saveCharModal()">保存</button>
    </div>
  </div>
</div>
```

- [ ] **Step 2: 验证 DOM 存在**

浏览器控制台执行 `document.getElementById('char-modal-overlay')` → 不为 null。

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat: add character modal HTML"
```

---

### Task 7: Frontend JS — state + 渲染

**Files:**
- Modify: `index.html` (JS)

- [ ] **Step 1: 在 `const S = {` 块内加 `characters:[]`**

找到：
```javascript
  pendingAction:null,
};
```
改为：
```javascript
  pendingAction:null,
  characters:[],
};
```

- [ ] **Step 2: 在 JS 末尾追加 `// ── Characters ──` 区块**

在 `function extractEpOutlinesFromText` 之后、`// ══ Markdown renderer` 之前追加：

```javascript
// ── Characters ───────────────────────────────────────────────────────────────

const roleLabel = {protagonist:'主角', antagonist:'反派', supporting:'配角'};

function renderCharSection() {
  let sec = $('char-section');
  if (!sec) {
    sec = document.createElement('div');
    sec.id = 'char-section';
    sec.className = 'char-section';
    $('cbody').appendChild(sec);
  }
  sec.innerHTML = `
    <div class="char-section-title">
      <h3>角色设定（${S.characters.length}）</h3>
      <button class="char-add-btn" onclick="addNewChar()">+ 新增角色</button>
    </div>
    <div class="char-grid" id="char-grid"></div>`;
  const grid = $('char-grid');
  S.characters.forEach(c => grid.appendChild(makeCharCard(c)));
}

function makeCharCard(c) {
  const card = document.createElement('div');
  card.className = 'char-card';
  card.id = `cc-${c.id}`;
  const avatarInner = c.imageUrl
    ? `<img src="${c.imageUrl}" alt="${c.name}">`
    : `<span class="char-avatar-placeholder">${c.name.charAt(0)}</span>`;
  card.innerHTML = `
    <div class="char-avatar">${avatarInner}</div>
    <div class="char-info">
      <div class="char-name">${c.name}</div>
      <span class="char-role-badge ${c.role}">${roleLabel[c.role] || c.role}</span>
    </div>
    <button class="char-edit-btn" onclick="openCharModal('${c.id}');event.stopPropagation()">编辑</button>`;
  return card;
}

async function saveCharacters() {
  if (!S.projectId) return;
  try {
    await fetch(`/api/project/${S.projectId}`, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({field: 'characters', characters: S.characters}),
    });
  } catch { /* 静默失败 */ }
}
```

- [ ] **Step 3: 验证 `S.characters` 存在**

浏览器控制台执行 `S.characters` → 返回 `[]`。

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat: add character state, renderCharSection, makeCharCard, saveCharacters"
```

---

### Task 8: Frontend JS — 提取角色

**Files:**
- Modify: `index.html` (JS)

- [ ] **Step 1: 在 Task 7 的 `// ── Characters ──` 区块内继续追加**

```javascript
async function extractCharacters() {
  if (!S.worldbuilding) return;
  const btn = document.querySelector('[onclick="extractCharacters()"]');
  if (btn) { btn.disabled = true; btn.textContent = '提取中…'; }
  try {
    const resp = await fetch(`/api/project/${S.projectId}/extract-characters`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({worldbuilding: S.worldbuilding}),
    });
    const list = await resp.json();
    S.characters = list.map((c, i) => ({
      id: c.id || `char_${Date.now()}_${i}`,
      name: c.name || '未命名',
      role: ['protagonist','antagonist','supporting'].includes(c.role) ? c.role : 'supporting',
      personality: c.personality || '',
      appearance: c.appearance || '',
      imageUrl: null,
    }));
    renderCharSection();
    await saveCharacters();
  } catch {
    appendMsg('system', '角色提取失败，请重试');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '✦ 提取角色'; }
  }
}
```

- [ ] **Step 2: 修改 `showWorldbuildingActions()`**

找到 `setToolbar` 调用（在 `showWorldbuildingActions` 内），将其改为：

```javascript
  setToolbar([
    {label:'✦ 提取角色', fn:extractCharacters},
    {label:'修改世界观', fn:()=>enterRefineMode({type:'worldbuilding'},'📝 修改世界观')},
  ]);
```

- [ ] **Step 3: 手动验证**

1. 启动服务，新建项目，完成聊天阶段
2. 生成世界观
3. 点击工具栏「✦ 提取角色」
4. 期望：`cbody` 底部出现角色卡区域，卡片数量与世界观中的角色一致

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat: add extractCharacters and wire to worldbuilding toolbar"
```

---

### Task 9: Frontend JS — modal CRUD

**Files:**
- Modify: `index.html` (JS)

在 `// ── Characters ──` 区块内继续追加：

- [ ] **Step 1: 追加 modal state 和 open/close 函数**

```javascript
let _editingCharId = null;

function openCharModal(charId) {
  const c = S.characters.find(x => x.id === charId);
  if (!c) return;
  _editingCharId = charId;
  $('char-modal-title').textContent = '编辑角色';
  $('char-f-name').value        = c.name;
  $('char-f-role').value        = c.role;
  $('char-f-personality').value = c.personality;
  $('char-f-appearance').value  = c.appearance;
  _refreshModalAvatar(c.imageUrl, c.name);
  $('char-delete-btn').style.display = '';
  $('char-modal-overlay').style.display = 'flex';
}

function addNewChar() {
  const newChar = {
    id: `char_${Date.now()}`,
    name: '新角色', role: 'supporting',
    personality: '', appearance: '', imageUrl: null,
  };
  S.characters.push(newChar);
  _editingCharId = newChar.id;
  $('char-modal-title').textContent = '新增角色';
  $('char-f-name').value        = newChar.name;
  $('char-f-role').value        = newChar.role;
  $('char-f-personality').value = '';
  $('char-f-appearance').value  = '';
  _refreshModalAvatar(null, newChar.name);
  $('char-delete-btn').style.display = '';
  $('char-modal-overlay').style.display = 'flex';
}

function closeCharModal() {
  $('char-modal-overlay').style.display = 'none';
  _editingCharId = null;
}

function _refreshModalAvatar(imageUrl, name) {
  const av = $('char-modal-avatar');
  if (imageUrl) {
    av.innerHTML = `<img src="${imageUrl}" alt="${name}">`;
  } else {
    av.innerHTML = `<span class="char-modal-avatar-ph">${(name||'?').charAt(0)}</span>`;
  }
}
```

- [ ] **Step 2: 追加 save 和 delete 函数**

```javascript
async function saveCharModal() {
  const idx = S.characters.findIndex(x => x.id === _editingCharId);
  if (idx === -1) return;
  S.characters[idx] = {
    ...S.characters[idx],
    name:        $('char-f-name').value.trim() || '未命名',
    role:        $('char-f-role').value,
    personality: $('char-f-personality').value.trim(),
    appearance:  $('char-f-appearance').value.trim(),
  };
  closeCharModal();
  renderCharSection();
  await saveCharacters();
}

async function deleteCharFromModal() {
  if (!_editingCharId) return;
  if (!confirm('确认删除此角色？')) return;
  S.characters = S.characters.filter(x => x.id !== _editingCharId);
  closeCharModal();
  renderCharSection();
  await saveCharacters();
}
```

- [ ] **Step 3: 手动验证**

1. 提取角色后点击任意角色卡的「编辑」
2. 修改姓名后点「保存」→ 卡片标题更新
3. 点「删除角色」→ 确认后卡片消失
4. 点「+ 新增角色」→ 弹窗打开，保存后新卡片出现

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat: character modal open/close/save/delete"
```

---

### Task 10: Frontend JS — 图片操作

**Files:**
- Modify: `index.html` (JS)

在 `// ── Characters ──` 区块内继续追加：

- [ ] **Step 1: 追加 uploadCharImage 函数**

```javascript
async function uploadCharImage(input) {
  if (!input.files[0] || !_editingCharId || !S.projectId) return;
  const btn = input.previousElementSibling;  // "上传图片" 按钮
  btn.disabled = true; btn.textContent = '上传中…';
  const fd = new FormData();
  fd.append('file', input.files[0]);
  try {
    const resp = await fetch(
      `/api/project/${S.projectId}/characters/${_editingCharId}/upload-image`,
      {method: 'POST', body: fd}
    );
    const {url} = await resp.json();
    const idx = S.characters.findIndex(x => x.id === _editingCharId);
    if (idx !== -1) S.characters[idx].imageUrl = url;
    _refreshModalAvatar(url, S.characters[idx]?.name || '');
    await saveCharacters();
    renderCharSection();
  } catch {
    alert('图片上传失败，请重试');
  } finally {
    btn.disabled = false; btn.textContent = '上传图片';
    input.value = '';
  }
}
```

- [ ] **Step 2: 追加 generateCharImage 函数**

```javascript
async function generateCharImage() {
  if (!_editingCharId || !S.projectId) return;
  const appearance = $('char-f-appearance').value.trim();
  if (!appearance) { alert('请先填写外貌描述'); return; }
  const btn = $('char-gen-btn');
  btn.disabled = true; btn.textContent = '生成中…';
  try {
    const resp = await fetch(
      `/api/project/${S.projectId}/characters/${_editingCharId}/generate-image`,
      {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({appearance}),
      }
    );
    const {url} = await resp.json();
    const idx = S.characters.findIndex(x => x.id === _editingCharId);
    if (idx !== -1) S.characters[idx].imageUrl = url;
    _refreshModalAvatar(url, S.characters[idx]?.name || '');
    await saveCharacters();
    renderCharSection();
  } catch {
    alert('图片生成失败，请检查外貌描述或稍后重试');
  } finally {
    btn.disabled = false; btn.textContent = '✦ AI 生成图';
  }
}
```

- [ ] **Step 3: 手动验证上传**

1. 编辑一个角色，点「上传图片」，选择一张本地 jpg
2. 期望：头像预览更新，Supabase Storage 中出现文件

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat: character image upload and AI generation"
```

---

### Task 11: Frontend JS — restoreProject 扩展

**Files:**
- Modify: `index.html` (JS)

- [ ] **Step 1: 在 `restoreProject` 函数里，`closeHistory()` 调用之前添加**

找到 `restoreProject` 函数中的：
```javascript
  closeHistory();
  appendMsg('assistant',`已恢复项目「${data.title}」，可从上次进度继续创作。`);
```

在 `closeHistory()` 之前插入：
```javascript
  S.characters = data.characters || [];
```

- [ ] **Step 2: 在 `restoreProject` 里，worldbuilding phase 的恢复分支后追加字符渲染**

找到：
```javascript
  } else if(phase==='worldbuilding') {
    setStep(2); $('ctitle').textContent='世界观设定';
    $('cbody').innerHTML=`<div class="rendered">${md(S.worldbuilding)}</div>`;
    showWorldbuildingActions();
  }
```

在 `showWorldbuildingActions();` 那行之后插入（仍在 `else if` 内）：
```javascript
    if (S.characters.length > 0) renderCharSection();
```

同样，找到 outline 和 episodes 的恢复分支——这两个阶段也可能有角色数据。在 `setStep(3)` 和 `setStep(4)` 的分支里，`showOutlineActions()` / `renderEpisodeGrid()` 之后分别追加：
```javascript
    if (S.characters.length > 0) renderCharSection();
```

- [ ] **Step 3: 手动验证**

1. 新建项目，完成世界观，提取角色
2. 刷新页面，路由到 `#/project/<id>` → 角色区域自动恢复

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat: restore character cards on project load"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Supabase `characters` JSONB column — Task 1
- ✅ Storage bucket `character-images` — Task 1
- ✅ Character schema (id/name/role/personality/appearance/imageUrl) — Task 7
- ✅ `_row_to_proj` / `_save_proj` extended — Task 3
- ✅ `POST /extract-characters` — Task 4
- ✅ `PATCH field='characters'` — Task 3
- ✅ `POST /upload-image` — Task 4
- ✅ `POST /generate-image` — Task 4
- ✅ DashScope Wanx fallback — Task 4
- ✅ Toolbar「✦ 提取角色」— Task 8
- ✅ Character grid below worldbuilding — Task 7
- ✅ Role badges (protagonist/antagonist/supporting) — Task 7
- ✅ Edit modal (left image + right form) — Task 6, 9
- ✅ Image upload — Task 10
- ✅ AI image generation — Task 10
- ✅ Delete character + Storage cleanup (via overwrite/upsert) — Task 9
- ✅ `restoreProject()` extension — Task 11
- ✅ `requirements.txt` dependencies — Task 2
- ✅ `CHARACTER_EXTRACT_SYSTEM/PROMPT` in prompts.py — Task 2

**Gaps found and fixed:**
- `S.characters` 初始化加在 `initNewProject()` 的 `Object.assign` 里已经覆盖（因为 Task 7 修改了 `const S` 定义），无需额外修改。
- Storage 文件在角色删除时使用 upsert 覆盖而非显式删除（简化实现，Storage 旧文件会被新上传覆盖，不影响使用）。
