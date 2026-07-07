(function() {
    const rssLabels = window.__RSS_LABELS__ || {};

    function text(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    }

    function percent(value) {
        return value == null ? '-' : `${(value * 100).toFixed(0)}%`;
    }

    function money(value) {
        return `$${Number(value || 0).toFixed(2)}`;
    }

    function sourceLabel(source) {
        if (!source) return '未知来源';
        if (rssLabels[source]) return rssLabels[source];
        if (/^https?:\/\//.test(source)) {
            return source.replace(/^https?:\/\//, '').split('/')[0];
        }
        return source;
    }

    function sourceDisplayName(source) {
        return sourceLabel(source.name || source.label || source.source_detail || source.source || source.id);
    }

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function sourceHealthLabel(status) {
        return {
            healthy: '正常',
            dedup_only: '本轮全重复',
            success_zero: '本轮零命中',
            analysis_failed: '分析失败',
            failed: '请求失败',
            not_scheduled: '尚未运行',
            disabled: '已禁用',
        }[status] || '未知';
    }

    function governanceLabel(status) {
        return {
            candidate: '候选',
            trial: '试运行',
            active: '运行中',
            degraded: '降权',
            quarantined: '隔离',
            disabled: '已禁用',
            rejected: '已拒绝',
        }[status] || '-';
    }

    function sourceErrorText(source) {
        if (source.budget_blocked) return '预算阻断';
        return source.last_error || '-';
    }

    function sourceDiscoveryText(source) {
        if (source.discovered_by !== 'github_search' || !source.discovery_query) return '';
        const repo = source.discovery_repo ? ` / ${source.discovery_repo}` : '';
        return `GitHub Search: ${source.discovery_query}${repo}`;
    }

    function isFoldedSource(source) {
        return ['candidate', 'disabled', 'rejected', 'quarantined'].includes(source.governance_status);
    }

    function sourceRowHtml(s) {
        const discoveryText = sourceDiscoveryText(s);
        return `
            <tr>
                <td>
                    ${escapeHtml(sourceDisplayName(s))}
                    ${discoveryText ? `<div class="source-discovery-meta">${escapeHtml(discoveryText)}</div>` : ''}
                </td>
                <td><span class="source-health-status ${escapeHtml(s.health_status)}">${sourceHealthLabel(s.health_status)}</span></td>
                <td><span class="source-governance-status ${escapeHtml(s.governance_status || '')}">${governanceLabel(s.governance_status)}</span></td>
                <td>${s.health_score == null ? '-' : Number(s.health_score).toFixed(1)}</td>
                <td>${s.total_collected || 0}</td>
                <td>${s.last_new_items || 0}</td>
                <td>${s.last_dedup_skipped || 0}</td>
                <td>${s.last_analysis_failed || 0}</td>
                <td>${((s.approved_rate || 0) * 100).toFixed(1)}%</td>
                <td>${s.avg_score == null ? '-' : Number(s.avg_score).toFixed(1)}</td>
                <td>${escapeHtml(sourceLastRun(s.last_run_at))}</td>
                <td class="source-health-error" title="${escapeHtml(sourceErrorText(s))}">${escapeHtml(sourceErrorText(s))}</td>
            </tr>
        `;
    }

    function sourceLastRun(value) {
        if (!value) return '-';
        return String(value).replace('T', ' ').slice(0, 16);
    }

    function dimScore(dim) {
        if (!dim || !dim.max_score) return 0;
        return Math.round((dim.avg_score || 0) / dim.max_score * 100);
    }

    function showError(message) {
        const box = document.getElementById('dashboard-error');
        if (!box) return;
        box.hidden = !message;
        box.textContent = message || '';
    }

    function renderSummary(data, label) {
        text('dash-total-articles', (data.total_articles || 0).toLocaleString());
        text('dash-period-articles', data.period_articles || 0);
        text('dash-period-label', label);
        text('dash-pass-rate', percent(data.pass_rate));
        text('dash-period-cost', money(data.period_cost));
        text('dash-active-sources', data.active_sources || 0);
    }

    function renderQuality(data, label) {
        const summary = data.summary || {};
        text('q-period-articles', summary.period_articles || 0);
        text('q-period-label', label);
        text('q-avg-score', summary.avg_score != null ? Number(summary.avg_score).toFixed(0) : '-');
        text('q-summary-coverage', percent(data.content_quality?.summary_coverage));
        text('q-tagged-rate', percent(data.tag_coverage?.tagged_rate));

        DashboardCharts.bar(
            'q-content-chart',
            ['Summary覆盖', '标签覆盖', '一次通过'],
            [
                (data.content_quality?.summary_coverage || 0) * 100,
                (data.tag_coverage?.tagged_rate || 0) * 100,
                (data.audit_efficiency?.one_pass_rate || 0) * 100,
            ],
            '#4F46E5'
        );

        const sources = (data.source_quality || []).slice(0, 10);
        DashboardCharts.horizontalBar(
            'q-source-chart',
            sources.length ? sources.map(s => sourceLabel(s.source_detail || s.source)) : ['暂无数据'],
            sources.length ? sources.map(s => s.avg_score || 0) : [0],
            sources.length ? '#10b981' : '#d1d5db'
        );

        const dims = data.dimensions || {};
        const qualityDims = [dims.ai_relevance, dims.engineering_relevance, dims.content_depth, dims.info_density];
        DashboardCharts.radar(
            'q-radar-chart',
            ['AI相关度', '工程相关度', '内容深度', '信息密度'],
            [
                dimScore(dims.ai_relevance),
                dimScore(dims.engineering_relevance),
                dimScore(dims.content_depth),
                dimScore(dims.info_density),
            ]
        );

        DashboardCharts.stackedBar(
            'q-dimension-chart',
            ['AI相关度', '工程相关度', '内容深度', '信息密度'],
            [
                {
                    label: '高',
                    data: qualityDims.map(d => (d?.high_rate || 0) * 100),
                    backgroundColor: '#10b981',
                },
                {
                    label: '中',
                    data: qualityDims.map(d => (d?.mid_rate || 0) * 100),
                    backgroundColor: '#f59e0b',
                },
                {
                    label: '低',
                    data: qualityDims.map(d => (d?.low_rate || 0) * 100),
                    backgroundColor: '#ef4444',
                },
            ],
            'y'
        );
    }

    function renderConsumption(data) {
        text('cs-period-cost', money(data.period_cost));
        text('cs-daily-avg', money(data.daily_avg));
        text('cs-token-eff', `$${data.cost_per_million_tokens || 0}`);
        const progress = (data.budget_progress || 0) * 100;
        text('cs-budget-progress', `${progress.toFixed(0)}%`);
        const bar = document.getElementById('cs-progress-bar');
        if (bar) {
            bar.style.width = `${Math.min(progress, 100)}%`;
            bar.className = `progress-bar${progress > 80 ? ' danger' : progress > 50 ? ' warning' : ''}`;
        }

        DashboardCharts.line('cs-trend-chart', (data.trend || []).map(t => t.label), (data.trend || []).map(t => t.cost), '#ef4444');

        const sources = [...new Set((data.source_trend || []).map(s => s.source))];
        DashboardCharts.stackedBar(
            'cs-source-chart',
            sources.map(sourceLabel),
            [
                {
                    label: '分析',
                    data: sources.map(source => (data.source_trend || []).filter(s => s.source === source && s.type === 'analyze').reduce((sum, s) => sum + (s.cost || 0), 0)),
                    backgroundColor: '#8b5cf6',
                },
                {
                    label: '审核',
                    data: sources.map(source => (data.source_trend || []).filter(s => s.source === source && s.type === 'review').reduce((sum, s) => sum + (s.cost || 0), 0)),
                    backgroundColor: '#6366f1',
                },
            ]
        );

        const providers = [...new Set((data.provider_trend || []).map(p => p.provider))];
        const labels = [...new Set((data.provider_trend || []).map(p => p.label))];
        DashboardCharts.groupedBar(
            'cs-provider-chart',
            labels.map(label => label.slice(-5)),
            providers.map(provider => ({
                label: provider,
                data: labels.map(label => {
                    const row = (data.provider_trend || []).find(item => item.provider === provider && item.label === label);
                    return row ? row.cost : 0;
                }),
                backgroundColor: provider === 'deepseek' ? '#4F46E5' : provider === 'minimax' ? '#10b981' : '#f59e0b',
            }))
        );
    }

    function renderSources(data) {
        const sources = data.sources || [];
        const chartSources = sources.filter(s => (s.total_collected || 0) > 0 && !['disabled', 'rejected', 'quarantined'].includes(s.governance_status));
        const activeStatuses = new Set(['healthy', 'dedup_only', 'success_zero', 'analysis_failed']);
        const activeSources = sources.filter(s => activeStatuses.has(s.health_status));
        const ratedSources = sources.filter(s => (s.total_collected || 0) > 0);
        const scoredSources = sources.filter(s => s.avg_score != null);
        const totalCollected = sources.reduce((sum, s) => sum + (s.total_collected || 0), 0);
        const avgRate = ratedSources.length
            ? ratedSources.reduce((sum, s) => sum + (s.approved_rate || 0), 0) / ratedSources.length
            : null;
        const avgScore = scoredSources.length
            ? scoredSources.reduce((sum, s) => sum + Number(s.avg_score), 0) / scoredSources.length
            : null;

        text('src-active-count', activeSources.length);
        text('src-avg-rate', percent(avgRate));
        text('src-total-collected', totalCollected);
        text('src-avg-score', avgScore == null ? '-' : avgScore.toFixed(1));

        DashboardCharts.line('src-approved-rate-chart', chartSources.map(sourceDisplayName), chartSources.map(s => (s.approved_rate || 0) * 100), '#22c55e');
        DashboardCharts.bar('src-contribution-chart', chartSources.map(sourceDisplayName), chartSources.map(s => s.total_collected || 0), '#3b82f6');

        const table = document.getElementById('src-quality-table');
        if (!table) return;
        const rows = [...sources].sort((a, b) => {
            if (a.enabled !== b.enabled) return a.enabled ? -1 : 1;
            return (b.last_run_at || '').localeCompare(a.last_run_at || '');
        });
        const visibleRows = rows.filter(s => !isFoldedSource(s));
        const foldedRows = rows.filter(isFoldedSource);
        const sourceTableHead = `
            <thead>
                <tr>
                    <th>数据源</th><th>状态</th><th>治理状态</th><th>健康分</th><th>窗口采集</th><th>本轮新增</th>
                    <th>本轮去重</th><th>分析失败</th><th>通过率</th><th>平均分</th>
                    <th>最近运行</th><th>错误</th>
                </tr>
            </thead>
        `;
        table.innerHTML = `
            <table class="log-table">
                ${sourceTableHead}
                <tbody>
                    ${visibleRows.map(sourceRowHtml).join('')}
                </tbody>
            </table>
            ${foldedRows.length ? `
                <details class="source-folded-group">
                    <summary>候选 / 已停用（${foldedRows.length}）</summary>
                    <table class="log-table">
                        ${sourceTableHead}
                        <tbody>${foldedRows.map(sourceRowHtml).join('')}</tbody>
                    </table>
                </details>
            ` : ''}
        `;
    }

    window.DashboardRenderers = {
        showError,
        renderSummary,
        renderQuality,
        renderConsumption,
        renderSources,
    };
})();
