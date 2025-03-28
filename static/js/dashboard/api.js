// api.js - Dashboard API communication
import { updateMetrics, updateProgressBar, showLoadingState, hideLoadingState } from './ui.js';
import { updateTimeSpentChart } from './charts/timeSpentChart.js';
import { updateOpenTasksChart } from './charts/openTasksChart.js';
import { updateClosedTasksChart } from './charts/closedTasksChart.js';

/**
 * Fetch dashboard data from the server
 * @returns {Promise} Promise that resolves with the dashboard data
 */
function fetchDashboardData() {
    console.log("Fetching dashboard data");

    // Show loading state
    showLoadingState();

    // Fetch data from API
    return fetch('/api/dashboard/data')
        .then(response => {
            console.log("API response status:", response.status);
            if (!response.ok) {
                throw new Error(`API returned status ${response.status}`);
            }
            return response.json();
        })
        .then(result => {
            console.log("Dashboard data received successfully");

            if (result.success && result.data) {
                // Process and display the data
                displayDashboardData(result.data);

                // Store the latest timestamp in the data-attribute
                if (result.data.latest_timestamp) {
                    document.body.dataset.latestTimestamp = result.data.latest_timestamp;
                }

                return result.data;
            } else {
                console.error("API returned success: false or no data");
                return null;
            }
        })
        .catch(error => {
            console.error("Error fetching dashboard data:", error);
            return null;
        })
        .finally(() => {
            // Remove loading state
            hideLoadingState();
        });
}

/**
 * Display dashboard data in all charts and UI elements
 * @param {Object} data - Dashboard data from the API
 */
function displayDashboardData(data) {
    console.log("Displaying dashboard data");

    // Update summary metrics from latest data
    if (data.latest_data) {
        updateSummaryMetrics(data.latest_data);

        // Update the last refresh timestamp to show the date from latest data
        const lastRefreshElement = document.getElementById('last-refresh-time');
        if (lastRefreshElement && data.latest_data.date) {
            lastRefreshElement.textContent = data.latest_data.date;
        }
    }

    // Display time spent chart
    if (data.time_series && data.time_series.dates && data.time_series.dates.length > 0) {
        console.log(`Displaying time spent chart with ${data.time_series.dates.length} data points`);
        updateTimeSpentChart(data.time_series);
    } else {
        console.warn("No time series data available");
    }

    // Display open tasks chart
    if (data.open_tasks_data && Object.keys(data.open_tasks_data).length > 0) {
        console.log(`Displaying open tasks chart with ${Object.keys(data.open_tasks_data).length} projects`);
        updateOpenTasksChart(data.open_tasks_data, data.latest_timestamp || '');
    } else {
        console.warn("No open tasks data available");
        // Инициализировать с пустыми данными чтобы показать пустой график
        updateOpenTasksChart({}, data.latest_timestamp || '');
    }

    // Display closed tasks chart
    console.log("Closed tasks data:", data.closed_tasks_data);
    if (data.closed_tasks_data && Object.keys(data.closed_tasks_data).length > 0) {
        console.log(`Displaying closed tasks chart with ${Object.keys(data.closed_tasks_data).length} projects`);
    } else {
        console.warn("No closed tasks data available");
    }

    // Всегда обновляем график закрытых задач, даже если данных нет
    updateClosedTasksChart(data.closed_tasks_data || {}, data.latest_timestamp || '');
}

/**
 * Update summary metrics
 * @param {Object} latestData - Latest dashboard data
 */
function updateSummaryMetrics(latestData) {
    console.log("Updating summary metrics");

    // Define hours per day constant
    const HOURS_PER_DAY = 8;

    // Import required modules
    import('./utils.js').then(({ getProjectBudget, calculateProjectedValue }) => {
        import('./ui.js').then(({ updateMetrics, updateProgressBar }) => {
            // Update actual time spent (converting from hours to days)
            const actualValueHours = latestData.total_time_spent_hours || 0;
            const actualValueDays = actualValueHours / HOURS_PER_DAY;
            updateMetrics('actual-time-spent', Math.round(actualValueDays).toLocaleString());

            // Calculate and update projected time
            const budget = getProjectBudget();
            const projectedValue = calculateProjectedValue(budget);
            updateMetrics('projected-time-spent', Math.round(projectedValue).toLocaleString());

            // Calculate and update difference
            const difference = projectedValue - actualValueDays;
            updateMetrics('time-difference', Math.round(difference).toLocaleString(), difference > 0 ? 'success' : 'danger');

            // Update progress bar using day values
            updateProgressBar(actualValueDays, budget);
        });
    });
}

/**
 * Trigger data collection
 */
function triggerDataCollection() {
    console.log("Triggering data collection");

    // Disable button and show loading
    const btn = document.getElementById('trigger-collection');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Запуск...';
    }

    // Show modal
    const modal = document.getElementById('collectionModal');
    if (modal) {
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    }

    // Call API to trigger collection
    fetch('/api/dashboard/collect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(data => {
        console.log("Data collection response:", data);

        // Refresh after 30 seconds
        setTimeout(fetchDashboardData, 30000);
    })
    .catch(error => {
        console.error("Error triggering data collection:", error);
        alert('Ошибка при запуске сбора данных: ' + error.message);
    })
    .finally(() => {
        // Reset button
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-cloud-download"></i> Сбор данных';
        }
    });
}

/**
 * Create JQL query for open tasks
 * @param {string} project - Project ID
 * @param {string} timestamp - Timestamp
 */
function createOpenTasksJQL(project, timestamp) {
    // Create URL parameters
    const params = new URLSearchParams();
    params.append('project', encodeURIComponent(project));
    params.append('chart_type', 'open_tasks');
    params.append('is_clm', 'true');
    params.append('timestamp', timestamp);

    // Explicitly request count-based (not time-based) data for open tasks
    params.append('count_based', 'true');

    // Fetch JQL from server
    fetch(`/jql/special?${params.toString()}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned status ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Received JQL for open tasks (count-based):", data.jql);

            // Import UI module to show modal
            import('./ui.js').then(({ showJqlModal }) => {
                showJqlModal(data.jql, data.url);
            });
        })
        .catch(error => {
            console.error("Error creating JQL for open tasks:", error);
            alert('Ошибка при создании JQL: ' + error.message);
        });
}

/**
 * Create JQL query for closed tasks without comments, attachments, and links
 * @param {string} project - Project ID
 * @param {string} timestamp - Timestamp
 */
function createClosedTasksJQL(project, timestamp) {
    // Create URL parameters
    const params = new URLSearchParams();
    params.append('project', encodeURIComponent(project));
    params.append('chart_type', 'closed_tasks');
    params.append('is_clm', 'true');
    params.append('timestamp', timestamp);

    // Explicitly request count-based (not time-based) data for closed tasks
    params.append('count_based', 'true');

    // Fetch JQL from server
    fetch(`/jql/special?${params.toString()}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned status ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Received JQL for closed tasks:", data.jql);

            // Import UI module to show modal
            import('./ui.js').then(({ showJqlModal }) => {
                showJqlModal(data.jql, data.url);
            });
        })
        .catch(error => {
            console.error("Error creating JQL for closed tasks:", error);
            alert('Ошибка при создании JQL: ' + error.message);
        });
}

export { fetchDashboardData, triggerDataCollection, createOpenTasksJQL, createClosedTasksJQL, updateSummaryMetrics };