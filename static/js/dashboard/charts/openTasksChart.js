// charts/openTasksChart.js - Open tasks chart functionality
import { createColorSet } from '../utils.js';
import { createOpenTasksJQL } from '../api.js';

/**
 * Initialize open tasks chart with data
 * @param {Object} openTasksData - Open tasks data
 * @param {string} timestampStr - Timestamp string
 */
function initOpenTasksChart(openTasksData, timestampStr) {
    // Update or create the chart
    updateOpenTasksChart(openTasksData, timestampStr);
}

/**
 * Update open tasks chart with new data
 * @param {Object} openTasksData - Open tasks data
 * @param {string} timestampStr - Timestamp string
 */
function updateOpenTasksChart(openTasksData, timestampStr) {
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

        // Create colors for chart
        const colors = createColorSet(projects.length);

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
                    handleOpenTasksChartClick(e, elements, projects, timestampStr);
                }
            }
        });

        console.log("Open tasks chart created successfully");
    } catch (error) {
        console.error("Error creating open tasks chart:", error);
    }
}

/**
 * Handle open tasks chart click
 * @param {Event} event - Click event
 * @param {Array} elements - Active chart elements
 * @param {Array} projects - Array of project names
 * @param {string} timestampStr - Timestamp string
 */
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

export { initOpenTasksChart, updateOpenTasksChart };