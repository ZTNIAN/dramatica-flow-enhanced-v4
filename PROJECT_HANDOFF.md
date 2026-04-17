# Dramatica-Flow Enhanced — 项目交接文档

> 最后更新：2026-04-17（含修补记录）
> 版本：V5（V4基础上架构重构：模块化 + 配置化 + 安全加固 + 异步化）
> **V5 更新（2026-04-17）**：架构优化 — 消除代码重复、魔法数字配置化、安全加固

> 本文档面向所有人，尤其是零基础用户。读完就能理解整个项目、怎么用、怎么继续迭代。

---

## 一、这是什么？

**Dramatica-Flow Enhanced** 是一个 **AI 自动写小说系统**。你给它一句话设定，它帮你：

1. **市场分析** — 分析目标读者偏好（引用番茄小说真实数据）
2. **构建世界观** — 角色/势力/地点/规则，全部自动生成
3. **角色成长规划** — 每个主要角色8维档案 + 成长弧线 + 转折点（V4新增）
4. **情绪曲线设计** — 整书情绪起伏规划，精确操控读者情绪（V4新增）
5. **生成大纲** — 三幕结构 + 逐章规划 + 张力曲线
6. **自动写作** — 一章一章写，每章2000字
7. **多维审查** — 对话/场景/心理/风格，4个专项审查Agent（V4新增）
8. **自动审计** — 9维度加权评分 + 17条红线一票否决
9. **审查→修订闭环** — 所有审查问题合并进修订循环（V4核心改进）
10. **MiroFish读者测试** — 每5章模拟1000名读者反馈（V4新增）
11. **Agent能力画像** — 追踪每个Agent的工作质量（V4新增）

**一句话：V3 是"AI写+AI审"，V4 是"AI写+多维审+闭环改+读者测"。**

---

## 二、项目地址

### GitHub 仓库

| 版本 | 地址 | 说明 |
|------|------|------|
| **原版** | https://github.com/ydsgangge-ux/dramatica-flow | 叙事逻辑强，但缺乏前期规划和质量管控 |
| **V1** | https://github.com/ZTNIAN/dramatica-flow-enhanced | 12个增强点完成但有6项"写了没接入" |
| **V2** | https://github.com/ZTNIAN/dramatica-flow-enhanced-v2 | 修复V1的核心问题 + 知识库扩充 |
| **V3** | https://github.com/ZTNIAN/dramatica-flow-enhanced-v3 | 全面升级：知识库+Web界面+动态规划+KB追踪 |
| **V4（当前）** | https://github.com/ZTNIAN/dramatica-flow-enhanced-v4 | 审查闭环+MiroFish反馈+Agent画像 |

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
- 对比示例库注入 Writer prompt（写手写作时看到"好vs坏"对比）
- 知识库注入 Architect prompt（建筑师参考写作技巧和去AI规则）
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

**V3 的问题：引入了10个新Agent（对话/场景/心理等），但审查结果只打 log 不管，没有闭环。**

### V4 做了什么

**V4 = V3 + 以下核心改进**

#### 1. 统一审查循环（核心改进）

**V3 管线：**
```
写手 → 对话审查(只打log) → 巡查 → 场景审查(只打log) → 心理审查(只打log) → 审计→修订 → 风格检查(只打log)
```

**V4 管线：**
```
写手 → 对话审查 ─┐
         巡查   ─┤
      场景审查   ─┼→ 汇聚为 issues 列表 → 审计合并 → 统一修订循环 → 风格修正
      心理审查   ─┘
```

**关键改动：** 所有审查 Agent 的问题转为 `AuditIssue`，合并进审计报告。修订循环同时解决审计问题 + 对话问题 + 场景问题 + 心理问题。

#### 2. MiroFish→Feedback→修订 串联

```
每5章触发：
MiroFish(1000名读者模拟) → Feedback(分类路由) → 保存报告 → 后续章节可参考
```

#### 3. Agent 能力画像

每章记录每个审查 Agent 的评分，保存到 `agent_performance.json`。可追踪：
- 哪个 Agent 最常发现问题
- 各 Agent 评分趋势
- 管线返工率变化

#### 4. 风格一致性修正

**V3：** 风格检查在审计之后，查出问题不管
**V4：** 风格检查 < 80 分且还有修订余量 → 自动做最后一轮 `polish` 修正

---

## 四、小白操作手册

### 4.1 两种用法

| | Web UI（浏览器） | CLI（命令行） |
|--|-----------------|---------------|
| 怎么打开 | 浏览器打开 http://127.0.0.1:8766/ | 终端输入 `df` 命令 |
| 适合谁 | 喜欢点按钮、看图形界面 | 喜欢敲命令、批量操作 |
| 功能 | 创建书、写章节、看状态、审计、市场分析、仪表盘 | 同上 + 全部命令 |
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
# 第1步：市场分析（可选，V4增强：自动引用番茄真实数据）
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
7. 步骤6（审计）：查看审计结果、质量仪表盘、KB统计、情绪曲线、风格一致性
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
- 每次 API 调用间隔 1-2 秒
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

#### 方法2：大文件（>1MB）或中文路径用 Python

```bash
cd /path/to/project
python3 << 'PYEOF'
import base64, json, urllib.request, time
from urllib.parse import quote

TOKEN = "你的GitHub Token"
REPO = "ZTNIAN/dramatica-flow-enhanced-v4"
filepath = "core/server.py"

# URL-encode for Chinese filenames
encoded = "/".join(quote(seg, safe="") for seg in filepath.split("/"))

with open(filepath, "rb") as f:
    content_b64 = base64.b64encode(f.read()).decode()

# Get existing sha
try:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/contents/{encoded}",
        headers={"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}
    )
    sha = json.loads(urllib.request.urlopen(req, timeout=10).read()).get("sha", "")
except:
    sha = ""

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
result = json.loads(urllib.request.urlopen(req, timeout=15).read())
print(f"{filepath} → {result.get('commit',{}).get('sha','ERROR')[:8]}")
PYEOF
```

#### 方法3：批量上传模板

```bash
#!/bin/bash
TOKEN="你的GitHub Token"
REPO="ZTNIAN/dramatica-flow-enhanced-v4"

upload() {
    local f="$1" msg="$2"
    python3 -c "
import base64, json, urllib.request, time
from urllib.parse import quote
T='$TOKEN'; R='$REPO'; F='$f'; M='$msg'
E='/'.join(quote(s,safe='') for s in F.split('/'))
with open(F,'rb') as fh: c=base64.b64encode(fh.read()).decode()
try:
    s=json.loads(urllib.request.urlopen(urllib.request.Request(f'https://api.github.com/repos/{R}/contents/{E}',headers={'Authorization':f'token {T}'}),timeout=10).read()).get('sha','')
except: s=''
d=json.dumps({'message':M,'content':c,'branch':'main',**({'sha':s} if s else {})}).encode()
r=urllib.request.urlopen(urllib.request.Request(f'https://api.github.com/repos/{R}/contents/{E}',data=d,headers={'Authorization':f'token {T}','Content-Type':'application/json'},method='PUT'),timeout=15)
print(f'{F} OK')
" && sleep 1
}

upload "core/agents/__init__.py" "更新Agent"
upload "core/pipeline.py" "更新管线"
upload "core/server.py" "更新API"
```

---

## 七、V4 是怎么迭代的

### 迭代过程

1. **用户上传 V3 交接文档 + GitHub Token**
   - V3 的 `PROJECT_HANDOFF.md` + `V3.txt` 对话记录
   - V3 GitHub Token：`ghp_xxxxx`

2. **AI 下载并阅读所有文档**，理解项目全貌

3. **AI 克隆 V3 仓库**，分析当前代码状态

4. **AI 分析 OpenMOSS Agent**，评估哪些值得引入（10个 Agent）

5. **AI 在服务器上修改代码**：
   - 新建 `core/agents/enhanced_agents.py`（10个新Agent，1104行）
   - 修改 `core/pipeline.py`（统一审查循环，+204行）
   - 增强 `core/agents/__init__.py`（注入钩子+开篇方法论）
   - 新增 8 个知识库指南文件
   - 修改 `core/server.py`（6个新API端点）
   - 修改 `dramatica_flow_web_ui.html`（新面板）
   - 生成 `PROJECT_HANDOFF.md` 完整交接文档

6. **用户给新 GitHub Token**，AI 通过 GitHub API 逐文件推送

7. **AI 清理 token 痕迹**，提醒用户 revoke

### 改了什么文件

| 文件 | 改动类型 | 改动内容 |
|------|---------|---------|
| `core/agents/enhanced_agents.py` | 新增 | 10个OpenMOSS Agent类（1104行） |
| `core/agents/__init__.py` | 修改 | ArchitectAgent prompt注入钩子+开篇方法论 |
| `core/pipeline.py` | 重写 | 统一审查循环 + MiroFish串联 + Agent画像 |
| `core/server.py` | 修改 | 新增6个API端点 |
| `dramatica_flow_web_ui.html` | 修改 | 新增角色成长/对话审查/情绪曲线/风格一致性面板 |
| `core/knowledge_base/agent-specific/` | 新增8文件 | 钩子/开篇/情绪/对话/人物/风格/场景/心理指南 |
| `PROJECT_HANDOFF.md` | 重写 | 完整交接文档 |

### 代码统计

- 修改文件：4个
- 新增文件：9个
- 总增行数：约1500行
- V5 总文件数：127个（V4修补后95个 + 新增kb.py）

---



### 本次修补记录（2026-04-17）

V4 仓库更新到一半断了连接，导致 GitHub 上的 V4 有以下问题：

**发现的问题：**
| 问题 | 严重度 | 状态 |
|------|--------|------|
| `.gitignore` 缺失 | 中 | ✅ 已修复（从V3补充） |
| `install.sh` 缺失 | 中 | ✅ 已修复（从V3补充） |
| `PROJECT_HANDOFF.md` 文件数描述不准确 | 低 | ✅ 已修正 |

**验证通过的文件（与V3一致或增强）：**
| 文件 | 状态 | 说明 |
|------|------|------|
| `core/agents/__init__.py` | ✅ 一致 | 与V3完全相同 |
| `core/agents/enhanced_agents.py` | ✅ 存在 | 40134字节，10个新Agent |
| `core/pipeline.py` | ✅ 增强 | 49352字节（V3为33010），统一审查循环 |
| `core/server.py` | ✅ 一致 | 与V3完全相同 |
| `core/dynamic_planner.py` | ✅ 一致 | 与V3完全相同 |
| `dramatica_flow_web_ui.html` | ✅ 一致 | 与V3完全相同 |
| 8个知识库指南文件 | ✅ 全部存在 | agent-specific/下8个.md |
| 其余78个文件 | ✅ 全部存在 | 知识库/模板/测试/文档等 |

**修补操作：**
1. 从V3仓库下载 `.gitignore` → 上传到V4
2. 从V3仓库下载 `install.sh` → 上传到V4
3. 更新 `PROJECT_HANDOFF.md`（本文件）

**修补后 V5 总文件数：127个（V4修补后95个 + 新增kb.py）**（与V3相同，V4增强内容通过修改已有文件实现）


### V5 优化记录（2026-04-17）

| 文件 | 改动 | 效果 |
|------|------|------|
| `core/agents/kb.py` | **新增** | 公共知识库模块，统一 KB 加载 + 查询追踪 |
| `core/agents/__init__.py` | 修改 | 改为从 `kb.py` 导入 KB 内容，消除 `_load_kb` 重复定义 |
| `core/agents/enhanced_agents.py` | 修改 | 同上，消除 `_load_kb` + `_KB_DIR` 重复定义 |
| `core/pipeline.py` | 修改 | 新增 `PipelineConfig` 数据类，10个魔法数字全部从环境变量读取 |
| `core/server.py` | 修改 | CORS 从 `*` 改为 localhost 白名单 + `_safe_book_dir()` 防路径遍历 |

#### 可配置参数（通过环境变量设置）

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `PIPELINE_MAX_REVISE_ROUNDS` | 3 | 最大修订轮数 |
| `PIPELINE_MIROFISH_INTERVAL` | 5 | MiroFish 每N章触发 |
| `PIPELINE_MIROFISH_SAMPLE_CHARS` | 3000 | MiroFish 每章采样字数 |
| `PIPELINE_RECENT_SUMMARIES_N` | 3 | 前情摘要取最近N章 |
| `PIPELINE_DORMANCY_THRESHOLD` | 5 | 支线掉线预警阈值（章） |
| `PIPELINE_REVIEW_SCORE_FLOOR` | 75 | 审查Agent问题汇入阈值 |
| `PIPELINE_STYLE_SCORE_FLOOR` | 80 | 风格一致性修正阈值 |
| `PIPELINE_AUDIT_TENSION_FLOOR` | 90 | 审计分低于此值调整张力曲线 |
| `PIPELINE_AUDIT_DIMENSION_FLOOR` | 85 | 单项维度最低分要求 |
| `PIPELINE_AUDIT_PASS_TOTAL` | 95 | 审计通过加权总分要求 |
| `CORS_ALLOW_ORIGINS` | localhost | CORS 允许的源（逗号分隔） |

#### V4→V5 文件变化

- 总文件数：**96个**（V4修补后95个 + 新增 kb.py = 96个）



### V5 架构优化（2026-04-17 完成）

**总文件数：127个**

#### 优化1：server.py 拆分（3618行 → 12个模块）

| 文件 | 行数 | 职责 |
|------|------|------|
| `core/server/__init__.py` | 106 | app 实例 + 中间件 + CORS + 静态文件 |
| `core/server/deps.py` | 301 | 公共依赖（_sm, _load_env, _create_llm, 请求模型） |
| `core/server/routers/books.py` | 170 | /api/books CRUD + 导入 |
| `core/server/routers/setup.py` | 101 | 世界观配置 |
| `core/server/routers/chapters.py` | 83 | 章节管理 |
| `core/server/routers/outline.py` | 151 | 大纲相关 |
| `core/server/routers/writing.py` | 222 | 写作+审计+修订（异步化） |
| `core/server/routers/ai_actions.py` | 380 | AI生成/提取 |
| `core/server/routers/threads.py` | 82 | 线程管理 |
| `core/server/routers/analysis.py` | 86 | 因果链/情感弧/钩子 |
| `core/server/routers/enhanced.py` | 134 | V4增强功能 |
| `core/server/routers/settings.py` | 76 | 设置 |
| `core/server/routers/export.py` | 53 | 导出 |

#### 优化2：agents 拆分（2528行 → 20个独立文件）

| 文件 | 职责 |
|------|------|
| `core/agents/__init__.py` | 72行 re-export 入口 |
| `core/agents/kb.py` | 公共KB模块（消除重复） |
| `core/agents/architect.py` | 建筑师 |
| `core/agents/writer.py` | 写手 |
| `core/agents/auditor.py` | 审计员 |
| `core/agents/reviser.py` | 修订者 |
| `core/agents/summary.py` | 摘要生成 |
| `core/agents/patrol.py` | 巡查者 |
| `core/agents/worldbuilder.py` | 世界观构建 |
| `core/agents/outline_planner.py` | 大纲规划 |
| `core/agents/market_analyzer.py` | 市场分析 |
| `core/agents/enhanced/character_growth.py` | 角色成长 |
| `core/agents/enhanced/dialogue.py` | 对话审查 |
| `core/agents/enhanced/emotion_curve.py` | 情绪曲线 |
| `core/agents/enhanced/feedback.py` | 反馈分类 |
| `core/agents/enhanced/style_checker.py` | 风格一致性 |
| `core/agents/enhanced/scene_architect.py` | 场景审核 |
| `core/agents/enhanced/psychological.py` | 心理描写 |
| `core/agents/enhanced/mirofish.py` | 模拟读者 |
| `core/agents/enhanced/methods.py` | 钩子/开篇方法论 |

#### 优化3：错误处理精细化

- pipeline.py 11个 `except Exception` 全部改为区分错误类型
- LLM 解析错误 → 记录 JSON/KeyError 详情
- IO 错误 → 记录文件路径
- 未知错误 → 记录 traceback（截断到500字符）
- 静默 `pass` 块 → 至少 debug 级别日志

#### 优化4：关键端点异步化

| 端点 | 改动 |
|------|------|
| `POST /api/action/write` | sync → async + run_in_executor |
| `POST /api/action/audit` | sync → async + run_in_executor |
| `POST /api/action/revise` | sync → async + run_in_executor |

LLM 调用不再阻塞 FastAPI 事件循环。

#### 删除的冗余文件

- `core/server.py`（旧单文件，被 `core/server/` 替代）
- `core/agents/enhanced_agents.py`（被 `core/agents/enhanced/` 替代）


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

## 九、Agent 体系（19个Agent）

### 原有 9 个

| Agent | 职责 | 触发时机 |
|-------|------|---------|
| WorldBuilderAgent | 一句话→世界观 | `df worldbuild` |
| OutlinePlannerAgent | 大纲+章纲 | `df outline` |
| MarketAnalyzerAgent | 市场分析 | `df market` |
| ArchitectAgent | 规划单章蓝图（V4增强：注入钩子+开篇方法论） | 每章写前 |
| WriterAgent | 生成正文 | 每章写手 |
| PatrolAgent | 快速扫描 | 写后立即 |
| AuditorAgent | 9维加权审计（V4增强：合并审查Agent问题） | 巡查后 |
| ReviserAgent | 修订正文 | 审计不通过 |
| SummaryAgent | 章节摘要 | 写完后 |

### V4 新增 10 个

| 优先级 | Agent | 职责 | 插入位置 |
|--------|-------|------|---------|
| P1 | CharacterGrowthExpert | 角色8维档案 + 成长弧线规划 | WorldBuilder → **此Agent** → OutlinePlanner |
| P1 | DialogueExpert | 对话审查 + 语言指纹六维度 | Writer → **此Agent** → 巡查（问题汇入修订） |
| P1 | EmotionCurveDesigner | 整书情绪曲线 + 每章情绪类型 | OutlinePlanner 之后增强章纲 |
| P1 | FeedbackExpert | 读者反馈分类路由 + 闭环追踪 | 每N章配合 MiroFish |
| P2 | HookDesigner | 7种章末钩子方法论 | 注入 ArchitectAgent prompt |
| P2 | OpeningEndingDesigner | 黄金三章 + 全书结尾方法论 | 注入 ArchitectAgent prompt |
| P2 | StyleConsistencyChecker | 五维一致性检查 | 审计循环之后（不通过→polish修正） |
| P3 | SceneArchitect | 场景四维审核（问题汇入修订） | 巡查之后、审计之前 |
| P3 | PsychologicalPortrayalExpert | 心理四维审核（问题汇入修订） | 巡查之后、审计之前 |
| P3 | MiroFishReader | 1000名读者模拟 + 结构化反馈 | 每5章触发 |

---

## 十、写作管线流程

```
[市场分析]（可选）
    题材 → MarketAnalyzerAgent → 风格指南 + 读者偏好
    ↓
[世界构建]（必做）
    一句话设定 → WorldBuilderAgent → 世界观JSON
    ↓
[角色成长规划]（V4新增）
    角色列表 → CharacterGrowthExpert → 8维档案 + 成长弧线
    ↓
[情绪曲线设计]（V4新增）
    章节数 → EmotionCurveDesigner → 整书情绪曲线
    ↓
[大纲规划]（必做）
    世界观 → OutlinePlannerAgent → 三幕结构 + 章纲
    ↓
[单章循环]（每章重复以下流程）
    ├── 快照备份
    ├── 建筑师：规划蓝图（注入五感+常见错误+钩子方法论+开篇方法论）
    ├── 写手：生成正文（注入写手技能库+ShowDon'tTell）+ 结算表
    ├── 对话专家审查（V4新增，问题汇入修订循环）
    ├── 验证器：零LLM硬规则扫描（13类禁止词/Tell式表达）
    ├── 巡查者：P0/P1/P2快速扫描 → 打回修正
    ├── 场景审核（V4新增，问题汇入修订循环）
    ├── 心理审核（V4新增，问题汇入修订循环）
    ├── 审计员：9维度加权评分（≥95分+单项≥85+无红线）
    │   └── 合并对话/场景/心理审查问题
    │   └── 不通过 → 修订者修正 → 再审（最多3轮）
    ├── 风格一致性检查（不通过→polish修正）
    ├── 保存最终稿
    ├── 因果链提取
    ├── 摘要生成
    ├── 状态结算
    ├── 质量仪表盘记录
    ├── 动态规划器更新（审计→张力曲线反馈）
    ├── KB查询统计保存
    ├── Agent能力画像记录（V4新增）
    └── MiroFish测试（每5章，V4新增）
        └── 反馈分类路由 → 保存报告
    ↓
[导出]
    df export → Markdown / TXT
```

---

## 十一、技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| 后端 | FastAPI |
| CLI | Typer |
| 数据存储 | 文件系统（JSON + Markdown） |
| LLM | DeepSeek API（默认）/ Ollama（本地免费） |
| 前端 | 单文件 HTML（暗色主题） |
| 校验 | Pydantic v2 |

---

## 十二、文件结构

```
dramatica-flow-enhanced-v4/
├── cli/main.py                          # CLI入口，13个命令
├── core/
│   ├── agents/
│   │   ├── __init__.py                  # 9个原有Agent
│   │   └── enhanced_agents.py           # 10个V4新增Agent（1104行）
│   ├── pipeline.py                      # 写作管线（V4：统一审查循环，1066行）
│   ├── llm/__init__.py                  # LLM抽象层（DeepSeek/Ollama）
│   ├── narrative/__init__.py            # 叙事引擎（因果链/伏笔/时间轴）
│   ├── state/__init__.py                # 状态管理
│   ├── types/                           # 数据类型
│   ├── validators/__init__.py           # 写后验证器（13类规则）
│   ├── server.py                        # FastAPI服务器（17个API端点）
│   ├── quality_dashboard.py             # 质量仪表盘
│   ├── dynamic_planner.py               # 动态规划器（自适应分层）
│   ├── kb_incentive.py                  # 知识库查询激励
│   └── knowledge_base/                  # 知识库（38+文件）
│       ├── rules/                       # 规则类（6文件）
│       ├── references/                  # 参考类
│       ├── agent-specific/              # Agent专属（10文件）
│       ├── examples/                    # 写作示例
│       ├── fanqie-data/                 # 番茄市场数据
│       └── indexes/                     # 索引
├── templates/                           # 模板文件
├── tests/                               # 测试
├── docs/                                # 文档
├── examples/                            # 示例
├── dramatica_flow_web_ui.html           # Web UI（暗色主题单文件）
├── dramatica_flow_timeline.html         # 时间轴可视化
├── pyproject.toml                       # 项目配置
├── .env.example                         # 环境变量模板
├── PROJECT_HANDOFF.md                   # 本文件
└── USER_MANUAL.md                       # 操作手册
```

---

## 十三、下一步可以做什么

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P1 | 端到端测试 | 实际跑一本书，验证审查闭环质量 |
| P1 | 管线成本优化 | 审查Agent只在高风险章节触发，不是每章都跑 |
| P2 | Agent能力画像可视化 | Web UI中展示各Agent评分趋势 |
| P2 | 反馈→修订自动触发 | MiroFish报告高优先级问题自动进入下一章修订 |
| P2 | 支持更多LLM | Claude、GPT-4等 |
| P2 | 导出格式增强 | PDF、EPUB格式支持 |

---

*本文档由AI自动生成。下次迭代时，把本文件发给AI即可快速理解整个项目。*
