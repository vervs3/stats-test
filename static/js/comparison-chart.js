/**
 * Comparison Chart Module - Implementation of estimate vs. time spent chart
 */
import { getChartColors, createSpecialJQL, commonChartOptions, deepCopy } from './chart-utils.js';

let comparisonChart = null;
let excludedProjects = new Set();
let fullProjectsList = [];

// Initialize and handle the comparison chart
export function initComparisonChart(chartData, originalChartData, isInitialData) {
    const ctxComparison = document.getElementById('comparisonChart');
    if (!ctxComparison || !chartData.project_estimates || !chartData.project_time_spent) {
        console.log("Comparison chart not initialized - missing element or data");
        return { updateChart: null };
    }

    console.log("Initializing comparison chart with filtering");

    // Collect all unique projects
    const allProjects = [...new Set([
        ...Object.keys(chartData.project_estimates),
        ...Object.keys(chartData.project_time_spent),
        ...(chartData.project_clm_estimates ? Object.keys(chartData.project_clm_estimates) : [])
    ])];

    if (allProjects.length === 0) {
        console.log("No projects with estimates or time spent");
        return { updateChart: null };
    }

    // Sort projects by sum of all three metrics (descending)
    allProjects.sort((a, b) => {
        const aTotal = (chartData.project_clm_estimates?.[a] || 0) +
                       (chartData.project_estimates[a] || 0) +
                       (chartData.project_time_spent[a] || 0);
        const bTotal = (chartData.project_clm_estimates?.[b] || 0) +
                       (chartData.project_estimates[b] || 0) +
                       (chartData.project_time_spent[b] || 0);
        return bTotal - aTotal;
    });

    // Save full projects list for filtering
    fullProjectsList = [...allProjects];

    // Create container for filter elements above chart
    setupFilterUI(ctxComparison, chartData);

    // Setup period toggle for CLM mode
    if (chartData.data_source === 'clm') {
        setupPeriodToggle(ctxComparison);
    }

    // Function to update chart data based on selected projects
    function updateChart() {
        // Filter projects, excluding those marked for exclusion
        const filteredProjects = fullProjectsList.filter(project => !excludedProjects.has(project));

        // Check that we have data and projects to display
        if (filteredProjects.length === 0) {
            console.warn("No projects to display after filtering");
            // Instead of leaving chart empty, show a message
            if (comparisonChart) {
                comparisonChart.destroy();
                comparisonChart = null;

                const ctx = ctxComparison.getContext('2d');
                ctx.clearRect(0, 0, ctxComparison.width, ctxComparison.height);
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.font = '16px Arial';
                ctx.fillStyle = '#666';
                ctx.fillText('Нет данных для отображения', ctxComparison.width / 2, ctxComparison.height / 2);
            }
            return;
        }

        // Limit number of projects for readability
        const displayProjects = filteredProjects.slice(0, 30);

        // Make sure we have valid data arrays
        const estimateData = displayProjects.map(project => chartData.project_estimates[project] || 0);
        const timeSpentData = displayProjects.map(project => chartData.project_time_spent[project] || 0);

        // Check data integrity
        const estimateSum = estimateData.reduce((sum, val) => sum + val, 0);
        const timeSpentSum = timeSpentData.reduce((sum, val) => sum + val, 0);
        console.log(`Chart data totals - Estimate: ${estimateSum.toFixed(2)}, Time spent: ${timeSpentSum.toFixed(2)}`);

        let needNewChart = !comparisonChart;

        // If chart already exists, update its data
        if (comparisonChart) {
            comparisonChart.data.labels = displayProjects;

            // Update data for each dataset
            let datasetIndex = 0;

            // If there are CLM estimates, update their data
            if (chartData.project_clm_estimates &&
                Object.values(chartData.project_clm_estimates).some(val => val > 0)) {

                if (datasetIndex >= comparisonChart.data.datasets.length) {
                    // Dataset missing, recreate chart
                    comparisonChart.destroy();
                    comparisonChart = null;
                    needNewChart = true;
                } else {
                    comparisonChart.data.datasets[datasetIndex].data =
                        displayProjects.map(project => chartData.project_clm_estimates[project] || 0);
                    datasetIndex++;
                }
            }

            // Check if we have enough datasets
            if (!needNewChart && datasetIndex + 1 >= comparisonChart.data.datasets.length) {
                console.warn("Not enough datasets in chart, recreating");
                comparisonChart.destroy();
                comparisonChart = null;
                needNewChart = true;
            }

            if (!needNewChart) {
                // Update original estimates
                comparisonChart.data.datasets[datasetIndex].data = estimateData;
                datasetIndex++;

                // Update time spent
                comparisonChart.data.datasets[datasetIndex].data = timeSpentData;

                // Force a full redraw
                comparisonChart.update('none');
            }
        }

        // Create new chart if needed
        if (needNewChart) {
            // Get CLM estimates data if available
            const clmEstimateData = chartData.project_clm_estimates
                ? displayProjects.map(project => chartData.project_clm_estimates[project] || 0)
                : null;

            // Create dataset array to be used for chart
            const datasets = [];

            // Add CLM estimate only if data is available
            if (clmEstimateData && clmEstimateData.some(val => val > 0)) {
                datasets.push({
                    label: 'CLM оценка (часы)',
                    data: clmEstimateData,
                    backgroundColor: 'rgba(75, 192, 192, 0.7)',  // Green
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1
                });
            }

            // Always add original estimate and time spent
            datasets.push({
                label: 'Исходная оценка (часы)',
                data: estimateData,
                backgroundColor: 'rgba(54, 162, 235, 0.7)',  // Blue
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            });

            datasets.push({
                label: 'Затраченное время (часы)',
                data: timeSpentData,
                backgroundColor: 'rgba(255, 99, 132, 0.7)',  // Red
                borderColor: 'rgba(255, 99, 132, 1)',
                borderWidth: 1
            });

            // Clear canvas before creating new chart
            if (ctxComparison.chart) {
                ctxComparison.chart.destroy();
            }

            // Force a clear
            const ctx = ctxComparison.getContext('2d');
            ctx.clearRect(0, 0, ctxComparison.width, ctxComparison.height);

            // Create new chart
            comparisonChart = new Chart(ctxComparison.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: displayProjects,
                    datasets: datasets
                },
                options: {
                    ...commonChartOptions,
                    onClick: (event, activeElements) => {
                        if (activeElements.length === 0) return;

                        const index = activeElements[0].index;
                        const project = displayProjects[index];

                        console.log(`Comparison chart click - Index: ${index}, Project: ${project}`);

                        // Use special JQL for CLM mode
                        const isClmAnalysis = !!document.querySelector('[data-source="clm"]');
                        if (isClmAnalysis) {
                            // Check selected period mode
                            const withoutPeriod = document.getElementById('withoutPeriod')?.checked || false;
                            createSpecialJQL(project, 'project_issues', withoutPeriod);
                        } else if (typeof createJiraLink === 'function') {
                            // Ensure we're passing the correct project
                            createJiraLink(project);
                        } else {
                            console.error("createJiraLink function not found");
                        }
                    }
                }
            });
        }
    }

    // Setup filter UI elements
    function setupFilterUI(ctxComparison, chartData) {
        const chartContainer = ctxComparison.closest('.chart-container');
        const filterContainer = document.createElement('div');
        filterContainer.className = 'mb-3 chart-filter-container';
        filterContainer.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <button class="btn btn-sm btn-outline-primary toggle-filter-btn">Показать/скрыть фильтр</button>
                <div class="filter-actions" style="display: none;">
                    <button class="btn btn-sm btn-outline-success select-all-btn">Выбрать все</button>
                    <button class="btn btn-sm btn-outline-danger deselect-all-btn">Снять все</button>
                    <button class="btn btn-sm btn-outline-warning reset-filter-btn">Сбросить</button>
                </div>
            </div>
            <div class="project-filter-options" style="display: none; max-height: 200px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; border-radius: 4px;">
            </div>
        `;

        if (chartContainer && chartContainer.parentNode) {
            chartContainer.parentNode.insertBefore(filterContainer, chartContainer);
        } else {
            ctxComparison.parentNode.insertBefore(filterContainer, ctxComparison);
        }

        const filterOptions = filterContainer.querySelector('.project-filter-options');

        // Populate filter options
        function populateFilterOptions() {
            filterOptions.innerHTML = ''; // Clear content

            // Create checkboxes for ALL projects
            fullProjectsList.forEach((project, index) => {
                const isExcluded = excludedProjects.has(project);
                const rowDiv = document.createElement('div');
                rowDiv.className = 'form-check';
                rowDiv.innerHTML = `
                    <input class="form-check-input project-checkbox" type="checkbox" value="${project}" id="project-${index}" ${isExcluded ? '' : 'checked'}>
                    <label class="form-check-label" for="project-${index}">${project}</label>
                `;
                filterOptions.appendChild(rowDiv);
            });

            // Add event handlers for checkboxes
            const checkboxes = filterOptions.querySelectorAll('.project-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.addEventListener('change', function() {
                    const project = this.value;
                    if (this.checked) {
                        excludedProjects.delete(project);
                    } else {
                        excludedProjects.add(project);
                    }
                    updateChart();
                });
            });
        }

        // Initialize filter options
        populateFilterOptions();

        // Setup filter buttons
        const toggleFilterBtn = filterContainer.querySelector('.toggle-filter-btn');
        const filterActions = filterContainer.querySelector('.filter-actions');
        const selectAllBtn = filterContainer.querySelector('.select-all-btn');
        const deselectAllBtn = filterContainer.querySelector('.deselect-all-btn');
        const resetFilterBtn = filterContainer.querySelector('.reset-filter-btn');

        toggleFilterBtn.addEventListener('click', function() {
            const filterOptions = filterContainer.querySelector('.project-filter-options');
            const isVisible = filterOptions.style.display !== 'none';
            filterOptions.style.display = isVisible ? 'none' : 'block';
            filterActions.style.display = isVisible ? 'none' : 'flex';
        });

        selectAllBtn.addEventListener('click', function() {
            const checkboxes = filterOptions.querySelectorAll('.project-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.checked = true;
            });
            excludedProjects.clear();
            updateChart();
        });

        deselectAllBtn.addEventListener('click', function() {
            const checkboxes = filterOptions.querySelectorAll('.project-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.checked = false;
            });
            excludedProjects = new Set(fullProjectsList);
            updateChart();
        });

        resetFilterBtn.addEventListener('click', function() {
            excludedProjects.clear();
            populateFilterOptions();
            updateChart();
        });

        return { populateFilterOptions };
    }

    // Setup period toggle UI for CLM mode
    function setupPeriodToggle(ctxComparison) {
        const chartContainer = ctxComparison.closest('.chart-container');
        const filterContainer = chartContainer.parentNode.querySelector('.chart-filter-container');

        if (filterContainer) {
            const periodToggleDiv = document.createElement('div');
            periodToggleDiv.className = 'period-toggle-container mb-3';
            periodToggleDiv.innerHTML = `
                <div class="alert alert-info py-2">
                    <small>Режим отображения данных:</small>
                    <div class="mt-1">
                        <div class="form-check form-check-inline">
                            <input class="form-check-input" type="radio" name="periodMode" id="withPeriod" value="withPeriod" checked>
                            <label class="form-check-label" for="withPeriod">
                                Данные за выбранный период
                            </label>
                        </div>
                        <div class="form-check form-check-inline">
                            <input class="form-check-input" type="radio" name="periodMode" id="withoutPeriod" value="withoutPeriod">
                            <label class="form-check-label" for="withoutPeriod">
                                Все данные CLM
                            </label>
                        </div>
                    </div>
                    <div id="period-loading" class="mt-2" style="display: none;">
                        <div class="spinner-border spinner-border-sm text-primary" role="status">
                            <span class="visually-hidden">Загрузка...</span>
                        </div>
                        <span class="ms-2">Загрузка данных...</span>
                    </div>
                </div>
            `;
            filterContainer.appendChild(periodToggleDiv);
        }
    }

    // Initialize chart with full dataset
    updateChart();

    // Return functions needed by main module
    return {
        updateChart,
        getExcludedProjects: () => excludedProjects,
        getFullProjectsList: () => fullProjectsList,
        updateFullProjectsList: (newList) => {
            fullProjectsList = newList;
        }
    };
}