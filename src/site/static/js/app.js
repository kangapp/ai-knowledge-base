(function() {
    const INIT = window.__INIT__ || { articles: [], stats: {} };
    const state = { source: '', tag: '', days: 30, query: '' };

    // RSS 源中文简称映射（全局）
    const RSS_LABELS = {
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

    function getSourceLabel(source, sourceDetail) {
        if (source === 'rss' && sourceDetail) {
            return RSS_LABELS[sourceDetail] || sourceDetail.replace(/^https?:\/\//, '').split('/')[0];
        }
        if (source === 'github') return 'GitHub';
        if (source === 'feishu') return '飞书';
        if (source === 'arxiv') return 'arXiv';
        return source;
    }

    function getOptionLabel(s) {
        if (RSS_LABELS[s]) return RSS_LABELS[s];
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
            return `
            <div class="article-card" data-score="${a.relevance_score}" data-source="${a.source}" data-source-detail="${a.source_detail || ''}">
                <div class="card-top"><span class="topic-tag">${escapeHtml(label)}</span></div>
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