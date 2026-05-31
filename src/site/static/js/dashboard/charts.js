(function() {
    const charts = {};

    function canvas(id) {
        return document.getElementById(id);
    }

    function replace(id, config) {
        const ctx = canvas(id);
        if (!ctx || !window.Chart) return;
        if (charts[id]) charts[id].destroy();
        charts[id] = new Chart(ctx, config);
    }

    const defaults = {
        responsive: true,
        maintainAspectRatio: false,
    };

    window.DashboardCharts = {
        bar(id, labels, data, color) {
            replace(id, {
                type: 'bar',
                data: { labels, datasets: [{ data, backgroundColor: color }] },
                options: { ...defaults, plugins: { legend: { display: false } } },
            });
        },
        horizontalBar(id, labels, data, color) {
            replace(id, {
                type: 'bar',
                data: { labels, datasets: [{ data, backgroundColor: color }] },
                options: {
                    ...defaults,
                    indexAxis: 'y',
                    scales: { x: { min: 0, max: 100 } },
                    plugins: { legend: { display: false } },
                },
            });
        },
        line(id, labels, data, color) {
            replace(id, {
                type: 'line',
                data: {
                    labels,
                    datasets: [{
                        data,
                        borderColor: color,
                        backgroundColor: `${color}20`,
                        fill: true,
                        tension: 0.3,
                    }],
                },
                options: { ...defaults, plugins: { legend: { display: false } } },
            });
        },
        radar(id, labels, data) {
            replace(id, {
                type: 'radar',
                data: {
                    labels,
                    datasets: [{
                        data,
                        backgroundColor: 'rgba(79,70,229,0.25)',
                        borderColor: '#4F46E5',
                        borderWidth: 2,
                    }],
                },
                options: {
                    ...defaults,
                    scales: { r: { min: 0, max: 100 } },
                    plugins: { legend: { display: false } },
                },
            });
        },
        stackedBar(id, labels, datasets, indexAxis) {
            replace(id, {
                type: 'bar',
                data: { labels, datasets },
                options: {
                    ...defaults,
                    indexAxis: indexAxis || 'x',
                    scales: { x: { stacked: true }, y: { stacked: true } },
                },
            });
        },
        groupedBar(id, labels, datasets) {
            replace(id, {
                type: 'bar',
                data: { labels, datasets },
                options: defaults,
            });
        },
    };
})();
