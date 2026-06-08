-- 幕启 Script Studio PostgreSQL 初始化脚本
-- 用法：
--   psql "postgresql://postgres:password@127.0.0.1:5432/muqi" -f db/init_postgres.sql

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
);

CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects (updated DESC);
