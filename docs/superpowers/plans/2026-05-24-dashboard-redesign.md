# 仪表盘重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构仪表盘三个 Tab（数据质量、资源消耗、数据源健康），统一时间切换器，优化指标展示

**Architecture:** 后端扩展 API 端点返回新数据结构，前端重写 Tab 渲染逻辑，新增 Chart.js 图表类型

**Tech Stack:** FastAPI + Jinja2 + Chart.js + aiosqlite

---

## 实现 Phase 总览

| Phase | 内容 | 优先级 |
|-------|------|-------|
| Phase 1 | 数据质量 Tab | P0 |
| Phase 2 | 资源消耗 Tab | P0 |
| Phase 3 | 数据源健康 Tab（前端调整） | P1 |

---

## Phase 1: 数据质量 Tab

### 1.1 里程碑

- [ ] **M1.1**: `GET /api/stats/quality-detail` 端点返回完整四维评分数据
- [ ] **M1.2**: 前端雷达图、堆叠柱状图、词云正常渲染
- [ ] **M1.3**: 日/周/月切换正确联动
- [ ] **M1.4**: 集成测试通过

### 1.2 验收测试

```bash
# 测试 API 端点返回正确结构
curl -s "http://localhost:8000/api/stats/quality-detail?period=week" | jq '.data.dimensions'

# 验证返回包含四维评分
# 预期：{"ai_relevance": {...}, "内容深度": {...}, "信息密度": {...}, "时效性": {...}}

# 测试前端渲染
# 1. 访问 /dashboard
# 2. 切换到数据质量 Tab
# 3. 验证雷达图显示（4条轴）
# 4. 验证堆叠柱状图显示
# 5. 验证词云显示
# 6. 切换日/周/月，验证数据变化
```

### 1.3 详细步骤

#### Step 1: 扩展 `src/db/operations.py` 添加质量详情查询

**文件:** `src/db/operations.py`

**末尾添加:**

```python
async def get_quality_detail_stats(db: Database, period: str = "week") -> dict:
    """
    数据质量详细统计（Phase 1）
    period: day(1) / week(7) / month(30)
    """
    days_map = {"day": 1, "week": 7, "month": 30}
    days = days_map.get(period, 7)

    # 1. 内容完整性指标
    summary_coverage = await db.fetch_one("""
        SELECT COUNT(*) * 1.0 / (SELECT COUNT(*) FROM articles WHERE status='approved' AND collected_at >= date('now', ?)) as rate
        FROM articles WHERE status='approved' AND summary IS NOT NULL AND summary != '' AND collected_at >= date('now', ?)
    """, (f"-{days} days", f"-{days} days"))

    desc_len = await db.fetch_one("""
        SELECT AVG(LENGTH(description)) as avg_len FROM articles WHERE status='approved' AND collected_at >= date('now', ?)
    """, (f"-{days} days",))

    summary_len = await db.fetch_one("""
        SELECT AVG(LENGTH(summary)) as avg_len FROM articles WHERE status='approved' AND summary IS NOT NULL AND collected_at >= date('now', ?)
    """, (f"-{days} days",))

    # 2. 审核效率指标
    one_pass = await db.fetch_one("""
        SELECT COUNT(*) * 1.0 / (SELECT COUNT(*) FROM articles WHERE status='approved' AND collected_at >= date('now', ?)) as rate
        FROM articles WHERE status='approved' AND retry_count = 0 AND collected_at >= date('now', ?)
    """, (f"-{days} days", f"-{days} days"))

    retry_rate = await db.fetch_one("""
        SELECT COUNT(*) * 1.0 / (SELECT COUNT(*) FROM articles WHERE collected_at >= date('now', ?)) as rate
        FROM articles WHERE status='retry' AND collected_at >= date('now', ?)
    """, (f"-{days} days", f"-{days} days"))

    exhausted_rate = await db.fetch_one("""
        SELECT COUNT(*) * 1.0 / (SELECT COUNT(*) FROM articles WHERE collected_at >= date('now', ?)) as rate
        FROM articles WHERE retry_count >= 2 AND collected_at >= date('now', ?)
    """, (f"-{days} days", f"-{days} days"))

    # 3. 标签覆盖指标
    tagged_rate = await db.fetch_one("""
        SELECT COUNT(DISTINCT at.article_id) * 1.0 / (SELECT COUNT(*) FROM articles WHERE status='approved' AND collected_at >= date('now', ?)) as rate
        FROM article_tags at
        JOIN articles a ON a.id = at.article_id
        WHERE a.collected_at >= date('now', ?)
    """, (f"-{days} days", f"-{days} days"))

    avg_tags = await db.fetch_one("""
        SELECT AVG(tag_count) as avg FROM (
            SELECT COUNT(*) as tag_count FROM article_tags at
            JOIN articles a ON a.id = at.article_id
            WHERE a.collected_at >= date('now', ?)
            GROUP BY at.article_id
        )
    """, (f"-{days} days",))

    # 4. 四维评分统计（从 extra_data JSON 解析）
    dimensions = ["ai_relevance", "内容深度", "信息密度", "时效性"]
    dimension_stats = {}
    for dim in dimensions:
        stats = await db.fetch_one(f"""
            SELECT
                AVG(JSON_EXTRACT(extra_data, '$.dimensions.{dim}.score')) as avg_score,
                COUNT(CASE WHEN JSON_EXTRACT(extra_data, '$.dimensions.{dim}.score') >= ? THEN 1 END) * 1.0 / COUNT(*) as high_rate,
                COUNT(CASE WHEN JSON_EXTRACT(extra_data, '$.dimensions.{dim}.score') >= ? AND JSON_EXTRACT(extra_data, '$.dimensions.{dim}.score') < ? THEN 1 END) * 1.0 / COUNT(*) as mid_rate,
                COUNT(CASE WHEN JSON_EXTRACT(extra_data, '$.dimensions.{dim}.score') < ? THEN 1 END) * 1.0 / COUNT(*) as low_rate
            FROM articles
            WHERE status='approved' AND extra_data IS NOT NULL AND collected_at >= date('now', ?)
        """, (0.6, 0.3, 0.6, 0.3, f"-{days} days"))
        dimension_stats[dim] = {
            "avg_score": round(stats["avg_score"] or 0, 1),
            "high_rate": round(stats["high_rate"] or 0, 3),
            "mid_rate": round(stats["mid_rate"] or 0, 3),
            "low_rate": round(stats["low_rate"] or 0, 3),
        }

    # 5. Reason 关键词（从 extra_data 提取）
    reason_rows = await db.fetch_all("""
        SELECT JSON_EXTRACT(extra_data, '$.dimensions."AI相关度".reason') as reason
        FROM articles WHERE status='approved' AND extra_data IS NOT NULL AND collected_at >= date('now', ?)
    """, (f"-{days} days",))

    # 简单词频统计（实际应用需要分词，这里简化处理）
    keyword_count = {}
    for row in reason_rows:
        if row["reason"]:
            # 提取中文词汇（简化版）
            import re
            words = re.findall(r'[一-龥]+', row["reason"])
            for w in words:
                keyword_count[w] = keyword_count.get(w, 0) + 1

    top_keywords = sorted(keyword_count.items(), key=lambda x: x[1], reverse=True)[:20]

    return {
        "content_quality": {
            "summary_coverage": round(summary_coverage["rate"] if summary_coverage and summary_coverage["rate"] else 0, 3),
            "avg_desc_length": round(desc_len["avg_len"] if desc_len and desc_len["avg_len"] else 0, 1),
            "avg_summary_length": round(summary_len["avg_len"] if summary_len and summary_len["avg_len"] else 0, 1),
        },
        "audit_efficiency": {
            "one_pass_rate": round(one_pass["rate"] if one_pass and one_pass["rate"] else 0, 3),
            "retry_rate": round(retry_rate["rate"] if retry_rate and retry_rate["rate"] else 0, 3),
            "exhausted_rate": round(exhausted_rate["rate"] if exhausted_rate and exhausted_rate["rate"] else 0, 3),
        },
        "tag_coverage": {
            "tagged_rate": round(tagged_rate["rate"] if tagged_rate and tagged_rate["rate"] else 0, 3),
            "avg_tags": round(avg_tags["avg"] if avg_tags and avg_tags["avg"] else 0, 1),
        },
        "dimensions": dimension_stats,
        "reason_keywords": [{"word": w, "count": c} for w, c in top_keywords],
    }
```

- [ ] **Step 1.1**: 添加上述函数到 `src/db/operations.py`

Run: `grep -n "async def get_quality_detail_stats" src/db/operations.py`
Expected: 找到函数定义

- [ ] **Step 1.2**: 运行测试验证 SQL 语法

Run: `cd /Users/liufukang/Workplace/ai-knowledge-base && uv run python -c "import asyncio; from src.db import get_db; asyncio.run(get_db())"`
Expected: 无错误

#### Step 2: 添加 API 端点

**文件:** `src/api/stats.py`

**末尾添加:**

```python
@router.get("/quality-detail")
async def get_stats_quality_detail(period: str = Query(default="week", regex="^(day|week|month)$")):
    db = get_db()
    return envelope(await operations.get_quality_detail_stats(db, period))
```

- [ ] **Step 2.1**: 添加端点

Run: `grep -n "quality-detail" src/api/stats.py`
Expected: 找到端点定义

- [ ] **Step 2.2**: 测试端点

Run: `curl -s "http://localhost:8000/api/stats/quality-detail?period=week" | jq '.code'`
Expected: `0`

#### Step 3: 重写前端数据质量 Tab HTML

**文件:** `src/site/templates/dashboard.html`

**替换 `<div id="tab-quality" class="tab-content active">` 整个内容为:**

```html
<div id="tab-quality" class="tab-content active">
    <!-- 顶部 KPI -->
    <div class="kpi-row" style="display:flex;gap:1rem;margin-bottom:1rem">
        <div class="kpi-card" style="flex:1">
            <div class="kpi-label">通过率</div>
            <div class="kpi-value" id="q-pass-rate">-</div>
        </div>
        <div class="kpi-card" style="flex:1">
            <div class="kpi-label">平均评分</div>
            <div class="kpi-value" id="q-avg-score">-</div>
        </div>
        <div class="kpi-card" style="flex:1">
            <div class="kpi-label">一次通过</div>
            <div class="kpi-value" id="q-one-pass">-</div>
        </div>
        <div class="kpi-card" style="flex:1">
            <div class="kpi-label">有标签占比</div>
            <div class="kpi-value" id="q-tag-rate">-</div>
        </div>
    </div>

    <!-- 第一行：分布图表 -->
    <div class="charts-layout" style="margin-bottom:1rem">
        <div class="chart-card">
            <h3>内容质量分布</h3>
            <div class="chart-canvas-wrapper"><canvas id="q-content-chart"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>来源质量对比</h3>
            <div class="chart-canvas-wrapper"><canvas id="q-source-chart"></canvas></div>
        </div>
    </div>

    <!-- 第二行：四维评分 -->
    <div class="charts-layout" style="margin-bottom:1rem">
        <div class="chart-card">
            <h3>四维平均分</h3>
            <div class="chart-canvas-wrapper"><canvas id="q-radar-chart"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>维度评分分布</h3>
            <div class="chart-canvas-wrapper"><canvas id="q-dimension-chart"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>Reason 关键词</h3>
            <div class="tag-cloud" id="q-keyword-cloud" style="padding:1rem"></div>
        </div>
    </div>
</div>
```

- [ ] **Step 3.1**: 更新 HTML

Run: `grep -n "q-pass-rate" src/site/templates/dashboard.html`
Expected: 找到元素 ID

#### Step 4: 添加前端渲染函数

**文件:** `src/site/static/js/app.js`

**在 `renderQuality` 函数后添加:**

```javascript
async function loadQualityTab(days) {
    const res = await fetch(`/api/stats/quality-detail?period=${days === 7 ? 'week' : days === 30 ? 'month' : 'day'}`);
    const json = await res.json();
    if (json.code !== 0) return null;
    return json.data;
}

function renderQualityDetail(data) {
    if (!data) return;

    // KPI 卡片
    document.getElementById('q-pass-rate').textContent = data.audit_efficiency ?
        (data.audit_efficiency.one_pass_rate * 100).toFixed(0) + '%' : '-';
    document.getElementById('q-avg-score').textContent = data.dimensions ?
        ((data.dimensions.ai_relevance?.avg_score || 0) / 40 * 100).toFixed(0) : '-';
    document.getElementById('q-one-pass').textContent = data.audit_efficiency ?
        (data.audit_efficiency.one_pass_rate * 100).toFixed(0) + '%' : '-';
    document.getElementById('q-tag-rate').textContent = data.tagCoverage ?
        (data.tagCoverage.tagged_rate * 100).toFixed(0) + '%' : '-';

    // 内容质量分布柱状图
    if (data.content_quality) {
        const cq = data.content_quality;
        renderBarChart('q-content-chart',
            ['Summary覆盖', '有标签', '一次通过', 'Exhausted', 'Retry'],
            [(cq.summary_coverage || 0) * 100, (data.tagCoverage?.tagged_rate || 0) * 100,
             (data.audit_efficiency?.one_pass_rate || 0) * 100,
             (data.audit_efficiency?.exhausted_rate || 0) * 100,
             (data.audit_efficiency?.retry_rate || 0) * 100],
            '#4F46E5');
    }

    // 来源质量对比柱状图（复用原有数据）
    const sourceScores = data.source_scores || [];
    if (sourceScores.length > 0) {
        renderBarChart('q-source-chart',
            sourceScores.slice(0, 4).map(s => s.source_detail || s.source),
            sourceScores.slice(0, 4).map(s => s.avg_score || 0),
            '#10b981');
    }

    // 四维评分雷达图
    if (data.dimensions) {
        const dims = data.dimensions;
        const radarLabels = ['AI相关度', '内容深度', '信息密度', '时效性'];
        const radarData = [
            ((dims.ai_relevance?.avg_score || 0) / 40 * 100).toFixed(1),
            ((dims.内容深度?.avg_score || 0) / 30 * 100).toFixed(1),
            ((dims.信息密度?.avg_score || 0) / 15 * 100).toFixed(1),
            ((dims.时效性?.avg_score || 0) / 15 * 100).toFixed(1),
        ];
        renderRadarChart('q-radar-chart', radarLabels, radarData);
    }

    // 维度评分分布堆叠柱状图
    if (data.dimensions) {
        const dims = data.dimensions;
        const dimLabels = ['AI相关度', '内容深度', '信息密度', '时效性'];
        const highData = [dims.ai_relevance?.high_rate || 0, dims.内容深度?.high_rate || 0,
                         dims.信息密度?.high_rate || 0, dims.时效性?.high_rate || 0].map(v => v * 100);
        const midData = [dims.ai_relevance?.mid_rate || 0, dims.内容深度?.mid_rate || 0,
                        dims.信息密度?.mid_rate || 0, dims.时效性?.mid_rate || 0].map(v => v * 100);
        const lowData = [dims.ai_relevance?.low_rate || 0, dims.内容深度?.low_rate || 0,
                        dims.信息密度?.low_rate || 0, dims.时效性?.low_rate || 0].map(v => v * 100);
        renderStackedBar('q-dimension-chart', dimLabels, [
            { label: '高', data: highData, backgroundColor: '#10b981' },
            { label: '中', data: midData, backgroundColor: '#f59e0b' },
            { label: '低', data: lowData, backgroundColor: '#ef4444' },
        ]);
    }

    // Reason 关键词云
    const cloud = document.getElementById('q-keyword-cloud');
    if (cloud && data.reason_keywords) {
        const keywords = data.reason_keywords.slice(0, 15);
        cloud.innerHTML = keywords.map(k => {
            const size = k.count > 5 ? 'large' : k.count > 2 ? 'medium' : 'small';
            return `<span class="tag-item ${size}" style="margin:4px">${k.word}</span>`;
        }).join('');
    }
}

function renderRadarChart(canvasId, labels, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    if (ctx._chart) ctx._chart.destroy();
    ctx._chart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: 'rgba(79,70,229,0.25)',
                borderColor: '#4F46E5',
                borderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { r: { min: 0, max: 100 } },
            plugins: { legend: { display: false } }
        }
    });
}
```

**修改 `renderTab` 函数中 quality 部分:**

```javascript
async function renderTab(tab) {
    if (tab === 'sources') {
        // ... existing sources code
    } else if (tab === 'quality') {
        const data = await loadQualityTab(state.quality);
        if (data) renderQualityDetail(data);
        return;
    }
    // ... rest unchanged
}
```

- [ ] **Step 4.1**: 添加新的渲染函数

Run: `grep -n "renderRadarChart" src/site/static/js/app.js`
Expected: 找到函数定义

- [ ] **Step 4.2**: 验证质量详情加载

Run: 启动服务器后访问 /dashboard，切换到数据质量 Tab
Expected: 雷达图、堆叠图、词云正常显示

#### Step 5: 集成测试

- [ ] **Step 5.1**: API 测试

```bash
curl -s "http://localhost:8000/api/stats/quality-detail?period=week" | jq '.data | keys'
```

- [ ] **Step 5.2**: 前端渲染测试

1. 访问 http://localhost:8000/dashboard
2. 验证数据质量 Tab 显示 4 个 KPI 卡片
3. 验证雷达图显示 4 条轴
4. 验证堆叠柱状图显示高/中/低分布
5. 验证词云显示关键词
6. 切换日/周/月，验证数据变化

#### Step 6: 提交

```bash
git add src/db/operations.py src/api/stats.py src/site/templates/dashboard.html src/site/static/js/app.js
git commit -m "feat(dashboard): Phase 1 - 数据质量 Tab 重构

- 新增 GET /api/stats/quality-detail 端点
- 新增四维评分统计（AI相关度、内容深度、信息密度、时效性）
- 新增内容完整性、审核效率、标签覆盖指标
- 新增雷达图、堆叠柱状图、Reason词云
- 日/周/月切换联动"
```

---

## Phase 2: 资源消耗 Tab

### 2.1 里程碑

- [ ] **M2.1**: `GET /api/stats/consumption-detail` 端点返回费用趋势数据
- [ ] **M2.2**: 来源费用趋势柱状图正常渲染（分析+审核堆叠）
- [ ] **M2.3**: Provider 费用趋势柱状图正常渲染
- [ ] **M2.4**: 日/周/月切换正确联动
- [ ] **M2.5**: 集成测试通过

### 2.2 验收测试

```bash
# 测试 API 端点返回正确结构
curl -s "http://localhost:8000/api/stats/consumption-detail?period=week" | jq '.data | keys'

# 验证返回包含费用趋势
# 预期：{ source_trend: [...], provider_trend: [...] }
```

### 2.3 详细步骤

#### Step 1: 扩展 `src/db/operations.py` 添加费用详情查询

**文件:** `src/db/operations.py`

**末尾添加:**

```python
async def get_consumption_detail_stats(db: Database, period: str = "week") -> dict:
    """
    资源消耗详细统计（Phase 2）
    period: day(1) / week(7) / month(30)
    """
    days_map = {"day": 1, "week": 7, "month": 30}
    days = days_map.get(period, 7)

    # 1. 周期总花费和日均
    period_cost = await db.fetch_one("""
        SELECT COALESCE(SUM(cost), 0) as total FROM cost_logs
        WHERE created_at >= date('now', ?)
    """, (f"-{days} days",))

    period_days = await db.fetch_one("""
        SELECT COUNT(DISTINCT date(created_at)) as days FROM cost_logs
        WHERE created_at >= date('now', ?)
    """, (f"-{days} days",))

    # 2. Token 效率
    period_tokens = await db.fetch_one("""
        SELECT COALESCE(SUM(tokens_in + tokens_out), 0) as total FROM cost_logs
        WHERE created_at >= date('now', ?)
    """, (f"-{days} days",))

    # 3. 花费趋势（按周，支持日/月切换）
    if period == "day":
        trend_sql = """
            SELECT date(created_at) as label,
                   SUM(cost) as cost, COUNT(*) as articles
            FROM cost_logs WHERE created_at >= date('now', ?)
            GROUP BY date(created_at) ORDER BY label
        """
    elif period == "week":
        trend_sql = """
            SELECT strftime('%Y-W%W', created_at) as label,
                   SUM(cost) as cost, COUNT(*) as articles
            FROM cost_logs WHERE created_at >= date('now', '-12 weeks')
            GROUP BY label ORDER BY label
        """
    else:  # month
        trend_sql = """
            SELECT strftime('%Y-%m', created_at) as label,
                   SUM(cost) as cost, COUNT(*) as articles
            FROM cost_logs WHERE created_at >= date('now', '-12 months')
            GROUP BY label ORDER BY label
        """

    trend = await db.fetch_all(trend_sql, (f"-{days} days",) if period == "day" else ())

    # 4. 来源费用趋势（分析 + 审核）
    # agent 字段: github_analyzer, rss_analyzer, feishu_analyzer, arxiv_analyzer, reviewer
    source_trend_sql = """
        SELECT
            CASE
                WHEN agent LIKE '%_analyzer' THEN SUBSTR(agent, 1, LENGTH(agent) - 8)
                ELSE agent
            END as source,
            CASE WHEN agent LIKE '%_analyzer' THEN 'analyze' ELSE 'review' END as type,
            date(created_at) as date,
            SUM(cost) as cost
        FROM cost_logs
        WHERE created_at >= date('now', ?)
        GROUP BY source, type, date(created_at)
        ORDER BY date
    """

    if period == "day":
        source_trend = await db.fetch_all(source_trend_sql, (f"-{days} days",))
    elif period == "week":
        source_trend = await db.fetch_all("""
            SELECT
                CASE WHEN agent LIKE '%_analyzer' THEN SUBSTR(agent, 1, LENGTH(agent) - 8) ELSE agent END as source,
                CASE WHEN agent LIKE '%_analyzer' THEN 'analyze' ELSE 'review' END as type,
                strftime('%Y-W%W', created_at) as label,
                SUM(cost) as cost
            FROM cost_logs WHERE created_at >= date('now', '-12 weeks')
            GROUP BY source, type, label ORDER BY label
        """)
    else:
        source_trend = await db.fetch_all("""
            SELECT
                CASE WHEN agent LIKE '%_analyzer' THEN SUBSTR(agent, 1, LENGTH(agent) - 8) ELSE agent END as source,
                CASE WHEN agent LIKE '%_analyzer' THEN 'analyze' ELSE 'review' END as type,
                strftime('%Y-%m', created_at) as label,
                SUM(cost) as cost
            FROM cost_logs WHERE created_at >= date('now', '-12 months')
            GROUP BY source, type, label ORDER BY label
        """)

    # 5. Provider 费用趋势
    provider_trend_sql = """
        SELECT date(created_at) as date, provider, SUM(cost) as cost
        FROM cost_logs WHERE created_at >= date('now', ?)
        GROUP BY provider, date(created_at) ORDER BY date
    """

    if period == "day":
        provider_trend = await db.fetch_all(provider_trend_sql, (f"-{days} days",))
    elif period == "week":
        provider_trend = await db.fetch_all("""
            SELECT strftime('%Y-W%W', created_at) as label, provider, SUM(cost) as cost
            FROM cost_logs WHERE created_at >= date('now', '-12 weeks')
            GROUP BY provider, label ORDER BY label
        """)
    else:
        provider_trend = await db.fetch_all("""
            SELECT strftime('%Y-%m', created_at) as label, provider, SUM(cost) as cost
            FROM cost_logs WHERE created_at >= date('now', '-12 months')
            GROUP BY provider, label ORDER BY label
        """)

    # 6. 预算进度（硬编码月度预算 $15）
    budget = 15.0
    monthly_cost = await db.fetch_one("""
        SELECT COALESCE(SUM(cost), 0) as total FROM cost_logs
        WHERE created_at >= date('now', '-30 days')
    """)

    return {
        "period_cost": round(period_cost["total"] if period_cost else 0, 4),
        "daily_avg": round((period_cost["total"] or 0) / max(period_days["days"] if period_days else 1, 1), 4),
        "token_efficiency": round((period_cost["total"] or 0) / max(period_tokens["total"] if period_tokens else 1, 1) * 1e6, 2),
        "budget_progress": round((monthly_cost["total"] or 0) / budget, 3),
        "budget_remaining": round(budget - (monthly_cost["total"] or 0), 2),
        "trend": [{"label": r["label"], "cost": r["cost"], "articles": r["articles"]} for r in trend] if isinstance(trend[0], dict) and "label" in trend[0] else [],
        "source_trend": [{"source": r["source"], "type": r["type"], "label": r.get("label") or r.get("date"), "cost": r["cost"]} for r in source_trend],
        "provider_trend": [{"provider": r["provider"], "label": r.get("label") or r.get("date"), "cost": r["cost"]} for r in provider_trend],
    }
```

- [ ] **Step 1.1**: 添加费用详情查询函数

#### Step 2: 添加 API 端点

**文件:** `src/api/stats.py`

**末尾添加:**

```python
@router.get("/consumption-detail")
async def get_stats_consumption_detail(period: str = Query(default="week", regex="^(day|week|month)$")):
    db = get_db()
    return envelope(await operations.get_consumption_detail_stats(db, period))
```

- [ ] **Step 2.1**: 添加端点

#### Step 3: 重写前端资源消耗 Tab HTML

**文件:** `src/site/templates/dashboard.html`

**替换 `<div id="tab-consumption" class="tab-content">` 整个内容为:**

```html
<div id="tab-consumption" class="tab-content">
    <!-- 顶部 KPI -->
    <div class="kpi-row" style="display:flex;gap:1rem;margin-bottom:1rem">
        <div class="kpi-card" style="flex:1">
            <div class="kpi-label">周期花费</div>
            <div class="kpi-value" id="cs-period-cost">-</div>
        </div>
        <div class="kpi-card" style="flex:1">
            <div class="kpi-label">日均花费</div>
            <div class="kpi-value" id="cs-daily-avg">-</div>
        </div>
        <div class="kpi-card" style="flex:1">
            <div class="kpi-label">Token 效率</div>
            <div class="kpi-value" id="cs-token-eff">-</div>
            <div class="kpi-sub">$/M tokens</div>
        </div>
        <div class="kpi-card" style="flex:1">
            <div class="kpi-label">预算进度</div>
            <div class="kpi-value" id="cs-budget-progress">-</div>
            <div class="progress-bar-wrapper"><div class="progress-bar" id="cs-progress-bar"></div></div>
        </div>
    </div>

    <!-- 花费趋势折线图 -->
    <div class="chart-card" style="margin-bottom:1rem">
        <h3>花费趋势</h3>
        <div class="chart-canvas-wrapper"><canvas id="cs-trend-chart"></canvas></div>
    </div>

    <!-- 费用分解 -->
    <div class="charts-layout">
        <div class="chart-card">
            <h3>来源费用分解</h3>
            <div class="chart-canvas-wrapper"><canvas id="cs-source-chart"></canvas></div>
        </div>
        <div class="chart-card">
            <h3>Provider 费用</h3>
            <div class="chart-canvas-wrapper"><canvas id="cs-provider-chart"></canvas></div>
        </div>
    </div>
</div>
```

- [ ] **Step 3.1**: 更新 HTML

#### Step 4: 添加前端渲染函数

**文件:** `src/site/static/js/app.js`

**添加函数:**

```javascript
async function loadConsumptionTab(days) {
    const period = days === 1 ? 'day' : days === 7 ? 'week' : 'month';
    const res = await fetch(`/api/stats/consumption-detail?period=${period}`);
    const json = await res.json();
    if (json.code !== 0) return null;
    return json.data;
}

function renderConsumptionDetail(data) {
    if (!data) return;

    // KPI
    document.getElementById('cs-period-cost').textContent = '$' + (data.period_cost || 0).toFixed(2);
    document.getElementById('cs-daily-avg').textContent = '$' + (data.daily_avg || 0).toFixed(2);
    document.getElementById('cs-token-eff').textContent = '$' + (data.token_efficiency || 0);
    const progress = (data.budget_progress || 0) * 100;
    document.getElementById('cs-budget-progress').textContent = progress.toFixed(0) + '%';
    const bar = document.getElementById('cs-progress-bar');
    if (bar) {
        bar.style.width = Math.min(progress, 100) + '%';
        bar.className = 'progress-bar' + (progress > 80 ? ' danger' : progress > 50 ? ' warning' : '');
    }

    // 花费趋势折线图（不变）
    if (data.trend && data.trend.length > 0) {
        renderLineChart('cs-trend-chart',
            data.trend.map(t => t.label),
            data.trend.map(t => t.cost),
            '#ef4444');
    }

    // 来源费用分解柱状图
    if (data.source_trend && data.source_trend.length > 0) {
        const sources = [...new Set(data.source_trend.map(s => s.source))];
        const labels = [...new Set(data.source_trend.map(s => s.label))];
        const analyzeData = sources.map(src =>
            labels.map(lbl => {
                const found = data.source_trend.find(s => s.source === src && s.type === 'analyze' && s.label === lbl);
                return found ? found.cost : 0;
            })
        );
        const reviewData = sources.map(src =>
            labels.map(lbl => {
                const found = data.source_trend.find(s => s.source === src && s.type === 'review' && s.label === lbl);
                return found ? found.cost : 0;
            })
        );
        const datasets = [
            { label: '分析', data: analyzeData.reduce((a, b) => a.map((v, i) => v + b[i]), new Array(labels.length).fill(0)), backgroundColor: '#8b5cf6' },
            { label: '审核', data: reviewData.reduce((a, b) => a.map((v, i) => v + b[i]), new Array(labels.length).fill(0)), backgroundColor: '#6366f1' },
        ];
        // 简化：只显示总分析+审核按来源
        const sourceTotals = sources.map((src, i) => ({
            source: src,
            analyze: analyzeData[i].reduce((a, b) => a + b, 0),
            review: reviewData[i].reduce((a, b) => a + b, 0),
        }));
        renderStackedBar('cs-source-chart',
            sources.map(s => s.charAt(0).toUpperCase() + s.slice(1)),
            [
                { label: '分析', data: sourceTotals.map(s => s.analyze), backgroundColor: '#8b5cf6' },
                { label: '审核', data: sourceTotals.map(s => s.review), backgroundColor: '#6366f1' },
            ]);
    }

    // Provider 费用趋势
    if (data.provider_trend && data.provider_trend.length > 0) {
        const providers = [...new Set(data.provider_trend.map(p => p.provider))];
        const labels = [...new Set(data.provider_trend.map(p => p.label))];
        const colors = { deepseek: '#4F46E5', minimax: '#10b981', 'siliconflow': '#f59e0b' };
        const datasets = providers.map(p => ({
            label: p,
            data: labels.map(lbl => {
                const found = data.provider_trend.find(r => r.provider === p && r.label === lbl);
                return found ? found.cost : 0;
            }),
            backgroundColor: colors[p] || '#8b5cf6',
        }));
        renderStackedBar('cs-provider-chart', labels.map(l => l.slice(-5)), datasets);
    }
}
```

**修改 `renderTab` 函数:**

```javascript
async function renderTab(tab) {
    if (tab === 'sources') {
        const days = state.sources || 7;
        const data = await loadSourcesTab(days);
        if (!data) return;
        renderSources(data);
        return;
    } else if (tab === 'quality') {
        const data = await loadQualityTab(state.quality);
        if (data) renderQualityDetail(data);
        return;
    } else if (tab === 'consumption') {
        const data = await loadConsumptionTab(state.consumption);
        if (data) renderConsumptionDetail(data);
        return;
    }
    // ... runtime unchanged
}
```

- [ ] **Step 4.1**: 添加渲染函数

#### Step 5: 集成测试

- [ ] **Step 5.1**: API 测试

```bash
curl -s "http://localhost:8000/api/stats/consumption-detail?period=week" | jq '.data | keys'
```

#### Step 6: 提交

```bash
git add src/db/operations.py src/api/stats.py src/site/templates/dashboard.html src/site/static/js/app.js
git commit -m "feat(dashboard): Phase 2 - 资源消耗 Tab 重构

- 新增 GET /api/stats/consumption-detail 端点
- 新增来源费用趋势（分析+审核堆叠）
- 新增 Provider 费用趋势
- 日/周/月切换联动（只影响趋势图粒度）"
```

---

## Phase 3: 数据源健康 Tab（前端调整）

### 3.1 里程碑

- [ ] **M3.1**: 现有 API 保持兼容
- [ ] **M3.2**: 前端展示优化（样式调整）
- [ ] **M3.3**: 集成测试通过

### 3.2 详细步骤

#### Step 1: 优化前端样式（可选，取决于是否需要）

根据设计文档，数据源健康 Tab 保持现有架构，仅调整前端展示。检查现有实现是否满足设计要求：

- [ ] **Step 1.1**: 检查现有 HTML 结构

现有 HTML 结构已包含：
- 4 个 KPI 卡片
- Approved 率折线图
- 贡献分布柱状图
- 质量排行表格

如无需调整，跳过 Step 2。

#### Step 2: 如需样式调整

**文件:** `src/site/templates/dashboard.html` 和 `src/site/static/css/style.css`

- [ ] **Step 2.1**: 如需要，添加样式调整

#### Step 3: 提交

```bash
git add src/site/templates/dashboard.html  # 如果有改动
git commit -m "refactor(dashboard): Phase 3 - 数据源健康 Tab 样式优化"
```

---

## 附录: CSS 样式参考

### 渐变 KPI 卡片

```css
.kpi-card {
    padding: 14px;
    border-radius: 8px;
    text-align: center;
    color: white;
}

.kpi-card.gradient-1 {
    background: linear-gradient(135deg, #4F46E5, #6366f1);
}

.kpi-card.gradient-2 {
    background: linear-gradient(135deg, #10b981, #34d399);
}

.kpi-card.gradient-3 {
    background: linear-gradient(135deg, #f59e0b, #fbbf24);
}

.kpi-card.gradient-4 {
    background: linear-gradient(135deg, #8b5cf6, #a78bfa);
}

.kpi-value {
    font-size: 22px;
    font-weight: bold;
}

.kpi-label {
    font-size: 11px;
    opacity: 0.9;
}
```

### 图表布局

```css
.charts-layout {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}

.chart-card {
    background: #f9f9f9;
    padding: 16px;
    border-radius: 8px;
}

.chart-card h3 {
    font-size: 13px;
    font-weight: bold;
    color: #666;
    margin-bottom: 12px;
}

.chart-canvas-wrapper {
    height: 120px;
    position: relative;
}
```

### 词云样式

```css
.tag-cloud .tag-item {
    display: inline-block;
    padding: 4px 8px;
    border-radius: 4px;
    background: #e5e5e5;
    color: #333;
}

.tag-item.large {
    font-size: 16px;
    font-weight: bold;
    color: #4F46E5;
}

.tag-item.medium {
    font-size: 13px;
    color: #6366f1;
}

.tag-item.small {
    font-size: 11px;
    color: #6b7280;
}
```

### 进度条

```css
.progress-bar-wrapper {
    height: 8px;
    background: #e5e5e5;
    border-radius: 4px;
    overflow: hidden;
    margin-top: 4px;
}

.progress-bar {
    height: 100%;
    background: #4F46E5;
    border-radius: 4px;
    transition: width 0.3s ease;
}

.progress-bar.warning {
    background: #f59e0b;
}

.progress-bar.danger {
    background: #ef4444;
}
```

---

## 执行方式选择

**Plan complete and saved to `docs/superpowers/plans/2026-05-24-dashboard-redesign.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**