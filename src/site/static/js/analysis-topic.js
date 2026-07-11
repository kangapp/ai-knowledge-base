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
    enhanceDetailSections();
    renderMermaid();
})();
