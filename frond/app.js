const STORAGE_KEY = "firefly-script-studio-state-v1";

const steps = [
  { id: 1, title: "故事定位", sub: "题材与标签", progress: 20 },
  { id: 2, title: "故事大纲", sub: "多方案 / 编辑", progress: 40 },
  { id: 3, title: "角色设定", sub: "人物小传", progress: 60 },
  { id: 4, title: "分集规划", sub: "冲突与钩子", progress: 80 },
  { id: 5, title: "正文创作", sub: "逐集生成", progress: 85 },
];

const tagOptions = {
  audience: ["男频", "女频", "全年龄"],
  genres: ["玄幻", "奇幻", "武侠", "仙侠", "都市", "现实", "军事", "历史", "游戏", "体育", "科幻", "悬疑", "恐怖", "灵异", "同人", "轻小说", "现代言情", "古代言情", "青春校园", "纯爱", "年代", "乡村", "职场", "家庭", "末世", "网游", "官场", "架空"],
  coreElements: ["重生", "穿越", "系统", "随身空间", "豪门世家", "娱乐圈", "种田", "宅斗", "宫斗", "无限流", "快穿", "争夺", "团宠", "马甲", "废材", "强者回归", "赘婿", "奶爸", "鉴宝", "盗墓", "洪荒", "诸天万界", "复仇", "霸总", "权谋", "甜宠", "神医", "战神", "异能", "萌宝"],
  emotionalTone: ["爽文", "甜宠", "虐恋", "搞笑", "热血", "治愈", "轻松", "腹黑", "扮猪吃虎", "升级练功", "杀伐果断", "智商在线", "悲剧", "暗黑", "唯美", "恐怖", "烧脑", "励志", "爆笑", "温馨", "沙雕"],
};

const app = document.querySelector("#app");
const portal = document.querySelector("#portal");
let saveTimer = null;
let generationRun = 0;
let state = loadState();

render();

app.addEventListener("click", onClick);
app.addEventListener("input", onInput);
app.addEventListener("change", onInput);
app.addEventListener("keydown", onKeyDown);
document.addEventListener("mouseup", captureSelection);
document.addEventListener("keyup", captureSelection);

function loadState() {
  try {
    const cached = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (cached && Array.isArray(cached.scripts)) {
      return applyStartupRoute(normalizeState(cached));
    }
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
  return applyStartupRoute(normalizeState({
    view: "list",
    listView: "grid",
    search: "",
    activeScriptId: "script-demo",
    selectedEpisodeId: "ep-1",
    outlineTab: "plans",
    assistantOpen: false,
    selectedOutlineIds: ["plan-1", "plan-2"],
    extraTags: { audience: [], genres: [], coreElements: [], emotionalTone: [] },
    scripts: [makeDemoScript()],
  }));
}

function applyStartupRoute(next) {
  const params = new URLSearchParams(window.location.search);
  if (params.get("view") === "workspace") {
    next.view = "workspace";
  }
  const step = Number(params.get("step"));
  if (step >= 1 && step <= 5) {
    const script = next.scripts.find((item) => item.id === next.activeScriptId) || next.scripts[0];
    if (script) script.currentStep = step;
  }
  return next;
}

function normalizeState(raw) {
  const next = {
    view: raw.view || "list",
    listView: raw.listView || "grid",
    search: raw.search || "",
    activeScriptId: raw.activeScriptId || raw.scripts?.[0]?.id || "script-demo",
    selectedEpisodeId: raw.selectedEpisodeId || raw.scripts?.[0]?.episodes?.[0]?.id || "ep-1",
    outlineTab: raw.outlineTab || "plans",
    assistantOpen: Boolean(raw.assistantOpen),
    selectedOutlineIds: raw.selectedOutlineIds || [],
    extraTags: raw.extraTags || { audience: [], genres: [], coreElements: [], emotionalTone: [] },
    scripts: raw.scripts?.length ? raw.scripts : [makeDemoScript()],
    modal: null,
    toasts: [],
    generation: null,
    selection: null,
  };
  if (!next.scripts.find((script) => script.id === next.activeScriptId)) {
    next.activeScriptId = next.scripts[0]?.id;
  }
  return next;
}

function persist() {
  const payload = {
    view: state.view,
    listView: state.listView,
    search: state.search,
    activeScriptId: state.activeScriptId,
    selectedEpisodeId: state.selectedEpisodeId,
    outlineTab: state.outlineTab,
    assistantOpen: state.assistantOpen,
    selectedOutlineIds: state.selectedOutlineIds,
    extraTags: state.extraTags,
    scripts: state.scripts,
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  setSaveState("saved");
}

function scheduleSave() {
  setSaveState("saving");
  clearTimeout(saveTimer);
  saveTimer = setTimeout(persist, 650);
}

function setSaveState(status) {
  const node = document.querySelector("[data-save-state]");
  if (!node) return;
  node.innerHTML = status === "saving"
    ? `<span class="save-dot saving"></span> 编辑中`
    : `<span class="save-dot"></span> 已自动保存`;
}

function makeDemoScript() {
  return {
    id: "script-demo",
    name: "金帝",
    status: "CREATING",
    completionRate: 85,
    currentStep: 5,
    createdAt: "2026-05-27 11:17:16",
    updatedAt: "2026-05-27 11:18:42",
    storyPositioning: {
      workType: "短剧",
      episodeCount: 50,
      audience: ["男频"],
      genres: ["仙侠"],
      coreElements: ["重生"],
      emotionalTone: ["爽文", "热血"],
    },
    storyOutline: {
      selectedPlanIndex: 0,
      plans: [
        {
          id: "plan-1",
          title: "方案一",
          label: "偏热血",
          content: "故事梗概总结\n\n一代仙尊“金帝”楚渊在飞升之际遭未婚妻与逆徒背叛，修为尽失，重生于三百年后。此时他附身在下界被抽干灵脉的家族废物私生子身上，昔日的仇敌却已高居三界。楚渊以残缺身体重修，于凡尘中重聚旧部，斩断族中压迫，逐步揭开未婚妻篡夺天命的真相。\n\n完整大纲\n\n开篇抓手：夺基之恨与强势反杀。\n第一场戏发生在楚家血雨祭祀大典。楚渊醒来时被绑在祭台上，家族长老正准备抽尽他最后一丝灵脉。前世记忆回归，他以残破身体催动禁术，反手夺回灵脉，留下“我从地狱回来，只为清算”这一核心宣言。\n\n主线推进：资源劫掠与旧部重逢。楚渊必须重塑“金帝霸体”，在下界重新夺回力量。他在试炼、家族斗争和宗门选拔中不断遭遇昔日因果的残影，逐步发现三百年前的背叛并非情仇，而是一次夺取天命的天界阴谋。\n\n高潮转折：当楚渊即将飞升时，发现真正背后的敌人并非未婚妻，而是自己曾经最信任的守界人。最终他以凡身逆伐天门，把散落于人间的旧部与新生盟友带回三界。",
          generatedAt: "2026-05-27 11:06:24",
        },
        {
          id: "plan-2",
          title: "方案二",
          label: "偏权谋",
          content: "故事背景设定在灵气崩坏后的下界王朝。楚渊重生后不再急于复仇，而是伪装成无用私生子，借楚家内斗、宗门选拔、皇朝供奉三重棋局重新收拢资源。\n\n主要人物包括沉静狠绝的楚渊、表面温顺实则掌握禁术的凤凌雪、以家族利益为先的楚万山，以及奉天界密令下界监视的楚惊云。\n\n核心冲突在于楚渊必须在隐藏身份的同时拿回前世遗物。每一次胜利都会暴露更多线索，也让天界旧敌更早察觉他的归来。结局走向是楚渊以一场假死布局诱敌下界，把三百年旧账一次清算。",
          generatedAt: "2026-05-27 11:06:24",
        },
        {
          id: "plan-3",
          title: "方案三",
          label: "偏虐心",
          content: "楚渊重生后发现未婚妻凤凌雪并非真正背叛者。她三百年前亲手刺他，是为了替他截断被天道锁定的死局。如今她也转生下界，却失去全部记忆，被迫站在楚渊对立面。\n\n故事主线围绕“复仇还是救赎”展开。楚渊一边重修，一边在蛛丝马迹中看到前世真相。他的敌人既有楚家、宗门和天界追杀者，也有自己对背叛的执念。\n\n高潮处，楚渊在飞升门前选择放弃一半修为救回凤凌雪，随后以二人残缺的天命共同撕开天界阴谋。结局保留开放式余韵，强调宿命与选择。",
          generatedAt: "2026-05-27 11:06:24",
        },
      ],
      versions: [],
    },
    characters: makeCharacters(),
    episodes: [
      makeEpisode(1, "意外开局", "楚渊在祭台醒来，夺回灵脉并震慑楚家。", "家族以祭祀为名剥夺他的最后一丝灵脉。", "楚渊发现祭台阵纹来自三百年前的天界旧敌。"),
      makeEpisode(2, "关系试探", "楚渊借凤凌雪的试探确认她与前世因果有关。", "凤凌雪奉命接近楚渊，却被他看穿破绽。", "凤凌雪无意识说出只有前世才知道的称呼。"),
      makeEpisode(3, "危机升级 3", "楚家长老联手宗门使者围杀楚渊。", "楚渊以残缺身体迎战高阶修士，必须暴露部分前世秘法。", "宗门使者认出金帝印记，暗中传讯天界。"),
    ],
    aiConversation: [
      { id: "msg-1", role: "ai", step: 5, content: "可以从当前分集钩子直接生成第一集正文，也可以先调整对白占比。", appliedToContent: false },
    ],
  };
}

function makeCharacters() {
  return [
    {
      id: "char-1",
      name: "楚渊",
      gender: "男",
      age: "28",
      role: "主角",
      personality: ["冷静", "隐忍", "果断"],
      biography: "前世为三界共主，遭未婚妻与徒弟联手背叛。重生于下界被抽干灵脉的私生子身上，唯一执念是重铸金帝霸体，一路杀上九重天夺回真相。",
      appearance: "身形单薄但脊背笔挺，常穿沾满暗红血污的粗布灰衣。面色苍白如纸，双眼锐利如刃。",
      background: "体内残留一缕金帝本源，却被楚家祭阵锁住。每次动用前世秘法都会撕裂经脉。",
    },
    {
      id: "char-2",
      name: "凤凌雪",
      gender: "女",
      age: "25",
      role: "女主",
      personality: ["克制", "聪慧", "矛盾"],
      biography: "曾是楚渊未婚妻，因一场天界棋局被迫亲手刺向楚渊。转世后被宗门培养为冷面圣女，对楚渊既警惕又本能靠近。",
      appearance: "常穿极尽素净的白衣，赤金凤纹拖地长裙只在祭典时出现。眉眼清冷，话少而锋利。",
      background: "灵魂深处封印着三百年前真相，封印越松动，她越容易受到天界操控。",
    },
    {
      id: "char-3",
      name: "楚万山",
      gender: "男",
      age: "52",
      role: "反派",
      personality: ["圆滑", "贪婪", "冷酷"],
      biography: "楚家族长，靠出卖楚渊前世旧部行踪换来下界权势。表面庇护楚家，实则把族人当成与天界交易的筹码。",
      appearance: "中年发福，体态略显臃肿，穿着刺绣繁密但配色俗气的暗紫色锦袍。",
      background: "掌握祭台阵眼，知道楚渊身体里藏着一枚足以改写命格的金印碎片。",
    },
    {
      id: "char-4",
      name: "楚惊云",
      gender: "男",
      age: "31",
      role: "反派",
      personality: ["傲慢", "多疑", "好胜"],
      biography: "楚家嫡长子，从小被培养成继承人。习惯把楚渊踩在脚下，一旦遭遇真正压力便会暴露怯懦与嫉妒。",
      appearance: "穿着仿造上界仙人款式的白袍，头发梳得油光水滑，佩戴金冠。",
      background: "借祭阵修炼邪法，却不知道自己也只是天界观察楚渊的试验品。",
    },
    {
      id: "char-5",
      name: "赵老四",
      gender: "男",
      age: "46",
      role: "配角",
      personality: ["圆滑", "重义", "胆小"],
      biography: "下界黑市掌柜，早年受过金帝旧部恩惠。最初只想自保，后来成为楚渊搜集资源和情报的关键帮手。",
      appearance: "常穿洗得发白的长衫，腰间挂着铁算盘。",
      background: "知道一条通往旧部遗藏的暗线，但每说出一步都会引来追杀。",
    },
    {
      id: "char-6",
      name: "贺铁心",
      gender: "男",
      age: "39",
      role: "配角",
      personality: ["沉稳", "忠诚", "狠辣"],
      biography: "金帝旧部后人，表面是流放矿山的铁匠。认出楚渊后重新燃起追随之心。",
      appearance: "宽肩厚背，掌心有常年打铁留下的灼痕。",
      background: "保管着金帝战旗残片，是楚渊重建势力的第一枚棋子。",
    },
  ];
}

function makeEpisode(num, title, goal, conflict, hook) {
  return {
    id: `ep-${num}-${uid()}`,
    episodeNumber: num,
    title,
    goal,
    conflict,
    hook,
    scriptContent: "",
    versions: [],
    alternateVersions: [],
    needsUpdate: false,
  };
}

function createBlankScript() {
  const id = `script-${uid()}`;
  return {
    id,
    name: "未命名剧本",
    status: "DRAFT",
    completionRate: 10,
    currentStep: 1,
    createdAt: formatDate(new Date()),
    updatedAt: formatDate(new Date()),
    storyPositioning: {
      workType: "短剧",
      episodeCount: 10,
      audience: ["男频"],
      genres: [],
      coreElements: [],
      emotionalTone: [],
    },
    storyOutline: { selectedPlanIndex: 0, plans: [], versions: [] },
    characters: [],
    episodes: [],
    aiConversation: [{ id: uid(), role: "ai", step: 1, content: "先给我一个题材方向，我可以帮你组合标签并生成大纲。", appliedToContent: false }],
  };
}

function render() {
  if (!state.scripts.length) {
    state.scripts.push(createBlankScript());
    state.activeScriptId = state.scripts[0].id;
  }
  app.innerHTML = `<div class="app">${renderTopNav()}${state.view === "list" ? renderListPage() : renderWorkspace()}</div>`;
  renderPortal();
}

function renderTopNav() {
  return `
    <header class="top-nav">
      <div class="nav-inner">
        <div class="brand">
          <span class="brand-mark"></span>
          <span class="brand-title">萤火织光·AI创作平台</span>
        </div>
        <nav class="nav-links" aria-label="主导航">
          <button class="nav-link" type="button">⌂ 首页</button>
          <button class="module-pill" type="button">✎ 剧本创作⌄</button>
          <button class="nav-link" type="button">▱ 视频创作</button>
        </nav>
        <div class="user-chip">
          <span class="avatar"></span>
          <span>9db322036316</span>
          <span>⌄</span>
        </div>
      </div>
    </header>
  `;
}

function renderListPage() {
  const scripts = filteredScripts();
  return `
    <main class="list-shell">
      <section class="list-head">
        <div class="title-row">
          <h1>我的剧本</h1>
          <span class="badge">共 ${scripts.length} 部作品</span>
        </div>
        <div class="list-tools">
          <input class="search-box" type="search" data-ui="search" placeholder="搜索剧本名称..." value="${escapeAttr(state.search)}" />
          <button class="icon-button ${state.listView === "grid" ? "active" : ""}" type="button" data-action="switch-list-view" data-view="grid" aria-label="网格视图">▦</button>
          <button class="icon-button ${state.listView === "table" ? "active" : ""}" type="button" data-action="switch-list-view" data-view="table" aria-label="列表视图">☷</button>
          <button class="primary-button violet" type="button" data-action="new-script">＋ 新建剧本</button>
        </div>
      </section>
      ${state.listView === "grid" ? renderScriptGrid(scripts) : renderScriptTable(scripts)}
      <footer class="pagination">
        <span>共 ${scripts.length} 条</span>
        <select class="small-select" aria-label="每页条数">
          <option>20条/页</option>
          <option>50条/页</option>
        </select>
        <button class="ghost-button" type="button" disabled>上一页</button>
        <button class="icon-button active" type="button">1</button>
        <button class="ghost-button" type="button" disabled>下一页</button>
        <span>前往</span>
        <input class="page-input" value="1" />
        <span>页</span>
      </footer>
    </main>
  `;
}

function renderScriptGrid(scripts) {
  if (!scripts.length) return `<div class="empty-state"><div><h3>没有匹配的剧本</h3><p>调整搜索条件，或创建一个新剧本。</p></div></div>`;
  return `
    <section class="scripts-grid">
      ${scripts.map((script) => `
        <article class="script-card">
          <div class="cover" style="background:${coverGradient(script.name)}">
            <span class="status-label">${statusText(script.status)}</span>
            <span class="cover-letter">${escapeHtml(firstChar(script.name))}</span>
          </div>
          <div class="card-body">
            <h3>${escapeHtml(script.name)}</h3>
            <div class="meta">▣ ${escapeHtml(script.createdAt)}</div>
            <div class="card-actions">
              <button class="primary-button violet" type="button" data-action="open-script" data-id="${script.id}">✎ 开始</button>
              <button class="ghost-button" type="button" data-action="detail-script" data-id="${script.id}">明细</button>
              <button class="danger-button" type="button" data-action="request-delete" data-id="${script.id}" aria-label="删除">⌫</button>
            </div>
          </div>
        </article>
      `).join("")}
    </section>
  `;
}

function renderScriptTable(scripts) {
  return `
    <section class="script-table">
      ${scripts.map((script) => `
        <div class="script-row">
          <div>
            <strong>${escapeHtml(script.name)}</strong>
            <div class="meta">${escapeHtml(script.createdAt)}</div>
          </div>
          <span>${statusText(script.status)}</span>
          <span>${script.completionRate}%</span>
          <div class="card-actions">
            <button class="primary-button violet" type="button" data-action="open-script" data-id="${script.id}">开始</button>
            <button class="ghost-button" type="button" data-action="detail-script" data-id="${script.id}">明细</button>
            <button class="danger-button" type="button" data-action="request-delete" data-id="${script.id}">删除</button>
          </div>
        </div>
      `).join("")}
    </section>
  `;
}

function renderWorkspace() {
  const script = activeScript();
  if (!script) return "";
  return `
    <section class="workbar">
      <button class="back-button" type="button" data-action="back-list" aria-label="返回">‹</button>
      <div class="work-title">
        <div class="kicker">SCRIPT STUDIO</div>
        <h2>${script.name ? escapeHtml(script.name) : "请输入作品标题"}</h2>
      </div>
      <div class="work-actions">
        <span class="muted" data-save-state><span class="save-dot"></span> 已自动保存</span>
        ${script.currentStep === 5 ? `<button class="ghost-button cyan" type="button" data-action="export-script">⇩ 导出剧本</button>` : ""}
        <button class="ghost-button" type="button" data-action="show-versions">▤ 保存版本</button>
      </div>
    </section>
    <section class="workspace ${state.assistantOpen ? "with-assistant" : ""}">
      ${renderSidebar(script)}
      <main class="stage">
        <div class="stage-inner">${renderCurrentStep(script)}</div>
      </main>
      ${state.assistantOpen ? renderAssistant(script) : ""}
    </section>
    <button class="assistant-toggle" type="button" data-action="toggle-assistant">${state.assistantOpen ? "收起 AI" : "AI 助手"}</button>
  `;
}

function renderSidebar(script) {
  return `
    <aside class="sidebar">
      <div class="step-list">
        ${steps.map((step) => {
          const done = script.completionRate >= step.progress || step.id < script.currentStep;
          const warn = step.id >= 4 && hasPendingDownstream(script);
          return `
            <button class="step-item ${script.currentStep === step.id ? "active" : ""} ${done ? "done" : ""}" type="button" data-action="set-step" data-step="${step.id}">
              <span class="step-no">${String(step.id).padStart(2, "0")}</span>
              <span>
                <span class="step-title">${step.title}</span>
                <span class="step-sub">${step.sub}</span>
              </span>
              <span>${warn && step.id === 4 ? "⚠" : done ? "✓" : ""}</span>
            </button>
          `;
        }).join("")}
      </div>
      <div class="progress-block">
        <div>作品完成度</div>
        <div class="progress-track"><div class="progress-fill" style="width:${script.completionRate}%"></div></div>
        <div class="progress-value">${script.completionRate}%</div>
      </div>
    </aside>
  `;
}

function renderCurrentStep(script) {
  if (script.currentStep === 1) return renderStepOne(script);
  if (script.currentStep === 2) return renderStepTwo(script);
  if (script.currentStep === 3) return renderStepThree(script);
  if (script.currentStep === 4) return renderStepFour(script);
  return renderStepFive(script);
}

function renderStepHead(step, title, subtitle, actionHtml = "") {
  return `
    <header class="content-head">
      <div>
        <div class="step-label">STEP ${String(step).padStart(2, "0")}</div>
        <h1>${title}</h1>
        <p class="subtitle">${subtitle}</p>
      </div>
      <div>${actionHtml}</div>
    </header>
  `;
}

function renderStepOne(script) {
  const pos = script.storyPositioning;
  return `
    ${renderStepHead(1, "故事定位", "先确定受众、题材和情绪，再让 AI 开始创作。", `<button class="primary-button" type="button" data-action="generate-outline">✳ 生成故事大纲</button>`)}
    <section class="panel panel-pad">
      <div class="positioning-grid">
        <div>
          <div class="form-grid">
            <div class="field">
              <label>作品标题</label>
              <input data-bind="name" value="${escapeAttr(script.name)}" placeholder="请输入作品标题" />
            </div>
            <div class="field">
              <label>作品类型</label>
              <div class="chip-line">
                ${["短剧", "动漫", "网文"].map((item) => `<button class="tag ${pos.workType === item ? "selected" : ""}" type="button" data-action="set-position" data-key="workType" data-value="${item}">${item}</button>`).join("")}
              </div>
            </div>
            <div class="field">
              <label>预计集数</label>
              <div class="chip-line">
                ${[3, 5, 10, 15, 20, 50, 100].map((count) => `<button class="tag ${Number(pos.episodeCount) === count ? "selected" : ""}" type="button" data-action="set-position" data-key="episodeCount" data-value="${count}">${count}集</button>`).join("")}
                <input class="small-input" type="number" min="1" max="100" data-bind="storyPositioning.episodeCount" value="${escapeAttr(pos.episodeCount)}" aria-label="自定义集数" />
              </div>
            </div>
          </div>
          ${renderTagSection("AUDIENCE", "受众", "audience", pos.audience)}
          ${renderTagSection("GENRE", "题材", "genres", pos.genres)}
          ${renderTagSection("CORE", "核心元素", "coreElements", pos.coreElements)}
          ${renderTagSection("TONE", "情感基调", "emotionalTone", pos.emotionalTone)}
        </div>
        <aside class="preview-card">
          <div class="preview-frame">${escapeHtml(firstChar(script.name))}</div>
          <div>
            <h3>${escapeHtml(script.name || "未命名剧本")}</h3>
            <p class="subtle-note">${escapeHtml(pos.workType)} · ${escapeHtml(pos.episodeCount)}集 · ${(pos.genres || []).slice(0, 4).join(" / ") || "等待题材标签"}</p>
            <div class="selected-tags">${[...pos.audience, ...pos.coreElements, ...pos.emotionalTone].slice(0, 8).map((tag) => `<span class="mini-chip">${escapeHtml(tag)}</span>`).join("")}</div>
          </div>
        </aside>
      </div>
    </section>
  `;
}

function renderTagSection(kicker, title, key, selected) {
  const options = [...new Set([...(tagOptions[key] || []), ...(state.extraTags[key] || []), ...(selected || [])])];
  return `
    <section class="tag-section">
      <div class="tag-title">
        <span class="kicker">${kicker}</span>
        <strong>${title}</strong>
        <div class="selected-tags">${(selected || []).map((tag) => `<span class="mini-chip">${escapeHtml(tag)}</span>`).join("")}</div>
      </div>
      <div>
        <div class="tag-grid">
          ${options.map((tag) => `<button class="tag ${(selected || []).includes(tag) ? "selected" : ""}" type="button" data-action="toggle-tag" data-key="${key}" data-value="${escapeAttr(tag)}">${escapeHtml(tag)}</button>`).join("")}
        </div>
        ${key !== "audience" ? `
          <div class="custom-tag-row">
            <input data-custom-input="${key}" placeholder="添加自定义${title}" />
            <button class="ghost-button cyan" type="button" data-action="add-custom-tag" data-key="${key}">添加</button>
          </div>
        ` : ""}
      </div>
    </section>
  `;
}

function renderStepTwo(script) {
  const isGenerating = state.generation?.active && state.generation.kind === "outline";
  if (isGenerating) {
    return `
      ${renderStepHead(2, "生成故事大纲", "AI 正在梳理起承转合、核心冲突与反转节奏。", `<button class="ghost-button" type="button" data-action="stop-generation">停止生成</button>`)}
      <section class="panel panel-pad">${renderStreamState()}</section>
    `;
  }
  const plans = script.storyOutline.plans || [];
  const selectedPlan = plans[script.storyOutline.selectedPlanIndex] || plans[0];
  return `
    ${renderStepHead(2, "生成故事大纲", "选择一个叙事方向，或让 AI 融合多个方案。", `<button class="primary-button" type="button" data-action="confirm-outline" ${plans.length ? "" : "disabled"}>✳ 确认大纲，生成角色</button>`)}
    <section class="panel panel-pad">
      <div class="panel-head">
        <div class="tabs">
          <button class="tab-button ${state.outlineTab === "plans" ? "active" : ""}" type="button" data-action="set-outline-tab" data-tab="plans">✳ 多方案生成</button>
          <button class="tab-button ${state.outlineTab === "edit" ? "active" : ""}" type="button" data-action="set-outline-tab" data-tab="edit">▤ 编辑模式</button>
        </div>
        <div class="chip-line">
          <button class="ghost-button violet" type="button" data-action="regenerate-outline">↻ 重新生成</button>
          ${state.outlineTab === "plans" ? `<button class="ghost-button cyan" type="button" data-action="merge-outline" ${plans.length ? "" : "disabled"}>AI 融合方案</button>` : ""}
        </div>
      </div>
      ${!plans.length ? renderEmptyOutline() : state.outlineTab === "plans" ? renderOutlinePlans(script, plans) : renderOutlineEditor(selectedPlan)}
    </section>
  `;
}

function renderOutlinePlans(script, plans) {
  return `
    <div class="outline-grid">
      ${plans.map((plan, index) => `
        <article class="outline-card ${script.storyOutline.selectedPlanIndex === index ? "selected" : ""}">
          <div class="card-head">
            <div>
              <h3>${escapeHtml(plan.title || `方案${index + 1}`)}</h3>
              <p class="subtle-note">${escapeHtml(plan.label || "AI 方案")}</p>
            </div>
            <label class="muted"><input type="checkbox" data-action="toggle-outline-merge" data-id="${plan.id}" ${state.selectedOutlineIds.includes(plan.id) ? "checked" : ""} /> 融合</label>
          </div>
          <div class="outline-content">${escapeHtml(plan.content)}</div>
          <div class="card-foot">
            <span class="muted">${escapeHtml(plan.generatedAt || "")}</span>
            <button class="primary-button" type="button" data-action="select-outline" data-index="${index}">选用此方案</button>
          </div>
        </article>
      `).join("")}
    </div>
  `;
}

function renderOutlineEditor(plan) {
  if (!plan) return renderEmptyOutline();
  return `
    <div class="field" style="margin-top:22px">
      <label>当前大纲</label>
      <textarea class="editor outline-edit" data-plan-field="content">${escapeHtml(plan.content)}</textarea>
      <p class="subtle-note">修改大纲后，下游角色与分集会被标记为待更新。</p>
    </div>
  `;
}

function renderEmptyOutline() {
  return `
    <div class="empty-state" style="margin-top:22px">
      <div>
        <div class="spinner"></div>
        <h3>故事主线大纲虚位以待</h3>
        <p>AI 将根据您的选题和故事定位标签，为您生成结构清晰、爆点十足的故事主线大纲。</p>
        <button class="primary-button" type="button" data-action="generate-outline">✳ 极速生成故事大纲</button>
      </div>
    </div>
  `;
}

function renderStepThree(script) {
  const isGenerating = state.generation?.active && state.generation.kind === "characters";
  if (isGenerating) {
    return `
      ${renderStepHead(3, "搭建角色关系", "AI 正在基于大纲抽取主角、反派和关键配角。", `<button class="ghost-button" type="button" data-action="stop-generation">停止生成</button>`)}
      <section class="panel panel-pad">${renderStreamState()}</section>
    `;
  }
  return `
    ${renderStepHead(3, "搭建角色关系", "角色小传可以就地编辑，后续会作为生成依据。", `<button class="primary-button" type="button" data-action="confirm-characters">✳ 确认角色，生成分集</button>`)}
    <section class="panel panel-pad">
      <div class="panel-head">
        <div class="title-row"><h3>角色设定</h3><span class="muted">共 ${script.characters.length} 位角色</span></div>
        <div class="chip-line">
          <button class="ghost-button violet" type="button" data-action="generate-characters">↻ 重新生成</button>
          <button class="ghost-button cyan" type="button" data-action="add-character">＋ 添加角色</button>
        </div>
      </div>
      <div class="roles-grid" style="margin-top:22px">
        ${script.characters.map((character) => renderRoleCard(character)).join("")}
      </div>
    </section>
  `;
}

function renderRoleCard(character) {
  return `
    <article class="role-card">
      <div class="role-top">
        <div class="role-avatar">${escapeHtml(firstChar(character.name))}</div>
        <div>
          <input class="small-input" data-character-field="name" data-id="${character.id}" value="${escapeAttr(character.name)}" />
          <div class="chip-line" style="margin-top:8px">
            ${["男", "女", "其他"].map((gender) => `<button class="role-chip ${character.gender === gender ? "hot" : ""}" type="button" data-action="set-character-gender" data-id="${character.id}" data-value="${gender}">${gender}</button>`).join("")}
          </div>
        </div>
      </div>
      <div class="role-fields">
        <label class="field-title">角色定位</label>
        <select class="small-select" data-character-field="role" data-id="${character.id}">
          ${["主角", "女主", "反派", "配角", "导师", "其他"].map((role) => `<option ${character.role === role ? "selected" : ""}>${role}</option>`).join("")}
        </select>
        <label class="field-title">性格特征</label>
        <input class="small-input" data-character-field="personalityText" data-id="${character.id}" value="${escapeAttr((character.personality || []).join("、"))}" />
        <label class="field-title">人物小传</label>
        <textarea data-character-field="biography" data-id="${character.id}">${escapeHtml(character.biography || "")}</textarea>
        <label class="field-title">外貌设定</label>
        <textarea data-character-field="appearance" data-id="${character.id}">${escapeHtml(character.appearance || "")}</textarea>
        <label class="field-title">人物背景</label>
        <textarea data-character-field="background" data-id="${character.id}">${escapeHtml(character.background || "")}</textarea>
        <button class="danger-button" type="button" data-action="delete-character" data-id="${character.id}">删除角色</button>
      </div>
    </article>
  `;
}

function renderStepFour(script) {
  const isGenerating = state.generation?.active && state.generation.kind === "episodes";
  if (isGenerating) {
    return `
      ${renderStepHead(4, "拆解分集规划", "AI 正在为每集生成目标、冲突和结尾钩子。", `<button class="ghost-button" type="button" data-action="stop-generation">停止生成</button>`)}
      <section class="panel panel-pad">${renderStreamState()}</section>
    `;
  }
  ensureEpisodeSelection(script);
  const episode = selectedEpisode(script);
  return `
    ${renderStepHead(4, "拆解分集规划", "每集都要有目标、冲突和结尾钩子。", `<button class="primary-button" type="button" data-action="enter-writing">进入正文创作</button>`)}
    <section class="panel panel-pad">
      ${!script.episodes.length ? `
        <div class="empty-state">
          <div>
            <h3>分集规划尚未生成</h3>
            <p>确认角色后可自动拆解，也可以直接在这里生成分集规划。</p>
            <button class="primary-button" type="button" data-action="generate-episodes">生成分集规划</button>
          </div>
        </div>
      ` : `
        <div class="planning-layout">
          <div class="episode-list">${script.episodes.map((ep) => renderEpisodeCard(ep)).join("")}</div>
          <div class="detail-form">
            <div class="panel-head">
              <h3>第 ${episode.episodeNumber} 集详情</h3>
              <button class="ghost-button violet" type="button" data-action="regenerate-episode">↻ 重新生成</button>
            </div>
            <label class="field-title">标题</label>
            <input data-episode-field="title" value="${escapeAttr(episode.title)}" />
            <label class="field-title">本集目标</label>
            <textarea data-episode-field="goal">${escapeHtml(episode.goal)}</textarea>
            <label class="field-title">主要冲突</label>
            <textarea data-episode-field="conflict">${escapeHtml(episode.conflict)}</textarea>
            <label class="field-title">结尾钩子</label>
            <textarea data-episode-field="hook">${escapeHtml(episode.hook)}</textarea>
          </div>
        </div>
      `}
    </section>
  `;
}

function renderEpisodeCard(ep) {
  return `
    <button class="episode-card ${state.selectedEpisodeId === ep.id ? "active" : ""}" type="button" data-action="select-episode" data-id="${ep.id}">
      <strong>第${ep.episodeNumber}集 ${escapeHtml(ep.title)}</strong>
      <p>${escapeHtml(ep.goal || "等待规划")}</p>
      ${ep.scriptContent ? `<span class="mini-chip">已生成</span>` : ""}
      ${ep.needsUpdate ? `<span class="mini-chip" style="background:#ffb648">待更新</span>` : ""}
    </button>
  `;
}

function renderStepFive(script) {
  ensureEpisodeSelection(script);
  const episode = selectedEpisode(script);
  const isGenerating = state.generation?.active && state.generation.kind === "script";
  const editorText = isGenerating ? state.generation.text : episode?.scriptContent;
  return `
    ${renderStepHead(5, "逐集生成正文", "生成、重写、保存版本都在当前页面完成。", `<button class="ghost-button cyan" type="button" data-action="validate-script">校验</button>`)}
    <section class="panel panel-pad">
      ${!script.episodes.length ? `
        <div class="empty-state">
          <div>
            <h3>请先生成分集规划</h3>
            <p>正文生成需要当前集目标、冲突和钩子作为上下文。</p>
            <button class="primary-button" type="button" data-action="generate-episodes">生成分集规划</button>
          </div>
        </div>
      ` : `
      <div class="writing-layout">
        <nav class="episode-nav">${script.episodes.map((ep) => renderEpisodeCard(ep)).join("")}</nav>
        <aside class="reference-pane">
          <h3><span style="color:var(--cyan)">●</span> 本集大纲参考</h3>
          <div class="reference-body">
            <label class="field-title">分集标题</label>
            <p style="margin:8px 0 18px">${escapeHtml(episode.title)}</p>
            <label class="field-title">冲突与悬念钩子</label>
            <p style="margin-top:8px">${escapeHtml(episode.conflict)}</p>
            <p style="margin-top:14px">${escapeHtml(episode.hook)}</p>
          </div>
          <div class="reference-actions">
            <div class="two-col">
              <label class="field"><span class="field-title">目标字数</span><input data-ui="targetWords" value="1800" /></label>
              <label class="field"><span class="field-title">对白占比</span><input data-ui="dialogRatio" value="60%" /></label>
            </div>
            <button class="primary-button" type="button" data-action="generate-episode-script" ${isGenerating ? "disabled" : ""}>✳ 生成本集正文</button>
            ${isGenerating ? `<button class="ghost-button" type="button" data-action="stop-generation">停止生成</button>` : ""}
            <p class="subtle-note"><span class="save-dot"></span> AI 将结合本集大纲与人物设定生成标准短剧本。</p>
          </div>
        </aside>
        <article class="script-pane">
          <div class="script-editor-head">
            <div>
              <div class="muted">剧本正文</div>
              <h2>${escapeHtml(episode.title)}</h2>
            </div>
            <button class="ghost-button" type="button" data-action="save-version">▤ 保存版本</button>
          </div>
          <div class="editable" contenteditable="true" data-script-editor data-placeholder="生成剧本正文后将在此处显示，您可以直接编辑、微调和润色正文内容。">${editorText ? formatScriptHtml(editorText) : ""}</div>
          ${isGenerating ? `<div class="progress-line"><span style="width:${state.generation.progress}%"></span></div>` : ""}
        </article>
      </div>
      `}
    </section>
  `;
}

function renderStreamState() {
  return `
    <div class="stream-state">
      <div class="stream-box">
        <div class="title-row"><div class="spinner"></div><div><h3>${escapeHtml(state.generation.title)}</h3><p class="subtle-note">${escapeHtml(state.generation.subtitle)}</p></div></div>
        <div class="stream-text">${escapeHtml(state.generation.text || "正在建立上下文...")}</div>
        <div class="progress-line"><span style="width:${state.generation.progress}%"></span></div>
      </div>
    </div>
  `;
}

function renderAssistant(script) {
  const messages = script.aiConversation || [];
  const quick = quickPrompts(script.currentStep);
  return `
    <aside class="assistant">
      <div class="panel-head">
        <h3>AI 助手</h3>
        <button class="icon-button" type="button" data-action="toggle-assistant">×</button>
      </div>
      <div class="quick-tags">${quick.map((item) => `<button type="button" data-action="quick-prompt" data-value="${escapeAttr(item)}">${escapeHtml(item)}</button>`).join("")}</div>
      <div class="chat-list">
        ${messages.map((msg) => `<div class="message ${msg.role === "user" ? "user" : "ai"}">${escapeHtml(msg.content)}</div>`).join("")}
      </div>
      <div class="chat-input">
        <input data-chat-input placeholder="输入修改要求..." />
        <button class="primary-button" type="button" data-action="send-chat">发送</button>
      </div>
    </aside>
  `;
}

function renderPortal() {
  const toasts = state.toasts.map((item) => `<div class="toast">${escapeHtml(item)}</div>`).join("");
  const modal = state.modal ? renderModal() : "";
  const toolbar = state.selection ? `
    <div class="selection-toolbar" style="left:${state.selection.x}px;top:${state.selection.y}px">
      <button type="button" data-action="rewrite-selection" data-mode="rewrite">AI 重写</button>
      <button type="button" data-action="rewrite-selection" data-mode="expand">扩写</button>
      <button type="button" data-action="rewrite-selection" data-mode="shorten">缩写</button>
      <button type="button" data-action="rewrite-selection" data-mode="tense">更紧张</button>
    </div>
  ` : "";
  portal.innerHTML = `${toasts ? `<div class="toast-stack">${toasts}</div>` : ""}${modal}${toolbar}`;
  portal.onclick = onClick;
}

function renderModal() {
  const modal = state.modal;
  if (modal.type === "delete") {
    const script = state.scripts.find((item) => item.id === modal.scriptId);
    return `
      <div class="modal-backdrop">
        <section class="modal">
          <header class="modal-head"><h3>删除剧本</h3><button class="icon-button" data-action="close-modal">×</button></header>
          <div class="modal-body"><p>确认删除《${escapeHtml(script?.name || "")}》？此操作会从本地存储中移除该作品。</p></div>
          <footer class="modal-actions">
            <button class="ghost-button" data-action="close-modal">取消</button>
            <button class="danger-button" data-action="confirm-delete" data-id="${modal.scriptId}">确认删除</button>
          </footer>
        </section>
      </div>
    `;
  }
  if (modal.type === "detail") {
    const script = state.scripts.find((item) => item.id === modal.scriptId);
    return `
      <div class="modal-backdrop">
        <section class="modal">
          <header class="modal-head"><h3>剧本明细</h3><button class="icon-button" data-action="close-modal">×</button></header>
          <div class="modal-body">
            <div class="two-col">
              <div><div class="muted">作品名称</div><h3>${escapeHtml(script?.name || "")}</h3></div>
              <div><div class="muted">状态</div><h3>${statusText(script?.status)}</h3></div>
              <div><div class="muted">完成度</div><h3>${script?.completionRate || 0}%</h3></div>
              <div><div class="muted">创建时间</div><h3>${escapeHtml(script?.createdAt || "")}</h3></div>
            </div>
          </div>
          <footer class="modal-actions"><button class="primary-button" data-action="open-script" data-id="${modal.scriptId}">进入工作台</button></footer>
        </section>
      </div>
    `;
  }
  if (modal.type === "versions") {
    const script = activeScript();
    const versions = collectVersions(script);
    return `
      <div class="modal-backdrop">
        <section class="modal">
          <header class="modal-head"><h3>版本管理</h3><button class="icon-button" data-action="close-modal">×</button></header>
          <div class="modal-body">
            ${versions.length ? versions.map((version) => `
              <div class="version-item">
                <div class="panel-head">
                  <div><strong>${escapeHtml(version.title)}</strong><div class="meta">${escapeHtml(version.savedAt)} · ${escapeHtml(version.type)}</div></div>
                  <button class="ghost-button cyan" data-action="restore-version" data-version-id="${version.id}">恢复此版本</button>
                </div>
              </div>
            `).join("") : `<p class="muted">暂无版本。点击“保存版本”可以创建快照。</p>`}
          </div>
          <footer class="modal-actions"><button class="ghost-button" data-action="close-modal">关闭</button></footer>
        </section>
      </div>
    `;
  }
  if (modal.type === "validation") {
    return `
      <div class="modal-backdrop">
        <section class="modal">
          <header class="modal-head"><h3>连贯性校验</h3><button class="icon-button" data-action="close-modal">×</button></header>
          <div class="modal-body">
            ${modal.items.map((item, index) => `
              <div class="validation-item">
                <div class="panel-head"><strong>${escapeHtml(item.type)} · 第${item.episodeNumber}集</strong><span class="badge">${escapeHtml(item.severity)}</span></div>
                <p style="margin-top:10px">${escapeHtml(item.description)}</p>
                <p class="subtle-note">${escapeHtml(item.suggestion)}</p>
                <button class="ghost-button cyan" data-action="fix-validation" data-index="${index}">一键修复</button>
              </div>
            `).join("")}
          </div>
          <footer class="modal-actions"><button class="ghost-button" data-action="close-modal">关闭</button></footer>
        </section>
      </div>
    `;
  }
  return "";
}

function onClick(event) {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const action = button.dataset.action;
  const script = activeScript();

  if (action === "new-script") {
    const next = createBlankScript();
    state.scripts.unshift(next);
    state.activeScriptId = next.id;
    state.selectedEpisodeId = "";
    state.view = "workspace";
    toast("已创建新剧本。");
    scheduleSave();
    render();
  }

  if (action === "open-script") {
    state.activeScriptId = button.dataset.id;
    const next = activeScript();
    state.selectedEpisodeId = next?.episodes?.[0]?.id || "";
    state.view = "workspace";
    state.modal = null;
    render();
  }

  if (action === "back-list") {
    state.view = "list";
    render();
  }

  if (action === "switch-list-view") {
    state.listView = button.dataset.view;
    scheduleSave();
    render();
  }

  if (action === "detail-script") {
    state.modal = { type: "detail", scriptId: button.dataset.id };
    renderPortal();
  }

  if (action === "request-delete") {
    state.modal = { type: "delete", scriptId: button.dataset.id };
    renderPortal();
  }

  if (action === "confirm-delete") {
    state.scripts = state.scripts.filter((item) => item.id !== button.dataset.id);
    if (!state.scripts.length) state.scripts.push(createBlankScript());
    state.activeScriptId = state.scripts[0].id;
    state.modal = null;
    toast("剧本已删除。");
    scheduleSave();
    render();
  }

  if (action === "close-modal") {
    state.modal = null;
    renderPortal();
  }

  if (action === "set-step" && script) {
    script.currentStep = Number(button.dataset.step);
    scheduleSave();
    render();
  }

  if (action === "set-position" && script) {
    const value = button.dataset.key === "episodeCount" ? Number(button.dataset.value) : button.dataset.value;
    script.storyPositioning[button.dataset.key] = value;
    markDownstream(script, 1);
    updateCompletion(script, steps[0].progress);
    scheduleSave();
    render();
  }

  if (action === "toggle-tag" && script) {
    const key = button.dataset.key;
    const value = button.dataset.value;
    const list = script.storyPositioning[key] || [];
    script.storyPositioning[key] = list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
    markDownstream(script, 1);
    updateCompletion(script, steps[0].progress);
    scheduleSave();
    render();
  }

  if (action === "add-custom-tag" && script) {
    const key = button.dataset.key;
    const input = document.querySelector(`[data-custom-input="${key}"]`);
    const value = input?.value.trim();
    if (!value) return;
    state.extraTags[key] = [...new Set([...(state.extraTags[key] || []), value])];
    script.storyPositioning[key] = [...new Set([...(script.storyPositioning[key] || []), value])];
    markDownstream(script, 1);
    scheduleSave();
    render();
  }

  if (action === "generate-outline" || action === "regenerate-outline") {
    runGeneration("outline");
  }

  if (action === "set-outline-tab") {
    state.outlineTab = button.dataset.tab;
    render();
  }

  if (action === "select-outline" && script) {
    script.storyOutline.selectedPlanIndex = Number(button.dataset.index);
    state.outlineTab = "edit";
    markDownstream(script, 2);
    scheduleSave();
    render();
  }

  if (action === "toggle-outline-merge") {
    const id = button.dataset.id;
    state.selectedOutlineIds = state.selectedOutlineIds.includes(id)
      ? state.selectedOutlineIds.filter((item) => item !== id)
      : [...state.selectedOutlineIds, id];
    render();
  }

  if (action === "merge-outline" && script) {
    mergeSelectedOutlines(script);
    scheduleSave();
    render();
  }

  if (action === "confirm-outline") {
    runGeneration("characters");
  }

  if (action === "generate-characters") {
    runGeneration("characters");
  }

  if (action === "add-character" && script) {
    script.characters.push({
      id: `char-${uid()}`,
      name: "新角色",
      gender: "其他",
      age: "25",
      role: "配角",
      personality: ["待定"],
      biography: "补充角色背景、身份与核心动机。",
      appearance: "",
      background: "",
    });
    markDownstream(script, 3);
    scheduleSave();
    render();
  }

  if (action === "delete-character" && script) {
    script.characters = script.characters.filter((item) => item.id !== button.dataset.id);
    markDownstream(script, 3);
    scheduleSave();
    render();
  }

  if (action === "set-character-gender" && script) {
    const character = script.characters.find((item) => item.id === button.dataset.id);
    if (character) character.gender = button.dataset.value;
    markDownstream(script, 3);
    scheduleSave();
    render();
  }

  if (action === "confirm-characters" || action === "generate-episodes") {
    runGeneration("episodes");
  }

  if (action === "select-episode") {
    state.selectedEpisodeId = button.dataset.id;
    scheduleSave();
    render();
  }

  if (action === "regenerate-episode" && script) {
    const ep = selectedEpisode(script);
    if (ep) {
      const next = generatedEpisodeDetails(script, ep.episodeNumber);
      Object.assign(ep, next, { id: ep.id, episodeNumber: ep.episodeNumber, versions: ep.versions || [], scriptContent: ep.scriptContent || "" });
      ep.needsUpdate = true;
      toast("当前集规划已重新生成，已有正文会被标记为待更新。");
      scheduleSave();
      render();
    }
  }

  if (action === "enter-writing" && script) {
    script.currentStep = 5;
    updateCompletion(script, 85);
    ensureEpisodeSelection(script);
    scheduleSave();
    render();
  }

  if (action === "generate-episode-script") {
    runGeneration("script");
  }

  if (action === "stop-generation") {
    generationRun += 1;
    state.generation = null;
    toast("生成已停止。");
    render();
  }

  if (action === "save-version") {
    saveCurrentVersion();
  }

  if (action === "show-versions") {
    saveCurrentVersion(false);
    state.modal = { type: "versions" };
    renderPortal();
  }

  if (action === "restore-version") {
    restoreVersion(button.dataset.versionId);
  }

  if (action === "export-script") {
    exportScript();
  }

  if (action === "validate-script") {
    runValidation();
  }

  if (action === "fix-validation") {
    toast("已根据建议标记修复。真实 AI 接入后可自动改写对应段落。");
    state.modal = null;
    renderPortal();
  }

  if (action === "toggle-assistant") {
    state.assistantOpen = !state.assistantOpen;
    scheduleSave();
    render();
  }

  if (action === "quick-prompt") {
    sendAssistantMessage(button.dataset.value);
  }

  if (action === "send-chat") {
    const input = document.querySelector("[data-chat-input]");
    const value = input?.value.trim();
    if (value) sendAssistantMessage(value);
  }

  if (action === "rewrite-selection") {
    rewriteSelection(button.dataset.mode);
  }
}

function onInput(event) {
  const target = event.target;
  const script = activeScript();
  if (!script) return;

  if (target.dataset.ui === "search") {
    state.search = target.value;
    render();
    return;
  }

  if (target.dataset.bind) {
    setPath(script, target.dataset.bind, target.value);
    if (target.dataset.bind.startsWith("storyPositioning")) markDownstream(script, 1);
    scheduleSave();
  }

  if (target.dataset.planField) {
    const plan = selectedPlan(script);
    if (plan) {
      plan[target.dataset.planField] = target.value;
      markDownstream(script, 2);
      scheduleSave();
    }
  }

  if (target.dataset.characterField) {
    const character = script.characters.find((item) => item.id === target.dataset.id);
    if (!character) return;
    const field = target.dataset.characterField;
    if (field === "personalityText") {
      character.personality = target.value.split(/[、,，]/).map((item) => item.trim()).filter(Boolean);
    } else {
      character[field] = target.value;
    }
    markDownstream(script, 3);
    scheduleSave();
  }

  if (target.dataset.episodeField) {
    const episode = selectedEpisode(script);
    if (!episode) return;
    episode[target.dataset.episodeField] = target.value;
    episode.needsUpdate = true;
    markDownstream(script, 4);
    scheduleSave();
  }

  if (target.dataset.scriptEditor !== undefined) {
    const episode = selectedEpisode(script);
    if (!episode) return;
    episode.scriptContent = target.innerText.trim();
    updateScriptCompletion(script);
    scheduleSave();
  }
}

function onKeyDown(event) {
  if (event.key === "Enter" && event.target.matches("[data-chat-input]")) {
    event.preventDefault();
    const value = event.target.value.trim();
    if (value) sendAssistantMessage(value);
  }
}

async function runGeneration(kind) {
  const script = activeScript();
  if (!script) return;
  generationRun += 1;
  const runId = generationRun;
  const meta = generationMeta(kind, script);
  state.generation = { active: true, kind, text: "", progress: 3, ...meta };
  render();

  const text = generationText(kind, script);
  for (let i = 0; i < text.length; i += 18) {
    if (runId !== generationRun) return;
    state.generation.text += text.slice(i, i + 18);
    state.generation.progress = Math.min(96, Math.round((i / text.length) * 100));
    render();
    await sleep(28);
  }

  if (runId !== generationRun) return;
  applyGeneratedResult(kind, script, text);
  state.generation = null;
  scheduleSave();
  render();
}

function generationMeta(kind) {
  const data = {
    outline: { title: "AI 正在为您构思剧本大纲…", subtitle: "梳理起承转合、核心冲突与反转节奏，生成完整故事骨架" },
    characters: { title: "AI 正在搭建角色关系…", subtitle: "提取主角欲望、反派压力与配角功能，让角色服务剧情推进" },
    episodes: { title: "AI 正在拆解分集规划…", subtitle: "为每集配置目标、冲突、转折和结尾钩子" },
    script: { title: "AI 正在生成本集正文…", subtitle: "按短剧格式逐字输出场景、动作、对白和转场" },
  };
  return data[kind];
}

function generationText(kind, script) {
  if (kind === "outline") {
    const tags = [...script.storyPositioning.genres, ...script.storyPositioning.coreElements, ...script.storyPositioning.emotionalTone].join("、") || "强冲突、快节奏";
    return `正在读取作品定位：${script.name || "未命名剧本"}。\n已识别核心标签：${tags}。\n\n方案一将突出开篇强反杀和持续升级的爽点；方案二强化权谋布局与身份隐藏；方案三保留情感误会与开放式余韵。\n\n正在生成多方案大纲、关键人物弧线和第一季钩子...`;
  }
  if (kind === "characters") {
    return "正在从大纲中抽取主角目标、反派压迫、女主秘密与配角功能。\n\n已建立角色关系：主角负责复仇与成长，女主承载前世误会，反派推动外部压迫，配角负责资源和信息。\n\n正在补充人物小传、外貌设定与隐藏动机...";
  }
  if (kind === "episodes") {
    return "正在拆解分集节奏。\n\n前 3 集用于建立主角重生、夺回资源、暴露旧敌线索；中段通过宗门、黑市和家族内斗连续升级；后段集中回收天界阴谋与前世背叛真相。\n\n正在为每集生成目标、冲突和结尾钩子...";
  }
  const ep = selectedEpisode(script);
  return makeScriptContent(script, ep);
}

function applyGeneratedResult(kind, script, text) {
  if (kind === "outline") {
    script.storyOutline.plans = makeOutlinePlans(script);
    script.storyOutline.selectedPlanIndex = 0;
    state.selectedOutlineIds = script.storyOutline.plans.slice(0, 2).map((plan) => plan.id);
    script.currentStep = 2;
    updateCompletion(script, 45);
    toast("故事大纲已生成。");
  }
  if (kind === "characters") {
    script.characters = makeCharacters();
    script.currentStep = 3;
    updateCompletion(script, 65);
    toast("角色体系已生成。");
  }
  if (kind === "episodes") {
    const count = Math.max(1, Math.min(Number(script.storyPositioning.episodeCount) || 10, 50));
    script.episodes = Array.from({ length: count }, (_, index) => {
      const num = index + 1;
      const generated = generatedEpisodeDetails(script, num);
      return makeEpisode(num, generated.title, generated.goal, generated.conflict, generated.hook);
    });
    state.selectedEpisodeId = script.episodes[0]?.id || "";
    script.currentStep = 4;
    updateCompletion(script, 80);
    toast("分集规划已生成。");
  }
  if (kind === "script") {
    const episode = selectedEpisode(script);
    if (!episode) return;
    episode.scriptContent = text;
    episode.needsUpdate = false;
    episode.versions = episode.versions || [];
    episode.versions.unshift({
      id: `version-${uid()}`,
      versionNumber: episode.versions.length + 1,
      content: text,
      savedAt: formatDate(new Date()),
      type: "AUTO",
    });
    updateScriptCompletion(script);
    toast(`第${episode.episodeNumber}集正文已生成。`);
  }
  script.updatedAt = formatDate(new Date());
}

function makeOutlinePlans(script) {
  const title = script.name || "未命名剧本";
  const genre = script.storyPositioning.genres[0] || "都市";
  const core = script.storyPositioning.coreElements[0] || "逆袭";
  return [
    {
      id: `plan-${uid()}`,
      title: "方案一",
      label: "偏爽感",
      content: `故事背景设定\n\n《${title}》发生在${genre}世界。主角原本被家族视作弃子，却在一次致命陷害中觉醒前世记忆，发现自己被卷入横跨数代的阴谋。\n\n主要人物介绍\n\n主角外冷内狠，目标明确；女主掌握关键线索，却因立场冲突与主角反复试探；反派代表既得利益集团，持续制造资源封锁和名誉打压。\n\n核心矛盾/冲突\n\n${core}不是单纯的金手指，而是主角重新拿回主动权的方式。每次胜利都会揭开更高层敌人的存在。\n\n主线发展脉络\n\n前期用强反杀建立爽点，中期通过资源争夺和关系误会制造连续转折，后期让主角直面真正幕后黑手。\n\n高潮与结局\n\n最终主角不再只是复仇，而是重构规则，让所有曾经压迫他的人付出代价。`,
      generatedAt: formatDate(new Date()),
    },
    {
      id: `plan-${uid()}`,
      title: "方案二",
      label: "偏悬疑",
      content: `故事背景设定\n\n《${title}》从一桩看似普通的家族事故开局。主角发现自己的死亡、重生和身边人的背叛都指向同一个被抹去的秘密组织。\n\n主要人物介绍\n\n主角擅长伪装与布局，女主似敌似友，配角中有人负责提供资源，有人则可能是埋藏更深的卧底。\n\n核心矛盾/冲突\n\n主角必须一边隐藏真实能力，一边反向调查真相。每当他接近答案，身边就会出现新的牺牲者。\n\n主线发展脉络\n\n前期建立谜团，中期通过多次反转让观众怀疑每个角色，后期揭示幕后操盘者与主角前史相关。\n\n高潮与结局\n\n主角以自己为诱饵，引出真正掌控命运的人，完成一次既是复仇也是自我救赎的终局。`,
      generatedAt: formatDate(new Date()),
    },
    {
      id: `plan-${uid()}`,
      title: "方案三",
      label: "偏情感",
      content: `故事背景设定\n\n《${title}》把主角的成长与一段被误解的旧情绑定。主角以为自己被至亲背叛，却在重来一次后不断发现当年的选择另有隐情。\n\n主要人物介绍\n\n主角背负复仇执念，女主背负不能说的秘密，反派则利用两人的误会扩大裂痕。\n\n核心矛盾/冲突\n\n复仇与信任互相拉扯。主角越强大，越必须面对自己可能误判了最重要的人。\n\n主线发展脉络\n\n前期以误会推动冲突，中期用事件逼迫二人合作，后期揭示真相后转为共同对抗宿命。\n\n高潮与结局\n\n结局保留强情绪爆点：主角做出选择，不再被仇恨驱使，而是亲手打破旧循环。`,
      generatedAt: formatDate(new Date()),
    },
  ];
}

function generatedEpisodeDetails(script, num) {
  const titles = ["意外开局", "关系试探", "危机升级", "旧部线索", "宗门选拔", "黑市交易", "身份暴露", "前世疑云", "反派围猎", "天门初现"];
  const title = titles[(num - 1) % titles.length] + (num > 10 ? ` ${num}` : "");
  return {
    title,
    goal: `第${num}集围绕“${title}”推进，让主角拿到一个阶段性筹码，同时暴露更高层阻力。`,
    conflict: `主角必须在资源不足、身份被怀疑和外部压迫中完成选择。对手会使用更直接的手段逼迫他露出底牌。`,
    hook: `结尾留下下一集钩子：一个来自前世的标记突然出现，证明当前危机不是偶然。`,
  };
}

function makeScriptContent(script, ep) {
  const hero = script.characters[0]?.name || "楚渊";
  const rival = script.characters[2]?.name || "楚万山";
  const heroine = script.characters[1]?.name || "凤凌雪";
  return `【场景一：楚家祭台 · 夜】\n（暴雨倾盆，青铜祭鼎里燃着幽蓝火焰。${hero}被铁链锁在阵心，脸色苍白，却缓缓睁开眼。）\n\n${rival}\n最后一缕灵脉抽出来，楚家的祭阵就成了。一个废物，能为家族死，也算有用。\n\n${hero}\n（三百年的记忆在眼底翻涌，他抬头，声音很轻。）\n你们用我的血开阵，问过我了吗？\n\n【场景二：祭台阵心 · 连续】\n（铁链骤然绷断。阵纹倒卷，原本涌向祭鼎的灵力反冲回${hero}体内。）\n\n${rival}\n不可能！你明明已经没有灵脉！\n\n${hero}\n我失去的东西，从来不是你们能拿稳的。\n\n（${hero}一步踏出，祭台碎裂。跪在四周的族人惊恐后退。）\n\n${hero}\n今日开始，欠我的，按命来还。\n\n转场：远处阁楼。\n\n【场景三：凤家观礼席 · 夜】\n（${heroine}隔着雨幕望向祭台，指尖微颤。她不认识眼前这个少年，却在他抬眼的一瞬间感到心口刺痛。）\n\n${heroine}\n为什么……像是在哪里见过他？\n\n（她袖中一枚残破凤纹玉佩突然发光。）\n\n【结尾钩子】\n（${hero}踩碎祭鼎，鼎底露出三百年前天界才有的金色阵纹。他眼神骤冷。）\n\n${hero}\n原来你们也下来了。`;
}

function mergeSelectedOutlines(script) {
  const selected = script.storyOutline.plans.filter((plan) => state.selectedOutlineIds.includes(plan.id));
  if (!selected.length) {
    toast("请至少选择一个方案用于融合。");
    return;
  }
  const merged = {
    id: `plan-${uid()}`,
    title: `融合方案`,
    label: "综合强化",
    content: selected.map((plan) => plan.content.split("\n\n")[0]).join("\n\n") + "\n\nAI 融合建议：保留最强开篇冲突，使用悬疑线推动中段反转，并把情感误会留到后段爆发，让爽点、谜团和情绪同时服务主线。",
    generatedAt: formatDate(new Date()),
  };
  script.storyOutline.plans.push(merged);
  script.storyOutline.selectedPlanIndex = script.storyOutline.plans.length - 1;
  state.outlineTab = "edit";
  toast("已融合所选方案。");
}

function saveCurrentVersion(showToast = true) {
  const script = activeScript();
  if (!script) return;
  if (script.currentStep === 2) {
    const plan = selectedPlan(script);
    if (plan) {
      script.storyOutline.versions.unshift({
        id: `outline-version-${uid()}`,
        content: plan.content,
        savedAt: formatDate(new Date()),
        type: "MANUAL",
      });
    }
  } else if (script.currentStep === 5) {
    const ep = selectedEpisode(script);
    if (ep?.scriptContent) {
      ep.versions.unshift({
        id: `version-${uid()}`,
        versionNumber: ep.versions.length + 1,
        content: ep.scriptContent,
        savedAt: formatDate(new Date()),
        type: "MANUAL",
      });
    }
  }
  scheduleSave();
  if (showToast) toast("版本快照已保存。");
}

function collectVersions(script) {
  const outlineVersions = (script.storyOutline.versions || []).map((version, index) => ({
    id: version.id,
    title: `大纲版本 ${index + 1}`,
    savedAt: version.savedAt,
    type: version.type,
  }));
  const episodeVersions = script.episodes.flatMap((episode) => (episode.versions || []).map((version) => ({
    id: version.id,
    title: `第${episode.episodeNumber}集 · 版本 ${version.versionNumber}`,
    savedAt: version.savedAt,
    type: version.type,
  })));
  return [...outlineVersions, ...episodeVersions].sort((a, b) => b.savedAt.localeCompare(a.savedAt));
}

function restoreVersion(versionId) {
  const script = activeScript();
  const outlineVersion = script.storyOutline.versions.find((version) => version.id === versionId);
  if (outlineVersion) {
    const plan = selectedPlan(script);
    if (plan) plan.content = outlineVersion.content;
    markDownstream(script, 2);
  }
  for (const episode of script.episodes) {
    const version = episode.versions.find((item) => item.id === versionId);
    if (version) {
      episode.scriptContent = version.content;
      state.selectedEpisodeId = episode.id;
      script.currentStep = 5;
    }
  }
  state.modal = null;
  toast("已恢复所选版本。");
  scheduleSave();
  render();
}

function exportScript() {
  const script = activeScript();
  if (!script) return;
  const plan = selectedPlan(script);
  const lines = [
    `作品名称：${script.name}`,
    "",
    "一、故事大纲",
    plan?.content || "未生成",
    "",
    "二、角色设定",
    ...script.characters.map((character) => `${character.name}（${character.role}）：${character.biography}`),
    "",
    "三、分集规划与正文",
    ...script.episodes.flatMap((episode) => [
      `第${episode.episodeNumber}集 ${episode.title}`,
      `目标：${episode.goal}`,
      `冲突：${episode.conflict}`,
      `钩子：${episode.hook}`,
      episode.scriptContent || "正文未生成",
      "",
    ]),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${script.name || "剧本"}.txt`;
  link.click();
  URL.revokeObjectURL(url);
  toast("已导出 TXT 剧本。");
}

function runValidation() {
  const script = activeScript();
  const generated = script.episodes.filter((episode) => episode.scriptContent);
  state.modal = {
    type: "validation",
    items: [
      {
        type: "角色一致性",
        severity: generated.length ? "INFO" : "WARNING",
        episodeNumber: selectedEpisode(script)?.episodeNumber || 1,
        description: generated.length ? "当前主角行为与“隐忍、果断”的设定基本一致。" : "尚未生成正文，无法完成完整校验。",
        suggestion: generated.length ? "后续集可继续强化主角对前世阴谋的判断能力。" : "先生成至少一集正文后再次校验。",
      },
      {
        type: "伏笔回收",
        severity: "INFO",
        episodeNumber: 1,
        description: "金色阵纹可以作为天界旧敌线索，在第 3-5 集继续出现。",
        suggestion: "建议在下一集让凤凌雪对阵纹产生异常反应。",
      },
    ],
  };
  renderPortal();
}

function sendAssistantMessage(value) {
  const script = activeScript();
  script.aiConversation = script.aiConversation || [];
  script.aiConversation.push({ id: uid(), role: "user", step: script.currentStep, content: value, appliedToContent: false });
  script.aiConversation.push({
    id: uid(),
    role: "ai",
    step: script.currentStep,
    content: assistantReply(value, script.currentStep),
    appliedToContent: false,
  });
  scheduleSave();
  render();
}

function assistantReply(value, step) {
  const prefix = {
    1: "建议把题材、核心元素和情绪各控制在 2-4 个，避免定位过散。",
    2: "可以保留当前大纲的强冲突开篇，同时把中段反转提前到第 3 集末尾。",
    3: "角色关系建议增加“共同秘密”或“不可说的旧债”，这样后续分集更容易制造钩子。",
    4: "分集节奏可以按“开局压迫、短胜利、再压迫、信息反转”的节拍推进。",
    5: "这段正文可以增加动作线和环境压力，让对白不要单独承担戏剧张力。",
  };
  return `${prefix[step]}\n\n针对“${value}”，我会优先加强冲突、明确角色欲望，并把下一集钩子留在段落末尾。`;
}

function rewriteSelection(mode) {
  const script = activeScript();
  const episode = selectedEpisode(script);
  if (!episode || !state.selection?.text) return;
  const original = state.selection.text.trim();
  let replacement = original;
  if (mode === "rewrite") replacement = `${original}（这句话被重新整理为更直接的戏剧表达。）`;
  if (mode === "expand") replacement = `${original} 周围的空气仿佛凝住，旁人的呼吸声都变得清晰，压力一点点压向角色。`;
  if (mode === "shorten") replacement = original.split(/[，。,.]/)[0] || original;
  if (mode === "tense") replacement = `${original} 话音未落，门外忽然传来急促脚步声，危险已经逼近。`;
  episode.scriptContent = episode.scriptContent.replace(original, replacement);
  state.selection = null;
  scheduleSave();
  render();
  toast("已应用局部改写。");
}

function captureSelection() {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || !selection.toString().trim()) {
    if (state.selection) {
      state.selection = null;
      renderPortal();
    }
    return;
  }
  const anchor = selection.anchorNode?.parentElement;
  if (!anchor?.closest?.("[data-script-editor]")) return;
  const range = selection.getRangeAt(0);
  const rect = range.getBoundingClientRect();
  state.selection = {
    text: selection.toString(),
    x: Math.max(12, rect.left),
    y: Math.max(12, rect.top - 48),
  };
  renderPortal();
}

function quickPrompts(step) {
  return {
    1: ["推荐题材组合", "热门标签", "加强爽点"],
    2: ["换个方向", "加强冲突", "改成开放式结局", "融合方案"],
    3: ["增加反派", "调整角色关系", "让男主更腹黑"],
    4: ["增加反转", "调整节奏", "加一集过渡"],
    5: ["对白太平", "增加环境描写", "氛围更紧张"],
  }[step] || [];
}

function filteredScripts() {
  const keyword = state.search.trim().toLowerCase();
  if (!keyword) return state.scripts;
  return state.scripts.filter((script) => script.name.toLowerCase().includes(keyword));
}

function activeScript() {
  return state.scripts.find((script) => script.id === state.activeScriptId) || state.scripts[0];
}

function selectedPlan(script) {
  return script.storyOutline.plans?.[script.storyOutline.selectedPlanIndex] || script.storyOutline.plans?.[0];
}

function selectedEpisode(script) {
  return script.episodes.find((episode) => episode.id === state.selectedEpisodeId) || script.episodes[0];
}

function ensureEpisodeSelection(script) {
  if (!script.episodes?.length) return;
  if (!script.episodes.find((episode) => episode.id === state.selectedEpisodeId)) {
    state.selectedEpisodeId = script.episodes[0].id;
  }
}

function setPath(target, path, value) {
  const parts = path.split(".");
  let node = target;
  for (let i = 0; i < parts.length - 1; i += 1) node = node[parts[i]];
  const key = parts.at(-1);
  node[key] = key === "episodeCount" ? Number(value) : value;
}

function markDownstream(script, fromStep) {
  if (fromStep <= 1 && script.storyOutline.plans.length) {
    script.episodes.forEach((episode) => { episode.needsUpdate = true; });
  }
  if (fromStep <= 2 && script.characters.length) {
    script.episodes.forEach((episode) => { episode.needsUpdate = true; });
  }
  if (fromStep <= 4) {
    script.episodes.forEach((episode) => {
      if (episode.scriptContent) episode.needsUpdate = true;
    });
  }
}

function hasPendingDownstream(script) {
  return script.episodes?.some((episode) => episode.needsUpdate);
}

function updateCompletion(script, value) {
  script.completionRate = Math.max(script.completionRate || 0, value);
}

function updateScriptCompletion(script) {
  const total = Math.max(1, script.episodes.length);
  const done = script.episodes.filter((episode) => episode.scriptContent).length;
  script.completionRate = Math.min(100, Math.round(80 + (done / total) * 20));
}

function formatScriptHtml(text) {
  return text.split("\n").map((line) => {
    const safe = escapeHtml(line);
    if (!line.trim()) return "<br>";
    if (/^(转场|【结尾钩子】)/.test(line)) return `<span class="transition-line">${safe}</span>`;
    if (/^【/.test(line)) return `<span class="scene-line">${safe}</span>`;
    if (/^[\u4e00-\u9fa5]{2,5}$/.test(line.trim())) return `<span class="character-line">${safe}</span>`;
    if (/^（|^\(/.test(line.trim())) return `<span class="action-line">${safe}</span>`;
    return `<span>${safe}</span>`;
  }).join("\n");
}

function firstChar(value) {
  return (value || "未").trim().slice(0, 1);
}

function statusText(status) {
  return { CREATING: "创作中", DRAFT: "草稿", COMPLETED: "已完成" }[status] || status || "草稿";
}

function coverGradient(name) {
  const gradients = [
    "linear-gradient(150deg, #13912d 0%, #07575a 100%)",
    "linear-gradient(150deg, #2254a8 0%, #0a6b73 100%)",
    "linear-gradient(150deg, #6d3a9f 0%, #0f6b62 100%)",
    "linear-gradient(150deg, #8a5419 0%, #0b6460 100%)",
  ];
  const index = [...(name || "")].reduce((sum, char) => sum + char.charCodeAt(0), 0) % gradients.length;
  return gradients[index];
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value = "") {
  return escapeHtml(value);
}

function formatDate(date) {
  const pad = (num) => String(num).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function uid() {
  return Math.random().toString(36).slice(2, 9);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function toast(message) {
  state.toasts.push(message);
  renderPortal();
  setTimeout(() => {
    state.toasts.shift();
    renderPortal();
  }, 2600);
}
