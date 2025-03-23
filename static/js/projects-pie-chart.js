/**
 * Projects Pie Chart Module - Distribution of tasks by project
 */
import { getChartColors, createSpecialJQL } from './chart-utils.js';

let pieChart = null;

// Initialize the projects pie chart
export function initProjectsPieChart(chartData) {
    const ctxProjectsPie = document.getElementById('projectsPieChart');
    if (!ctxProjectsPie || !chartData.project_counts || Object.keys(chartData.project_counts).length === 0) {
        console.log("Projects pie chart not initialized - missing element or data");
        return { recreateChart: null };
    }

    console.log("Initializing projects pie chart");

    // Add period toggle for CLM mode
    if (chartData.data_source === 'clm') {
        setupPieChartToggle(ctxProjectsPie);
    }

    // Function to explicitly recreate the pie chart with current data
    function recreatePieChart() {
        console.log("Explicitly recreating pie chart with current data");

        // Always destroy the existing chart to prevent stale data
        if (pieChart) {
            console.log("Destroying existing pie chart");
            pieChart.destroy();
            pieChart = null;
        }

        // Check that we have data to work with
        if (!chartData || !chartData.project_counts || Object.keys(chartData.project_counts).length === 0) {
            console.warn("No project_counts data available for pie chart");
            return;
        }

        console.log("Creating pie chart with data:", {
            project_counts_length: Object.keys(chartData.project_counts).length,
            sample: Object.entries(chartData.project_counts).slice(0, 3)
        });

        // Sort projects by count (descending)
        const sortedProjects = Object.entries(chartData.project_counts)
            .sort((a, b) => b[1] - a[1]);

        // Take top-20 projects, group the rest as "Others"
        const TOP_PROJECTS = 20;
        const topProjects = sortedProjects.slice(0, TOP_PROJECTS);
        const otherProjects = sortedProjects.slice(TOP_PROJECTS);

        // Create arrays for labels and values
        let labels = topProjects.map(item => item[0]);
        let values = topProjects.map(item => item[1]);

        // Add "Others" category if needed
        if (otherProjects.length > 0) {
            const otherValue = otherProjects.reduce((sum, item) => sum + item[1], 0);
            labels.push('Другие');
            values.push(otherValue);
        }

        // Create colors
        const pieColors = getChartColors(labels.length);

        // Clear the canvas
        const ctx = ctxProjectsPie.getContext('2d');
        ctx.clearRect(0, 0, ctxProjectsPie.width, ctxProjectsPie.height);

        // Create new chart
        pieChart = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: pieColors,
                    borderColor: pieColors.map(color => color.replace('0.7', '1')),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            boxWidth: 15,
                            padding: 10
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
                                return `${label}: ${value} задач (${percentage}%)`;
                            }
                        }
                    }
                },
                onClick: (event, activeElements) => {
                    if (activeElements.length > 0) {
                        const index = activeElements[0].index;
                        const project = labels[index];

                        if (project !== 'Другие') {
                            const isClmAnalysis = !!document.querySelector('[data-source="clm"]');
                            if (isClmAnalysis) {
                                const withoutPeriod = document.getElementById('withoutPeriod')?.checked || false;
                                createSpecialJQL(project, 'project_issues', withoutPeriod);
                            } else if (typeof createJiraLink === 'function') {
                                createJiraLink(project);
                            }
                        } else {
                            console.log("Clicked on 'Others' category - no action");
                        }
                    }
                }
            }
        });

        console.log("Pie chart successfully recreated");
    }

    // Setup toggle UI for CLM mode
    function setupPieChartToggle(ctxProjectsPie) {
        const chartContainer = ctxProjectsPie.closest('.chart-container');
        if (chartContainer) {
            const periodToggleDiv = document.createElement('div');
            periodToggleDiv.className = 'period-toggle-container pie-period-toggle-container mb-3';
            periodToggleDiv.innerHTML = `
                <div class="alert alert-info py-2">
                    <small>Режим отображения данных:</small>
                    <div class="mt-1">
                        <div class="form-check form-check-inline">
                            <input class="form-check-input" type="radio" name="piePeriodMode" id="pieWithPeriod" value="withPeriod" checked>
                            <label class="form-check-label" for="pieWithPeriod">
                                Данные за выбранный период
                            </label>
                        </div>
                        <div class="form-check form-check-inline">
                            <input class="form-check-input" type="radio" name="piePeriodMode" id="pieWithoutPeriod" value="withoutPeriod">
                            <label class="form-check-label" for="pieWithoutPeriod">
                                Все данные CLM
                            </label>
                        </div>
                    </div>
                    <div id="pie-period-loading" class="mt-2" style="display: none;">
                        <div class="spinner-border spinner-border-sm text-primary" role="status">
                            <span class="visually-hidden">Загрузка...</span>
                        </div>
                        <span class="ms-2">Загрузка данных...</span>
                    </div>
                </div>
            `;

            // Insert the toggle before the chart
            chartContainer.parentNode.insertBefore(periodToggleDiv, chartContainer);
        }

        // Add indicator to chart header
        const chartCard = ctxProjectsPie.closest('.card');
        if (chartCard) {
            const cardHeader = chartCard.querySelector('.card-header');
            if (cardHeader) {
                // Check if indicator already exists
                if (!cardHeader.querySelector('#pie-data-mode-indicator')) {
                    const indicator = document.createElement('span');
                    indicator.id = 'pie-data-mode-indicator';
                    indicator.className = 'badge bg-info';
                    indicator.textContent = 'Данные за период';

                    // Create container for title and indicator
                    const headerContainer = document.createElement('div');
                    headerContainer.className = 'd-flex justify-content-between align-items-center w-100';

                    // Move existing content
                    const existingContent = cardHeader.innerHTML;
                    headerContainer.innerHTML = `<h4>${existingContent}</h4>`;
                    headerContainer.appendChild(indicator);

                    // Update header
                    cardHeader.innerHTML = '';
                    cardHeader.appendChild(headerContainer);
                }
            }
        }
    }

    // Create the initial pie chart
    recreatePieChart();

    // Return functions needed by main module
    return {
        recreateChart: recreatePieChart
    };
}