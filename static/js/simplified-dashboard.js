// Super simplified dashboard script focused on reliability
document.addEventListener('DOMContentLoaded', function() {
    console.log("Dashboard DOM loaded, starting initialization");

    // Ensure Chart.js is available
    if (typeof Chart === 'undefined') {
        console.error("Chart.js is not loaded, dashboard functionality will be limited");
    } else {
        console.log("Chart.js is available, version:", Chart.version);
    }

    // Check if we're on the dashboard page
    if (!isDashboardPage()) {
        console.log("Not on dashboard page, exiting initialization");
        return;
    }

    // Initialize dashboard
    initDashboard();
});

// Check if we're on the dashboard page
function isDashboardPage() {
    return document.querySelector('.dashboard') !== null ||
           window.location.pathname.includes('dashboard');
}

// Initialize dashboard
function initDashboard() {
    console.log("Initializing dashboard");

    // Set up UI event listeners
    setupEventListeners();

    // Update with fallback data first to ensure something is displayed
    updateUIWithFallbackData();

    // Fetch and display real data
    fetchDashboardData();
}

// Set up dashboard event listeners
function setupEventListeners() {
    // Manual refresh button
    const refreshBtn = document.getElementById('manual-refresh');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            console.log("Manual refresh triggered");
            fetchDashboardData();
        });
    }

    // Data collection button
    const collectionBtn = document.getElementById('trigger-collection');
    if (collectionBtn) {
        collectionBtn.addEventListener('click', triggerDataCollection);
    }

    // Set up auto-refresh
    setupAutoRefresh();
}

// Set up auto-refresh
function setupAutoRefresh() {
    const refreshInterval = parseInt(document.body.dataset.refreshInterval || '3600');
    if (refreshInterval > 0) {
        console.log(`Setting up auto-refresh every ${refreshInterval} seconds`);
        setInterval(fetchDashboardData, refreshInterval * 1000);
    }
}

// Update UI with fallback data
function updateUIWithFallbackData() {
    console.log("Updating UI with fallback data");

    // Update key metrics
    updateMetric('actual-time-spent', '950');
    updateMetric('projected-time-spent', '1100');
    updateMetric('time-difference', '150', 'success');

    // Update progress bar
    updateProgressBar(950, 18000);

    // Update last refresh time
    updateLastRefreshTime();

    // Initialize empty charts
    initEmptyCharts();
}

// Update a metric display
function updateMetric(id, value, statusClass) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;

        // Add status class if provided
        if (statusClass) {
            if (statusClass === 'success') {
                element.classList.add('text-success');
                element.classList.remove('text-danger');
            } else if (statusClass === 'danger') {
                element.classList.add('text-danger');
                element.classList.remove('text-success');
            }
        }
    }
}

// Update progress bar
function updateProgressBar(value, total) {
    const progressBar = document.getElementById('time-progress');
    if (progressBar) {
        const percent = Math.min(100, Math.max(0, (value / total) * 100));
        progressBar.style.width = `${percent}%`;
        progressBar.textContent = `${Math.round(percent)}%`;
    }
}

// Update last refresh time
function updateLastRefreshTime() {
    const element = document.getElementById('last-refresh-time');
    if (element) {
        element.textContent = new Date().toLocaleTimeString();
    }
}

// Initialize empty charts
function initEmptyCharts() {
    // Try to initialize empty charts as placeholders
    const timeSpentCanvas = document.getElementById('timeSpentChart');
    const openTasksCanvas = document.getElementById('openTasksChart');

    // Only proceed if Chart.js is available
    if (typeof Chart === 'undefined') return;

    // Initialize empty time spent chart
    if (timeSpentCanvas) {
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

    // Initialize empty open tasks chart
    if (openTasksCanvas) {
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
}

// Fetch dashboard data
function fetchDashboardData() {
    console.log("Fetching dashboard data");

    // Show loading state
    const refreshBtn = document.getElementById('manual-refresh');
    if (refreshBtn) {
        refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
        refreshBtn.disabled = true;
    }

    // Fetch data from API
    fetch('/api/dashboard/data')
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
            } else {
                console.error("API returned success: false or no data");
            }
        })
        .catch(error => {
            console.error("Error fetching dashboard data:", error);
        })
        .finally(() => {
            // Reset button state
            if (refreshBtn) {
                refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i>';
                refreshBtn.disabled = false;
            }

            // Always update the refresh time
            updateLastRefreshTime();
        });
}

// Display dashboard data
function displayDashboardData(data) {
    console.log("Displaying dashboard data");

    // Update summary metrics from latest data
    if (data.latest_data) {
        updateSummaryMetrics(data.latest_data);
    }

    // Display time spent chart
    if (data.time_series && data.time_series.dates && data.time_series.dates.length > 0) {
        console.log(`Displaying time spent chart with ${data.time_series.dates.length} data points`);
        displayTimeSpentChart(data.time_series);
    } else {
        console.warn("No time series data available");
    }

    // Display open tasks chart
    if (data.open_tasks_data && Object.keys(data.open_tasks_data).length > 0) {
        console.log(`Displaying open tasks chart with ${Object.keys(data.open_tasks_data).length} projects`);
        displayOpenTasksChart(data.open_tasks_data, data.latest_timestamp || '');
    } else {
        console.warn("No open tasks data available");
    }
}

// Update summary metrics
function updateSummaryMetrics(latestData) {
    console.log("Updating summary metrics");

    // Update actual time spent
    const actualValue = latestData.total_time_spent_days || 0;
    updateMetric('actual-time-spent', Math.round(actualValue).toLocaleString());

    // Calculate and update projected time
    const budget = getProjectBudget();
    const projectedValue = calculateProjectedValue(budget);
    updateMetric('projected-time-spent', Math.round(projectedValue).toLocaleString());

    // Calculate and update difference
    const difference = projectedValue - actualValue;
    updateMetric('time-difference', Math.round(difference).toLocaleString(), difference > 0 ? 'success' : 'danger');

    // Update progress bar
    updateProgressBar(actualValue, budget);
}

// Get project budget from DOM
function getProjectBudget() {
    const progressElement = document.querySelector('.progress');
    return progressElement ? parseInt(progressElement.dataset.budget) || 18000 : 18000;
}

// Calculate projected value based on current date
function calculateProjectedValue(budget) {
    // Get current date
    const today = new Date();

    // Project start (Jan 1, 2025)
    const startDate = new Date('2025-01-01');

    // Project end (Dec 31, 2025)
    const endDate = new Date('2025-12-31');

    // Total days in project
    const totalDays = Math.round((endDate - startDate) / (1000 * 60 * 60 * 24)) + 1;

    // Days elapsed so far
    let daysElapsed;
    if (today < startDate) {
        daysElapsed = 0;
    } else if (today > endDate) {
        daysElapsed = totalDays;
    } else {
        daysElapsed = Math.round((today - startDate) / (1000 * 60 * 60 * 24)) + 1;
    }

    // Calculate projected value (linear projection)
    return (budget / totalDays) * daysElapsed;
}

// Display time spent chart
function displayTimeSpentChart(timeSeriesData) {
    // Basic validation
    if (!timeSeriesData || !timeSeriesData.dates || !Array.isArray(timeSeriesData.dates) ||
        !timeSeriesData.actual_time_spent || !Array.isArray(timeSeriesData.actual_time_spent)) {
        console.error("Invalid time series data structure");
        return;
    }

    // Get canvas element
    const canvas = document.getElementById('timeSpentChart');
    if (!canvas) {
        console.error("Time spent chart canvas not found");
        return;
    }

    try {
        // Get canvas context
        const ctx = canvas.getContext('2d');

        // Destroy existing chart if it exists
        if (window.timeSpentChart instanceof Chart) {
            window.timeSpentChart.destroy();
        }

        // Prepare data
        const dates = [...timeSeriesData.dates];
        const actualData = [...timeSeriesData.actual_time_spent];
        const projectedData = [...timeSeriesData.projected_time_spent];

        // Add forecast data
        const forecastData = createSimpleForecast(dates, actualData);

        // Create datasets
        const datasets = [
            {
                label: 'Фактические трудозатраты',
                data: actualData,
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                borderColor: 'rgba(255, 99, 132, 1)',
                borderWidth: 2
            },
            {
                label: 'Прогнозные трудозатраты',
                data: projectedData,
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 2
            }
        ];

        // Add forecast dataset if available
        if (forecastData && forecastData.dates && forecastData.values) {
            // Create combined datasets for forecast
            const combinedDates = forecastData.dates;
            const forecastValues = forecastData.values;

            // Add forecast dataset with green color
            datasets.push({
                label: 'Прогноз до конца 2025',
                data: forecastValues,
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 2,
                borderDash: [5, 5],
                pointRadius: 0
            });

            // Use combined dates for the chart
            window.timeSpentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: combinedDates,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    },
                    onClick: handleTimeSpentChartClick
                }
            });
        } else {
            // Fallback to basic chart without forecast
            window.timeSpentChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: datasets.slice(0, 2) // Just use actual and projected
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    },
                    onClick: handleTimeSpentChartClick
                }
            });
        }
    } catch (error) {
        console.error("Error creating time spent chart:", error);

        try {
            // Fallback to direct canvas drawing
            const ctx = canvas.getContext('2d');
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.font = '16px Arial';
            ctx.textAlign = 'center';
            ctx.fillStyle = '#333';
            ctx.fillText('Не удалось построить график', canvas.width / 2, canvas.height / 2);
            ctx.fillText(`Доступно ${timeSeriesData.dates.length} точек данных`, canvas.width / 2, canvas.height / 2 + 30);
        } catch (e) {
            console.error("Fallback drawing also failed:", e);
        }
    }
}

// Create simple forecast data
function createSimpleForecast(dates, values) {
    if (!dates || !dates.length || !values || !values.length) {
        return null;
    }

    try {
        // Use the last data point as starting point
        const lastDate = new Date(dates[dates.length - 1]);
        const lastValue = values[values.length - 1];

        // End date (December 31, 2025)
        const endDate = new Date('2025-12-31');

        // Weekly growth rate (can be calculated from data or use default)
        let growthRate = 5; // Default: 5 person-days per week

        // If we have at least 2 points, try to calculate growth rate
        if (dates.length >= 2 && values.length >= 2) {
            const firstDate = new Date(dates[0]);
            const firstValue = values[0];

            const daysDiff = Math.max(1, (lastDate - firstDate) / (1000 * 60 * 60 * 24));
            const valueDiff = lastValue - firstValue;

            // Calculate daily growth and convert to weekly
            const dailyGrowth = valueDiff / daysDiff;
            growthRate = dailyGrowth * 7;

            // Ensure growth rate is positive and reasonable
            growthRate = Math.max(1, growthRate);
        }

        // Create forecast arrays starting with actual data
        const forecastDates = [...dates];
        const forecastValues = [...values];

        // Generate weekly data points from last date to end of 2025
        let currentDate = new Date(lastDate);
        let currentValue = lastValue;

        // Move to next week
        currentDate.setDate(currentDate.getDate() + 7);

        // Add points while we're still in 2025
        while (currentDate <= endDate) {
            // Format date as YYYY-MM-DD
            const dateStr = currentDate.toISOString().split('T')[0];

            // Add growth to current value
            currentValue += growthRate;

            // Add to forecast arrays
            forecastDates.push(dateStr);
            forecastValues.push(currentValue);

            // Move to next week
            currentDate.setDate(currentDate.getDate() + 7);
        }

        return {
            dates: forecastDates,
            values: forecastValues,
            originalDataCount: dates.length
        };
    } catch (error) {
        console.error("Error creating forecast data:", error);
        return null;
    }
}

// Handle time spent chart click
function handleTimeSpentChartClick(event, elements) {
    // Only handle clicks on data points
    if (!elements || !elements.length) return;

    // Get clicked element info
    const clickedIndex = elements[0].index;
    const clickedChart = this.chart;
    const labels = clickedChart.data.labels;

    // Check if this is an actual data point (not forecast)
    if (clickedIndex < timeSeriesData.dates.length) {
        // Get the date
        const date = labels[clickedIndex];

        // Convert to folder format (YYYYMMDD)
        try {
            const dateObj = new Date(date);
            const year = dateObj.getFullYear();
            const month = String(dateObj.getMonth() + 1).padStart(2, '0');
            const day = String(dateObj.getDate()).padStart(2, '0');
            const folderDate = `${year}${month}${day}`;

            // Navigate to dashboard view for this date
            window.location.href = `/view/dashboard/${folderDate}`;
        } catch (error) {
            console.error("Error parsing date for navigation:", error);
        }
    }
}

// Display open tasks chart
function displayOpenTasksChart(openTasksData, timestampStr) {
    // Basic validation
    if (!openTasksData || typeof openTasksData !== 'object') {
        console.error("Invalid open tasks data");
        return;
    }

    // Get canvas element
    const canvas = document.getElementById('openTasksChart');
    if (!canvas) {
        console.error("Open tasks chart canvas not found");
        return;
    }

    try {
        // Get canvas context
        const ctx = canvas.getContext('2d');

        // Destroy existing chart if it exists
        if (window.openTasksChart instanceof Chart) {
            window.openTasksChart.destroy();
        }

        // Prepare data
        const projects = Object.keys(openTasksData);
        const values = projects.map(p => openTasksData[p]);

        // Create color array
        const colors = [
            'rgba(255, 99, 132, 0.7)',
            'rgba(54, 162, 235, 0.7)',
            'rgba(255, 206, 86, 0.7)',
            'rgba(75, 192, 192, 0.7)',
            'rgba(153, 102, 255, 0.7)',
            'rgba(255, 159, 64, 0.7)'
        ];

        // Generate colors for each project
        const backgroundColor = projects.map((_, i) => colors[i % colors.length]);

        // Create chart
        window.openTasksChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: projects,
                datasets: [{
                    label: 'Открытые задачи',
                    data: values,
                    backgroundColor: backgroundColor,
                    borderColor: backgroundColor.map(c => c.replace('0.7', '1')),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                onClick: function(e, elements) {
                    handleOpenTasksChartClick(e, elements, projects, timestampStr);
                }
            }
        });
    } catch (error) {
        console.error("Error creating open tasks chart:", error);
    }
}

// Handle open tasks chart click
function handleOpenTasksChartClick(event, elements, projects, timestampStr) {
    // Check if we have clicked elements
    if (!elements || !elements.length) return;

    // Get clicked element info
    const clickedIndex = elements[0].index;
    const project = projects[clickedIndex];

    console.log(`Open tasks chart clicked: project=${project}, timestamp=${timestampStr}`);

    // Create JQL query for this project
    createOpenTasksJQL(project, timestampStr);
}

// Create JQL query for open tasks
function createOpenTasksJQL(project, timestamp) {
    // Create URL parameters
    const params = new URLSearchParams();
    params.append('project', encodeURIComponent(project));
    params.append('chart_type', 'open_tasks');
    params.append('is_clm', 'true');
    params.append('timestamp', timestamp);

    // Fetch JQL from server
    fetch(`/jql/special?${params.toString()}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned status ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Received JQL:", data.jql);

            // Display in modal
            showJqlModal(data.jql, data.url);
        })
        .catch(error => {
            console.error("Error creating JQL:", error);
            alert('Ошибка при создании JQL: ' + error.message);
        });
}

// Show JQL modal
function showJqlModal(jql, url) {
    // Get modal elements
    const modal = document.getElementById('jqlModal');
    const jqlText = document.getElementById('jqlQuery');
    const openBtn = document.getElementById('openJiraBtn');

    if (!modal || !jqlText || !openBtn) {
        console.error("Modal elements not found");
        // Fallback - open directly
        window.open(url, '_blank');
        return;
    }

    // Set modal content
    jqlText.value = jql;
    openBtn.href = url;

    // Show modal
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

// Trigger data collection
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