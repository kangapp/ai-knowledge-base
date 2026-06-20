(function() {
    const DIMENSIONS = [
        ['ai_relevance', 'AI 相关度'],
        ['content_depth', '内容深度'],
        ['info_density', '信息密度'],
        ['timeliness', '时效性'],
    ];
    let lastFocusedElement = null;

    function createElement(tag, className, text) {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (text != null) element.textContent = String(text);
        return element;
    }

    function appendLink(parent, label, href, className) {
        const link = createElement('a', className, label);
        link.href = href;
        if (/^https?:\/\//.test(href)) {
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
        }
        parent.appendChild(link);
        return link;
    }

    function formatDate(value) {
        if (!value) return '未知';
        return String(value).slice(0, 10);
    }

    function sourceLabel(article) {
        const raw = article.source_detail || article.source || '未知来源';
        const labels = window.__RSS_LABELS__ || {};
        return labels[raw] || raw;
    }

    function setStatus(container, message, isError) {
        container.replaceChildren(
            createElement('p', isError ? 'article-detail-status error' : 'article-detail-status loading', message)
        );
    }

    function renderTags(parent, tags) {
        if (!Array.isArray(tags) || tags.length === 0) return;
        const tagList = createElement('div', 'article-detail-tags');
        tags.forEach(tag => tagList.appendChild(createElement('span', 'tag', tag)));
        parent.appendChild(tagList);
    }

    function renderDimensions(parent, dimensions) {
        const available = DIMENSIONS.filter(([key]) => dimensions && dimensions[key]);
        if (available.length === 0) return;

        const section = createElement('section', 'article-detail-section');
        section.appendChild(createElement('h2', '', '审核评分'));
        const grid = createElement('div', 'article-dimension-grid');
        available.forEach(([key, label]) => {
            const dimension = dimensions[key];
            const card = createElement('article', 'article-dimension-card');
            const heading = createElement('div', 'article-dimension-heading');
            heading.appendChild(createElement('strong', '', label));
            heading.appendChild(
                createElement('span', '', `${dimension.score || 0}/${dimension.max_score || 0}`)
            );
            card.appendChild(heading);
            const track = createElement('div', 'article-dimension-track');
            const fill = createElement('span', 'article-dimension-fill');
            const maxScore = Number(dimension.max_score) || 1;
            const percent = Math.max(0, Math.min(100, Number(dimension.score || 0) / maxScore * 100));
            fill.style.width = `${percent}%`;
            track.appendChild(fill);
            card.appendChild(track);
            if (dimension.reason) card.appendChild(createElement('p', '', dimension.reason));
            grid.appendChild(card);
        });
        section.appendChild(grid);
        parent.appendChild(section);
    }

    function renderArticle(container, article) {
        const content = createElement('article', 'article-detail-content');
        const eyebrow = createElement('div', 'article-detail-eyebrow');
        eyebrow.appendChild(createElement('span', 'topic-tag', sourceLabel(article)));
        eyebrow.appendChild(
            createElement('span', '', `发布 ${formatDate(article.published_at)} · 收录 ${formatDate(article.collected_at)}`)
        );
        content.appendChild(eyebrow);
        content.appendChild(createElement('h1', '', article.title || '未命名文章'));
        renderTags(content, article.tags);

        const actions = createElement('div', 'article-detail-actions');
        if (article.url) appendLink(actions, '查看原文 ↗', article.url, 'button primary');
        if (article.deep_report && article.deep_report.url) {
            appendLink(actions, '查看深度报告', article.deep_report.url, 'button');
        }
        const shareButton = createElement('button', 'button', '复制详情链接');
        shareButton.type = 'button';
        shareButton.addEventListener('click', async () => {
            const url = `${location.origin}/article.html?id=${article.id}`;
            try {
                await navigator.clipboard.writeText(url);
                shareButton.textContent = '已复制';
            } catch (error) {
                shareButton.textContent = '复制失败';
            }
        });
        actions.appendChild(shareButton);
        content.appendChild(actions);

        const summarySection = createElement('section', 'article-detail-section article-summary-card');
        summarySection.appendChild(createElement('h2', '', 'AI 摘要'));
        summarySection.appendChild(createElement('p', '', article.summary || '暂无摘要'));
        content.appendChild(summarySection);

        if (article.description && article.description !== article.summary) {
            const originalSection = createElement('section', 'article-detail-section');
            originalSection.appendChild(createElement('h2', '', '原始简介'));
            originalSection.appendChild(createElement('p', 'article-original-description', article.description));
            content.appendChild(originalSection);
        }

        if (article.deep_report) {
            const report = createElement('section', 'article-detail-section article-deep-report-callout');
            report.appendChild(createElement('h2', '', '深度报告已生成'));
            report.appendChild(
                createElement('p', '', article.deep_report.trigger_reason || '该项目已完成源码级深度分析。')
            );
            appendLink(report, `打开 ${article.deep_report.repo_name || '深度报告'}`, article.deep_report.url, '');
            content.appendChild(report);
        }

        renderDimensions(content, article.dimensions);

        const processing = createElement('details', 'article-processing-details');
        processing.appendChild(createElement('summary', '', '处理信息'));
        const metadata = createElement('dl', 'article-metadata');
        [
            ['综合评分', `${article.relevance_score || 0} 分`],
            ['分析花费', `$${Number(article.analysis_cost || 0).toFixed(6)}`],
            ['分析 Token', article.analysis_tokens || 0],
        ].forEach(([label, value]) => {
            metadata.appendChild(createElement('dt', '', label));
            metadata.appendChild(createElement('dd', '', value));
        });
        processing.appendChild(metadata);
        content.appendChild(processing);
        container.replaceChildren(content);
    }

    async function loadArticle(container, articleId) {
        if (!articleId) {
            setStatus(container, '缺少文章 ID，无法加载详情。', true);
            return;
        }
        setStatus(container, '正在加载文章详情…', false);
        try {
            const response = await fetch(`/api/articles/${encodeURIComponent(articleId)}`);
            const payload = await response.json();
            if (!response.ok || payload.code !== 0 || !payload.data) {
                throw new Error(payload.message || '文章详情加载失败');
            }
            renderArticle(container, payload.data);
        } catch (error) {
            setStatus(container, error.message || '文章详情加载失败，请稍后重试。', true);
        }
    }

    function openDrawer(articleId, trigger) {
        const drawer = document.getElementById('article-detail-drawer');
        if (!drawer) return;
        lastFocusedElement = trigger || document.activeElement;
        drawer.hidden = false;
        document.body.classList.add('article-drawer-open');
        const content = drawer.querySelector('[data-article-detail-content]');
        loadArticle(content, articleId);
        const closeButton = drawer.querySelector('[data-article-drawer-close]');
        if (closeButton) closeButton.focus();
    }

    function closeDrawer() {
        const drawer = document.getElementById('article-detail-drawer');
        if (!drawer || drawer.hidden) return;
        drawer.hidden = true;
        document.body.classList.remove('article-drawer-open');
        const content = drawer.querySelector('[data-article-detail-content]');
        if (content) content.replaceChildren();
        if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
            lastFocusedElement.focus();
        }
    }

    function setupDrawer() {
        const drawer = document.getElementById('article-detail-drawer');
        if (!drawer) return;
        drawer.querySelectorAll('[data-article-drawer-close]').forEach(element => {
            element.addEventListener('click', closeDrawer);
        });
        document.addEventListener('keydown', event => {
            if (event.key === 'Escape') closeDrawer();
        });
    }

    function mountPage(container) {
        const articleId = new URLSearchParams(location.search).get('id');
        loadArticle(container, articleId);
    }

    document.addEventListener('DOMContentLoaded', () => {
        setupDrawer();
        const pageContainer = document.querySelector('[data-article-detail-page]');
        if (pageContainer) mountPage(pageContainer);
    });

    window.ArticleDetail = { openDrawer, closeDrawer, mountPage };
})();
