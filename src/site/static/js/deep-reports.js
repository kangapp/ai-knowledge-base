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

    function normalizeFlow(value) {
        const flow = asObject(value);
        const seenIds = new Set();
        const steps = Array.isArray(flow.steps)
            ? flow.steps
                .map(asObject)
                .map(step => ({
                    id: asString(step.id),
                    title: asString(step.title),
                    description: asString(step.description),
                }))
                .filter(step => {
                    if (!step.id || !step.title || seenIds.has(step.id)) {
                        return false;
                    }
                    seenIds.add(step.id);
                    return true;
                })
            : [];

        return {
            prerequisites: asStringList(flow.prerequisites),
            steps,
            expectedResult: asString(flow.expected_result),
            operations: asStringList(flow.operations),
        };
    }

    function normalizeArchitecture(value) {
        const architecture = asObject(value);
        const seenIds = new Set();
        const nodes = Array.isArray(architecture.nodes)
            ? architecture.nodes
                .map(asObject)
                .map(node => ({
                    id: asString(node.id),
                    label: asString(node.label),
                    role: asString(node.role),
                    group: asString(node.group),
                }))
                .filter(node => {
                    if (!node.id || !node.label || seenIds.has(node.id)) {
                        return false;
                    }
                    seenIds.add(node.id);
                    return true;
                })
            : [];
        const nodeIds = new Set(nodes.map(node => node.id));
        const rawEdges = Array.isArray(architecture.edges)
            ? architecture.edges.map(asObject).map(edge => ({
                    source: asString(edge.source),
                    target: asString(edge.target),
                    label: asString(edge.label),
                }))
            : [];
        const edges = rawEdges.filter(edge => (
            edge.source &&
            edge.target &&
            edge.source !== edge.target &&
            nodeIds.has(edge.source) &&
            nodeIds.has(edge.target)
        ));

        return {
            pattern: asString(architecture.pattern),
            summary: asString(architecture.summary),
            nodes,
            edges,
            isValid: nodes.length === (Array.isArray(architecture.nodes) ? architecture.nodes.length : 0) &&
                edges.length === rawEdges.length,
        };
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

    function renderDecision(value) {
        const decision = asObject(value);
        const recommendation = asString(decision.recommendation);
        const reasons = asStringList(decision.reasons);
        const bestFor = asStringList(decision.best_for);
        const notFor = asStringList(decision.not_for);
        if (!recommendation && !reasons.length && !bestFor.length && !notFor.length) {
            return '';
        }

        return `
            <section class="deep-band deep-decision">
                <h2>采用结论</h2>
                ${recommendation ? `<p class="deep-recommendation">${escapeHtml(recommendation)}</p>` : ''}
                ${reasons.length ? `
                    <ul class="deep-bullets deep-reason-list">
                        ${reasons.map(item => `<li>${escapeHtml(item)}</li>`).join('')}
                    </ul>
                ` : ''}
                <div class="deep-decision-grid">
                    ${bestFor.length ? `
                        <div class="deep-decision-card deep-decision-best">
                            <h3>适合</h3>
                            <ul>${bestFor.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
                        </div>
                    ` : ''}
                    ${notFor.length ? `
                        <div class="deep-decision-card deep-decision-not">
                            <h3>不适合</h3>
                            <ul>${notFor.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
                        </div>
                    ` : ''}
                </div>
            </section>
        `;
    }

    function renderArchitectureDiagram(value) {
        const architecture = normalizeArchitecture(value);
        if (!architecture.pattern && !architecture.summary && !architecture.nodes.length) {
            return '';
        }

        const nodeWidth = 150;
        const nodeHeight = 72;
        const gap = 40;
        const padding = 30;
        const width = Math.max(720, padding * 2 + architecture.nodes.length * nodeWidth + Math.max(architecture.nodes.length - 1, 0) * gap);
        const height = 150;
        const positions = new Map();
        architecture.nodes.forEach((node, index) => {
            positions.set(node.id, {
                x: padding + index * (nodeWidth + gap),
                y: 38,
            });
        });
        const edgeSvg = architecture.edges.map(edge => {
            const source = positions.get(edge.source);
            const target = positions.get(edge.target);
            if (!source || !target) {
                return '';
            }
            const x1 = source.x + nodeWidth;
            const y1 = source.y + nodeHeight / 2;
            const x2 = target.x;
            const y2 = target.y + nodeHeight / 2;
            const labelX = (x1 + x2) / 2;
            return `
                <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" marker-end="url(#deep-arrow)"></line>
                ${edge.label ? `<text class="deep-edge-label" x="${labelX}" y="${y1 - 8}" text-anchor="middle">${escapeHtml(edge.label)}</text>` : ''}
            `;
        }).join('');
        const nodeSvg = architecture.nodes.map(node => {
            const position = positions.get(node.id);
            return `
                <g class="deep-architecture-node">
                    <rect x="${position.x}" y="${position.y}" width="${nodeWidth}" height="${nodeHeight}" rx="8"></rect>
                    <text x="${position.x + nodeWidth / 2}" y="${position.y + 28}" text-anchor="middle">${escapeHtml(node.label)}</text>
                    <text class="deep-node-role" x="${position.x + nodeWidth / 2}" y="${position.y + 50}" text-anchor="middle">${escapeHtml(node.role)}</text>
                </g>
            `;
        }).join('');
        const cards = architecture.nodes.map(node => `
            <article class="deep-architecture-card">
                <h3>${escapeHtml(node.label)}</h3>
                <p>${escapeHtml(node.role)}</p>
                ${node.group ? `<span>${escapeHtml(node.group)}</span>` : ''}
            </article>
        `).join('');
        const canRenderDiagram = architecture.nodes.length >= 4 && architecture.isValid;
        const diagram = canRenderDiagram ? `
            <div class="deep-architecture-diagram" aria-label="系统架构图">
                <svg viewBox="0 0 ${width} ${height}" role="img">
                    <defs>
                        <marker id="deep-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                            <path d="M0,0 L8,4 L0,8 Z"></path>
                        </marker>
                    </defs>
                    ${edgeSvg}
                    ${nodeSvg}
                </svg>
            </div>
        ` : '';

        return `
            <section class="deep-band">
                <h2>系统架构</h2>
                ${architecture.pattern ? `<p class="deep-architecture-pattern">模式：${escapeHtml(architecture.pattern)}</p>` : ''}
                ${architecture.summary ? `<p class="deep-section-summary">${escapeHtml(architecture.summary)}</p>` : ''}
                ${diagram}
                ${cards ? `<div class="deep-architecture-cards${canRenderDiagram ? '' : ' is-fallback'}">${cards}</div>` : ''}
            </section>
        `;
    }

    function renderFlow(title, value) {
        const flow = normalizeFlow(value);
        if (!flow.steps.length && !flow.prerequisites.length && !flow.expectedResult && !flow.operations.length) {
            return '';
        }

        return `
            <section class="deep-band">
                <h2>${escapeHtml(title)}</h2>
                ${flow.prerequisites.length ? `
                    <div class="deep-prerequisites">
                        <strong>前置条件</strong>
                        <span>${flow.prerequisites.map(escapeHtml).join(' · ')}</span>
                    </div>
                ` : ''}
                ${flow.steps.length ? `
                    <div class="deep-flow">
                        ${flow.steps.map((step, index) => `
                            <article class="deep-flow-step">
                                <span class="deep-flow-index">${index + 1}</span>
                                <h3>${escapeHtml(step.title)}</h3>
                                ${step.description ? `<p>${escapeHtml(step.description)}</p>` : ''}
                            </article>
                        `).join('')}
                    </div>
                ` : ''}
                ${flow.expectedResult ? `<p class="deep-flow-result"><strong>预期结果：</strong>${escapeHtml(flow.expectedResult)}</p>` : ''}
                ${flow.operations.length ? `
                    <div class="deep-operations">
                        <strong>持续运行</strong>
                        <ul>${flow.operations.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
                    </div>
                ` : ''}
            </section>
        `;
    }

    function renderCoreModules(value) {
        if (!Array.isArray(value)) {
            return '';
        }
        const modules = value
            .map(asObject)
            .map(module => ({
                name: asString(module.name),
                responsibility: asString(module.responsibility),
                dependsOn: asStringList(module.depends_on),
            }))
            .filter(module => module.name || module.responsibility);
        if (!modules.length) {
            return '';
        }

        return `
            <section class="deep-band">
                <h2>核心模块</h2>
                <div class="deep-module-grid">
                    ${modules.map(module => `
                        <article class="deep-module-card">
                            <h3>${escapeHtml(module.name)}</h3>
                            <p>${escapeHtml(module.responsibility)}</p>
                            ${module.dependsOn.length ? `<span>依赖：${module.dependsOn.map(escapeHtml).join('、')}</span>` : ''}
                        </article>
                    `).join('')}
                </div>
            </section>
        `;
    }

    function renderAdoptionNotes(strengths, limitations, takeaways) {
        const sections = [
            ['优势', asStringList(strengths)],
            ['限制', asStringList(limitations)],
            ['采用建议', asStringList(takeaways)],
        ].filter(([_title, items]) => items.length);
        if (!sections.length) {
            return '';
        }

        return `
            <section class="deep-band">
                <h2>采用判断</h2>
                <div class="deep-notes-grid">
                    ${sections.map(([title, items]) => `
                        <article class="deep-note-card">
                            <h3>${escapeHtml(title)}</h3>
                            <ul>${items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
                        </article>
                    `).join('')}
                </div>
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
            ${renderDecision(report.decision)}
            ${listSection('应用场景', report.use_cases)}
            ${stack.length ? `
                <section class="deep-band">
                    <h2>技术栈</h2>
                    <div class="deep-tech-list">
                        ${stack.map(item => `<span class="deep-tech-tag">${escapeHtml(item)}</span>`).join('')}
                    </div>
                </section>
            ` : ''}
            ${renderArchitectureDiagram(report.architecture)}
            ${renderFlow('快速上手', report.quick_start)}
            ${renderFlow('部署运行', report.deployment)}
            ${renderCoreModules(report.core_modules)}
            ${renderFlow('运行时数据流', { steps: report.runtime_data_flow })}
            ${renderAdoptionNotes(report.strengths, report.limitations, report.actionable_takeaways)}
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
        if (safeItem.report_version !== 2) {
            renderStatus(container, 'empty-text', '报告正在升级，请稍后查看。');
            return;
        }

        container.innerHTML = renderStructuredReport(safeItem);
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
