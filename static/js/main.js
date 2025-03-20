// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    // Enable Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Data source selection handling
    const sourceJiraRadio = document.getElementById('source-jira');
    const sourceClmRadio = document.getElementById('source-clm');
    const jiraSettings = document.getElementById('jira-settings');
    const clmSettings = document.getElementById('clm-settings');

    if (sourceJiraRadio && sourceClmRadio) {
        sourceJiraRadio.addEventListener('change', function() {
            if (this.checked) {
                jiraSettings.classList.remove('d-none');
                clmSettings.classList.add('d-none');
            }
        });

        sourceClmRadio.addEventListener('change', function() {
            if (this.checked) {
                jiraSettings.classList.add('d-none');
                clmSettings.classList.remove('d-none');
            }
        });
    }

    // Show appropriate fields based on selected method (Jira)
    const useFilterRadio = document.getElementById('use-filter');
    const useJqlRadio = document.getElementById('use-jql');
    const filterIdGroup = document.getElementById('filter-id-group');
    const jqlQueryGroup = document.getElementById('jql-query-group');

    // Show appropriate fields based on selected method (CLM)
    const clmFilterIdGroup = document.getElementById('clm-filter-id-group');
    const clmJqlQueryGroup = document.getElementById('clm-jql-query-group');

    if (useFilterRadio && useJqlRadio) {
        useFilterRadio.addEventListener('change', function() {
            if (this.checked) {
                filterIdGroup.classList.remove('d-none');
                jqlQueryGroup.classList.add('d-none');
                clmFilterIdGroup.classList.remove('d-none');
                clmJqlQueryGroup.classList.add('d-none');
            }
        });

        useJqlRadio.addEventListener('change', function() {
            if (this.checked) {
                filterIdGroup.classList.add('d-none');
                jqlQueryGroup.classList.remove('d-none');
                clmFilterIdGroup.classList.add('d-none');
                clmJqlQueryGroup.classList.remove('d-none');
            }
        });
    }

    // Handle reports selection for deletion
    const toggleSelectBtn = document.getElementById('toggle-select-btn');
    const deleteForm = document.getElementById('delete-form');
    const normalView = document.getElementById('normal-view');
    const selectCheckboxes = document.querySelectorAll('.select-checkbox');
    const viewLinks = document.querySelectorAll('.view-link');

    if (toggleSelectBtn && deleteForm && normalView) {
        toggleSelectBtn.addEventListener('click', function() {
            if (deleteForm.style.display === 'none') {
                // Switch to selection mode
                deleteForm.style.display = 'block';
                normalView.style.display = 'none';
                toggleSelectBtn.textContent = 'Cancel';
                toggleSelectBtn.classList.remove('btn-outline-primary');
                toggleSelectBtn.classList.add('btn-outline-secondary');

                // Show checkboxes
                selectCheckboxes.forEach(checkbox => {
                    checkbox.style.display = 'block';
                });

                // Remove stretched link
                viewLinks.forEach(link => {
                    link.classList.remove('stretched-link');
                });
            } else {
                // Switch to normal mode
                deleteForm.style.display = 'none';
                normalView.style.display = 'block';
                toggleSelectBtn.textContent = 'Select';
                toggleSelectBtn.classList.remove('btn-outline-secondary');
                toggleSelectBtn.classList.add('btn-outline-primary');
            }
        });
    }

    // Modal dialog for JQL
    const jqlModal = document.getElementById('jqlModal');
    if (jqlModal) {
        const bsJqlModal = new bootstrap.Modal(jqlModal);
        window.createJiraLink = function(project) {
            // Get parameters for request
            const params = new URLSearchParams();
            const dateFrom = document.querySelector('[data-date-from]')?.getAttribute('data-date-from');
            const dateTo = document.querySelector('[data-date-to]')?.getAttribute('data-date-to');
            const baseJql = document.querySelector('[data-base-jql]')?.getAttribute('data-base-jql');

            if (dateFrom) params.append('date_from', dateFrom);
            if (dateTo) params.append('date_to', dateTo);
            if (baseJql) params.append('base_jql', baseJql);

            // Make request to server for JQL
            fetch(`/jql/project/${project}?${params.toString()}`)
                .then(response => response.json())
                .then(data => {
                    // Fill modal dialog
                    document.getElementById('jqlQuery').value = data.jql;
                    document.getElementById('openJiraBtn').href = data.url;

                    // Show modal dialog
                    bsJqlModal.show();
                })
                .catch(error => {
                    console.error('Error generating JQL:', error);
                    alert('Error creating JQL query');
                });
        };
    }

    // Update status if analysis is running
    const refreshStatus = function() {
        fetch('/status')
            .then(response => response.json())
            .then(data => {
                // If analysis is running, update progress
                if (data.is_running) {
                    const statusMessage = document.getElementById('status-message');
                    const progressBar = document.getElementById('progress-bar');

                    if (statusMessage && progressBar) {
                        statusMessage.textContent = data.status_message;
                        progressBar.style.width = data.progress + '%';
                        progressBar.setAttribute('aria-valuenow', data.progress);
                        progressBar.textContent = data.progress + '%';
                    }

                    // Schedule next update in 1 second
                    setTimeout(refreshStatus, 1000);
                } else {
                    // If analysis is complete, reload page
                    if (document.getElementById('status-message')) {
                        setTimeout(() => { window.location.reload(); }, 1000);
                    }
                }
            })
            .catch(error => {
                console.error('Error fetching status:', error);
                // Even on error, try to update again in 5 seconds
                setTimeout(refreshStatus, 5000);
            });
    };

    // Start status updates if analysis is running
    if (document.querySelector('[data-analysis-running="true"]')) {
        setTimeout(refreshStatus, 1000);
    }
});