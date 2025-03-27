// utils.js - Dashboard utility functions

/**
 * Get project budget from DOM
 * @returns {number} Project budget
 */
function getProjectBudget() {
    const progressElement = document.querySelector('.progress');
    return progressElement ? parseInt(progressElement.dataset.budget) || 18000 : 18000;
}

/**
 * Calculate projected value based on current date
 * @param {number} budget - Project budget
 * @returns {number} Projected value
 */
function calculateProjectedValue(budget) {
    // Get current date
    const today = new Date();

    // Project start (Jan 1, 2025)
    const startDate = new Date('2025-01-01');

    // Project end (Dec 31, 2025)
    const endDate = new Date('2025-12-31');

    // Total days in project
    const totalDays = Math.round((endDate - startDate) / (1000 * 60 * 60 * 24)) + 1;

    // Days elapsed so far
    let daysElapsed;
    if (today < startDate) {
        daysElapsed = 0;
    } else if (today > endDate) {
        daysElapsed = totalDays;
    } else {
        daysElapsed = Math.round((today - startDate) / (1000 * 60 * 60 * 24)) + 1;
    }

    // Calculate projected value (linear projection)
    return (budget / totalDays) * daysElapsed;
}

/**
 * Generate color set for charts
 * @param {number} count - Number of colors needed
 * @returns {Object} Object with background and border colors
 */
function createColorSet(count) {
    // Predefined color palette
    const colorPalette = [
        { bg: 'rgba(255, 99, 132, 0.7)', border: 'rgba(255, 99, 132, 1)' },    // Red
        { bg: 'rgba(54, 162, 235, 0.7)', border: 'rgba(54, 162, 235, 1)' },    // Blue
        { bg: 'rgba(255, 206, 86, 0.7)', border: 'rgba(255, 206, 86, 1)' },    // Yellow
        { bg: 'rgba(75, 192, 192, 0.7)', border: 'rgba(75, 192, 192, 1)' },    // Green
        { bg: 'rgba(153, 102, 255, 0.7)', border: 'rgba(153, 102, 255, 1)' },  // Purple
        { bg: 'rgba(255, 159, 64, 0.7)', border: 'rgba(255, 159, 64, 1)' }     // Orange
    ];

    const background = [];
    const border = [];

    // Use palette colors first, then generate additional ones if needed
    for (let i = 0; i < count; i++) {
        if (i < colorPalette.length) {
            background.push(colorPalette[i].bg);
            border.push(colorPalette[i].border);
        } else {
            // Generate additional colors using HSL
            const hue = (i * 137) % 360; // Golden ratio for good distribution
            background.push(`hsla(${hue}, 70%, 60%, 0.7)`);
            border.push(`hsla(${hue}, 70%, 60%, 1)`);
        }
    }

    return { background, border };
}

/**
 * Format date to folder format (YYYYMMDD)
 * @param {string} dateStr - Date string (YYYY-MM-DD)
 * @returns {string} Formatted date (YYYYMMDD)
 */
function formatDateForFolder(dateStr) {
    try {
        const dateObj = new Date(dateStr);
        const year = dateObj.getFullYear();
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const day = String(dateObj.getDate()).padStart(2, '0');
        return `${year}${month}${day}`;
    } catch (e) {
        console.error("Error formatting date:", e);
        return dateStr.replace(/-/g, '');
    }
}

export {
    getProjectBudget,
    calculateProjectedValue,
    createColorSet,
    formatDateForFolder
};