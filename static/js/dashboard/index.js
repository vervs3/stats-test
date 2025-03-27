// index.js - Main entry point that loads all dashboard modules
// Import this file in your HTML to load the dashboard system

// Import main dashboard module
import { initDashboard } from './main.js';

// Initialize the dashboard when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the dashboard page
    if (document.querySelector('.dashboard') !== null ||
        window.location.pathname.includes('dashboard')) {
        // Initialize the dashboard
        initDashboard();
    }
});