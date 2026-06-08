# PostgreSQL + 本地附件配置

后端现在支持两部分解耦：

- 项目数据：配置 `DATABASE_URL` 后使用自部署 PostgreSQL。
- 图片附件：默认使用本地 `uploads/`，通过 `/uploads/...` 访问，不再依赖 Supabase Storage。

## 环境变量

```env
DATABASE_URL=postgresql://postgres:password@127.0.0.1:5432/muqi
ATTACHMENT_STORAGE=local
UPLOAD_DIR=uploads
UPLOAD_URL_PREFIX=/uploads
```

没有配置 `DATABASE_URL` 时，项目数据仍会走 Supabase 兼容模式。

## 依赖

```powershell
pip install -r requirements.txt
```

其中 `psycopg[binary]` 用于连接 PostgreSQL。

## 数据表

服务启动时会自动创建 `projects` 表，字段与原 Supabase `projects` 表保持一致，JSON 字段使用 `jsonb`。

也可以手动执行初始化脚本：

```powershell
psql "postgresql://postgres:password@127.0.0.1:5432/muqi" -f db/init_postgres.sql
```

## 附件目录

上传或生成的角色图、封面、分镜图会保存到：

```text
uploads/<project_id>/...
```

这些文件不会提交到 Git，已加入 `.gitignore`。

## 从 Supabase 迁移

如果旧数据还在 Supabase，需要把 `projects` 表导出后导入自部署 PostgreSQL。图片旧 URL 可以继续显示；新上传和新生成的图片会使用本地 `/uploads/...`。
