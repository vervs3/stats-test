// main.js - Entry point for the dashboard
import { fetchDashboardData, triggerDataCollection } from './api.js';
import { initEmptyCharts, updateDashboardCharts } from './charts.js';
import { updateUIWithFallbackData, setupEventListeners } from './ui.js';
import { updateSummaryStatistics } from './summary-updater.js';


// Initialize dashboard when DOM is loaded
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
    setupEventListeners(triggerDataCollection);

    // Set up auto-refresh
    setupAutoRefresh();

    // Update with fallback data first to ensure something is displayed
    updateUIWithFallbackData();

    // Initialize empty charts as placeholders
    initEmptyCharts();

    // Fetch and display real data
    fetchDashboardData().then(data => {
        if (data) {
            updateDashboardCharts(data);
        }
    });
}

// Set up auto-refresh
function setupAutoRefresh() {
    const refreshInterval = parseInt(document.body.dataset.refreshInterval || '3600');
    if (refreshInterval > 0) {
        console.log(`Setting up auto-refresh every ${refreshInterval} seconds`);
        setInterval(fetchDashboardData, refreshInterval * 1000);
    }
}

// Export functions that might be used by other scripts
export { initDashboard, setupAutoRefresh };