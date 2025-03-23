/**
 * Data Manager Module - Handles loading and state of chart data
 */

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
    filtered_project_counts: {},
    projects: [],
    projectOrder: []
};

// Store original summary data for restoration
let originalSummaryData = null;

// Deep copy function to avoid reference issues
function deepCopy(obj) {
    return JSON.parse(JSON.stringify(obj));
}

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

// Helper function to update summary statistics
function updateSummaryStatistics(data) {
    console.log("UPDATING SUMMARY STATISTICS");

    // Find summary rows by their field labels
    const summaryRows = document.querySelectorAll('.card-body table tbody tr');
    if (!summaryRows || summaryRows.length === 0) {
        console.warn("Summary statistics table not found");
        return;
    }

    // Helper function to find a row by the text in its th element
    function findRowByLabel(label) {
        for (const row of summaryRows) {
            const thElement = row.querySelector('th');
            if (thElement && thElement.textContent.includes(label)) {
                return row;
            }
        }
        return null;
    }

    // Update total issues count
    const totalIssuesRow = findRowByLabel('Всего задач');
    if (totalIssuesRow) {
        const tdElement = totalIssuesRow.querySelector('td');
        if (tdElement) {
            const newCount = data.implementation_count || data.filtered_count || 0;
            tdElement.textContent = newCount;
            console.log(`Updated total issues count to ${newCount}`);
        }
    }

    // Update project count
    const projectsCountRow = findRowByLabel('Количество проектов');
    if (projectsCountRow) {
        const tdElement = projectsCountRow.querySelector('td');
        if (tdElement) {
            const projectCount = Object.keys(data.project_estimates || {}).length;
            tdElement.textContent = projectCount;
            console.log(`Updated project count to ${projectCount}`);
        }
    }

    // Update total estimate hours
    const totalEstimateRow = findRowByLabel('Общая исходная оценка');
    if (totalEstimateRow) {
        const tdElement = totalEstimateRow.querySelector('td');
        if (tdElement) {
            const totalEstimate = Object.values(data.project_estimates || {}).reduce((sum, val) => sum + val, 0);
            tdElement.textContent = totalEstimate.toFixed(2);
            console.log(`Updated total estimate to ${totalEstimate.toFixed(2)}`);
        }
    }

    // Update total time spent hours
    const totalTimeSpentRow = findRowByLabel('Общее затраченное время');
    if (totalTimeSpentRow) {
        const tdElement = totalTimeSpentRow.querySelector('td');
        if (tdElement) {
            const totalTimeSpent = Object.values(data.project_time_spent || {}).reduce((sum, val) => sum + val, 0);
            tdElement.textContent = totalTimeSpent.toFixed(2);
            console.log(`Updated total time spent to ${totalTimeSpent.toFixed(2)}`);
        }
    }

    // Update average estimate per issue
    const avgEstimateRow = findRowByLabel('Средняя оценка на задачу');
    if (avgEstimateRow) {
        const tdElement = avgEstimateRow.querySelector('td');
        if (tdElement) {
            const totalEstimate = Object.values(data.project_estimates || {}).reduce((sum, val) => sum + val, 0);
            const issueCount = data.implementation_count || data.filtered_count || 0;
            const avgEstimate = issueCount > 0 ? totalEstimate / issueCount : 0;
            tdElement.textContent = avgEstimate.toFixed(2);
            console.log(`Updated average estimate to ${avgEstimate.toFixed(2)}`);
        }
    }

    // Update average time spent per issue
    const avgTimeSpentRow = findRowByLabel('Среднее затраченное время на задачу');
    if (avgTimeSpentRow) {
        const tdElement = avgTimeSpentRow.querySelector('td');
        if (tdElement) {
            const totalTimeSpent = Object.values(data.project_time_spent || {}).reduce((sum, val) => sum + val, 0);
            const issueCount = data.implementation_count || data.filtered_count || 0;
            const avgTimeSpent = issueCount > 0 ? totalTimeSpent / issueCount : 0;
            tdElement.textContent = avgTimeSpent.toFixed(2);
            console.log(`Updated average time spent to ${avgTimeSpent.toFixed(2)}`);
        }
    }

    // Update overall efficiency
    const efficiencyRow = findRowByLabel('Общий коэффициент эффективности');
    if (efficiencyRow) {
        const tdElement = efficiencyRow.querySelector('td');
        if (tdElement) {
            const totalEstimate = Object.values(data.project_estimates || {}).reduce((sum, val) => sum + val, 0);
            const totalTimeSpent = Object.values(data.project_time_spent || {}).reduce((sum, val) => sum + val, 0);
            const efficiency = totalEstimate > 0 ? totalTimeSpent / totalEstimate : 0;
            tdElement.textContent = efficiency.toFixed(2);
            console.log(`Updated efficiency to ${efficiency.toFixed(2)}`);
        }
    }

    // Update CLM-specific metrics if they exist
    if (data.clm_issues_count !== undefined) {
        // CLM Issues count
        const clmIssuesRow = findRowByLabel('Количество тикетов CLM');
        if (clmIssuesRow) {
            const tdElement = clmIssuesRow.querySelector('td');
            if (tdElement) {
                tdElement.textContent = data.clm_issues_count;
                console.log(`Updated CLM issues count to ${data.clm_issues_count}`);
            }
        }

        // EST Issues count
        const estIssuesRow = findRowByLabel('Количество тикетов EST');
        if (estIssuesRow) {
            const tdElement = estIssuesRow.querySelector('td');
            if (tdElement) {
                tdElement.textContent = data.est_issues_count;
                console.log(`Updated EST issues count to ${data.est_issues_count}`);
            }
        }

        // Improvement Issues count
        const improvementIssuesRow = findRowByLabel('Количество Improvement');
        if (improvementIssuesRow) {
            const tdElement = improvementIssuesRow.querySelector('td');
            if (tdElement) {
                tdElement.textContent = data.improvement_issues_count;
                console.log(`Updated Improvement issues count to ${data.improvement_issues_count}`);
            }
        }

        // Linked Issues count
        const linkedIssuesRow = findRowByLabel('Всего связанных задач');
        if (linkedIssuesRow) {
            const tdElement = linkedIssuesRow.querySelector('td');
            if (tdElement) {
                tdElement.textContent = data.linked_issues_count || data.implementation_count;
                console.log(`Updated linked issues count to ${data.linked_issues_count || data.implementation_count}`);
            }
        }
    }

    // Update CLM estimate total in the dynamically populated field
    const totalClmEstElement = document.getElementById('total-clm-est');
    if (totalClmEstElement && data.project_clm_estimates) {
        const totalClmEst = Object.values(data.project_clm_estimates).reduce((sum, val) => sum + val, 0);
        totalClmEstElement.textContent = totalClmEst.toFixed(2);
        console.log(`Updated total CLM estimate to ${totalClmEst.toFixed(2)}`);
    }

    console.log("Summary statistics update complete");
}

// Capture original summary data
function captureSummaryData() {
    console.log("CAPTURING ORIGINAL SUMMARY DATA");

    // Initialize empty summary data object
    const data = {};

    // Get all table rows in summary section
    const rows = document.querySelectorAll('.card-body table tbody tr');

    // Helper function to find a row by its label
    function getRowValue(label) {
        for (const row of rows) {
            const th = row.querySelector('th');
            if (th && th.textContent.includes(label)) {
                const td = row.querySelector('td');
                if (td) return td.textContent;
            }
        }
        return null;
    }

    // Capture all relevant statistics
    data.totalIssues = getRowValue('Всего задач');
    data.projectsCount = getRowValue('Количество проектов');
    data.totalEstimate = getRowValue('Общая исходная оценка');
    data.totalTimeSpent = getRowValue('Общее затраченное время');
    data.avgEstimate = getRowValue('Средняя оценка на задачу');
    data.avgTimeSpent = getRowValue('Среднее затраченное время');
    data.efficiency = getRowValue('Общий коэффициент эффективности');
    data.clmIssuesCount = getRowValue('Количество тикетов CLM');
    data.estIssuesCount = getRowValue('Количество тикетов EST');
    data.improvementIssuesCount = getRowValue('Количество Improvement');
    data.linkedIssuesCount = getRowValue('Всего связанных задач');

    // Capture CLM estimate total if available
    const totalClmEstElement = document.getElementById('total-clm-est');
    if (totalClmEstElement) {
        data.totalClmEst = totalClmEstElement.textContent;
    }

    console.log("Original summary data captured", data);
    return data;
}

// Restore summary data from backup
function restoreSummaryData(data) {
    console.log("RESTORING ORIGINAL SUMMARY DATA");

    if (!data) {
        console.warn("No summary data to restore");
        return;
    }

    // Get all table rows
    const rows = document.querySelectorAll('.card-body table tbody tr');

    // Helper function to update a row value
    function setRowValue(label, value) {
        if (value === null) return;

        for (const row of rows) {
            const th = row.querySelector('th');
            if (th && th.textContent.includes(label)) {
                const td = row.querySelector('td');
                if (td) {
                    td.textContent = value;
                    console.log(`Restored ${label} to ${value}`);
                }
            }
        }
    }

    // Restore all saved values
    setRowValue('Всего задач', data.totalIssues);
    setRowValue('Количество проектов', data.projectsCount);
    setRowValue('Общая исходная оценка', data.totalEstimate);
    setRowValue('Общее затраченное время', data.totalTimeSpent);
    setRowValue('Средняя оценка на задачу', data.avgEstimate);
    setRowValue('Среднее затраченное время', data.avgTimeSpent);
    setRowValue('Общий коэффициент эффективности', data.efficiency);
    setRowValue('Количество тикетов CLM', data.clmIssuesCount);
    setRowValue('Количество тикетов EST', data.estIssuesCount);
    setRowValue('Количество Improvement', data.improvementIssuesCount);
    setRowValue('Всего связанных задач', data.linkedIssuesCount);

    // Restore CLM estimate if it was captured
    if (data.totalClmEst) {
        const totalClmEstElement = document.getElementById('total-clm-est');
        if (totalClmEstElement) {
            totalClmEstElement.textContent = data.totalClmEst;
            console.log(`Restored total CLM estimate to ${data.totalClmEst}`);
        }
    }

    console.log("Summary data restoration complete");
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

    const pieLoadingIndicator = document.getElementById('pie-period-loading');
    if (pieLoadingIndicator) {
        pieLoadingIndicator.style.display = 'block';
    }

    // Backup current summary data if not already saved
    if (!originalSummaryData) {
        // Capture the current displayed summary values
        originalSummaryData = captureSummaryData();
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
            originalChartData.filtered_project_counts = deepCopy(chartData.project_counts);
            originalChartData.projectOrder = callbacks.getFullProjectsList ? [...callbacks.getFullProjectsList()] : [];

            // Update chart data with full implementation issues data
            chartData.project_estimates = fullData.project_estimates;
            chartData.project_time_spent = fullData.project_time_spent;
            chartData.project_counts = fullData.project_counts;

            if (fullData.project_clm_estimates) {
                chartData.project_clm_estimates = fullData.project_clm_estimates;
                originalChartData.project_clm_estimates = deepCopy(fullData.project_clm_estimates);
            }

            // Update project order based on new data
            if (callbacks.updateFullProjectsList) {
                // Get all unique projects from both datasets
                const newUniqueProjects = [...new Set([
                    ...Object.keys(fullData.project_estimates),
                    ...Object.keys(fullData.project_time_spent),
                    ...Object.keys(fullData.project_counts),
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

            // First update the comparison chart
            if (callbacks.updateChart) {
                callbacks.updateChart();
            }

            // Update summary statistics directly with the full data
            updateSummaryStatistics({
                implementation_count: fullData.implementation_count,
                filtered_count: fullData.filtered_count,
                project_estimates: fullData.project_estimates,
                project_time_spent: fullData.project_time_spent,
                project_counts: fullData.project_counts,
                project_clm_estimates: fullData.project_clm_estimates,
                // Include CLM-specific metrics if available
                clm_issues_count: fullData.clm_issues_count,
                est_issues_count: fullData.est_issues_count,
                improvement_issues_count: fullData.improvement_issues_count,
                linked_issues_count: fullData.implementation_count
            });

            // Then update the pie chart with a delay and pass the updated chartData
            if (callbacks.recreatePieChart) {
                // Use a proper delay to ensure the chart data is ready
                setTimeout(() => {
                    console.log("FORCE RECREATING PIE CHART with full data");
                    console.log(`PIE CHART DATA: ${Object.keys(chartData.project_counts).length} projects, ` +
                              `total count: ${Object.values(chartData.project_counts).reduce((a, b) => a + b, 0)}`);

                    // Create a complete new copy to ensure no shared references
                    const chartDataCopy = JSON.parse(JSON.stringify(chartData));
                    callbacks.recreatePieChart(chartDataCopy);

                    // Hide loading indicators
                    if (pieLoadingIndicator) {
                        pieLoadingIndicator.style.display = 'none';
                    }
                }, 400);
            }

            console.log("Data updated to full implementation data:",
                Object.keys(chartData.project_estimates).length,
                "projects in estimates,",
                Object.keys(chartData.project_time_spent).length,
                "projects in time spent,",
                Object.keys(chartData.project_counts).length,
                "projects in counts");

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

            const dataModeIndicator = document.getElementById('data-mode-indicator');
            if (dataModeIndicator) {
                dataModeIndicator.textContent = 'Данные за период';
            }
            const pieIndicator = document.getElementById('pie-data-mode-indicator');
            if (pieIndicator) {
                pieIndicator.textContent = 'Данные за период';
            }

            // Hide loading indicators
            if (loadingIndicator) {
                loadingIndicator.style.display = 'none';
            }
            if (pieLoadingIndicator) {
                pieLoadingIndicator.style.display = 'none';
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

    const pieLoadingIndicator = document.getElementById('pie-period-loading');
    if (pieLoadingIndicator) {
        pieLoadingIndicator.style.display = 'block';
    }

    // Restore the data
    if (originalChartData.filtered_project_estimates &&
        Object.keys(originalChartData.filtered_project_estimates).length > 0) {
        // If we have explicit filtered data saved, use it
        chartData.project_estimates = deepCopy(originalChartData.filtered_project_estimates);
        chartData.project_time_spent = deepCopy(originalChartData.filtered_project_time_spent);
        chartData.project_counts = deepCopy(originalChartData.filtered_project_counts);
        console.log("Using explicitly saved filtered data");
    } else {
        // Otherwise fallback to original data
        chartData.project_estimates = deepCopy(originalChartData.project_estimates);
        chartData.project_time_spent = deepCopy(originalChartData.project_time_spent);
        chartData.project_counts = deepCopy(originalChartData.project_counts);
        console.log("Using fallback original data");
    }

    if (originalChartData.project_clm_estimates) {
        chartData.project_clm_estimates = deepCopy(originalChartData.project_clm_estimates);
    }

    // Restore original project order
    if (callbacks.updateFullProjectsList && originalChartData.projectOrder.length > 0) {
        console.log("Restoring original project order");
        callbacks.updateFullProjectsList([...originalChartData.projectOrder]);
    }

    // Switch flag back
    isInitialData = true;

    // First update the comparison chart
    if (callbacks.updateChart) {
        callbacks.updateChart();
    }

    // Restore original summary data if available
    if (originalSummaryData) {
        restoreSummaryData(originalSummaryData);
    }

    // Then update the pie chart with a delay and pass the updated chartData
    if (callbacks.recreatePieChart) {
        setTimeout(() => {
            console.log("FORCE RECREATING PIE CHART with filtered data");
            console.log(`PIE CHART DATA: ${Object.keys(chartData.project_counts).length} projects, ` +
                      `total count: ${Object.values(chartData.project_counts).reduce((a, b) => a + b, 0)}`);

            // Create a complete new copy to ensure no shared references
            const chartDataCopy = JSON.parse(JSON.stringify(chartData));
            callbacks.recreatePieChart(chartDataCopy);

            // Hide loading indicator
            if (pieLoadingIndicator) {
                pieLoadingIndicator.style.display = 'none';
            }
        }, 400);
    }

    console.log("Data restored to filtered worklog data:",
        Object.keys(chartData.project_estimates).length,
        "projects in estimates,",
        Object.keys(chartData.project_time_spent).length,
        "projects in time spent,",
        Object.keys(chartData.project_counts).length,
        "projects in counts");

    // Hide loading indicator
    if (loadingIndicator) {
        loadingIndicator.style.display = 'none';
    }
}

// Check if we're using initial/filtered data
export function getIsInitialData() {
    return isInitialData;
}