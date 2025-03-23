/**
 * Projects Pie Chart Module - Distribution of tasks by project
 * With forced visual update on data change
 */
import { getChartColors, createSpecialJQL } from './chart-utils.js';

let pieChart = null;
let currentProjectCounts = {}; // Store the current project counts
let chartCanvas = null;

// Initialize the projects pie chart
export function initProjectsPieChart(initialChartData) {
    // Initialize current project counts
    if (initialChartData && initialChartData.project_counts) {
        currentProjectCounts = {...initialChartData.project_counts};
    }

    chartCanvas = document.getElementById('projectsPieChart');
    if (!chartCanvas || !initialChartData.project_counts || Object.keys(initialChartData.project_counts).length === 0) {
        console.log("Projects pie chart not initialized - missing element or data");
        return { recreateChart: null };
    }

    console.log("Initializing projects pie chart");

    // Add period toggle for CLM mode
    if (initialChartData.data_source === 'clm') {
        setupPieChartToggle(chartCanvas);
    }

    // Function to explicitly recreate the pie chart with current data
    function recreatePieChart(updatedChartData) {
        console.log("FORCE RECREATING PIE CHART", updatedChartData ? "with new data" : "with current data");

        // Update current project counts if new data is provided
        if (updatedChartData && updatedChartData.project_counts) {
            console.log("PIE CHART: Updating with new project counts:", {
                old_count: Object.keys(currentProjectCounts).length,
                new_count: Object.keys(updatedChartData.project_counts).length,
                old_total: Object.values(currentProjectCounts).reduce((a, b) => a + b, 0),
                new_total: Object.values(updatedChartData.project_counts).reduce((a, b) => a + b, 0)
            });

            // Print first few old and new projects for comparison
            const oldProjects = Object.entries(currentProjectCounts).sort((a, b) => b[1] - a[1]).slice(0, 3);
            const newProjects = Object.entries(updatedChartData.project_counts).sort((a, b) => b[1] - a[1]).slice(0, 3);
            console.log("OLD TOP PROJECTS:", JSON.stringify(oldProjects));
            console.log("NEW TOP PROJECTS:", JSON.stringify(newProjects));

            // Completely replace the project counts
            currentProjectCounts = {...updatedChartData.project_counts};
        }

        // Always destroy the existing chart
        if (pieChart) {
            console.log("Destroying existing pie chart");
            pieChart.destroy();
            pieChart = null;
        }

        // Check that we have data to work with
        if (Object.keys(currentProjectCounts).length === 0) {
            console.warn("No project_counts data available for pie chart");
            return;
        }

        // FORCE RECREATE: Completely replace the canvas element
        const parent = chartCanvas.parentNode;
        const oldCanvas = chartCanvas;

        // Create a new canvas with the same ID and class
        const newCanvas = document.createElement('canvas');
        newCanvas.id = oldCanvas.id;
        newCanvas.className = oldCanvas.className;

        // Replace the old canvas with the new one
        parent.replaceChild(newCanvas, oldCanvas);

        // Update the reference
        chartCanvas = newCanvas;

        // Sort projects by count (descending)
        const sortedProjects = Object.entries(currentProjectCounts)
            .sort((a, b) => b[1] - a[1]);

        console.log(`PIE CHART: Creating with ${sortedProjects.length} projects, total count: ${
            sortedProjects.reduce((sum, [_, count]) => sum + count, 0)}`);

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

        // Calculate total for logging
        const totalTasks = values.reduce((sum, val) => sum + val, 0);
        console.log(`PIE CHART: Total tasks: ${totalTasks}, segments: ${values.length}`);
        console.log(`PIE CHART: Values: ${JSON.stringify(values.slice(0, 5))}...`);

        // Create colors
        const pieColors = getChartColors(labels.length);

        // Create new chart
        pieChart = new Chart(chartCanvas.getContext('2d'), {
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
                                const withoutPeriod = document.getElementById('pieWithoutPeriod')?.checked || false;
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

        console.log("PIE CHART: Successfully recreated");
    }

    // Setup toggle UI for CLM mode
    function setupPieChartToggle(chartCanvas) {
        const chartContainer = chartCanvas.closest('.chart-container');
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
        const chartCard = chartCanvas.closest('.card');
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