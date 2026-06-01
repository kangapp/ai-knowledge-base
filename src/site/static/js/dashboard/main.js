(function() {
    async function loadCached(scope, loader) {
        const cached = DashboardState.getCached(scope);
        if (cached) return cached;
        const data = await loader();
        DashboardState.setCached(scope, data);
        return data;
    }

    async function renderCurrent() {
        DashboardRenderers.showError('');
        const period = DashboardState.period;
        const days = DashboardState.currentDays;
        const label = DashboardState.currentLabel;

        try {
            const summary = await loadCached('summary', () => DashboardApi.loadSummary(days));
            DashboardRenderers.renderSummary(summary, label);

            if (DashboardState.activeTab === 'quality') {
                const data = await loadCached('quality', () => DashboardApi.loadQuality(period));
                DashboardRenderers.renderQuality(data, label);
            } else if (DashboardState.activeTab === 'consumption') {
                const data = await loadCached('consumption', () => DashboardApi.loadConsumption(period, DashboardState.currentTrendWindow));
                DashboardRenderers.renderConsumption(data);
            } else if (DashboardState.activeTab === 'sources') {
                const data = await loadCached('sources', () => DashboardApi.loadSources(period));
                DashboardRenderers.renderSources(data);
            }
        } catch (error) {
            DashboardRenderers.showError(error.message || '仪表盘加载失败');
        }
    }

    function switchTab(tab) {
        DashboardState.setTab(tab);
        document.querySelectorAll('.tab').forEach(item => item.classList.toggle('active', item.dataset.tab === tab));
        document.querySelectorAll('.tab-content').forEach(item => item.classList.toggle('active', item.id === `tab-${tab}`));
        renderCurrent();
    }

    function switchPeriod(period) {
        DashboardState.setPeriod(period);
        DashboardState.clearCache();
        document.querySelectorAll('#global-date-filters .date-btn').forEach(item => item.classList.toggle('active', item.dataset.period === period));
        renderCurrent();
    }

    document.addEventListener('DOMContentLoaded', () => {
        if (!document.querySelector('.dashboard-page')) return;
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => switchTab(tab.dataset.tab));
        });
        document.querySelectorAll('#global-date-filters .date-btn').forEach(button => {
            button.addEventListener('click', () => switchPeriod(button.dataset.period));
        });
        renderCurrent();
    });
})();
