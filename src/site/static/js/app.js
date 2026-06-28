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
    const FAVORITES_KEY = 'ai_kb_favorite_articles';
    const state = { source: '', tag: '', days: 30, query: '', favoritesOnly: false };
    let allArticles = INIT.articles;
    let favoriteIds = loadFavoriteIds();

    function getSourceLabel(source, sourceDetail) {
        if (source === 'hotlist' && sourceDetail) {
            return sourceDetail;
        }
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

    function listSummary(value) {
        const text = value || '';
        return text.length <= 120 ? text : `${text.slice(0, 120)}...`;
    }

    function render(articles) {
        const list = document.getElementById('article-list');
        if (!list) return;
        if (articles.length === 0) {
            list.innerHTML = `<p class="loading">${state.favoritesOnly ? '暂无收藏文章' : '暂无文章'}</p>`;
            return;
        }
        list.innerHTML = articles.map(a => {
            const label = getSourceLabel(a.source, a.source_detail);
            const tagsHtml = (a.tags || []).slice(0, 3).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('');
            const isFavorite = favoriteIds.has(String(a.id));
            return `
            <div class="article-card" data-score="${a.relevance_score}" data-source="${a.source}" data-source-detail="${a.source_detail || ''}">
                <div class="card-header">
                    <span class="topic-tag">${escapeHtml(label)}</span>
                    ${tagsHtml ? `<div class="tags">${tagsHtml}</div>` : ''}
                    <button type="button" class="favorite-btn ${isFavorite ? 'active' : ''}" data-favorite-toggle data-article-id="${a.id}" aria-label="${isFavorite ? '取消收藏文章' : '收藏文章'}" aria-pressed="${isFavorite ? 'true' : 'false'}">${isFavorite ? '★' : '☆'}</button>
                </div>
                <h3><a href="/article.html?id=${a.id}" data-article-link data-article-id="${a.id}">${escapeHtml(a.title)}</a></h3>
                <p>${escapeHtml(listSummary(a.summary || a.description || ''))}</p>
                <div class="meta">
                    <span>${escapeHtml(a.source_detail || a.source || '')}</span>
                    <span>${a.collected_at ? a.collected_at.slice(0, 10) : ''}</span>
                    <span class="score">${a.relevance_score}分</span>
                </div>
            </div>
        `}).join('');
    }

    function filterArticles() {
        let articles = allArticles;
        if (state.days > 0) {
            const cutoff = new Date();
            cutoff.setDate(cutoff.getDate() - state.days);
            articles = articles.filter(a => new Date(a.collected_at) >= cutoff);
        }
        if (state.source) {
            // state.source 可能是基础类型，或 RSS/热榜的具体子源名
            articles = articles.filter(a => {
                if (state.source === 'github' || state.source === 'feishu' || state.source === 'arxiv') {
                    return a.source === state.source;
                }
                // RSS/热榜子源匹配：source_detail 匹配，或无 detail 时按基础类型匹配
                if (['rss', 'hotlist'].includes(a.source)) {
                    return a.source_detail === state.source || (!a.source_detail && state.source === 'rss');
                }
                return false;
            });
        }
        if (state.tag) {
            articles = articles.filter(a => (a.tags || []).includes(state.tag));
        }
        if (state.favoritesOnly) {
            articles = articles.filter(a => favoriteIds.has(String(a.id)));
        }
        if (state.query) {
            const q = state.query.toLowerCase();
            articles = articles.filter(a =>
                a.title.toLowerCase().includes(q) ||
                (a.summary || '').toLowerCase().includes(q) ||
                (a.description || '').toLowerCase().includes(q)
            );
        }
        render(articles);
    }

    function loadFavoriteIds() {
        try {
            return new Set(JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]').map(String));
        } catch (_) {
            return new Set();
        }
    }

    function saveFavoriteIds() {
        localStorage.setItem(FAVORITES_KEY, JSON.stringify([...favoriteIds]));
    }

    function toggleFavorite(articleId) {
        const id = String(articleId);
        if (favoriteIds.has(id)) {
            favoriteIds.delete(id);
        } else {
            favoriteIds.add(id);
        }
        saveFavoriteIds();
        filterArticles();
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
            allArticles.forEach(a => {
                const raw = ['rss', 'hotlist'].includes(a.source) && a.source_detail ? a.source_detail : a.source;
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
            const allTags = [...new Set(allArticles.flatMap(a => a.tags || []))].sort();
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

        document.querySelectorAll('[data-favorite-filter]').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('[data-favorite-filter]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.favoritesOnly = btn.dataset.favoriteFilter === 'favorites';
                filterArticles();
            });
        });

        document.addEventListener('click', event => {
            const btn = event.target.closest('[data-favorite-toggle]');
            if (!btn) return;
            event.preventDefault();
            toggleFavorite(btn.dataset.articleId);
        });

        // default: show active button
        const activeBtn = document.querySelector('.date-filters button.active') ||
                          document.querySelector('.date-filters button[data-days="30"]');
        if (activeBtn) activeBtn.classList.add('active');
        filterArticles();
    }

    async function loadAllArticles() {
        try {
            const response = await fetch('/data.json');
            if (response.ok) {
                allArticles = await response.json();
            }
        } catch (_) {
            allArticles = INIT.articles;
        }
    }

    function setupArticleDrawer() {
        document.addEventListener('click', event => {
            const link = event.target.closest('[data-article-link]');
            if (!link || event.defaultPrevented) return;
            if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            if (!window.ArticleDetail) return;
            event.preventDefault();
            window.ArticleDetail.openDrawer(link.dataset.articleId, link);
        });
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

    document.addEventListener('DOMContentLoaded', async () => {
        if (document.getElementById('article-list')) {
            await loadAllArticles();
            setupFilters();
            setupArticleDrawer();
        }
        if (document.getElementById('stats-overview')) initDashboard();
    });
})();
