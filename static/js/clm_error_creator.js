/**
 * CLM Error Creator functionality
 */

// Добавим отладочный вывод
console.log('CLM Error Creator JS loaded');

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded in CLM Error Creator JS');

    // Form for creating CLM Errors
    const clmErrorForm = document.getElementById('clm-error-form');
    const createButton = document.getElementById('create-button');
    const createSpinner = document.getElementById('create-spinner');
    const resultsContainer = document.getElementById('results-container');
    const resultsTable = document.getElementById('results-table');

    console.log('Elements found:', {
        clmErrorForm: !!clmErrorForm,
        createButton: !!createButton,
        createSpinner: !!createSpinner,
        resultsContainer: !!resultsContainer,
        resultsTable: !!resultsTable
    });

    // Form for uploading mapping file
    const uploadMappingForm = document.getElementById('upload-mapping-form');
    const uploadButton = document.getElementById('upload-button');
    const uploadSpinner = document.getElementById('upload-spinner');

    // Error modal elements
    const errorModalElement = document.getElementById('errorModal');
    const errorMessage = document.getElementById('error-message');

    // Initialize Bootstrap modal
    let errorModal;
    if (errorModalElement) {
        errorModal = new bootstrap.Modal(errorModalElement);
    }

    // Handle CLM Error form submission
    if (clmErrorForm) {
        console.log('Adding submit event listener to form');

        clmErrorForm.addEventListener('submit', function(e) {
            console.log('Form submit event triggered');
            e.preventDefault();

            // Get input value and trim whitespace
            const issueKeysInput = document.getElementById('issue-keys');
            const issueKeys = issueKeysInput ? issueKeysInput.value.trim() : '';

            console.log('Issue keys to submit:', issueKeys);

            // Validate input
            if (!issueKeys) {
                console.log('No issue keys provided');
                showError('Введите ключи задач Jira');
                return;
            }

            // Show spinner and disable button
            if (createSpinner) createSpinner.classList.remove('d-none');
            if (createButton) createButton.disabled = true;

            // Get form data
            const formData = new FormData();
            formData.append('issue_keys', issueKeys);

            console.log('Sending request to create CLM Errors');

            // Send request
            fetch('/api/create-clm-errors', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                console.log('Response received, status:', response.status);
                return response.json();
            })
            .then(data => {
                console.log('Response data:', data);

                if (data.success) {
                    // Show results container
                    if (resultsContainer) resultsContainer.classList.remove('d-none');

                    // Clear previous results
                    if (resultsTable) resultsTable.innerHTML = '';

                    // Add results to table
                    if (resultsTable) {
                        const results = data.results || {};
                        console.log('Processing results:', results);

                        for (const [issueKey, clmErrorKey] of Object.entries(results)) {
                            const row = document.createElement('tr');

                            // Original issue key
                            const issueCell = document.createElement('td');
                            const issueLink = document.createElement('a');
                            issueLink.href = `https://jira.nexign.com/browse/${issueKey}`;
                            issueLink.target = '_blank';
                            issueLink.textContent = issueKey;
                            issueCell.appendChild(issueLink);
                            row.appendChild(issueCell);

                            // CLM Error key
                            const clmErrorCell = document.createElement('td');
                            if (clmErrorKey) {
                                const clmErrorLink = document.createElement('a');
                                clmErrorLink.href = `https://jira.nexign.com/browse/${clmErrorKey}`;
                                clmErrorLink.target = '_blank';
                                clmErrorLink.textContent = clmErrorKey;
                                clmErrorCell.appendChild(clmErrorLink);
                            } else {
                                clmErrorCell.textContent = 'Не создан';
                            }
                            row.appendChild(clmErrorCell);

                            // Status
                            const statusCell = document.createElement('td');
                            if (clmErrorKey) {
                                statusCell.innerHTML = '<span class="badge bg-success">Успешно</span>';
                            } else {
                                statusCell.innerHTML = '<span class="badge bg-danger">Ошибка</span>';
                            }
                            row.appendChild(statusCell);

                            resultsTable.appendChild(row);
                        }
                    }
                } else {
                    // Show error modal
                    console.log('Error creating CLM Errors:', data.error);
                    showError(data.error || 'Произошла ошибка при создании CLM Error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showError('Произошла ошибка при отправке запроса: ' + error.message);
            })
            .finally(() => {
                console.log('Request completed');
                // Hide spinner and enable button
                if (createSpinner) createSpinner.classList.add('d-none');
                if (createButton) createButton.disabled = false;
            });
        });
    } else {
        console.error('CLM Error form not found!');
    }

    // Handle mapping file upload
    if (uploadMappingForm) {
        uploadMappingForm.addEventListener('submit', function(e) {
            e.preventDefault();

            // Get file
            const fileInput = document.getElementById('mapping-file');
            const file = fileInput ? fileInput.files[0] : null;

            if (!file) {
                showError('Выберите файл для загрузки');
                return;
            }

            // Show spinner and disable button
            if (uploadSpinner) uploadSpinner.classList.remove('d-none');
            if (uploadButton) uploadButton.disabled = true;

            // Create form data
            const formData = new FormData();
            formData.append('mapping_file', file);

            // Send request
            fetch('/api/upload-subsystem-mapping', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Reload page to show updated subsystems
                    window.location.reload();
                } else {
                    // Show error modal
                    showError(data.error || 'Произошла ошибка при загрузке файла');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showError('Произошла ошибка при отправке запроса: ' + error.message);
            })
            .finally(() => {
                // Hide spinner and enable button
                if (uploadSpinner) uploadSpinner.classList.add('d-none');
                if (uploadButton) uploadButton.disabled = false;
            });
        });
    }

    // Function to show error message
    function showError(message) {
        console.error('Error in CLM Error Creator:', message);

        if (errorMessage) {
            errorMessage.textContent = message;
        }

        if (errorModal) {
            errorModal.show();
        } else {
            // Fallback if modal is not available
            alert(message);
        }
    }
});