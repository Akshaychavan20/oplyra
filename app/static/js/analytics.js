document.addEventListener("DOMContentLoaded", function() {
    let rawData = null;
    let activityChartInstance = null;
    let tokensChartInstance = null;
    let contentTypeChartInstance = null;

    function getTheme() {
        if (window.OplyraTheme && typeof window.OplyraTheme.getChartTheme === 'function') {
            return window.OplyraTheme.getChartTheme();
        }
        var isLight = document.documentElement.getAttribute('data-theme') === 'light';
        return {
            isLight: isLight,
            fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
            tick: isLight ? 'hsl(224, 12%, 48%)' : 'hsl(215, 13%, 45%)',
            legend: isLight ? 'hsl(224, 20%, 32%)' : 'hsl(215, 15%, 72%)',
            grid: isLight ? 'hsla(224, 15%, 20%, 0.08)' : 'hsla(148, 163, 184, 0.08)',
            tooltipBg: isLight ? 'hsla(0, 0%, 100%, 0.98)' : 'hsla(224, 25%, 4%, 0.92)',
            tooltipTitle: isLight ? 'hsl(224, 25%, 12%)' : 'hsl(0, 0%, 100%)',
            tooltipBody: isLight ? 'hsl(224, 20%, 32%)' : 'hsl(215, 20%, 84%)',
            pointBorder: isLight ? 'hsl(210, 40%, 98%)' : 'hsl(224, 25%, 4%)'
        };
    }

    function chartFont(theme, size, weight) {
        var font = { family: theme.fontFamily || 'Inter, sans-serif', size: size };
        if (weight) font.weight = weight;
        return font;
    }

    function getCommonChartOptions(glowColor, isBar) {
        var theme = getTheme();
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: theme.tooltipBg,
                    titleColor: theme.tooltipTitle,
                    bodyColor: theme.tooltipBody,
                    borderColor: glowColor,
                    borderWidth: 1,
                    padding: 10,
                    titleFont: chartFont(theme, 12, 600),
                    bodyFont: chartFont(theme, 12)
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        color: theme.tick,
                        font: chartFont(theme, 11)
                    }
                },
                y: {
                    grid: { color: theme.grid },
                    ticks: {
                        color: theme.tick,
                        font: chartFont(theme, 11),
                        beginAtZero: true,
                        precision: 0
                    }
                }
            }
        };
    }

    function applyThemeToCharts() {
        var theme = getTheme();

        if (contentTypeChartInstance) {
            contentTypeChartInstance.options.plugins.legend.labels.color = theme.legend;
            contentTypeChartInstance.options.plugins.tooltip.backgroundColor = theme.tooltipBg;
            contentTypeChartInstance.options.plugins.tooltip.titleColor = theme.tooltipTitle;
            contentTypeChartInstance.options.plugins.tooltip.bodyColor = theme.tooltipBody;
            contentTypeChartInstance.update('none');
        }

        [activityChartInstance, tokensChartInstance].forEach(function(chart) {
            if (!chart) return;
            chart.options.plugins.tooltip.backgroundColor = theme.tooltipBg;
            chart.options.plugins.tooltip.titleColor = theme.tooltipTitle;
            chart.options.plugins.tooltip.bodyColor = theme.tooltipBody;
            chart.options.scales.x.ticks.color = theme.tick;
            chart.options.scales.y.ticks.color = theme.tick;
            chart.options.scales.y.grid.color = theme.grid;
            chart.update('none');
        });
    }

    function initCharts(data) {
        var theme = getTheme();
        var typeCtx = document.getElementById('contentTypeChart');
        if (!typeCtx) return;
        typeCtx = typeCtx.getContext('2d');

        var typeDistribution = data.content_type_distribution;
        var totalGenerated = data.total_contents;
        var doughnutLabels = ['Blog Posts', 'Emails', 'Facebook Posts', 'Product Reviews'];
        var doughnutData = [
            typeDistribution.blog || 0,
            typeDistribution.email || 0,
            typeDistribution.facebook_post || 0,
            typeDistribution.product_review || 0
        ];

        contentTypeChartInstance = new Chart(typeCtx, {
            type: 'doughnut',
            data: {
                labels: doughnutLabels,
                datasets: [{
                    data: doughnutData,
                    backgroundColor: [
                        'rgba(99, 102, 241, 0.75)',
                        'rgba(20, 184, 166, 0.75)',
                        'rgba(6, 182, 212, 0.75)',
                        'rgba(168, 85, 247, 0.75)'
                    ],
                    borderColor: [
                        'rgba(99, 102, 241, 1)',
                        'rgba(20, 184, 166, 1)',
                        'rgba(6, 182, 212, 1)',
                        'rgba(168, 85, 247, 1)'
                    ],
                    borderWidth: 2,
                    hoverOffset: 12
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: theme.legend,
                            font: chartFont(theme, 12, 600),
                            padding: 15
                        }
                    },
                    tooltip: {
                        backgroundColor: theme.tooltipBg,
                        titleColor: theme.tooltipTitle,
                        bodyColor: theme.tooltipBody,
                        borderColor: 'rgba(99, 102, 241, 0.3)',
                        borderWidth: 1,
                        padding: 10,
                        displayColors: true,
                        callbacks: {
                            label: function(context) {
                                var val = context.raw;
                                var pct = totalGenerated > 0 ? ((val / totalGenerated) * 100).toFixed(1) : 0;
                                return ' ' + context.label + ': ' + val + ' (' + pct + '%)';
                            }
                        }
                    }
                },
                cutout: '68%'
            }
        });

        var activityEl = document.getElementById('activityChart');
        if (activityEl) {
            activityChartInstance = new Chart(activityEl.getContext('2d'), {
                type: 'line',
                data: {
                    labels: data.weekly_activity.labels,
                    datasets: [{
                        label: 'Assets Generated',
                        data: data.weekly_activity.counts,
                        fill: true,
                        backgroundColor: 'rgba(20, 184, 166, 0.12)',
                        borderColor: 'rgba(20, 184, 166, 1)',
                        borderWidth: 3,
                        tension: 0.35,
                        pointBackgroundColor: 'rgba(20, 184, 166, 1)',
                        pointBorderColor: theme.pointBorder,
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }]
                },
                options: getCommonChartOptions('rgba(20, 184, 166, 1)')
            });
        }

        var tokensEl = document.getElementById('tokensChart');
        if (tokensEl) {
            tokensChartInstance = new Chart(tokensEl.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: data.weekly_token_usage.labels,
                    datasets: [{
                        label: 'Tokens Consumed',
                        data: data.weekly_token_usage.tokens,
                        backgroundColor: 'rgba(99, 102, 241, 0.75)',
                        borderColor: 'rgba(99, 102, 241, 1)',
                        borderWidth: 2,
                        borderRadius: 5,
                        borderSkipped: false
                    }]
                },
                options: getCommonChartOptions('rgba(99, 102, 241, 1)', true)
            });
        }
    }

    fetch('/api/analytics/dashboard')
        .then(function(response) { return response.json(); })
        .then(function(data) {
            rawData = data;
            initCharts(data);
            setupEventListeners();
        })
        .catch(function(error) {
            console.error("Error fetching analytics data:", error);
        });

    window.addEventListener('oplyra:themechange', applyThemeToCharts);

    function setupEventListeners() {
        var btnWeekly = document.getElementById('analyticsBtnWeekly');
        var btnMonthly = document.getElementById('analyticsBtnMonthly');

        if (btnWeekly) {
            btnWeekly.addEventListener('click', function() {
                if (this.classList.contains('active')) return;
                btnWeekly.classList.add('active');
                if (btnMonthly) btnMonthly.classList.remove('active');
                if (activityChartInstance && rawData) {
                    activityChartInstance.data.labels = rawData.weekly_activity.labels;
                    activityChartInstance.data.datasets[0].data = rawData.weekly_activity.counts;
                    activityChartInstance.update();
                }
                if (tokensChartInstance && rawData) {
                    tokensChartInstance.data.labels = rawData.weekly_token_usage.labels;
                    tokensChartInstance.data.datasets[0].data = rawData.weekly_token_usage.tokens;
                    tokensChartInstance.update();
                }
            });
        }

        if (btnMonthly) {
            btnMonthly.addEventListener('click', function() {
                if (this.classList.contains('active')) return;
                btnMonthly.classList.add('active');
                if (btnWeekly) btnWeekly.classList.remove('active');
                if (activityChartInstance && rawData) {
                    activityChartInstance.data.labels = rawData.monthly_activity.labels;
                    activityChartInstance.data.datasets[0].data = rawData.monthly_activity.counts;
                    activityChartInstance.update();
                }
                if (tokensChartInstance && rawData) {
                    tokensChartInstance.data.labels = rawData.monthly_token_usage.labels;
                    tokensChartInstance.data.datasets[0].data = rawData.monthly_token_usage.tokens;
                    tokensChartInstance.update();
                }
            });
        }
    }
});
