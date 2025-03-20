// Log Console Functionality
document.addEventListener('DOMContentLoaded', function() {
    const logConsole = document.getElementById('log-console');
    const logConsoleContainer = document.getElementById('log-console-container');
    const toggleLogConsoleBtn = document.getElementById('toggle-log-console');
    const refreshLogsBtn = document.getElementById('refresh-logs');
    const clearLogsBtn = document.getElementById('clear-logs');
    const autoRefreshCheckbox = document.getElementById('auto-refresh');
    const logLimitSelect = document.getElementById('log-limit');

    // Skip if log console elements don't exist on this page
    if (!logConsole || !toggleLogConsoleBtn) return;

    let logsVisible = true;
    let logRefreshInterval;
    const DEFAULT_REFRESH_INTERVAL = 3000; // 3 seconds

    // Function to toggle log console visibility
    function toggleLogConsole() {
        if (logsVisible) {
            logConsoleContainer.style.display = 'none';
            toggleLogConsoleBtn.textContent = 'Show';
            logsVisible = false;
        } else {
            logConsoleContainer.style.display = 'block';
            toggleLogConsoleBtn.textContent = 'Hide';
            logsVisible = true;
            fetchLogs(); // Refresh logs when showing
        }
    }

    // Function to fetch and display logs
    function fetchLogs() {
        const limit = logLimitSelect.value;
        fetch(`/logs?limit=${limit}`)
            .then(response => response.json())
            .then(logs => {
                // Clear current logs
                logConsole.innerHTML = '';

                // Add each log entry
                logs.forEach(log => {
                    const logEntry = document.createElement('div');
                    logEntry.className = 'log-entry';

                    // Add color classes based on log level
                    if (log.includes(' - ERROR - ')) {
                        logEntry.classList.add('error');
                    } else if (log.includes(' - WARNING - ')) {
                        logEntry.classList.add('warning');
                    } else if (log.includes(' - INFO - ')) {
                        logEntry.classList.add('info');
                    }

                    logEntry.textContent = log;
                    logConsole.appendChild(logEntry);
                });

                // Scroll to bottom
                logConsole.scrollTop = logConsole.scrollHeight;
            })
            .catch(error => {
                console.error('Error fetching logs:', error);
                logConsole.innerHTML += `<div class="log-entry error">Error fetching logs: ${error}</div>`;
            });
    }

    // Function to clear logs
    function clearLogs() {
        logConsole.innerHTML = '';
    }

    // Function to start/stop auto refresh
    function toggleAutoRefresh() {
        if (autoRefreshCheckbox.checked) {
            // Start auto refresh
            logRefreshInterval = setInterval(fetchLogs, DEFAULT_REFRESH_INTERVAL);
        } else {
            // Stop auto refresh
            clearInterval(logRefreshInterval);
        }
    }

    // Initialize with first log fetch
    fetchLogs();

    // Set up auto refresh if checked
    if (autoRefreshCheckbox.checked) {
        logRefreshInterval = setInterval(fetchLogs, DEFAULT_REFRESH_INTERVAL);
    }

    // Add event listeners
    toggleLogConsoleBtn.addEventListener('click', toggleLogConsole);
    refreshLogsBtn.addEventListener('click', fetchLogs);
    clearLogsBtn.addEventListener('click', clearLogs);
    autoRefreshCheckbox.addEventListener('change', toggleAutoRefresh);
    logLimitSelect.addEventListener('change', fetchLogs);

    // Store log console state in localStorage
    const savedLogVisibility = localStorage.getItem('logConsoleVisible');
    if (savedLogVisibility === 'false') {
        toggleLogConsole(); // Hide initially if it was hidden before
    }

    // Save visibility state on toggle
    toggleLogConsoleBtn.addEventListener('click', () => {
        localStorage.setItem('logConsoleVisible', logsVisible);
    });
});