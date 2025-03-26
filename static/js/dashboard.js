// Initialize dashboard charts
document.addEventListener('DOMContentLoaded', function() {
    // Fetch dashboard data
    fetchDashboardData();

    // Set up auto-refresh based on configuration
    setupAutoRefresh();

    // Add event listener for manual refresh button
    const manualRefreshBtn = document.getElementById('manual-refresh');
    if (manualRefreshBtn) {
        manualRefreshBtn.addEventListener('click', function() {
            console.log("Manual refresh clicked");
            fetchDashboardData();
        });
    }
});

// Set up auto-refresh based on server configuration
function setupAutoRefresh() {
    // Get refresh interval from data attribute (in seconds)
    const refreshInterval = parseInt(document.body.dataset.refreshInterval || '3600');

    if (refreshInterval > 0) {
        console.log(`Setting up dashboard auto-refresh every ${refreshInterval} seconds`);

        // Convert to milliseconds
        const refreshMs = refreshInterval * 1000;

        // Set up the refresh timer
        setInterval(function() {
            console.log('Auto-refreshing dashboard data...');
            fetchDashboardData();
        }, refreshMs);
    }
}

// Fetch dashboard data from the API
function fetchDashboardData() {
    console.log("Fetching dashboard data...");

    // Show loading indicator
    const refreshBtn = document.getElementById('manual-refresh');
    if (refreshBtn) {
        refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
        refreshBtn.disabled = true;
    }

    fetch('/api/dashboard/data')
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                console.log("Dashboard data fetched successfully");
                // Store the refresh interval in a data attribute
                if (result.data.refresh_interval) {
                    document.body.dataset.refreshInterval = result.data.refresh_interval;
                }

                // Store the latest analysis timestamp in a data attribute
                if (result.data.latest_timestamp) {
                    document.body.dataset.latestAnalysis = result.data.latest_timestamp;
                    console.log("Latest analysis timestamp:", result.data.latest_timestamp);
                }

                // Initialize charts with the data
                initTimeSpentChart(result.data.time_series);

                // Explicitly log the open tasks data
                console.log("Open tasks data from API:", result.data.open_tasks_data);
                initOpenTasksChart(result.data.open_tasks_data);

                // Update dashboard summary if needed
                if (result.data.latest_data) {
                    updateDashboardSummary(result.data.latest_data);
                }

                // Update last refresh time
                updateLastRefreshTime();
            } else {
                console.error('Error fetching dashboard data:', result.error);
                // Initialize charts with empty data
                initTimeSpentChart(null);
                initOpenTasksChart(null);
            }
        })
        .catch(error => {
            console.error('Error fetching dashboard data:', error);
            // Initialize charts with empty data
            initTimeSpentChart(null);
            initOpenTasksChart(null);

            // If API isn't available yet, use fallback data
            useFallbackData();
        })
        .finally(() => {
            // Reset refresh button
            if (refreshBtn) {
                refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i>';
                refreshBtn.disabled = false;
            }
        });
}

// Update last refresh time indicator
function updateLastRefreshTime() {
    const refreshElement = document.getElementById('last-refresh-time');
    if (refreshElement) {
        const now = new Date();
        const timeString = now.toLocaleTimeString();
        refreshElement.textContent = timeString;
    }
}

// Use fallback data if API isn't available yet
function useFallbackData() {
    // Get budget from the progress element data attribute
    const progressElement = document.querySelector('.progress');
    const budget = progressElement ? parseInt(progressElement.dataset.budget) || 18000 : 18000;

    // Calculate fallback data
    const today = new Date();
    const labels = [];
    const actualData = [];
    const projectedData = [];

    // Generate data for the past 30 days
    for (let i = 30; i >= 0; i--) {
        const date = new Date(today);
        date.setDate(date.getDate() - i);

        // Format date as YYYY-MM-DD
        const dateStr = date.toISOString().split('T')[0];
        labels.push(dateStr);

        // Generate some random actual time spent data (increasing trend)
        const actual = Math.round(500 + i * 20 + Math.random() * 50);
        actualData.push(actual);

        // Calculate projected time spent based on fixed budget of 18000
        // Project duration = 365 days (2025)
        const daysInYear = 365;
        const daysPassed = Math.min(31 + 28 + 31 + 30 + 31 + 30 + 31 + 31 + 30 + 31 + date.getDate(), 365);
        const projected = Math.round((budget / daysInYear) * daysPassed);
        projectedData.push(projected);
    }

    // Initialize charts with fallback data
    initTimeSpentChart({
        dates: labels,
        actual_time_spent: actualData,
        projected_time_spent: projectedData
    });

    // Fallback open tasks data
    const openTasksData = {
        'NBSSPORTAL': 15,
        'UDB': 10,
        'CHM': 7,
        'NUS': 5,
        'ATS': 3
    };
    initOpenTasksChart(openTasksData);

    // Update summary with fallback data
    updateDashboardSummary({
        total_time_spent_days: actualData[actualData.length - 1],
        projected_time_spent_days: projectedData[projectedData.length - 1]
    });

    // Update last refresh time
    updateLastRefreshTime();
}

// Initialize time spent chart
function initTimeSpentChart(timeSeriesData) {
    const ctx = document.getElementById('timeSpentChart').getContext('2d');

    // Get budget from the progress element
    const progressElement = document.querySelector('.progress');
    const totalBudget = progressElement ? parseInt(progressElement.dataset.budget) || 18000 : 18000;
    console.log(`Using total budget: ${totalBudget} for projections`);

    // Default empty data
    let labels = [];
    let actualData = [];
    let projectedData = [];
    let forecastData = [];
    let forecastLabels = [];

    // Use real data if available
    if (timeSeriesData && timeSeriesData.dates && timeSeriesData.dates.length > 0) {
        labels = timeSeriesData.dates;
        actualData = timeSeriesData.actual_time_spent;
        projectedData = timeSeriesData.projected_time_spent;

        // Calculate trend for forecast to the end of 2025
        if (actualData.length >= 2) {
            // Calculate average daily rate of change using linear regression
            // This is more robust than simple differences
            const xValues = [];
            const yValues = [];

            // Convert dates to numerical values (days since first date)
            const firstDate = new Date(labels[0]);
            for (let i = 0; i < labels.length; i++) {
                const currentDate = new Date(labels[i]);
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

            const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
            const intercept = (sumY - slope * sumX) / n;

            console.log(`Linear regression: y = ${slope.toFixed(2)}x + ${intercept.toFixed(2)}`);

            // Create forecast data through the end of 2025
            if (slope > 0) {  // Only forecast if we have a positive trend
                // Start from the last actual data point
                const lastActualDate = new Date(labels[labels.length - 1]);
                const lastActualValue = actualData[actualData.length - 1];

                // End date (December 31, 2025)
                const endDate = new Date('2025-12-31');

                // Generate forecast data points
                let currentDate = new Date(lastActualDate);

                // Copy the last actual data point to start the forecast
                forecastLabels.push(labels[labels.length - 1]);
                forecastData.push(lastActualValue);

                // Advance to the next day
                currentDate.setDate(currentDate.getDate() + 1);

                while (currentDate <= endDate) {
                    const dateStr = currentDate.toISOString().split('T')[0];

                    // Calculate forecast value using the regression model
                    const daysSinceFirst = Math.round((currentDate - firstDate) / (1000 * 60 * 60 * 24));
                    const forecastValue = slope * daysSinceFirst + intercept;

                    forecastLabels.push(dateStr);
                    forecastData.push(forecastValue);

                    // For performance reasons, add weekly points instead of daily for long forecasts
                    currentDate.setDate(currentDate.getDate() + 7);
                }
            }
        }
    }

    // Prepare final data for the chart
    // We need to combine the actual data with the forecast
    // For the forecast dataset, we'll have null values for the historical period
    // and then the forecast values for the future period

    // Create a combined labels array (avoiding duplicates)
    const combinedLabels = [...labels];

    // Add future dates from forecast (excluding the first one which overlaps)
    for (let i = 1; i < forecastLabels.length; i++) {
        combinedLabels.push(forecastLabels[i]);
    }

    // Create datasets
    const datasets = [
        {
            label: 'Фактические трудозатраты',
            data: [...actualData, ...Array(forecastLabels.length - 1).fill(null)],
            backgroundColor: 'rgba(255, 99, 132, 0.2)',
            borderColor: 'rgba(255, 99, 132, 1)',
            borderWidth: 1,
            pointBackgroundColor: 'rgba(255, 99, 132, 1)',
            pointBorderColor: '#fff',
            pointRadius: 5,
            pointHoverRadius: 7
        }
    ];

    // Add projected time spent based on budget - STARTING FROM JAN 1, 2025
    // Create new array for budget-based projected time spent
    const budgetProjectedData = [];

    if (combinedLabels.length > 0) {
        // Start date for projection (Jan 1, 2025)
        const startDate = new Date('2025-01-01');
        // End date for the project (Dec 31, 2025)
        const endDate = new Date('2025-12-31');

        // Calculate total days in 2025
        const totalDays = Math.round((endDate - startDate) / (1000 * 60 * 60 * 24)) + 1; // +1 to include Dec 31

        // For each date, calculate expected spend based on linear budget consumption
        for (let i = 0; i < combinedLabels.length; i++) {
            const currentDate = new Date(combinedLabels[i]);

            // If date is before 2025, use null (no projection data)
            if (currentDate < startDate) {
                budgetProjectedData.push(null);
            } else if (currentDate > endDate) {
                // If date is after 2025, use the full budget
                budgetProjectedData.push(totalBudget);
            } else {
                // Calculate days passed since Jan 1, 2025
                const daysPassed = Math.round((currentDate - startDate) / (1000 * 60 * 60 * 24)) + 1; // +1 to include Jan 1

                // Linear projection based on 18000 budget and days in 2025
                const projected = (totalBudget / totalDays) * daysPassed;
                budgetProjectedData.push(projected);
            }
        }

        // Add the budget-based projection to datasets
        datasets.push({
            label: 'Прогнозные трудозатраты',
            data: budgetProjectedData,
            backgroundColor: 'rgba(54, 162, 235, 0.2)',
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 1,
            pointBackgroundColor: 'rgba(54, 162, 235, 1)',
            pointBorderColor: '#fff',
            pointRadius: 0, // No points to reduce visual clutter
            pointHoverRadius: 7
        });
    } else if (projectedData.length > 0) {
        // Fallback to original projected data if no combined labels
        datasets.push({
            label: 'Прогнозные трудозатраты',
            data: [...projectedData, ...Array(forecastLabels.length - 1).fill(null)],
            backgroundColor: 'rgba(54, 162, 235, 0.2)',
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 1,
            pointBackgroundColor: 'rgba(54, 162, 235, 1)',
            pointBorderColor: '#fff',
            pointRadius: 5,
            pointHoverRadius: 7
        });
    }

    // Add forecast dataset if we have forecast data
    if (forecastData.length > 0) {
        // Create an array of nulls for historical period except the last point
        const forecastDataWithNulls = Array(actualData.length - 1).fill(null);
        // Add the actual forecast data
        forecastDataWithNulls.push(...forecastData);

        datasets.push({
            label: 'Прогноз до конца 2025',
            data: forecastDataWithNulls,
            backgroundColor: 'rgba(75, 192, 192, 0.2)',
            borderColor: 'rgba(75, 192, 192, 1)',
            borderWidth: 1,
            borderDash: [5, 5], // Dashed line for forecast
            pointRadius: 0, // No points for the forecast line
            pointHoverRadius: 3,
            fill: false // Don't fill area under the line
        });
    }

    const timeSpentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: combinedLabels,
            datasets: datasets
        },
        options: {
            responsive: true,
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Дата'
                    },
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45,
                        // Show fewer ticks for readability with extended dates
                        maxTicksLimit: 20
                    }
                },
                y: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Человекодни'
                    },
                    beginAtZero: true
                }
            },
            plugins: {
                tooltip: {
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
                        boxWidth: 10
                    }
                }
            },
            onClick: function(e, elements) {
                if (elements.length > 0) {
                    const index = elements[0].index;
                    const date = combinedLabels[index];

                    // Format date to folder format (YYYYMMDD)
                    const dateObj = new Date(date);
                    const year = dateObj.getFullYear();
                    const month = String(dateObj.getMonth() + 1).padStart(2, '0');
                    const day = String(dateObj.getDate()).padStart(2, '0');
                    const folderDate = `${year}${month}${day}`;

                    console.log(`Clicked on date ${date}, folder date: ${folderDate}`);

                    // Only navigate if we have data for this date (not a future date)
                    if (index < labels.length) {
                        // Navigate to the dashboard view for this date
                        window.location.href = `/view/dashboard/${folderDate}`;
                    }
                }
            }
        }
    });
}

/// Initialize open tasks chart
function initOpenTasksChart(openTasksData) {
    console.log("Initializing open tasks chart with data:", openTasksData);
    const chartElement = document.getElementById('openTasksChart');

    // Exit if chart element is not found
    if (!chartElement) {
        console.error("Open tasks chart element not found!");
        return;
    }

    // Get context (using try-catch to handle potential errors)
    let ctx;
    try {
        ctx = chartElement.getContext('2d');
    } catch (error) {
        console.error("Error getting chart context:", error);
        return;
    }

    // Default empty data
    let labels = [];
    let data = [];

    // Validate the openTasksData structure carefully
    const isValidData = openTasksData &&
                      typeof openTasksData === 'object' &&
                      !Array.isArray(openTasksData) &&
                      openTasksData !== null &&
                      Object.keys(openTasksData).length > 0;

    console.log("Is open tasks data valid?", isValidData);

    // Use real data if available and valid
    if (isValidData) {
        console.log("Using real open tasks data, keys:", Object.keys(openTasksData));

        try {
            // Convert object to entries and sort by value (descending)
            const entries = Object.entries(openTasksData);
            console.log("Data entries:", entries);

            if (entries.length > 0) {
                // Sort projects by hours spent (descending)
                const sortedProjects = entries.sort((a, b) => b[1] - a[1]);
                console.log("Sorted projects:", sortedProjects);

                // Use ALL projects - don't limit to 20 or any number
                labels = sortedProjects.map(item => item[0]);
                data = sortedProjects.map(item => typeof item[1] === 'number' ? item[1] : 0);

                console.log(`Final labels (${labels.length} projects):`, labels);
                console.log(`Final data:`, data);
            } else {
                console.log("No entries in openTasksData, using fallback");
                // Fall back to defaults if no entries
                labels = ['TUDS', 'DMS', 'UMNP', 'NBSSPORTAL', 'GUS', 'CSM', 'SSO', 'UDB', 'CHM', 'LIS', 'APC'];
                data = [2671, 1879, 443, 374, 133, 115, 93, 32, 21, 9, 5];
            }
        } catch (error) {
            console.error("Error processing open tasks data:", error);
            // Fall back to defaults if processing fails
            labels = ['TUDS', 'DMS', 'UMNP', 'NBSSPORTAL', 'GUS', 'CSM', 'SSO', 'UDB', 'CHM', 'LIS', 'APC'];
            data = [2671, 1879, 443, 374, 133, 115, 93, 32, 21, 9, 5];
        }
    } else {
        console.log("Using fallback data for open tasks chart");
        // Use fallback data if no real data is available
        labels = ['TUDS', 'DMS', 'UMNP', 'NBSSPORTAL', 'GUS', 'CSM', 'SSO', 'UDB', 'CHM', 'LIS', 'APC'];
        data = [2671, 1879, 443, 374, 133, 115, 93, 32, 21, 9, 5];
    }

    // Generate colors for each bar
    const colors = generateColors(labels.length);

    const chartData = {
        labels: labels,
        datasets: [{
            label: 'Затраченные часы',
            data: data,
            backgroundColor: colors.background,
            borderColor: colors.border,
            borderWidth: 1
        }]
    };

    // Check if there's an existing chart and destroy it
    if (chartElement.chart instanceof Chart) {
        chartElement.chart.destroy();
    }

    try {
        // Create new chart and store reference on the element
        chartElement.chart = new Chart(ctx, {
            type: 'bar',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Проект'
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Часы'
                        },
                        beginAtZero: true
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const value = context.parsed.y;
                                return `Затраченное время: ${value.toFixed(1)} ч.`;
                            }
                        }
                    }
                },
                onClick: function(e, elements) {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const project = chartData.labels[index];

                        // Create JQL query for open tasks in this project
                        createOpenTasksJQL(project);
                    }
                }
            }
        });
        console.log("Open tasks chart created successfully");
    } catch (error) {
        console.error("Error creating open tasks chart:", error);
    }
}

// Helper function to generate colors for chart bars
function generateColors(count) {
    const background = [];
    const border = [];

    // Use a predefined palette for better visual appeal
    const colorPalette = [
        { bg: 'rgba(255, 99, 132, 0.7)', border: 'rgba(255, 99, 132, 1)' },    // Red
        { bg: 'rgba(54, 162, 235, 0.7)', border: 'rgba(54, 162, 235, 1)' },    // Blue
        { bg: 'rgba(255, 206, 86, 0.7)', border: 'rgba(255, 206, 86, 1)' },    // Yellow
        { bg: 'rgba(75, 192, 192, 0.7)', border: 'rgba(75, 192, 192, 1)' },    // Green
        { bg: 'rgba(153, 102, 255, 0.7)', border: 'rgba(153, 102, 255, 1)' },  // Purple
        { bg: 'rgba(255, 159, 64, 0.7)', border: 'rgba(255, 159, 64, 1)' },    // Orange
        { bg: 'rgba(199, 199, 199, 0.7)', border: 'rgba(199, 199, 199, 1)' },  // Gray
        { bg: 'rgba(83, 102, 255, 0.7)', border: 'rgba(83, 102, 255, 1)' },    // Light Purple
        { bg: 'rgba(255, 99, 255, 0.7)', border: 'rgba(255, 99, 255, 1)' },    // Pink
        { bg: 'rgba(99, 255, 132, 0.7)', border: 'rgba(99, 255, 132, 1)' }     // Light Green
    ];

    // If we need more colors than in our palette, generate them
    if (count <= colorPalette.length) {
        // Use colors from palette
        for (let i = 0; i < count; i++) {
            background.push(colorPalette[i].bg);
            border.push(colorPalette[i].border);
        }
    } else {
        // Use palette colors first
        for (let i = 0; i < colorPalette.length; i++) {
            background.push(colorPalette[i].bg);
            border.push(colorPalette[i].border);
        }

        // Generate additional colors using HSL for good distribution
        for (let i = colorPalette.length; i < count; i++) {
            const hue = (i * 137) % 360; // Golden angle provides good distribution
            background.push(`hsla(${hue}, 70%, 60%, 0.7)`);
            border.push(`hsla(${hue}, 70%, 60%, 1)`);
        }
    }

    return { background, border };
}

// Create JQL query for open tasks in a project
function createOpenTasksJQL(project) {
    // Get the timestamp from the latest dashboard data - should be in format YYYYMMDD for dashboard data
    const timestamp = document.body.getAttribute('data-latest-analysis') || '';

    console.log(`Creating open tasks JQL for project: ${project}, using timestamp: ${timestamp}`);

    // Create request to get JQL query for open tasks in this project
    fetch(`/jql/special?project=${encodeURIComponent(project)}&chart_type=open_tasks&is_clm=true&timestamp=${timestamp}`)
        .then(response => response.json())
        .then(data => {
            console.log("Received JQL:", data.jql);

            // Fill modal dialog
            document.getElementById('jqlQuery').value = data.jql;
            document.getElementById('openJiraBtn').href = data.url;

            // Show modal dialog
            const bsJqlModal = new bootstrap.Modal(document.getElementById('jqlModal'));
            bsJqlModal.show();
        })
        .catch(error => {
            console.error('Error generating JQL:', error);
            alert('Error creating JQL query: ' + error.message);
        });
}

// Update dashboard summary with latest data
function updateDashboardSummary(latestData) {
    // If we have summary elements on the page, update them
    const actualElement = document.getElementById('actual-time-spent');
    if (actualElement) {
        actualElement.textContent = Math.round(latestData.total_time_spent_days).toLocaleString();
    }

    // Get the budget from the progress element
    const progressElement = document.getElementById('time-progress');
    const budget = progressElement ?
        parseInt(progressElement.closest('.progress').dataset.budget) || 18000 :
        18000;

    // Calculate our own projected value based on current date and 2025 timeline
    const projectedElement = document.getElementById('projected-time-spent');
    if (projectedElement) {
        // Today's date
        const today = new Date();

        // Start date for project (Jan 1, 2025)
        const startDate = new Date('2025-01-01');

        // End date for project (Dec 31, 2025)
        const endDate = new Date('2025-12-31');

        // Total days in 2025
        const totalDays = 365; // Fixed to avoid issues with date calculation

        let projectedValue;

        // If date is before 2025, projected value is 0
        if (today < startDate) {
            projectedValue = 0;
        }
        // If date is after 2025, projected value is the full budget
        else if (today > endDate) {
            projectedValue = budget;
        }
        // Calculate based on days passed in 2025
        else {
            // Calculate days passed in 2025
            const daysPassed = Math.floor((today - startDate) / (1000 * 60 * 60 * 24)) + 1;

            // Calculate projected value based on linear progression
            projectedValue = Math.round((budget / totalDays) * daysPassed);
        }

        // Update the element with our calculated value
        projectedElement.textContent = projectedValue.toLocaleString();

        // Log the calculation details
        console.log(`Projected value calculation: ${projectedValue} based on ${budget} budget`);
        console.log(`Date info: Today=${today.toISOString().split('T')[0]}, startDate=2025-01-01, using ${totalDays} days`);
    }

    // Recalculate the difference based on our newly calculated projected value
    const differenceElement = document.getElementById('time-difference');
    if (differenceElement && actualElement && projectedElement) {
        // Extract values from the displayed text (which now has our corrected calculation)
        const actualValue = parseInt(actualElement.textContent.replace(/,/g, '')) || 0;
        const projectedValue = parseInt(projectedElement.textContent.replace(/,/g, '')) || 0;

        // Calculate difference
        const difference = projectedValue - actualValue;
        differenceElement.textContent = Math.round(difference).toLocaleString();

        // Add class based on difference
        if (difference > 0) {
            differenceElement.classList.add('text-success');
            differenceElement.classList.remove('text-danger');
        } else {
            differenceElement.classList.add('text-danger');
            differenceElement.classList.remove('text-success');
        }

        console.log(`Difference calculation: ${difference} (${projectedValue} - ${actualValue})`);
    }

    // Update progress bar
    if (progressElement) {
        // Get actual value for progress calculation
        const actualValue = latestData.total_time_spent_days || 0;
        const progress = (actualValue / budget) * 100;
        progressElement.style.width = `${progress}%`;
        progressElement.textContent = `${Math.round(progress)}%`;

        console.log(`Progress bar: ${progress.toFixed(2)}% (${actualValue}/${budget})`);
    }
}