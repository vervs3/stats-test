// ui.js - Dashboard UI management
import { getProjectBudget, calculateProjectedValue } from './utils.js';

/**
 * Setup event listeners for the dashboard UI
 * @param {Function} triggerDataCollectionFn - Function to trigger data collection
 */
function setupEventListeners(triggerDataCollectionFn) {
    // Data collection button
    const collectionBtn = document.getElementById('trigger-collection');
    if (collectionBtn) {
        collectionBtn.addEventListener('click', triggerDataCollectionFn);
    }
}

/**
 * Update UI with fallback data
 */
function updateUIWithFallbackData() {
    console.log("Updating UI with fallback data");

    // Update key metrics
    updateMetrics('actual-time-spent', '950');
    updateMetrics('projected-time-spent', '1100');
    updateMetrics('time-difference', '150', 'success');

    // Update progress bar
    updateProgressBar(950, 18000);
}

/**
 * Update a metric display
 * @param {string} id - Element ID
 * @param {string} value - Value to display
 * @param {string} statusClass - CSS class for status (success/danger)
 */
function updateMetrics(id, value, statusClass) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;

        // Add status class if provided
        if (statusClass) {
            if (statusClass === 'success') {
                element.classList.add('text-success');
                element.classList.remove('text-danger');
            } else if (statusClass === 'danger') {
                element.classList.add('text-danger');
                element.classList.remove('text-success');
            }
        }
    }
}

/**
 * Update progress bar
 * @param {number} value - Current value
 * @param {number} total - Total value
 */
function updateProgressBar(value, total) {
    const progressBar = document.getElementById('time-progress');
    if (progressBar) {
        const percent = Math.min(100, Math.max(0, (value / total) * 100));
        progressBar.style.width = `${percent}%`;
        progressBar.textContent = `${Math.round(percent)}%`;
    }
}

/**
 * Show loading state
 */
function showLoadingState() {
    document.getElementById('last-refresh-time')?.classList.add('text-muted');
}

/**
 * Hide loading state
 */
function hideLoadingState() {
    document.getElementById('last-refresh-time')?.classList.remove('text-muted');
}

/**
 * Show JQL modal
 * @param {string} jql - JQL query
 * @param {string} url - URL to open
 */
function showJqlModal(jql, url) {
    // Get modal elements
    const modal = document.getElementById('jqlModal');
    const jqlText = document.getElementById('jqlQuery');
    const openBtn = document.getElementById('openJiraBtn');

    if (!modal || !jqlText || !openBtn) {
        console.error("Modal elements not found");
        // Fallback - open directly
        window.open(url, '_blank');
        return;
    }

    // Set modal content
    jqlText.value = jql;
    openBtn.href = url;

    // Show modal
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

export {
    setupEventListeners,
    updateUIWithFallbackData,
    updateMetrics,
    updateProgressBar,
    showLoadingState,
    hideLoadingState,
    showJqlModal
};