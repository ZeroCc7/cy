# 角色管理与图片功能设计

## 目标

在世界观阶段之后，为每个项目维护一组角色卡。支持 AI 自动提取、手动增删改、图片上传和 AI 生图。角色数据随项目持久化到 Supabase。

---

## 数据模型

### projects 表新增列

```sql
ALTER TABLE projects ADD COLUMN characters JSONB DEFAULT '[]';
```

### 角色对象结构

```json
{
  "id": "char_1748200000000",
  "name": "凌霄",
  "role": "protagonist",
  "personality": "冷傲外表下隐藏温柔，极度护短",
  "appearance": "白发银眸，常着玄色长袍，左手有血色印记",
  "imageUrl": null
}
```

字段说明：
- `id`：`"char_" + Date.now()`，客户端生成
- `role`：枚举值 `protagonist` | `antagonist` | `supporting`
- `imageUrl`：Supabase Storage 公开 URL，无图为 `null`

### Supabase Storage

- bucket 名：`character-images`，Public 读取
- 文件路径：`{project_id}/{character_id}.webp`
- 删除角色时同步删除 Storage 中对应文件（若存在）

---

## 后端接口

### 新增接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/project/{pid}/extract-characters` | AI 从世界观文本提取角色，同步返回 JSON 数组 |
| `POST` | `/api/project/{pid}/characters/{cid}/upload-image` | 上传图片文件到 Supabase Storage，返回 URL |
| `POST` | `/api/project/{pid}/characters/{cid}/generate-image` | 调 DashScope Wanx 生图，上传到 Storage，返回 URL |

### 扩展现有接口

`PATCH /api/project/{pid}` 新增 `field='characters'` 分支：

```python
elif field == "characters":
    db.table("projects").update({
        "characters": body["characters"], "updated": now
    }).eq("id", pid).execute()
```

### extract-characters 接口

同步调用 OpenAI client（非流式），system 使用 `CHARACTER_EXTRACT_SYSTEM`，user 消息包含世界观全文。AI 输出纯 JSON 数组，后端解析后直接返回 `JSONResponse`。`max_tokens=1500`。

### upload-image 接口

```python
@app.post("/api/project/{pid}/characters/{cid}/upload-image")
async def upload_character_image(pid: str, cid: str, file: UploadFile):
    data = await file.read()
    path = f"{pid}/{cid}.webp"
    db.storage.from_("character-images").upload(path, data,
        file_options={"content-type": "image/webp", "upsert": "true"})
    url = db.storage.from_("character-images").get_public_url(path)
    return {"url": url}
```

### generate-image 接口

```python
@app.post("/api/project/{pid}/characters/{cid}/generate-image")
async def generate_character_image(pid: str, cid: str, req: Request):
    body = await req.json()
    appearance = body.get("appearance", "")
    prompt = f"{appearance}，古装写实风格，精致面部，电影质感，高清竖版半身像"
    # 调 DashScope wanx2.1-t2i-turbo 同步接口
    resp = client.images.generate(
        model="wanx2.1-t2i-turbo",
        prompt=prompt,
        size="768*1024",
        n=1,
    )
    image_url = resp.data[0].url
    # 下载图片并上传到 Storage
    import httpx
    img_data = httpx.get(image_url).content
    path = f"{pid}/{cid}.webp"
    db.storage.from_("character-images").upload(path, img_data,
        file_options={"content-type": "image/webp", "upsert": "true"})
    public_url = db.storage.from_("character-images").get_public_url(path)
    return {"url": public_url}
```

---

## prompts.py 新增

```python
CHARACTER_EXTRACT_SYSTEM = """你是角色信息提取助手。从世界观文档中准确提取所有角色信息，只输出 JSON，不输出其他内容。"""

CHARACTER_EXTRACT_PROMPT = """从以下世界观设定文档中提取所有角色，输出 JSON 数组。

【世界观文本】
{worldbuilding}

输出格式（纯 JSON 数组，无其他文字）：
[
  {{
    "id": "char_1",
    "name": "角色姓名",
    "role": "protagonist 或 antagonist 或 supporting",
    "personality": "性格描述，30字内",
    "appearance": "外貌描述，40字内，突出视觉特征",
    "imageUrl": null
  }}
]

注意：
- role 只能是 protagonist / antagonist / supporting 三个值之一
- 只提取有名有姓的具体角色，不提取势力/组织
- 最多提取 8 个角色"""
```

---

## 前端 UI

### 触发时机

世界观生成完毕后，`showWorldbuildingActions()` 工具栏新增「✦ 提取角色」按钮。点击调用 extract 接口，解析完成后在世界观文本下方渲染角色卡区域。

### 角色卡区域

世界观文本渲染容器下方追加 `<div id="char-section">`，包含：
- 标题行：「角色设定」+ 「+ 新增角色」按钮
- 角色卡网格：`display:grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr))`

### 角色卡片

每张卡片：
- 顶部：头像图（有 `imageUrl` 则 `<img>`，无则显示姓名首字的占位色块）
- 中部：姓名 + 角色类型徽章
- 底部：「编辑」按钮

角色类型徽章颜色：
- `protagonist` → 金色（复用 `.phase-badge` 样式）
- `antagonist` → 红色
- `supporting` → 灰色

### 编辑弹窗（modal）

点击「编辑」打开全局 modal，包含：
- 左侧：头像预览 + 「上传图片」按钮 + 「AI 生成图」按钮
- 右侧：姓名、定位（select）、性格、外貌描述（textarea）
- 底部：「删除角色」（左对齐，红色）+ 「保存」（右对齐，主色）

### 图片操作

**上传**：`<input type="file" accept="image/*">` → FormData → POST upload 接口 → 更新 `character.imageUrl` → PATCH 保存 → 刷新头像

**AI 生成**：点击按钮 → 读取 `appearance` 字段 → POST generate 接口 → 按钮显示加载动画（不阻塞 modal）→ 返回 URL → 更新头像

### 数据保存时机

每次操作（提取/新增/编辑/删除）后立即调用 `PATCH /api/project/{pid}` with `field='characters'`，静默失败。

### restoreProject() 扩展

加载已有项目时，若 `data.characters.length > 0` 且当前 phase 为 `worldbuilding` 或更后阶段，自动在世界观文本下方渲染角色卡区域。

---

## 依赖变更

`requirements.txt` 新增：
```
python-multipart>=0.0.9
httpx>=0.27.0
```

> **注意**：DashScope Wanx 图片生成是否完全兼容 OpenAI SDK 的 `client.images.generate()` 需在实现时验证。若不兼容，改用 `httpx` 直接调用 DashScope REST API：`POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis`。

---

## 不在本次范围

- 角色跨项目复用
- 角色关系图谱
- 剧本生成时将角色设定注入到 episode prompt
- 批量生成所有角色图片

---

## CSS 新增类名

```
.char-section          角色区域容器
.char-section-title    标题行
.char-grid             角色卡网格
.char-card             单张角色卡
.char-avatar           头像容器（正方形）
.char-avatar-placeholder  无图占位色块
.char-name             角色姓名
.char-role-badge       角色类型徽章
.char-edit-btn         编辑按钮

.char-modal-overlay    modal 遮罩
.char-modal            modal 容器
.char-modal-left       左侧图片区
.char-modal-right      右侧表单区
.char-img-btn          上传/生成图片按钮
```
