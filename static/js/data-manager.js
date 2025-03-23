/**
 * Data Manager Module - Handles loading and state of chart data
 */
import { deepCopy } from './chart-utils.js';

// Track if we're using initial data
let isInitialData = true;

// Store original data for toggling between modes
const originalChartData = {
    project_estimates: {},
    project_time_spent: {},
    project_clm_estimates: {},
    project_counts: {},
    filtered_project_estimates: {},
    filtered_project_time_spent: {},
    projects: [],
    projectOrder: []
};

// Load chart data from the page
export function loadChartData() {
    const chartDataElement = document.getElementById('chart-data');
    if (!chartDataElement) {
        console.log("No chart data element found");
        return null;
    }

    try {
        const chartData = JSON.parse(chartDataElement.textContent);
        if (!chartData) {
            console.log("Chart data element exists but no data found");
            return null;
        }

        console.log("Chart data loaded successfully");

        // If CLM mode, make a backup of the original data
        if (chartData.data_source === 'clm') {
            originalChartData.project_estimates = deepCopy(chartData.project_estimates);
            originalChartData.project_time_spent = deepCopy(chartData.project_time_spent);
            originalChartData.project_counts = deepCopy(chartData.project_counts);

            if (chartData.project_clm_estimates) {
                originalChartData.project_clm_estimates = deepCopy(chartData.project_clm_estimates);
            }

            console.log("Original data saved for CLM mode");
        }

        return chartData;
    } catch (error) {
        console.error("Error loading chart data:", error);
        return null;
    }
}

// Handle data mode change (CLM mode)
export function loadFullClmData(chartData, timestamp, callbacks) {
    if (!isInitialData) {
        console.log("Already using full data");
        return;
    }

    console.log("Loading full CLM data...");
    const loadingIndicator = document.getElementById('period-loading');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'block';
    }

    // Update indicator
    const dataModeIndicator = document.getElementById('data-mode-indicator');
    if (dataModeIndicator) {
        dataModeIndicator.textContent = 'Все данные CLM';
    }
    const pieIndicator = document.getElementById('pie-data-mode-indicator');
    if (pieIndicator) {
        pieIndicator.textContent = 'Все данные CLM';
    }

    fetch(`/api/clm-chart-data/${timestamp}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(fullData => {
            if (!fullData.success) {
                throw new Error(fullData.error || 'Failed to get full data');
            }

            // Switch flag - now using full data
            isInitialData = false;

            // Store filtered data for later restoration
            originalChartData.filtered_project_estimates = deepCopy(chartData.project_estimates);
            originalChartData.filtered_project_time_spent = deepCopy(chartData.project_time_spent);
            originalChartData.projectOrder = callbacks.getFullProjectsList ? [...callbacks.getFullProjectsList()] : [];

            // Take first 5 common projects and show the difference
            const commonProjects = Object.keys(fullData.project_estimates)
                .filter(p => p in fullData.filtered_project_estimates)
                .slice(0, 5);

            console.log("Data comparison examples (first 5 common projects):");
            commonProjects.forEach(project => {
                const fullEst = fullData.project_estimates[project] || 0;
                const filteredEst = fullData.filtered_project_estimates[project] || 0;
                const fullSpent = fullData.project_time_spent[project] || 0;
                const filteredSpent = fullData.filtered_project_time_spent[project] || 0;

                console.log(`Project ${project}:
                    Full data: Estimate=${fullEst}, Spent=${fullSpent}
                    Filtered: Estimate=${filteredEst}, Spent=${filteredSpent}
                    Differences: Estimate=${fullEst - filteredEst}, Spent=${fullSpent - filteredSpent}`);
            });

            // Update chart data with full implementation issues data
            chartData.project_estimates = fullData.project_estimates;
            chartData.project_time_spent = fullData.project_time_spent;

            if (fullData.project_clm_estimates) {
                chartData.project_clm_estimates = fullData.project_clm_estimates;
                originalChartData.project_clm_estimates = deepCopy(fullData.project_clm_estimates);
            }

            // Create new project counts based on implementation issues
            if (fullData.implementation_count > 0) {
                let newProjectCounts = {};

                // Try to use project_issue_mapping if available
                if (chartData.project_issue_mapping) {
                    Object.keys(chartData.project_issue_mapping).forEach(project => {
                        const count = chartData.project_issue_mapping[project].length;
                        if (count > 0) {
                            newProjectCounts[project] = count;
                        }
                    });
                } else {
                    // Fallback to approximation based on estimates
                    newProjectCounts = Object.keys(fullData.project_estimates).reduce((acc, project) => {
                        if (fullData.project_estimates[project] > 0) {
                            acc[project] = Math.max(1, Math.round(fullData.project_estimates[project] / 8));
                        }
                        return acc;
                    }, {});
                }

                // Save original counts for restoration
                originalChartData.project_counts_filtered = deepCopy(chartData.project_counts);

                // Update counts
                chartData.project_counts = newProjectCounts;
                console.log("Updated project_counts for full data mode",
                            Object.keys(newProjectCounts).length, "projects");
            }

            // Update project order based on new data
            if (callbacks.updateFullProjectsList) {
                // Get all unique projects from both datasets
                const newUniqueProjects = [...new Set([
                    ...Object.keys(fullData.project_estimates),
                    ...Object.keys(fullData.project_time_spent),
                    ...(fullData.project_clm_estimates ? Object.keys(fullData.project_clm_estimates) : [])
                ])];

                const newProjectsSet = new Set(newUniqueProjects);
                const currentProjects = callbacks.getFullProjectsList ? callbacks.getFullProjectsList() : [];

                // Start with existing projects that exist in the new data
                const orderedProjects = currentProjects.filter(p => newProjectsSet.has(p));

                // Add any new projects that weren't in the original list
                newUniqueProjects.forEach(p => {
                    if (!orderedProjects.includes(p)) {
                        orderedProjects.push(p);
                    }
                });

                // Update the projects list
                callbacks.updateFullProjectsList(orderedProjects);
            }

            // Update charts with new data
            if (callbacks.updateChart) {
                callbacks.updateChart();
            }
            if (callbacks.recreatePieChart) {
                setTimeout(() => callbacks.recreatePieChart(), 200);
            }

            console.log("Data updated to full implementation data:",
                Object.keys(chartData.project_estimates).length,
                "projects in estimates,",
                Object.keys(chartData.project_time_spent).length,
                "projects in time spent");

            // Hide loading indicator
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
        })
        .catch(error => {
            console.error('Error loading full data:', error);
            alert('Ошибка при загрузке полных данных: ' + error.message);

            // Switch back to original mode
            document.getElementById('withPeriod').checked = true;
            document.getElementById('pieWithPeriod').checked = true;

            if (dataModeIndicator) {
                dataModeIndicator.textContent = 'Данные за период';
            }
            if (pieIndicator) {
                pieIndicator.textContent = 'Данные за период';
            }

            // Hide loading indicator
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
        });
}

// Restore filtered data (CLM mode)
export function restoreFilteredData(chartData, callbacks) {
    if (isInitialData) {
        console.log("Already using filtered data");
        return;
    }

    console.log("Restoring filtered worklog data");
    const loadingIndicator = document.getElementById('period-loading');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'block';
    }

    // Update indicators
    const dataModeIndicator = document.getElementById('data-mode-indicator');
    if (dataModeIndicator) {
        dataModeIndicator.textContent = 'Данные за период';
    }
    const pieIndicator = document.getElementById('pie-data-mode-indicator');
    if (pieIndicator) {
        pieIndicator.textContent = 'Данные за период';
    }

    // Restore the data
    if (originalChartData.filtered_project_estimates &&
        Object.keys(originalChartData.filtered_project_estimates).length > 0) {
        // If we have explicit filtered data saved, use it
        chartData.project_estimates = deepCopy(originalChartData.filtered_project_estimates);
        chartData.project_time_spent = deepCopy(originalChartData.filtered_project_time_spent);
        console.log("Using explicitly saved filtered data");
    } else {
        // Otherwise fallback to original data
        chartData.project_estimates = deepCopy(originalChartData.project_estimates);
        chartData.project_time_spent = deepCopy(originalChartData.project_time_spent);
        console.log("Using fallback original data");
    }

    if (originalChartData.project_clm_estimates) {
        chartData.project_clm_estimates = deepCopy(originalChartData.project_clm_estimates);
    }

    // Restore original project counts
    if (originalChartData.project_counts_filtered) {
        chartData.project_counts = deepCopy(originalChartData.project_counts_filtered);
        console.log("Restored original project counts");
    } else if (originalChartData.project_counts) {
        chartData.project_counts = deepCopy(originalChartData.project_counts);
        console.log("Restored fallback project counts");
    }

    // Restore original project order
    if (callbacks.updateFullProjectsList && originalChartData.projectOrder.length > 0) {
        console.log("Restoring original project order");
        callbacks.updateFullProjectsList([...originalChartData.projectOrder]);
    }

    // Switch flag back
    isInitialData = true;

    // Update charts with restored data
    if (callbacks.updateChart) {
        callbacks.updateChart();
    }
    if (callbacks.recreatePieChart) {
        setTimeout(() => callbacks.recreatePieChart(), 200);
    }

    console.log("Data restored to filtered worklog data:",
        Object.keys(chartData.project_estimates).length,
        "projects in estimates,",
        Object.keys(chartData.project_time_spent).length,
        "projects in time spent");

    // Hide loading indicator
    if (loadingIndicator) {
        loadingIndicator.style.display = 'none';
    }
}

// Check if we're using initial/filtered data
export function getIsInitialData() {
    return isInitialData;
}