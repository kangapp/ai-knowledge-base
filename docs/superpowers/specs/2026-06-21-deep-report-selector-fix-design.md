# Deep Report 候选选择修复设计

## 背景

生产环境自 2026-06-12 后没有自动生成新的深度报告。生成、仓库扫描和持久化
链路没有报错，所有运行都在候选选择阶段返回 `no candidate`。

当前 Selector 依赖少量英文精确短语识别 Coding 能力，并对 Reviewer 分和候选分
分别设置 85 分门槛。真实 GitHub description 较短，Analyzer 输出主要为中文，
导致 `goose`、`context7`、`rtk`、`ponytail` 等 Coding 工具被误判为无交付证据。

## 目标

- 恢复符合条件的 Coding 工具深度报告生成。
- 继续排除论文、模型权重、数据集、benchmark、资源合集和通用 AI 框架。
- 候选资格由结构化字段决定，不再依赖中英文关键词词表。
- `no candidate` 时能看到各拒绝原因的数量。

## 非目标

- 不调整 Deep Report 的 clone、源码扫描、LLM 分析或入库逻辑。
- 不为历史文章批量补写 `project_type`。
- 不自动重建历史报告。
- 不改变每轮最多生成一份深度报告的约定。

## GitHub Analyzer 输出

`AnalyzedItem` 增加可选字段：

```python
project_type: str | None = None
```

GitHub Analyzer 必须输出以下枚举之一：

| 值 | 含义 |
|---|---|
| `coding_tool` | 直接服务于编码、代码理解、代码生成、测试、调试、IDE/CLI、开发自动化或 Coding Agent |
| `ai_infrastructure` | LLM 网关、向量库、通用 Agent/RAG 平台、模型服务等 AI 基础设施 |
| `framework` | 通用编程、ML、深度学习或应用开发框架 |
| `research` | 论文、研究实现、评测研究或模型权重 |
| `dataset` | 数据集或数据集构建项目 |
| `benchmark` | benchmark、leaderboard、evaluation suite 或 testbed |
| `resource_collection` | awesome list、课程、教程、知识库或资源合集 |
| `other` | 不属于以上类型 |

GitHub Prompt 必须要求根据仓库“主要交付物”分类，而不是根据 topics 或偶然出现的
关键词分类。例如：提供 MCP 接口的日历工具仍是 `other`；供 Coding Agent 使用的
代码文档 MCP 服务是 `coding_tool`。

非 GitHub Analyzer 不需要输出该字段。

## 兼容策略

`project_type` 是可选字段，避免影响旧数据和非 GitHub Analyzer。

Deep Report Selector 对缺失或未知的 `project_type` 采取 fail closed：
拒绝该候选，并记录拒绝原因 `project_type_missing`。不回退到旧关键词算法。

这意味着修复部署后的新流水线会使用结构化分类；历史数据只能通过显式 rebuild
或重新分析进入候选，不做隐式猜测。

## 候选资格

候选必须同时满足：

1. Reviewer verdict 为 `approved`。
2. Reviewer 总分至少 85。
3. 原始条目是合法的 GitHub 仓库 URL。
4. `project_type == "coding_tool"`。
5. Reviewer `ai_relevance` 至少 28。
6. Reviewer `developer_utility` 至少 24。
7. 同一仓库最近 7 天没有 completed 深度报告。

不再使用 `_coding_capabilities()` 作为资格条件，也不设置二次候选分门槛。

## 排序

多个合格候选按以下分数选择最高者：

```text
candidate_score =
    reviewer_total × 0.7
    + developer_utility × 0.6
    + source_bonus
```

其中：

- `github_ai_devtools`：`source_bonus = 5`
- 其他 GitHub 来源：`source_bonus = 0`
- 最终使用 `round()` 转为整数

候选分仅用于排序和审计，不作为第三道准入门槛。分数相同时保持 Reviewer 输出顺序，
不增加额外排序规则。

## Reviewer 维度读取

Selector 从 `ReviewedItem.dimensions` 读取：

```text
ai_relevance.score
developer_utility.score
```

字段缺失、类型错误或不可转为整数时按 0 处理，并按对应维度不足拒绝，不抛异常。

## 可观测性

Selector 返回候选和本轮选择诊断：

```json
{
  "reviewed_total": 10,
  "approved_github": 4,
  "eligible": 1,
  "rejected": {
    "not_approved": 3,
    "reviewer_score": 1,
    "not_github": 1,
    "invalid_repo_url": 0,
    "project_type_missing": 1,
    "project_type": 1,
    "ai_relevance": 1,
    "developer_utility": 1,
    "recent_report": 0
  }
}
```

每个 ReviewedItem 只计入第一个失败原因，顺序与“候选资格”一致，保证汇总数量可解释。

`run_deep_report_stage()`：

- 在 `deep.selector_skipped` 的 payload 中记录完整诊断。
- 找到候选时新增 `deep.selector_done` 事件，记录诊断、候选分和 `project_type`。
- 阶段返回契约保持不变。

不为每个被拒条目写单独事件，避免流水线事件膨胀。

## 测试

### Analyzer

- GitHub Prompt 包含全部 `project_type` 枚举与分类边界。
- GitHub Analyzer 输出可解析并透传 `project_type`。
- 非 GitHub Analyzer 不提供该字段时仍可正常校验。
- Prompt 回归测试继续通过。

### Selector 生产样本

应接受：

- `aaif-goose/goose`
- `upstash/context7`
- `rtk-ai/rtk`
- `DietrichGebert/ponytail`

这些 fixture 必须显式提供 `project_type="coding_tool"` 和合格 Reviewer 维度。

应拒绝：

- `ultralytics/yolov5`：`framework`
- `keras-team/keras`：`framework`
- 论文或模型权重：`research`
- 数据集：`dataset`
- evaluation suite：`benchmark`
- awesome list 或课程：`resource_collection`
- `project_type` 缺失或未知
- Reviewer 分、AI 相关度或开发者实用性未达门槛
- 7 天内已有 completed 报告

### 可观测性

- 每个条目只进入一个拒绝原因。
- `deep.selector_skipped` 带完整诊断。
- `deep.selector_done` 带候选分、类型和诊断。

### 验证命令

```bash
.venv/bin/python -m pytest \
  tests/test_deep_reports_selector.py \
  tests/test_deep_reports_pipeline.py \
  tests/test_analyzer.py \
  tests/test_prompt_regression.py -q

.venv/bin/python -m pytest \
  tests/test_deep_reports_analyzer.py \
  tests/test_deep_reports_db.py \
  tests/test_deep_reports_api.py \
  tests/test_repo_inspector.py -q
```

## 文档同步

- 更新 `docs/architecture.md`：候选资格和结构化项目类型。
- 更新 `docs/codemap.md`：Selector 的新职责与诊断事件。
- 更新 `docs/task.md`：记录根因、修复和验证结果。
- 更新 `docs/bug-progress.md`：记录本次生产问题。
