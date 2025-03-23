/**
 * CLM Summary Chart Module - Shows summary of CLM-related data
 */
import { createSpecialJQL } from './chart-utils.js';

// Initialize CLM summary chart
export function initClmSummaryChart() {
    const clmDataElement = document.getElementById('clm-data');
    const ctxClmSummary = document.getElementById('clmSummaryChart');

    if (!clmDataElement || !ctxClmSummary) {
        console.log("CLM summary chart not initialized - missing element or data");
        return;
    }

    try {
        const clmData = JSON.parse(clmDataElement.textContent);

        const clmColors = [
            'rgba(75, 192, 192, 0.7)',  // CLM Issues
            'rgba(54, 162, 235, 0.7)',  // EST Issues
            'rgba(153, 102, 255, 0.7)', // Improvement Issues
            'rgba(255, 159, 64, 0.7)',  // Linked Issues
            'rgba(255, 99, 132, 0.7)'   // Filtered Issues
        ];

        const clmChart = new Chart(ctxClmSummary.getContext('2d'), {
            type: 'bar',
            data: {
                labels: clmData.labels,
                datasets: [{
                    label: 'Количество',
                    data: clmData.values,
                    backgroundColor: clmColors,
                    borderColor: clmColors.map(color => color.replace('0.7', '1')),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Количество: ${context.raw}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    },
                    x: {
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45
                        }
                    }
                },
                onClick: (event, activeElements) => {
                    if (activeElements.length === 0) return;

                    const index = activeElements[0].index;
                    const label = clmData.labels[index];

                    // Create JQL based on clicked column
                    let chartType = '';
                    if (label === 'CLM Issues') {
                        chartType = 'clm_issues';
                    } else if (label === 'EST Issues') {
                        chartType = 'est_issues';
                    } else if (label === 'Improvement Issues') {
                        chartType = 'improvement_issues';
                    } else if (label === 'Linked Issues') {
                        chartType = 'linked_issues';
                    } else if (label === 'Filtered Issues') {
                        chartType = 'filtered_issues';
                    }

                    if (chartType) {
                        // Respect the current period toggle
                        const withoutPeriod = document.getElementById('withoutPeriod')?.checked || false;
                        // Use 'all' as project parameter to get all tasks of this type
                        createSpecialJQL('all', chartType, withoutPeriod);
                    }
                }
            }
        });

        console.log("CLM summary chart initialized successfully");
    } catch (error) {
        console.error('Error initializing CLM summary chart:', error);
    }
}