# V3 OpenMOSS 集成分析报告

> 整理自 V3 迭代对话记录
> 日期：2026-04-17

---

## 背景

V3 迭代引入了 OpenMOSS 操作手册的精华内容。本报告详细记录了哪些内容被引入、哪些没有、以及原因。

---

## OpenMOSS 增强来源

| 来源 | 链接 | 大小 | 内容 |
|------|------|------|------|
| gz 包 | https://litter.catbox.moe/xyzwkq.gz | 1.6MB | 完整项目：知识库 + Agent 提示词 + FastAPI 后端 + OpenClaw 技能 |
| 7z 包 | https://litter.catbox.moe/2bmxac.7z | 158KB | 归档文档 + 工作流程规范 + 民国摸金校尉完整测试案例 |

**注意：** catbox 链接 72 小时过期。如需重新下载，用：
```bash
curl -F "reqtype=fileupload" -F "time=72h" -F "fileToUpload=@文件路径" \
  https://litterbox.catbox.moe/resources/internals/api.php
```

---

## 一、gz 包集成情况

### ✅ 已 100% 引入的内容（知识库文件）

| 内容 | V3 路径 | 说明 |
|------|---------|------|
| `knowledge-base/rules/anti_ai_rules.md` | `core/knowledge_base/rules/anti_ai_rules.md` | 去AI味规则、45特征润色系统 |
| `knowledge-base/rules/common-mistakes.md` | `core/knowledge_base/rules/common-mistakes.md` | 常见错误及避免方法（附修正示例） |
| `knowledge-base/rules/de-ai-guidelines.md` | `core/knowledge_base/rules/de-ai-guidelines.md` | 去AI味完整指南（4步法） |
| `knowledge-base/rules/redlines.md` | `core/knowledge_base/rules/redlines.md` | 17条红线完整定义+示例+避免方法 |
| `knowledge-base/rules/review-criteria-95.md` | `core/knowledge_base/rules/review-criteria-95.md` | 95分审查标准详解（6维+检查清单） |
| `knowledge-base/references/writing-techniques/` | `core/knowledge_base/references/writing-techniques/` | 五感描写指南 + Show Don't Tell 详解 |
| `knowledge-base/references/genre-guides/` | `core/knowledge_base/references/genre-guides/` | 玄幻题材指南 + 悬疑题材指南 |
| `knowledge-base/references/fanqie-novel/` | `core/knowledge_base/fanqie-data/` | 6份番茄小说报告（V2已有）+ 2份新增 |
| `knowledge-base/agent-specific/` | `core/knowledge_base/agent-specific/` | 写手技能库 + 审查者检查清单 |
| `knowledge-base/examples/` | `core/knowledge_base/examples/` | 好/坏/对比写作示例 |
| `knowledge-base/indexes/` | `core/knowledge_base/indexes/` | 知识库总索引 + 概览 |
| `knowledge-base/query-incentive-system.md` | `core/knowledge_base/query-incentive-system.md` | 知识库查询激励系统 |

**总计：30+ 个知识库文件全部引入。**

### ⚠️ 部分引入（概念融入代码，但未作为独立文件）

| 原始文件 | 集成方式 | 说明 |
|---------|---------|------|
| `prompts/role/writer-v2.md` | OODA 循环 / 记忆系统的**概念**注入了 WriterAgent 提示词结构 | 完整 prompt 未作为独立文件存档 |
| `prompts/role/reviewer-v2.md` | 预判性审查 / 质量数据库的概念注入了 AuditorAgent 检查清单 | 完整 prompt 未作为独立文件存档 |

### ❌ 未引入的内容

| 原始内容 | 原因 |
|---------|------|
| `prompts/role/` 其他 20+ 角色提示词 | Dramatica-Flow 只有 9 个 Agent，架构完全不同，不能直接套用 |
| `app/` FastAPI 后端代码 | 完全不同的技术栈（数据库/认证/路由），Dramatica-Flow 用文件系统存储 |
| `skills/` OpenClaw 技能 | 与小说写作系统无关 |

---

## 二、7z 包集成情况

### ✅ 已引入

| 内容 | V3 路径 | 说明 |
|------|---------|------|
| `MOSS_动态分层规划机制.md` | 核心公式写入 `core/dynamic_planner.py` | 自适应分层公式 + 四层结构完整实现 |
| `归档/06-爬虫数据/读者画像深度分析报告.md` | `core/knowledge_base/fanqie-data/` | 读者画像深度分析已复制 |

### ⚠️ 概念参考（未直接复制文档）

| 内容 | 说明 |
|------|------|
| `MOSS工作流程规范_v6.0.md` | 双流程 / 95分投票 / 自动返工的**概念**参考了，文档本身未复制（但已存为 `rules/v6.0-workflow-overview.md` 概览版） |
| `归档/99-历史备份/民国摸金校尉/` | 读了理解完整写作流程，作为测试参考案例 |

### ❌ 未引入

| 内容 | 原因 |
|------|------|
| `MOSS_Agent框架深度审视报告.md` | 仅供参考，OpenMOSS 的 Agent 框架与 Dramatica-Flow 架构差异大 |

---

## 三、总结

| 类别 | 引入比例 | 说明 |
|------|---------|------|
| 知识库文件 | **100%** | 30+ 个文件全部复制到 V3 |
| Agent 提示词 | **概念级** | OODA 循环、预判审查等概念已融入代码，但原始 prompt 未作为独立文件 |
| 工作流文档 | **概览级** | v6.0 核心概念已参考并实现，完整文档未复制 |
| 后端代码 | **0%** | 架构完全不同，无法合并 |
| 其他 Agent 角色 | **0%** | 20+ 角色与 V3 的 9 Agent 体系不兼容 |

**结论：OpenMOSS 的知识库精华 100% 在 V3 里了。Agent prompt 和工作流文档的概念已融入代码，但原文未作为独立参考文件存档。**

### 是否需要补存独立参考文件？

可选操作：将 `writer-v2.md`、`reviewer-v2.md` 复制到 `core/knowledge_base/reference-prompts/` 作为存档参考，方便后续迭代时回溯原始设计思路。

---

## 四、V4 迭代准备

### 迭代时只需做两件事

1. **发交接文档**：将 `PROJECT_HANDOFF.md` 全文发给新 AI 对话
2. **给 GitHub Token**：每次生成新的，推完立刻 revoke

### 发送模板

```
我下次迭代V4，以下是V3的项目交接文档：

（粘贴 PROJECT_HANDOFF.md 全部内容）

---

GitHub Token：ghp_xxxxx

OpenMOSS增强来源（如果需要参考）：
- gz包：https://litter.catbox.moe/xyzwkq.gz
- 7z包：https://litter.catbox.moe/2bmxac.7z

V4要做的事：
（列出具体事项）
```

### 关键点

1. 交接文档贴全文 — AI 靠这个理解项目
2. Token 给新的 — 每次重新生成
3. **说清楚 V4 要做什么** — 不然 AI 不知道改什么
4. OpenMOSS 链接备用 — 知识库已在 V3 仓库里，一般不需要重新下载

---

*本文档整理自 V3 迭代期间的对话记录，记录了 OpenMOSS 内容的完整集成情况。*
