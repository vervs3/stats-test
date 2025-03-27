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
    document.getElementById('last-refresh-time').classList.add('text-muted');

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

                // Store the latest timestamp in the data-attribute
                if (result.data.latest_timestamp) {
                    document.body.dataset.latestTimestamp = result.data.latest_timestamp;
                }
            } else {
                console.error("API returned success: false or no data");
            }
        })
        .catch(error => {
            console.error("Error fetching dashboard data:", error);
        })
        .finally(() => {
            // Remove loading state
            document.getElementById('last-refresh-time').classList.remove('text-muted');
        });
}

// Display dashboard data
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

        // Store original data for click handler
        window.originalTimeSeriesData = {
            dates: [...timeSeriesData.dates],
            actualData: [...timeSeriesData.actual_time_spent]
        };

        // Prepare data
        const dates = [...timeSeriesData.dates];
        const actualData = [...timeSeriesData.actual_time_spent];
        const projectedData = [...timeSeriesData.projected_time_spent];

        // Create complete forecast data that extends all lines to the end of 2025
        const extendedData = createExtendedForecastData(dates, actualData, projectedData);

        // Create datasets
        const datasets = [
            {
                label: 'Фактические трудозатраты',
                data: extendedData.actualExtended,
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                borderColor: 'rgba(255, 99, 132, 1)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(255, 99, 132, 1)',
                pointBorderColor: '#fff',
                pointRadius: function(context) {
                    // Always show points for original data
                    return context.dataIndex < dates.length ? 6 : 0;
                },
                pointHoverRadius: function(context) {
                    return context.dataIndex < dates.length ? 8 : 0;
                },
                pointHitRadius: 10, // Larger hit area for easier clicking
                pointStyle: 'circle',
                pointHoverBorderWidth: 2,
                tension: 0.1
            },
            {
                label: 'Прогнозные трудозатраты',
                data: extendedData.projectedExtended,
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(54, 162, 235, 1)',
                pointBorderColor: '#fff',
                pointRadius: 0, // No points to reduce visual clutter
                pointHoverRadius: 0,
                tension: 0.1
            }
        ];

        // Add forecast dataset (green dashed line)
        if (extendedData.forecastData && extendedData.forecastData.length > 0) {
            datasets.push({
                label: 'Прогноз до конца 2025',
                data: extendedData.forecastData,
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 2,
                borderDash: [5, 5], // Dashed line for forecast
                pointRadius: 0, // No points for the forecast line
                pointHoverRadius: 0,
                fill: false, // Don't fill area under the line
                tension: 0.1
            });
        }

        // Map of original indices to extended indices
        const indexMap = {};
        for (let i = 0; i < dates.length; i++) {
            const date = dates[i];
            const extendedIndex = extendedData.allDates.indexOf(date);
            if (extendedIndex !== -1) {
                indexMap[extendedIndex] = i;
            }
        }

        // Store the index map for click handling
        window.dateIndexMap = indexMap;

        // Create chart
        window.timeSpentChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: extendedData.allDates,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Человекодни'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Дата'
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45,
                            maxTicksLimit: 20
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function(context) {
                                const label = context.dataset.label || '';
                                const value = context.parsed.y;
                                if (value === null) return '';
                                return `${label}: ${value.toFixed(0)} человекодней`;
                            }
                        }
                    },
                    legend: {
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            padding: 15
                        }
                    }
                },
                hover: {
                    mode: 'nearest',
                    intersect: true
                },
                onClick: handleTimeSpentChartClick,
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                },
                elements: {
                    point: {
                        // Make points more visually prominent
                        radius: 5,
                        hitRadius: 10,
                        hoverRadius: 7
                    }
                }
            }
        });

        // Add click handler directly to the chart element for better interactivity
        canvas.onclick = function(evt) {
            console.log('Canvas click event triggered');
            const activePoints = window.timeSpentChart.getElementsAtEventForMode(
                evt, 'nearest', { intersect: true }, true
            );

            if (activePoints.length > 0) {
                const clickedIndex = activePoints[0].index;
                handlePointClick(clickedIndex);
            }
        };

        console.log("Time spent chart initialized with click handlers");
    } catch (error) {
        console.error("Error creating time spent chart:", error);
    }
}

// Create extended forecast data that goes to the end of 2025
function createExtendedForecast(dates, actualData, projectedData) {
    if (!dates || !dates.length || !actualData || !actualData.length) {
        return {
            dates: dates,
            actualData: actualData,
            projectedData: projectedData
        };
    }

    try {
        // Get last date and value from actual data
        const lastDate = new Date(dates[dates.length - 1]);
        const lastActual = actualData[actualData.length - 1];

        // End date (December 31, 2025)
        const endDate = new Date('2025-12-31');

        // If last date is already at or past end date, no need to extend
        if (lastDate >= endDate) {
            return {
                dates: dates,
                actualData: actualData,
                projectedData: projectedData
            };
        }

        // Create extended arrays starting with existing data
        const extendedDates = [...dates];
        const extendedActual = [...actualData];
        const extendedProjected = [...projectedData];

        // Calculate growth rate from actual data
        // Use linear regression for better accuracy
        let growthRate = 0;
        if (dates.length >= 2) {
            // Convert dates to numerical values (days since first date)
            const xValues = [];
            const yValues = [];
            const firstDate = new Date(dates[0]);

            for (let i = 0; i < dates.length; i++) {
                const currentDate = new Date(dates[i]);
                const daysDiff = Math.round((currentDate - firstDate) / (1000 * 60 * 60 * 24));
                xValues.push(daysDiff);
                yValues.push(actualData[i]);
            }

            // Calculate linear regression (slope)
            const n = xValues.length;
            let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
            for (let i = 0; i < n; i++) {
                sumX += xValues[i];
                sumY += yValues[i];
                sumXY += xValues[i] * yValues[i];
                sumXX += xValues[i] * xValues[i];
            }

            if (n * sumXX - sumX * sumX !== 0) {
                const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
                growthRate = slope * 7; // Weekly growth rate
            }
        }

        // Ensure growth rate is positive and reasonable
        growthRate = Math.max(5, growthRate);

        // Get budget for projecting the end value
        const budget = getProjectBudget();

        // Generate weekly data points to end of 2025
        let currentDate = new Date(lastDate);
        let currentActual = lastActual;

        // Move to next week
        currentDate.setDate(currentDate.getDate() + 7);

        // Add points until end of 2025
        while (currentDate <= endDate) {
            // Format date as YYYY-MM-DD
            const dateStr = currentDate.toISOString().split('T')[0];

            // Add growth to actual value
            currentActual += growthRate;

            // Calculate projected value based on date relative to year
            const daysInYear = 365;
            const dayOfYear = Math.round((currentDate - new Date('2025-01-01')) / (1000 * 60 * 60 * 24));
            const projectedValue = (budget / daysInYear) * dayOfYear;

            // Add to extended arrays
            extendedDates.push(dateStr);
            extendedActual.push(currentActual);
            extendedProjected.push(projectedValue);

            // Move to next week
            currentDate.setDate(currentDate.getDate() + 7);
        }

        return {
            dates: extendedDates,
            actualData: extendedActual,
            projectedData: extendedProjected
        };
    } catch (error) {
        console.error("Error creating extended forecast:", error);
        return {
            dates: dates,
            actualData: actualData,
            projectedData: projectedData
        };
    }
}

// Create forecast data that extends to end of 2025
function createForecastToEndOfYear(dates, values) {
    if (!dates || !dates.length || !values || !values.length) {
        return null;
    }

    try {
        // Use the last data point as starting point
        const lastDate = new Date(dates[dates.length - 1]);
        const lastValue = values[values.length - 1];

        // End date (December 31, 2025)
        const endDate = new Date('2025-12-31');

        // Check if we're already at or past end date
        if (lastDate >= endDate) {
            return { values: [], extraDates: [] };
        }

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

        // Create forecast arrays
        const forecastValues = [];
        const forecastDates = [];

        // Start with the last actual data point
        forecastValues.push(lastValue);

        // Then add new points from the next week until end of 2025
        let currentDate = new Date(lastDate);
        let currentValue = lastValue;

        // Move to next week
        currentDate.setDate(currentDate.getDate() + 7);

        // Add points while we're still in 2025
        while (currentDate <= endDate) {
            // Format date as YYYY-MM-DD
            const dateStr = currentDate.toISOString().split('T')[0];

            // Add to forecast dates
            forecastDates.push(dateStr);

            // Add growth to current value
            currentValue += growthRate;

            // Add to forecast values (for the forecast line)
            forecastValues.push(currentValue);

            // Move to next week
            currentDate.setDate(currentDate.getDate() + 7);
        }

        // Remove the first point (it's the duplicated last actual point)
        forecastValues.shift();

        return {
            values: forecastValues,
            extraDates: forecastDates
        };
    } catch (error) {
        console.error("Error creating forecast data:", error);
        return null;
    }
}

// Create extended forecast data that makes all lines go to end of 2025
function createExtendedForecastData(dates, actualData, projectedData) {
    if (!dates || !dates.length || !actualData || !actualData.length) {
        return {
            allDates: dates,
            actualExtended: actualData,
            projectedExtended: projectedData,
            forecastData: []
        };
    }

    try {
        // Get budget to calculate proper projections
        const budget = getProjectBudget();

        // Get last date and values from actual data
        const lastDate = new Date(dates[dates.length - 1]);
        const lastActualValue = actualData[actualData.length - 1];
        const lastProjectedValue = projectedData[projectedData.length - 1];

        // End date (December 31, 2025)
        const endDate = new Date('2025-12-31');

        // If last date is already at or past end date, no need to extend
        if (lastDate >= endDate) {
            return {
                allDates: dates,
                actualExtended: actualData,
                projectedExtended: projectedData,
                forecastData: []
            };
        }

        // Store all dates - start with existing dates
        const allDates = [...dates];

        // Create extended arrays for each dataset
        const actualExtended = [...actualData];
        const projectedExtended = [...projectedData];

        // Create forecast data array that starts exactly at the last actual point
        const forecastData = new Array(allDates.length).fill(null);
        forecastData[forecastData.length - 1] = lastActualValue; // Set last point

        // Calculate growth rate from actual data
        let growthRate = 0;
        if (dates.length >= 2) {
            // Calculate using linear regression
            const xValues = [];
            const yValues = [];
            const firstDate = new Date(dates[0]);

            for (let i = 0; i < dates.length; i++) {
                const currentDate = new Date(dates[i]);
                const daysDiff = Math.round((currentDate - firstDate) / (1000 * 60 * 60 * 24));
                xValues.push(daysDiff);
                yValues.push(actualData[i]);
            }

            // Calculate linear regression (slope)
            const n = xValues.length;
            let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
            for (let i = 0; i < n; i++) {
                sumX += xValues[i];
                sumY += yValues[i];
                sumXY += xValues[i] * yValues[i];
                sumXX += xValues[i] * xValues[i];
            }

            if (n * sumXX - sumX * sumX !== 0) {
                const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
                growthRate = slope * 7; // Weekly growth rate
            }
        }

        // Ensure growth rate is positive and reasonable
        growthRate = Math.max(5, growthRate);

        // Generate weekly data points to end of 2025
        let currentDate = new Date(lastDate);
        let currentActualForecast = lastActualValue;

        // Move to next week
        currentDate.setDate(currentDate.getDate() + 7);

        // Add points until end of 2025
        while (currentDate <= endDate) {
            // Format date as YYYY-MM-DD
            const dateStr = currentDate.toISOString().split('T')[0];

            // Add date to all dates array
            allDates.push(dateStr);

            // Calculate the projected value based on budget and day of year
            const daysInYear = 365;
            const startOfYear = new Date('2025-01-01');
            const dayOfYear = Math.round((currentDate - startOfYear) / (1000 * 60 * 60 * 24));
            const projectedValue = (budget / daysInYear) * dayOfYear;

            // Add growth to actual forecast value
            currentActualForecast += growthRate;

            // Add to extended arrays
            actualExtended.push(null); // No actual data for future dates
            projectedExtended.push(projectedValue); // Projected continues to end of year
            forecastData.push(currentActualForecast); // Forecast grows from last actual point

            // Move to next week
            currentDate.setDate(currentDate.getDate() + 7);
        }

        return {
            allDates: allDates,
            actualExtended: actualExtended,
            projectedExtended: projectedExtended,
            forecastData: forecastData
        };
    } catch (error) {
        console.error("Error creating extended forecast data:", error);
        return {
            allDates: dates,
            actualExtended: actualData,
            projectedExtended: projectedData,
            forecastData: []
        };
    }
}

// Handle time spent chart click
function handleTimeSpentChartClick(event, elements) {
    if (!elements || !elements.length) return;

    // Get the clicked element
    const index = elements[0].index;

    // Check if we clicked on an actual data point (not forecast)
    if (index < window.timeSeriesData.dates.length) {
        const clickedDate = window.timeSeriesData.dates[index];

        // Get the timestamp for folder navigation
        try {
            const dateObj = new Date(clickedDate);
            const year = dateObj.getFullYear();
            const month = String(dateObj.getMonth() + 1).padStart(2, '0');
            const day = String(dateObj.getDate()).padStart(2, '0');
            const folderDate = `${year}${month}${day}`;

            console.log(`Clicked on date ${clickedDate}, navigating to folder ${folderDate}`);

            // Navigate to the detailed view for this date
            window.location.href = `/view/dashboard/${folderDate}`;
        } catch (error) {
            console.error("Error processing chart click:", error);
        }
    } else {
        console.log("Clicked on forecast data point, no navigation");
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

        // If no timestamp provided, use the one from the DOM
        if (!timestampStr) {
            timestampStr = document.body.dataset.latestTimestamp || '';
        }

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