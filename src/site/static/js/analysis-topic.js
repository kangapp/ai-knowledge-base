(() => {
    const panel = document.getElementById('detail-panel');
    const backdrop = document.querySelector('.detail-backdrop');
    const title = document.getElementById('detail-title');
    const content = document.getElementById('detail-content');
    let trigger = null;

    function closeDetail() {
        if (!panel) return;
        panel.hidden = true;
        backdrop.hidden = true;
        document.body.style.overflow = '';
        trigger?.focus();
    }

    function openDetail(button) {
        const target = document.getElementById(button.dataset.detailTarget);
        if (!target || !panel) return;
        trigger = button;
        title.textContent = button.dataset.detailTitle || button.textContent.trim();
        content.replaceChildren(target.content?.cloneNode(true) || target.cloneNode(true));
        panel.hidden = false;
        backdrop.hidden = false;
        document.body.style.overflow = 'hidden';
        panel.querySelector('.detail-close').focus();
    }

    function enhanceDetailSections() {
        document.querySelectorAll('.topic-content h3').forEach((heading, index) => {
            const template = document.createElement('template');
            template.id = `detail-section-${index}`;
            let sibling = heading.nextElementSibling;
            while (sibling && !['H2', 'H3'].includes(sibling.tagName)) {
                template.content.append(sibling.cloneNode(true));
                sibling = sibling.nextElementSibling;
            }
            if (!template.content.childElementCount) return;
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'detail-trigger';
            button.textContent = '查看详情';
            button.dataset.detailTarget = template.id;
            button.dataset.detailTitle = heading.textContent.trim();
            heading.insertAdjacentElement('afterend', button);
            document.body.append(template);
        });
    }

    function renderMermaid() {
        if (!window.mermaid) return;
        document.querySelectorAll('pre code.language-mermaid').forEach((code) => {
            const diagram = document.createElement('div');
            diagram.className = 'mermaid';
            diagram.textContent = code.textContent;
            code.parentElement.replaceWith(diagram);
        });
        window.mermaid.initialize({ startOnLoad: false, theme: 'neutral' });
        window.mermaid.run({ querySelector: '.mermaid' });
    }

    document.addEventListener('click', (event) => {
        const opener = event.target.closest('[data-detail-target]');
        if (opener) openDetail(opener);
        if (event.target.closest('[data-detail-close]')) closeDetail();
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && panel && !panel.hidden) closeDetail();
    });
    document.querySelectorAll('[data-copy-target]').forEach((button) => {
        const target = document.getElementById(button.dataset.copyTarget);
        if (!target) return;
        const feedback = document.getElementById(button.getAttribute('aria-describedby'));
        button.hidden = false;
        button.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(target.textContent);
                feedback.textContent = '已复制。粘贴到 AI 对话中，填入你的想法即可。';
            } catch {
                target.closest('details').open = true;
                feedback.textContent = '未能自动复制，已展开提示词，请选中文字后手动复制。';
            }
        });
    });
    document.querySelectorAll('[data-spec-demo]').forEach((demo) => {
        function updatePreview() {
            const refresh = demo.querySelector('input:checked').value === 'refresh';
            demo.querySelector('[data-demo-order]').textContent = refresh
                ? '文章 A（11:00） → 文章 B（10:00）'
                : '文章 B（10:00） → 文章 A（09:00）';
            demo.querySelector('[data-demo-rule]').textContent = refresh
                ? '候选规则：再次主动收藏更新时间，同一文章仍保留一条关系。'
                : '规则：重复收藏保留原关系与时间。';
            demo.querySelector('[data-demo-check]').textContent = refresh
                ? '候选验收：新操作后 A 的时间变为 11:00，关系数量不变，A 排在 B 前面。'
                : '验收：再次收藏 A 后，关系数量、时间和排序均不变。';
            demo.querySelector('[data-demo-impact]').textContent = refresh
                ? '需要同步：重复操作正文、时间写入、接口处理、图示、排序示例和验收；排序依据仍是收藏时间倒序。'
                : '关联检查：正文、排序说明、接口处理、图示与验收均沿用原规则。';
            demo.querySelector('[data-demo-open]').textContent = refresh
                ? '待决定：同一操作的重试要保留首次时间，还是每次请求都更新时间？候选尚不能定稿。'
                : '重试：相同请求再次执行，也不改变时间。';
        }
        demo.addEventListener('change', updatePreview);
        updatePreview();
    });
    enhanceDetailSections();
    renderMermaid();
})();
