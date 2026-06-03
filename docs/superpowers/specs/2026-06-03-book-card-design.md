# 书本卡片设计文档

**日期**：2026-06-03  
**范围**：首页剧本卡片重设计 + AI 书名/封面生成

---

## 背景

当前首页卡片是普通矩形卡，封面区为纯渐变色 + 首字母。  
目标：改成立体书本样式，强化"剧本创作工坊"的沉浸感，并支持 AI 生成专属书名和封面图。

---

## 视觉设计

### 静止状态（25° 倾斜）

```
书架视角，书本绕 Y 轴旋转约 25°：

┌──┬─────────────┐
│脊│  封面（透视）│
│  │  水墨纹理   │
│  │  书名竖排   │
└──┴─────────────┘
```

- 用 CSS `perspective` + `rotateY(25deg)` 实现
- 左侧书脊：宽 36px，颜色比封面暗 30%（`brightness(0.7)` filter），书名竖排 11px，底部显示进度步骤
- 封面：`card-texture.png` 平铺叠加渐变，书名竖排居中
- 整体有轻微投影，像书架上摆放的书

### Hover 状态（拉正展开）

```
书本从书架抽出，正面朝向用户：

┌────────────────────┐  ← translateY(-12px) 上浮 + 阴影加深
│   [封面图 or 水墨]  │
│    书 名（2-4字）   │
│   竖排居中显示      │
│ ─────────────────  │
│ 第N步 · YYYY-MM-DD │
│ [打开]  [✦书名][✦封面] │  ← 操作按钮 fade in
└────────────────────┘
```

- transition：`transform 0.35s cubic-bezier(0.25, 0.46, 0.45, 0.94)`
- hover：`rotateY(0deg) translateY(-12px)`，阴影从 `0 4px 16px` 增强至 `0 16px 40px`
- 操作按钮区在 hover 时 `opacity: 0 → 1`，`translateY(4px → 0)`

### 封面占位（无 AI 图）

- 背景：`coverGradient(script.name)` 彩色渐变（复用现有函数）
- 叠加：`card-texture.png` 平铺，opacity 0.12，`mix-blend-mode: overlay`
- 书名：有 `bookTitle` 用它竖排显示；否则截取剧本名前 4 字

---

## 数据模型

### 新增 script 字段

```js
bookTitle: "",       // AI 生成短书名（2-4字），空字符串表示未生成
coverImageUrl: "",   // AI 生成封面图 URL，空字符串表示未生成
```

### 前端持久化

`scriptToServerPayload`：
```js
bookTitle: script.bookTitle || "",
coverImageUrl: script.coverImageUrl || "",
```

`serverProjectToScript`：
```js
bookTitle: data.bookTitle || "",
coverImageUrl: data.coverImageUrl || "",
```

### DB 字段

在 `projects` 表 upsert 时增加：
```python
"book_title":     data.get("bookTitle", ""),
"cover_image_url": data.get("coverImageUrl", ""),
```

`_row_to_proj` 读取时还原：
```python
"bookTitle":      row.get("book_title", ""),
"coverImageUrl":  row.get("cover_image_url", ""),
```

---

## AI 功能

### 生成书名

- **触发**：hover 卡片 → 点击 `✦ 书名` 按钮
- **端点**：`POST /api/project/:id/generate-book-title`
- **输入**：`{ title: script.name, worldbuilding?: string }`
- **Prompt**：根据剧本名和世界观，生成一个 2-4 个汉字的书名，要求简洁有力、富有意境，只返回书名本身，不要任何解释
- **输出**：`{ bookTitle: "xxx" }`
- **状态**：生成中书脊显示小 spinner，完成后立即写入 `script.bookTitle`，`persist()`

### 生成封面图

- **触发**：hover 卡片 → 点击 `✦ 封面` 按钮
- **端点**：`POST /api/project/:id/generate-cover`
- **输入**：`{ bookTitle, worldbuilding? }`
- **尺寸**：512×768（竖版，DashScope wan2.7-image-pro）
- **Prompt 模板**：`{书名}，古风插画书籍封面，竖版，精致装帧，水墨渲染，金色细线边框，留白构图，高清`
- **存储**：上传至 Supabase `character-images` bucket（复用现有 bucket），路径 `{pid}/cover_{timestamp}.webp`
- **状态**：生成中封面显示 spinner overlay，完成后写入 `script.coverImageUrl`，`persist()`

---

## 组件结构

### HTML 结构（renderScriptGrid）

```html
<article class="script-card book-card">
  <div class="book-spine">
    <span class="spine-title">{bookTitle || name.slice(0,4)}</span>
    <span class="spine-step">S{step}</span>
  </div>
  <div class="book-cover">
    <!-- 封面图 or 占位 -->
    <div class="book-cover-img" style="background-image:url(...)">
      <div class="cover-texture"></div>
      <span class="book-title-vert">{bookTitle || name.slice(0,4)}</span>
    </div>
    <!-- hover 时显示 -->
    <div class="book-info">
      <div class="book-meta">第{step}步 · {date}</div>
      <div class="book-actions">
        <button data-action="open-script">打开</button>
        <button data-action="gen-book-title">✦ 书名</button>
        <button data-action="gen-book-cover">✦ 封面</button>
      </div>
    </div>
  </div>
</article>
```

### CSS 关键规则

```css
.scripts-grid {
  perspective: 1200px;
}

.book-card {
  transform: rotateY(25deg);
  transform-style: preserve-3d;
  transition: transform 0.35s cubic-bezier(0.25, 0.46, 0.45, 0.94),
              box-shadow 0.35s ease;
}

.book-card:hover {
  transform: rotateY(0deg) translateY(-12px);
  box-shadow: 0 16px 40px rgba(0,0,0,0.5);
}

.book-info {
  opacity: 0;
  transform: translateY(6px);
  transition: opacity 0.2s, transform 0.2s;
}

.book-card:hover .book-info {
  opacity: 1;
  transform: translateY(0);
}
```

---

## 受影响文件

| 文件 | 改动 |
|------|------|
| `app.js` | `renderScriptGrid`、`createBlankScript`、`serverProjectToScript`、`scriptToServerPayload`、onClick handler 新增两个 action |
| `styles.css` | 新增 `.book-card`、`.book-spine`、`.book-cover`、`.book-title-vert`、`.book-info`、`.book-actions` 等 |
| `server.py` | 新增 `/api/project/:id/generate-book-title`、`/api/project/:id/generate-cover` 端点；`_save_proj` / `_row_to_proj` 增加两个字段 |

---

## 不在本次范围内

- 列表视图（table view）的书本样式改造
- 书本翻页动画（3D flip）
- 批量生成书名/封面
