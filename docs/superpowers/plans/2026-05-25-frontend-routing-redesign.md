# Frontend Routing Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将入口改为项目列表首页，通过 Hash 路由实现首页与创作页的切换，并优化聊天框长文本体验。

**Architecture:** 保留现有创作页 HTML 结构（显示/隐藏方式切换），在其上叠加 `#home-view` div 作为首页。Router 监听 `hashchange` 决定显示哪个视图，并动态调整 header 内容。首页增加项目卡片网格与删除功能。

**Tech Stack:** Vanilla JS, HTML/CSS, FastAPI (Python), Supabase

---

## 涉及文件

| 文件 | 变更 |
|---|---|
| `server.py` | 新增 `DELETE /api/project/:id` |
| `index.html` | 新增 home-view、header 改造、router JS、home 渲染、项目初始化/加载、聊天框优化 |

---

### Task 1: Backend — DELETE /api/project/:id

**Files:**
- Modify: `server.py`

- [ ] **Step 1: 在 `# ── Export` 注释前插入 DELETE 接口**

```python
@app.delete("/api/project/{pid}")
async def project_delete(pid: str):
    db.table("projects").delete().eq("id", pid).execute()
    return {"ok": True}
```

- [ ] **Step 2: 启动服务验证**

```powershell
.\venv\Scripts\uvicorn server:app --reload
```

新建一个测试项目后，执行（替换 `<id>`）：

```powershell
Invoke-WebRequest -Method DELETE -Uri "http://localhost:8000/api/project/<id>" -UseBasicParsing
```

期望：响应 `{"ok":true}`，Supabase Table Editor 中该行消失。

- [ ] **Step 3: Commit**

```bash
git add server.py
git commit -m "feat: add DELETE /api/project/:id endpoint"
```

---

### Task 2: HTML 结构 — home-view 容器与 header 改造

**Files:**
- Modify: `index.html`

- [ ] **Step 1: 在 `<body>` 开头（`<header>` 之前）插入 home-view 容器**

```html
<div id="home-view" style="display:none;flex-direction:column;height:100vh;background:#0f0f13"></div>
```

- [ ] **Step 2: 将现有 `<header>` 替换为含按钮槽的新版本**

```html
<header>
  <button class="hdr-btn" id="back-home-btn" onclick="goto('#/')" style="display:none">← 首页</button>
  <h1>✦ 短视频剧本生成器</h1>
  <div class="step-bar" id="step-bar">
    <div class="step active" id="s1">① 聊需求</div>
    <span class="step-arrow">›</span>
    <div class="step" id="s2">② 世界观</div>
    <span class="step-arrow">›</span>
    <div class="step" id="s3">③ 大纲</div>
    <span class="step-arrow">›</span>
    <div class="step" id="s4">④ 剧本</div>
  </div>
  <button class="hdr-btn primary-hdr-btn" id="new-proj-btn" onclick="goto('#/project/new')" style="display:none">+ 新建剧本</button>
  <button class="hdr-btn" id="history-btn" onclick="toggleHistory()">
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <polyline points="12 8 12 12 14 14"/>
      <path d="M3.05 11a9 9 0 1 0 .5-4"/><polyline points="3 3 3 7 7 7"/>
    </svg>
    项目历史
  </button>
</header>
```

- [ ] **Step 3: 在 CSS 末尾（`</style>` 之前）追加 home-view 样式**

```css
.primary-hdr-btn{background:#c9a96e;color:#1a1208;border-color:#c9a96e;font-weight:600}
.primary-hdr-btn:hover{background:#d4b87a}

.home-body{flex:1;overflow-y:auto;padding:28px 32px}
.home-body::-webkit-scrollbar{width:3px}
.home-body::-webkit-scrollbar-thumb{background:#1e1e2a}
.home-section-title{font-size:13px;color:#555;margin-bottom:14px}
.proj-grid-home{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:11px}
.proj-card-home{background:#111120;border:1px solid #1e1e2c;border-radius:11px;
  padding:14px 16px;cursor:pointer;transition:all .18s}
.proj-card-home:hover{border-color:#c9a96e44;background:#17172a}
.pch-title{font-size:14px;color:#c9a96e;font-weight:600;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:8px}
.pch-meta{display:flex;gap:6px;align-items:center;margin-bottom:10px}
.pch-progress{font-size:11px;color:#4a6a4a}
.pch-footer{display:flex;align-items:center;justify-content:space-between}
.pch-time{font-size:11px;color:#383848}
.pch-delete{background:none;border:none;color:#2a2a3a;font-size:18px;
  cursor:pointer;padding:0 4px;border-radius:4px;line-height:1;transition:color .15s}
.pch-delete:hover{color:#c06060}
.home-empty{display:flex;flex-direction:column;align-items:center;
  justify-content:center;height:60vh;gap:12px}
.home-empty p{font-size:14px;color:#3a3a50}
.home-empty small{font-size:12px;color:#252535}
```

- [ ] **Step 4: 删除 `window.onload` 块**

找到并完整删除：

```javascript
window.onload = () => {
  appendMsg('assistant','你好！我是你的短视频剧本助手，专注古装/玄幻类型 ✨\n\n先聊聊你想要什么样的故事——\n\n你的主角是什么人？有什么特别的身份或能力？');
  $input().focus();
};
```

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat: add home-view container, header slots, home CSS"
```

---

### Task 3: Router — goto() / router() / 视图切换

**Files:**
- Modify: `index.html` (JS)

- [ ] **Step 1: 在 `const S = {...}` 定义之后添加 router 代码块**

```javascript
// ── Router ──────────────────────────────────────────────────────────────────

function goto(hash) {
  location.hash = hash;
}

function showHomeView() {
  $('home-view').style.display      = 'flex';
  document.querySelector('.layout').style.display = 'none';
  $('step-bar').style.display       = 'none';
  $('back-home-btn').style.display  = 'none';
  $('history-btn').style.display    = 'none';
  $('new-proj-btn').style.display   = '';
}

function showCreationView() {
  $('home-view').style.display      = 'none';
  document.querySelector('.layout').style.display = 'flex';
  $('step-bar').style.display       = '';
  $('back-home-btn').style.display  = '';
  $('history-btn').style.display    = '';
  $('new-proj-btn').style.display   = 'none';
}

async function router() {
  const hash = location.hash || '#/';
  if (hash === '#/' || hash === '') {
    showHomeView();
    await loadHome();
  } else if (hash === '#/project/new') {
    showCreationView();
    initNewProject();
  } else if (hash.startsWith('#/project/')) {
    const pid = hash.replace('#/project/', '');
    showCreationView();
    await loadProject(pid);
  }
}

window.addEventListener('hashchange', router);
window.addEventListener('load', router);
```

- [ ] **Step 2: 手动验证路由切换**

打开 `http://localhost:8000`：
- 默认 hash 为空 → 显示 home-view（暂时空白），创作区隐藏，header 显示「新建剧本」
- 手动修改 URL 为 `#/project/new` → 显示创作区，header 显示「← 首页」和步骤条

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat: add hash router with view switching"
```

---

### Task 4: Home view — 项目列表渲染

**Files:**
- Modify: `index.html` (JS)

- [ ] **Step 1: 在 router 代码块之后添加 home view 渲染函数**

注意：`phaseLabel` 已在文件中存在，不要重复声明。

```javascript
// ── Home View ────────────────────────────────────────────────────────────────

async function loadHome() {
  const hv = $('home-view');
  hv.innerHTML = `<div class="home-body" id="home-body">
    <div class="home-empty"><p>加载中…</p></div>
  </div>`;
  try {
    const resp = await fetch('/api/projects');
    const list = await resp.json();
    renderHomeList(list);
  } catch {
    $('home-body').innerHTML =
      '<div class="home-empty"><p>加载失败，请刷新重试</p></div>';
  }
}

function renderHomeList(list) {
  const body = $('home-body');
  if (!list.length) {
    body.innerHTML = `<div class="home-empty">
      <p>还没有剧本项目</p>
      <small>点击右上角「+ 新建剧本」开始创作</small>
    </div>`;
    return;
  }
  body.innerHTML = `
    <div class="home-section-title">全部项目（${list.length} 个）</div>
    <div class="proj-grid-home" id="proj-grid-home"></div>`;
  const grid = $('proj-grid-home');
  list.forEach(p => grid.appendChild(makeHomeCard(p)));
}

function makeHomeCard(p) {
  const card = document.createElement('div');
  card.className = 'proj-card-home';
  card.id = `hcard-${p.id}`;
  const progress = p.phase === 'episodes' && p.episodeCount
    ? `${p.episodesDone}/${p.episodeCount} 集` : '';
  card.innerHTML = `
    <div class="pch-title">《${p.title}》</div>
    <div class="pch-meta">
      <span class="phase-badge ${p.phase}">${phaseLabel[p.phase] || p.phase}</span>
      ${progress ? `<span class="pch-progress">${progress}</span>` : ''}
    </div>
    <div class="pch-footer">
      <span class="pch-time">${p.updated || ''}</span>
      <button class="pch-delete" title="删除项目"
        onclick="deleteProject('${p.id}',event)">×</button>
    </div>`;
  card.onclick = () => goto(`#/project/${p.id}`);
  return card;
}

async function deleteProject(id, event) {
  event.stopPropagation();
  if (!confirm('删除后无法恢复，确认删除此项目？')) return;
  try {
    await fetch(`/api/project/${id}`, { method: 'DELETE' });
    $(`hcard-${id}`)?.remove();
    const grid = $('proj-grid-home');
    if (grid && grid.children.length === 0) renderHomeList([]);
  } catch {
    alert('删除失败，请重试');
  }
}
```

- [ ] **Step 2: 手动验证**

访问 `http://localhost:8000/#/`：
- 有项目 → 显示卡片网格（标题、阶段徽章、集数进度、更新时间）
- 无项目 → 显示空状态文案
- 点击卡片 → URL 跳转到 `#/project/:id`
- 点击 `×` → 确认后卡片消失，Supabase 中对应行被删除

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat: home view with project list and delete"
```

---

### Task 5: 创作页 — 新建项目初始化与加载已有项目

**Files:**
- Modify: `index.html` (JS)

- [ ] **Step 1: 在 home view 代码块之前添加创作页初始化函数**

```javascript
// ── Creation Page Init ───────────────────────────────────────────────────────

function initNewProject() {
  Object.assign(S, {
    phase:'chat', projectId:null, messages:[], requirements:'',
    worldbuilding:'', outline:'', episodeCount:15, episodes:{},
    generating:false, pendingAction:null,
  });
  $('messages').innerHTML = '';
  $('cbody').innerHTML = `
    <div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
      </svg>
      <p>和左侧 AI 描述你的故事想法</p>
      <small>世界观 → 大纲 → 分集剧本，一条龙生成</small>
    </div>`;
  setChips([]); setToolbar([]);
  $('refine-hint').style.display = 'none';
  closeHistory();
  setStep(1);
  appendMsg('assistant',
    '你好！我是你的短视频剧本助手，专注古装/玄幻类型 ✨\n\n先聊聊你想要什么样的故事——\n\n你的主角是什么人？有什么特别的身份或能力？');
  $input().value = ''; $input().style.height = 'auto'; $input().focus();
}

async function loadProject(pid) {
  $('messages').innerHTML = '';
  $('cbody').innerHTML =
    '<div class="empty-state"><p style="color:#555">加载中…</p></div>';
  setStep(1);
  try {
    const resp = await fetch(`/api/project/${pid}`);
    if (!resp.ok) throw new Error();
    restoreProject(await resp.json());
  } catch {
    appendMsg('system', '项目加载失败，请返回首页重试');
  }
}
```

- [ ] **Step 2: 手动验证**

- 访问 `#/project/new` → 聊天区清空，出现 AI 欢迎语，步骤条重置到①
- 访问 `#/project/<已有id>` → 项目内容正确恢复（对话记录、阶段、内容）
- 在创作页点击「← 首页」→ 跳回首页，显示项目列表

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat: creation page init and project load via hash route"
```

---

### Task 6: 第一条消息自动创建项目记录

**Files:**
- Modify: `index.html` (JS，`handleSend` 函数)

- [ ] **Step 1: 在 handleSend 中找到以下两行**

```javascript
  S.messages.push({role:'user',content:text});
  setLoading(true); setChips([]);
```

在这两行之后、`const b=appendStreamMsg('assistant')` 之前插入：

```javascript
  if (S.messages.length === 1 && !S.projectId) {
    const tempTitle = text.replace(/\s+/g,'').slice(0,20) || '新故事';
    try {
      const r = await fetch('/api/project',{
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({title:tempTitle, phase:'chat', messages:S.messages}),
      });
      const {id} = await r.json();
      S.projectId = id;
      history.replaceState(null,'',`#/project/${id}`);
    } catch { /* saveProject 后续会补救 */ }
  }
```

- [ ] **Step 2: 手动验证**

新建项目，发第一条消息后：
- URL 从 `#/project/new` 变为 `#/project/20260525_xxxxxx`
- Supabase Table Editor 出现新行，title 为消息前 20 字
- 完成世界观 + 大纲后，title 自动更新为 `《书名》`（由 saveProject 里的 extractTitle 完成）

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat: auto-create project record on first chat message"
```

---

### Task 7: 聊天框长文本 + 仅按钮发送

**Files:**
- Modify: `index.html` (CSS + JS)

- [ ] **Step 1: 修改 textarea 的 max-height**

将 CSS 中：

```css
textarea{...;max-height:110px;...}
```

改为：

```css
textarea{...;max-height:40vh;...}
```

- [ ] **Step 2: 删除 Enter 发送的 keydown 监听**

找到并完整删除：

```javascript
$input().addEventListener('keydown', e => {
  if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
});
```

- [ ] **Step 3: 手动验证**

- 粘贴 200+ 字长文本到聊天框 → 文本框自动扩展，不超过屏幕 40%
- 按 Enter → 换行，不发送
- 点击发送按钮 → 正常发送

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat: textarea max-height 40vh, button-only send"
```
