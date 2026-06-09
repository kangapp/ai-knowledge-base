(function () {
    function asObject(value) {
        if (!value || typeof value !== 'object' || Array.isArray(value)) {
            return {};
        }

        if (Object.getPrototypeOf(value) === Object.prototype) {
            return value;
        }

        return {};
    }

    function asString(value) {
        return typeof value === 'string' ? value : '';
    }

    function asStringList(value) {
        if (!Array.isArray(value)) {
            return [];
        }

        return value.filter(item => typeof item === 'string');
    }

    function asPositiveInt(value) {
        if (typeof value === 'number') {
            return Number.isInteger(value) && value > 0 ? value : 0;
        }

        if (typeof value !== 'string') {
            return 0;
        }

        const trimmed = value.trim();
        if (!/^[1-9]\d*$/.test(trimmed)) {
            return 0;
        }

        const parsed = Number(trimmed);
        return Number.isSafeInteger(parsed) ? parsed : 0;
    }

    function normalizeEvidence(value) {
        if (!Array.isArray(value)) {
            return [];
        }

        return value
            .map(item => {
                const evidence = asObject(item);
                return {
                    path: asString(evidence.path),
                    reason: asString(evidence.reason),
                };
            })
            .filter(item => item.path || item.reason);
    }

    function escapeHtml(value) {
        const text = value === null || value === undefined ? '' : String(value);
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function safeHttpUrl(value) {
        if (!value) {
            return '';
        }

        try {
            const url = new URL(value);
            if (url.protocol === 'http:' || url.protocol === 'https:') {
                return url.toString();
            }
        } catch (_error) {
            return '';
        }

        return '';
    }

    async function requestJson(url) {
        const response = await fetch(url, {
            headers: { Accept: 'application/json' },
        });

        let payload = null;
        try {
            payload = await response.json();
        } catch (_error) {
            payload = null;
        }

        if (!response.ok) {
            throw new Error((payload && payload.message) || `请求失败 (${response.status})`);
        }

        if (!payload || payload.code !== 0) {
            throw new Error((payload && payload.message) || '接口返回异常');
        }

        return payload.data;
    }

    function formatDate(value) {
        if (!value) {
            return '未知时间';
        }
        return escapeHtml(String(value).replace('T', ' ').slice(0, 16));
    }

    function shortSha(value) {
        const text = String(value || '').trim();
        return text ? escapeHtml(text.slice(0, 7)) : '未知提交';
    }

    function detailHref(value) {
        const safeId = asPositiveInt(value);
        return safeId ? `/deep-report.html?id=${safeId}` : '';
    }

    function firstTechStack(item) {
        const reportStack = asStringList(item.report_tech_stack);
        if (reportStack.length) {
            return reportStack.slice(0, 4);
        }

        const techStack = asObject(item.tech_stack_json);
        const values = [];
        for (const key of ['languages', 'frameworks', 'dependencies']) {
            const entries = asStringList(techStack[key]);
            if (entries.length) {
                values.push(...entries);
            }
        }
        return values.slice(0, 4);
    }

    function renderStatus(container, className, message) {
        container.innerHTML = `<div class="${className}">${escapeHtml(message)}</div>`;
    }

    function safeExternalLink(url, label, className) {
        const safeUrl = safeHttpUrl(url);
        if (!safeUrl) {
            return '';
        }
        return `<a class="${className}" href="${escapeHtml(safeUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
    }

    function renderListItem(item) {
        const summary = asString(item.report_summary) || asString(item.trigger_reason) || '暂无摘要';
        const stack = firstTechStack(item);
        const stackHtml = stack.length
            ? `<div class="deep-tech-list">${stack.map(value => `<span class="deep-tech-tag">${escapeHtml(value)}</span>`).join('')}</div>`
            : '<div class="deep-empty-inline">未提取技术栈</div>';
        const repoLink = safeExternalLink(item.repo_url, 'GitHub', 'deep-inline-link');
        const safeId = asPositiveInt(item.id);
        const detailUrl = detailHref(item.id);
        const repoName = escapeHtml(asString(item.repo_name) || '未命名仓库');
        const titleHtml = safeId
            ? `<h2><a href="/deep-report.html?id=${safeId}">${repoName}</a></h2>`
            : `<h2>${repoName}</h2>`;
        const detailLink = detailUrl ? `<span><a href="${detailUrl}">查看详情</a></span>` : '';

        return `
            <article class="deep-list-item">
                <div class="deep-list-main">
                    <div class="deep-list-header">
                        <div class="deep-list-title-group">
                            ${titleHtml}
                            <div class="deep-list-links">${repoLink}</div>
                        </div>
                        <div class="deep-score-badge" aria-label="候选分">${escapeHtml(item.candidate_score || 0)}</div>
                    </div>
                    <p class="deep-summary">${escapeHtml(summary)}</p>
                    ${stackHtml}
                    <div class="meta deep-meta">
                        <span>更新时间 ${formatDate(item.updated_at || item.created_at)}</span>
                        <span>Commit ${shortSha(item.commit_sha)}</span>
                        ${detailLink}
                    </div>
                </div>
            </article>
        `;
    }

    function listSection(title, items) {
        const safeItems = asStringList(items);
        if (!safeItems.length) {
            return '';
        }

        return `
            <section class="deep-band">
                <h2>${escapeHtml(title)}</h2>
                <ul class="deep-bullets">
                    ${safeItems.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
                </ul>
            </section>
        `;
    }

    function renderEvidenceItems(items) {
        const evidenceItems = normalizeEvidence(items);
        if (!evidenceItems.length) {
            return '';
        }

        return `
            <section class="deep-band">
                <h2>源码证据</h2>
                <ul class="deep-evidence-list">
                    ${evidenceItems.map(item => `
                        <li>
                            <code>${escapeHtml(item.path)}</code>
                            <span>${escapeHtml(item.reason)}</span>
                        </li>
                    `).join('')}
                </ul>
            </section>
        `;
    }

    function renderArchitecture(report) {
        const architecture = asObject(report.architecture);
        const pattern = asString(architecture.pattern);
        const components = asStringList(architecture.components);
        if (!pattern && !components.length) {
            return '';
        }

        return `
            <section class="deep-band">
                <h2>架构</h2>
                ${pattern ? `<p class="deep-architecture-pattern">模式：${escapeHtml(pattern)}</p>` : ''}
                ${components.length ? `
                    <ul class="deep-bullets">
                        ${components.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
                    </ul>
                ` : ''}
            </section>
        `;
    }

    function renderStructuredReport(item) {
        const report = asObject(item.report_json);
        const repoLink = safeExternalLink(item.repo_url, 'GitHub 仓库', 'deep-inline-link');
        const heading = asString(report.title) || asString(item.repo_name) || '深度报告';
        const stack = asStringList(report.tech_stack);
        const summary = asString(report.summary);

        return `
            <section class="deep-band deep-report-head">
                <div class="deep-report-head-main">
                    <div>
                        <div class="deep-kicker">候选分 ${escapeHtml(item.candidate_score || 0)}</div>
                        <h1>${escapeHtml(heading)}</h1>
                        <p class="deep-repo-name">${escapeHtml(asString(item.repo_name))}</p>
                    </div>
                    <div class="deep-score-badge" aria-label="候选分">${escapeHtml(item.candidate_score || 0)}</div>
                </div>
                <div class="meta deep-meta">
                    <span>更新时间 ${formatDate(item.updated_at || item.created_at)}</span>
                    <span>Commit ${shortSha(item.commit_sha)}</span>
                    ${repoLink ? `<span>${repoLink}</span>` : ''}
                </div>
                ${summary ? `<p class="deep-overview">${escapeHtml(summary)}</p>` : ''}
            </section>
            ${stack.length ? `
                <section class="deep-band">
                    <h2>技术栈</h2>
                    <div class="deep-tech-list">
                        ${stack.map(item => `<span class="deep-tech-tag">${escapeHtml(item)}</span>`).join('')}
                    </div>
                </section>
            ` : ''}
            ${renderArchitecture(report)}
            ${listSection('数据流', report.data_flow)}
            ${listSection('应用场景', report.use_cases)}
            ${listSection('优势', report.strengths)}
            ${listSection('局限', report.limitations)}
            ${listSection('可执行建议', report.actionable_takeaways)}
            ${renderEvidenceItems(report.source_evidence)}
        `;
    }

    function hasStructuredReport(item) {
        const report = asObject(item.report_json);
        const architecture = asObject(report.architecture);
        return Boolean(
            asString(report.summary) ||
            asStringList(report.tech_stack).length ||
            asString(architecture.pattern) ||
            asStringList(architecture.components).length ||
            asStringList(report.data_flow).length ||
            asStringList(report.use_cases).length ||
            asStringList(report.strengths).length ||
            asStringList(report.limitations).length ||
            asStringList(report.actionable_takeaways).length ||
            normalizeEvidence(report.source_evidence).length
        );
    }

    function renderMarkdownFallback(item) {
        const reportMarkdown = asString(item.report_markdown) || '暂无可展示的报告内容。';
        const repoLink = safeExternalLink(item.repo_url, 'GitHub 仓库', 'deep-inline-link');

        return `
            <section class="deep-band deep-report-head">
                <div class="deep-report-head-main">
                    <div>
                        <div class="deep-kicker">候选分 ${escapeHtml(item.candidate_score || 0)}</div>
                        <h1>${escapeHtml(asString(item.repo_name) || '深度报告')}</h1>
                    </div>
                    <div class="deep-score-badge" aria-label="候选分">${escapeHtml(item.candidate_score || 0)}</div>
                </div>
                <div class="meta deep-meta">
                    <span>更新时间 ${formatDate(item.updated_at || item.created_at)}</span>
                    <span>Commit ${shortSha(item.commit_sha)}</span>
                    ${repoLink ? `<span>${repoLink}</span>` : ''}
                </div>
            </section>
            <section class="deep-band">
                <h2>原始报告</h2>
                <pre class="deep-report-pre" style="white-space: pre-wrap;">${escapeHtml(reportMarkdown)}</pre>
            </section>
        `;
    }

    function renderList(data) {
        const container = document.getElementById('deep-reports-list');
        if (!container) {
            return;
        }

        const payload = asObject(data);
        const items = Array.isArray(payload.items) ? payload.items.map(asObject) : [];
        const filteredItems = items.filter(item => item.status === 'completed');

        if (!filteredItems.length) {
            renderStatus(container, 'empty-text', '暂无已完成的深度报告。');
            return;
        }

        container.innerHTML = filteredItems.map(renderListItem).join('');
    }

    function renderDetail(item) {
        const container = document.getElementById('deep-report-detail');
        if (!container) {
            return;
        }

        const safeItem = asObject(item);
        if (!asPositiveInt(safeItem.id)) {
            renderStatus(container, 'empty-text', '暂无可展示的深度报告。');
            return;
        }

        container.innerHTML = hasStructuredReport(safeItem)
            ? renderStructuredReport(safeItem)
            : renderMarkdownFallback(safeItem);
    }

    async function initListPage() {
        const data = await requestJson('/api/deep-reports?page=1&page_size=100');
        renderList(data);
    }

    async function initDetailPage() {
        const params = new URLSearchParams(window.location.search);
        const id = params.get('id');
        const safeId = asPositiveInt(id);
        const data = safeId
            ? await requestJson(`/api/deep-reports/${safeId}`)
            : await requestJson('/api/deep-reports/latest');
        renderDetail(data);
    }

    async function init() {
        if (document.getElementById('deep-reports-list')) {
            await initListPage();
        }

        if (document.getElementById('deep-report-detail')) {
            await initDetailPage();
        }
    }

    init().catch(error => {
        const target = document.getElementById('deep-reports-list') || document.getElementById('deep-report-detail');
        if (target) {
            renderStatus(target, 'error', error.message || '深度报告加载失败。');
        }
    });
})();
