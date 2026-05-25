# 短视频剧本生成器

古装/玄幻短剧专项，生成可拆分为多集短视频的完整剧本。

## 快速开始

### macOS / Linux

```bash
# 0. 创建虚拟环境（首次运行需要）
python3 -m venv venv

# 1. 激活虚拟环境
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 设置 API Key
export ANTHROPIC_API_KEY=你的密钥

# 4. 运行
python main.py
```

### Windows

**PowerShell：**

```powershell
# 0. 创建虚拟环境（首次运行需要）
python -m venv venv

# 1. 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 2. 安装依赖
pip install -r requirements.txt

# 3. 设置 API Key
$env:ANTHROPIC_API_KEY="你的密钥"

# 4. 运行
python main.py
```

> 如果遇到执行策略限制，先运行：`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

**CMD：**

```cmd
:: 0. 创建虚拟环境（首次运行需要）
python -m venv venv

:: 1. 激活虚拟环境
venv\Scripts\activate.bat

:: 2. 安装依赖
pip install -r requirements.txt

:: 3. 设置 API Key
set ANTHROPIC_API_KEY=你的密钥

:: 4. 运行
python main.py
```

## 启动 Web 界面

项目提供 Web 可视化操作界面，相比 `main.py` 命令行模式更直观。

### macOS / Linux

```bash
# 0. 创建虚拟环境（首次运行需要）
python3 -m venv venv

# 1. 激活虚拟环境
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量（参考 .env 文件）
export OPENAI_API_KEY=你的密钥
export OPENAI_BASE_URL=你的API地址
export OPENAI_MODEL_ID=模型ID

# 4. 启动服务
uvicorn server:app --reload
```

浏览器打开 http://127.0.0.1:8000

### Windows

**PowerShell：**

```powershell
# 0. 创建虚拟环境（首次运行需要）
python -m venv venv

# 1. 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量（参考 .env 文件）
$env:OPENAI_API_KEY="你的密钥"
$env:OPENAI_BASE_URL="你的API地址"
$env:OPENAI_MODEL_ID="模型ID"

# 4. 启动服务
uvicorn server:app --reload
```

浏览器打开 http://127.0.0.1:8000

> 如果遇到执行策略限制，先运行：`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

**CMD：**

```cmd
:: 0. 创建虚拟环境（首次运行需要）
python -m venv venv

:: 1. 激活虚拟环境
venv\Scripts\activate.bat

:: 2. 安装依赖
pip install -r requirements.txt

:: 3. 配置环境变量（参考 .env 文件）
set OPENAI_API_KEY=你的密钥
set OPENAI_BASE_URL=你的API地址
set OPENAI_MODEL_ID=模型ID

:: 4. 启动服务
uvicorn server:app --reload
```

浏览器打开 http://127.0.0.1:8000

## 工作流程

```
聊需求 → 生成大纲 → 逐集生成剧本 → 导出文件
```

1. **聊需求**：和 AI 对话，描述你想要的故事（主角、世界观、爽点等）
2. **确认大纲**：AI 生成 10-20 集大纲，可修改或重新生成
3. **生成剧本**：逐集生成，每集约 1-3 分钟时长
4. **导出文件**：每集单独保存为 `.md` 文件，另有完整版合集

## 输出格式

```
scripts/
├── 00_大纲_故事标题.md      # 完整大纲
├── 01_第1集_集标题.md       # 分集剧本
├── 02_第2集_集标题.md
├── ...
└── 完整剧本_标题_时间戳.md  # 合集版本
```

每集剧本包含：
- 开场钩子（前3秒抓眼球）
- 分场景对白 + 旁白 + 动作描述
- 结尾钩子（悬念/反转，让观众看下一集）
- 下集预告关键词

## 环境要求

- Python 3.10+
- Anthropic API Key（[获取地址](https://console.anthropic.com)）
