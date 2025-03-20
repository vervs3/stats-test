// Chart functionality for interactive charts
document.addEventListener('DOMContentLoaded', function() {
    // Initialize charts if chart data exists
    const chartDataElement = document.getElementById('chart-data');
    if (!chartDataElement) {
        console.log("No chart data element found");
        return;
    }

    try {
        const chartData = JSON.parse(chartDataElement.textContent);
        if (!chartData) {
            console.log("Chart data element exists but no data found");
            return;
        }

        console.log("Chart data loaded successfully");

        // Initialize CLM summary chart if this is a CLM analysis
        initClmSummaryChart();

        // Function to get colors for charts
        function getChartColors(count) {
            const colors = [];
            for (let i = 0; i < count; i++) {
                // Cycle through colors using golden angle for even distribution
                const hue = (i * 137) % 360;
                colors.push(`hsla(${hue}, 70%, 60%, 0.7)`);
            }
            return colors;
        }

        // Handler for chart clicks based on chart type
        function handleChartClick(event, chartType, activeElements, chart) {
            if (activeElements.length === 0) return;

            const index = activeElements[0].index;
            const project = chart.data.labels[index];
            console.log(`Chart click: ${chartType}, Project: ${project}`);

            // Формирование специфичного JQL запроса в зависимости от типа графика
            if (chartType === 'no_transitions') {
                // Для графика "Открытые задачи со списаниями"
                createSpecialJQL(project, 'open_tasks');
            } else {
                // Для стандартных графиков используем обычную ссылку
                if (typeof createJiraLink === 'function') {
                    createJiraLink(project);
                } else {
                    console.error("createJiraLink function not found");
                }
            }
        }

        // Функция для создания специального JQL запроса
        function createSpecialJQL(project, chartType) {
            // Базовые параметры
            const params = new URLSearchParams();
            const dateFrom = document.querySelector('[data-date-from]')?.getAttribute('data-date-from');
            const dateTo = document.querySelector('[data-date-to]')?.getAttribute('data-date-to');
            const baseJql = document.querySelector('[data-base-jql]')?.getAttribute('data-base-jql');
            const isClm = document.querySelector('[data-source="clm"]') ? 'true' : 'false';

            // Добавляем timestamp анализа для доступа к сохраненным данным
            const timestamp = document.querySelector('[data-timestamp]')?.getAttribute('data-timestamp') ||
                              window.location.pathname.split('/').pop();

            params.append('project', project);
            params.append('chart_type', chartType);
            params.append('is_clm', isClm);
            if (dateFrom) params.append('date_from', dateFrom);
            if (dateTo) params.append('date_to', dateTo);
            if (baseJql) params.append('base_jql', baseJql);
            if (timestamp) params.append('timestamp', timestamp);

            console.log(`Creating special JQL for project: ${project}, chart type: ${chartType}, timestamp: ${timestamp}`);

            // Запрос на сервер для формирования специального JQL
            fetch(`/jql/special?${params.toString()}`)
                .then(response => response.json())
                .then(data => {
                    console.log("Received JQL:", data.jql);

                    // Заполняем модальное окно
                    document.getElementById('jqlQuery').value = data.jql;
                    document.getElementById('openJiraBtn').href = data.url;

                    // Показываем модальное окно
                    const bsJqlModal = new bootstrap.Modal(document.getElementById('jqlModal'));
                    bsJqlModal.show();
                })
                .catch(error => {
                    console.error('Error generating special JQL:', error);
                    alert('Ошибка при формировании JQL запроса');

                    // Если произошла ошибка, используем обычную ссылку
                    if (typeof createJiraLink === 'function') {
                        createJiraLink(project);
                    }
                });
        }

        // Common chart options
        const commonOptions = {
            responsive: true,
            maintainAspectRatio: false,
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
            layout: {
                padding: {
                    left: 10,
                    right: 10,
                    top: 0,
                    bottom: 20
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        boxWidth: 15,
                        padding: 10
                    }
                }
            }
        };

        // Comparison chart (estimate vs. time spent) с возможностью фильтрации
        const ctxComparison = document.getElementById('comparisonChart');
        if (ctxComparison && chartData.project_estimates && chartData.project_time_spent) {
            console.log("Initializing comparison chart with filtering");

            // Collect all unique projects
            const allProjects = [...new Set([
                ...Object.keys(chartData.project_estimates),
                ...Object.keys(chartData.project_time_spent)
            ])];

            if (allProjects.length > 0) {
                // Sort projects by sum of estimate and time spent (descending)
                allProjects.sort((a, b) => {
                    const aTotal = (chartData.project_estimates[a] || 0) + (chartData.project_time_spent[a] || 0);
                    const bTotal = (chartData.project_estimates[b] || 0) + (chartData.project_time_spent[b] || 0);
                    return bTotal - aTotal;
                });

                // Сохраняем полный список проектов для использования при фильтрации
                const fullProjectsList = [...allProjects];

                // Инициализация состояния исключенных проектов
                let excludedProjects = new Set();

                // Создаем контейнер для элементов фильтрации над графиком
                const chartContainer = ctxComparison.closest('.chart-container');
                const filterContainer = document.createElement('div');
                filterContainer.className = 'mb-3 chart-filter-container';
                filterContainer.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <button class="btn btn-sm btn-outline-primary toggle-filter-btn">Показать/скрыть фильтр</button>
                        <div class="filter-actions" style="display: none;">
                            <button class="btn btn-sm btn-outline-success select-all-btn">Выбрать все</button>
                            <button class="btn btn-sm btn-outline-danger deselect-all-btn">Снять все</button>
                            <button class="btn btn-sm btn-outline-warning reset-filter-btn">Сбросить</button>
                        </div>
                    </div>
                    <div class="project-filter-options" style="display: none; max-height: 200px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; border-radius: 4px;">
                    </div>
                `;

                if (chartContainer && chartContainer.parentNode) {
                    chartContainer.parentNode.insertBefore(filterContainer, chartContainer);
                } else {
                    ctxComparison.parentNode.insertBefore(filterContainer, ctxComparison);
                }

                // Добавляем чекбоксы для проектов
                const filterOptions = filterContainer.querySelector('.project-filter-options');

                function populateFilterOptions() {
                    filterOptions.innerHTML = ''; // Очищаем содержимое

                    // Создаем чекбоксы для проектов - выводим ВСЕ проекты, включая малозначимые
                    fullProjectsList.forEach((project, index) => {
                        const isExcluded = excludedProjects.has(project);
                        const rowDiv = document.createElement('div');
                        rowDiv.className = 'form-check';
                        rowDiv.innerHTML = `
                            <input class="form-check-input project-checkbox" type="checkbox" value="${project}" id="project-${index}" ${isExcluded ? '' : 'checked'}>
                            <label class="form-check-label" for="project-${index}">${project}</label>
                        `;
                        filterOptions.appendChild(rowDiv);
                    });

                    // Добавляем обработчики событий для чекбоксов
                    const checkboxes = filterOptions.querySelectorAll('.project-checkbox');
                    checkboxes.forEach(checkbox => {
                        checkbox.addEventListener('change', function() {
                            const project = this.value;
                            if (this.checked) {
                                excludedProjects.delete(project);
                            } else {
                                excludedProjects.add(project);
                            }
                            updateChart();
                        });
                    });
                }

                // Заполняем опции фильтра
                populateFilterOptions();

                // Обработчики для кнопок фильтра
                const toggleFilterBtn = filterContainer.querySelector('.toggle-filter-btn');
                const filterActions = filterContainer.querySelector('.filter-actions');
                const selectAllBtn = filterContainer.querySelector('.select-all-btn');
                const deselectAllBtn = filterContainer.querySelector('.deselect-all-btn');
                const resetFilterBtn = filterContainer.querySelector('.reset-filter-btn');

                toggleFilterBtn.addEventListener('click', function() {
                    const filterOptions = filterContainer.querySelector('.project-filter-options');
                    const isVisible = filterOptions.style.display !== 'none';
                    filterOptions.style.display = isVisible ? 'none' : 'block';
                    filterActions.style.display = isVisible ? 'none' : 'flex';
                });

                selectAllBtn.addEventListener('click', function() {
                    const checkboxes = filterOptions.querySelectorAll('.project-checkbox');
                    checkboxes.forEach(checkbox => {
                        checkbox.checked = true;
                    });
                    excludedProjects.clear();
                    updateChart();
                });

                deselectAllBtn.addEventListener('click', function() {
                    const checkboxes = filterOptions.querySelectorAll('.project-checkbox');
                    checkboxes.forEach(checkbox => {
                        checkbox.checked = false;
                    });
                    excludedProjects = new Set(fullProjectsList);
                    updateChart();
                });

                resetFilterBtn.addEventListener('click', function() {
                    excludedProjects.clear();
                    populateFilterOptions();
                    updateChart();
                });

                // Создаем пустой график, который будет обновляться
                let comparisonChart = null;

                // Функция для обновления данных графика на основе выбранных проектов
                function updateChart() {
                    // Фильтруем проекты, исключая те, что отмечены для исключения
                    const filteredProjects = fullProjectsList.filter(project => !excludedProjects.has(project));

                    // Ограничиваем количество проектов для читаемости (можно увеличить)
                    const displayProjects = filteredProjects.slice(0, 30);

                    const estimateData = displayProjects.map(project => chartData.project_estimates[project] || 0);
                    const timeSpentData = displayProjects.map(project => chartData.project_time_spent[project] || 0);

                    // Если график уже существует, обновляем его данные
                    if (comparisonChart) {
                        comparisonChart.data.labels = displayProjects;
                        comparisonChart.data.datasets[0].data = estimateData;
                        comparisonChart.data.datasets[1].data = timeSpentData;
                        comparisonChart.update();
                    } else {
                        // Создаем новый график
                        comparisonChart = new Chart(ctxComparison.getContext('2d'), {
                            type: 'bar',
                            data: {
                                labels: displayProjects,
                                datasets: [
                                    {
                                        label: 'Исходная оценка (часы)',
                                        data: estimateData,
                                        backgroundColor: 'rgba(54, 162, 235, 0.7)',
                                        borderColor: 'rgba(54, 162, 235, 1)',
                                        borderWidth: 1
                                    },
                                    {
                                        label: 'Затраченное время (часы)',
                                        data: timeSpentData,
                                        backgroundColor: 'rgba(255, 99, 132, 0.7)',
                                        borderColor: 'rgba(255, 99, 132, 1)',
                                        borderWidth: 1
                                    }
                                ]
                            },
                            options: {
                                ...commonOptions,
                                onClick: (event, activeElements) => {
                                    if (activeElements.length === 0) return;

                                    const index = activeElements[0].index;
                                    const project = displayProjects[index];
                                    console.log(`Chart click: comparison, Project: ${project}`);

                                    // Use the same special JQL for CLM mode
                                    const isClmAnalysis = !!document.querySelector('[data-source="clm"]');
                                    if (isClmAnalysis) {
                                        createSpecialJQL(project, 'project_issues');
                                    } else if (typeof createJiraLink === 'function') {
                                        createJiraLink(project);
                                    } else {
                                        console.error("createJiraLink function not found");
                                    }
                                }
                            }
                        });
                    }
                }

                // Инициализируем график с полным набором данных
                updateChart();
            } else {
                console.log("No projects with estimates or time spent");
            }
        } else {
            console.log("Comparison chart not initialized - missing element or data");
        }

        // No transitions tasks chart (переименованные в "Открытые задачи со списаниями")
        const ctxNoTrans = document.getElementById('noTransitionsChart');
        if (ctxNoTrans && chartData.special_charts && chartData.special_charts.no_transitions) {
            console.log("Initializing No Transitions Chart (renamed to Open Tasks with Worklogs)");

            const noTransData = chartData.special_charts.no_transitions;
            const noTransLabels = Object.keys(noTransData.by_project || {});

            // Only create the chart if we have data
            if (noTransLabels.length > 0) {
                const noTransValues = noTransLabels.map(project => noTransData.by_project[project] || 0);
                const noTransColors = getChartColors(noTransLabels.length);

                try {
                    const noTransChart = new Chart(ctxNoTrans.getContext('2d'), {
                        type: 'bar',
                        data: {
                            labels: noTransLabels,
                            datasets: [{
                                label: 'Количество задач',
                                data: noTransValues,
                                backgroundColor: noTransColors,
                                borderColor: noTransColors.map(color => color.replace('0.7', '1')),
                                borderWidth: 1
                            }]
                        },
                        options: {
                            ...commonOptions,
                            onClick: (event, activeElements) => {
                                handleChartClick(event, 'no_transitions', activeElements, noTransChart);
                            }
                        }
                    });
                } catch (err) {
                    console.error("Error creating no transitions chart:", err);
                }
            } else {
                console.log("No transitions chart has no data");
            }
        } else {
            console.log("No transitions chart not initialized - missing element or data");
        }

        // Projects Pie Chart (переименованный в "Распределение задач по проектам")
        const ctxProjectsPie = document.getElementById('projectsPieChart');
        if (ctxProjectsPie && chartData.project_counts && Object.keys(chartData.project_counts).length > 0) {
            console.log("Initializing projects pie chart");

            // Сортируем проекты по количеству задач (от большего к меньшему)
            const sortedProjects = Object.entries(chartData.project_counts)
                .sort((a, b) => b[1] - a[1]);

            // Возьмем топ-20 проектов, остальные объединим в "Другие" (увеличено с 10 до 20)
            const TOP_PROJECTS = 20;
            const topProjects = sortedProjects.slice(0, TOP_PROJECTS);
            const otherProjects = sortedProjects.slice(TOP_PROJECTS);

            let labels = topProjects.map(item => item[0]);
            let values = topProjects.map(item => item[1]);

            // Если есть другие проекты, добавляем их как одну категорию
            if (otherProjects.length > 0) {
                const otherValue = otherProjects.reduce((sum, item) => sum + item[1], 0);
                labels.push('Другие');
                values.push(otherValue);
            }

            const pieColors = getChartColors(labels.length);

            try {
                const pieChart = new Chart(ctxProjectsPie.getContext('2d'), {
                    type: 'pie',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: values,
                            backgroundColor: pieColors,
                            borderColor: pieColors.map(color => color.replace('0.7', '1')),
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'right',
                                labels: {
                                    boxWidth: 15,
                                    padding: 10
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const label = context.label || '';
                                        const value = context.parsed || 0;
                                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                        const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
                                        return `${label}: ${value} задач (${percentage}%)`;
                                    }
                                }
                            }
                        },
                        onClick: (event, activeElements) => {
                            if (activeElements.length > 0) {
                                const index = activeElements[0].index;
                                const project = labels[index];

                                // Не открываем Jira для категории "Другие"
                                if (project !== 'Другие') {
                                    // Use the same special JQL for CLM mode
                                    const isClmAnalysis = !!document.querySelector('[data-source="clm"]');
                                    if (isClmAnalysis) {
                                        createSpecialJQL(project, 'project_issues');
                                    } else {
                                        handleChartClick(event, 'pie', activeElements, pieChart);
                                    }
                                } else {
                                    console.log("Clicked on 'Others' category - no action");
                                }
                            }
                        }
                    }
                });
            } catch (err) {
                console.error("Error creating projects pie chart:", err);
            }
        } else {
            console.log("Projects pie chart not initialized - missing element or data");
        }
    } catch (error) {
        console.error('Error initializing charts:', error);
    }

    // Function to initialize CLM summary chart
    function initClmSummaryChart() {
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
                    // Добавляем обработчик клика на графике
                    onClick: (event, activeElements) => {
                        if (activeElements.length === 0) return;

                        const index = activeElements[0].index;
                        const label = clmData.labels[index];

                        // Создаем JQL в зависимости от того, на какой столбец нажали
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
                            // Используем 'all' как параметр project чтобы получить все задачи данного типа
                            createSpecialJQL('all', chartType);
                        }
                    }
                }
            });

            console.log("CLM summary chart initialized successfully");
        } catch (error) {
            console.error('Error initializing CLM summary chart:', error);
        }
    }
});