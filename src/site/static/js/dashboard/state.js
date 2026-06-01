(function() {
    const periods = {
        day: { days: 1, label: '今日', trendWindow: '14d' },
        week: { days: 7, label: '近 7 天', trendWindow: '12w' },
        month: { days: 30, label: '近 30 天', trendWindow: '12m' },
    };

    const state = {
        activeTab: 'quality',
        period: 'week',
        cache: {},
    };

    function cacheKey(scope) {
        return `${scope}:${state.period}`;
    }

    window.DashboardState = {
        periods,
        get activeTab() {
            return state.activeTab;
        },
        get period() {
            return state.period;
        },
        get currentDays() {
            return periods[state.period].days;
        },
        get currentLabel() {
            return periods[state.period].label;
        },
        get currentTrendWindow() {
            return periods[state.period].trendWindow;
        },
        setTab(tab) {
            state.activeTab = tab;
        },
        setPeriod(period) {
            state.period = periods[period] ? period : 'week';
        },
        getCached(scope) {
            return state.cache[cacheKey(scope)];
        },
        setCached(scope, data) {
            state.cache[cacheKey(scope)] = data;
        },
        clearCache() {
            state.cache = {};
        },
    };
})();
