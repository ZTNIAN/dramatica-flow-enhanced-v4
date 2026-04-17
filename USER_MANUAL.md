# Dramatica-Flow Enhanced — 小白操作手册

> 本手册面向零基础用户，手把手教你用这个AI写小说系统。

---

## 两种用法的区别

| | Web UI（浏览器） | CLI（命令行） |
|--|-----------------|---------------|
| 怎么打开 | 浏览器打开 http://127.0.0.1:8766/ | WSL终端输入 `df` 命令 |
| 适合谁 | 喜欢点击按钮、看图形界面 | 喜欢敲命令、批量操作 |
| 功能 | 创建书、写章节、看状态、审计 | 同上 + **世界观构建/大纲规划/市场分析** |
| 区别 | 界面友好，但功能可能不全 | 功能最全，新功能优先在CLI |

**结论：日常写作用Web UI，前期设计（世界观/大纲）用CLI。**

---

## 完整操作流程（从零开始写一本小说）

### 第1步：启动项目

打开WSL终端，输入：

```bash
cd ~/dramatica-flow-enhanced
source .venv/bin/activate
```

看到终端前面出现 `(.venv)` 就说明虚拟环境激活了。

### 第2步：市场分析（可选）

看看什么题材火、读者喜欢什么：

```bash
df market 科幻 --premise "AI觉醒后取代人类工作"
```

AI会输出：
- 目标读者画像（年龄/性别/阅读习惯）
- 读者偏好（该题材读者最看重什么）
- 题材趋势（当前流行什么）
- 推荐文风方向
- 竞品分析

**这步可跳过**，直接进入第3步。

### 第3步：世界观构建（核心！）

这是最重要的一步。你给AI一句话，它帮你生成完整的世界观：

```bash
df worldbuild "你的设定" --genre 题材
```

**举例：**

```bash
# 玄幻类
df worldbuild "废灵根少年被退婚后觉醒上古传承，一路逆袭登顶" --genre 玄幻

# 都市科幻类
df worldbuild "2045年AI取代了所有人类工作，最后一个程序员发现了AI的秘密" --genre 都市科幻

# 悬疑类
df worldbuild "连环杀手每次作案后都给警方寄一张拼图，最后一块拼图指向警察局长" --genre 悬疑
```

**AI会自动生成：**
- 5+个角色（主角/反派/冲击者/守护者/伙伴），每个角色有外部目标+内在渴望+性格锁定
- 3+个势力（互有矛盾）
- 4+个地点
- 世界规则+力量体系
- 情节钩子
- 市场定位

**生成的文件保存在：** `books/书名/setup/` 目录下（characters.json、locations.json等）

**完成后AI会告诉你下一步命令**，类似：
```
下一步：df outline --book 书名
```

### 第4步：大纲规划

把世界观变成三幕结构+逐章规划：

```bash
df outline --book 上一步生成的书名
```

**AI会自动生成：**
- 三幕结构（建立→对抗→解决）
- 每章的标题、摘要、戏剧功能
- 情感弧线（开始情绪→结束情绪）
- 张力曲线（每章1-10分）
- 支线规划

**生成的文件保存在：** `books/书名/outlines/` 目录下

### 第5步：开始写作

**方式A：命令行（一次写一章）**

```bash
df write 书名
```

AI会自动走完完整管线：建筑师规划→写手写作→巡查扫描→审计评分→不合格自动修订

**方式B：浏览器（推荐，更直观）**

```bash
# 先启动服务器（WSL里执行，不要关掉这个终端）
uvicorn core.server:app --reload --host 0.0.0.0 --port 8766
```

然后浏览器打开：http://127.0.0.1:8766/

在Web UI里你可以：
- 看到书籍列表
- 点击"写下一章"
- 查看每章的审计报告
- 看质量评分趋势

### 第6步：查看状态

```bash
df status 书名
```

会显示：
- 当前写到第几章
- 总字数
- 审计通过率
- 伏笔状态

### 第7步：导出正文

```bash
df export 书名
```

导出为可阅读的文本文件。

---

## 命令速查表

| 命令 | 作用 | 什么时候用 |
|------|------|-----------|
| `df doctor` | 诊断API连接 | 第一次用，或出问题时 |
| `df market 题材` | 市场分析 | 开始写新书前（可选） |
| `df worldbuild "设定"` | 构建世界观 | 开始写新书（必做） |
| `df outline --book 书名` | 生成大纲 | 世界观构建后（必做） |
| `df write 书名` | 写下一章 | 日常写作 |
| `df audit 书名 --chapter N` | 手动审计第N章 | 对某章质量不满意时 |
| `df revise 书名 --chapter N` | 手动修订第N章 | 审计不通过时 |
| `df status 书名` | 查看状态 | 随时 |
| `df export 书名` | 导出正文 | 写完后 |
| `df setup init-templates` | 生成配置模板 | 旧流程用（已被worldbuild替代） |
| `df setup load` | 加载配置 | 旧流程用（已被worldbuild替代） |

---

## Web UI 怎么用？

### 启动Web UI

```bash
cd ~/dramatica-flow-enhanced
source .venv/bin/activate
uvicorn core.server:app --reload --host 0.0.0.0 --port 8766
```

**注意**：这个终端窗口不要关！关了Web UI就不能用了。

### 打开浏览器

地址栏输入：http://127.0.0.1:8766/

### Web UI能做什么

- **创建新书**：填书名、题材、每章字数
- **配置世界观**：填角色、地点、势力（手动填JSON）
- **写章节**：点击按钮，AI自动写
- **审计**：查看每章的评分和问题
- **查看时间轴**：多线叙事的时间线

### Web UI vs CLI

Web UI的"配置世界观"需要你手动填JSON，比较麻烦。
CLI的 `df worldbuild` 是AI自动生成，**推荐用CLI做前期设计，用Web UI做日常写作。**

---

## 常见问题

### Q: df命令找不到？
```bash
source .venv/bin/activate
```
每次开新终端都要先激活虚拟环境。

### Q: API连接失败？
```bash
df doctor
```
检查 .env 文件里的 DEEPSEEK_API_KEY 是否正确。

### Q: 写出来的内容AI味很重？
这是正常的。系统有13类禁止词扫描和17条红线，但AI不是完美的。如果某章审计不通过，系统会自动修订。你也可以手动审计：
```bash
df audit 书名 --chapter N
```

### Q: 每章只有2000字，太短了？
2000字是硬限制，设计如此。短章节更适合手机阅读，节奏也更紧凑。如果你想改，编辑 `.env` 文件里的 `DEFAULT_WORDS_PER_CHAPTER`，但建议先用2000字跑几章试试。

### Q: 怎么用Ollama本地模型（免费）？
编辑 `.env` 文件：
```
# 注释掉DeepSeek
# LLM_PROVIDER=deepseek
# DEEPSEEK_API_KEY=xxx

# 启用Ollama
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.1
```
需要先安装Ollama：https://ollama.com

### Q: Web UI打不开？
确认WSL里的uvicorn正在运行，且没有报错。如果端口被占用，换一个：
```bash
uvicorn core.server:app --reload --host 0.0.0.0 --port 9999
```
然后浏览器打开 http://127.0.0.1:9999/

### Q: git pull 拉不到最新代码？
```bash
git fetch origin
git reset --hard origin/main
```

### Q: 想修改项目代码？
```bash
cd ~/dramatica-flow-enhanced
# 用你喜欢的编辑器
code .  # VS Code
# 或
nano cli/main.py
```
改完后不用重新安装（pip install -e . 是开发模式，代码改了立即生效）。

---

## 写作流程总结（一张图）

```
你的一句话设定
      ↓
  df worldbuild（AI生成世界观）
      ↓
  df outline（AI生成大纲+章纲）
      ↓
  ┌─────────────────────────────┐
  │  df write 或 Web UI 写作     │
  │  （AI自动：规划→写作→审计→修订）│
  │  （重复直到写完所有章）        │
  └─────────────────────────────┘
      ↓
  df export（导出成品）
```

**你只需要做两件事：**
1. 给一句好的设定
2. 审核AI写出来的内容

剩下的全部自动化。

---

*祝你写出好小说！*
