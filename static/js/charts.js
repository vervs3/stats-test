/**
 * Main Charts Module - Initializes and coordinates all charts
 */
import { loadChartData, loadFullClmData, restoreFilteredData, getIsInitialData } from './data-manager.js';
import { initComparisonChart } from './comparison-chart.js';
import { initProjectsPieChart } from './projects-pie-chart.js';
import { initOpenTasksChart } from './open-tasks-chart.js';
import { initClmSummaryChart } from './clm-summary-chart.js';
import { updateSummaryStatistics } from './summary-updater.js';


// Initialize charts when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Load chart data
    const chartData = loadChartData();
    if (!chartData) {
        return; // Exit if no data
    }

    console.log("Charts initialization - Initial chart data loaded successfully");

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

            console.log(`Main toggle changed to: ${withoutPeriod ? 'All CLM data' : 'Period data'}`);
            handlePeriodChange(withoutPeriod, chartData, callbacks);

            // Ensure pie toggle is synchronized
            const piePeriodToggle = document.getElementById(withoutPeriod ? 'pieWithoutPeriod' : 'pieWithPeriod');
            if (piePeriodToggle && !piePeriodToggle.checked) {
                console.log("Synchronizing pie toggle with main toggle");
                piePeriodToggle.checked = true;
            }
        });
    });

    // Get the pie-specific toggle radio buttons
    const piePeriodRadios = document.querySelectorAll('input[name="piePeriodMode"]');
    if (piePeriodRadios.length === 0) return;

    // Add event handler for pie toggle
    piePeriodRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            const withoutPeriod = this.value === 'withoutPeriod';

            console.log(`Pie toggle changed to: ${withoutPeriod ? 'All CLM data' : 'Period data'}`);

            // Sync the main toggle
            const mainPeriodToggle = document.getElementById(withoutPeriod ? 'withoutPeriod' : 'withPeriod');
            if (mainPeriodToggle && !mainPeriodToggle.checked) {
                console.log("Synchronizing main toggle with pie toggle");
                mainPeriodToggle.checked = true;

                // Trigger the period change manually
                handlePeriodChange(withoutPeriod, chartData, callbacks);
            }
        });
    });
}

// Handle period toggle changes
function handlePeriodChange(withoutPeriod, chartData, callbacks) {
    const timestamp = document.querySelector('[data-timestamp]')?.getAttribute('data-timestamp') ||
                     window.location.pathname.split('/').pop();

    console.log(`Handling period change to ${withoutPeriod ? 'All CLM data' : 'Period data'} mode`);

    // Update indicators first
    const dataModeIndicator = document.getElementById('data-mode-indicator');
    if (dataModeIndicator) {
        dataModeIndicator.textContent = withoutPeriod ? 'Все данные CLM' : 'Данные за период';
    }
    const pieIndicator = document.getElementById('pie-data-mode-indicator');
    if (pieIndicator) {
        pieIndicator.textContent = withoutPeriod ? 'Все данные CLM' : 'Данные за период';
    }

    if (withoutPeriod && getIsInitialData()) {
        console.log("Loading full CLM data...");
        // Load full CLM data
        loadFullClmData(chartData, timestamp, callbacks);
    } else if (!withoutPeriod && !getIsInitialData()) {
        console.log("Restoring filtered data...");
        // Restore filtered data
        restoreFilteredData(chartData, callbacks);
    } else {
        // No data change needed, just update the indicators
        console.log("No data change needed, already in the right mode");

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