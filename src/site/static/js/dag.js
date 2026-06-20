(function() {
    let selectedRunId = '';

    const STATUS_LABELS = {
        running: '运行中',
        completed: '已完成',
        failed: '失败',
        queued: '等待构建',
        superseded: '已合并',
        skipped: '已跳过',
        untracked: '未记录',
        waiting: '等待',
        idle: '空闲',
    };

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function formatTime(value) {
        if (!value) return '-';
        return String(value).slice(5, 19).replace('T', ' ');
    }

    function formatDuration(value) {
        if (value == null) return '-';
        if (value < 1000) return `${value}ms`;
        return `${(value / 1000).toFixed(value < 10000 ? 1 : 0)}s`;
    }

    function statusLabel(status) {
        return STATUS_LABELS[status] || status || '未知';
    }

    function statusClass(status) {
        return `is-${status || 'waiting'}`;
    }

    async function fetchDag() {
        const query = selectedRunId ? `&run_id=${encodeURIComponent(selectedRunId)}` : '';
        try {
            const response = await fetch(`/api/pipeline/dag?detail=full${query}`);
            const payload = await response.json();
            if (!response.ok || payload.code !== 0) {
                throw new Error(payload.message || '运行状态加载失败');
            }
            renderDag(payload.data);
        } catch (error) {
            document.getElementById('pipeline-status').textContent = '加载失败';
            document.getElementById('publication-status').textContent = error.message || '加载失败';
        }
    }

    function renderDag(data) {
        renderRunSelector(data.recent_runs || [], data.run_id || '');
        renderSummary(data.summary || {});
        renderProcessing(data.processing_stages || []);
        renderReviewRounds(data.review_rounds || []);
        renderPostprocess(data.postprocess || {});
        renderSourceFunnels(data.source_funnels || []);
        renderActiveItems(data.active_items || []);
        renderEvents(data.events || []);
    }

    function renderRunSelector(runs, currentRunId) {
        const select = document.getElementById('dag-run-select');
        const value = selectedRunId || currentRunId;
        select.innerHTML = runs.map(run => `
            <option value="${escapeHtml(run.id)}">
                ${escapeHtml(formatTime(run.started_at))} · ${escapeHtml(statusLabel(run.status))} · ${escapeHtml(run.trigger || '-')}
            </option>
        `).join('');
        select.value = value;
        if (!select.value && runs.length) select.value = runs[0].id;
    }

    function renderSummary(summary) {
        const pipelineCard = document.getElementById('pipeline-status-card');
        const publicationCard = document.getElementById('publication-status-card');
        pipelineCard.className = `dag-status-card ${statusClass(summary.pipeline_status)}`;
        publicationCard.className = `dag-status-card ${statusClass(summary.publication_status)}`;
        document.getElementById('pipeline-status').textContent = statusLabel(summary.pipeline_status);
        document.getElementById('publication-status').textContent = statusLabel(summary.publication_status);
        document.getElementById('pipeline-trigger').textContent = `触发方式：${summary.trigger || '-'}`;
        document.getElementById('publication-detail').textContent =
            summary.publication_status === 'superseded' ? '已由后续流水线统一构建' : '静态站发布状态';
        document.getElementById('dag-run-time').textContent =
            `${formatTime(summary.started_at)} → ${formatTime(summary.ended_at)}`;

        const metrics = [
            ['采集', summary.collected],
            ['新增', summary.new_items],
            ['分析', summary.analyzed],
            ['入库', summary.inserted],
            ['丢弃', summary.discarded],
            ['失败', summary.failed],
            ['花费', `$${Number(summary.cost || 0).toFixed(4)}`],
            ['Tokens', Number(summary.tokens || 0).toLocaleString()],
        ];
        document.getElementById('dag-summary-metrics').innerHTML = metrics.map(([label, value]) => `
            <div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value == null ? 0 : value)}</strong></div>
        `).join('');
    }

    function renderProcessing(stages) {
        const container = document.getElementById('processing-stages');
        if (!stages.length) {
            container.innerHTML = '<p class="empty-text">暂无核心处理记录</p>';
            return;
        }
        container.innerHTML = stages.map((stage, index) => {
            const sourceRows = (stage.sources || []).map(source => `
                <li>
                    <span>${escapeHtml(source.label || source.source_id)}</span>
                    <b>${source.analyzed || 0}</b>
                    ${source.failed ? `<em>失败 ${source.failed}</em>` : ''}
                </li>
            `).join('');
            return `
                <article class="dag-stage-card ${statusClass(stage.status)}">
                    <div class="dag-stage-head">
                        <span>${String(index + 1).padStart(2, '0')}</span>
                        <b>${escapeHtml(statusLabel(stage.status))}</b>
                    </div>
                    <h3>${escapeHtml(stage.label)}</h3>
                    <p>${escapeHtml(stage.details || '暂无详情')}</p>
                    ${sourceRows ? `<ul class="dag-analyzer-sources">${sourceRows}</ul>` : ''}
                    <small>${escapeHtml(formatDuration(stage.duration_ms))}</small>
                </article>
            `;
        }).join('');
    }

    function renderReviewRounds(rounds) {
        const container = document.getElementById('review-rounds');
        if (!rounds.length) {
            container.innerHTML = '<p class="empty-text">本轮未进入审核</p>';
            return;
        }
        container.innerHTML = rounds.map(round => `
            <article class="dag-review-round ${statusClass(round.status)}">
                <div>
                    <strong>${escapeHtml(round.label)}</strong>
                    <span>${escapeHtml(formatDuration(round.duration_ms))}</span>
                </div>
                <p>通过 ${round.approved || 0} · 重试 ${round.retry || 0} · 丢弃 ${round.discarded || 0}</p>
            </article>
        `).join('');
    }

    function renderPostprocess(postprocess) {
        const stages = ['deep_report', 'backup', 'build']
            .map(key => postprocess[key])
            .filter(Boolean);
        document.getElementById('postprocess-stages').innerHTML = stages.map(stage => `
            <article class="dag-postprocess-card ${statusClass(stage.status)}">
                <div>
                    <span class="dag-status-dot"></span>
                    <strong>${escapeHtml(stage.label)}</strong>
                </div>
                <b>${escapeHtml(statusLabel(stage.status))}</b>
                <p>${escapeHtml(stage.details || '暂无详情')}</p>
                <small>${escapeHtml(formatDuration(stage.duration_ms))}</small>
            </article>
        `).join('');
    }

    function renderSourceFunnels(rows) {
        const container = document.getElementById('source-funnels');
        if (!rows.length) {
            container.innerHTML = '<p class="empty-text">暂无数据源记录</p>';
            return;
        }
        container.innerHTML = rows.map(row => `
            <article class="source-funnel">
                <div class="source-funnel-head">
                    <strong>${escapeHtml(row.source_detail || row.source_id)}</strong>
                    <span>${escapeHtml(row.source_id)}</span>
                </div>
                <div class="funnel-metrics">
                    <span>采集 ${row.collected || 0}</span>
                    <span>新增 ${row.new_items || 0}</span>
                    <span>去重 ${row.dedup_skipped || 0}</span>
                    <span>分析 ${row.analyzed || 0}</span>
                    <span>入库 ${row.inserted || 0}</span>
                    <span>失败 ${(row.analysis_failed || 0) + (row.failed || 0)}</span>
                </div>
            </article>
        `).join('');
    }

    function renderActiveItems(items) {
        const container = document.getElementById('active-items');
        if (!items.length) {
            container.innerHTML = '<p class="empty-text">当前没有活跃任务</p>';
            return;
        }
        container.innerHTML = items.map(item => `
            <article class="active-item">
                <strong>${escapeHtml(item.title || item.ref_url)}</strong>
                <span>${escapeHtml(item.agent || item.phase)} · ${escapeHtml(item.source_id)}</span>
                <small>${escapeHtml(item.ref_url)}</small>
            </article>
        `).join('');
    }

    function renderEvents(events) {
        const container = document.getElementById('dag-events');
        if (!events.length) {
            container.innerHTML = '<p class="empty-text">暂无事件</p>';
            return;
        }
        container.innerHTML = events.slice(-200).reverse().map(event => `
            <div class="log-entry ${escapeHtml(event.level || 'info')}">
                <span class="log-time">${escapeHtml(formatTime(event.ts))}</span>
                <span class="log-msg">
                    <b>${escapeHtml(event.event)}</b>
                    ${escapeHtml(event.message || '')}
                    ${event.source_id ? `<em>${escapeHtml(event.source_id)}</em>` : ''}
                </span>
            </div>
        `).join('');
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.getElementById('dag-run-select').addEventListener('change', event => {
            selectedRunId = event.target.value;
            fetchDag();
        });
        fetchDag();
        setInterval(fetchDag, 5000);
    });
})();
