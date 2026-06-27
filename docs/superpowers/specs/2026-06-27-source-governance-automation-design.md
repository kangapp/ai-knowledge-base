# 数据源自动治理设计

## 目标

把数据源管理从“手工配置 + 健康页观察”升级为可追溯的自动治理闭环：

```text
发现 -> 候选 -> 试运行 -> 启用 -> 降权/隔离 -> 禁用
```

系统可以自动发现、试跑、评分、降权和禁用数据源，但不自动删除数据源。删除只保留人工操作。

## 非目标

- 不做多用户审批流。
- 不自动启用飞书数据源。
- 不把预算熔断当作数据源质量问题。
- 不因为单次失败或单次低通过率禁用数据源。
- 不继续扩大当前 `sources.yaml` 的职责；它只作为初始配置和人工兜底。

## 状态模型

数据源治理状态使用以下枚举：

| 状态 | 含义 |
| --- | --- |
| `candidate` | 已发现，尚未验证 |
| `trial` | 试运行中，不进入正式内容池 |
| `active` | 正式运行 |
| `degraded` | 质量下降，自动降频或减少 `max_items` |
| `quarantined` | 隔离观察，不进入正式分析和展示 |
| `disabled` | 自动或人工禁用 |
| `rejected` | 人工或规则拒绝候选源 |

人工禁用的源不得被自动恢复。自动禁用的源可以人工恢复到 `trial` 或 `active`。

## 数据模型

新增 `source_registry` 作为运行态数据源注册表：

- `id`
- `name`
- `type`
- `status`
- `enabled`
- `priority`
- `cron`
- `max_items`
- `config_json`
- `manual_override`
- `created_at`
- `updated_at`

新增 `source_health_daily` 保存每日治理指标：

- `source_id`
- `date`
- `request_success_rate`
- `collected`
- `new_items`
- `analyzed`
- `analysis_failed`
- `approved`
- `discarded`
- `avg_score`
- `cost`
- `tokens`
- `health_score`

新增 `source_governance_events` 保存所有自动动作：

- `source_id`
- `event`
- `from_status`
- `to_status`
- `reason`
- `payload_json`
- `created_at`

保留 `discovered_sources`，扩展为候选池和人工审核入口。`sources.yaml` 启动时同步到 `source_registry`，后续调度读取 `source_registry`。

## 发现机制

每周一 09:00 执行发现：

- GitHub：从 Trending 和高质量 GitHub 源中发现新 topic。
- RSS：扫描现有媒体首页的 `<link rel="alternate" type="application/rss+xml">`。
- Hotlist：不自动扩展，只允许人工配置。
- Feishu：不自动发现。

发现结果只写入 `discovered_sources` 和 `source_registry(candidate)`，不直接进入正式调度。

## 试运行机制

`candidate` 可以自动进入 `trial`。试运行源按原采集器请求，但不进入正式文章入库和首页展示。

试运行通过条件：

- 最近 3 次请求成功率不低于 80%。
- 至少 1 次产生新增条目。
- 分析失败不是预算熔断导致。
- 通过率不低于 10%，或平均分不低于 75。

通过后自动变为 `active`。未通过但仍有数据价值的源继续观察 1 次；仍不达标则变为 `rejected`。

## 健康评分

正式源每天计算 `health_score`，范围 0-100：

```text
health_score =
  request_success_rate * 25
+ fresh_rate           * 20
+ approved_rate        * 25
+ avg_score_norm       * 20
+ cost_efficiency      * 10
```

指标定义：

- `request_success_rate`：请求成功率。
- `fresh_rate`：新增数 / 采集数。
- `approved_rate`：通过数 / 新增数。
- `avg_score_norm`：平均分按 100 分归一化。
- `cost_efficiency`：单位成本产出的通过条目数，按全源分位数归一化。

预算熔断产生的 `analysis_failed` 不参与评分，只记录为 `budget_blocked`。

## 自动动作

使用最近 7 天滚动窗口：

- `health_score >= 70`：保持 `active`。
- `50 <= health_score < 70`：保持当前状态，不升级频率。
- `30 <= health_score < 50`：进入 `degraded`，`max_items` 减半或 cron 降频。
- `health_score < 30` 连续 3 次：进入 `quarantined`。
- `quarantined` 连续 3 次仍低于 30：进入 `disabled`。
- 连续 3 次请求失败：进入 `disabled`。
- 连续零命中：只降频，不禁用。

所有动作必须写入 `source_governance_events`。

## 预算联动

预算不足时：

- 记录 `budget_blocked`。
- 不更新源的质量评分。
- 不把该轮计入 `analysis_failed` 质量惩罚。
- Dashboard 单独显示“预算阻断”。

预算恢复后，源从原状态继续运行，不需要人工干预。

## Dashboard

数据源健康页按状态分组：

- 正式运行：`active`、`degraded`
- 隔离观察：`quarantined`
- 候选试跑：`candidate`、`trial`
- 已停用：`disabled`、`rejected`

每行展示：

- 状态
- 最近运行时间
- 请求成功率
- 新增率
- 通过率
- 平均分
- 成本/通过
- 最近自动动作原因
- 手动操作：启用、禁用、拒绝、恢复、固定保护

## API

新增或扩展：

- `GET /api/sources/stats`：返回治理状态和评分。
- `GET /api/sources/discovered`：返回候选和试运行源。
- `POST /api/sources/{source_id}/action`：支持 `enable`、`disable`、`reject`、`restore`、`protect`。
- `GET /api/sources/{source_id}/events`：返回治理事件。

现有统一响应信封保持不变。

## 调度与数据流

启动时：

1. 从 `sources.yaml` 同步内置源到 `source_registry`。
2. 调度器只注册 `active`、`degraded`、`trial` 源。
3. `trial` 源采集和分析结果写健康事实，但不入正式文章表。

流水线结束时：

1. 写入 `pipeline_source_runs`。
2. 汇总到 `source_health_daily`。
3. 更新 `health_score`。
4. 执行治理状态迁移。
5. 记录 `source_governance_events`。

## 测试

最小测试覆盖：

- 启动同步不会覆盖人工禁用状态。
- discovered source 只进入 `candidate`，不会自动写入正式配置。
- trial 满足规则后进入 `active`。
- budget hard limit 不降低 `health_score`。
- 连续 3 次请求失败进入 `disabled`。
- 连续低分按 `active -> degraded -> quarantined -> disabled` 迁移。
- Dashboard API 返回状态、分数、最近事件和人工操作字段。

## 实施顺序

1. 新增表和注册表同步，不改变现有采集行为。
2. 让调度读取 `source_registry`。
3. 自动发现只进入 candidate。
4. 加 trial 试运行。
5. 加健康评分和治理事件。
6. 加 degraded/quarantined/disabled 自动迁移。
7. 更新 Dashboard 和 API。

