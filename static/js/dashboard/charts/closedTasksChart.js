// charts/closedTasksChart.js - Closed tasks chart functionality
import { createColorSet } from '../utils.js';
import { createClosedTasksJQL } from '../api.js';

/**
 * Initialize closed tasks chart with data
 * @param {Object} closedTasksData - Closed tasks data
 * @param {string} timestampStr - Timestamp string
 */
function initClosedTasksChart(closedTasksData, timestampStr) {
    console.log('Initializing closed tasks chart with data:', closedTasksData);

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
        console.warn("Invalid closed tasks data, using empty object");
        closedTasksData = {};
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
        const colors = createColorSet(projects.length || 1);

        // If no timestamp provided, use the one from the DOM
        if (!timestampStr) {
            timestampStr = document.body.dataset.latestTimestamp || '';
        }

        console.log(`Creating closed tasks chart with ${projects.length} projects, timestamp: ${timestampStr}`);

        // Store projects and timestamp for click handler
        const storedProjects = [...projects];
        const storedTimestamp = timestampStr;

        // Create chart options with improved tooltips
        const chartOptions = {
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
                // Важно: передаем сохраненные проекты и timestamp в обработчик клика
                handleClosedTasksChartClick(e, elements, storedProjects, storedTimestamp);
            }
        };

        // If data is empty, show "no data" message
        if (projects.length === 0) {
            window.closedTasksChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['Нет данных'],
                    datasets: [{
                        label: 'Закрытые задачи без комментариев, вложений и связей',
                        data: [0],
                        backgroundColor: colors.background,
                        borderColor: colors.border,
                        borderWidth: 1
                    }]
                },
                options: {
                    ...chartOptions,
                    plugins: {
                        ...chartOptions.plugins,
                        tooltip: {
                            callbacks: {
                                label: function() {
                                    return 'Нет задач';
                                }
                            }
                        }
                    }
                }
            });

            // Add text annotation for empty chart
            ctx.font = '16px Arial';
            ctx.fillStyle = '#666';
            ctx.textAlign = 'center';
            ctx.fillText('Нет закрытых задач без комментариев, вложений и связей', canvas.width / 2, canvas.height / 2);

            console.log("Created empty closed tasks chart");
        } else {
            // Create chart with real data
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
                options: chartOptions
            });

            console.log("Closed tasks chart created successfully with data", values);
        }
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
    // Check if we have clicked elements and projects
    if (!elements || !elements.length || !projects || projects.length === 0) {
        console.log("No valid elements or projects to handle click");
        return;
    }

    // Get clicked element info
    const clickedIndex = elements[0].index;

    // Проверяем, что clickedIndex в пределах массива projects
    if (clickedIndex < 0 || clickedIndex >= projects.length) {
        console.error(`Invalid clickedIndex: ${clickedIndex}, projects array length: ${projects.length}`);
        return;
    }

    const project = projects[clickedIndex];

    console.log(`Closed tasks chart clicked: project=${project}, timestamp=${timestampStr}`);

    // Проверяем, что значение проекта не пустое
    if (!project) {
        console.error("Project value is empty, cannot create JQL");
        return;
    }

    // Create JQL query for this project
    createClosedTasksJQL(project, timestampStr);
}

export { initClosedTasksChart, updateClosedTasksChart };