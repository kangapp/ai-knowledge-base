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
        'hn': 'Hacker News',
        'feishu': '飞书',
        'arxiv': 'arXiv',
    };
    window.__SOURCE_ID_LABELS__ = {
        github_trending: 'GitHub Trending AI',
        github_trending_hot: 'GitHub 持续热门',
        github_trending_velocity: 'GitHub 趋势增速',
        github_ai_devtools: 'GitHub AI 开发工具',
        github_agent_infra: 'GitHub Agent 联网工具',
        github_data_ai: 'GitHub AI × 数据工程',
        github_data_infra: 'GitHub 数据工程基础设施',
    };

    const INIT = window.__INIT__ || { articles: [], stats: {} };
    const FAVORITES_KEY = 'ai_kb_favorite_articles';
    const HIDDEN_KEY = 'ai_kb_hidden_articles';
    const PAGE_SIZE_KEY = 'ai_kb_page_size';
    const SCORE_DIMENSIONS = [
        ['ai_relevance', 'AI 相关度'],
        ['engineering_relevance', '工程相关度'],
        ['data_infra_relevance', '数据工程相关度'],
        ['developer_utility', '项目实用性'],
        ['project_signal', '项目信号'],
        ['content_clarity', '内容清晰度'],
        ['content_depth', '内容深度'],
        ['info_density', '信息密度'],
        ['timeliness', '时效性'],
    ];
    const state = { source: '', tag: '', days: 30, query: '', favoritesOnly: false, view: 'all', page: 1, pageSize: loadPageSize() };
    let allArticles = INIT.articles;
    let favoriteIds = loadFavoriteIds();
    let hiddenIds = loadHiddenIds();
    const scoreDetailCache = new Map();
    let activeScoreTrigger = null;
    let scoreTooltipHideTimer = null;

    function getSourceLabel(source, sourceDetail, sourceId) {
        if (sourceId && window.__SOURCE_ID_LABELS__[sourceId]) {
            return window.__SOURCE_ID_LABELS__[sourceId];
        }
        if (source === 'hotlist' && sourceDetail) {
            return sourceDetail;
        }
        if (source === 'hn' && sourceDetail) {
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
        if (window.__SOURCE_ID_LABELS__[s]) return window.__SOURCE_ID_LABELS__[s];
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
            const label = getSourceLabel(a.source, a.source_detail, a.source_id);
            const tagsHtml = (a.tags || []).slice(0, 3).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join('');
            const isFavorite = favoriteIds.has(String(a.id));
            const isHidden = hiddenIds.has(String(a.id));
            return `
            <div class="article-card" data-score="${a.relevance_score}" data-source="${a.source}" data-source-id="${a.source_id || ''}" data-source-detail="${a.source_detail || ''}">
                <div class="card-header">
                    <span class="topic-tag">${escapeHtml(label)}</span>
                    ${tagsHtml ? `<div class="tags">${tagsHtml}</div>` : ''}
                    <button type="button" class="favorite-btn ${isFavorite ? 'active' : ''}" data-favorite-toggle data-article-id="${a.id}" aria-label="${isFavorite ? '取消收藏文章' : '收藏文章'}" aria-pressed="${isFavorite ? 'true' : 'false'}">${isFavorite ? '★' : '☆'}</button>
                    <button type="button" class="hide-btn ${isHidden ? 'active' : ''}" data-hide-toggle data-article-id="${a.id}">${isHidden ? '恢复' : '屏蔽'}</button>
                </div>
                <h3><a href="/article.html?id=${a.id}" data-article-link data-article-id="${a.id}">${escapeHtml(a.title)}</a></h3>
                <p>${escapeHtml(listSummary(a.summary || a.description || ''))}</p>
                <div class="meta">
                    <span>${escapeHtml(a.source_detail || a.source || '')}</span>
                    <span>${a.collected_at ? a.collected_at.slice(0, 10) : ''}</span>
                    <span class="score" data-score-tooltip data-article-id="${a.id}" tabindex="0" aria-label="查看评分组成">${a.relevance_score}分</span>
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
            // state.source 可能是配置 source_id、基础类型，或 RSS/热榜的具体子源名
            articles = articles.filter(a => {
                if (a.source_id === state.source) {
                    return true;
                }
                if (state.source === 'github' || state.source === 'feishu' || state.source === 'arxiv') {
                    return a.source === state.source;
                }
                // RSS/热榜子源匹配：source_detail 匹配，或无 detail 时按基础类型匹配
                if (['rss', 'hotlist', 'hn'].includes(a.source)) {
                    return a.source_detail === state.source || (!a.source_detail && state.source === 'rss');
                }
                return false;
            });
        }
        if (state.tag) {
            articles = articles.filter(a => (a.tags || []).includes(state.tag));
        }
        if (state.view === 'hidden') {
            articles = articles.filter(a => hiddenIds.has(String(a.id)));
        } else {
            articles = articles.filter(a => !hiddenIds.has(String(a.id)));
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
        renderPage(articles);
    }

    function renderPage(articles) {
        const totalPages = Math.max(1, Math.ceil(articles.length / state.pageSize));
        if (state.page > totalPages) state.page = totalPages;
        const start = (state.page - 1) * state.pageSize;
        render(articles.slice(start, start + state.pageSize));
        renderPagination(articles.length, totalPages);
    }

    function renderPagination(total, totalPages) {
        const el = document.getElementById('pagination-controls');
        if (!el) return;
        el.innerHTML = `
            <label>每页
                <select data-page-size aria-label="每页条数">
                    ${[10, 20, 50, 100].map(size => `<option value="${size}" ${state.pageSize === size ? 'selected' : ''}>${size}</option>`).join('')}
                </select>
            </label>
            <button type="button" data-page-prev ${state.page <= 1 ? 'disabled' : ''}>上一页</button>
            <span>${total ? state.page : 0} / ${total ? totalPages : 0} 页 · ${total} 条</span>
            <button type="button" data-page-next ${state.page >= totalPages ? 'disabled' : ''}>下一页</button>
        `;
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

    function loadHiddenIds() {
        try {
            return new Set(JSON.parse(localStorage.getItem(HIDDEN_KEY) || '[]').map(String));
        } catch (_) {
            return new Set();
        }
    }

    function saveHiddenIds() {
        localStorage.setItem(HIDDEN_KEY, JSON.stringify([...hiddenIds]));
    }

    function toggleHidden(articleId) {
        const id = String(articleId);
        if (hiddenIds.has(id)) {
            hiddenIds.delete(id);
        } else {
            hiddenIds.add(id);
        }
        saveHiddenIds();
        state.page = 1;
        filterArticles();
    }

    function loadPageSize() {
        const size = parseInt(localStorage.getItem(PAGE_SIZE_KEY), 10);
        return [10, 20, 50, 100].includes(size) ? size : 20;
    }

    function savePageSize() {
        localStorage.setItem(PAGE_SIZE_KEY, String(state.pageSize));
    }

    function escapeHtml(str) {
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function getScoreTooltip() {
        return document.getElementById('score-tooltip');
    }

    function positionScoreTooltip(trigger, tooltip) {
        const rect = trigger.getBoundingClientRect();
        const gap = 8;
        const margin = 12;
        tooltip.hidden = false;
        const left = Math.min(window.innerWidth - tooltip.offsetWidth - margin, Math.max(margin, rect.left));
        let top = rect.bottom + gap;
        if (top + tooltip.offsetHeight > window.innerHeight - margin) {
            top = rect.top - tooltip.offsetHeight - gap;
        }
        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${Math.max(margin, top)}px`;
    }

    async function loadScoreDetail(articleId) {
        if (scoreDetailCache.has(articleId)) return scoreDetailCache.get(articleId);
        const response = await fetch(`/api/articles/${encodeURIComponent(articleId)}`);
        const payload = await response.json();
        if (!response.ok || payload.code !== 0 || !payload.data) {
            throw new Error(payload.message || '评分加载失败');
        }
        scoreDetailCache.set(articleId, payload.data);
        return payload.data;
    }

    function renderScoreTooltip(trigger, article, message) {
        const tooltip = getScoreTooltip();
        if (!tooltip) return;
        if (message) {
            tooltip.innerHTML = `<div class="score-tooltip-status">${escapeHtml(message)}</div>`;
            positionScoreTooltip(trigger, tooltip);
            return;
        }
        const dimensions = article.dimensions || {};
        const rows = SCORE_DIMENSIONS.filter(([key]) => dimensions[key]).map(([key, label]) => {
            const dim = dimensions[key];
            const score = Number(dim.score || 0);
            const maxScore = Number(dim.max_score || 0);
            const percent = maxScore ? Math.max(0, Math.min(100, score / maxScore * 100)) : 0;
            const reason = dim.reason ? `<p>${escapeHtml(String(dim.reason))}</p>` : '';
            return `
                <div class="score-tooltip-row">
                    <div class="score-tooltip-heading"><strong>${label}</strong><span>${score}/${maxScore}</span></div>
                    <div class="score-tooltip-track"><span style="width:${percent}%"></span></div>
                    ${reason}
                </div>
            `;
        }).join('');
        tooltip.innerHTML = rows || '<div class="score-tooltip-status">暂无评分组成</div>';
        positionScoreTooltip(trigger, tooltip);
    }

    async function showScoreTooltip(trigger) {
        clearTimeout(scoreTooltipHideTimer);
        const articleId = trigger.dataset.articleId;
        if (!articleId) return;
        activeScoreTrigger = trigger;
        trigger.setAttribute('aria-describedby', 'score-tooltip');
        renderScoreTooltip(trigger, null, '正在加载评分组成…');
        try {
            const article = await loadScoreDetail(articleId);
            if (activeScoreTrigger === trigger) renderScoreTooltip(trigger, article);
        } catch (error) {
            if (activeScoreTrigger === trigger) renderScoreTooltip(trigger, null, error.message || '评分加载失败');
        }
    }

    function hideScoreTooltip() {
        const tooltip = getScoreTooltip();
        if (!tooltip) return;
        if (activeScoreTrigger) activeScoreTrigger.removeAttribute('aria-describedby');
        activeScoreTrigger = null;
        tooltip.hidden = true;
    }

    function scheduleHideScoreTooltip() {
        clearTimeout(scoreTooltipHideTimer);
        scoreTooltipHideTimer = setTimeout(hideScoreTooltip, 120);
    }

    function setupScoreTooltip() {
        document.addEventListener('pointerenter', event => {
            const trigger = event.target.closest('[data-score-tooltip]');
            if (trigger) showScoreTooltip(trigger);
        }, true);
        document.addEventListener('pointerleave', event => {
            if (event.target.closest('[data-score-tooltip]')) scheduleHideScoreTooltip();
        }, true);
        document.addEventListener('focusin', event => {
            const trigger = event.target.closest('[data-score-tooltip]');
            if (trigger) showScoreTooltip(trigger);
        });
        document.addEventListener('focusout', event => {
            if (event.target.closest('[data-score-tooltip]')) scheduleHideScoreTooltip();
        });
        document.addEventListener('click', event => {
            const trigger = event.target.closest('[data-score-tooltip]');
            if (!trigger) return;
            event.preventDefault();
            showScoreTooltip(trigger);
        });
        window.addEventListener('resize', hideScoreTooltip);
        window.addEventListener('scroll', hideScoreTooltip, true);
    }

    function setupFilters() {
        const searchBox = document.getElementById('search-box');
        if (searchBox) {
            searchBox.addEventListener('input', debounce(e => {
                state.query = e.target.value;
                state.page = 1;
                filterArticles();
            }, 200));
        }

        const sourceFilter = document.getElementById('source-filter');
        if (sourceFilter) {
            // 按 label 分组去重，value 使用最后一个匹配的 raw
            const sourceMap = {};
            allArticles.forEach(a => {
                const raw = ['rss', 'hotlist', 'hn'].includes(a.source) && a.source_detail ? a.source_detail : (a.source_id || a.source);
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
                state.page = 1;
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
                state.page = 1;
                filterArticles();
            });
        }

        document.querySelectorAll('.date-filters button').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.date-filters button').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.days = parseInt(btn.dataset.days) || 0;
                state.page = 1;
                filterArticles();
            });
        });

        document.querySelectorAll('[data-view-filter]').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('[data-view-filter]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.view = btn.dataset.viewFilter;
                state.favoritesOnly = state.view === 'favorites';
                state.page = 1;
                filterArticles();
            });
        });

        document.addEventListener('click', event => {
            const btn = event.target.closest('[data-favorite-toggle]');
            if (!btn) return;
            event.preventDefault();
            toggleFavorite(btn.dataset.articleId);
        });

        document.addEventListener('click', event => {
            const btn = event.target.closest('[data-hide-toggle]');
            if (!btn) return;
            event.preventDefault();
            toggleHidden(btn.dataset.articleId);
        });

        document.addEventListener('click', event => {
            if (event.target.closest('[data-page-prev]') && state.page > 1) {
                state.page -= 1;
                filterArticles();
            }
            if (event.target.closest('[data-page-next]')) {
                state.page += 1;
                filterArticles();
            }
        });

        document.addEventListener('change', event => {
            if (!event.target.matches('[data-page-size]')) return;
            state.pageSize = parseInt(event.target.value, 10) || 20;
            state.page = 1;
            savePageSize();
            filterArticles();
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
            setupScoreTooltip();
        }
        if (document.getElementById('stats-overview')) initDashboard();
    });
})();
