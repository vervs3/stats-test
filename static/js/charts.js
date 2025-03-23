/**
 * Main Charts Module - Initializes and coordinates all charts
 */
import { loadChartData, loadFullClmData, restoreFilteredData, getIsInitialData } from './data-manager.js';
import { initComparisonChart } from './comparison-chart.js';
import { initProjectsPieChart } from './projects-pie-chart.js';
import { initOpenTasksChart } from './open-tasks-chart.js';
import { initClmSummaryChart } from './clm-summary-chart.js';

// Initialize charts when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Load chart data
    const chartData = loadChartData();
    if (!chartData) {
        return; // Exit if no data
    }

    // Initialize chart modules
    const { updateChart, getFullProjectsList, updateFullProjectsList } = initComparisonChart(chartData) || {};
    const { recreateChart: recreatePieChart } = initProjectsPieChart(chartData) || {};
    initOpenTasksChart(chartData);
    initClmSummaryChart();

    // Setup callbacks for data manager
    const callbacks = {
        updateChart,
        recreatePieChart,
        getFullProjectsList,
        updateFullProjectsList
    };

    // Setup period toggle handlers for CLM mode
    if (chartData.data_source === 'clm') {
        setupPeriodToggles(chartData, callbacks);
    }
});

// Setup toggle handlers for CLM mode
function setupPeriodToggles(chartData, callbacks) {
    // Get the main toggle radio buttons
    const periodRadios = document.querySelectorAll('input[name="periodMode"]');
    if (periodRadios.length === 0) return;

    // Add event handler for main toggle
    periodRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            const withoutPeriod = this.value === 'withoutPeriod';
            handlePeriodChange(withoutPeriod, chartData, callbacks);
        });
    });

    // Get the pie-specific toggle radio buttons
    const piePeriodRadios = document.querySelectorAll('input[name="piePeriodMode"]');
    if (piePeriodRadios.length === 0) return;

    // Add event handler for pie toggle
    piePeriodRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            const withoutPeriod = this.value === 'withoutPeriod';

            // Sync the main toggle
            const mainPeriodToggle = document.getElementById(withoutPeriod ? 'withoutPeriod' : 'withPeriod');
            if (mainPeriodToggle && !mainPeriodToggle.checked) {
                // Change main toggle programmatically
                mainPeriodToggle.checked = true;

                // Trigger the period change manually
                handlePeriodChange(withoutPeriod, chartData, callbacks);
            } else if (mainPeriodToggle && mainPeriodToggle.checked) {
                // If toggles are already in sync, just update the pie chart
                if (callbacks.recreatePieChart) {
                    setTimeout(() => callbacks.recreatePieChart(), 300);
                }

                // Hide the pie loading indicator
                const pieLoadingIndicator = document.getElementById('pie-period-loading');
                if (pieLoadingIndicator) {
                    pieLoadingIndicator.style.display = 'none';
                }
            }
        });
    });

    // Listen to changes on the main toggle to keep pie toggle in sync
    periodRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            const withoutPeriod = this.value === 'withoutPeriod';

            // Sync the pie toggle
            const piePeriodToggle = document.getElementById(withoutPeriod ? 'pieWithoutPeriod' : 'pieWithPeriod');
            if (piePeriodToggle && !piePeriodToggle.checked) {
                piePeriodToggle.checked = true;
            }

            // Hide the pie loading indicator after a delay
            setTimeout(() => {
                const pieLoadingIndicator = document.getElementById('pie-period-loading');
                if (pieLoadingIndicator) {
                    pieLoadingIndicator.style.display = 'none';
                }
            }, 500);
        });
    });
}

// Handle period toggle changes
function handlePeriodChange(withoutPeriod, chartData, callbacks) {
    const timestamp = document.querySelector('[data-timestamp]')?.getAttribute('data-timestamp') ||
                     window.location.pathname.split('/').pop();

    if (withoutPeriod && getIsInitialData()) {
        // Load full CLM data
        loadFullClmData(chartData, timestamp, callbacks);
    } else if (!withoutPeriod && !getIsInitialData()) {
        // Restore filtered data
        restoreFilteredData(chartData, callbacks);
    } else {
        // No data change needed
        console.log("No data change needed, already in the right mode.");

        // Hide loading indicators
        const mainLoadingIndicator = document.getElementById('period-loading');
        if (mainLoadingIndicator) {
            mainLoadingIndicator.style.display = 'none';
        }
        const pieLoadingIndicator = document.getElementById('pie-period-loading');
        if (pieLoadingIndicator) {
            pieLoadingIndicator.style.display = 'none';
        }
    }
}