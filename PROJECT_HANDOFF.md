# Dramatica-Flow Enhanced — 项目交接文档

> 最后更新：2026-04-17
> 版本：V5（V4 基础上多 LLM + 选择性审查 + WebSocket + Agent 画像可视化）
> 本文档面向所有人，尤其是零基础用户。读完就能理解整个项目、怎么用、怎么继续迭代。

---

## 一、这是什么？

**Dramatica-Flow Enhanced** 是一个 **AI 自动写小说系统**。你给它一句话设定，它帮你：

1. **市场分析** — 分析目标读者偏好（引用番茄小说真实数据）
2. **构建世界观** — 角色/势力/地点/规则，全部自动生成
3. **角色成长规划** — 每个主要角色8维档案 + 成长弧线 + 转折点
4. **情绪曲线设计** — 整书情绪起伏规划，精确操控读者情绪
5. **生成大纲** — 三幕结构 + 逐章规划 + 张力曲线
6. **自动写作** — 一章一章写，每章2000字
7. **多维审查** — 对话/场景/心理/风格，4个专项审查Agent
8. **自动审计** — 9维度加权评分 + 17条红线一票否决
9. **审查→修订闭环** — 所有审查问题合并进修订循环
10. **MiroFish读者测试** — 每5章模拟1000名读者反馈
11. **Agent能力画像** — 追踪每个Agent的工作质量

**一句话：V3 是"AI写+AI审"，V4 是"AI写+多维审+闭环改+读者测+架构重构"。**

---

## 二、项目地址

### GitHub 仓库

| 版本 | 地址 | 说明 |
|------|------|------|
| **原版** | https://github.com/ydsgangge-ux/dramatica-flow | 叙事逻辑强，但缺乏前期规划和质量管控 |
| **V1** | https://github.com/ZTNIAN/dramatica-flow-enhanced | 12个增强点完成但有6项"写了没接入" |
| **V2** | https://github.com/ZTNIAN/dramatica-flow-enhanced-v2 | 修复V1的核心问题 + 知识库扩充 |
| **V3** | https://github.com/ZTNIAN/dramatica-flow-enhanced-v3 | 全面升级：知识库+Web界面+动态规划+KB追踪 |
| **V4（当前）** | https://github.com/ZTNIAN/dramatica-flow-enhanced-v4 | 架构重构：模块化+配置化+安全加固+异步化 |

### 本地部署位置

```bash
git clone https://github.com/ZTNIAN/dramatica-flow-enhanced-v4.git
cd dramatica-flow-enhanced-v4
```

---

## 三、V1 → V2 → V3 → V4 的区别

### V1 做了什么

在原版基础上完成了12个增强点：
- 9维度加权评分 + 17条红线一票否决
- 禁止词汇清单 + 正则扫描
- 知识库目录 + 去AI味规则
- 45条写作风格约束
- Show Don't Tell 转换表
- 对比示例库
- 返工上限3次 + 监控
- 动态分层规划器
- 巡查Agent
- 质量统计仪表盘
- 知识库查询激励

**V1 的问题：12个功能中有6项写了代码但没接入管线（仪表盘、示例库注入、知识库注入等），等于"写了但没用"。**

### V2 修了什么

修复了 V1 的核心问题：
- 质量仪表盘接入管线（每章写完自动记录评分）
- 对比示例库注入 Writer prompt
- 知识库注入 Architect prompt
- LLM 重试增强（智能判断异常 + 指数退避）
- 动态规划器接入管线
- 写作技巧库扩充（61行→265行）
- 番茄小说市场数据引入（6份报告）
- 写作示例引入（6好1坏）

**V2 的问题：知识库只引入了一小部分，Agent提示词不够完整，动态规划器太基础，Web界面功能不全。**

### V3 做了什么

**V3 = V2 + 以下全部升级**

1. **知识库全量引入**（12个文件 → 30+个文件）：从 OpenMOSS 引入全部知识库
2. **Agent 提示词增强**：4个Agent注入更多知识库内容
3. **动态规划器大幅升级**：完整自适应分层公式 + 四层结构
4. **KB 查询追踪**：记录每次知识库使用
5. **Web 界面增强**：市场分析面板 + 质量仪表盘 + KB统计
6. **10个增强Agent引入**：对话/场景/心理/风格/情绪/MiroFish等

**V3 的问题：功能全了，但代码架构撑不住。**
- `server.py` 一个文件 3618 行，65个端点全堆在一起
- `agents/__init__.py` 一个文件 1428 行，9个Agent挤在一起
- `enhanced_agents.py` 1104 行，10个Agent也挤一起
- `_load_kb()` 在两个文件里重复定义
- 魔法数字散布各处，改个阈值要翻代码
- CORS 全开 `allow_origins=["*"]`
- LLM端点同步阻塞
- 错误处理全是裸 `except Exception`

### V4 做了什么

**V4 = V3 + 全面架构重构（12项优化）**

#### 优化1：公共KB模块
- 新建 `core/agents/kb.py`（67行）
- 统一 KB 加载 + 查询追踪
- 消除 `__init__.py` 和 `enhanced_agents.py` 中的重复代码

#### 优化2：agents 拆分为独立文件
- **V3**：`agents/__init__.py`（1428行）+ `enhanced_agents.py`（1104行）= 2个巨型文件
- **V4**：20个独立文件，最大339行

| 文件 | 行数 | 职责 |
|------|------|------|
| `agents/__init__.py` | 73 | re-export 入口 |
| `agents/architect.py` | 229 | 建筑师 |
| `agents/writer.py` | 302 | 写手 |
| `agents/auditor.py` | 339 | 审计员 |
| `agents/reviser.py` | 101 | 修订者 |
| `agents/summary.py` | 107 | 摘要生成 |
| `agents/patrol.py` | 147 | 巡查者 |
| `agents/worldbuilder.py` | 114 | 世界观构建 |
| `agents/outline_planner.py` | 135 | 大纲规划 |
| `agents/market_analyzer.py` | 92 | 市场分析 |
| `agents/kb.py` | 67 | 公共KB模块 |
| `agents/enhanced/character_growth.py` | 175 | 角色成长 |
| `agents/enhanced/dialogue.py` | 166 | 对话审查 |
| `agents/enhanced/emotion_curve.py` | 136 | 情绪曲线 |
| `agents/enhanced/feedback.py` | 124 | 反馈分类 |
| `agents/enhanced/style_checker.py` | 141 | 风格一致性 |
| `agents/enhanced/scene_architect.py` | 145 | 场景审核 |
| `agents/enhanced/psychological.py` | 150 | 心理描写 |
| `agents/enhanced/mirofish.py` | — | 模拟读者 |
| `agents/enhanced/methods.py` | 59 | 钩子/开篇方法论 |

#### 优化3：server.py 拆分为 routers
- **V3**：`server.py` 3618行，65个端点混在一起
- **V4**：`core/server/` 模块化，12个文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `server/__init__.py` | 107 | app实例+中间件+CORS |
| `server/deps.py` | 302 | 公共依赖+请求模型 |
| `server/routers/books.py` | 171 | 书籍CRUD |
| `server/routers/setup.py` | 102 | 世界观配置 |
| `server/routers/chapters.py` | 84 | 章节管理 |
| `server/routers/outline.py` | 152 | 大纲 |
| `server/routers/writing.py` | 236 | 写作+审计（异步化） |
| `server/routers/ai_actions.py` | 381 | AI生成 |
| `server/routers/threads.py` | 83 | 线程管理 |
| `server/routers/analysis.py` | 87 | 因果链/情感弧 |
| `server/routers/enhanced.py` | 135 | V4增强功能 |
| `server/routers/settings.py` | 77 | 设置 |
| `server/routers/export.py` | 54 | 导出 |

#### 优化4：魔法数字配置化
- 新建 `PipelineConfig` 数据类
- 10个硬编码值全部支持环境变量覆盖
- 不改代码就能调整管线行为

#### 优化5：错误处理精细化
- 11个 `except Exception as e` 全部区分错误类型
- LLM解析错误 → 记录 JSON/KeyError 详情
- IO错误 → 记录文件路径
- 未知错误 → 记录 traceback（截断到500字符）

#### 优化6：API安全加固
- **CORS**：从 `allow_origins=["*"]` 改为 localhost 白名单
- **路径遍历**：新增 `safe_book_dir()` 防止 `../` 穿越攻击
- 可通过 `CORS_ALLOW_ORIGINS` 环境变量自定义

#### 优化7：关键端点异步化
- `POST /api/action/write` → async + run_in_executor
- `POST /api/action/audit` → async + run_in_executor
- `POST /api/action/revise` → async + run_in_executor
- LLM 调用不再阻塞 FastAPI 事件循环

---

## 四、小白操作手册

### 4.1 两种用法

| | Web UI（浏览器） | CLI（命令行） |
|--|-----------------|---------------|
| 怎么打开 | 浏览器打开 http://127.0.0.1:8766/ | 终端输入 `df` 命令 |
| 适合谁 | 喜欢点按钮、看图形界面 | 喜欢敲命令、批量操作 |
| 功能 | 创建书、写章节、看状态、审计 | 同上 + 全部命令 |
| 区别 | 界面友好 | 功能最全 |

**结论：日常写作用 Web UI，前期设计用 CLI。**

### 4.2 首次部署（5步）

```bash
# 第1步：克隆项目
git clone https://github.com/ZTNIAN/dramatica-flow-enhanced-v4.git
cd dramatica-flow-enhanced-v4

# 第2步：创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate    # Linux/Mac
# .venv\Scripts\activate     # Windows

# 第3步：安装依赖
pip install -e .

# 第4步：配置API Key
cp .env.example .env
# 用编辑器打开 .env，填入你的 DeepSeek API Key
```

`.env` 文件内容：
```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的key           # 去 https://platform.deepseek.com 申请
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DEFAULT_WORDS_PER_CHAPTER=2000
DEFAULT_TEMPERATURE=0.7
AUDITOR_TEMPERATURE=0.0
BOOKS_DIR=./books
```

V4 新增可选配置（不设则用默认值）：
```env
# 管线参数（可选，不设则用默认值）
PIPELINE_MAX_REVISE_ROUNDS=3       # 最大修订轮数
PIPELINE_MIROFISH_INTERVAL=5       # MiroFish每N章触发
PIPELINE_REVIEW_SCORE_FLOOR=75     # 审查问题汇入阈值
PIPELINE_STYLE_SCORE_FLOOR=80      # 风格修正阈值
PIPELINE_AUDIT_PASS_TOTAL=95       # 审计通过分数
PIPELINE_DORMANCY_THRESHOLD=5      # 支线掉线预警章数

# 安全配置（可选）
CORS_ALLOW_ORIGINS=http://localhost:8766,http://127.0.0.1:8766
```

```bash
# 第5步：启动
# 方式A：命令行
df --help

# 方式B：Web UI
uvicorn core.server:app --reload --host 0.0.0.0 --port 8766
# 然后浏览器打开 http://127.0.0.1:8766/
```

### 4.3 日常使用流程

```bash
# 第1步：市场分析（可选）
df market 科幻 --premise "你的设定"

# 第2步：世界观构建（必做）
df worldbuild "废灵根少年觉醒上古传承逆袭" --genre 玄幻

# 第3步：大纲规划（必做）
df outline --book 生成的书名

# 第4步：开始写作
df write 书名          # CLI写一章
# 或用 Web UI 点「写作」按钮

# 第5步：查看状态
df status 书名

# 第6步：导出
df export 书名
```

### 4.4 命令速查表

| 命令 | 作用 | 什么时候用 |
|------|------|-----------|
| `df doctor` | 检查API连接 | 第一次用，或出问题时 |
| `df market 题材` | 市场分析 | 写新书前（可选） |
| `df worldbuild "设定"` | 世界观构建 | 写新书（必做） |
| `df outline --book 书名` | 大纲规划 | 世界观后（必做） |
| `df write 书名` | 写下一章 | 日常写作 |
| `df audit 书名 --chapter N` | 手动审计 | 对某章不满意时 |
| `df revise 书名 --chapter N` | 手动修订 | 审计不通过时 |
| `df status 书名` | 查看状态 | 随时 |
| `df export 书名` | 导出正文 | 写完后 |

### 4.5 Web UI 操作流程

1. 打开 http://127.0.0.1:8766/
2. 步骤1（API配置）：填入 DeepSeek API Key → 保存
3. 步骤2（创建书籍）：点「+ 创建新书籍」→ 填书名、题材
4. 步骤3（世界观）：先点「市场分析」看看读者喜好 → 然后「AI 生成世界观」→「角色成长规划」
5. 步骤4（大纲）：AI 自动生成三幕结构 + 章纲
6. 步骤5（写作）：点「写下一章」→ AI 自动写 + 多维审查 + 审计 + 修订
7. 步骤6（审计）：查看审计结果、质量仪表盘、KB统计、情绪曲线
8. 步骤7（导出）：导出为 Markdown 或 TXT

---

## 五、踩坑记录（重要！）

### 坑1：heredoc写中文文件会损坏

```bash
# ❌ 不要用
cat > file << 'EOF' 中文内容 EOF

# ✅ 用这个
python3 -c "with open('file','w') as f: f.write('中文内容')"
```

### 坑2：sed无法匹配中文字符

```bash
# ❌ 不要用
sed -i 's/中文/替换/' file

# ✅ 用这个
python3 -c "import pathlib; p=pathlib.Path('file'); p.write_text(p.read_text().replace('中文','替换'))"
```

### 坑3：Python虚拟环境报错

```bash
# 如果 pip install -e . 报 externally-managed-environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 坑4：catbox文件链接72小时过期

```bash
# 重新上传
curl -F "reqtype=fileupload" -F "time=72h" -F "fileToUpload=@文件路径" https://litterbox.catbox.moe/resources/internals/api.php
```

### 坑5：git push 经常挂（TLS 连接失败）⭐

```bash
# ❌ git push 经常卡死或报 GnuTLS recv error (-110)
git push origin main

# ✅ 用 GitHub Contents API 逐文件上传（见下方方法）
```

### 坑6：GitHub API 大文件上传报错

```bash
# ❌ shell 变量传大文件内容会报 Argument list too large
CONTENT=$(base64 -w0 huge_file.py)

# ✅ 用 Python urllib 直接调用（见下方脚本）
```

### 坑7：from ..llm 导入bug

```bash
# 从GitHub下载单文件后出现 from ..llm 报错
python3 -c "import pathlib; p=pathlib.Path('file.py'); p.write_text(p.read_text().replace('from ..llm','from .llm'))"
```

### 坑8：DeepSeek API Key安全

**API Key 不要发在聊天记录里！** 用 `.env` 文件配置。`.env` 不要提交到 git。

### 坑9：entry point 缓存

改了 `cli/main.py` 但 `df --help` 不显示新命令：
```bash
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
pip install --force-reinstall --no-deps -e .
```

### 坑10：审查Agent问题格式不统一

对话/场景/心理审查的 `issues` 是 `list[dict]`，审计的是 `list[AuditIssue]`。合并时需要转换：
```python
AuditIssue(
    dimension="对话质量",
    severity="warning",
    description=f"[{issue.get('character')}] {issue.get('description')}",
    suggestion=issue.get("suggestion", ""),
)
```

### 坑11：GitHub API 中文文件名报错

GitHub API 的 URL 路径含中文会报 `ascii codec` 错误。需要 URL encode：
```python
from urllib.parse import quote
encoded = "/".join(quote(seg, safe="") for seg in filepath.split("/"))
```

### 坑12：GitHub TLS 连接不稳定

服务器的 git/TLS 连接经常断。解决方案：
- 每次 API 调用间隔 1.5 秒
- 失败自动重试 3 次
- 大文件用 Python urllib 而非 curl

---

## 六、迭代写入方式（推荐方法）

### 为什么不推荐 git push

本服务器的 git 客户端存在 TLS 连接问题（GnuTLS recv error -110），`git push` 经常卡死。这是服务器环境问题，不是代码问题。

### 推荐方法：GitHub Contents API 逐文件上传

#### 方法1：小文件（<1MB）用 curl

```bash
TOKEN="你的GitHub Token"
REPO="ZTNIAN/dramatica-flow-enhanced-v4"
filepath="要上传的文件路径"

CONTENT=$(base64 -w0 "$filepath")
SHA=$(curl -s -H "Authorization: token $TOKEN" \
  "https://api.github.com/repos/$REPO/contents/$filepath" | \
  python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))")

DATA="{\"message\":\"update $filepath\",\"content\":\"$CONTENT\",\"branch\":\"main\""
[ -n "$SHA" ] && DATA="$DATA,\"sha\":\"$SHA\""
DATA="$DATA}"

curl -s -X PUT \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/$REPO/contents/$filepath" \
  -d "$DATA"
```

#### 方法2：大文件（>1MB）或中文路径用 Python ⭐推荐

```python
import base64, json, urllib.request, time
from urllib.parse import quote

TOKEN = "你的GitHub Token"
REPO = "ZTNIAN/dramatica-flow-enhanced-v4"
filepath = "core/pipeline.py"

# URL-encode for Chinese filenames
encoded = "/".join(quote(seg, safe="") for seg in filepath.split("/"))

with open(filepath, "rb") as f:
    content_b64 = base64.b64encode(f.read()).decode()

# Get existing sha
sha = ""
try:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/contents/{encoded}",
        headers={"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}
    )
    sha = json.loads(urllib.request.urlopen(req, timeout=10).read()).get("sha", "")
except:
    pass

data = json.dumps({
    "message": "update " + filepath,
    "content": content_b64,
    "branch": "main",
    **({"sha": sha} if sha else {}),
}).encode()

req = urllib.request.Request(
    f"https://api.github.com/repos/{REPO}/contents/{encoded}",
    data=data,
    headers={
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    },
    method="PUT"
)
result = json.loads(urllib.request.urlopen(req, timeout=20).read())
print(f"{filepath} → {result.get('commit',{}).get('sha','ERROR')[:8]}")
```

#### 方法3：批量上传

```python
import base64, json, urllib.request, time
from urllib.parse import quote

TOKEN = "你的GitHub Token"
REPO = "ZTNIAN/dramatica-flow-enhanced-v4"

def upload(filepath, content, message):
    encoded = "/".join(quote(seg, safe="") for seg in filepath.split("/"))
    content_b64 = base64.b64encode(content.encode("utf-8")).decode()
    sha = ""
    try:
        url = f"https://api.github.com/repos/{REPO}/contents/{encoded}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"
        })
        sha = json.loads(urllib.request.urlopen(req, timeout=10).read()).get("sha", "")
    except:
        pass
    data = json.dumps({
        "message": message, "content": content_b64, "branch": "main",
        **({"sha": sha} if sha else {}),
    }).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/contents/{encoded}",
        data=data, method="PUT",
        headers={
            "Authorization": f"token {TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    result = json.loads(urllib.request.urlopen(req, timeout=20).read())
    commit = result.get("commit", {}).get("sha", "ERROR")[:8]
    print(f"  ✅ {filepath} → {commit}")
    time.sleep(1.5)  # 防止速率限制

# 使用示例
with open("core/pipeline.py", "r") as f:
    upload("core/pipeline.py", f.read(), "更新管线")
```

---

## 七、V4 是怎么迭代的

### 迭代过程

V4 从 V3 出发，经历了两个阶段：

**阶段1：功能补全（原"V4增强"）**
- 用户上传 V3 交接文档 + GitHub Token
- AI 引入 10 个增强 Agent（对话/场景/心理/风格/MiroFish等）
- 新建 `core/agents/enhanced_agents.py`（1104行）
- 修改 `core/pipeline.py`（统一审查循环）
- 新增 8 个知识库指南文件

**阶段2：架构重构（原"V5优化"，合并为V4）**
- 消除代码重复（`_load_kb` → `kb.py`）
- agents 拆分为 20 个独立文件
- server.py 拆分为 12 个模块
- 魔法数字 → `PipelineConfig`
- 错误处理精细化
- CORS 加固 + 路径遍历防护
- 关键端点异步化

### 改了什么文件

**新建文件（22个）：**

| 文件 | 说明 |
|------|------|
| `core/agents/kb.py` | 公共知识库模块 |
| `core/agents/architect.py` | 建筑师Agent |
| `core/agents/writer.py` | 写手Agent |
| `core/agents/auditor.py` | 审计员Agent |
| `core/agents/reviser.py` | 修订者Agent |
| `core/agents/summary.py` | 摘要Agent |
| `core/agents/patrol.py` | 巡查Agent |
| `core/agents/worldbuilder.py` | 世界观构建Agent |
| `core/agents/outline_planner.py` | 大纲规划Agent |
| `core/agents/market_analyzer.py` | 市场分析Agent |
| `core/agents/enhanced/__init__.py` | 增强Agent re-export |
| `core/agents/enhanced/character_growth.py` | 角色成长Agent |
| `core/agents/enhanced/dialogue.py` | 对话审查Agent |
| `core/agents/enhanced/emotion_curve.py` | 情绪曲线Agent |
| `core/agents/enhanced/feedback.py` | 反馈分类Agent |
| `core/agents/enhanced/style_checker.py` | 风格一致性Agent |
| `core/agents/enhanced/scene_architect.py` | 场景审核Agent |
| `core/agents/enhanced/psychological.py` | 心理描写Agent |
| `core/agents/enhanced/mirofish.py` | 模拟读者Agent |
| `core/agents/enhanced/methods.py` | 钩子/开篇方法论 |
| `core/server/__init__.py` | app实例+中间件 |
| `core/server/deps.py` | 公共依赖 |
| `core/server/routers/` (10个文件) | 各功能路由 |

**修改文件（3个）：**

| 文件 | 改动 |
|------|------|
| `core/agents/__init__.py` | 1428行 → 73行（改为re-export入口） |
| `core/pipeline.py` | +PipelineConfig +错误处理 +async |
| `core/agents/enhanced_agents.py` | 后被删除（被enhanced/替代） |

**删除文件（2个）：**

| 文件 | 原因 |
|------|------|
| `core/server.py` | 被 `core/server/` 模块化替代 |
| `core/agents/enhanced_agents.py` | 被 `core/agents/enhanced/` 替代 |

### 代码统计

| 指标 | V3 | V4 |
|------|----|----|
| 总文件数 | 95 | 127 |
| Python文件数 | ~45 | ~65 |
| 最大文件行数 | 3618 (server.py) | 390 (narrative/__init__.py) |
| Agent相关文件 | 2个 | 21个 |
| Server相关文件 | 1个 | 13个 |

---

## 八、后续迭代流程（V5 通用模板）

每次迭代只需要做 **两件事**：

### 第1步：发交接文档

把本文件 `PROJECT_HANDOFF.md` 发给 AI。它就能读懂整个项目。

如果有新的参考资料（比如运行日志、审计报告、MiroFish测试报告），也一起发。

### 第2步：给 GitHub Token

```
New personal access token (classic)：ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**获取方法**：
1. 打开 https://github.com/settings/tokens
2. 点「Generate new token (classic)」
3. Note 填 "dramatica-flow-v5-迭代"
4. 勾选 `repo` 权限（第一个勾）
5. 点「Generate token」
6. 复制 `ghp_xxxxx` 发给 AI

**⚠️ AI 推完代码后必须立刻 revoke 这个 token！** 因为 token 会出现在聊天记录里，不安全。

### AI 会做的事

1. 读交接文档 → 理解项目
2. 在服务器上修改代码
3. 用 GitHub API 逐文件推送（因为 git push 有 TLS 问题）
4. 更新交接文档
5. 告诉你推完了

### 你只需要做

1. **Revoke token**（推完后立刻做）
2. **本地拉取最新代码**：

```bash
cd dramatica-flow-enhanced-v4
git fetch origin
git reset --hard origin/main
```

---

## 九、V5 改动清单

V5 在 V4 基础上实现了 7 项优化：

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 1 | 多LLM后端 | ✅ 完成 | 新增 Claude + GPT-4 Provider + 自动降级链 |
| 2 | 选择性审查 | ✅ 完成 | 4种模式：all/light/minimal/adaptive，环境变量控制 |
| 3 | WebSocket进度 | ✅ 完成 | `/ws/progress/{book_id}` 实时推送写作各阶段状态 |
| 4 | Agent画像可视化 | ✅ 完成 | `/api/books/{id}/agent-performance` 端点 + Web UI 趋势图 |
| 5 | .env.example | ✅ 完成 | 补齐 Claude/GPT-4/WebSocket/review mode 环境变量 |
| 6 | Web UI对齐 | ✅ 完成 | WebSocket客户端 + Agent画像Tab + 进度显示条 |
| 7 | 端到端测试 | ⏳ 待做 | 需要实际部署运行验证 |

### V5 新增文件/改动

| 文件 | 改动 |
|------|------|
| `core/llm/__init__.py` | +150行：ClaudeProvider + OpenAIProvider + FallbackProvider + PROVIDER_FACTORIES |
| `core/pipeline.py` | +30行：review_mode/adaptive配置 + _emit回调 + _should_run_review网关 |
| `core/server/__init__.py` | +40行：WSProgressManager + /ws/progress WebSocket端点 |
| `core/server/routers/enhanced.py` | +80行：agent-performance + review-stats 端点 |
| `.env.example` | +30行：Claude/GPT-4/降级链/审查模式/WebSocket配置 |
| `dramatica_flow_web_ui.html` | +100行：WebSocket客户端 + Agent画像Tab + 进度条 |

### V5 审查模式说明

通过 `PIPELINE_REVIEW_MODE` 环境变量控制：

| 模式 | 说明 | 省钱程度 |
|------|------|---------|
| `all` | 每章跑全部审查Agent（默认） | 0% |
| `light` | 只跑对话+场景审查 | ~50% |
| `minimal` | 跳过所有专项审查，只跑审计 | ~70% |
| `adaptive` | light基础上，每N章或低分章强制全量 | ~40% |

### V5 LLM 降级链

通过 `LLM_FALLBACK_CHAIN` 配置，主 Provider 失败时自动切换备用：

```env
LLM_FALLBACK_CHAIN=deepseek,claude,openai
```

支持的 Provider：deepseek / ollama / claude / openai

---

## 十、技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| 后端 | FastAPI |
| CLI | Typer |
| 数据存储 | 文件系统（JSON + Markdown） |
| LLM | DeepSeek API（默认）/ Ollama（本地免费）/ Claude / GPT-4 |
| 前端 | 单文件 HTML（暗色主题） |
| 校验 | Pydantic v2 |

---

## 十一、文件结构

```
dramatica-flow-enhanced-v4/
├── cli/main.py                          # CLI入口
├── core/
│   ├── agents/                          # Agent模块（21个文件）
│   │   ├── __init__.py                  # re-export入口
│   │   ├── kb.py                        # 公共知识库模块
│   │   ├── architect.py                 # 建筑师
│   │   ├── writer.py                    # 写手
│   │   ├── auditor.py                   # 审计员
│   │   ├── reviser.py                   # 修订者
│   │   ├── summary.py                   # 摘要
│   │   ├── patrol.py                    # 巡查
│   │   ├── worldbuilder.py              # 世界观构建
│   │   ├── outline_planner.py           # 大纲规划
│   │   ├── market_analyzer.py           # 市场分析
│   │   └── enhanced/                    # 增强Agent（10个文件）
│   │       ├── character_growth.py
│   │       ├── dialogue.py
│   │       ├── emotion_curve.py
│   │       ├── feedback.py
│   │       ├── style_checker.py
│   │       ├── scene_architect.py
│   │       ├── psychological.py
│   │       ├── mirofish.py
│   │       └── methods.py
│   ├── pipeline.py                      # 写作管线（PipelineConfig+异步）
│   ├── llm/__init__.py                  # LLM抽象层
│   ├── narrative/__init__.py            # 叙事引擎
│   ├── state/__init__.py                # 状态管理
│   ├── types/                           # 数据类型
│   ├── validators/__init__.py           # 写后验证器
│   ├── server/                          # Web服务（13个文件）
│   │   ├── __init__.py                  # app实例+中间件+CORS
│   │   ├── deps.py                      # 公共依赖+请求模型
│   │   └── routers/                     # 路由模块
│   │       ├── books.py / setup.py / chapters.py
│   │       ├── outline.py / writing.py / ai_actions.py
│   │       ├── threads.py / analysis.py / enhanced.py
│   │       ├── settings.py / export.py
│   ├── quality_dashboard.py             # 质量仪表盘
│   ├── dynamic_planner.py               # 动态规划器
│   ├── kb_incentive.py                  # KB查询激励
│   └── knowledge_base/                  # 知识库（30+文件）
│       ├── rules/ references/ agent-specific/
│       ├── examples/ fanqie-data/ indexes/
├── templates/                           # JSON配置模板
├── tests/                               # 测试
├── docs/                                # 文档
├── dramatica_flow_web_ui.html           # Web UI
├── dramatica_flow_timeline.html         # 时间轴可视化
├── pyproject.toml                       # 项目配置
├── .env.example                         # 环境变量模板
├── PROJECT_HANDOFF.md                   # 本文件
└── USER_MANUAL.md                       # 操作手册
```

---

## 十二、Agent 体系（19个Agent）

### 原有 9 个

| Agent | 职责 | 触发时机 |
|-------|------|---------|
| WorldBuilderAgent | 一句话→世界观 | `df worldbuild` |
| OutlinePlannerAgent | 大纲+章纲 | `df outline` |
| MarketAnalyzerAgent | 市场分析 | `df market` |
| ArchitectAgent | 规划单章蓝图 | 每章写前 |
| WriterAgent | 生成正文 | 每章写手 |
| PatrolAgent | 快速扫描 | 写后立即 |
| AuditorAgent | 9维加权审计 | 巡查后 |
| ReviserAgent | 修订正文 | 审计不通过 |
| SummaryAgent | 章节摘要 | 写完后 |

### V4 新增 10 个

| 优先级 | Agent | 职责 |
|--------|-------|------|
| P1 | CharacterGrowthExpert | 角色8维档案 + 成长弧线规划 |
| P1 | DialogueExpert | 对话审查 + 语言指纹六维度 |
| P1 | EmotionCurveDesigner | 整书情绪曲线 + 每章情绪类型 |
| P1 | FeedbackExpert | 读者反馈分类路由 + 闭环追踪 |
| P2 | HookDesigner | 7种章末钩子方法论（注入Architect） |
| P2 | OpeningEndingDesigner | 黄金三章 + 全书结尾（注入Architect） |
| P2 | StyleConsistencyChecker | 五维一致性检查 |
| P3 | SceneArchitect | 场景四维审核 |
| P3 | PsychologicalPortrayalExpert | 心理四维审核 |
| P3 | MiroFishReader | 1000名读者模拟 |

---

## 十三、写作管线流程

```
[市场分析]（可选）
    题材 → MarketAnalyzer → 风格指南 + 读者偏好
    ↓
[世界构建]（必做）
    一句话设定 → WorldBuilder → 世界观JSON
    ↓
[角色成长规划]
    角色列表 → CharacterGrowthExpert → 8维档案 + 成长弧线
    ↓
[情绪曲线设计]
    章节数 → EmotionCurveDesigner → 整书情绪曲线
    ↓
[大纲规划]（必做）
    世界观 → OutlinePlanner → 三幕结构 + 章纲
    ↓
[单章循环]（每章重复）
    ├── 快照备份
    ├── 建筑师：规划蓝图
    ├── 写手：生成正文 + 结算表
    ├── 对话专家审查 → 问题汇入修订循环
    ├── 验证器：零LLM硬规则扫描
    ├── 巡查者：快速扫描
    ├── 场景审核 → 问题汇入修订循环
    ├── 心理审核 → 问题汇入修订循环
    ├── 审计员：9维度加权评分
    │   └── 合并所有审查问题 → 不通过 → 修订（最多3轮）
    ├── 风格一致性检查 → 不通过则polish修正
    ├── 保存最终稿
    ├── 因果链提取 → 摘要生成 → 状态更新
    ├── 质量仪表盘记录
    ├── 动态规划器更新
    ├── KB查询统计保存
    ├── Agent能力画像记录
    └── MiroFish测试（每5章）
    ↓
[导出]
    df export → Markdown / TXT
```

---

## 十四、可配置参数

通过 `.env` 文件或环境变量设置，不设则用默认值：

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `PIPELINE_MAX_REVISE_ROUNDS` | 3 | 最大修订轮数 |
| `PIPELINE_MIROFISH_INTERVAL` | 5 | MiroFish每N章触发 |
| `PIPELINE_MIROFISH_SAMPLE_CHARS` | 3000 | MiroFish每章采样字数 |
| `PIPELINE_RECENT_SUMMARIES_N` | 3 | 前情摘要取最近N章 |
| `PIPELINE_DORMANCY_THRESHOLD` | 5 | 支线掉线预警章数 |
| `PIPELINE_REVIEW_SCORE_FLOOR` | 75 | 审查Agent问题汇入阈值 |
| `PIPELINE_STYLE_SCORE_FLOOR` | 80 | 风格一致性修正阈值 |
| `PIPELINE_AUDIT_TENSION_FLOOR` | 90 | 审计分低于此值调整张力曲线 |
| `PIPELINE_AUDIT_DIMENSION_FLOOR` | 85 | 单项维度最低分 |
| `PIPELINE_AUDIT_PASS_TOTAL` | 95 | 审计通过加权总分 |
| `CORS_ALLOW_ORIGINS` | localhost | CORS白名单（逗号分隔） |

---

*本文档由AI自动生成。下次迭代时，把本文件发给AI即可快速理解整个项目。*
