// charts/timeSpentChart.js - Time spent chart functionality
import { formatDateForFolder, getProjectBudget } from '../utils.js';

// Store original data for click handlers
window.originalTimeSeriesData = {
    dates: [],
    actualData: []
};

/**
 * Initialize time spent chart with data
 * @param {Object} timeSeriesData - Time series data
 */
function initTimeSpentChart(timeSeriesData) {
    // Store the time series data for later reference
    window.timeSeriesData = timeSeriesData;

    // Update or create the chart
    updateTimeSpentChart(timeSeriesData);
}

/**
 * Update time spent chart with new data
 * @param {Object} timeSeriesData - Time series data
 */
function updateTimeSpentChart(timeSeriesData) {
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

/**
 * Handle time spent chart click
 * @param {Event} event - Click event
 * @param {Array} elements - Active chart elements
 */
function handleTimeSpentChartClick(event, elements) {
    if (!elements || !elements.length) return;

    // Get the clicked element
    const index = elements[0].index;
    handlePointClick(index);
}

/**
 * Handle point click on the chart
 * @param {number} index - Index of the clicked point
 */
function handlePointClick(index) {
    // Map back to original data index if we're using the date index map
    const originalIndex = window.dateIndexMap ? window.dateIndexMap[index] : index;

    // Check if we have the original data
    if (window.timeSeriesData && window.timeSeriesData.dates && originalIndex !== undefined) {
        // Check if we clicked on an actual data point (not forecast)
        if (originalIndex < window.timeSeriesData.dates.length) {
            const clickedDate = window.timeSeriesData.dates[originalIndex];

            // Get the timestamp for folder navigation
            try {
                const folderDate = formatDateForFolder(clickedDate);
                console.log(`Clicked on date ${clickedDate}, navigating to folder ${folderDate}`);

                // Navigate to the detailed view for this date
                window.location.href = `/view/dashboard/${folderDate}`;
            } catch (error) {
                console.error("Error processing chart click:", error);
            }
        } else {
            console.log("Clicked on forecast data point, no navigation");
        }
    } else {
        console.warn("No time series data available for click handling");
    }
}

/**
 * Create extended forecast data that makes all lines go to end of 2025
 * @param {Array} dates - Array of date strings
 * @param {Array} actualData - Array of actual data points
 * @param {Array} projectedData - Array of projected data points
 * @returns {Object} Extended forecast data
 */
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

export { initTimeSpentChart, updateTimeSpentChart };