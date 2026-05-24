(function() {
    // RSS 源中文简称映射（挂载到 window供两个IIFE共用）
    window.__RSS_LABELS__ = {
        'https://36kr.com/feed': '36氪',
        'https://www.ithome.com/rss/': 'IT之家',
        'https://techcrunch.com/feed/': 'TechCrunch',
        'https://www.theverge.com/rss/index.xml': 'The Verge',
        'https://feeds.arstechnica.com/arstechnica/index': 'Ars Technica',
        'https://feeds.reuters.com/reuters/scienceNews': 'Reuters',
        'https://www.huxiu.com/rss/feed': '虎嗅',
        'https://api.juejin.cn/rss': '掘金',
        'https://openai.com/blog/rss.xml': 'OpenAI',
        'https://feeds.feedburner.com/producthunt': 'Product Hunt',
        '36氪': '36氪',
        'TechCrunch AI': 'TechCrunch',
        'The Verge AI': 'The Verge',
        'IT之家': 'IT之家',
        'Ars Technica': 'Ars Technica',
        'Ars Technica AI': 'Ars Technica',
        'OpenAI': 'OpenAI',
        '虎嗅': '虎嗅',
        '掘金': '掘金',
        'Reuters': 'Reuters',
        'github': 'GitHub',
        'feishu': '飞书',
        'arxiv': 'arXiv',
    };

    const INIT = window.__INIT__ || { articles: [], stats: {} };
    const state = { source: '', tag: '', days: 30, query: '' };

    function getSourceLabel(source, sourceDetail) {
        if (source === 'rss' && sourceDetail) {
            return window.__RSS_LABELS__[sourceDetail] || sourceDetail.replace(/^https?:\/\//, '').split('/')[0];
        }
        if (source === 'github') return 'GitHub';
        if (source === 'feishu') return '飞书';
        if (source === 'arxiv') return 'arXiv';
        return source;
    }

    function getOptionLabel(s) {
        if (window.__RSS_LABELS__[s]) return window.__RSS_LABELS__[s];
        if (s.startsWith('http')) return s.replace(/^https?:\/\//, '').split('/')[0];
        return s;
    }

    function render(articles) {
        const list = document.getElementById('article-list');
        if (!list) return;
        if (articles.length === 0) {
            list.innerHTML = '<p class="loading">暂无文章</p>';
            return;
        }
        list.innerHTML = articles.map(a => {
            const label = getSourceLabel(a.source, a.source_detail);
            const tagsHtml = (a.tags || []).slice(0, 3).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('');
            return `
            <div class="article-card" data-score="${a.relevance_score}" data-source="${a.source}" data-source-detail="${a.source_detail || ''}">
                <div class="card-header">
                    <span class="topic-tag">${escapeHtml(label)}</span>
                    ${tagsHtml ? `<div class="tags">${tagsHtml}</div>` : ''}
                </div>
                <h3><a href="/article.html?id=${a.id}">${escapeHtml(a.title)}</a></h3>
                <p>${escapeHtml(a.description || '')}</p>
                <div class="meta">
                    <span>${a.source_detail || a.source}</span>
                    <span>${a.collected_at ? a.collected_at.slice(0, 10) : ''}</span>
                    <span class="score">${a.relevance_score}分</span>
                </div>
            </div>
        `}).join('');
    }

    function filterArticles() {
        let articles = INIT.articles;
        if (state.days > 0) {
            const cutoff = new Date();
            cutoff.setDate(cutoff.getDate() - state.days);
            articles = articles.filter(a => new Date(a.collected_at) >= cutoff);
        }
        if (state.source) {
            // state.source 可能是 'github'、'rss'、或具体 RSS 子源名（如 '36氪'）
            articles = articles.filter(a => {
                if (state.source === 'github' || state.source === 'feishu' || state.source === 'arxiv') {
                    return a.source === state.source;
                }
                // RSS 子源匹配：source_detail 匹配，或 source=rss 且无 detail
                if (a.source === 'rss') {
                    return a.source_detail === state.source || (!a.source_detail && state.source === 'rss');
                }
                return false;
            });
        }
        if (state.tag) {
            articles = articles.filter(a => (a.tags || []).includes(state.tag));
        }
        if (state.query) {
            const q = state.query.toLowerCase();
            articles = articles.filter(a =>
                a.title.toLowerCase().includes(q) ||
                (a.description || '').toLowerCase().includes(q)
            );
        }
        render(articles);
    }

    function escapeHtml(str) {
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function setupFilters() {
        const searchBox = document.getElementById('search-box');
        if (searchBox) {
            searchBox.addEventListener('input', debounce(e => {
                state.query = e.target.value;
                filterArticles();
            }, 200));
        }

        const sourceFilter = document.getElementById('source-filter');
        if (sourceFilter) {
            // 按 label 分组去重，value 使用最后一个匹配的 raw
            const sourceMap = {};
            INIT.articles.forEach(a => {
                const raw = a.source === 'rss' && a.source_detail ? a.source_detail : a.source;
                const normalized = getOptionLabel(raw);
                if (!sourceMap[normalized]) {
                    sourceMap[normalized] = { label: normalized, value: raw };
                }
            });
            const sourceOptions = Object.values(sourceMap);
            sourceFilter.innerHTML = '<option value="">全部来源</option>';
            sourceOptions.forEach(opt => {
                const el = document.createElement('option');
                el.value = opt.value; el.textContent = opt.label;
                sourceFilter.appendChild(el);
            });
            sourceFilter.addEventListener('change', e => {
                state.source = e.target.value;
                filterArticles();
            });
        }

        const tagFilter = document.getElementById('tag-filter');
        if (tagFilter) {
            const allTags = [...new Set(INIT.articles.flatMap(a => a.tags || []))].sort();
            allTags.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t; opt.textContent = t;
                tagFilter.appendChild(opt);
            });
            tagFilter.addEventListener('change', e => {
                state.tag = e.target.value;
                filterArticles();
            });
        }

        document.querySelectorAll('.date-filters button').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.date-filters button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.days = parseInt(btn.dataset.days) || 0;
                filterArticles();
            });
        });

        // default: show active button
        const activeBtn = document.querySelector('.date-filters button.active') ||
                          document.querySelector('.date-filters button[data-days="30"]');
        if (activeBtn) activeBtn.classList.add('active');
    }

    function debounce(fn, ms) {
        let timer;
        return function(...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), ms);
        };
    }

    function initDashboard() {
        const stats = INIT.stats;
        const statsEl = document.getElementById('stats-overview');
        if (statsEl && stats) {
            statsEl.innerHTML = `
                <div class="stat-card"><div class="value">${stats.total_articles || 0}</div><div class="label">总文章数</div></div>
                <div class="stat-card"><div class="value">${stats.period_articles || 0}</div><div class="label">本月新增</div></div>
                <div class="stat-card"><div class="value">$${(stats.period_cost || 0).toFixed(2)}</div><div class="label">本月花费</div></div>
            `;
        }
        const canvas = document.getElementById('cost-chart');
        if (canvas && stats.daily_cost && stats.daily_cost.length > 0) {
            new Chart(canvas, {
                type: 'line',
                data: {
                    labels: stats.daily_cost.map(d => d.date),
                    datasets: [{
                        label: '日花费',
                        data: stats.daily_cost.map(d => d.cost),
                        borderColor: '#1a1a2e',
                        backgroundColor: 'rgba(26,26,46,0.1)',
                        fill: true,
                        tension: 0.3,
                    }]
                },
                options: { responsive: true, plugins: { legend: { display: false } } }
            });
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('article-list')) setupFilters();
        if (document.getElementById('stats-overview')) initDashboard();
    });
})();

// Dashboard Tab Controller
(function() {
    // RSS 中文简称本地映射（避免跨 IIFE 作用域问题）
    const RSS_LABELS_LOCAL = {
        'https://36kr.com/feed': '36氪', 'https://www.ithome.com/rss/': 'IT之家',
        'https://techcrunch.com/feed/': 'TechCrunch', 'https://www.theverge.com/rss/index.xml': 'The Verge',
        'https://feeds.arstechnica.com/arstechnica/index': 'Ars Technica', 'https://feeds.reuters.com/reuters/scienceNews': 'Reuters',
        'https://www.huxiu.com/rss/feed': '虎嗅', 'https://api.juejin.cn/rss': '掘金',
        'https://openai.com/blog/rss.xml': 'OpenAI', 'https://feeds.feedburner.com/producthunt': 'Product Hunt',
        '36氪': '36氪', 'TechCrunch AI': 'TechCrunch', 'IT之家': 'IT之家',
        'Ars Technica': 'Ars Technica', 'OpenAI': 'OpenAI', '虎嗅': '虎嗅',
    };
    let cachedData = { quality: null, runtime: null, consumption: null, sources: null };
    const state = { quality: 7, runtime: 7, consumption: 30, sources: 7 };
    const globalDays = { value: 30 };

    async function loadGlobalKPIs(days) {
        const res = await fetch(`/api/stats/enhanced?days=${days}`);
        const json = await res.json();
        if (json.code !== 0) return;
        const s = json.data.summary || {};
        document.getElementById('kpi-total').textContent = (s.total_articles || 0).toLocaleString();
        document.getElementById('kpi-period').textContent = '↑ ' + (s.period_articles || 0);
        document.getElementById('kpi-period-count').textContent = s.period_articles || 0;
        document.getElementById('kpi-period-count').parentElement.querySelector('.range-label').textContent = days;
        const rate = s.pass_rate != null ? (s.pass_rate * 100).toFixed(0) + '%' : '-';
        document.getElementById('kpi-approve-rate').textContent = rate;
        document.getElementById('kpi-avg-score').textContent = s.avg_score ? s.avg_score.toFixed(0) : '-';
        document.getElementById('kpi-active-sources').textContent = s.active_sources || 0;
        const details = json.data.active_source_details || [];
        const rssSubs = details.filter(d => d.source === 'rss').map(d => RSS_LABELS_LOCAL[d.source_detail] || d.source_detail).filter(Boolean).slice(0, 5);
        const subLabel = rssSubs.length > 0 ? 'RSS: ' + rssSubs.join(', ') : (details.length > 0 ? details.map(d => RSS_LABELS_LOCAL[d.source_detail] || d.source_detail || d.source).filter(Boolean).slice(0, 3).join(', ') : '无');
        document.getElementById('kpi-active-sources-sub').textContent = subLabel;
    }

    function setupDateFilters() {
        // 全局日期筛选器（KPI + 所有 Tab 共用）
        const globalContainer = document.getElementById('global-date-filters');
        if (globalContainer) {
            globalContainer.querySelectorAll('.date-btn').forEach(btn => {
                const d = parseInt(btn.dataset.days) || 30;
                if (d === globalDays.value) btn.classList.add('active');
                btn.addEventListener('click', () => {
                    globalContainer.querySelectorAll('.date-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    globalDays.value = d;
                    loadGlobalKPIs(d);
                    // 同步更新各 Tab 的筛选器
                    Object.keys(state).forEach(tab => { state[tab] = d; });
                    // 重新渲染当前 Tab
                    const activeTab = document.querySelector('.tab.active')?.dataset.tab || 'quality';
                    cachedData = {};
                    renderTab(activeTab);
                });
            });
        }
    }

    async function loadTab(tab) {
        const days = state[tab] || 30;
        const key = `${tab}_${days}`;
        if (cachedData[key]) return cachedData[key];
        const res = await fetch(`/api/stats/${tab}?days=${days}`);
        const json = await res.json();
        if (json.code !== 0) return null;
        cachedData[key] = json.data;
        return cachedData[key];
    }

    function invalidateCache(tab) {
        const days = state[tab] || 30;
        const key = `${tab}_${days}`;
        delete cachedData[key];
    }

    function switchTab(tab) {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.querySelector(`.tab[data-tab="${tab}"]`).classList.add('active');
        document.getElementById(`tab-${tab}`).classList.add('active');
        renderTab(tab);
    }

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
        const data = await loadTab(tab);
        if (!data) return;
        if (tab === 'runtime') renderRuntime(data);
    }

    async function loadQualityTab(days) {
        const key = `quality_${days}`;
        if (cachedData[key]) return cachedData[key];
        const res = await fetch(`/api/stats/quality-detail?period=${days === 7 ? 'week' : days === 30 ? 'month' : 'day'}`);
        const json = await res.json();
        if (json.code !== 0) return null;
        cachedData[key] = json.data;
        return cachedData[key];
    }

    function renderQualityDetail(data) {
        if (!data) return;

        // KPI 卡片
        document.getElementById('q-pass-rate').textContent = data.audit_efficiency ?
            (data.audit_efficiency.one_pass_rate * 100).toFixed(0) + '%' : '-';
        document.getElementById('q-avg-score').textContent = data.dimensions ?
            (data.dimensions.ai_relevance?.avg_score || 0).toFixed(0) : '-';
        document.getElementById('q-one-pass').textContent = data.audit_efficiency ?
            (data.audit_efficiency.one_pass_rate * 100).toFixed(0) + '%' : '-';
        document.getElementById('q-tag-rate').textContent = data.tag_coverage ?
            (data.tag_coverage.tagged_rate * 100).toFixed(0) + '%' : '-';

        // 内容质量分布柱状图
        if (data.content_quality) {
            const cq = data.content_quality;
            renderBarChart('q-content-chart',
                ['Summary覆盖', '有标签', '一次通过', 'Exhausted', 'Retry'],
                [(cq.summary_coverage || 0) * 100, (data.tag_coverage?.tagged_rate || 0) * 100,
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
                parseFloat((dims.ai_relevance?.avg_score || 0).toFixed(1)),
                parseFloat((dims.内容深度?.avg_score || 0).toFixed(1)),
                parseFloat((dims.信息密度?.avg_score || 0).toFixed(1)),
                parseFloat((dims.时效性?.avg_score || 0).toFixed(1)),
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
        document.getElementById('cs-token-eff').textContent = '$' + (data.cost_per_million_tokens || 0);
        const progress = (data.budget_progress || 0) * 100;
        document.getElementById('cs-budget-progress').textContent = progress.toFixed(0) + '%';
        const bar = document.getElementById('cs-progress-bar');
        if (bar) {
            bar.style.width = Math.min(progress, 100) + '%';
            bar.className = 'progress-bar' + (progress > 80 ? ' danger' : progress > 50 ? ' warning' : '');
        }

        // 花费趋势折线图
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
            renderGroupedBar('cs-provider-chart', labels.map(l => l.slice(-5)), datasets);
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

    async function loadSourcesTab(days) {
        const key = `sources_${days}`;
        if (cachedData[key]) return cachedData[key];
        const res = await fetch(`/api/sources/stats?period=${days === 7 ? 'week' : 'month'}`);
        const json = await res.json();
        if (json.code !== 0) return null;
        cachedData[key] = json.data;
        return cachedData[key];
    }

    function renderRuntime(data) {
        if (!data.run) return;
        const run = data.run;
        document.getElementById('rt-run-id').textContent = run.id.slice(-8);
        document.getElementById('rt-run-time').textContent = run.started_at ? run.started_at.slice(0, 16) : '-';

        if (run.started_at && run.ended_at) {
            const start = new Date(run.started_at);
            const end = new Date(run.ended_at);
            const dur = ((end - start) / 1000).toFixed(1);
            document.getElementById('rt-duration').textContent = dur + 's';
        }

        let summary = {};
        try { summary = JSON.parse(run.summary || '{}'); } catch(e) {}
        const total = (summary.approved || 0) + (summary.discarded || 0);
        const rate = total > 0 ? ((summary.approved || 0) / total * 100).toFixed(0) + '%' : '-';
        document.getElementById('rt-success-rate').textContent = rate;
        document.getElementById('rt-fail-count').textContent = (summary.retry || 0) + (summary.discarded || 0);

        const flow = document.getElementById('pipeline-flow');
        if (flow && data.phases) {
            const phases = ['collect', 'route', 'analyze', 'aggregate', 'review'];
            const phaseMap = {};
            data.phases.forEach(p => { phaseMap[p.phase] = p; });
            flow.innerHTML = phases.map((p, i) => {
                const info = phaseMap[p] || {};
                const status = info.status || 'pending';
                const duration = info.duration_ms ? (info.duration_ms / 1000).toFixed(1) + 's' : '-';
                return `
                    <div class="stage ${status}">
                        <div class="stage-box">
                            <div class="stage-name">${p}</div>
                            <div class="stage-duration">${duration}</div>
                        </div>
                    </div>
                    ${i < phases.length - 1 ? '<div class="arrow">→</div>' : ''}
                `;
            }).join('');
        }

        const tbody = document.getElementById('failure-tbody');
        if (tbody) {
            tbody.innerHTML = (data.failures || []).map(f => `
                <tr>
                    <td>${f.time}</td>
                    <td>${f.stage}</td>
                    <td>${f.provider}</td>
                    <td>${f.title || f.url || '-'}</td>
                </tr>
            `).join('') || '<tr><td colspan="4" style="text-align:center;color:#999">无失败记录</td></tr>';
        }
    }

    function renderBarChart(canvasId, labels, data, color) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
        if (ctx._chart) ctx._chart.destroy();
        ctx._chart = new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets: [{ data, backgroundColor: color }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
        });
    }

    function renderStackedBar(canvasId, labels, datasets) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
        if (ctx._chart) ctx._chart.destroy();
        ctx._chart = new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets },
            options: { responsive: true, maintainAspectRatio: false, scales: { x: { stacked: true }, y: { stacked: true } } }
        });
    }

    function renderGroupedBar(canvasId, labels, datasets) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
        if (ctx._chart) ctx._chart.destroy();
        ctx._chart = new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets },
            options: { responsive: true, maintainAspectRatio: false }
        });
    }

    function renderSources(data) {
        if (!data || !data.sources) return;

        const sources = data.sources || [];
        const activeCount = sources.length;
        const totalCollected = sources.reduce((sum, s) => sum + (s.total_collected || 0), 0);
        const avgRate = sources.length > 0
            ? (sources.reduce((sum, s) => sum + (s.approved_rate || 0), 0) / sources.length * 100).toFixed(0) + '%'
            : '-';
        const avgScore = sources.length > 0
            ? (sources.reduce((sum, s) => sum + (s.avg_score || 0), 0) / sources.length).toFixed(1)
            : '-';

        document.getElementById('src-active-count').textContent = activeCount;
        document.getElementById('src-avg-rate').textContent = avgRate;
        document.getElementById('src-total-collected').textContent = totalCollected;
        document.getElementById('src-avg-score').textContent = avgScore;

        // Approved 率折线图
        const labels = sources.map(s => s.id);
        const approvedRates = sources.map(s => ((s.approved_rate || 0) * 100).toFixed(1));
        renderLineChart('src-approved-rate-chart', labels, approvedRates, '#22c55e');

        // 贡献分布柱状图（total_collected）
        const collected = sources.map(s => s.total_collected || 0);
        renderBarChart('src-contribution-chart', labels, collected, '#3b82f6');

        // 质量排行表格
        const table = document.getElementById('src-quality-table');
        if (table) {
            const sorted = [...sources].sort((a, b) => (b.avg_score || 0) - (a.avg_score || 0));
            table.innerHTML = `
                <table class="log-table">
                    <thead><tr><th>数据源</th><th>采集量</th><th>通过率</th><th>平均分</th><th>趋势</th></tr></thead>
                    <tbody>
                        ${sorted.map(s => `
                            <tr>
                                <td>${s.id}</td>
                                <td>${s.total_collected || 0}</td>
                                <td>${((s.approved_rate || 0) * 100).toFixed(1)}%</td>
                                <td>${(s.avg_score || 0).toFixed(1)}</td>
                                <td>${getTrendIcon(s.trend)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }
    }

    function getTrendIcon(trend) {
        if (trend === 'rising') return '↑';
        if (trend === 'falling') return '↓';
        return '→';
    }

    function renderLineChart(canvasId, labels, data, color) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
        if (ctx._chart) ctx._chart.destroy();
        ctx._chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    data,
                    borderColor: color,
                    backgroundColor: color + '20',
                    fill: true,
                    tension: 0.3,
                }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
        });
    }

    document.addEventListener('DOMContentLoaded', async () => {
        // 加载全局 KPI（默认30天）
        await loadGlobalKPIs(30);

        // Tab 切换
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => switchTab(tab.dataset.tab));
        });

        // 日期筛选器
        setupDateFilters();

        // 渲染默认 Tab
        renderTab('quality');
    });
})();