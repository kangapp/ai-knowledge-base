(function() {
    async function requestJson(url) {
        const response = await fetch(url);
        const payload = await response.json();
        if (!response.ok || payload.code !== 0) {
            throw new Error(payload.message || '请求失败');
        }
        return payload.data;
    }

    window.DashboardApi = {
        loadSummary(days) {
            return requestJson(`/api/dashboard/summary?days=${days}`);
        },
        loadQuality(period) {
            return requestJson(`/api/stats/quality-detail?period=${period}`);
        },
        loadConsumption(period) {
            return requestJson(`/api/stats/consumption-detail?period=${period}`);
        },
        loadSources(period) {
            return requestJson(`/api/sources/stats?period=${period}`);
        },
    };
})();
