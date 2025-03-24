// Initialize dashboard charts
document.addEventListener('DOMContentLoaded', function() {
    // Fetch dashboard data
    fetchDashboardData();
});

// Fetch dashboard data from the API
function fetchDashboardData() {
    fetch('/api/dashboard/data')
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                // Initialize charts with the data
                initTimeSpentChart(result.data.time_series);
                initOpenTasksChart(result.data.open_tasks_data);

                // Update dashboard summary if needed
                if (result.data.latest_data) {
                    updateDashboardSummary(result.data.latest_data);
                }
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
        });
}

// Use fallback data if API isn't available yet
function useFallbackData() {
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

        // Calculate projected time spent
        // Budget = 23000 person-days, project duration = 365 days (2025)

        const daysInYear = 365;
        const budget = PROJECT_BUDGET;
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
        'Project A': 12,
        'Project B': 19,
        'Project C': 8,
        'Project D': 15,
        'Project E': 7
    };
    initOpenTasksChart(openTasksData);

    // Update summary with fallback data
    updateDashboardSummary({
        total_time_spent_days: actualData[actualData.length - 1],
        projected_time_spent_days: projectedData[projectedData.length - 1]
    });
}

// Initialize time spent chart
function initTimeSpentChart(timeSeriesData) {
    const ctx = document.getElementById('timeSpentChart').getContext('2d');

    // Default empty data
    let labels = [];
    let actualData = [];
    let projectedData = [];

    // Use real data if available
    if (timeSeriesData && timeSeriesData.dates && timeSeriesData.dates.length > 0) {
        labels = timeSeriesData.dates;
        actualData = timeSeriesData.actual_time_spent;
        projectedData = timeSeriesData.projected_time_spent;
    }

    const data = {
        labels: labels,
        datasets: [
            {
                label: 'Фактические трудозатраты',
                data: actualData,
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                borderColor: 'rgba(255, 99, 132, 1)',
                borderWidth: 1,
                pointBackgroundColor: 'rgba(255, 99, 132, 1)',
                pointBorderColor: '#fff',
                pointRadius: 5,
                pointHoverRadius: 7
            },
            {
                label: 'Прогнозные трудозатраты',
                data: projectedData,
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1,
                pointBackgroundColor: 'rgba(54, 162, 235, 1)',
                pointBorderColor: '#fff',
                pointRadius: 5,
                pointHoverRadius: 7
            }
        ]
    };

    const timeSpentChart = new Chart(ctx, {
        type: 'line',
        data: data,
        options: {
            responsive: true,
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Дата'
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
                            return `${label}: ${value.toFixed(0)} человекодней`;
                        }
                    }
                }
            },
            onClick: function(e, elements) {
                if (elements.length > 0) {
                    const index = elements[0].index;
                    const date = data.labels[index];
                    // Navigate to the detailed view for this date
                    console.log(`Clicked on ${date}`);

                    // For now, let's just navigate to the index page
                    window.location.href = '/?date_from=' + date + '&date_to=' + date;
                }
            }
        }
    });
}

// Initialize open tasks chart
function initOpenTasksChart(openTasksData) {
    const ctx = document.getElementById('openTasksChart').getContext('2d');

    // Default empty data
    let labels = [];
    let data = [];

    // Use real data if available
    if (openTasksData && Object.keys(openTasksData).length > 0) {
        // Sort projects by number of open tasks (descending)
        const sortedProjects = Object.entries(openTasksData)
            .sort((a, b) => b[1] - a[1]);

        // Take top 20 projects
        const topProjects = sortedProjects.slice(0, 20);

        labels = topProjects.map(item => item[0]);
        data = topProjects.map(item => item[1]);
    }

    // Generate colors for each bar
    const colors = generateColors(labels.length);

    const chartData = {
        labels: labels,
        datasets: [{
            label: 'Количество открытых задач',
            data: data,
            backgroundColor: colors.background,
            borderColor: colors.border,
            borderWidth: 1
        }]
    };

    const openTasksChart = new Chart(ctx, {
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
                        text: 'Количество задач'
                    },
                    beginAtZero: true
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
    // Create request to get JQL query for open tasks in this project
    fetch(`/jql/special?project=${encodeURIComponent(project)}&chart_type=open_tasks`)
        .then(response => response.json())
        .then(data => {
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

    const projectedElement = document.getElementById('projected-time-spent');
    if (projectedElement) {
        projectedElement.textContent = Math.round(latestData.projected_time_spent_days).toLocaleString();
    }

    const differenceElement = document.getElementById('time-difference');
    if (differenceElement) {
        const difference = latestData.projected_time_spent_days - latestData.total_time_spent_days;
        differenceElement.textContent = Math.round(difference).toLocaleString();

        // Add class based on difference
        if (difference > 0) {
            differenceElement.classList.add('text-success');
            differenceElement.classList.remove('text-danger');
        } else {
            differenceElement.classList.add('text-danger');
            differenceElement.classList.remove('text-success');
        }
    }

    const progressElement = document.getElementById('time-progress');
    if (progressElement) {
        // Получаем бюджет из атрибута data-* прогресс-бара или его родителя
        const budget = parseInt(progressElement.closest('.progress').dataset.budget) || 18000;
        const progress = (latestData.total_time_spent_days / budget) * 100;
        progressElement.style.width = `${progress}%`;
        progressElement.textContent = `${Math.round(progress)}%`;
    }
}