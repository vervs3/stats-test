// charts/closedTasksChart.js - Closed tasks chart functionality
import { createColorSet } from '../utils.js';
import { createClosedTasksJQL } from '../api.js';

/**
 * Initialize closed tasks chart with data
 * @param {Object} closedTasksData - Closed tasks data
 * @param {string} timestampStr - Timestamp string
 */
function initClosedTasksChart(closedTasksData, timestampStr) {
    // Update or create the chart
    updateClosedTasksChart(closedTasksData, timestampStr);
}

/**
 * Update closed tasks chart with new data
 * @param {Object} closedTasksData - Closed tasks data
 * @param {string} timestampStr - Timestamp string
 */
function updateClosedTasksChart(closedTasksData, timestampStr) {
    // Basic validation
    if (!closedTasksData || typeof closedTasksData !== 'object') {
        console.error("Invalid closed tasks data");
        return;
    }

    // Get canvas element
    const canvas = document.getElementById('closedTasksChart');
    if (!canvas) {
        console.error("Closed tasks chart canvas not found");
        return;
    }

    try {
        // Get canvas context
        const ctx = canvas.getContext('2d');

        // Destroy existing chart if it exists
        if (window.closedTasksChart instanceof Chart) {
            window.closedTasksChart.destroy();
        }

        // Prepare data
        const projects = Object.keys(closedTasksData);
        const values = projects.map(p => closedTasksData[p]);

        // Create colors for chart
        const colors = createColorSet(projects.length);

        // If no timestamp provided, use the one from the DOM
        if (!timestampStr) {
            timestampStr = document.body.dataset.latestTimestamp || '';
        }

        // Create chart
        window.closedTasksChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: projects,
                datasets: [{
                    label: 'Количество задач',
                    data: values,
                    backgroundColor: colors.background,
                    borderColor: colors.border,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Количество задач'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Проект'
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const value = context.parsed.y;
                                return `Количество задач: ${value}`;
                            }
                        }
                    },
                    legend: {
                        position: 'top',
                        labels: {
                            boxWidth: 15,
                            padding: 10
                        }
                    }
                },
                onClick: function(e, elements) {
                    handleClosedTasksChartClick(e, elements, projects, timestampStr);
                }
            }
        });

        console.log("Closed tasks chart created successfully");
    } catch (error) {
        console.error("Error creating closed tasks chart:", error);
    }
}

/**
 * Handle closed tasks chart click
 * @param {Event} event - Click event
 * @param {Array} elements - Active chart elements
 * @param {Array} projects - Array of project names
 * @param {string} timestampStr - Timestamp string
 */
function handleClosedTasksChartClick(event, elements, projects, timestampStr) {
    // Check if we have clicked elements
    if (!elements || !elements.length) return;

    // Get clicked element info
    const clickedIndex = elements[0].index;
    const project = projects[clickedIndex];

    console.log(`Closed tasks chart clicked: project=${project}, timestamp=${timestampStr}`);

    // Create JQL query for this project
    createClosedTasksJQL(project, timestampStr);
}

export { initClosedTasksChart, updateClosedTasksChart };