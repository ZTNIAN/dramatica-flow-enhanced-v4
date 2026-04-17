# Dramatica-Flow Enhanced — 项目交接文档

> 最后更新：2026-04-17
> 版本：V4（基于 V3 全面升级：审查闭环 + MiroFish反馈 + Agent画像）
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

| 版本 | 地址 | 说明 |
|------|------|------|
| V1 | https://github.com/ZTNIAN/dramatica-flow-enhanced | 12个增强点，6项没接入 |
| V2 | https://github.com/ZTNIAN/dramatica-flow-enhanced-v2 | 修复V1 + 知识库扩充 |
| V3 | https://github.com/ZTNIAN/dramatica-flow-enhanced-v3 | 知识库+Web界面+动态规划 |
| **V4（当前）** | https://github.com/ZTNIAN/dramatica-flow-enhanced-v4 | 审查闭环+MiroFish+Agent画像 |

---

## 三、V3 → V4 的核心区别

### V3 的问题

V3 加了 10 个新 Agent（对话/场景/心理等），但存在严重问题：
- **审查结果没有闭环** — 查完只打 log，分数低也不会触发修订
- **MiroFish/Feedback 是孤岛** — 没有串联
- **风格一致性在审计之后** — 查出问题但已过了修订循环
- **每章多 ~6 次 LLM 调用** — 成本翻倍但质量没闭环

### V4 修了什么

#### 1. 统一审查循环（核心改进）

**V3 管线：**
```
写手 → 对话审查(打log) → 巡查 → 场景审查(打log) → 心理审查(打log) → 审计→修订 → 风格检查(打log)
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

## 四、Agent 体系（19个Agent）

### 原有 9 个

| Agent | 职责 |
|-------|------|
| WorldBuilderAgent | 一句话→世界观 |
| OutlinePlannerAgent | 大纲+章纲 |
| MarketAnalyzerAgent | 市场分析 |
| ArchitectAgent | 规划单章蓝图（V4增强：注入钩子+开篇方法论） |
| WriterAgent | 生成正文 |
| PatrolAgent | 快速扫描 |
| AuditorAgent | 9维加权审计 |
| ReviserAgent | 修订正文 |
| SummaryAgent | 章节摘要 |

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

## 五、写作管线流程（V4）

```
[市场分析]（可选）
    ↓
[世界构建]
    ↓
[角色成长规划]（V4新增）
    ↓
[情绪曲线设计]（V4新增）
    ↓
[大纲规划]
    ↓
[单章循环]（每章重复以下流程）
    ├── 快照备份
    ├── 建筑师：规划蓝图（注入钩子+开篇方法论）
    ├── 写手：生成正文 + 结算表
    ├── 对话专家审查（V4新增，问题汇入修订）
    ├── 写后验证（零LLM硬规则）
    ├── 巡查者：P0/P1/P2快速扫描
    ├── 场景审核（V4新增，问题汇入修订）
    ├── 心理审核（V4新增，问题汇入修订）
    ├── 审计员：9维加权评分 + 合并所有审查问题
    │   └── 不通过 → 修订者修正 → 再审（最多3轮）
    ├── 风格一致性检查（不通过→polish修正）
    ├── 保存最终稿
    ├── 因果链提取 → 摘要生成 → 状态更新
    ├── 质量仪表盘记录
    ├── 动态规划器更新
    ├── KB查询统计保存
    ├── Agent能力画像记录（V4新增）
    └── MiroFish测试（每5章，V4新增）
        └── 反馈分类路由 → 保存报告
    ↓
[导出]
```

---

## 六、文件结构

```
dramatica-flow-enhanced-v4/
├── cli/main.py                          # CLI入口
├── core/
│   ├── agents/
│   │   ├── __init__.py                  # 9个原有Agent
│   │   └── enhanced_agents.py           # 10个V4新增Agent（1104行）
│   ├── pipeline.py                      # 写作管线（V4：统一审查循环，1066行）
│   ├── llm/__init__.py                  # LLM抽象层
│   ├── narrative/__init__.py            # 叙事引擎
│   ├── state/__init__.py                # 状态管理
│   ├── types/                           # 数据类型
│   ├── validators/__init__.py           # 写后验证器
│   ├── server.py                        # FastAPI服务器
│   ├── quality_dashboard.py             # 质量仪表盘
│   ├── dynamic_planner.py               # 动态规划器
│   ├── kb_incentive.py                  # 知识库查询激励
│   └── knowledge_base/                  # 知识库（38+文件）
│       ├── rules/                       # 规则类（6文件）
│       ├── references/                  # 参考类
│       ├── agent-specific/              # Agent专属（10文件，V4新增8个指南）
│       ├── examples/                    # 写作示例
│       ├── fanqie-data/                 # 番茄市场数据
│       └── indexes/                     # 索引
├── dramatica_flow_web_ui.html           # Web UI
├── dramatica_flow_timeline.html         # 时间轴可视化
├── pyproject.toml
├── .env.example
├── PROJECT_HANDOFF.md                   # 本文件
└── USER_MANUAL.md
```

---

## 七、V4 新增 API 端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/books/{id}/character-growth` | POST | 角色成长规划 |
| `/api/books/{id}/dialogue-review` | POST | 对话审查 |
| `/api/books/{id}/emotion-curve` | POST | 情绪曲线设计 |
| `/api/books/{id}/feedback` | POST | 提交读者反馈 |
| `/api/books/{id}/mirofish-test` | POST | MiroFish模拟测试 |
| `/api/books/{id}/hook-designs` | GET | 获取钩子设计方案 |

---

## 八、向后兼容

所有 V4 新增 Agent 参数均为**可选**（`| None = None`）。不传入时，管线行为与 V3 完全一致。可以逐步启用新功能：

```python
# 最小启动（与V3一致）
pipeline = WritingPipeline(state_manager, architect, writer, auditor, reviser, ...)

# 启用对话审查
pipeline = WritingPipeline(..., dialogue_expert=DialogueExpert(llm))

# 全功能
pipeline = WritingPipeline(..., dialogue_expert=..., scene_architect=..., psychological_expert=..., style_checker=..., mirofish_reader=..., feedback_expert=...)
```

---

## 九、踩坑记录

（同 V3，新增以下内容）

### 坑10：审查 Agent 问题格式

对话/场景/心理审查的 `issues` 是 `list[dict]`，不是 `list[AuditIssue]`。在合并到审计循环时需要转换：
```python
AuditIssue(
    dimension="对话质量",
    severity="warning",
    description=f"[{issue.get('character')}] {issue.get('description')}",
    suggestion=issue.get("suggestion", ""),
)
```

### 坑11：MiroFish 触发频率

默认每5章触发一次。如果书很短（<10章），可能永远不会触发。可在 `pipeline.py` 中修改 `MIROFISH_INTERVAL`。

---

## 十、迭代流程

每次迭代只需要做 **两件事**：

1. **发交接文档**：把本文件 `PROJECT_HANDOFF.md` 全文发给 AI
2. **给 GitHub Token**：每次生成新的，推完立刻 revoke

---

## 十一、下一步可以做什么

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P1 | 端到端测试 | 实际跑一本书，验证审查闭环质量 |
| P1 | 管线成本优化 | 审查 Agent 只在高风险章节触发 |
| P2 | Agent 能力画像可视化 | Web UI 中展示各 Agent 评分趋势 |
| P2 | 反馈→修订自动触发 | MiroFish 报告高优先级问题自动进入下一章修订 |
| P2 | 支持更多 LLM | Claude、GPT-4等 |
| P2 | 导出格式增强 | PDF、EPUB |

---

## 十二、技术栈

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

*本文档由AI自动生成。下次迭代时，把本文件发给AI即可快速理解整个项目。*
