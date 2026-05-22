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
    let cachedData = { quality: null, runtime: null, consumption: null };
    const state = { quality: 30, runtime: 7, consumption: 30 };

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

    function setupDateFilters() {
        document.querySelectorAll('.date-filters').forEach(container => {
            const tab = container.id.replace('-date-filters', '');
            const defaultDays = tab === 'runtime' ? 7 : 30;
            container.querySelectorAll('.date-btn').forEach(btn => {
                const d = parseInt(btn.dataset.days) || defaultDays;
                if (d === defaultDays) btn.classList.add('active');
                btn.addEventListener('click', () => {
                    container.querySelectorAll('.date-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    state[tab] = d;
                    invalidateCache(tab);
                    renderTab(tab);
                });
            });
        });
    }

    function switchTab(tab) {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.querySelector(`.tab[data-tab="${tab}"]`).classList.add('active');
        document.getElementById(`tab-${tab}`).classList.add('active');
        renderTab(tab);
    }

    async function renderTab(tab) {
        const data = await loadTab(tab);
        if (!data) return;
        if (tab === 'quality') renderQuality(data);
        else if (tab === 'runtime') renderRuntime(data);
        else if (tab === 'consumption') renderConsumption(data);
    }

    function renderQuality(data) {
        const buckets = ['0-20','20-40','40-60','60-80','80-100'];
        const counts = buckets.map(b => {
            const found = data.score_distribution ? data.score_distribution.find(s => s.bucket === b) : null;
            return found ? found.count : 0;
        });
        renderBarChart('score-dist-chart', buckets, counts, '#3b82f6');

        const list = document.getElementById('source-score-list');
        if (list) {
            list.innerHTML = (data.source_scores || []).map(s => `
                <div class="source-score-item">
                    <div>
                        <div class="source-name">${s.source_detail || s.source}</div>
                        <div class="count">${s.article_count} 篇</div>
                    </div>
                    <div class="score">${s.avg_score}分</div>
                </div>
            `).join('');
        }

        const cloud = document.getElementById('tag-cloud');
        if (cloud && data.top_tags && data.top_tags.length > 0) {
            const maxCount = Math.max(...data.top_tags.map(t => t.count));
            cloud.innerHTML = data.top_tags.map(t => {
                const ratio = t.count / maxCount;
                const size = ratio > 0.7 ? 'large' : ratio > 0.4 ? 'medium' : 'small';
                return `<span class="tag-item ${size}">${t.name}</span>`;
            }).join('');
        }
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

    function renderConsumption(data) {
        document.getElementById('cs-period-cost').textContent = '$' + (data.period_cost || 0).toFixed(4);
        const tokens = data.period_tokens || 1;
        const cost = data.period_cost || 0;
        const efficiency = (cost / tokens * 1e6).toFixed(2);
        document.getElementById('cs-token-efficiency').textContent = '$' + efficiency;

        const budget = 10.0;
        const progress = Math.min((cost / budget) * 100, 100);
        const bar = document.getElementById('cs-progress-bar');
        if (bar) {
            bar.style.width = progress + '%';
            bar.className = 'progress-bar' + (progress > 80 ? ' danger' : progress > 50 ? ' warning' : '');
        }
        document.getElementById('cs-budget-progress').textContent = progress.toFixed(0) + '%';

        if (data.provider_daily) {
            const dates = [...new Set(data.provider_daily.map(d => d.date))].sort();
            const providers = [...new Set(data.provider_daily.map(d => d.provider))];
            const colors = { minimax: '#f97316', deepseek: '#22c55e', openai: '#3b82f6' };
            const datasets = providers.map(p => {
                const pData = data.provider_daily.filter(d => d.provider === p);
                return {
                    label: p,
                    data: dates.map(dt => {
                        const found = pData.find(d => d.date === dt);
                        return found ? found.cost : 0;
                    }),
                    backgroundColor: colors[p] || '#8b5cf6'
                };
            });
            renderStackedBar('provider-cost-chart', dates.map(d => d.slice(5)), datasets);
        }

        if (data.agent_daily) {
            const dates = [...new Set(data.agent_daily.map(d => d.date))].sort();
            const agents = [...new Set(data.agent_daily.map(d => d.agent))];
            const colors = ['#3b82f6', '#22c55e', '#f97316', '#ef4444', '#8b5cf6'];
            const datasets = agents.map((a, i) => {
                const aData = data.agent_daily.filter(d => d.agent === a);
                return {
                    label: a,
                    data: dates.map(dt => {
                        const found = aData.find(d => d.date === dt);
                        return found ? found.cost : 0;
                    }),
                    backgroundColor: colors[i % colors.length]
                };
            });
            renderGroupedBar('agent-cost-chart', dates.map(d => d.slice(5)), datasets);
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

    document.addEventListener('DOMContentLoaded', async () => {
        // 加载全局 KPI
        const res = await fetch('/api/stats/enhanced');
        const json = await res.json();
        if (json.code === 0) {
            const s = json.data.summary || {};
            document.getElementById('kpi-total').textContent = (s.total_articles || 0).toLocaleString();
            document.getElementById('kpi-period').textContent = '↑ ' + (s.period_articles || 0);
            document.getElementById('kpi-period-count').textContent = s.period_articles || 0;
            // 通过率
            const total = s.total_articles || 0;
            const rate = total > 0 ? ((s.period_articles || 0) / total * 100).toFixed(0) + '%' : '-';
            document.getElementById('kpi-approve-rate').textContent = rate;
            document.getElementById('kpi-avg-score').textContent = s.avg_score ? s.avg_score.toFixed(0) : '-';
            document.getElementById('kpi-active-sources').textContent = s.active_sources || 0;
            // 活跃源显示细分（使用RSS_LABELS映射中文）
            const details = json.data.active_source_details || [];
            const rssSubs = details.filter(d => d.source === 'rss').map(d => RSS_LABELS_LOCAL[d.source_detail] || d.source_detail).filter(Boolean).slice(0, 5);
            const subLabel = rssSubs.length > 0 ? 'RSS: ' + rssSubs.join(', ') : (details.length > 0 ? details.map(d => RSS_LABELS_LOCAL[d.source_detail] || d.source_detail || d.source).filter(Boolean).slice(0, 3).join(', ') : '无');
            document.getElementById('kpi-active-sources-sub').textContent = subLabel;
        }

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