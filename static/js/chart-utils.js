/**
 * Utility functions for chart creation and manipulation
 */

// Generate a set of colors for chart elements
export function getChartColors(count) {
    const colors = [];
    for (let i = 0; i < count; i++) {
        // Cycle through colors using golden angle for even distribution
        const hue = (i * 137) % 360;
        colors.push(`hsla(${hue}, 70%, 60%, 0.7)`);
    }
    return colors;
}

// Create a special JQL query for chart segments
export function createSpecialJQL(project, chartType, withoutPeriod = false) {
    // Basic parameters
    const params = new URLSearchParams();
    const dateFrom = !withoutPeriod ? document.querySelector('[data-date-from]')?.getAttribute('data-date-from') : null;
    const dateTo = !withoutPeriod ? document.querySelector('[data-date-to]')?.getAttribute('data-date-to') : null;
    const baseJql = document.querySelector('[data-base-jql]')?.getAttribute('data-base-jql');
    const isClm = document.querySelector('[data-source="clm"]') ? 'true' : 'false';

    // Add timestamp for accessing saved data
    const timestamp = document.querySelector('[data-timestamp]')?.getAttribute('data-timestamp') ||
                    window.location.pathname.split('/').pop();

    // Ensure project is properly encoded
    params.append('project', encodeURIComponent(project));
    params.append('chart_type', chartType);
    params.append('is_clm', isClm);
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);
    if (baseJql) params.append('base_jql', baseJql);
    if (timestamp) params.append('timestamp', timestamp);
    params.append('ignore_period', withoutPeriod ? 'true' : 'false');

    console.log(`Creating special JQL for project: ${project}, chart type: ${chartType}, timestamp: ${timestamp}, ignore_period: ${withoutPeriod}`);

    // Request JQL from server
    fetch(`/jql/special?${params.toString()}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
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
            console.error('Error generating special JQL:', error);
            alert('Ошибка при формировании JQL запроса: ' + error.message);

            // If error occurs, use regular link
            if (typeof createJiraLink === 'function') {
                createJiraLink(project);
            }
        });
}

// Common chart options used across multiple charts
export const commonChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
        y: {
            beginAtZero: true
        },
        x: {
            ticks: {
                maxRotation: 45,
                minRotation: 45
            }
        }
    },
    layout: {
        padding: {
            left: 10,
            right: 10,
            top: 0,
            bottom: 20
        }
    },
    plugins: {
        legend: {
            position: 'top',
            labels: {
                boxWidth: 15,
                padding: 10
            }
        }
    }
};

// Handle chart clicks based on chart type
export function handleChartClick(event, chartType, activeElements, chart) {
    if (activeElements.length === 0) return;

    const index = activeElements[0].index;
    const project = chart.data.labels[index];
    console.log(`Chart click: ${chartType}, Project: ${project}`);

    if (chartType === 'no_transitions') {
        // For "Открытые задачи со списаниями" chart
        const isClmAnalysis = !!document.querySelector('[data-source="clm"]');
        const withoutPeriod = isClmAnalysis ? document.getElementById('withoutPeriod')?.checked || false : false;
        createSpecialJQL(project, 'open_tasks', withoutPeriod);
    } else {
        // For standard charts use regular link
        if (typeof createJiraLink === 'function') {
            // Ensure project is properly encoded
            createJiraLink(project);
        } else {
            console.error("createJiraLink function not found");
        }
    }
}

// Deep copy an object to avoid reference issues
export function deepCopy(obj) {
    return JSON.parse(JSON.stringify(obj));
}

// Extract query parameters from URL
export function getQueryParams() {
    const params = new URLSearchParams(window.location.search);
    return Object.fromEntries(params);
}