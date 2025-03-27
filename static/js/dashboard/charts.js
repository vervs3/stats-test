// charts.js - Common functions for chart initialization
import { initTimeSpentChart } from './charts/timeSpentChart.js';
import { initOpenTasksChart } from './charts/openTasksChart.js';
import { initClosedTasksChart } from './charts/closedTasksChart.js';

/**
 * Initialize empty charts as placeholders
 */
function initEmptyCharts() {
    console.log("Initializing empty charts as placeholders");

    // Initialize empty time spent chart
    initTimeSpentEmptyChart();

    // Initialize empty open tasks chart
    initOpenTasksEmptyChart();

    // Initialize empty closed tasks chart
    initClosedTasksEmptyChart();
}

/**
 * Initialize empty time spent chart
 */
function initTimeSpentEmptyChart() {
    const timeSpentCanvas = document.getElementById('timeSpentChart');
    if (!timeSpentCanvas || typeof Chart === 'undefined') return;

    try {
        if (window.timeSpentChart instanceof Chart) {
            window.timeSpentChart.destroy();
        }

        window.timeSpentChart = new Chart(timeSpentCanvas, {
            type: 'line',
            data: {
                labels: ['2025-03-01', '2025-03-15', '2025-03-30'],
                datasets: [{
                    label: 'Загрузка данных...',
                    data: [800, 850, 900],
                    borderColor: 'rgba(200, 200, 200, 0.5)',
                    backgroundColor: 'rgba(200, 200, 200, 0.1)',
                    borderDash: [5, 5]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    } catch (error) {
        console.error("Failed to create empty time spent chart:", error);
    }
}

/**
 * Initialize empty open tasks chart
 */
function initOpenTasksEmptyChart() {
    const openTasksCanvas = document.getElementById('openTasksChart');
    if (!openTasksCanvas || typeof Chart === 'undefined') return;

    try {
        if (window.openTasksChart instanceof Chart) {
            window.openTasksChart.destroy();
        }

        window.openTasksChart = new Chart(openTasksCanvas, {
            type: 'bar',
            data: {
                labels: ['Загрузка...'],
                datasets: [{
                    label: 'Загрузка данных...',
                    data: [50],
                    backgroundColor: 'rgba(200, 200, 200, 0.5)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    } catch (error) {
        console.error("Failed to create empty open tasks chart:", error);
    }
}

/**
 * Initialize empty closed tasks chart
 */
function initClosedTasksEmptyChart() {
    const closedTasksCanvas = document.getElementById('closedTasksChart');
    if (!closedTasksCanvas || typeof Chart === 'undefined') return;

    try {
        if (window.closedTasksChart instanceof Chart) {
            window.closedTasksChart.destroy();
        }

        window.closedTasksChart = new Chart(closedTasksCanvas, {
            type: 'bar',
            data: {
                labels: ['Загрузка...'],
                datasets: [{
                    label: 'Загрузка данных...',
                    data: [50],
                    backgroundColor: 'rgba(200, 200, 200, 0.5)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    } catch (error) {
        console.error("Failed to create empty closed tasks chart:", error);
    }
}

/**
 * Update all dashboard charts with real data
 * @param {Object} data - Dashboard data
 */
function updateDashboardCharts(data) {
    // Update time spent chart
    if (data.time_series && data.time_series.dates && data.time_series.dates.length > 0) {
        initTimeSpentChart(data.time_series);
    }

    // Update open tasks chart
    if (data.open_tasks_data && Object.keys(data.open_tasks_data).length > 0) {
        initOpenTasksChart(data.open_tasks_data, data.latest_timestamp || '');
    }

    // Update closed tasks chart
    if (data.closed_tasks_data && Object.keys(data.closed_tasks_data).length > 0) {
        initClosedTasksChart(data.closed_tasks_data, data.latest_timestamp || '');
    }
}

export { initEmptyCharts, updateDashboardCharts };