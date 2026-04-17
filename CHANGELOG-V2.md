# Dramatica-Flow Enhanced v2 — 改动日志

## 改动时间
2026-04-17 09:43 — 10:07 (约25分钟)

## 文件统计
- 修改文件：4个（+379行，-50行）
- 新增目录：2个（examples/、fanqie-data/）
- 新增文件：8个（6个写作示例 + 2个市场数据目录）

---

## P0 修复（交接文档中的核心缺失）

### 1. 质量仪表盘接入管线 ✅
**文件**: `core/pipeline.py`
- `WritingPipeline` 新增 `dashboard: QualityDashboard | None` 可选参数
- 每章写完后自动记录 `ChapterStats`（加权分数、9维度得分、返工次数、红线违规、禁止词频率）
- 自动保存到 `books/{书名}/quality_dashboard.json`
- 不阻塞主流程（异常被捕获并记录日志）

### 2. 对比示例库注入 Writer prompt ✅
**文件**: `core/agents/__init__.py`
- 新增 `_load_kb()` 函数：从 `knowledge_base/` 目录加载文件
- 模块级预加载 `_KB_ANTI_AI`、`_KB_BEFORE_AFTER`、`_KB_WRITING_TECHNIQUES`
- `WriterAgent.write_chapter()` 自动注入 `before_after_examples.md` 内容
- 写手写完后可自查是否像"修改前"的反面示例

### 3. 知识库注入 Architect prompt ✅
**文件**: `core/agents/__init__.py`
- `ArchitectAgent.plan_chapter()` 注入 `writing_techniques.md`（写作技巧参考）
- 注入 `anti_ai_rules.md`（去AI味红线）
- 建筑师规划蓝图时可参考写作技巧来设计节拍和节奏建议

---

## P1 修复

### 4. LLM 调用错误处理加固 ✅
**文件**: `core/llm/__init__.py`
- 新增 `logging` 模块导入
- 新增 `_is_retryable()` 函数：智能判断异常是否值得重试
- `with_retry()` 增强：
  - 指数退避（2s → 4s）
  - 不可重试错误直接抛出（不浪费时间）
  - 每次重试自动记录 warning 日志
  - 支持 openai SDK 异常类型（APIConnectionError、RateLimitError 等）
  - 耗尽重试后记录详细错误信息

---

## 知识库扩充

### 5. 写作技巧库扩充 ✅
**文件**: `core/knowledge_base/writing_techniques.md`
- 从 61 行扩充到 265 行（+336%）
- 新增内容：
  - 人物出场模板（神秘人物/反派）
  - 答非所问对话技巧
  - 章末钩子5种类型 + 结尾余韵技巧
  - Show Don't Tell 转换表（8组）
  - 情绪升级阶梯（愤怒/恐惧/悲伤/爱慕）
  - 伏笔埋设手法 + 回收原则 + 铺垫距离
  - 快速修复表

### 6. 番茄小说市场数据引入 ✅
**新增目录**: `core/knowledge_base/fanqie-data/`
- 番茄小说及男性向网文市场数据报告_完整版.md
- 番茄小说男性向详尽调研报告_完整版.md
- 番茄小说男性向读者内容偏好研究报告_完整版.md
- 番茄小说男性向读者用户画像研究报告_完整版.md
- 番茄小说男性用户行为数据分析报告_完整版.md
- 番茄小说用户行为数据.json

### 7. 写作示例引入 ✅
**新增目录**: `core/knowledge_base/examples/`
- `good/`：6个正面示例（对话张力/心理冲突/章末钩子/心理恐惧/神秘出场/雨夜场景）
- `bad/`：1个反面示例（AI味严重）
