/**
 * Open Tasks Chart Module (formerly "No Transitions Tasks")
 * Shows open tasks with work logs
 */
import { getChartColors, commonChartOptions, handleChartClick } from './chart-utils.js';

// Initialize the open tasks chart
export function initOpenTasksChart(chartData) {
    const ctxNoTrans = document.getElementById('noTransitionsChart');
    if (!ctxNoTrans || !chartData.special_charts || !chartData.special_charts.no_transitions) {
        console.log("Open tasks chart not initialized - missing element or data");
        return;
    }

    console.log("Initializing Open Tasks Chart (formerly 'No Transitions Tasks')");

    const noTransData = chartData.special_charts.no_transitions;
    const noTransLabels = Object.keys(noTransData.by_project || {});

    // Only create the chart if we have data
    if (noTransLabels.length === 0) {
        console.log("Open tasks chart has no data");
        return;
    }

    const noTransValues = noTransLabels.map(project => noTransData.by_project[project] || 0);
    const noTransColors = getChartColors(noTransLabels.length);

    try {
        const noTransChart = new Chart(ctxNoTrans.getContext('2d'), {
            type: 'bar',
            data: {
                labels: noTransLabels,
                datasets: [{
                    label: 'Количество задач',
                    data: noTransValues,
                    backgroundColor: noTransColors,
                    borderColor: noTransColors.map(color => color.replace('0.7', '1')),
                    borderWidth: 1
                }]
            },
            options: {
                ...commonChartOptions,
                onClick: (event, activeElements) => {
                    handleChartClick(event, 'no_transitions', activeElements, noTransChart);
                }
            }
        });
    } catch (err) {
        console.error("Error creating open tasks chart:", err);
    }
}